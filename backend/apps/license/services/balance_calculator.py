"""
Balance calculation service for licenses and items.

This module centralizes all balance calculation logic for:
- License-level balances (credit, debit, allotment, final balance)
- Import/Export item balances
- Available values for allocation
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, DecimalField, Exists, F, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, Least, Greatest

from apps.core.constants import DEC_0, DEBIT
from apps.core.utils.decimal_utils import to_decimal

# Module-level imports so tests can patch via
# patch("apps.license.services.balance_calculator.LicenseExportItemModel") etc.
from apps.license.models import LicenseExportItemModel
from apps.bill_of_entry.models import RowDetails
from apps.allotment.models import AllotmentItems

DECIMAL_CENT = Decimal("0.01")

# Output field for allocation-driven annotations in calculate_debit() /
# calculate_allotment() below: sized to match
# apps.reconciliation.models.{InvoiceBOEAllocation,BOEAllotmentAllocation}
# .allocated_cif_fc (max_digits=20, decimal_places=3), which is itself sized
# to cover RowDetails.cif_fc (15, 3) with room for the larger
# LicenseTradeLine.cif_fc (20, 2) side -- see that module's docstring.
_ALLOCATION_DECIMAL_FIELD = DecimalField(max_digits=20, decimal_places=3)


def quantize_2dp(value: Decimal) -> Decimal:
    """Quantize decimal to 2 decimal places."""
    return to_decimal(value, DEC_0).quantize(DECIMAL_CENT, rounding=ROUND_HALF_UP)


class LicenseBalanceCalculator:
    """
    Service for calculating license-level balances.
    
    Centralizes the calculation of:
    - Credit (total export CIF)
    - Debit (total BOE debits)
    - Allotment (total non-BOE allotments)
    - Final balance
    """

    @staticmethod
    def calculate_credit(license_obj) -> Decimal:
        """
        Calculate total credit (export CIF) for license.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Total export CIF as Decimal
        """

        return to_decimal(
            LicenseExportItemModel.objects.filter(
                license=license_obj
            ).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def _compute_linked_boe_row_ids(trades_queryset):
        """
        Given a queryset of SALE `LicenseTrade` rows that have at least one
        legacy `.boes` attachment, returns `{row_details_id: Decimal}` of
        the FULL `cif_fc` of every `RowDetails` row that
        `find_boe_allocation_candidates` (see `apps.reconciliation.services.
        boe_link_reconciler` — the SAME candidate lookup `reconcile_trade_
        boe_links` itself uses) identifies as belonging to a SALE trade
        line, for exclusion from `calculate_debit()`.

        A linked BOE is excluded in FULL regardless of whether its CIF
        matches the trade line's own CIF within tolerance — i.e. this
        covers `"auto_migrated"`, `"mismatch"`, AND `"ambiguous"` candidates
        alike (only `"no_match"` contributes nothing, since no candidate
        exists to find). This is a deliberate design choice: the Financial
        Ledger is an accounting ledger, not a reconciliation report — once a
        BOE is linked to an invoice, that invoice is its sole financial
        representation from then on, and a CIF discrepancy is a data-quality
        signal surfaced separately (see `build_financial_ledger`'s
        `mismatch_warning`), never a second debit. Reuses the exact same
        candidate-finding logic the reconciliation panel/backfill command
        already trust, so a licence's Balance CIF is correct even before
        anyone creates a formal `InvoiceBOEAllocation` for real.
        """
        from apps.reconciliation.services.boe_link_reconciler import find_boe_allocation_candidates

        by_row_details: dict = {}
        for trade in trades_queryset.prefetch_related("lines", "boes"):
            for line in trade.lines.all():
                for candidate in find_boe_allocation_candidates(line):
                    by_row_details[candidate.id] = to_decimal(candidate.cif_fc, DEC_0)
        return by_row_details

    @staticmethod
    def _linked_boe_debit_exclusion_case(*, license_obj=None, license_ids=None):
        """
        A `Case`/`When` SQL expression that yields the full CIF of each
        `RowDetails` primary key found by `_compute_linked_boe_row_ids`,
        else 0 — built for either a single license (`get_debit_rows`) or a
        batch of them (`calculate_debit_for_licenses`), sharing the exact
        same underlying computation either way. Exactly one of
        `license_obj`/`license_ids` must be given.
        """
        from apps.trade.models import LicenseTrade

        trades = LicenseTrade.objects.filter(direction=LicenseTrade.DIR_SALE, boes__isnull=False).distinct()
        if license_obj is not None:
            trades = trades.filter(lines__sr_number__license=license_obj)
        else:
            trades = trades.filter(lines__sr_number__license_id__in=list(license_ids))

        by_row_details = LicenseBalanceCalculator._compute_linked_boe_row_ids(trades)
        if not by_row_details:
            return Value(DEC_0, output_field=_ALLOCATION_DECIMAL_FIELD)
        return Case(
            *[When(pk=row_id, then=Value(amount)) for row_id, amount in by_row_details.items()],
            default=Value(DEC_0),
            output_field=_ALLOCATION_DECIMAL_FIELD,
        )

    @staticmethod
    def get_debit_rows(license_obj):
        """
        Annotated RowDetails debit-row queryset for a license: each row
        carries `allocated` / `linked_excluded` / `matched` / `contributed`
        annotations (see `calculate_debit`'s docstring for the allocation-
        driven partial-exclusion business rule this implements).

        Factored out of `calculate_debit` so the Financial Ledger PDF
        (services/exporters/license_balance_pdf.py) can render the exact
        same rows the Balance Engine sums, rather than recomputing the
        allocation logic a second time and risking the two drifting apart.

        `linked_excluded` (on top of the persisted-`InvoiceBOEAllocation`-
        driven `allocated`) nets out the FULL cif_fc of any `RowDetails` row
        that `find_boe_allocation_candidates` identifies as linked to a
        SALE trade line via the legacy `trade.boes` M2M — regardless of
        whether the CIF matches within tolerance — see
        `_linked_boe_debit_exclusion_case`. This is the ONLY side of the
        debit/trade pair adjusted: `calculate_trade()` intentionally keeps
        counting every SALE line's cif_fc unconditionally (per its own
        docstring, "the matched portion is counted instead via the matching
        SALE trade line in calculate_trade()") — the exclusion belongs
        solely here, exactly mirroring how a persisted allocation already
        works, so together debit+trade still debit the license exactly once
        per linked amount, whether formally allocated, cleanly auto-
        matched, or merely tagged-but-mismatched (a CIF discrepancy is
        surfaced as a warning on the invoice row instead — see
        `build_financial_ledger`'s `mismatch_warning` — never a second debit).

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Annotated RowDetails queryset (transaction_type=DEBIT only).
        """
        from apps.reconciliation.models import InvoiceBOEAllocation

        allocated_subquery = (
            InvoiceBOEAllocation.objects.filter(
                row_details_id=OuterRef("pk"),
                status=InvoiceBOEAllocation.STATUS_ACTIVE,
                is_current=True,
            )
            .order_by()
            .values("row_details_id")
            .annotate(total=Sum("allocated_cif_fc"))
            .values("total")
        )
        linked_case = LicenseBalanceCalculator._linked_boe_debit_exclusion_case(license_obj=license_obj)

        return (
            RowDetails.objects.filter(
                sr_number__license=license_obj,
                transaction_type=DEBIT,
            )
            .annotate(
                allocated=Coalesce(
                    Subquery(allocated_subquery, output_field=_ALLOCATION_DECIMAL_FIELD),
                    Value(DEC_0),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .annotate(linked_excluded=linked_case)
            .annotate(
                matched=Least(
                    F("cif_fc"), F("allocated") + F("linked_excluded"), output_field=_ALLOCATION_DECIMAL_FIELD
                )
            )
            .annotate(
                contributed=Greatest(
                    F("cif_fc") - F("matched"), Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD
                )
            )
        )

    @staticmethod
    def calculate_debit(license_obj) -> Decimal:
        """
        Calculate total debit (BOE transactions) for license.

        Business rule: One physical import may generate multiple documents,
        but it must produce exactly one licence debit.

        ALLOCATION-DRIVEN (Phase A): each BOE debit row (RowDetails)
        contributes `cif_fc - min(cif_fc, allocated)` to the license's
        debit, floored at 0, where `allocated` is the sum of that row's
        ACTIVE, current `InvoiceBOEAllocation` rows (see
        apps.reconciliation.models.InvoiceBOEAllocation) -- i.e. however
        much of this exact row has been explicitly matched to a SALE
        LicenseTradeLine. This replaces the earlier binary, BOE-level
        `Exists()` exclusion (which excluded a row's ENTIRE cif_fc the
        instant ANY SALE line on a trade linking that exact BOE existed)
        with a real partial-allocation ledger: one invoice can be split
        across many BOEs, one BOE can back many invoices, and amounts
        rarely divide evenly, so exclusion must happen at the allocated-
        amount level, not the whole-row level.

        The matched portion is counted instead via the matching SALE trade
        line in calculate_trade(), so together they debit the license
        exactly once per allocated amount -- any UNMATCHED remainder of a
        BOE row (no allocation, or a partial one) still counts here as
        debit, which the earlier binary exclusion could hide entirely.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total debit CIF as Decimal
        """
        rows = LicenseBalanceCalculator.get_debit_rows(license_obj)

        return to_decimal(
            rows.aggregate(
                total=Coalesce(Sum("contributed"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_credit_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_credit` — total credit (export CIF)
        for MANY licenses in one query, grouped by license id.

        For bulk report/export code that used to call `calculate_credit`
        once per license (one query each): call this once with all the ids
        instead. Returns a `{license_id: Decimal}` map; a license id with no
        export items is simply absent (callers should use `.get(id, DEC_0)`,
        matching `calculate_credit`'s own zero-default via `Coalesce`).

        Args:
            license_ids: iterable of license pks.

        Returns:
            `{license_id: Decimal}` total credit per license.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        rows = (
            LicenseExportItemModel.objects
            .filter(license_id__in=ids)
            .values("license_id")
            .annotate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @staticmethod
    def calculate_debit_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_debit` — total debit (allocation-
        driven, partial exclusion; see `calculate_debit`'s docstring for
        the business rule) for MANY licenses in one query, grouped by
        license id. Same per-row allocation annotation as `calculate_debit`
        — evaluated per-RowDetails-row via a single correlated subquery
        regardless of how many licenses are batched, so the grouping
        doesn't change the exclusion semantics and stays a bounded number
        of queries (not one per license). See `calculate_credit_for_licenses`
        for the return-shape/zero-default contract.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        from apps.reconciliation.models import InvoiceBOEAllocation

        allocated_subquery = (
            InvoiceBOEAllocation.objects.filter(
                row_details_id=OuterRef("pk"),
                status=InvoiceBOEAllocation.STATUS_ACTIVE,
                is_current=True,
            )
            .order_by()
            .values("row_details_id")
            .annotate(total=Sum("allocated_cif_fc"))
            .values("total")
        )
        # Same linked-BOE exclusion as `get_debit_rows()` — one shared
        # computation, kept in sync so batched (bulk report) and single-
        # license Balance CIF never diverge. Bounded by how many SALE
        # trades in this batch carry a legacy `.boes` tag (system-wide, a
        # small, fixed set — not one query per license).
        linked_case = LicenseBalanceCalculator._linked_boe_debit_exclusion_case(license_ids=ids)

        rows = (
            RowDetails.objects
            .filter(
                sr_number__license_id__in=ids,
                transaction_type=DEBIT,
            )
            .annotate(
                allocated=Coalesce(
                    Subquery(allocated_subquery, output_field=_ALLOCATION_DECIMAL_FIELD),
                    Value(DEC_0),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .annotate(linked_excluded=linked_case)
            .annotate(
                matched=Least(
                    F("cif_fc"), F("allocated") + F("linked_excluded"), output_field=_ALLOCATION_DECIMAL_FIELD
                )
            )
            .annotate(
                contributed=Greatest(
                    F("cif_fc") - F("matched"), Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD
                )
            )
            .values("sr_number__license_id")
            .annotate(total=Coalesce(Sum("contributed"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["sr_number__license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @staticmethod
    def get_allotment_rows(license_obj):
        """
        Annotated AllotmentItems queryset for a license: each row carries
        `allocated` / `matched` / `contributed` (CIF) and `allocated_qty` /
        `matched_qty` / `contributed_qty` (quantity) annotations (see
        `calculate_allotment`'s docstring for the allocation-driven
        partial-exclusion business rule this implements — the quantity
        annotations are the exact same rule, applied to `qty`/`allocated_qty`
        instead of `cif_fc`/`allocated_cif_fc`, so a licence item's Available
        Quantity — see `get_outstanding_allotment_totals` — can never
        structurally drift from the Balance Engine's own CIF figure).

        Factored out of `calculate_allotment` so the Financial Ledger PDF
        (services/exporters/license_balance_pdf.py) can render the exact
        same "Active Allotment" rows the Balance Engine sums — filtering
        this queryset to `contributed > 0` is precisely "no BOE linked OR
        remaining allocation exists".

        `contributed` is forced to 0 whenever the parent `AllotmentModel` has
        ANY linked BOE at all (an `Exists()` check against the real
        `BillOfEntryModel.allotment` M2M relationship set by the BOE form's
        allotment picker, `apps/bill_of_entry/serializers.py`), REGARDLESS of
        whether a `BOEAllotmentAllocation` row exists yet — this must still
        fully exclude, on top of (not replaced by) the finer
        BOEAllotmentAllocation-driven partial exclusion below.

        This checks the REAL relationship rather than `AllotmentModel.
        is_boe` (a hand-maintained cache boolean set/cleared alongside the
        M2M by that same serializer) — `is_boe` has been found stale at
        real-world scale (thousands of allotments linked to a BOE via the
        M2M with `is_boe` still `False`), which silently let an allotment
        show as an outstanding "Pending Allotment" AND get debited a second
        time even though the linked BOE's own `RowDetails` row already
        debits the identical utilisation — see `build_customs_ledger`'s
        "Pending Allotment" rows / `build_financial_ledger`'s "Active
        Allotment" rows, both driven by this same annotation.

        Without this exclusion, an allotment tagged to a BOE but not yet
        formally allocated silently contributes its FULL cif_fc as an
        "outstanding commitment" even though the underlying goods have
        already been debited against the licence via that BOE's own
        `RowDetails` row — double-counting the same physical import once as
        a pending allotment and once as a BOE debit.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Annotated AllotmentItems queryset for the license.
        """
        from apps.bill_of_entry.models import BillOfEntryModel
        from apps.reconciliation.models import BOEAllotmentAllocation

        allocated_subquery = (
            BOEAllotmentAllocation.objects.filter(
                allotment_item_id=OuterRef("pk"),
                status=BOEAllotmentAllocation.STATUS_ACTIVE,
                is_current=True,
            )
            .order_by()
            .values("allotment_item_id")
            .annotate(total=Sum("allocated_cif_fc"))
            .values("total")
        )
        allocated_qty_subquery = (
            BOEAllotmentAllocation.objects.filter(
                allotment_item_id=OuterRef("pk"),
                status=BOEAllotmentAllocation.STATUS_ACTIVE,
                is_current=True,
            )
            .order_by()
            .values("allotment_item_id")
            .annotate(total=Sum("allocated_qty"))
            .values("total")
        )
        # `Exists()` rather than a `Case`/`When` over the `allotment__
        # bill_of_entry` M2M lookup directly: the latter would add a JOIN to
        # the through table, duplicating this row once per linked BOE (an
        # allotment can legitimately be linked to more than one) — corrupting
        # `calculate_allotment()`'s `Sum('contributed')` aggregate. `Exists`
        # is a correlated subquery, never joined into the outer FROM clause,
        # so it can't duplicate rows regardless of how many BOEs are linked.
        has_linked_boe = Exists(
            BillOfEntryModel.objects.filter(allotment=OuterRef("allotment_id"))
        )

        return (
            AllotmentItems.objects.filter(
                item__license=license_obj,
            )
            .annotate(
                allocated=Coalesce(
                    Subquery(allocated_subquery, output_field=_ALLOCATION_DECIMAL_FIELD),
                    Value(DEC_0),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .annotate(
                allocated_qty=Coalesce(
                    Subquery(allocated_qty_subquery, output_field=_ALLOCATION_DECIMAL_FIELD),
                    Value(DEC_0),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .annotate(
                matched=Least(F("cif_fc"), F("allocated"), output_field=_ALLOCATION_DECIMAL_FIELD)
            )
            .annotate(
                matched_qty=Least(F("qty"), F("allocated_qty"), output_field=_ALLOCATION_DECIMAL_FIELD)
            )
            .annotate(
                contributed=Case(
                    When(has_linked_boe, then=Value(DEC_0)),
                    default=Greatest(
                        F("cif_fc") - F("matched"), Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD
                    ),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .annotate(
                contributed_qty=Case(
                    When(has_linked_boe, then=Value(DEC_0)),
                    default=Greatest(
                        F("qty") - F("matched_qty"), Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD
                    ),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
        )

    @staticmethod
    def get_outstanding_allotment_totals(import_item) -> tuple[Decimal, Decimal]:
        """
        `(outstanding_qty, outstanding_cif)` for ONE licence item — the
        single source of truth for "Allotted Quantity"/"Allotted CIF" in the
        Item Summary, the Balance Engine, and `apps.core.scripts.
        calculate_balance`'s stored-field writer alike. Reuses
        `get_allotment_rows()` verbatim (same `has_linked_boe`/partial-
        allocation exclusion as the licence-level Balance Engine — a BOE-
        linked allotment, fully or partially, is never counted here, and a
        formally-allocated remainder is netted the same way).

        Restricted to `AllotmentModel.type == 'AT'` — ARO-type allotments
        are treated as already-debited (folded into "Debited", not
        "Allotted") by `calculate_balance.py`'s existing AT/ARO split, which
        this does not change.

        Args:
            import_item: LicenseImportItemsModel instance

        Returns:
            (outstanding_qty, outstanding_cif) as Decimals.
        """
        row = (
            LicenseBalanceCalculator.get_allotment_rows(import_item.license)
            .filter(item=import_item, allotment__type='AT')
            .aggregate(
                qty=Coalesce(Sum("contributed_qty"), Value(DEC_0), output_field=DecimalField()),
                cif=Coalesce(Sum("contributed"), Value(DEC_0), output_field=DecimalField()),
            )
        )
        return to_decimal(row["qty"], DEC_0), to_decimal(row["cif"], DEC_0)

    @staticmethod
    def calculate_allotment(license_obj) -> Decimal:
        """
        Calculate total allotment (non-BOE) for license.

        ALLOCATION-DRIVEN (Phase A): every AllotmentItems row for the
        license contributes `cif_fc - min(cif_fc, allocated)` to the
        license's allotment total, floored at 0, where `allocated` is the
        sum of that row's ACTIVE, current `BOEAllotmentAllocation` rows
        (see apps.reconciliation.models.BOEAllotmentAllocation) — i.e.
        however much of this exact allotment item has been explicitly
        matched to a RowDetails BOE debit row. This replaces the earlier
        binary `allotment__bill_of_entry__isnull=True` inclusion (which
        counted an allotment's FULL cif_fc unless ANY BOE was linked to its
        parent Allotment at all) with a real partial-allocation ledger: a
        BOE can only partially consume an allotment, and amounts rarely
        divide evenly.

        Only the CIF component feeds the licence balance formula (matching
        this method's existing behavior, which has never summed qty) — the
        BOEAllotmentAllocation sum subtracted is therefore also
        `allocated_cif_fc`, to stay in the same unit.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total allotment CIF as Decimal
        """
        rows = LicenseBalanceCalculator.get_allotment_rows(license_obj)

        return to_decimal(
            rows.aggregate(
                total=Coalesce(Sum("contributed"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def get_trade_rows(license_obj):
        """
        SALE LicenseTradeLine queryset for a license (see `calculate_trade`'s
        docstring). Factored out so the Financial Ledger PDF
        (services/exporters/license_balance_pdf.py) can list the exact same
        rows the Balance Engine sums as licence trade debits.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            LicenseTradeLine queryset (trade__direction='SALE' only).
        """
        from apps.trade.models import LicenseTradeLine

        return LicenseTradeLine.objects.filter(
            sr_number__license=license_obj,
            trade__direction='SALE'  # Only count SALE trades that debit the license
        )

    @staticmethod
    def get_purchase_trade_rows(license_obj):
        """
        PURCHASE-direction `LicenseTradeLine` queryset for a license — the
        symmetric counterpart to `get_trade_rows()` (SALE only). Factored
        out the same way, so the Financial Ledger (`license_balance_ledger_
        builder.py`) can render "Licence Trade (Purchased)" credit rows
        without re-deriving the direction filter.

        NOT summed into `calculate_credit()`, which remains unchanged — the
        licence's face-value credit is, and stays, sourced solely from
        `LicenseExportItemModel` (see `calculate_credit`'s docstring). It IS
        summed by `calculate_purchase_credit()` and used by
        `calculate_balance()` as the credit anchor for any licence with
        trading activity (see that method's docstring) — the Balance Engine
        and Financial Ledger must always reconcile exactly, and the ledger's
        own `running` already anchors on real Purchase credit rather than
        the original export-item CIF once trading exists.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            LicenseTradeLine queryset (trade__direction in PURCHASE/
            COMMISSION_PURCHASE — same two directions `build_timeline`
            already treats as "purchase" for its own event labeling).
        """
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        return LicenseTradeLine.objects.filter(
            sr_number__license=license_obj,
            trade__direction__in=(LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE),
        )

    @staticmethod
    def calculate_trade(license_obj) -> Decimal:
        """
        Calculate total trade CIF $ for license.

        Counts ALL SALE trade lines, regardless of BOE status.
        BOEs linked to trades are excluded from calculate_debit() to avoid double-counting.

        NOTE: Only SALE trades debit the license. PURCHASE trades add to the license (already counted in allotments).

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total trade CIF as Decimal
        """
        return to_decimal(
            LicenseBalanceCalculator.get_trade_rows(license_obj).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_purchase_credit(license_obj) -> Decimal:
        """
        Sum of every PURCHASE trade line's cif_fc for this licence — the
        credit-side counterpart to `calculate_trade()` (SALE debit), used
        ONLY by `calculate_balance()`'s trading-licence branch (see that
        method's docstring). Mirrors `get_purchase_trade_rows()`'s own
        "display-only" note: this is the one place that note no longer
        applies, now that a trading licence's Balance Engine anchors on its
        actual trading history instead of the original export-item CIF,
        exactly like `build_financial_ledger()`'s `running` already does.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total purchase CIF as Decimal
        """
        return to_decimal(
            LicenseBalanceCalculator.get_purchase_trade_rows(license_obj).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def has_trading_activity(license_obj) -> bool:
        """
        True when this licence has ANY Purchase or Sale trade line at all —
        the SAME condition `build_financial_ledger()` uses to decide whether
        to anchor on the original export-item CIF or on real trading
        history (see that method's docstring). Shared here so
        `calculate_balance()` and the Financial Ledger can never independently
        drift on which licences get which formula.

        ONE combined `.exists()` query (not two) — same direction set as
        `get_purchase_trade_rows()` + `get_trade_rows()` OR'd together,
        rather than checking each separately, since `calculate_balance()`
        runs this on every call (list views, bulk recompute tasks).
        """
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        return LicenseTradeLine.objects.filter(
            sr_number__license=license_obj,
            trade__direction__in=(
                LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE, LicenseTrade.DIR_SALE,
            ),
        ).exists()

    @staticmethod
    def has_trading_activity_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `has_trading_activity` — `{license_id: bool}` for
        MANY licenses in 2 queries total (not 2xN), used by
        `calculate_balance_for_licenses()`.
        """
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        ids = list(license_ids)
        if not ids:
            return {}
        # Same direction sets as `get_purchase_trade_rows()` (PURCHASE +
        # COMMISSION_PURCHASE) and `get_trade_rows()` (SALE only — NOT
        # COMMISSION_SALE, matching that method's own filter exactly).
        trading_ids = set(
            LicenseTradeLine.objects.filter(
                sr_number__license_id__in=ids,
                trade__direction__in=(
                    LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE, LicenseTrade.DIR_SALE,
                ),
            ).values_list("sr_number__license_id", flat=True)
        )
        return {lid: (lid in trading_ids) for lid in ids}

    @staticmethod
    def calculate_allotment_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_allotment` — total allotment
        (allocation-driven, partial exclusion; see `calculate_allotment`'s
        docstring for the business rule) for MANY licenses in one query,
        grouped by license id. Same per-row allocation annotation as
        `calculate_allotment` — evaluated per-AllotmentItems-row via a
        single correlated subquery regardless of how many licenses are
        batched, so it stays a bounded number of queries (not one per
        license). See `calculate_credit_for_licenses` for the return-
        shape/zero-default contract.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        from apps.bill_of_entry.models import BillOfEntryModel
        from apps.reconciliation.models import BOEAllotmentAllocation

        allocated_subquery = (
            BOEAllotmentAllocation.objects.filter(
                allotment_item_id=OuterRef("pk"),
                status=BOEAllotmentAllocation.STATUS_ACTIVE,
                is_current=True,
            )
            .order_by()
            .values("allotment_item_id")
            .annotate(total=Sum("allocated_cif_fc"))
            .values("total")
        )
        # Same `Exists()` linked-BOE exclusion as `get_allotment_rows()` —
        # see that method's docstring for why this must be an `Exists()`
        # subquery, not a `Case`/`When` over the M2M lookup directly (which
        # would duplicate rows and corrupt this `Sum('contributed')`).
        has_linked_boe = Exists(
            BillOfEntryModel.objects.filter(allotment=OuterRef("allotment_id"))
        )

        rows = (
            AllotmentItems.objects
            .filter(
                item__license_id__in=ids,
            )
            .annotate(
                allocated=Coalesce(
                    Subquery(allocated_subquery, output_field=_ALLOCATION_DECIMAL_FIELD),
                    Value(DEC_0),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .annotate(
                matched=Least(F("cif_fc"), F("allocated"), output_field=_ALLOCATION_DECIMAL_FIELD)
            )
            .annotate(
                # Kept in sync with get_allotment_rows() so batched (bulk
                # report) and single-license balances never diverge.
                contributed=Case(
                    When(has_linked_boe, then=Value(DEC_0)),
                    default=Greatest(
                        F("cif_fc") - F("matched"), Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD
                    ),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
            .values("item__license_id")
            .annotate(total=Coalesce(Sum("contributed"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["item__license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @staticmethod
    def calculate_trade_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_trade` — total SALE-trade CIF for MANY
        licenses in one query, grouped by license id. Same
        `trade__direction='SALE'` filter as `calculate_trade`. See
        `calculate_credit_for_licenses` for the return-shape/zero-default
        contract.
        """
        from apps.trade.models import LicenseTradeLine

        ids = list(license_ids)
        if not ids:
            return {}
        rows = (
            LicenseTradeLine.objects
            .filter(
                sr_number__license_id__in=ids,
                trade__direction='SALE',
            )
            .values("sr_number__license_id")
            .annotate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["sr_number__license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @staticmethod
    def calculate_purchase_credit_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_purchase_credit` — total PURCHASE-trade
        CIF for MANY licenses in one query, grouped by license id. Same
        direction set as `get_purchase_trade_rows`. See
        `calculate_credit_for_licenses` for the return-shape/zero-default
        contract.
        """
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        ids = list(license_ids)
        if not ids:
            return {}
        rows = (
            LicenseTradeLine.objects
            .filter(
                sr_number__license_id__in=ids,
                trade__direction__in=(LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE),
            )
            .values("sr_number__license_id")
            .annotate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["sr_number__license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @classmethod
    def calculate_balance_for_licenses(cls, license_ids) -> dict:
        """
        Batched sibling of `calculate_balance` — final balance for MANY
        licenses in a fixed 6 queries total (not 6×N), by composing
        `calculate_credit_for_licenses`, `calculate_debit_for_licenses`,
        `calculate_allotment_for_licenses`, `calculate_trade_for_licenses`,
        `calculate_purchase_credit_for_licenses`, `has_trading_activity_for_licenses`.

        Same formula/rounding/floor-at-0 as `calculate_balance` (see that
        method's docstring for the trading-licence branch): every id in
        `license_ids` gets an entry here — missing components simply
        contribute `DEC_0`, matching what a per-license
        `calculate_balance(license_obj)` call would have computed for a
        license with no rows in some component.

        Args:
            license_ids: iterable of license pks.

        Returns:
            `{license_id: Decimal}` final balance per license.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        credit = cls.calculate_credit_for_licenses(ids)
        debit = cls.calculate_debit_for_licenses(ids)
        allotment = cls.calculate_allotment_for_licenses(ids)
        trade = cls.calculate_trade_for_licenses(ids)
        purchase_credit = cls.calculate_purchase_credit_for_licenses(ids)
        trading = cls.has_trading_activity_for_licenses(ids)

        result = {}
        for lid in ids:
            anchor = purchase_credit.get(lid, DEC_0) if trading.get(lid, False) else credit.get(lid, DEC_0)
            balance = anchor - (
                debit.get(lid, DEC_0) + allotment.get(lid, DEC_0) + trade.get(lid, DEC_0)
            )
            balance = quantize_2dp(balance)
            result[lid] = balance if balance >= DEC_0 else DEC_0
        return result

    @classmethod
    def calculate_balance(cls, license_obj) -> Decimal:
        """
        Calculate final balance for license — the single "Balance Engine"
        value shown everywhere (List/Detail, Overview, PDF/Excel, Customs
        Ledger's anchor row) and the one `build_financial_ledger()`'s own
        running total must always reconcile with exactly (never merely
        within tolerance).

        Formula:
        - No Purchase/Sale trading activity at all: `Credit - (Debit +
          Allotment + Trade)` (unchanged; `Trade` is always 0 here since it
          requires a SALE line).
        - ANY Purchase/Sale trading activity: `PurchaseCredit - (Debit +
          Allotment + Trade)` — the SAME `has_trading_activity` condition and
          the SAME switch from the original export-item CIF to real trading
          history that `build_financial_ledger()`'s `running` already makes
          (see that method's docstring: a traded licence's ledger is no
          longer anchored on a fabricated Opening Balance). `Debit`/`Trade`
          already correctly net out matched vs. unmatched BOE/invoice amounts
          (see `calculate_debit`/`calculate_trade`'s own docstrings) — this
          branch is the only piece that was missing for the two to always
          agree exactly.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Final balance as Decimal (minimum 0), quantized to 2 decimal places
        """
        debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        trade = cls.calculate_trade(license_obj)
        anchor = (
            cls.calculate_purchase_credit(license_obj)
            if cls.has_trading_activity(license_obj)
            else cls.calculate_credit(license_obj)
        )

        balance = anchor - (debit + allotment + trade)
        balance = quantize_2dp(balance)
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_all_components(cls, license_obj) -> dict[str, Decimal]:
        """
        Calculate all balance components at once.

        `credit` always stays "original export-item CIF" (used for display
        elsewhere as e.g. "Original CIF") regardless of trading activity —
        only `balance` itself switches to the purchase-credit-anchored
        formula for a traded licence; see `calculate_balance`'s docstring.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dictionary with credit, debit, allotment, trade, and balance (all quantized to 2dp)
        """
        credit = cls.calculate_credit(license_obj)
        debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        trade = cls.calculate_trade(license_obj)
        anchor = cls.calculate_purchase_credit(license_obj) if cls.has_trading_activity(license_obj) else credit
        balance = anchor - (debit + allotment + trade)
        balance = quantize_2dp(balance)

        return {
            'credit': quantize_2dp(credit),
            'debit': quantize_2dp(debit),
            'allotment': quantize_2dp(allotment),
            'trade': quantize_2dp(trade),
            'balance': balance if balance >= DEC_0 else DEC_0,
        }


class ItemBalanceCalculator:
    """
    Service for calculating item-level balances.
    
    Handles calculations for import and export items.
    """

    @staticmethod
    def calculate_item_credit_debit(import_item) -> tuple[Decimal, Decimal]:
        """
        Calculate credit and debit for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Tuple of (credit, total_debit) as Decimals
        """

        # Calculate credit
        if not import_item.cif_fc or import_item.cif_fc == 0:
            # Use total export CIF if item CIF is 0
            credit = to_decimal(
                LicenseExportItemModel.objects.filter(
                    license=import_item.license
                ).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )

            # Debit is for entire license
            debit = to_decimal(
                RowDetails.objects.filter(
                    sr_number__license=import_item.license,
                    transaction_type=DEBIT
                ).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )
        else:
            # Use specific item CIF
            credit = to_decimal(import_item.cif_fc, DEC_0)

            # Debit is for this specific item
            debit = to_decimal(
                RowDetails.objects.filter(
                    sr_number=import_item,
                    transaction_type=DEBIT
                ).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )

        # Add outstanding (BOE-unlinked) allotments to debit — reuses the
        # SAME Balance Engine helper `calculate_available_quantity` below
        # uses, rather than an independent `allotment__bill_of_entry__
        # isnull=True` filter (the legacy, partial-allocation-unaware join
        # check `get_allotment_rows`'s docstring documents replacing).
        _allotted_qty, allotment = LicenseBalanceCalculator.get_outstanding_allotment_totals(import_item)

        total_debit = debit + allotment

        return credit, total_debit

    @classmethod
    def calculate_item_balance(cls, import_item) -> Decimal:
        """
        Calculate balance for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Balance as Decimal (minimum 0)
        """
        credit, debit = cls.calculate_item_credit_debit(import_item)
        balance = credit - debit
        return balance if balance >= DEC_0 else DEC_0

    @staticmethod
    def calculate_available_quantity(import_item) -> Decimal:
        """
        Available Quantity for an import item = current stored `quantity`
        (NEVER `old_quantity` — see `apps.core.scripts.calculate_balance.
        calculate_available_quantity`'s docstring for why that legacy
        substitution was removed) − Debited − Outstanding (BOE-unlinked)
        Allotted. The allotted term reuses `LicenseBalanceCalculator.
        get_outstanding_allotment_totals` — the same Balance Engine
        exclusion (`Exists()` against the real BOE↔allotment relationship,
        plus `BOEAllotmentAllocation` partial-allocation netting) every
        other consumer (Item Summary, Financial/Customs Ledger, the stored
        `available_quantity` field) uses, so this can never structurally
        drift from them.

        Args:
            import_item: LicenseImportItemsModel instance

        Returns:
            Available quantity as Decimal
        """
        total_quantity = to_decimal(import_item.quantity, DEC_0)

        debited = to_decimal(
            RowDetails.objects.filter(
                sr_number=import_item,
                transaction_type=DEBIT
            ).aggregate(
                Sum('qty')
            )['qty__sum'],
            DEC_0
        )

        allotted, _allotted_cif = LicenseBalanceCalculator.get_outstanding_allotment_totals(import_item)

        available = total_quantity - debited - allotted
        return available if available >= DEC_0 else DEC_0

    @classmethod
    def calculate_item_components(cls, import_item) -> dict[str, Decimal]:
        """
        Calculate all components for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Dictionary with credit, debit, balance, and available_quantity
        """
        credit, debit = cls.calculate_item_credit_debit(import_item)
        balance = credit - debit
        available_qty = cls.calculate_available_quantity(import_item)

        return {
            'credit': credit,
            'debit': debit,
            'balance': balance if balance >= DEC_0 else DEC_0,
            'available_quantity': available_qty,
        }

    @staticmethod
    def calculate_available_value_for_allocation(
            import_item,
            unit_price: Decimal,
            required_value_with_buffer: Decimal | None = None
    ) -> dict[str, Decimal]:
        """
        Calculate maximum available value for allocation considering all constraints.
        
        Args:
            import_item: LicenseImportItemsModel instance
            unit_price: Price per unit
            required_value_with_buffer: Required value with buffer for allotment
            
        Returns:
            Dictionary with max_quantity and max_value
        """
        available_qty = ItemBalanceCalculator.calculate_available_quantity(import_item)
        balance_cif = ItemBalanceCalculator.calculate_item_balance(import_item)
        unit_price = to_decimal(unit_price, DEC_0)

        if unit_price <= 0:
            return {
                'max_quantity': DEC_0,
                'max_value': DEC_0,
            }

        # Start with available quantity
        max_qty = available_qty
        max_value = max_qty * unit_price

        # Check CIF constraint
        if max_value > balance_cif:
            max_qty = balance_cif / unit_price
            max_value = max_qty * unit_price

        # Check required value constraint if provided
        required_value = to_decimal(required_value_with_buffer, DEC_0)
        if required_value > DEC_0 and max_value > required_value:
            max_qty = required_value / unit_price
            max_value = max_qty * unit_price

        return {
            'max_quantity': max_qty,
            'max_value': max_value,
        }
