"""
Balance calculation service for licenses and items.

This module centralizes all balance calculation logic for:
- License-level balances (credit, debit, allotment, final balance)
- Import/Export item balances
- Available values for allocation
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, DecimalField, F, OuterRef, Subquery, Sum, Value, When
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
    def _compute_virtual_boe_trade_matches(trades_queryset):
        """
        Given a queryset of SALE `LicenseTrade` rows that have at least one
        legacy `.boes` attachment, returns `{row_details_id: Decimal}` of
        CIF amounts that WOULD be allocated by `backfill_boe_allocations`
        (see `apps.reconciliation.services.boe_link_reconciler.
        reconcile_trade_boe_links`) — i.e. unambiguous 1:1 matches within
        the existing reconciliation tolerances — WITHOUT writing anything.

        This is the single shared computation behind the debit-side fix in
        `get_debit_rows()`/`calculate_debit_for_licenses()`: reuses the
        SAME conservative matching logic already trusted for the persisted-
        allocation path (never forked/duplicated), so a licence's Balance
        CIF is correct even before anyone runs the backfill command for
        real. Deliberately excludes `ambiguous`/`mismatch`/`no_match`
        results — those trade lines reference data that cannot be resolved
        without a human decision (multiple candidate BOEs, or amounts that
        genuinely don't line up), so they are intentionally left counted
        as-is rather than guessed at.
        """
        from apps.core.utils.decimal_utils import to_decimal
        from apps.reconciliation.services.boe_link_reconciler import reconcile_trade_boe_links

        by_row_details: dict = {}
        for trade in trades_queryset.prefetch_related("lines", "boes"):
            for result in reconcile_trade_boe_links(trade, dry_run=True):
                if result["status"] != "auto_migrated":
                    continue
                row_id = result["row_details_id"]
                amount = to_decimal(result["matched_cif_fc"], DEC_0)
                by_row_details[row_id] = by_row_details.get(row_id, DEC_0) + amount
        return by_row_details

    @staticmethod
    def _virtual_boe_debit_exclusion_case(*, license_obj=None, license_ids=None):
        """
        A `Case`/`When` SQL expression that yields the virtual (unpersisted)
        matched CIF for each `RowDetails` primary key found by
        `_compute_virtual_boe_trade_matches`, else 0 — built for either a
        single license (`get_debit_rows`) or a batch of them
        (`calculate_debit_for_licenses`), sharing the exact same underlying
        computation either way. Exactly one of `license_obj`/`license_ids`
        must be given.
        """
        from apps.trade.models import LicenseTrade

        trades = LicenseTrade.objects.filter(direction=LicenseTrade.DIR_SALE, boes__isnull=False).distinct()
        if license_obj is not None:
            trades = trades.filter(lines__sr_number__license=license_obj)
        else:
            trades = trades.filter(lines__sr_number__license_id__in=list(license_ids))

        by_row_details = LicenseBalanceCalculator._compute_virtual_boe_trade_matches(trades)
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
        carries `allocated` / `virtual_allocated` / `matched` / `contributed`
        annotations (see `calculate_debit`'s docstring for the allocation-
        driven partial-exclusion business rule this implements).

        Factored out of `calculate_debit` so the Financial Ledger PDF
        (services/exporters/license_balance_pdf.py) can render the exact
        same rows the Balance Engine sums, rather than recomputing the
        allocation logic a second time and risking the two drifting apart.

        `virtual_allocated` (on top of the persisted-`InvoiceBOEAllocation`-
        driven `allocated`) nets out unambiguous `trade.boes` matches that
        have not yet been written as a real allocation record — see
        `_virtual_boe_debit_exclusion_case`. This is the ONLY side of the
        debit/trade pair adjusted: `calculate_trade()` intentionally keeps
        counting every SALE line's cif_fc unconditionally (per its own
        docstring, "the matched portion is counted instead via the matching
        SALE trade line in calculate_trade()") — the exclusion belongs
        solely here, exactly mirroring how a persisted allocation already
        works, so together debit+trade still debit the license exactly once
        per matched amount, virtual or persisted.

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
        virtual_case = LicenseBalanceCalculator._virtual_boe_debit_exclusion_case(license_obj=license_obj)

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
            .annotate(virtual_allocated=virtual_case)
            .annotate(
                matched=Least(
                    F("cif_fc"), F("allocated") + F("virtual_allocated"), output_field=_ALLOCATION_DECIMAL_FIELD
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
        # Same virtual (unpersisted) trade.boes-match exclusion as
        # `get_debit_rows()` — one shared computation, kept in sync so
        # batched (bulk report) and single-license Balance CIF never
        # diverge. Bounded by how many SALE trades in this batch carry a
        # legacy `.boes` tag (system-wide, a small, fixed set — not one
        # query per license).
        virtual_case = LicenseBalanceCalculator._virtual_boe_debit_exclusion_case(license_ids=ids)

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
            .annotate(virtual_allocated=virtual_case)
            .annotate(
                matched=Least(
                    F("cif_fc"), F("allocated") + F("virtual_allocated"), output_field=_ALLOCATION_DECIMAL_FIELD
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
        `allocated` / `matched` / `contributed` annotations (see
        `calculate_allotment`'s docstring for the allocation-driven
        partial-exclusion business rule this implements).

        Factored out of `calculate_allotment` so the Financial Ledger PDF
        (services/exporters/license_balance_pdf.py) can render the exact
        same "Active Allotment" rows the Balance Engine sums — filtering
        this queryset to `contributed > 0` is precisely "no BOE linked OR
        remaining allocation exists".

        `contributed` is forced to 0 whenever the parent `AllotmentModel.
        is_boe` is True, REGARDLESS of whether a `BOEAllotmentAllocation`
        row exists yet — this is the coarse, binary signal the pre-Phase-A
        design used (`allotment__bill_of_entry__isnull=True`, see below) and
        it must still fully exclude, on top of (not replaced by) the finer
        BOEAllotmentAllocation-driven partial exclusion: `is_boe` is set the
        moment a BOE is tagged to the allotment via the BOE form's picker
        (`apps/bill_of_entry/serializers.py`), which can happen well before
        (or entirely without) anyone creating the matching
        `BOEAllotmentAllocation` ledger row. Without this, an allotment
        tagged to a BOE but not yet formally allocated silently contributes
        its FULL cif_fc as an "outstanding commitment" even though the
        underlying goods have already been debited against the licence via
        that BOE's own `RowDetails` row — double-counting the same physical
        import once as a pending allotment and once as a BOE debit.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Annotated AllotmentItems queryset for the license.
        """
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
                matched=Least(F("cif_fc"), F("allocated"), output_field=_ALLOCATION_DECIMAL_FIELD)
            )
            .annotate(
                contributed=Case(
                    When(allotment__is_boe=True, then=Value(DEC_0)),
                    default=Greatest(
                        F("cif_fc") - F("matched"), Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD
                    ),
                    output_field=_ALLOCATION_DECIMAL_FIELD,
                )
            )
        )

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
                # Same is_boe binary exclusion as get_allotment_rows() — see
                # that method's docstring. Kept in sync so batched (bulk
                # report) and single-license balances never diverge.
                contributed=Case(
                    When(allotment__is_boe=True, then=Value(DEC_0)),
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

    @classmethod
    def calculate_balance_for_licenses(cls, license_ids) -> dict:
        """
        Batched sibling of `calculate_balance` — final balance for MANY
        licenses in a fixed 4 queries total (not 4×N), by composing
        `calculate_credit_for_licenses`, `calculate_debit_for_licenses`,
        `calculate_allotment_for_licenses`, `calculate_trade_for_licenses`.

        Same formula/rounding/floor-at-0 as `calculate_balance`:
        `credit - (debit + allotment + trade)`, quantized to 2dp, floored at 0.

        Unlike the four per-component maps above (which omit a license id
        with no matching rows), every id in `license_ids` gets an entry here
        — missing components simply contribute `DEC_0`, matching what a
        per-license `calculate_balance(license_obj)` call would have
        computed for a license with no rows in some component.

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

        result = {}
        for lid in ids:
            balance = credit.get(lid, DEC_0) - (
                debit.get(lid, DEC_0) + allotment.get(lid, DEC_0) + trade.get(lid, DEC_0)
            )
            balance = quantize_2dp(balance)
            result[lid] = balance if balance >= DEC_0 else DEC_0
        return result

    @classmethod
    def calculate_balance(cls, license_obj) -> Decimal:
        """
        Calculate final balance for license.

        Formula: Credit - (Debit + Allotment + Trade)

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Final balance as Decimal (minimum 0), quantized to 2 decimal places
        """
        credit = cls.calculate_credit(license_obj)
        debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        trade = cls.calculate_trade(license_obj)

        balance = credit - (debit + allotment + trade)
        balance = quantize_2dp(balance)
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_all_components(cls, license_obj) -> dict[str, Decimal]:
        """
        Calculate all balance components at once.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dictionary with credit, debit, allotment, trade, and balance (all quantized to 2dp)
        """
        credit = cls.calculate_credit(license_obj)
        debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        trade = cls.calculate_trade(license_obj)
        balance = credit - (debit + allotment + trade)
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

        # Add allotments to debit (only non-BOE allotments)
        allotment = to_decimal(
            AllotmentItems.objects.filter(
                item=import_item,
                allotment__bill_of_entry__isnull=True
            ).aggregate(
                Sum('cif_fc')
            )['cif_fc__sum'],
            DEC_0
        )

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
        Calculate available quantity for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Available quantity as Decimal
        """

        total_quantity = to_decimal(import_item.quantity, DEC_0)

        # Sum debited quantities
        debited = to_decimal(
            RowDetails.objects.filter(
                sr_number=import_item,
                transaction_type=DEBIT
            ).aggregate(
                Sum('qty')
            )['qty__sum'],
            DEC_0
        )

        # Sum allotted quantities (only non-BOE allotments)
        allotted = to_decimal(
            AllotmentItems.objects.filter(
                item=import_item,
                allotment__bill_of_entry__isnull=True
            ).aggregate(
                Sum('qty')
            )['qty__sum'],
            DEC_0
        )

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
