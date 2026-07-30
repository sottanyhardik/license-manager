"""
Tests for `LicenseBalanceCalculator.resolve_boes_represented_by_invoice[_for_
licenses]` (`apps/license/services/balance_calculator.py`) and its rewiring
into `get_debit_rows()`/`calculate_debit()`/`calculate_debit_for_licenses()`
and `LicenseBalanceLedgerBuilder.build_financial_ledger()`'s "BOE Utilisation
(Pending Invoice)" suppression.

Closes a real structural gap: `find_boe_allocation_candidates` (and a single
`InvoiceBOEAllocation`) only ever matches ONE licence item's `RowDetails` row
at a time. A physical BOE covering MULTIPLE licence items (several
`RowDetails` rows, different `sr_number`s, same `bill_of_entry`) used to only
have the ONE matched item's row excluded from Pending -- the BOE's OTHER
item rows wrongly stayed "Pending" even though the same physical document is
already represented by an invoice. The fix: once ANY debit row of a BOE is
matched (by a formal `InvoiceBOEAllocation` OR a legacy `trade.boes`
candidate match), the WHOLE BOE is "represented" and every one of its debit
rows is excluded, not just the matched one.

Uses the real model-creation helpers from `apps.reconciliation.tests.
test_reconciliation.ReconciliationFixtureMixin` (make_company/make_license/
make_item/make_boe/make_debit_row/make_sale_trade/make_trade_line) and
`apps.reconciliation.services.allocation_service.create_invoice_boe_allocation`
-- never reimplemented.
"""
import uuid
from decimal import Decimal

from django.test import TestCase

from apps.core.constants import DEC_0
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder
from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation
from apps.reconciliation.services.boe_link_reconciler import reconcile_trade_boe_links
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin


def assert_no_boe_in_both_pending_and_invoiced(test, rows):
    """
    Invariant helper: for every row in a `build_financial_ledger()` result,
    no `boe_number` appears in BOTH a `row_kind='boe'` (Pending) row AND in
    the represented-BOE set backing any `row_kind='trade'` row's
    `linked_boe_numbers`.
    """
    pending_boe_numbers = {
        row["boe_number"] for row in rows if row.get("row_kind") == "boe" and row.get("boe_number")
    }
    invoiced_boe_numbers = set()
    for row in rows:
        if row.get("row_kind") == "trade":
            invoiced_boe_numbers.update(row.get("linked_boe_numbers") or [])
    overlap = pending_boe_numbers & invoiced_boe_numbers
    test.assertFalse(
        overlap,
        f"BOE(s) {overlap} appear in BOTH a Pending row and an invoice's linked_boe_numbers",
    )


class BoeInvoiceRepresentationFixtureMixin(ReconciliationFixtureMixin):
    """Adds a helper for a formal InvoiceBOEAllocation on top of the shared
    ReconciliationFixtureMixin model-creation helpers."""

    def make_allocation(self, trade_line, row_details, cif_fc, qty=None, cif_inr=None):
        return create_invoice_boe_allocation(
            trade_line=trade_line,
            row_details=row_details,
            qty=qty if qty is not None else DEC_0,
            cif_fc=cif_fc,
            cif_inr=cif_inr if cif_inr is not None else cif_fc * Decimal("84.5"),
            user=None,
        )

    def pending_boe_numbers(self, license_obj):
        rows, _summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        return {row["boe_number"] for row in rows if row.get("row_kind") == "boe"}


