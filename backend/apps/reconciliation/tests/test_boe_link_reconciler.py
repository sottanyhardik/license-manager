# reconciliation/tests/test_boe_link_reconciler.py
"""
Tests for `apps.reconciliation.services.boe_link_reconciler` — the
conservative, single-source-of-truth matcher that turns a legacy
`trade.boes` attachment into a real `InvoiceBOEAllocation` only when the
match is unambiguous (see the module docstring for the double-debit bug
this closes: license 2399 / trade LML/2025-26/064 / BOE 4560271, reproduced
as `test_exact_one_to_one_match_is_auto_migrated` below).
"""

from decimal import Decimal

from django.test import TestCase

from apps.core.constants import DEC_0
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.reconciliation.models import InvoiceBOEAllocation
from apps.reconciliation.services.allocation_service import (
    create_invoice_boe_allocation,
    reverse_invoice_boe_allocation,
)
from apps.reconciliation.services.boe_link_reconciler import (
    find_boe_allocation_candidates,
    reconcile_trade_boe_links,
)
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

EXC = Decimal("84.5")


class BoeLinkReconcilerTests(ReconciliationFixtureMixin, TestCase):
    def test_exact_one_to_one_match_is_auto_migrated(self):
        """Reproduces the real license-2399 scenario: a SALE trade line's
        cif_fc/qty exactly match one RowDetails row on an attached BOE, with
        no existing allocation — must auto-migrate and stop the double debit.

        `LicenseBalanceCalculator.get_debit_rows()` nets out this EXACT same
        unambiguous match virtually (see its `_virtual_boe_debit_exclusion_
        case`, which reuses this module's `reconcile_trade_boe_links` in
        dry-run) — so the double debit is already closed by the calculation
        itself, even before anyone runs `reconcile_trade_boe_links` for
        real. Persisting the allocation (this test's main subject) then
        keeps `calculate_debit()` at 0 via a real record instead of an
        inferred one — the calculated result doesn't change, but the
        source of truth becomes durable/auditable instead of recomputed
        every time."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("3214.77"), qty=Decimal("2339.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("3214.77"), qty_kg=Decimal("2339.0000"))

        # Before persisting any allocation: the unambiguous match is already
        # netted out VIRTUALLY by calculate_debit(), so the double debit
        # never surfaces in the first place for this clean-cut case.
        debit_before = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit_before, DEC_0)

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "auto_migrated")
        self.assertEqual(results[0]["trade_line_id"], line.id)
        self.assertTrue(
            InvoiceBOEAllocation.objects.filter(
                trade_line=line, row_details=row, status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
            ).exists()
        )

        # Now backed by a real, persisted allocation instead of an inferred
        # one — calculate_debit() stays at 0 either way.
        debit_after = LicenseBalanceCalculator.calculate_debit(license_obj)
        self.assertEqual(debit_after, DEC_0)

    def test_dry_run_reports_without_writing(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("500.00"), qty_kg=Decimal("100.0000"))

        results = reconcile_trade_boe_links(trade, dry_run=True)

        self.assertEqual(results[0]["status"], "auto_migrated")
        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_ambiguous_multiple_candidates_is_not_migrated(self):
        """Two DIFFERENT BOEs both attached to the trade each have a debit
        row for the same item — a single RowDetails can't duplicate
        (bill_of_entry, sr_number, transaction_type) per the DB's own
        unique constraint, so real ambiguity only arises across BOEs."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe_a = self.make_boe(company)
        boe_b = self.make_boe(company)
        self.make_debit_row(boe_a, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        self.make_debit_row(boe_b, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe_a, boe_b])
        self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"), qty_kg=Decimal("500.0000"))

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results[0]["status"], "ambiguous")
        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_no_candidate_is_reported_not_migrated(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        # No RowDetails on this BOE for this item at all.
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("750.00"), qty_kg=Decimal("300.0000"))

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results[0]["status"], "no_match")
        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_cif_mismatch_beyond_tolerance_is_not_migrated(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        # CIF differs by 50 — far beyond RECONCILIATION_CIF_TOLERANCE (1.00).
        self.make_trade_line(trade, item, cif_fc=Decimal("950.00"), qty_kg=Decimal("500.0000"))

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results[0]["status"], "mismatch")
        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_qty_mismatch_beyond_tolerance_is_not_migrated(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        # Qty differs by 50 — far beyond RECONCILIATION_QTY_TOLERANCE (1.000).
        self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"), qty_kg=Decimal("450.0000"))

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results[0]["status"], "mismatch")
        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_already_allocated_line_is_skipped(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"), qty_kg=Decimal("500.0000"))
        create_invoice_boe_allocation(
            trade_line=line, row_details=row, qty=Decimal("500.000"),
            cif_fc=Decimal("1000.00"), cif_inr=Decimal("1000.00") * EXC, user=None,
        )

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results, [])

    def test_reversed_allocation_is_reconsidered(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        row = self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"), qty_kg=Decimal("500.0000"))
        allocation = create_invoice_boe_allocation(
            trade_line=line, row_details=row, qty=Decimal("500.000"),
            cif_fc=Decimal("1000.00"), cif_inr=Decimal("1000.00") * EXC, user=None,
        )
        reverse_invoice_boe_allocation(allocation, user=None, reason="test reversal")

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results[0]["status"], "auto_migrated")

    def test_rerun_is_idempotent_single_allocation(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        self.make_trade_line(trade, item, cif_fc=Decimal("1000.00"), qty_kg=Decimal("500.0000"))

        reconcile_trade_boe_links(trade)
        second_run_results = reconcile_trade_boe_links(trade)

        self.assertEqual(second_run_results, [])
        self.assertEqual(InvoiceBOEAllocation.objects.count(), 1)

    def test_purchase_trade_is_never_reconciled(self):
        from apps.trade.models import LicenseTrade

        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("500.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        trade.direction = LicenseTrade.DIR_PURCHASE
        trade.save()

        results = reconcile_trade_boe_links(trade)

        self.assertEqual(results, [])
        self.assertFalse(InvoiceBOEAllocation.objects.exists())

    def test_find_candidates_excludes_rows_on_other_items(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item_a = self.make_item(license_obj, 1)
        item_b = self.make_item(license_obj, 2)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item_b, cif_fc=Decimal("500.00"), qty=Decimal("100.000"))
        trade = self.make_sale_trade(company, boes=[boe])
        line = self.make_trade_line(trade, item_a, cif_fc=Decimal("500.00"), qty_kg=Decimal("100.0000"))

        candidates = find_boe_allocation_candidates(line)

        self.assertEqual(candidates, [])
