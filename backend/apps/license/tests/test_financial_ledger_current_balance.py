"""OD-10 (owner decision 2026-11-15): the Financial Ledger "Current Balance"
row shows the Balance Engine value (`calculate_financial_balance`), i.e.
Available = Original - (BOE + outstanding allotment + billed-without-BOE).

Regression context: Phase 4E-D (7fd7104d) overwrote that row with the
canonical trade-only running total (opening + purchases - sales), so every
licence with BOE/allotment utilisation showed an inflated balance on screen,
PDF and Excel. Existing tests called `build_financial_ledger()` without
`canonical_data` (bypassing the override) or used trade-only licences where
both figures coincide, so these tests go through `build()` with BOE debits.

The trade-only total is kept, under its own name `trade_running_balance`.
"""
from decimal import Decimal

from django.test import TestCase

from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder
from apps.license.tests import test_balance_ledger_views as _ledger_view_tests
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin
from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin


class FinancialLedgerCurrentBalanceTests(LicenseBalanceLedgerFixtureMixin, ReconciliationFixtureMixin, TestCase):
    # Module import (not the TestCase class) so pytest doesn't re-collect its tests here.
    _make_purchase_trade = _ledger_view_tests.FinancialLedgerOpeningBalanceGateTests._make_purchase_trade

    def _licence_with_boe_debit(self, original_cif, boe_cif):
        company = self.make_company()
        licence = self.make_license(company)
        LicenseExportItemModel.objects.create(license=licence, cif_fc=original_cif)
        item = self.make_item(licence, 1)
        self.make_debit_row(self.make_boe(company), item, cif_fc=boe_cif)
        return licence, company, item

    def _final_row(self, dataset):
        rows = dataset["financial_ledger"]["rows"]
        self.assertEqual(rows[-1]["row_kind"], "final")
        return rows[-1]

    def test_current_balance_is_engine_value_when_boe_utilised(self):
        licence, _company, _item = self._licence_with_boe_debit(Decimal("50000.00"), Decimal("10000.00"))

        dataset = LicenseBalanceLedgerBuilder.build(licence)
        final_row = self._final_row(dataset)
        summary = dataset["financial_ledger"]["summary"]
        engine = LicenseBalanceCalculator.calculate_financial_balance(licence)

        self.assertEqual(engine, Decimal("40000.00"))
        self.assertEqual(final_row["running_balance"], Decimal("40000.00"))
        self.assertEqual(summary["computed_balance"], Decimal("40000.00"))
        self.assertEqual(summary["engine_balance"], Decimal("40000.00"))
        self.assertFalse(summary["mismatched"])
        self.assertFalse(final_row["mismatched"])
        self.assertNotIn("MISMATCH", final_row["remarks"])

    def test_trade_running_balance_is_exposed_separately_and_unchanged(self):
        licence, company, item = self._licence_with_boe_debit(Decimal("50000.00"), Decimal("10000.00"))
        self._make_purchase_trade(company, item, cif_fc=Decimal("50000.00"))

        dataset = LicenseBalanceLedgerBuilder.build(licence)
        summary = dataset["financial_ledger"]["summary"]
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=licence.id, license_type="DFIA"
        )

        # Trade-only total keeps its value, under its own explicit name ...
        self.assertEqual(summary["trade_running_balance"], canonical["license_running_balance"])
        # ... and never replaces the engine-backed Current Balance.
        self.assertEqual(self._final_row(dataset)["running_balance"],
                         LicenseBalanceCalculator.calculate_financial_balance(licence))
