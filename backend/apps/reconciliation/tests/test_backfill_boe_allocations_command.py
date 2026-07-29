# reconciliation/tests/test_backfill_boe_allocations_command.py
"""
Tests for the `backfill_boe_allocations` management command — the one-time,
explicitly-gated migration that turns unambiguous legacy `trade.boes` links
into real `InvoiceBOEAllocation` records. See
`apps.reconciliation.services.boe_link_reconciler` for the matching rule
this command drives.
"""

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.reconciliation.models import InvoiceBOEAllocation
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin


class BackfillBoeAllocationsCommandTests(ReconciliationFixtureMixin, TestCase):
    def _make_clean_match(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("3214.77"), qty=Decimal("2339.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("3214.77"), qty_kg=Decimal("2339.0000"))
        return trade, line, row

    def test_dry_run_makes_zero_writes(self):
        self._make_clean_match()
        out = StringIO()
        call_command("backfill_boe_allocations", stdout=out)

        self.assertFalse(InvoiceBOEAllocation.objects.exists())
        self.assertIn("DRY RUN", out.getvalue())
        self.assertIn("auto_migrated: 1", out.getvalue())

    def test_apply_creates_expected_allocation_only(self):
        trade, line, row = self._make_clean_match()
        out = StringIO()
        call_command("backfill_boe_allocations", "--apply", stdout=out)

        self.assertIn("APPLY", out.getvalue())
        allocations = InvoiceBOEAllocation.objects.filter(
            trade_line=line, row_details=row,
            status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
        )
        self.assertEqual(allocations.count(), 1)
        allocation = allocations.get()
        self.assertEqual(allocation.allocated_cif_fc, Decimal("3214.77"))
        self.assertEqual(allocation.allocated_qty, Decimal("2339.000"))

    def test_report_covers_all_status_buckets(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        # auto_migrated
        item1 = self.make_item(license_obj, 1)
        boe1 = self.make_boe(company)
        self.make_debit_row(boe1, item1, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade1 = self.make_sale_trade(company, boes=[boe1])
        self.make_trade_line(trade1, item1, cif_fc=Decimal("500.00"), qty_kg=Decimal("100.0000"))

        # mismatch
        item2 = self.make_item(license_obj, 2)
        boe2 = self.make_boe(company)
        self.make_debit_row(boe2, item2, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade2 = self.make_sale_trade(company, boes=[boe2])
        self.make_trade_line(trade2, item2, cif_fc=Decimal("400.00"), qty_kg=Decimal("100.0000"))

        # no_match
        item3 = self.make_item(license_obj, 3)
        boe3 = self.make_boe(company)
        trade3 = self.make_sale_trade(company, boes=[boe3])
        self.make_trade_line(trade3, item3, cif_fc=Decimal("300.00"), qty_kg=Decimal("50.0000"))

        # ambiguous
        item4 = self.make_item(license_obj, 4)
        boe4a = self.make_boe(company)
        boe4b = self.make_boe(company)
        self.make_debit_row(boe4a, item4, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))
        self.make_debit_row(boe4b, item4, cif_fc=Decimal("200.00"), qty=Decimal("20.000"))
        trade4 = self.make_sale_trade(company, boes=[boe4a, boe4b])
        self.make_trade_line(trade4, item4, cif_fc=Decimal("200.00"), qty_kg=Decimal("20.0000"))

        out = StringIO()
        call_command("backfill_boe_allocations", stdout=out)
        output = out.getvalue()

        self.assertIn("auto_migrated: 1", output)
        self.assertIn("mismatch: 1", output)
        self.assertIn("no_match: 1", output)
        self.assertIn("ambiguous: 1", output)
        self.assertIn("Report written to", output)

        report_path = output.split("Report written to")[1].strip().splitlines()[0]
        with open(report_path) as f:
            content = f.read()
        self.assertIn("auto_migrated", content)
        self.assertIn("ambiguous", content)
        self.assertIn("mismatch", content)
        self.assertIn("no_match", content)

    def test_rerun_after_apply_is_idempotent(self):
        self._make_clean_match()
        call_command("backfill_boe_allocations", "--apply", stdout=StringIO())
        call_command("backfill_boe_allocations", "--apply", stdout=StringIO())

        self.assertEqual(InvoiceBOEAllocation.objects.count(), 1)
