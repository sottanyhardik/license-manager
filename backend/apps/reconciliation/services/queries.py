# reconciliation/services/queries.py
"""
Detection queries for the BOE / Invoice Reconciliation panel (Phase 1).

Business rule: One physical import may generate multiple documents, but it
must produce exactly one licence debit.

Every function here is READ-ONLY (never writes to the DB) and returns a
plain list of dicts (or a single summary dict) built from the existing
`trade` / `bill_of_entry` / `license` models — there is no new
source-of-truth data here, only detection of where the rule above is
currently violated or unlinked.

NOTE (Hidden BOEs / previous-owner utilisation, see
`apps.bill_of_entry.models.RowDetails.is_hidden`): the `RowDetails`
queries in this module deliberately do NOT exclude hidden rows. A hidden
BOE is still a real, physical BOE that was genuinely filed — hiding it
only means "exclude from THIS licence's balance/financial figures", never
"pretend it doesn't exist." Reconciliation matching/audit here is
concerned with whether a document trail is internally consistent, not
with whose balance it counts toward, so hidden BOEs must keep
participating in it exactly as before. Do NOT "fix" this in a future PR.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from itertools import combinations

from django.conf import settings
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT, DEC_0
from apps.trade.models import LicenseTrade, LicenseTradeLine

# Every direction the trade form treats as "BOE-eligible" — i.e. everything
# except PURCHASE (see frontend/src/pages/TradeForm.tsx's
# `formData.direction !== 'PURCHASE'` condition). This matches the set used
# by `LicenseImportItemSerializer.get_billed_no_boe` and the trade form's
# BOE-attachment UI; it is intentionally broader than the balance
# calculator's `direction='SALE'`-only filter (calculate_trade), which is
# concerned only with what actually debits a licence.
NON_PURCHASE_DIRECTIONS = ~Q(direction=LicenseTrade.DIR_PURCHASE)
# Same condition, expressed relative to a `LicenseTradeLine` queryset
# (traversing the `trade` FK) rather than a `LicenseTrade` queryset directly.
NON_PURCHASE_TRADE_LINE_DIRECTIONS = ~Q(trade__direction=LicenseTrade.DIR_PURCHASE)

# Directions where "us" is on the `to_company` side of the trade (we are the
# buyer) — see TradeForm.tsx's `isPurchaseType` ternary for
# `handlePrefillInvoiceNumber`. For these, the external counterparty is
# `from_company`; for every other direction (SALE / COMMISSION_SALE), "us"
# is `from_company` and the counterparty is `to_company`.
_BUYER_SIDE_DIRECTIONS = {LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE}


def _counterparty_name(trade: LicenseTrade) -> str | None:
    """External counterparty company name for a trade, direction-aware."""
    company = trade.from_company if trade.direction in _BUYER_SIDE_DIRECTIONS else trade.to_company
    return company.name if company else None


def _sr_number_label(item) -> str | None:
    return str(item) if item is not None else None


def _license_number(item) -> str | None:
    if item is not None and item.license_id:
        return item.license.license_number
    return None


# ---------------------------------------------------------------------------
# 1. Missing BOE
# ---------------------------------------------------------------------------

def missing_boe() -> list[dict]:
    """
    Row-level version of `get_billed_no_boe`
    (`apps.license.serializers.license`:238-264): one row per
    `LicenseTradeLine` on a BOE-eligible trade (`NON_PURCHASE_DIRECTIONS`)
    whose parent trade has no BOE linked at all (`trade.boes` empty).
    """
    lines = (
        LicenseTradeLine.objects
        .filter(NON_PURCHASE_TRADE_LINE_DIRECTIONS, trade__boes__isnull=True)
        .select_related(
            "trade", "trade__from_company", "trade__to_company",
            "sr_number", "sr_number__license",
        )
        .order_by("-trade__invoice_date", "-trade_id")
    )
    return [
        {
            "trade_line_id": line.id,
            "trade_id": line.trade_id,
            "invoice_number": line.trade.invoice_number,
            "invoice_date": line.trade.invoice_date,
            "counterparty": _counterparty_name(line.trade),
            "cif_fc": line.cif_fc,
            "qty_kg": line.qty_kg,
            "license_number": _license_number(line.sr_number),
            "sr_number_label": _sr_number_label(line.sr_number),
        }
        for line in lines
    ]


# ---------------------------------------------------------------------------
# 2. Missing Invoice
# ---------------------------------------------------------------------------

def missing_invoice() -> list[dict]:
    """
    BOEs with no invoice number stamped — the exact `invoice_no` condition
    `bill_of_entry/views/boe.py`'s `available_for_trade=true` handling uses
    (~line 157): `Q(invoice_no__isnull=True) | Q(invoice_no='')`.

    Excludes BOEs that have been explicitly resolved via the Licence Balance
    Workspace's "mark as external invoice" action (an active
    `ExternalInvoiceLink` on any of the BOE's debit rows) — those have a
    real, user-confirmed invoice reference even though it isn't a system
    `LicenseTradeLine`, so they shouldn't keep showing up as unresolved.
    """
    from apps.reconciliation.models import ExternalInvoiceLink

    boes = (
        BillOfEntryModel.objects
        .filter(Q(invoice_no__isnull=True) | Q(invoice_no=""))
        .exclude(
            item_details__external_invoice_links__status=ExternalInvoiceLink.STATUS_ACTIVE,
            item_details__external_invoice_links__is_current=True,
        )
        .select_related("company", "port")
        .prefetch_related(
            "item_details", "item_details__sr_number", "item_details__sr_number__license",
        )
        .order_by("-bill_of_entry_date")
    )
    return [
        {
            "boe_id": boe.id,
            "bill_of_entry_number": boe.bill_of_entry_number,
            "bill_of_entry_date": boe.bill_of_entry_date,
            "total_cif_fc": boe.get_total_fc,
            "total_quantity": boe.get_total_quantity,
            "license_numbers": boe.get_licenses,
        }
        for boe in boes
    ]


# ---------------------------------------------------------------------------
# 3. Duplicate Debits (the literal double-debit bug scenario)
# ---------------------------------------------------------------------------

def duplicate_debits() -> list[dict]:
    """
    The double-debit scenario the calculator deliberately leaves
    unresolved absent an explicit allocation (see
    `LicenseBalanceCalculator.calculate_debit`'s docstring): a SALE
    `LicenseTradeLine` debits a `sr_number`, AND a `RowDetails` DEBIT row
    debits the SAME `sr_number`, with no `InvoiceBOEAllocation` tying the
    two together. Both amounts are still counted today — this is a DATA
    problem for an operator to resolve (create an allocation via the
    reconciliation workbench, or ignore), not something the calculator
    should silently guess at.

    Phase A update: `calculate_debit()`'s exclusion is now ALLOCATION-
    DRIVEN, not BOE-linkage-driven -- merely having this BOE in the
    trade's `boes` M2M no longer excludes anything on its own. So "already
    excluded" here means "an ACTIVE, current `InvoiceBOEAllocation` row
    exists for this EXACT (trade_line, row_details) pair" -- matching
    `calculate_debit()`'s real exclusion condition -- rather than the
    former "row.bill_of_entry_id is in trade.boes" check, which tested a
    BOE-level linkage the calculator no longer reads.

    Batched as three queries (SALE lines, their sr_numbers' debit rows,
    and the allocated (trade_line, row_details) pairs) plus an in-memory
    join, rather than a query per trade line, to avoid N+1s over what
    could be a large `RowDetails` table.
    """
    from apps.reconciliation.models import InvoiceBOEAllocation

    sale_lines = list(
        LicenseTradeLine.objects
        .filter(trade__direction=LicenseTrade.DIR_SALE)
        .select_related("trade", "sr_number", "sr_number__license")
    )
    if not sale_lines:
        return []

    sr_ids = {line.sr_number_id for line in sale_lines}
    debit_rows_by_sr: dict[int, list[RowDetails]] = defaultdict(list)
    for row in (
        RowDetails.objects
        .filter(sr_number_id__in=sr_ids, transaction_type=DEBIT)
        .select_related("bill_of_entry")
    ):
        debit_rows_by_sr[row.sr_number_id].append(row)

    trade_line_ids = [line.id for line in sale_lines]
    allocated_pairs: set[tuple[int, int]] = set(
        InvoiceBOEAllocation.objects
        .filter(
            trade_line_id__in=trade_line_ids,
            status=InvoiceBOEAllocation.STATUS_ACTIVE,
            is_current=True,
        )
        .values_list("trade_line_id", "row_details_id")
    )

    results: list[dict] = []
    for line in sale_lines:
        for row in debit_rows_by_sr.get(line.sr_number_id, []):
            if row.bill_of_entry_id is None:
                # No BOE to reconcile against at all -- not a duplicate-
                # debit candidate (unrelated data anomaly, same as before).
                continue
            if (line.id, row.id) in allocated_pairs:
                # Already excluded by calculate_debit()'s allocation-driven
                # exclusion (an ACTIVE InvoiceBOEAllocation exists for this
                # exact trade_line/row_details pair) — not a duplicate in
                # practice.
                continue
            invoice_debit = line.cif_fc or DEC_0
            boe_debit = row.cif_fc or DEC_0
            results.append({
                "sr_number_id": line.sr_number_id,
                "sr_number_label": _sr_number_label(line.sr_number),
                "license_number": _license_number(line.sr_number),
                "trade_id": line.trade_id,
                "invoice_number": line.trade.invoice_number,
                "boe_id": row.bill_of_entry_id,
                "bill_of_entry_number": row.bill_of_entry.bill_of_entry_number if row.bill_of_entry else None,
                "invoice_debit": invoice_debit,
                "boe_debit": boe_debit,
                "difference": abs(invoice_debit - boe_debit),
            })
    return results


# ---------------------------------------------------------------------------
# 4. Duplicate BOEs (literal duplicate documents)
# ---------------------------------------------------------------------------

def duplicate_boes() -> list[dict]:
    """
    Literal duplicate BOE *records* (the same physical document entered
    twice) — a separate concern from `duplicate_debits()` above, which
    feeds the "Merge" action (reuses the existing `merge_boe` service, see
    `apps.bill_of_entry.services.boe_service.merge_boe`).

    Exact `(bill_of_entry_number, bill_of_entry_date)` collisions are
    already prevented by `BillOfEntryModel.Meta.unique_together`, so this
    detects NEAR-duplicates instead: same company + port + date, a
    DIFFERENT bill_of_entry_number, and near-identical total CIF (within
    `settings.RECONCILIATION_CIF_TOLERANCE`).
    """
    tolerance: Decimal = settings.RECONCILIATION_CIF_TOLERANCE

    rows = BillOfEntryModel.objects.filter(
        company__isnull=False, port__isnull=False, bill_of_entry_date__isnull=False,
    ).values("id", "company_id", "port_id", "bill_of_entry_date", "bill_of_entry_number")

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["company_id"], row["port_id"], row["bill_of_entry_date"])].append(row)

    candidate_pairs = []
    candidate_ids: set[int] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        for a, b in combinations(group, 2):
            if a["bill_of_entry_number"] == b["bill_of_entry_number"]:
                continue  # would already be blocked by the DB unique constraint
            candidate_pairs.append((a, b))
            candidate_ids.add(a["id"])
            candidate_ids.add(b["id"])

    if not candidate_pairs:
        return []

    totals = {
        boe.id: boe.get_total_fc
        for boe in BillOfEntryModel.objects.filter(id__in=candidate_ids)
    }

    results = []
    for a, b in candidate_pairs:
        diff = abs(totals[a["id"]] - totals[b["id"]])
        if diff <= tolerance:
            results.append({
                "boe_id_a": a["id"],
                "bill_of_entry_number_a": a["bill_of_entry_number"],
                "boe_id_b": b["id"],
                "bill_of_entry_number_b": b["bill_of_entry_number"],
                "reason": (
                    f"Same company/port/date, CIF difference {diff} "
                    f"within tolerance ({tolerance})"
                ),
            })
    return results


# ---------------------------------------------------------------------------
# 5/6. CIF / Quantity comparison
# ---------------------------------------------------------------------------

def _linked_trade_comparison(*, trade_field: str, boe_field: str, tolerance: Decimal) -> list[dict]:
    """
    Shared implementation for `cif_comparison()` / `qty_comparison()`: for
    every trade with `boes` linked, compare
    `Sum(LicenseTradeLine.<trade_field>)` against
    `Sum(RowDetails.<boe_field>)` (DEBIT rows only, on the linked BOEs),
    flagging where the absolute difference exceeds `tolerance`.

    Three queries total regardless of table size: trades (+ prefetch
    `boes`), a grouped sum of trade-line amounts, and a grouped sum of BOE
    debit-row amounts — never one query per trade.
    """
    trades = list(
        LicenseTrade.objects
        .filter(boes__isnull=False)
        .distinct()
        .prefetch_related("boes")
    )
    if not trades:
        return []

    trade_ids = [t.id for t in trades]
    invoice_totals = {
        row["trade_id"]: row["total"]
        for row in (
            LicenseTradeLine.objects
            .filter(trade_id__in=trade_ids)
            .values("trade_id")
            .annotate(total=Coalesce(Sum(trade_field), Value(DEC_0), output_field=DecimalField()))
        )
    }

    boe_ids = {boe.id for trade in trades for boe in trade.boes.all()}
    boe_totals = {
        row["bill_of_entry_id"]: row["total"]
        for row in (
            RowDetails.objects
            .filter(bill_of_entry_id__in=boe_ids, transaction_type=DEBIT)
            .values("bill_of_entry_id")
            .annotate(total=Coalesce(Sum(boe_field), Value(DEC_0), output_field=DecimalField()))
        )
    }

    results = []
    for trade in trades:
        boes = list(trade.boes.all())
        boe_side_total = sum((boe_totals.get(boe.id, DEC_0) for boe in boes), DEC_0)
        invoice_side_total = invoice_totals.get(trade.id, DEC_0)
        difference = invoice_side_total - boe_side_total
        if abs(difference) > tolerance:
            results.append({
                "trade_id": trade.id,
                "invoice_number": trade.invoice_number,
                "boe_numbers": [boe.bill_of_entry_number for boe in boes],
                "invoice_total": invoice_side_total,
                "boe_total": boe_side_total,
                "difference": difference,
            })
    return results


def cif_comparison() -> list[dict]:
    """Invoice CIF vs linked-BOE debit CIF, flagged beyond `RECONCILIATION_CIF_TOLERANCE`."""
    return _linked_trade_comparison(
        trade_field="cif_fc", boe_field="cif_fc",
        tolerance=settings.RECONCILIATION_CIF_TOLERANCE,
    )


def qty_comparison() -> list[dict]:
    """Invoice quantity vs linked-BOE debit quantity, flagged beyond `RECONCILIATION_QTY_TOLERANCE`."""
    return _linked_trade_comparison(
        trade_field="qty_kg", boe_field="qty",
        tolerance=settings.RECONCILIATION_QTY_TOLERANCE,
    )


# ---------------------------------------------------------------------------
# 6/7. Multi-BOE / multi-invoice
# ---------------------------------------------------------------------------

def multi_boe_per_invoice() -> list[dict]:
    """Trades linking more than one BOE (`trade.boes.count() > 1`)."""
    trades = (
        LicenseTrade.objects
        .annotate(boe_count=Count("boes", distinct=True))
        .filter(boe_count__gt=1)
        .prefetch_related("boes")
    )
    return [
        {
            "trade_id": trade.id,
            "invoice_number": trade.invoice_number,
            "boe_numbers": [boe.bill_of_entry_number for boe in trade.boes.all()],
        }
        for trade in trades
    ]


def multi_invoice_per_boe() -> list[dict]:
    """BOEs linked from more than one trade (`boe.license_trades.count() > 1`)."""
    boes = (
        BillOfEntryModel.objects
        .annotate(trade_count=Count("license_trades", distinct=True))
        .filter(trade_count__gt=1)
        .prefetch_related("license_trades")
    )
    return [
        {
            "boe_id": boe.id,
            "bill_of_entry_number": boe.bill_of_entry_number,
            "invoice_numbers": [trade.invoice_number for trade in boe.license_trades.all()],
        }
        for boe in boes
    ]


# ---------------------------------------------------------------------------
# 8. Dashboard summary
# ---------------------------------------------------------------------------

def summary() -> dict:
    """Dashboard counter cards, aggregating the detection queries above."""
    total_boe = BillOfEntryModel.objects.count()
    total_import_invoices = (
        LicenseTrade.objects
        .filter(NON_PURCHASE_DIRECTIONS)
        .exclude(invoice_number="")
        .count()
    )

    cif_flags = cif_comparison()
    dup_debit_rows = duplicate_debits()
    flagged_trade_ids = (
        {row["trade_id"] for row in cif_flags} | {row["trade_id"] for row in dup_debit_rows}
    )

    matched = (
        LicenseTrade.objects
        .filter(NON_PURCHASE_DIRECTIONS, boes__isnull=False)
        .exclude(id__in=flagged_trade_ids)
        .distinct()
        .count()
    )

    missing_boe_rows = missing_boe()
    unmatched_invoice = len({row["trade_id"] for row in missing_boe_rows})
    unmatched_boe = len(missing_invoice())

    cif_difference = sum((row["difference"] for row in cif_flags), DEC_0)

    return {
        "total_boe": total_boe,
        "total_import_invoices": total_import_invoices,
        "matched": matched,
        "unmatched_boe": unmatched_boe,
        "unmatched_invoice": unmatched_invoice,
        "duplicate_debits": len(dup_debit_rows),
        "cif_difference": cif_difference,
    }
