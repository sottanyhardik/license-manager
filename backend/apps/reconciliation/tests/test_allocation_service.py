# reconciliation/tests/test_allocation_service.py
"""
Real-DB tests for the Phase A partial-allocation ledger
(`apps.reconciliation.services.allocation_service`) and its effect on
`LicenseBalanceCalculator.calculate_debit()` / `.calculate_allotment()`.

Reuses `ReconciliationFixtureMixin` from `test_reconciliation.py` for the
company/license/item/BOE/trade fixtures (same conventions as the rest of
this app's tests) and adds a small allotment-side mixin for
`AllotmentModel` / `AllotmentItems` fixtures, since those aren't needed by
the Phase 1 detection-query tests this app already has.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.constants import DEC_0
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.reconciliation.models import BOEAllotmentAllocation, InvoiceBOEAllocation
from apps.reconciliation.services import allocation_service
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

EXC = Decimal("84.5")


class AllotmentFixtureMixin:
    """Allotment-side fixtures, mirroring ReconciliationFixtureMixin's style."""

    def make_allotment(self, company):
        return AllotmentModel.objects.create(
            company=company,
            item_name="Test Allotment Item",
        )

    def make_allotment_item(self, allotment, item, cif_fc, qty=Decimal("100.000")):
        return AllotmentItems.objects.create(
            item=item,
            allotment=allotment,
            cif_fc=cif_fc,
            cif_inr=cif_fc * EXC,
            qty=qty,
        )


# ---------------------------------------------------------------------------
# Invoice side: InvoiceBOEAllocation / create_invoice_boe_allocation
# ---------------------------------------------------------------------------

