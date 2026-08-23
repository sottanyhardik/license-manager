"""
Unit tests for `apps.reconciliation.services.allocation_service`'s
external-invoice-link functions (`mark_boe_as_external_invoice`,
`reverse_external_invoice_link`) and their interaction with
`remaining_for_row_details_invoice_side` / `missing_invoice` detection.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.constants import DEC_0
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.reconciliation.models import ExternalInvoiceLink
from apps.reconciliation.services import allocation_service, queries
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

EXC = Decimal("84.5")


class ExternalInvoiceLinkTests(ReconciliationFixtureMixin, TestCase):

    def test_mark_creates_active_link_and_reduces_remaining(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        link = allocation_service.mark_boe_as_external_invoice(
            row, "OTH-001245", qty=DEC_0, cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC, user=None,
        )

        self.assertEqual(link.status, ExternalInvoiceLink.STATUS_ACTIVE)
        self.assertTrue(link.is_current)
        self.assertEqual(link.invoice_number, "OTH-001245")

        _, remaining_cif_fc, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(remaining_cif_fc, DEC_0)

    def test_mark_does_not_affect_licence_balance(self):
        """Marking a BOE's invoice as external is a purchase-side
        reconciliation annotation only -- it must never move
        calculate_debit()/calculate_balance()."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        before = LicenseBalanceCalculator.calculate_debit(license_obj)
        allocation_service.mark_boe_as_external_invoice(
            row, "OTH-001245", qty=DEC_0, cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC, user=None,
        )
        after = LicenseBalanceCalculator.calculate_debit(license_obj)

        self.assertEqual(before, after)
        self.assertEqual(after, Decimal("1000.00"))  # still a full, unmatched debit

    def test_blank_invoice_number_rejected(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        with self.assertRaises(ValidationError):
            allocation_service.mark_boe_as_external_invoice(
                row, "   ", qty=DEC_0, cif_fc=Decimal("500.00"),
                cif_inr=Decimal("500.00") * EXC, user=None,
            )

    def test_over_allocation_rejected(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        with self.assertRaises(ValidationError):
            allocation_service.mark_boe_as_external_invoice(
                row, "OTH-001245", qty=DEC_0, cif_fc=Decimal("1500.00"),
                cif_inr=Decimal("1500.00") * EXC, user=None,
            )

    def test_shares_invoice_side_capacity_with_system_allocation(self):
        """Partial external mark + partial system InvoiceBOEAllocation must
        not together exceed the row's own total -- they draw from the same
        remaining-on-invoice-side balance."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self.make_sale_trade(company)
        trade_line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        allocation_service.mark_boe_as_external_invoice(
            row, "OTH-001245", qty=DEC_0, cif_fc=Decimal("700.00"),
            cif_inr=Decimal("700.00") * EXC, user=None,
        )
        _, remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(remaining, Decimal("300.00"))

        # Exactly the remainder succeeds.
        allocation_service.create_invoice_boe_allocation(
            trade_line, row, qty=DEC_0, cif_fc=Decimal("300.00"),
            cif_inr=Decimal("300.00") * EXC, user=None,
        )
        _, remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(remaining, DEC_0)

    def test_reverse_makes_amount_available_again(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        link = allocation_service.mark_boe_as_external_invoice(
            row, "OTH-001245", qty=DEC_0, cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC, user=None,
        )
        _, remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(remaining, DEC_0)

        reversed_link = allocation_service.reverse_external_invoice_link(link, user=None, reason="wrong BOE")
        self.assertEqual(reversed_link.status, ExternalInvoiceLink.STATUS_REVERSED)
        self.assertFalse(reversed_link.is_current)

        _, remaining, _ = allocation_service.remaining_for_row_details_invoice_side(row)
        self.assertEqual(remaining, Decimal("1000.00"))

    def test_missing_invoice_excludes_boe_once_marked_and_reincludes_after_reversal(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, invoice_no="")  # blank -> would normally show as missing
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        boe_ids_before = {r["boe_id"] for r in queries.missing_invoice()}
        self.assertIn(boe.id, boe_ids_before)

        link = allocation_service.mark_boe_as_external_invoice(
            row, "OTH-001245", qty=DEC_0, cif_fc=Decimal("1000.00"),
            cif_inr=Decimal("1000.00") * EXC, user=None,
        )

        boe_ids_after_mark = {r["boe_id"] for r in queries.missing_invoice()}
        self.assertNotIn(boe.id, boe_ids_after_mark)

        allocation_service.reverse_external_invoice_link(link, user=None, reason="test reversal")

        boe_ids_after_reverse = {r["boe_id"] for r in queries.missing_invoice()}
        self.assertIn(boe.id, boe_ids_after_reverse)
