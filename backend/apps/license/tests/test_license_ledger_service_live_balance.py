"""
Regression coverage for BL-LEDGER-02's remaining stale-balance readers in
`apps.license.services.ledger_service`: `build_license_queryset`'s and
`search_licenses`'s `min_balance` filters, `get_ledger_summary`'s
`min_balance` filter AND its `balance_value_usd` aggregate, and
`get_license_wise_trades`'s `min_balance` post-filter and `balance_value`
sort key. All six used to read the cached `balance__balance_cif` column
directly; all six now resolve against the LIVE, batched-computed balance
(`LicenseBalanceCalculator.calculate_financial_balance_for_licenses`),
matching the fix already applied to `prepare_dfia_data`'s displayed
`balance_value` (see that function's own comment).

`ledger.py::available_for_sale`'s identical fix is covered separately in
`test_ledger_available_for_sale_live_balance.py`.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.ledger_service import (
    build_license_queryset,
    get_ledger_summary,
    get_license_wise_trades,
    search_licenses,
)
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin
from apps.trade.models import LicenseTrade, LicenseTradeLine


class LedgerServiceLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def _make_license(self, company, number, *, export_cif, debit_cif):
        license_obj = LicenseDetailsModel.objects.create(
            license_number=number,
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=365),
            exporter=company,
        )
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=export_cif)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget A",
            quantity=Decimal("1000.000"), cif_fc=export_cif,
        )
        if debit_cif:
            boe = self.make_boe(company)
            self.make_debit_row(boe, item, cif_fc=debit_cif, qty=Decimal("100.000"))
        return license_obj, item

    def _stale_cache(self, license_obj, fake_balance_cif):
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=fake_balance_cif)
        license_obj.refresh_from_db()

    def _make_purchase_trade(self, seller, buyer, item, cif_fc):
        """A PURCHASE trade switches `calculate_opening_balance` from the
        license's own export-item credit to the trade's `cif_fc` (a plain
        stored field, NOT derived from `cif_inr`/`pct` at read time) --
        must be set explicitly or the license's live balance floors to 0."""
        trade = LicenseTrade.objects.create(
            direction="PURCHASE", license_type="DFIA",
            from_company=seller, to_company=buyer,
            invoice_number=f"LEDGER-LIVE-{item.license_id}", invoice_date=date.today(),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, description="Widget A",
            mode="CIF_INR", cif_inr=cif_fc * Decimal("84.5"), cif_fc=cif_fc, pct=Decimal("10.000"),
        )
        return trade

    def setUp(self):
        self.company = self.make_company("Ledger Live Balance Exporter")
        self.buyer = self.make_company("Ledger Live Balance Buyer")

    def test_build_license_queryset_min_balance_uses_live_balance(self):
        high, _ = self._make_license(self.company, "DFIA-LIVE-HIGH-001", export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"))
        low, _ = self._make_license(self.company, "DFIA-LIVE-LOW-001", export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"))
        live_high = LicenseBalanceCalculator.calculate_financial_balance(high)
        live_low = LicenseBalanceCalculator.calculate_financial_balance(low)
        self.assertGreater(live_high, live_low)
        self._stale_cache(high, Decimal("0.00"))
        self._stale_cache(low, Decimal("999999.00"))

        results = build_license_queryset(
            {"license_type": "DFIA", "min_balance": str((live_high + live_low) / 2), "active_only": "false"}
        )
        numbers = {r["license_number"] for r in results}
        self.assertIn(high.license_number, numbers)
        self.assertNotIn(low.license_number, numbers)

    def test_search_licenses_min_balance_uses_live_balance(self):
        high, _ = self._make_license(self.company, "DFIA-LIVE-HIGH-002", export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"))
        low, _ = self._make_license(self.company, "DFIA-LIVE-LOW-002", export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"))
        live_high = LicenseBalanceCalculator.calculate_financial_balance(high)
        live_low = LicenseBalanceCalculator.calculate_financial_balance(low)
        self._stale_cache(high, Decimal("0.00"))
        self._stale_cache(low, Decimal("999999.00"))

        result = search_licenses(
            {"q": "DFIA-LIVE-", "license_type": "DFIA", "min_balance": str((live_high + live_low) / 2), "active_only": "false"}
        )
        numbers = {r["license_number"] for r in result["results"]}
        self.assertIn(high.license_number, numbers)
        self.assertNotIn(low.license_number, numbers)

    def test_get_ledger_summary_min_balance_filters_by_live_balance(self):
        high, _ = self._make_license(self.company, "DFIA-LIVE-HIGH-003", export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"))
        low, _ = self._make_license(self.company, "DFIA-LIVE-LOW-003", export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"))
        live_high = LicenseBalanceCalculator.calculate_financial_balance(high)
        live_low = LicenseBalanceCalculator.calculate_financial_balance(low)
        self._stale_cache(high, Decimal("0.00"))
        self._stale_cache(low, Decimal("999999.00"))

        summary = get_ledger_summary(
            {"license_type": "DFIA", "min_balance": str((live_high + live_low) / 2), "active_only": "false"}
        )
        self.assertEqual(summary["dfia"]["total_licenses"], 1)

    def test_get_ledger_summary_balance_aggregate_uses_live_balance(self):
        high, _ = self._make_license(self.company, "DFIA-LIVE-HIGH-004", export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"))
        low, _ = self._make_license(self.company, "DFIA-LIVE-LOW-004", export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"))
        live_high = LicenseBalanceCalculator.calculate_financial_balance(high)
        live_low = LicenseBalanceCalculator.calculate_financial_balance(low)
        self._stale_cache(high, Decimal("0.00"))
        self._stale_cache(low, Decimal("999999.00"))

        summary = get_ledger_summary({"license_type": "DFIA", "active_only": "false"})
        expected = round(float(live_high + live_low), 2)
        self.assertEqual(summary["dfia"]["balance_value_usd"], expected)
        # The stale cache sum (0 + 999999) must NOT be what's reported.
        self.assertNotEqual(summary["dfia"]["balance_value_usd"], 999999.00)

    def test_get_license_wise_trades_min_balance_post_filter_uses_live_balance(self):
        high, high_item = self._make_license(self.company, "DFIA-LIVE-HIGH-005", export_cif=Decimal("0"), debit_cif=Decimal("1000.00"))
        low, low_item = self._make_license(self.company, "DFIA-LIVE-LOW-005", export_cif=Decimal("0"), debit_cif=Decimal("5000.00"))
        self._make_purchase_trade(self.company, self.buyer, high_item, cif_fc=Decimal("5000.00"))
        self._make_purchase_trade(self.company, self.buyer, low_item, cif_fc=Decimal("5000.00"))

        live_high = LicenseBalanceCalculator.calculate_financial_balance(high)
        live_low = LicenseBalanceCalculator.calculate_financial_balance(low)
        self.assertGreater(live_high, live_low)
        self._stale_cache(high, Decimal("0.00"))
        self._stale_cache(low, Decimal("999999.00"))

        result = get_license_wise_trades(
            {"min_balance": str((live_high + live_low) / 2), "active_only": "false"}
        )
        license_ids = {lic["license_id"] for lic in result["licenses"]}
        self.assertIn(high.id, license_ids)
        self.assertNotIn(low.id, license_ids)

    def test_get_license_wise_trades_balance_sort_uses_live_balance(self):
        high, high_item = self._make_license(self.company, "DFIA-LIVE-HIGH-006", export_cif=Decimal("0"), debit_cif=Decimal("1000.00"))
        low, low_item = self._make_license(self.company, "DFIA-LIVE-LOW-006", export_cif=Decimal("0"), debit_cif=Decimal("5000.00"))
        self._make_purchase_trade(self.company, self.buyer, high_item, cif_fc=Decimal("5000.00"))
        self._make_purchase_trade(self.company, self.buyer, low_item, cif_fc=Decimal("5000.00"))

        live_high = LicenseBalanceCalculator.calculate_financial_balance(high)
        live_low = LicenseBalanceCalculator.calculate_financial_balance(low)
        self.assertGreater(live_high, live_low)
        self._stale_cache(high, Decimal("0.00"))
        self._stale_cache(low, Decimal("999999.00"))

        result = get_license_wise_trades({"ordering": "-balance_value", "active_only": "false"})
        ids_in_order = [lic["license_id"] for lic in result["licenses"] if lic["license_id"] in (high.id, low.id)]
        self.assertEqual(
            ids_in_order, [high.id, low.id],
            "Descending balance_value sort must rank the live-high license first, "
            "even though its cache is stale-low and the other's is stale-high",
        )
