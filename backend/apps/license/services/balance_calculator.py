"""
Balance calculation service for licenses and items.

This module centralizes all balance calculation logic for:
- License-level balances (credit, debit, allotment, final balance)
- Import/Export item balances
- Available values for allocation
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, Least, Greatest

from apps.core.constants import DEC_0, DEBIT
from apps.core.utils.decimal_utils import to_decimal

# Module-level imports so tests can patch via
# patch("apps.license.services.balance_calculator.LicenseExportItemModel") etc.
from apps.license.models import LicenseExportItemModel
from apps.bill_of_entry.models import RowDetails, OTH_INVOICE_MARKER, annotate_and_exclude_hidden
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


def exclude_hidden(qs):
    """
    Exclude previous-owner "hidden" BOE debit rows from a `RowDetails`
    queryset — a BOE is hidden when `BillOfEntryModel.invoice_no ==
    OTH_INVOICE_MARKER` AND its audit trail confirms a genuine hide (see
    `apps.bill_of_entry.models.annotate_and_exclude_hidden`'s docstring:
    the raw string match alone collides with ~35-40% of real BOEs that
    carry "OTH" as unrelated legacy free-text data). Applied at every
    site that builds a DEBIT `RowDetails` queryset for a live
    balance/report calculation — see `LicenseBalanceCalculator.
    get_debit_rows`'s `include_hidden` param for the one deliberate
    exception (the Customs Ledger's `show_hidden` audit view). A single,
    shared definition so every consumer's exclusion can never silently
    diverge.
    """
    return annotate_and_exclude_hidden(qs, boe_field="bill_of_entry")


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
    def _sale_trades_with_boes_for(*, license_obj=None, license_ids=None):
        """
        Shared trades-queryset builder for the legacy-tag scan
        (`_scan_linked_boe_candidates`): every SALE `LicenseTrade` carrying
        >=1 legacy `.boes` attachment and >=1 line for the given license(s).
        Exactly one of `license_obj`/`license_ids` must be given.
        """
        from apps.trade.models import LicenseTrade

        trades = LicenseTrade.objects.filter(direction=LicenseTrade.DIR_SALE, boes__isnull=False).distinct()
        if license_obj is not None:
            return trades.filter(lines__sr_number__license=license_obj)
        return trades.filter(lines__sr_number__license_id__in=list(license_ids))

    @staticmethod
    def _scan_linked_boe_candidates(trades_queryset):
        """
        THE single shared scan over `trades_queryset` (SALE trades carrying
        a legacy `.boes` tag) that decides which BOEs are "represented by
        an invoice" for `resolve_boes_represented_by_invoice[_for_licenses]`.

        Any BOE tagged to a SALE trade via `trade.boes` is treated as
        represented for EVERY licence that trade has a line for —
        regardless of which licence ITEM (`sr_number`) the BOE's own debit
        row(s) actually sit on. This is the explicit, user-confirmed BOE
        Invoice Status Consistency rule: "invoice linkage is determined by
        the BOE," not by item — see `resolve_boes_represented_by_invoice`'s
        docstring. Excludes OTH-marked (hidden/previous-owner) BOEs per the
        Pending BOE rule.

        Deliberately does NOT filter through `find_boe_allocation_
        candidates` (`apps.reconciliation.services.boe_link_reconciler`) —
        that helper additionally requires an EXACT `sr_number_id` match
        plus remaining invoice-side capacity, which is the right, narrower
        test for "should `reconcile_trade_boe_links` auto-CREATE a formal
        `InvoiceBOEAllocation` on this specific row" but the wrong test for
        "has this physical BOE already been invoiced" — a BOE spanning two
        items of the SAME licence must count as represented on both once
        the trade references it, even though only one item's row is the
        literal allocation candidate (concrete case: BOE 6756437, trade
        LML/2025-26/0097, tagged to licence 2433 but its own debit row on
        that licence sits on a different item than the trade line's item —
        it must still stop generating a "BOE Utilisation (Pending
        Invoice)" row).

        Once ANY BOE on a trade is treated as represented, it stays
        represented regardless of whether its CIF matches the trade
        line's own CIF within tolerance — a CIF discrepancy is a
        data-quality signal surfaced separately (`build_financial_
        ledger`'s `mismatch_warning`), never a second debit.

        Returns `boe_ids_by_license`: `{license_id: {bill_of_entry_id,
        ...}}` grouped by the trade LINE's own licence.
        """
        boe_ids_by_license: dict = {}
        for trade in trades_queryset.prefetch_related("lines__sr_number", "boes"):
            tagged_boe_ids = set(
                annotate_and_exclude_hidden(trade.boes).values_list("id", flat=True)
            )
            if not tagged_boe_ids:
                continue
            for line in trade.lines.all():
                license_id = line.sr_number.license_id
                boe_ids_by_license.setdefault(license_id, set()).update(tagged_boe_ids)
        return boe_ids_by_license

    @staticmethod
    def resolve_boes_represented_by_invoice(license_obj) -> set:
        """
        Set of `BillOfEntryModel` ids "represented by an invoice" for this
        licence — invoice linkage is determined at the BOE level, NEVER
        per licence item/row (explicit business rule): once EITHER
        mechanism below matches ANY debit row of a physical BOE, the WHOLE
        BOE is "represented" and every debit row on it — regardless of
        which licence item it belongs to — is treated as invoiced. This is
        the ONE place that answers "has this physical BOE already been
        accounted for by a Sale invoice," so `_linked_boe_debit_exclusion_
        case`/`get_debit_rows`/`build_financial_ledger`'s Pending-row
        suppression AND `build_customs_ledger`'s Matched/Unmatched status
        label never answer it independently — see both call sites.

        Combines BOTH:
          (a) any BOE with >=1 ACTIVE, current `InvoiceBOEAllocation` on ANY
              of its debit rows for this licence (regardless of item), and
          (b) any BOE `find_boe_allocation_candidates` identifies (via
              `_scan_linked_boe_candidates`) as linked to a SALE trade line
              through the legacy `trade.boes` M2M.

        KNOWN, ACCEPTED TRADE-OFF: a BOE can debit multiple licence items
        via multiple `RowDetails` rows (a single physical Customs document
        covering several items on the same licence). Once this BOE is
        represented, EVERY such row is excluded from `calculate_debit()`
        in full, even an item with no relationship to the matched invoice
        beyond sharing the same physical document — that item's own debit
        no longer reduces the Financial Balance. This is a deliberate
        product decision (confirmed against the concrete counter-example
        of BOE 7836435 debiting two different licence items, only one of
        which had an invoice), not an oversight — see the Financial Ledger
        BOE Invoice Status Consistency spec.

        Returns a (possibly empty) `set` of `bill_of_entry_id`s.
        """
        return LicenseBalanceCalculator.resolve_boes_represented_by_invoice_for_licenses(
            [license_obj.id]
        ).get(license_obj.id, set())

    @staticmethod
    def resolve_boes_represented_by_invoice_for_licenses(license_ids) -> dict:
        """
        Bulk sibling of `resolve_boes_represented_by_invoice` —
        `{license_id: {bill_of_entry_id, ...}}` for MANY licenses in a
        fixed, small number of queries (not one per license). See that
        method's docstring for the BOE-level "whole BOE represented"
        business rule. Every id in `license_ids` is present in the result
        (empty set when nothing represents any of that licence's BOEs).
        """
        ids = list(license_ids)
        if not ids:
            return {}

        from apps.reconciliation.models import InvoiceBOEAllocation

        result: dict = {lid: set() for lid in ids}

        # (a) Formal, active InvoiceBOEAllocation — any BOE with >=1 such
        # allocation on any of its debit rows, per license. One fixed query
        # regardless of how many licenses/BOEs are in play.
        formal_rows = (
            InvoiceBOEAllocation.objects.filter(
                row_details__sr_number__license_id__in=ids,
                status=InvoiceBOEAllocation.STATUS_ACTIVE,
                is_current=True,
            )
            .values_list("row_details__sr_number__license_id", "row_details__bill_of_entry_id")
            .distinct()
        )
        for license_id, boe_id in formal_rows:
            if boe_id is not None:
                result.setdefault(license_id, set()).add(boe_id)

        # (b) Legacy-tag/candidate match — the ONE shared trade-line-
        # scanning loop, `_scan_linked_boe_candidates` (never a second,
        # independent copy of it).
        trades = LicenseBalanceCalculator._sale_trades_with_boes_for(license_ids=ids)
        boe_ids_by_license = LicenseBalanceCalculator._scan_linked_boe_candidates(trades)
        for license_id, boe_ids in boe_ids_by_license.items():
            result.setdefault(license_id, set()).update(boe_ids)

        return result

    @staticmethod
    def _linked_boe_debit_exclusion_case(*, license_obj=None, license_ids=None):
        """
        A `Case`/`When` SQL expression that yields the full CIF of every
        `RowDetails` row whose `bill_of_entry_id` is in the BOE-id set
        returned by `resolve_boes_represented_by_invoice[_for_licenses]`
        AND which has NO active formal allocation of its OWN (`allocated ==
        0`) — else 0. Built for either a single license (`get_debit_rows`)
        or a batch of them (`calculate_debit_for_licenses`), sharing the
        exact same underlying resolver either way. Exactly one of
        `license_obj`/`license_ids` must be given.

        PRECONDITION: the caller's queryset must already carry an
        `allocated` annotation (the per-row ACTIVE/current
        `InvoiceBOEAllocation` sum) BEFORE this expression is added as
        `linked_excluded` — `F("allocated")`/`Q(allocated=...)` below
        resolve against that annotation at query-compile time.

        Keyed on `bill_of_entry_id`, NOT `row_details_id` — see `resolve_
        boes_represented_by_invoice`'s docstring: once ANY debit row of a
        BOE is represented, every OTHER debit row of that same physical
        BOE that has no allocation of its own also gets its FULL `cif_fc`
        excluded (the explicit BOE-level Invoice Status Consistency rule).

        The `allocated == 0` guard is deliberate and NOT part of a naive
        "exclude the whole BOE unconditionally" reading: a row that already
        carries its own PARTIAL formal allocation (e.g. 300 of a 1000 CIF
        row) must keep leaving its unmatched remainder (700) visible to
        `calculate_debit()`/the Financial Ledger's Pending row — see
        `apps.reconciliation.tests.test_allocation_service.
        InvoiceBOEAllocationTests.test_partial_allocation_leaves_correct_
        unmatched_remainder` — pre-existing, deliberately-tested Phase-A
        partial-allocation-ledger behavior this must not regress. Only a
        row with NO allocation of its own (a sibling row, or a legacy-
        candidate match that never became a formal allocation) falls
        through to the BOE-level "represented" exclusion.

        The `license_ids` (batch) branch scopes the exclusion PER LICENSE
        (one `When` per license id with a non-empty represented set,
        additionally gated on `Q(sr_number__license_id=lid)`) rather than
        flattening every license's represented BOE ids into one global set
        — a single shared multi-license SALE trade can legitimately
        attribute a candidate BOE to OTHER licenses beyond the ones
        requested (see `_scan_linked_boe_candidates`); flattening would
        incorrectly exclude a same-`bill_of_entry_id` debit row belonging
        to a DIFFERENT, unrelated license in the same batch, one for which
        that BOE was never actually "represented" at all.
        """
        if license_obj is not None:
            represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
            if not represented:
                return Value(DEC_0, output_field=_ALLOCATION_DECIMAL_FIELD)
            return Case(
                When(
                    Q(bill_of_entry_id__in=represented) & Q(allocated=DEC_0),
                    then=F("cif_fc"),
                ),
                default=Value(DEC_0),
                output_field=_ALLOCATION_DECIMAL_FIELD,
            )

        by_license = LicenseBalanceCalculator.resolve_boes_represented_by_invoice_for_licenses(
            list(license_ids)
        )
        whens = [
            When(
                Q(sr_number__license_id=lid) & Q(bill_of_entry_id__in=boe_ids) & Q(allocated=DEC_0),
                then=F("cif_fc"),
            )
            for lid, boe_ids in by_license.items() if boe_ids
        ]
        if not whens:
            return Value(DEC_0, output_field=_ALLOCATION_DECIMAL_FIELD)
        return Case(*whens, default=Value(DEC_0), output_field=_ALLOCATION_DECIMAL_FIELD)

    @staticmethod
    def get_debit_rows(license_obj, include_hidden=False):
        """
        Annotated RowDetails debit-row queryset for a license: each row
        carries `allocated` / `linked_excluded` / `matched` / `contributed`
        annotations (see `calculate_debit`'s docstring for the allocation-
        driven partial-exclusion business rule this implements).

        `include_hidden=False` (default) excludes previous-owner "hidden"
        rows (`RowDetails.is_hidden`, see `exclude_hidden`) — every live
        balance/financial calculation built on this queryset (`calculate_
        debit`, `calculate_boe_debit_total`, `build_financial_ledger`,
        `build_timeline`, etc.) therefore excludes hidden BOEs automatically.
        `include_hidden=True` is the one deliberate exception: the Customs
        Ledger's audit view (`build_customs_ledger`'s `show_hidden` param),
        which must still be able to show hidden rows on request.

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

        rows = RowDetails.objects.filter(
            sr_number__license=license_obj,
            transaction_type=DEBIT,
        )
        if not include_hidden:
            rows = exclude_hidden(rows)

        return (
            rows
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
        Allocation-netted BOE debit -- how much of this licence's BOE
        utilisation is still UNMATCHED to a Sale invoice.

        NOT part of the Balance CIF formula (see `calculate_balance`'s
        docstring -- that now uses the raw, unconditional
        `calculate_boe_debit_total` instead, matching the Customs Ledger).
        This method remains for `build_financial_ledger()`'s own Purchase/
        Sale/BOE-pending transactional narrative and for the reconciliation
        app's tests that verify invoice-BOE allocation nets out correctly --
        a genuinely different concern ("how reconciled is this licence
        financially") from "what is its Balance CIF."

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
    def calculate_boe_debit_total(license_obj) -> Decimal:
        """
        Total BOE debit at FULL raw `cif_fc`, unconditionally -- every
        DEBIT `RowDetails` row against this licence, regardless of any
        invoice/Sale allocation. This is the Customs Ledger's own
        `total_boe_cif` formula (see `build_customs_ledger`) and is now the
        sole BOE debit component of Balance CIF (`calculate_balance`) --
        deliberately NOT netted the way `calculate_debit()` is, since that
        netting exists for the Financial Ledger's Purchase/Sale
        transactional view, not for Balance CIF.

        Uses the exact same base rows `get_debit_rows()` (and therefore
        `build_customs_ledger()`) already query -- only the aggregate
        column differs (`cif_fc` here vs. `contributed` in `calculate_debit`).

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total raw BOE debit CIF as Decimal
        """
        rows = LicenseBalanceCalculator.get_debit_rows(license_obj)
        return to_decimal(
            rows.aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_boe_debit_total_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_boe_debit_total` -- raw, unconditional
        BOE debit total for MANY licenses in one query, grouped by license
        id. No allocation/linked-BOE annotations needed (unlike
        `calculate_debit_for_licenses`) since nothing here is netted.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        rows = (
            exclude_hidden(
                RowDetails.objects.filter(sr_number__license_id__in=ids, transaction_type=DEBIT)
            )
            .values("sr_number__license_id")
            .annotate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["sr_number__license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @staticmethod
    def calculate_hidden_boe_debit_total(license_obj) -> Decimal:
        """
        Total raw `cif_fc` of HIDDEN (previous-owner) DEBIT `RowDetails`
        rows for this licence — the subtrahend in the Financial Ledger's
        Opening Balance rule (`Original Licence CIF - Hidden BOE total`,
        see `LicenseBalanceLedgerBuilder.build_financial_ledger`'s
        docstring). Symmetric complement of `calculate_boe_debit_total`
        (which now excludes hidden rows via `get_debit_rows`) — together
        they still sum to the total raw debit across every BOE row
        regardless of hidden status.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total hidden BOE debit CIF as Decimal
        """
        return to_decimal(
            annotate_and_exclude_hidden(
                RowDetails.objects.filter(sr_number__license=license_obj, transaction_type=DEBIT),
                boe_field="bill_of_entry",
                hidden_only=True,
            ).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_hidden_boe_debit_total_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `calculate_hidden_boe_debit_total` — total raw
        `cif_fc` of HIDDEN (previous-owner) DEBIT `RowDetails` rows for MANY
        licenses in one query, grouped by license id. Feeds the Opening
        Balance gate in `calculate_financial_balance_for_licenses` — see
        `calculate_hidden_boe_debit_total`'s docstring for the business rule.
        See `calculate_credit_for_licenses` for the return-shape/zero-default
        contract.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        rows = (
            annotate_and_exclude_hidden(
                RowDetails.objects.filter(sr_number__license_id__in=ids, transaction_type=DEBIT),
                boe_field="bill_of_entry",
                hidden_only=True,
            )
            .values("sr_number__license_id")
            .annotate(total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["sr_number__license_id"]: to_decimal(row["total"], DEC_0) for row in rows}

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
            exclude_hidden(
                RowDetails.objects.filter(
                    sr_number__license_id__in=ids,
                    transaction_type=DEBIT,
                )
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
    def _annotate_allotment_contribution(queryset):
        """
        Shared annotation chain for `get_allotment_rows` (single license) /
        `get_allotment_rows_bulk` (many licenses): each row carries
        `allocated` / `matched` / `contributed` (CIF) and `allocated_qty` /
        `matched_qty` / `contributed_qty` (quantity) annotations (see
        `calculate_allotment`'s docstring for the allocation-driven
        partial-exclusion business rule this implements — the quantity
        annotations are the exact same rule, applied to `qty`/`allocated_qty`
        instead of `cif_fc`/`allocated_cif_fc`, so a licence item's Available
        Quantity — see `get_outstanding_allotment_totals` /
        `get_outstanding_allotment_totals_for_items` — can never structurally
        drift from the Balance Engine's own CIF figure).

        Factored out of the old single-license `get_allotment_rows` body so
        the single-license and license-spanning-bulk queryset builders share
        ONE implementation of this annotation chain and can never silently
        diverge — `queryset` is caller-filtered (one license or many) before
        being passed in here; this only adds annotations, never a license
        filter.

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
            queryset: an `AllotmentItems` queryset, already filtered by the
                caller to one license (`get_allotment_rows`) or many
                (`get_allotment_rows_bulk`).

        Returns:
            The same queryset with the annotations above applied.
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
            queryset
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
    def get_allotment_rows(license_obj):
        """
        Annotated AllotmentItems queryset for a license — see
        `_annotate_allotment_contribution` for the full annotation/business-
        rule writeup (allocated/matched/contributed CIF+qty, BOE-link
        exclusion, partial-allocation netting).

        Factored out of `calculate_allotment` so the Financial Ledger PDF
        (services/exporters/license_balance_pdf.py) can render the exact
        same "Active Allotment" rows the Balance Engine sums — filtering
        this queryset to `contributed > 0` is precisely "no BOE linked OR
        remaining allocation exists".

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Annotated AllotmentItems queryset for the license.
        """
        return LicenseBalanceCalculator._annotate_allotment_contribution(
            AllotmentItems.objects.filter(item__license=license_obj)
        )

    @staticmethod
    def get_allotment_rows_bulk(license_ids):
        """
        License-SPANNING sibling of `get_allotment_rows` — same annotation
        chain (`_annotate_allotment_contribution`, shared verbatim so the
        two can never silently diverge), filtered by
        `item__license_id__in=license_ids` instead of a single license.

        Used by `get_outstanding_allotment_totals_for_items` (grouped by
        `item_id`) for bulk/batched per-item consumers — see
        `apps.license.services.balance_snapshot`.

        Args:
            license_ids: iterable of license pks.

        Returns:
            Annotated AllotmentItems queryset spanning all given licenses
            (empty queryset if `license_ids` is empty).
        """
        ids = list(license_ids)
        if not ids:
            return AllotmentItems.objects.none()
        return LicenseBalanceCalculator._annotate_allotment_contribution(
            AllotmentItems.objects.filter(item__license_id__in=ids)
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
    def get_outstanding_allotment_totals_for_items(license_ids) -> dict:
        """
        Batched, license-spanning sibling of `get_outstanding_allotment_
        totals` — `{item_id: (outstanding_qty, outstanding_cif)}` for every
        import item across MANY licenses in one query, via
        `get_allotment_rows_bulk` (same AT-type filter, same BOE-link-
        exclusion + partial-allocation netting — see that method's and
        `_annotate_allotment_contribution`'s docstrings for the shared
        business rule this can never diverge from).

        Used by `ItemBalanceCalculator.calculate_available_quantity_for_items`
        and `apps.license.services.balance_snapshot` so the snapshot's
        per-item Available/Outstanding-Allotted Quantity stay in the exact
        same lineage as the single-item `get_outstanding_allotment_totals`.

        Args:
            license_ids: iterable of license pks.

        Returns:
            `{item_id: (Decimal, Decimal)}`; an item id with no outstanding
            AT-type allotment rows is simply absent — callers should use
            `.get(id, (DEC_0, DEC_0))`, matching this method's zero-default
            single-item counterpart.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        rows = (
            LicenseBalanceCalculator.get_allotment_rows_bulk(ids)
            .filter(allotment__type='AT')
            .values('item_id')
            .annotate(
                qty=Coalesce(Sum("contributed_qty"), Value(DEC_0), output_field=DecimalField()),
                cif=Coalesce(Sum("contributed"), Value(DEC_0), output_field=DecimalField()),
            )
        )
        return {
            row["item_id"]: (to_decimal(row["qty"], DEC_0), to_decimal(row["cif"], DEC_0))
            for row in rows
        }

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

        NOT part of the Balance CIF formula (see `calculate_balance`'s
        docstring — Customs Ledger's formula, the sole source of truth, has
        no trade term at all). Stays in use for `build_financial_ledger()`'s
        own Purchase/Sale transactional narrative/summary stats.

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
        credit-side counterpart to `calculate_trade()` (SALE debit).

        NOT part of the Balance CIF formula (see `calculate_balance`'s
        docstring — the old anchor-switch that used this as an alternate
        credit anchor for "traded" licences produced wrong results whenever
        a licence had real BOE-debited face value AND incidental trading,
        e.g. licence 5211016017: a $38,272.50 Purchase/Sale pair discarded
        $3.31M of real credit, giving $0 instead of the correct $243,034.85
        Customs Ledger figure). Stays in use for `build_financial_ledger()`'s
        own Purchase/Sale transactional narrative/summary stats.

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
        True when this licence has ANY Purchase or Sale trade line at all.

        NOT used by `calculate_balance()` any more (see that method's
        docstring — Balance CIF no longer branches on trading activity at
        all, matching the Customs Ledger). Kept for
        `build_financial_ledger()`'s own summary/gating (its
        `has_trading_activity`/`missing_purchase_warning` fields) and for
        anything reporting "has this licence ever been traded" as a fact,
        independent of Balance CIF.

        ONE combined `.exists()` query (not two) — same direction set as
        `get_purchase_trade_rows()` + `get_trade_rows()` OR'd together.
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
    def has_purchase_for_licenses(license_ids) -> dict:
        """
        Batched sibling of `get_purchase_trade_rows(...).exists()` —
        `{license_id: bool}` for MANY licenses in one query (not one per
        license). Same direction set as `get_purchase_trade_rows`
        (PURCHASE + COMMISSION_PURCHASE). Feeds the Opening Balance gate in
        `calculate_financial_balance_for_licenses` — the batched equivalent
        of `build_financial_ledger`'s/`calculate_financial_balance`'s own
        per-license `has_purchase` check. Distinct from
        `has_trading_activity_for_licenses` (PURCHASE + COMMISSION_PURCHASE
        + SALE) — this one is PURCHASE-only, matching the Opening Balance
        gate's own `has_purchase` (not `has_trading_activity`).
        """
        from apps.trade.models import LicenseTrade, LicenseTradeLine

        ids = list(license_ids)
        if not ids:
            return {}
        purchasing_ids = set(
            LicenseTradeLine.objects.filter(
                sr_number__license_id__in=ids,
                trade__direction__in=(LicenseTrade.DIR_PURCHASE, LicenseTrade.DIR_COMMISSION_PURCHASE),
            ).values_list("sr_number__license_id", flat=True)
        )
        return {lid: (lid in purchasing_ids) for lid in ids}

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
        licenses in a fixed 3 queries total (not 3×N), by composing
        `calculate_credit_for_licenses`, `calculate_boe_debit_total_for_licenses`,
        `calculate_allotment_for_licenses`.

        Same formula/rounding/floor-at-0 as `calculate_balance` (see that
        method's docstring): every id in `license_ids` gets an entry here —
        missing components simply contribute `DEC_0`, matching what a
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
        boe_debit = cls.calculate_boe_debit_total_for_licenses(ids)
        allotment = cls.calculate_allotment_for_licenses(ids)

        result = {}
        for lid in ids:
            balance = credit.get(lid, DEC_0) - (boe_debit.get(lid, DEC_0) + allotment.get(lid, DEC_0))
            balance = quantize_2dp(balance)
            result[lid] = balance if balance >= DEC_0 else DEC_0
        return result

    @classmethod
    def calculate_balance(cls, license_obj) -> Decimal:
        """
        `Credit - (non-hidden BOE Debit + Allotment)` — NOT the "Balance
        Engine"/business figure any more (see `LicenseDetailsModel.
        get_balance_cif`, which now calls `calculate_financial_balance`
        instead). This function excludes hidden (previous-owner) BOE rows
        the same way every other live calculation does, via `calculate_
        boe_debit_total()` -> `get_debit_rows()`'s default `include_hidden
        =False` — it therefore does NOT reconcile with `build_customs_
        ledger()`'s own running total for a licence with hidden BOEs (that
        ledger deliberately includes hidden rows unconditionally; see its
        docstring). Use `calculate_customs_balance()` for the figure that
        DOES always match the Customs Ledger exactly, hidden or not.

        Formula: `Credit - (BOE Debit + Allotment)`:
        - `Credit` = `calculate_credit()` — Total Licence CIF (sum of
          export-item cif_fc), Coalesced to 0.
        - `BOE Debit` = `calculate_boe_debit_total()` — every non-hidden
          DEBIT `RowDetails` row's FULL raw `cif_fc`, unconditionally. No
          invoice-allocation netting, no Purchase/Sale participation.
        - `Allotment` = `calculate_allotment()` — outstanding (BOE-unlinked)
          allotted CIF only; allotments already linked to a BOE are never
          deducted (unchanged).

        Previously this branched on `has_trading_activity()`, swapping
        `Credit` for `calculate_purchase_credit()` and adding
        `calculate_trade()` the instant ANY Purchase/Sale trade existed —
        intended to make a traded licence's balance track its trading
        history. That broke for a licence with real BOE-debited face value
        PLUS incidental trading: licence 5211016017 has $3.31M Credit and
        $3.07M of direct BOE debit, but also one small $38,272.50
        Purchase/Sale pair — the old formula discarded the $3.31M Credit
        entirely and anchored on just $38,272.50, giving $0.00 instead of
        the correct $243,034.85 (`Credit - BOE Debit - Allotment`, exactly
        what the Customs Ledger already computed). Purchase/Sale trades no
        longer participate in Balance CIF at all; `calculate_trade`/
        `calculate_purchase_credit`/`has_trading_activity`/`calculate_debit`
        remain available for `build_financial_ledger()`'s own Purchase/Sale
        transactional narrative, which may now legitimately diverge from
        this value for a traded licence — surfaced via that ledger's own
        `mismatched` flag, never silently forced to match.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Final balance as Decimal (minimum 0), quantized to 2 decimal places
        """
        credit = cls.calculate_credit(license_obj)
        boe_debit = cls.calculate_boe_debit_total(license_obj)
        allotment = cls.calculate_allotment(license_obj)

        balance = credit - (boe_debit + allotment)
        balance = quantize_2dp(balance)
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_customs_balance(cls, license_obj) -> Decimal:
        """
        "Customs Available Balance" — `Credit - (ALL BOE Debit, hidden +
        visible + Allotment)`. The literal, unconditional Customs Ledger
        figure (`build_customs_ledger`'s own running total uses exactly
        this formula) — the ONE figure guaranteed to always reconcile with
        that ledger exactly, regardless of hidden BOEs. Distinct from
        `calculate_balance()` (excludes hidden rows) and `calculate_
        financial_balance()` (the Financial/business figure, ALSO
        hidden-aware but via the Opening Balance/Previous Owner Utilisation
        route, not a flat subtraction) — see both docstrings.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Customs Available Balance as Decimal (minimum 0), quantized to
            2 decimal places.
        """
        credit = cls.calculate_credit(license_obj)
        boe_debit = cls.calculate_boe_debit_total(license_obj) + cls.calculate_hidden_boe_debit_total(license_obj)
        allotment = cls.calculate_allotment(license_obj)

        balance = credit - (boe_debit + allotment)
        balance = quantize_2dp(balance)
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_customs_balance_for_licenses(cls, license_ids) -> dict:
        """
        Batched sibling of `calculate_customs_balance` — same formula, for
        MANY licenses in a fixed, small number of queries. See `calculate_
        credit_for_licenses` for the return-shape/zero-default contract.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        credit_map = cls.calculate_credit_for_licenses(ids)
        boe_debit_map = cls.calculate_boe_debit_total_for_licenses(ids)
        hidden_map = cls.calculate_hidden_boe_debit_total_for_licenses(ids)
        allotment_map = cls.calculate_allotment_for_licenses(ids)

        result = {}
        for lid in ids:
            balance = credit_map.get(lid, DEC_0) - (
                boe_debit_map.get(lid, DEC_0) + hidden_map.get(lid, DEC_0) + allotment_map.get(lid, DEC_0)
            )
            balance = quantize_2dp(balance)
            result[lid] = balance if balance >= DEC_0 else DEC_0
        return result

    @classmethod
    def calculate_all_components(cls, license_obj) -> dict[str, Decimal]:
        """
        Calculate all balance components at once — same formula as
        `calculate_balance` (see its docstring), returned alongside the
        components themselves for display (e.g. License Overview's
        Total/Debited/Allotted/Balance CIF cards, which sum to each other
        exactly by construction: `credit - debit - allotment == balance`).

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dictionary with credit, debit, allotment, and balance (all quantized to 2dp)
        """
        credit = cls.calculate_credit(license_obj)
        debit = cls.calculate_boe_debit_total(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        balance = credit - (debit + allotment)
        balance = quantize_2dp(balance)

        return {
            'credit': quantize_2dp(credit),
            'debit': quantize_2dp(debit),
            'allotment': quantize_2dp(allotment),
            'balance': balance if balance >= DEC_0 else DEC_0,
        }

    @classmethod
    def calculate_opening_balance(cls, license_obj) -> Decimal:
        """
        The hidden-BOE-aware Opening Balance — the SAME 3-way gate
        `build_financial_ledger` uses for its own Opening Balance /
        Previous Owner Utilisation rows, as a plain number rather than
        ledger rows. The sole anchor `calculate_financial_balance` starts
        from. Checked in this order:
          1. `hidden_total = calculate_hidden_boe_debit_total()` > 0 ->
             `calculate_credit()` (Original Licence CIF) - `hidden_total`
             - `calculate_purchase_credit()`. "Previous Owner Utilisation"
             represents everything that left the ORIGINAL licence's
             available pool before it became ours: Hidden BOEs (never
             ours) AND Purchased CIF (no longer "available to purchase"
             from the previous owner — it's already been bought). Licence
             Purchase is STILL a separate, independent financial event —
             it re-enters the ledger as its own "Licence Trade
             (Purchased)" credit row/term (see `calculate_financial_
             balance`'s unconditional `+ purchase_credit`), so subtracting
             it here and adding it back there is NOT a bug: the two
             together give Purchase a net-zero effect on the final balance
             UNLESS something else (a Sale, in particular) also touches
             it — exactly the "two different questions, one ledger" design
             this formula implements (see `build_financial_ledger`'s
             "Previous Owner Utilisation" row docstring).
          2. else `has_purchase` (`get_purchase_trade_rows().exists()`) ->
             0 (a purchased licence tells its story from that trading
             history, not the original DGFT-issued face value).
          3. else -> `calculate_credit()` (the untouched original face
             value).

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Opening Balance as Decimal (un-quantized/un-floored — matches
            `calculate_credit()`'s own precision; `calculate_financial_
            balance` quantizes/floors only the FINAL balance, same as
            `build_financial_ledger`'s `running`).
        """
        credit = cls.calculate_credit(license_obj)
        hidden_total = cls.calculate_hidden_boe_debit_total(license_obj)
        if hidden_total > DEC_0:
            return credit - hidden_total - cls.calculate_purchase_credit(license_obj)
        if cls.get_purchase_trade_rows(license_obj).exists():
            return DEC_0
        return credit

    @classmethod
    def calculate_opening_balance_for_licenses(cls, license_ids) -> dict:
        """
        Batched sibling of `calculate_opening_balance` — same 3-way gate,
        for MANY licenses in a fixed, small number of queries, composed
        from `calculate_credit_for_licenses`, `calculate_hidden_boe_debit_
        total_for_licenses`, `has_purchase_for_licenses`, `calculate_
        purchase_credit_for_licenses`. See `calculate_credit_for_licenses`
        for the return-shape/zero-default contract.
        """
        ids = list(license_ids)
        if not ids:
            return {}
        credit_map = cls.calculate_credit_for_licenses(ids)
        hidden_map = cls.calculate_hidden_boe_debit_total_for_licenses(ids)
        has_purchase_map = cls.has_purchase_for_licenses(ids)
        purchase_credit_map = cls.calculate_purchase_credit_for_licenses(ids)

        result = {}
        for lid in ids:
            credit = credit_map.get(lid, DEC_0)
            hidden_total = hidden_map.get(lid, DEC_0)
            if hidden_total > DEC_0:
                result[lid] = credit - hidden_total - purchase_credit_map.get(lid, DEC_0)
            elif has_purchase_map.get(lid, False):
                result[lid] = DEC_0
            else:
                result[lid] = credit
        return result

    @classmethod
    def calculate_financial_balance(cls, license_obj) -> Decimal:
        """
        Calculate the Financial Available Balance for a license — the
        second of the two Balance Engines (see `calculate_balance`'s
        docstring for the first, "Customs Balance"). A pure-function
        formalization of `LicenseBalanceLedgerBuilder.build_financial_
        ledger`'s row-by-row `running` accumulation's final
        `computed_balance`, for callers that only need the number, not the
        whole ledger (rows, invoice-match children, mismatch warnings,
        etc.) — composes this class's own existing bulk-lineage methods,
        never re-derives their arithmetic.

        Formula:

            Opening Balance + Purchase Invoice CIF - Sale Invoice CIF
                - Our (unallocated) BOE debit - Outstanding Allotments
            = Financial Available Balance

        `Opening Balance` is `calculate_opening_balance()` — see that
        method's docstring for the hidden-BOE-aware 3-way gate. When
        hidden BOEs exist, that Opening Balance has ALREADY subtracted
        Purchase Invoice CIF too (as part of "Previous Owner
        Utilisation" — everything that left the original licence's pool
        before it became ours), and this `+ Purchase Invoice CIF` term
        unconditionally adds it straight back — deliberately, not a bug:
        Purchase re-enters the ledger here as its own independent
        financial event (`build_financial_ledger`'s "Licence Trade
        (Purchased)" credit row), giving it a net-zero effect on the
        final balance unless something else (typically a matching Sale)
        also touches the same CIF. For a licence with zero hidden BOEs,
        `calculate_opening_balance()` never subtracted Purchase in the
        first place, so this term behaves exactly as a plain addition,
        unchanged from before.

        IMPORTANT — the BOE term here is `calculate_debit()` (allocation-
        and legacy-candidate-driven, per-row exclusion; see `get_debit_
        rows()`/`_linked_boe_debit_exclusion_case`'s docstrings), deliberately
        NOT `calculate_boe_debit_total()` (raw, invoice-allocation-UNaware).
        Both already exclude hidden rows (via `get_debit_rows()`), but only
        `calculate_debit()` avoids double-counting a BOE row already netted
        out by a real allocation or legacy-candidate match: such a row's
        cif is counted EITHER here (as an unmatched remainder) OR via the
        matching SALE trade line's full `cif_fc` in `calculate_trade()`
        below — never both. This exactly mirrors `build_financial_ledger`'s
        own pairing of `total_boe_debit` (`get_debit_rows()`'s
        `contributed`, i.e. `calculate_debit()`) with `total_trade_debit`
        (`calculate_trade()`). Re-verify empirically against a dev-DB sweep
        after any change to either exclusion mechanism — `calculate_debit()`
        must always agree with `build_financial_ledger`'s `computed_balance`
        (its own `mismatched` self-check is the guard for this); substituting
        `calculate_boe_debit_total()` here is known to diverge whenever a
        SALE-matched BOE row still has an unmatched sibling elsewhere.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Financial Available Balance as Decimal (minimum 0), quantized
            to 2 decimal places — same floor-at-0/quantize convention as
            `calculate_balance`.
        """
        opening = cls.calculate_opening_balance(license_obj)
        purchase_credit = cls.calculate_purchase_credit(license_obj)
        sale_debit = cls.calculate_trade(license_obj)
        boe_debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)

        balance = opening + purchase_credit - sale_debit - boe_debit - allotment
        balance = quantize_2dp(balance)
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_financial_balance_for_licenses(cls, license_ids) -> dict:
        """
        Batched sibling of `calculate_financial_balance` — Financial
        Available Balance for MANY licenses in a fixed, small number of
        queries (not N-per-license), composed entirely from each
        component's own `_for_licenses` bulk sibling (including
        `calculate_opening_balance_for_licenses` for the Opening Balance
        anchor). See `calculate_financial_balance`'s docstring for the
        formula / why-`calculate_debit()`-not-`calculate_boe_debit_total()`
        rationale — identical logic, just batched.

        Args:
            license_ids: iterable of license pks.

        Returns:
            `{license_id: Decimal}` Financial Available Balance per
            license — every id in `license_ids` gets an entry (missing
            components simply contribute `DEC_0`/`False`, matching
            `calculate_balance_for_licenses`'s own convention).
        """
        ids = list(license_ids)
        if not ids:
            return {}

        opening_map = cls.calculate_opening_balance_for_licenses(ids)
        purchase_credit_map = cls.calculate_purchase_credit_for_licenses(ids)
        sale_debit_map = cls.calculate_trade_for_licenses(ids)
        boe_debit_map = cls.calculate_debit_for_licenses(ids)
        allotment_map = cls.calculate_allotment_for_licenses(ids)

        result = {}
        for lid in ids:
            balance = (
                opening_map.get(lid, DEC_0)
                + purchase_credit_map.get(lid, DEC_0)
                - sale_debit_map.get(lid, DEC_0)
                - boe_debit_map.get(lid, DEC_0)
                - allotment_map.get(lid, DEC_0)
            )
            balance = quantize_2dp(balance)
            result[lid] = balance if balance >= DEC_0 else DEC_0
        return result


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
                exclude_hidden(RowDetails.objects.filter(
                    sr_number__license=import_item.license,
                    transaction_type=DEBIT
                )).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )
        else:
            # Use specific item CIF
            credit = to_decimal(import_item.cif_fc, DEC_0)

            # Debit is for this specific item
            debit = to_decimal(
                exclude_hidden(RowDetails.objects.filter(
                    sr_number=import_item,
                    transaction_type=DEBIT
                )).aggregate(
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
            exclude_hidden(RowDetails.objects.filter(
                sr_number=import_item,
                transaction_type=DEBIT
            )).aggregate(
                Sum('qty')
            )['qty__sum'],
            DEC_0
        )

        allotted, _allotted_cif = LicenseBalanceCalculator.get_outstanding_allotment_totals(import_item)

        available = total_quantity - debited - allotted
        return available if available >= DEC_0 else DEC_0

    @staticmethod
    def calculate_debited_quantity_for_items(item_ids) -> dict:
        """
        Batched sibling of the `debited` component inside
        `calculate_available_quantity` — raw DEBIT `RowDetails.qty` total for
        MANY import items in one query, grouped by item id. Same shape/
        zero-default contract as `LicenseBalanceCalculator.
        calculate_boe_debit_total_for_licenses` (grouped by item instead of
        license).

        Args:
            item_ids: iterable of `LicenseImportItemsModel` pks.

        Returns:
            `{item_id: Decimal}`; an item id with no DEBIT rows is simply
            absent — callers should use `.get(id, DEC_0)`.
        """
        ids = list(item_ids)
        if not ids:
            return {}
        rows = (
            exclude_hidden(
                RowDetails.objects.filter(sr_number_id__in=ids, transaction_type=DEBIT)
            )
            .values("sr_number_id")
            .annotate(total=Coalesce(Sum("qty"), Value(DEC_0), output_field=DecimalField()))
        )
        return {row["sr_number_id"]: to_decimal(row["total"], DEC_0) for row in rows}

    @staticmethod
    def calculate_available_quantity_for_items(items) -> dict:
        """
        Batched sibling of `calculate_available_quantity` — same formula
        (`quantity - debited - outstanding AT-type allotted`, floored at 0),
        for MANY import items, possibly spanning MANY licenses, in a fixed
        small number of queries. Composes
        `calculate_debited_quantity_for_items` and `LicenseBalanceCalculator.
        get_outstanding_allotment_totals_for_items` — same Balance-Engine
        lineage as the per-item method above (NOT `apps.core.scripts.
        calculate_balance.calculate_available_quantity`'s legacy stored-field
        lineage — see that per-item method's docstring for the distinction),
        so bulk callers (e.g. `apps.license.services.balance_snapshot`) stay
        aligned with the Allotment Max-button path.

        Accepts an iterable of ALREADY-FETCHED `LicenseImportItemsModel`
        instances (mirrors `apps.license.services.condition_pool.
        available_value_bulk_map`'s `items`-not-`ids` convention — the
        caller typically already has them loaded from one query and this
        avoids a second).

        Args:
            items: iterable of `LicenseImportItemsModel` instances.

        Returns:
            `{item_id: Decimal}`, present for every item in `items`
            (always floored at 0), matching what a per-item
            `calculate_available_quantity(item)` call would return.
        """
        items = list(items)
        if not items:
            return {}
        item_ids = [item.id for item in items]
        license_ids = list({item.license_id for item in items if item.license_id})

        debited_map = ItemBalanceCalculator.calculate_debited_quantity_for_items(item_ids)
        outstanding_map = (
            LicenseBalanceCalculator.get_outstanding_allotment_totals_for_items(license_ids)
            if license_ids else {}
        )

        result = {}
        for item in items:
            total_quantity = to_decimal(item.quantity, DEC_0)
            debited = debited_map.get(item.id, DEC_0)
            outstanding_qty, _outstanding_cif = outstanding_map.get(item.id, (DEC_0, DEC_0))
            available = total_quantity - debited - outstanding_qty
            result[item.id] = available if available >= DEC_0 else DEC_0
        return result

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