class InvoiceBOEAllocationTests(ReconciliationFixtureMixin, TestCase):

    def test_one_invoice_line_split_across_many_boe_rows(self):
        """One LicenseTradeLine's cif_fc split across two RowDetails rows on
        two different BOEs -- remaining balances correct after each partial
        allocation, and both rows end up fully excluded from calculate_debit."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe_a = self.make_boe(company)
        boe_b = self.make_boe(company)
        row_a = self.make_debit_row(boe_a, item, cif_fc=Decimal("600.00"))
        row_b = self.make_debit_row(boe_b, item, cif_fc=Decimal("400.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        allocation_service.create_invoice_boe_allocation(
            trade_line, row_a, qty=DEC_0, cif_fc=Decimal("600.00"),
            cif_inr=Decimal("600.00") * EXC, user=None,
        )
        _, remaining_cif_fc, _ = allocation_service.remaining_for_trade_line(trade_line)
        self.assertEqual(remaining_cif_fc, Decimal("400.00"))
        _, row_a_remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row_a)
        self.assertEqual(row_a_remaining, DEC_0)

        allocation_service.create_invoice_boe_allocation(
            trade_line, row_b, qty=DEC_0, cif_fc=Decimal("400.00"),
            cif_inr=Decimal("400.00") * EXC, user=None,
        )
        _, remaining_cif_fc, _ = allocation_service.remaining_for_trade_line(trade_line)
        self.assertEqual(remaining_cif_fc, DEC_0)
        _, row_b_remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row_b)
        self.assertEqual(row_b_remaining, DEC_0)

        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_trade(license_obj), Decimal("1000.00"))

    def test_many_invoice_lines_matched_to_one_boe_row(self):
        """Two LicenseTradeLines (from two SALE trades) both allocate
        against the SAME RowDetails row -- row ends up fully matched."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade_1 = self.make_sale_trade(company)
        trade_2 = self.make_sale_trade(company)
        line_1 = self.make_trade_line(trade_1, item, cif_fc=Decimal("600.00"))
        line_2 = self.make_trade_line(trade_2, item, cif_fc=Decimal("400.00"))

        allocation_service.create_invoice_boe_allocation(
            line_1, row, qty=DEC_0, cif_fc=Decimal("600.00"), cif_inr=Decimal("600.00") * EXC, user=None,
        )
        _, row_remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(row_remaining, Decimal("400.00"))

        allocation_service.create_invoice_boe_allocation(
            line_2, row, qty=DEC_0, cif_fc=Decimal("400.00"), cif_inr=Decimal("400.00") * EXC, user=None,
        )
        _, row_remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(row_remaining, DEC_0)

        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_trade(license_obj), Decimal("1000.00"))

    def test_full_many_to_many_chain(self):
        """Two trade lines (600, 400) and two BOE rows (700, 300) -- a
        three-allocation chain fully reconciles both sides."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe_1 = self.make_boe(company)
        boe_2 = self.make_boe(company)
        row_1 = self.make_debit_row(boe_1, item, cif_fc=Decimal("700.00"))
        row_2 = self.make_debit_row(boe_2, item, cif_fc=Decimal("300.00"))
        trade_1 = self.make_sale_trade(company)
        trade_2 = self.make_sale_trade(company)
        line_1 = self.make_trade_line(trade_1, item, cif_fc=Decimal("600.00"))
        line_2 = self.make_trade_line(trade_2, item, cif_fc=Decimal("400.00"))

        # line_1 (600) -> row_1 (700): fully consumes line_1, leaves row_1 with 100 remaining.
        allocation_service.create_invoice_boe_allocation(
            line_1, row_1, qty=DEC_0, cif_fc=Decimal("600.00"), cif_inr=Decimal("600.00") * EXC, user=None,
        )
        # line_2 (400) -> row_1 remaining (100): partial on line_2, fully consumes row_1.
        allocation_service.create_invoice_boe_allocation(
            line_2, row_1, qty=DEC_0, cif_fc=Decimal("100.00"), cif_inr=Decimal("100.00") * EXC, user=None,
        )
        # line_2 remaining (300) -> row_2 (300): fully consumes both.
        allocation_service.create_invoice_boe_allocation(
            line_2, row_2, qty=DEC_0, cif_fc=Decimal("300.00"), cif_inr=Decimal("300.00") * EXC, user=None,
        )

        _, line_1_remaining, _ = allocation_service.remaining_for_trade_line(line_1)
        _, line_2_remaining, _ = allocation_service.remaining_for_trade_line(line_2)
        _, row_1_remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row_1)
        _, row_2_remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row_2)
        self.assertEqual(line_1_remaining, DEC_0)
        self.assertEqual(line_2_remaining, DEC_0)
        self.assertEqual(row_1_remaining, DEC_0)
        self.assertEqual(row_2_remaining, DEC_0)

        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_trade(license_obj), Decimal("1000.00"))

    def test_partial_allocation_leaves_correct_unmatched_remainder(self):
        """A partial allocation must leave the UNMATCHED remainder of the
        BOE row visible to calculate_debit() -- not the whole row hidden."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        allocation_service.create_invoice_boe_allocation(
            trade_line, row, qty=DEC_0, cif_fc=Decimal("300.00"), cif_inr=Decimal("300.00") * EXC, user=None,
        )

        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), Decimal("700.00"))
        self.assertEqual(LicenseBalanceCalculator.calculate_trade(license_obj), Decimal("1000.00"))

    def test_over_allocation_rejected_exceeds_trade_line_remaining(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("500.00"))

        with self.assertRaises(ValidationError):
            allocation_service.create_invoice_boe_allocation(
                trade_line, row, qty=DEC_0, cif_fc=Decimal("600.00"),
                cif_inr=Decimal("600.00") * EXC, user=None,
            )
        # Nothing should have been persisted on a failed validation.
        self.assertFalse(InvoiceBOEAllocation.objects.filter(trade_line=trade_line).exists())

    def test_over_allocation_rejected_exceeds_row_details_remaining(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        with self.assertRaises(ValidationError):
            allocation_service.create_invoice_boe_allocation(
                trade_line, row, qty=DEC_0, cif_fc=Decimal("600.00"),
                cif_inr=Decimal("600.00") * EXC, user=None,
            )
        self.assertFalse(InvoiceBOEAllocation.objects.filter(row_details=row).exists())

    def test_cross_licence_allocation_rejected(self):
        company = self.make_company()
        license_a = self.make_license(company)
        license_b = self.make_license(company)
        item_a = self.make_item(license_a, 1)
        item_b = self.make_item(license_b, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item_b, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item_a, cif_fc=Decimal("1000.00"))

        with self.assertRaises(ValidationError):
            allocation_service.create_invoice_boe_allocation(
                trade_line, row, qty=DEC_0, cif_fc=Decimal("500.00"),
                cif_inr=Decimal("500.00") * EXC, user=None,
            )

    def test_duplicate_active_allocation_rejected(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        allocation_service.create_invoice_boe_allocation(
            trade_line, row, qty=DEC_0, cif_fc=Decimal("100.00"), cif_inr=Decimal("100.00") * EXC, user=None,
        )
        with self.assertRaisesMessage(ValidationError, "edit_invoice_boe_allocation"):
            allocation_service.create_invoice_boe_allocation(
                trade_line, row, qty=DEC_0, cif_fc=Decimal("50.00"), cif_inr=Decimal("50.00") * EXC, user=None,
            )

    def test_reversal_makes_amount_count_again_and_never_deletes(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        allocation = allocation_service.create_invoice_boe_allocation(
            trade_line, row, qty=DEC_0, cif_fc=Decimal("1000.00"), cif_inr=Decimal("1000.00") * EXC, user=None,
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), DEC_0)

        allocation_service.reverse_invoice_boe_allocation(allocation, user=None, reason="test reversal")

        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), Decimal("1000.00"))

        allocation.refresh_from_db()
        self.assertEqual(allocation.status, InvoiceBOEAllocation.STATUS_REVERSED)
        self.assertFalse(allocation.is_current)
        # Never deleted.
        self.assertTrue(InvoiceBOEAllocation.objects.filter(pk=allocation.pk).exists())

    def test_edit_supersedes_rather_than_mutates(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        original = allocation_service.create_invoice_boe_allocation(
            trade_line, row, qty=DEC_0, cif_fc=Decimal("300.00"), cif_inr=Decimal("300.00") * EXC, user=None,
        )

        updated = allocation_service.edit_invoice_boe_allocation(
            original, qty=DEC_0, cif_fc=Decimal("500.00"), cif_inr=Decimal("500.00") * EXC, user=None,
        )

        original.refresh_from_db()
        self.assertFalse(original.is_current)
        self.assertEqual(original.superseded_by_id, updated.id)
        self.assertEqual(original.allocated_cif_fc, Decimal("300.00"))  # unchanged
        self.assertEqual(original.status, InvoiceBOEAllocation.STATUS_ACTIVE)  # not reversed, just superseded

        self.assertEqual(updated.version, original.version + 1)
        self.assertEqual(updated.allocated_cif_fc, Decimal("500.00"))
        self.assertTrue(updated.is_current)

        # Both rows still exist.
        self.assertEqual(
            InvoiceBOEAllocation.objects.filter(trade_line=trade_line, row_details=row).count(), 2
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_debit(license_obj), Decimal("500.00"))


# ---------------------------------------------------------------------------
# Allotment side: BOEAllotmentAllocation / create_boe_allotment_allocation
# ---------------------------------------------------------------------------

class BOEAllotmentAllocationTests(ReconciliationFixtureMixin, AllotmentFixtureMixin, TestCase):

    def test_one_allotment_item_split_across_many_boe_rows(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe_a = self.make_boe(company)
        boe_b = self.make_boe(company)
        row_a = self.make_debit_row(boe_a, item, cif_fc=Decimal("600.00"))
        row_b = self.make_debit_row(boe_b, item, cif_fc=Decimal("400.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))

        allocation_service.create_boe_allotment_allocation(
            row_a, allotment_item, qty=DEC_0, cif_fc=Decimal("600.00"), cif_inr=Decimal("600.00") * EXC, user=None,
        )
        _, remaining, _ = allocation_service.remaining_for_allotment_item(allotment_item)
        self.assertEqual(remaining, Decimal("400.00"))

        allocation_service.create_boe_allotment_allocation(
            row_b, allotment_item, qty=DEC_0, cif_fc=Decimal("400.00"), cif_inr=Decimal("400.00") * EXC, user=None,
        )
        _, remaining, _ = allocation_service.remaining_for_allotment_item(allotment_item)
        self.assertEqual(remaining, DEC_0)

        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(license_obj), DEC_0)

    def test_many_allotment_items_matched_to_one_boe_row(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        # AllotmentItems has unique_together=("item", "allotment") -- two
        # allotment items against the SAME item need separate Allotment
        # headers (as would happen in practice: two separate allotment
        # documents both partially sourcing the same import).
        allotment_1 = self.make_allotment(company)
        allotment_2 = self.make_allotment(company)
        allotment_item_1 = self.make_allotment_item(allotment_1, item, cif_fc=Decimal("600.00"))
        allotment_item_2 = self.make_allotment_item(allotment_2, item, cif_fc=Decimal("400.00"))

        allocation_service.create_boe_allotment_allocation(
            row, allotment_item_1, qty=DEC_0, cif_fc=Decimal("600.00"), cif_inr=Decimal("600.00") * EXC, user=None,
        )
        _, row_remaining, _ = allocation_service.remaining_for_row_details_allotment_side(row)
        self.assertEqual(row_remaining, Decimal("400.00"))

        allocation_service.create_boe_allotment_allocation(
            row, allotment_item_2, qty=DEC_0, cif_fc=Decimal("400.00"), cif_inr=Decimal("400.00") * EXC, user=None,
        )
        _, row_remaining, _ = allocation_service.remaining_for_row_details_allotment_side(row)
        self.assertEqual(row_remaining, DEC_0)

        self.assertEqual(
            LicenseBalanceCalculator.calculate_allotment(license_obj), DEC_0
        )

    def test_full_many_to_many_chain(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe_1 = self.make_boe(company)
        boe_2 = self.make_boe(company)
        row_1 = self.make_debit_row(boe_1, item, cif_fc=Decimal("700.00"))
        row_2 = self.make_debit_row(boe_2, item, cif_fc=Decimal("300.00"))
        # Two separate Allotment headers -- see comment in
        # test_many_allotment_items_matched_to_one_boe_row about
        # unique_together=("item", "allotment").
        allotment_1 = self.make_allotment(company)
        allotment_2 = self.make_allotment(company)
        allotment_item_1 = self.make_allotment_item(allotment_1, item, cif_fc=Decimal("600.00"))
        allotment_item_2 = self.make_allotment_item(allotment_2, item, cif_fc=Decimal("400.00"))

        allocation_service.create_boe_allotment_allocation(
            row_1, allotment_item_1, qty=DEC_0, cif_fc=Decimal("600.00"),
            cif_inr=Decimal("600.00") * EXC, user=None,
        )
        allocation_service.create_boe_allotment_allocation(
            row_1, allotment_item_2, qty=DEC_0, cif_fc=Decimal("100.00"),
            cif_inr=Decimal("100.00") * EXC, user=None,
        )
        allocation_service.create_boe_allotment_allocation(
            row_2, allotment_item_2, qty=DEC_0, cif_fc=Decimal("300.00"),
            cif_inr=Decimal("300.00") * EXC, user=None,
        )

        _, item_1_remaining, _ = allocation_service.remaining_for_allotment_item(allotment_item_1)
        _, item_2_remaining, _ = allocation_service.remaining_for_allotment_item(allotment_item_2)
        self.assertEqual(item_1_remaining, DEC_0)
        self.assertEqual(item_2_remaining, DEC_0)
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(license_obj), DEC_0)

    def test_partial_allocation_leaves_correct_unmatched_remainder(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))

        allocation_service.create_boe_allotment_allocation(
            row, allotment_item, qty=DEC_0, cif_fc=Decimal("300.00"), cif_inr=Decimal("300.00") * EXC, user=None,
        )

        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(license_obj), Decimal("700.00"))

    def test_over_allocation_rejected_exceeds_allotment_item_remaining(self):
        company = self.make_company()
        item_license = self.make_license(company)
        item = self.make_item(item_license, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("500.00"))

        with self.assertRaises(ValidationError):
            allocation_service.create_boe_allotment_allocation(
                row, allotment_item, qty=DEC_0, cif_fc=Decimal("600.00"),
                cif_inr=Decimal("600.00") * EXC, user=None,
            )
        self.assertFalse(BOEAllotmentAllocation.objects.filter(allotment_item=allotment_item).exists())

    def test_over_allocation_rejected_exceeds_row_details_remaining(self):
        company = self.make_company()
        item_license = self.make_license(company)
        item = self.make_item(item_license, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("500.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))

        with self.assertRaises(ValidationError):
            allocation_service.create_boe_allotment_allocation(
                row, allotment_item, qty=DEC_0, cif_fc=Decimal("600.00"),
                cif_inr=Decimal("600.00") * EXC, user=None,
            )
        self.assertFalse(BOEAllotmentAllocation.objects.filter(row_details=row).exists())

    def test_cross_licence_allocation_rejected(self):
        company = self.make_company()
        license_a = self.make_license(company)
        license_b = self.make_license(company)
        item_a = self.make_item(license_a, 1)
        item_b = self.make_item(license_b, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item_a, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item_b, cif_fc=Decimal("1000.00"))

        with self.assertRaises(ValidationError):
            allocation_service.create_boe_allotment_allocation(
                row, allotment_item, qty=DEC_0, cif_fc=Decimal("500.00"),
                cif_inr=Decimal("500.00") * EXC, user=None,
            )

    def test_allotment_item_with_no_item_rejected_cleanly(self):
        """AllotmentItems.item is nullable -- must raise ValidationError, not
        AttributeError, when there's no licence to validate against."""
        company = self.make_company()
        item_license = self.make_license(company)
        item = self.make_item(item_license, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = AllotmentItems.objects.create(
            item=None,
            allotment=allotment,
            cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC,
            qty=Decimal("100.000"),
        )

        with self.assertRaises(ValidationError):
            allocation_service.create_boe_allotment_allocation(
                row, allotment_item, qty=DEC_0, cif_fc=Decimal("500.00"),
                cif_inr=Decimal("500.00") * EXC, user=None,
            )

    def test_duplicate_active_allocation_rejected(self):
        company = self.make_company()
        item_license = self.make_license(company)
        item = self.make_item(item_license, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))

        allocation_service.create_boe_allotment_allocation(
            row, allotment_item, qty=DEC_0, cif_fc=Decimal("100.00"), cif_inr=Decimal("100.00") * EXC, user=None,
        )
        with self.assertRaisesMessage(ValidationError, "edit_boe_allotment_allocation"):
            allocation_service.create_boe_allotment_allocation(
                row, allotment_item, qty=DEC_0, cif_fc=Decimal("50.00"), cif_inr=Decimal("50.00") * EXC, user=None,
            )

    def test_reversal_makes_amount_count_again_and_never_deletes(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))

        allocation = allocation_service.create_boe_allotment_allocation(
            row, allotment_item, qty=DEC_0, cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC, user=None,
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(license_obj), DEC_0)

        allocation_service.reverse_boe_allotment_allocation(allocation, user=None, reason="test reversal")

        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(license_obj), Decimal("1000.00"))

        allocation.refresh_from_db()
        self.assertEqual(allocation.status, BOEAllotmentAllocation.STATUS_REVERSED)
        self.assertFalse(allocation.is_current)
        self.assertTrue(BOEAllotmentAllocation.objects.filter(pk=allocation.pk).exists())

    def test_edit_supersedes_rather_than_mutates(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))

        original = allocation_service.create_boe_allotment_allocation(
            row, allotment_item, qty=DEC_0, cif_fc=Decimal("300.00"),
            cif_inr=Decimal("300.00") * EXC, user=None,
        )

        updated = allocation_service.edit_boe_allotment_allocation(
            original, qty=DEC_0, cif_fc=Decimal("500.00"), cif_inr=Decimal("500.00") * EXC, user=None,
        )

        original.refresh_from_db()
        self.assertFalse(original.is_current)
        self.assertEqual(original.superseded_by_id, updated.id)
        self.assertEqual(original.allocated_cif_fc, Decimal("300.00"))
        self.assertEqual(original.status, BOEAllotmentAllocation.STATUS_ACTIVE)

        self.assertEqual(updated.version, original.version + 1)
        self.assertEqual(updated.allocated_cif_fc, Decimal("500.00"))
        self.assertTrue(updated.is_current)

        self.assertEqual(
            BOEAllotmentAllocation.objects.filter(row_details=row, allotment_item=allotment_item).count(), 2
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_allotment(license_obj), Decimal("500.00"))


# ---------------------------------------------------------------------------
# reverse_allocation() dispatcher
# ---------------------------------------------------------------------------

class ReverseAllocationDispatcherTests(ReconciliationFixtureMixin, AllotmentFixtureMixin, TestCase):

    def test_dispatches_to_invoice_side(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))
        allocation = allocation_service.create_invoice_boe_allocation(
            trade_line, row, qty=DEC_0, cif_fc=Decimal("1000.00"), cif_inr=Decimal("1000.00") * EXC, user=None,
        )

        allocation_service.reverse_allocation(allocation, user=None, reason="dispatch test")

        allocation.refresh_from_db()
        self.assertEqual(allocation.status, InvoiceBOEAllocation.STATUS_REVERSED)

    def test_dispatches_to_allotment_side(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        allotment = self.make_allotment(company)
        allotment_item = self.make_allotment_item(allotment, item, cif_fc=Decimal("1000.00"))
        allocation = allocation_service.create_boe_allotment_allocation(
            row, allotment_item, qty=DEC_0, cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC, user=None,
        )

        allocation_service.reverse_allocation(allocation, user=None, reason="dispatch test")

        allocation.refresh_from_db()
        self.assertEqual(allocation.status, BOEAllotmentAllocation.STATUS_REVERSED)

    def test_rejects_unknown_type(self):
        with self.assertRaises(TypeError):
            allocation_service.reverse_allocation(object(), user=None, reason="nope")
