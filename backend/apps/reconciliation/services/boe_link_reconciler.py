# reconciliation/services/boe_link_reconciler.py
"""
Reconciles the legacy `LicenseTrade.boes` ManyToManyField (a reference-only
BOE attachment on a SALE trade, edited from `TradeForm.tsx`) against the real
accounting ledger, `InvoiceBOEAllocation`.

Business problem this closes: `LicenseBalanceCalculator.calculate_trade()`
counts every SALE `LicenseTradeLine.cif_fc` unconditionally, while
`calculate_debit()` only excludes a BOE row's contributed CIF when an ACTIVE,
current `InvoiceBOEAllocation` exists for it. `trade.boes` has never fed that
exclusion, so a SALE trade line whose goods came from an attached BOE, but
which was never explicitly allocated, gets debited TWICE: once as the raw BOE
row, once as the trade row. See `apps.reconciliation.services.allocation_service`
for the allocation ledger itself.

This module is the ONE place that decides whether a `trade.boes` link should
become a real `InvoiceBOEAllocation` — used by the one-time backfill command
(`backfill_boe_allocations`), the read-only diagnostic
(`check_allocation_health`), the live trade-edit hook (Phase 4), and the
Warnings builder. Matching is deliberately conservative: it only ever
auto-creates an allocation for an UNAMBIGUOUS 1:1 match (exactly one
candidate `RowDetails`, both CIF and quantity within the existing
reconciliation tolerances) — anything else is left untouched and reported so
a human decides, never guessed.

NOTE (Hidden BOEs / previous-owner utilisation, see
`apps.bill_of_entry.models.OTH_INVOICE_MARKER`): `find_boe_allocation_
candidates` below EXCLUDES hidden BOEs (`invoice_no == OTH_INVOICE_MARKER`)
— the Pending BOE rule: a BOE marked as belonging to a previous owner must
never surface as an invoice-matching candidate/suggestion, matching entry
elsewhere. This is a deliberate reversal of this module's earlier
position (when hiding was RowDetails-row-scoped, a hidden row could still
legitimately be a real document eligible for linking) — hiding is now
BOE-level, so a hidden BOE is a previous-owner document end to end, never
eligible for matching against OUR trades.
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.constants import DEBIT, DEC_0
from apps.core.utils.decimal_utils import to_decimal


def find_boe_allocation_candidates(trade_line):
    """
    Candidate `RowDetails` debit rows for `trade_line`: on a BOE attached to
    the trade via the legacy `.boes` link, on the SAME licence item
    (`sr_number`), with some remaining invoice-side capacity left. Ordinarily
    a single candidate; more than one means the match is ambiguous and must
    not be auto-resolved.
    """
    from apps.bill_of_entry.models import RowDetails, OTH_INVOICE_MARKER
    from apps.reconciliation.services.allocation_service import remaining_for_row_details_invoice_side

    rows = (
        RowDetails.objects.filter(
            bill_of_entry__in=trade_line.trade.boes.all(),
            sr_number_id=trade_line.sr_number_id,
            transaction_type=DEBIT,
        )
        # Pending BOE rule: previous-owner BOEs are never eligible
        # candidates for invoice matching — see module docstring.
        .exclude(bill_of_entry__invoice_no=OTH_INVOICE_MARKER)
        .select_related("bill_of_entry")
    )
    return [row for row in rows if remaining_for_row_details_invoice_side(row)[1] > DEC_0]


def reconcile_trade_boe_links(trade, *, user=None, dry_run=False) -> list[dict]:
    """
    For every SALE `LicenseTradeLine` on `trade` still carrying unallocated
    CIF, try to match it to exactly one `RowDetails` row from `trade.boes`
    and, when unambiguous and within tolerance, create the corresponding
    `InvoiceBOEAllocation` (unless `dry_run=True`, which reports what WOULD
    happen without writing anything).

    Returns one report dict per examined trade line:
    `{license_id, trade_id, invoice_number, trade_line_id, boe_numbers, status, detail}`,
    `status` one of:
      - `"auto_migrated"` — matched and (unless dry_run) allocated.
      - `"no_match"` — no candidate `RowDetails` found.
      - `"ambiguous"` — more than one candidate; needs manual review.
      - `"mismatch"` — exactly one candidate but CIF/qty differ beyond
        tolerance, or the allocation service rejected it (e.g. a race
        consumed the remaining capacity first).

    Trade lines that already have no remaining CIF (fully allocated, or a
    PURCHASE trade) are skipped entirely — they don't need reconciling.
    """
    from apps.reconciliation.services.allocation_service import (
        create_invoice_boe_allocation,
        remaining_for_row_details_invoice_side,
        remaining_for_trade_line,
    )

    results: list[dict] = []
    if trade.direction != trade.DIR_SALE:
        return results

    cif_tolerance = settings.RECONCILIATION_CIF_TOLERANCE
    qty_tolerance = settings.RECONCILIATION_QTY_TOLERANCE

    for line in trade.lines.all():
        remaining_qty, remaining_cif_fc, remaining_cif_inr = remaining_for_trade_line(line)
        if remaining_cif_fc <= DEC_0:
            continue

        base = {
            "license_id": line.sr_number.license_id,
            "trade_id": trade.id,
            "invoice_number": trade.invoice_number,
            "trade_line_id": line.id,
        }

        candidates = find_boe_allocation_candidates(line)
        if not candidates:
            results.append({
                **base, "boe_numbers": [], "status": "no_match",
                "detail": "No matching BOE row found among this trade's attached BOE(s) for this item.",
            })
            continue
        if len(candidates) > 1:
            results.append({
                **base,
                "boe_numbers": [c.bill_of_entry.bill_of_entry_number if c.bill_of_entry else "-" for c in candidates],
                "status": "ambiguous",
                "detail": f"{len(candidates)} candidate BOE rows match this item — cannot auto-select.",
            })
            continue

        candidate = candidates[0]
        boe_number = candidate.bill_of_entry.bill_of_entry_number if candidate.bill_of_entry else "-"
        cif_diff = abs(to_decimal(candidate.cif_fc, DEC_0) - to_decimal(line.cif_fc, DEC_0))
        qty_diff = abs(to_decimal(candidate.qty, DEC_0) - to_decimal(line.qty_kg, DEC_0))
        if cif_diff > cif_tolerance or qty_diff > qty_tolerance:
            results.append({
                **base, "boe_numbers": [boe_number], "status": "mismatch",
                "detail": f"CIF differs by {cif_diff} and qty by {qty_diff} — beyond tolerance ({cif_tolerance}/{qty_tolerance}).",
            })
            continue

        row_remaining_qty, row_remaining_cif_fc, row_remaining_cif_inr = remaining_for_row_details_invoice_side(candidate)
        alloc_qty = min(remaining_qty, row_remaining_qty, to_decimal(candidate.qty, DEC_0))
        alloc_cif_fc = min(remaining_cif_fc, row_remaining_cif_fc, to_decimal(candidate.cif_fc, DEC_0))
        alloc_cif_inr = min(remaining_cif_inr, row_remaining_cif_inr, to_decimal(candidate.cif_inr, DEC_0))
        if alloc_cif_fc <= DEC_0:
            results.append({
                **base, "boe_numbers": [boe_number], "status": "no_match",
                "detail": "Matching BOE row has no remaining invoice-side capacity left.",
            })
            continue

        status, detail = "auto_migrated", (
            f"Matched BOE {boe_number} row (qty={alloc_qty}, cif_fc={alloc_cif_fc}) within tolerance."
        )
        # Structured match data (row/amounts), only meaningful while status
        # stays "auto_migrated" — cleared below if the write attempt fails.
        # Used by `LicenseBalanceCalculator` to net this exact match out of
        # BOTH calculate_debit() and calculate_trade() on the fly, WITHOUT
        # requiring a persisted `InvoiceBOEAllocation` row to exist (see
        # `_virtual_boe_trade_matches` there) — additive fields, ignored by
        # existing callers (`backfill_boe_allocations`,
        # `check_allocation_health`) that only read `status`/`detail`.
        match_fields = {
            "row_details_id": candidate.id,
            "matched_qty": alloc_qty,
            "matched_cif_fc": alloc_cif_fc,
            "matched_cif_inr": alloc_cif_inr,
        }
        if not dry_run:
            try:
                with transaction.atomic():
                    create_invoice_boe_allocation(
                        trade_line=line, row_details=candidate,
                        qty=alloc_qty, cif_fc=alloc_cif_fc, cif_inr=alloc_cif_inr,
                        user=user, notes="Auto-reconciled from legacy trade.boes link",
                    )
            except ValidationError as exc:
                status, detail = "mismatch", f"Auto-allocation rejected: {exc}"
                match_fields = {}

        results.append({**base, "boe_numbers": [boe_number], "status": status, "detail": detail, **match_fields})

    return results