class SingleBoeSingleRowInvoiceLinkedTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 1: single BOE, single debit row, formal InvoiceBOEAllocation --
    invoice only, zero Pending rows for that BOE."""

    def test_fully_allocated_row_has_zero_pending_and_zero_debit(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        debit_row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))
        self.make_allocation(trade_line, debit_row, cif_fc=Decimal("1000.00"))

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, {boe.id})

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit, DEC_0)

        rows, _summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        pending = [r for r in rows if r.get("row_kind") == "boe"]
        self.assertEqual(pending, [])
        trade_rows = [r for r in rows if r.get("row_kind") == "trade"]
        self.assertEqual(len(trade_rows), 1)
        assert_no_boe_in_both_pending_and_invoiced(self, rows)


class SingleBoeMultipleRowsInvoiceLinkedTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 2: single BOE, multiple debit rows (2 licence items on the SAME
    BOE), invoice-linked -- invoice only, ZERO Pending rows for EITHER row
    of that BOE."""

    def test_both_rows_suppressed_when_one_is_formally_allocated(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item_a = self.make_item(license_obj, 1)
        item_b = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        row_a = self.make_debit_row(boe, item_a, cif_fc=Decimal("400.00"))
        row_b = self.make_debit_row(boe, item_b, cif_fc=Decimal("600.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        trade_line_b = self.make_trade_line(trade, item_b, cif_fc=Decimal("600.00"))
        self.make_allocation(trade_line_b, row_b, cif_fc=Decimal("600.00"))

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, {boe.id})

        pending = self.pending_boe_numbers(license_obj)
        self.assertNotIn(boe.bill_of_entry_number, pending)
        self.assertEqual(pending, set())


class MultiItemBoePartialCandidateGapTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 3 -- THE gap being closed: single BOE, multiple licence items,
    where only ONE item's RowDetails row is candidate/allocation-matched by
    the trade. The BOE's OTHER (unmatched) row must ALSO be suppressed from
    Pending, because the same physical BOE is already represented."""

    def test_unmatched_sibling_row_on_same_boe_also_suppressed(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item_a = self.make_item(license_obj, 1)
        item_b = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        row_a = self.make_debit_row(boe, item_a, cif_fc=Decimal("400.00"))
        row_b = self.make_debit_row(boe, item_b, cif_fc=Decimal("600.00"))
        # The trade/invoice ONLY has a line for item B -- item A has no
        # trade line, no allocation, nothing referencing it directly.
        trade = self.make_sale_trade(company, boes=[boe])
        trade_line_b = self.make_trade_line(trade, item_b, cif_fc=Decimal("600.00"))
        self.make_allocation(trade_line_b, row_b, cif_fc=Decimal("600.00"))

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, {boe.id})

        # get_debit_rows(): row A's `contributed` must now be 0 -- the whole
        # BOE is represented, not just row B.
        rows_by_id = {
            r.id: r for r in LicenseBalanceCalculator.get_debit_rows(license_obj)
        }
        self.assertEqual(rows_by_id[row_a.id].contributed, DEC_0)
        self.assertEqual(rows_by_id[row_b.id].contributed, DEC_0)

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit, DEC_0)
        batched_debit = LicenseBalanceCalculator.calculate_debit_for_licenses([license_obj.id])
        self.assertEqual(batched_debit.get(license_obj.id, DEC_0), DEC_0)

        pending = self.pending_boe_numbers(license_obj)
        self.assertEqual(pending, set(), "Item A's row on the same physical BOE must not stay Pending")

        rows, _summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        assert_no_boe_in_both_pending_and_invoiced(self, rows)


class NoInvoiceLinkageRegressionTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 4: single BOE, no invoice linkage at all -- Pending, unchanged
    (regression guard)."""

    def test_unlinked_boe_still_pending(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, set())

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit, Decimal("1000.00"))

        pending = self.pending_boe_numbers(license_obj)
        self.assertEqual(pending, {boe.bill_of_entry_number})


class MultipleBoesOneInvoiceTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 5: multiple BOEs linked to one invoice -- invoice row lists all
    linked BOEs (existing display, unchanged), none of them appear in
    Pending."""

    def test_all_linked_boes_suppressed_from_pending(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe1 = self.make_boe(company)
        boe2 = self.make_boe(company)
        row1 = self.make_debit_row(boe1, item, cif_fc=Decimal("500.00"))
        row2 = self.make_debit_row(boe2, item, cif_fc=Decimal("500.00"))
        trade = self.make_sale_trade(company, boes=[boe1, boe2])
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))
        self.make_allocation(trade_line, row1, cif_fc=Decimal("500.00"))
        self.make_allocation(trade_line, row2, cif_fc=Decimal("500.00"))

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, {boe1.id, boe2.id})

        pending = self.pending_boe_numbers(license_obj)
        self.assertEqual(pending, set())

        rows, _summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        trade_rows = [r for r in rows if r.get("row_kind") == "trade"]
        self.assertEqual(len(trade_rows), 1)
        linked = set(trade_rows[0]["linked_boe_numbers"])
        self.assertEqual(linked, {boe1.bill_of_entry_number, boe2.bill_of_entry_number})
        assert_no_boe_in_both_pending_and_invoiced(self, rows)


class LegacyAutoMigratedLinkageTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 6: legacy-migrated linkage (`auto_migrated` status via
    `reconcile_trade_boe_links`) -- suppressed, matches case 1/2 behavior."""

    def test_auto_migrated_candidate_suppresses_pending(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        debit_row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        # Live-migrate via the same reconciliation service the backfill
        # command/reconciliation panel use (NOT dry_run -- creates a real
        # InvoiceBOEAllocation).
        results = reconcile_trade_boe_links(trade, dry_run=False)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "auto_migrated")

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, {boe.id})

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit, DEC_0)

        pending = self.pending_boe_numbers(license_obj)
        self.assertEqual(pending, set())


class ReconciliationCandidateLinkageTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """Case 7: reconciliation-candidate linkage (`mismatch`/`ambiguous`,
    never formally allocated) -- still suppressed from Pending, and
    `mismatch_warning` is still shown on the invoice row."""

    def test_mismatch_candidate_suppressed_with_warning_shown(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        debit_row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        # 10.00 CIF difference -- beyond the 1.00 default tolerance, so
        # this is a "mismatch", not an "auto_migrated" clean match.
        self.make_trade_line(trade, item, cif_fc=Decimal("990.00"))

        represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license_obj)
        self.assertEqual(represented, {boe.id})

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit, DEC_0, "Mismatched-but-linked BOE must still be excluded in full")

        pending = self.pending_boe_numbers(license_obj)
        self.assertEqual(pending, set())

        rows, _summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj)
        trade_rows = [r for r in rows if r.get("row_kind") == "trade"]
        self.assertEqual(len(trade_rows), 1)
        warning = trade_rows[0]["mismatch_warning"]
        self.assertIsNotNone(warning)
        self.assertTrue(warning["show_warning"])
        self.assertEqual(warning["status"], "mismatch")
        assert_no_boe_in_both_pending_and_invoiced(self, rows)

        # No formal allocation was ever persisted -- this is computed live
        # from the `.boes` tag alone (dry-run reconciliation).
        from apps.reconciliation.models import InvoiceBOEAllocation
        self.assertFalse(InvoiceBOEAllocation.objects.filter(row_details=debit_row).exists())


class CalculateBalanceUnaffectedTests(BoeInvoiceRepresentationFixtureMixin, TestCase):
    """`calculate_balance()`/`calculate_boe_debit_total()` must be totally
    unaffected by this refactor -- they use raw, unconditional `cif_fc`,
    never netted, regardless of any invoice linkage."""

    def test_balance_unaffected_by_represented_boe_in_multi_item_gap_scenario(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item_a = self.make_item(license_obj, 1)
        item_b = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        row_a = self.make_debit_row(boe, item_a, cif_fc=Decimal("400.00"))
        row_b = self.make_debit_row(boe, item_b, cif_fc=Decimal("600.00"))
        trade = self.make_sale_trade(company, boes=[boe])
        trade_line_b = self.make_trade_line(trade, item_b, cif_fc=Decimal("600.00"))
        self.make_allocation(trade_line_b, row_b, cif_fc=Decimal("600.00"))

        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(
            license=license_obj, description="Export",
            cif_fc=Decimal("2000.00"), cif_inr=Decimal("2000.00") * Decimal("84.5"),
        )

        boe_debit_total = LicenseBalanceCalculator.calculate_boe_debit_total(license_obj)
        self.assertEqual(boe_debit_total, Decimal("1000.00"), "Raw BOE debit must count both rows in full")

        balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        self.assertEqual(balance, Decimal("1000.00"))  # 2000 credit - 1000 raw boe debit - 0 allotment

    def test_balance_unaffected_when_no_invoice_linkage(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        from apps.license.models import LicenseExportItemModel
        LicenseExportItemModel.objects.create(
            license=license_obj, description="Export",
            cif_fc=Decimal("2000.00"), cif_inr=Decimal("2000.00") * Decimal("84.5"),
        )

        boe_debit_total = LicenseBalanceCalculator.calculate_boe_debit_total(license_obj)
        self.assertEqual(boe_debit_total, Decimal("1000.00"))
        balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        self.assertEqual(balance, Decimal("1000.00"))
