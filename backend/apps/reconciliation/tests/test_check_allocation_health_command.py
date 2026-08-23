# reconciliation/tests/test_check_allocation_health_command.py
"""
Tests for the `check_allocation_health` management command — a permanent,
always-read-only data-health diagnostic (see the command's own docstring).
Verifies it surfaces (a) an unresolved legacy trade.boes link, (b) a
duplicate ACTIVE allocation, and (c) an over-allocation beyond a row's own
CIF — and never writes anything.
"""

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.reconciliation.models import InvoiceBOEAllocation
from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

EXC = Decimal("84.5")


class CheckAllocationHealthCommandTests(ReconciliationFixtureMixin, TestCase):
    def _run(self):
        out = StringIO()
        call_command("check_allocation_health", stdout=out)
        return out.getvalue()

    def test_command_is_read_only(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"), qty_kg=Decimal("100.0000"))

        self._run()

        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_surfaces_unresolved_boe_link(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        # CIF mismatch beyond tolerance -> stays unresolved.
        self.make_trade_line(trade, item, cif_fc=Decimal("450.00"), qty_kg=Decimal("100.0000"))

        output = self._run()

        self.assertIn("[1] Trades with .boes linked but unresolved SALE lines: 1", output)
        self.assertIn(f"Trade {trade.id}", output)

    def test_auto_migratable_link_is_not_reported_as_unresolved(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"), qty_kg=Decimal("100.0000"))

        output = self._run()

        self.assertIn("[1] Trades with .boes linked but unresolved SALE lines: 0", output)

    def test_surfaces_duplicate_active_allocation(self):
        """`InvoiceBOEAllocation` has no DB-level uniqueness on (trade_line,
        row_details) — only the service layer prevents new duplicates — so
        this seeds a duplicate directly via the ORM to prove the command's
        own defensive check catches historical/legacy duplicates."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"), qty_kg=Decimal("500.0000"))

        InvoiceBOEAllocation.objects.create(
            trade_line=line, row_details=row, allocated_qty=Decimal("250.000"),
            allocated_cif_fc=Decimal("500.00"), allocated_cif_inr=Decimal("500.00") * EXC,
            status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
        )
        InvoiceBOEAllocation.objects.create(
            trade_line=line, row_details=row, allocated_qty=Decimal("250.000"),
            allocated_cif_fc=Decimal("500.00"), allocated_cif_inr=Decimal("500.00") * EXC,
            status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
        )

        output = self._run()

        self.assertIn("[4] Duplicate ACTIVE allocations for the same (trade line, BOE row): 1", output)

    def test_surfaces_boe_over_allocation(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("5000.00"), qty_kg=Decimal("500.0000"))

        # Bypass the service layer's own _validate_fits guard to simulate a
        # pre-existing bad row (e.g. from before this validation existed).
        InvoiceBOEAllocation.objects.create(
            trade_line=line, row_details=row, allocated_qty=Decimal("500.000"),
            allocated_cif_fc=Decimal("5000.00"), allocated_cif_inr=Decimal("5000.00") * EXC,
            status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
        )

        output = self._run()

        self.assertIn("[2] BOE rows allocated beyond their own CIF: 1", output)

    def test_service_layer_prevents_the_over_allocation_case_going_forward(self):
        """Companion to the above: prove `create_invoice_boe_allocation`
        itself would reject the same over-allocation, so [2]/[3] only ever
        catch pre-existing/legacy data, never new writes."""
        from django.core.exceptions import ValidationError

        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("5000.00"), qty_kg=Decimal("500.0000"))

        with self.assertRaises(ValidationError):
            create_invoice_boe_allocation(
                trade_line=line, row_details=row, qty=Decimal("500.000"),
                cif_fc=Decimal("5000.00"), cif_inr=Decimal("5000.00") * EXC, user=None,
            )
