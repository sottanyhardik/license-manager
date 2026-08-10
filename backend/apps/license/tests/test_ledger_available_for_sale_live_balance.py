"""
Regression coverage for BL-LEDGER-02's stale-balance reader in
`LicenseLedgerViewSet.available_for_sale` (`GET /api/license-ledger/
available_for_sale/`): the `min_balance` filter used to read the cached
`balance__balance_cif` column directly. Now resolves against the LIVE,
batched-computed balance instead (same fix as `ledger_service.py`'s five
sibling `min_balance` filters).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

AVAILABLE_FOR_SALE_URL = "/api/license-ledger/available_for_sale/"


class AvailableForSaleLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

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
        return license_obj

    def _stale_cache(self, license_obj, fake_balance_cif):
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=fake_balance_cif)
        license_obj.refresh_from_db()

    def test_min_balance_filter_uses_live_balance_not_stale_cache(self):
        company = self.make_company()

        included = self._make_license(company, "DFIA-AFS-HIGH-001", export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"))
        excluded = self._make_license(company, "DFIA-AFS-LOW-001", export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"))

        live_included = LicenseBalanceCalculator.calculate_financial_balance(included)
        live_excluded = LicenseBalanceCalculator.calculate_financial_balance(excluded)
        self.assertGreater(live_included, live_excluded)

        # Stale caches deliberately INVERTED relative to the live values.
        self._stale_cache(included, Decimal("0.00"))
        self._stale_cache(excluded, Decimal("999999.00"))

        threshold = (live_included + live_excluded) / 2
        resp = self.client.get(AVAILABLE_FOR_SALE_URL, {"min_balance": str(threshold)})
        self.assertEqual(resp.status_code, 200, resp.data)

        numbers = {lic["license_number"] for lic in resp.data["licenses"]}
        self.assertIn(included.license_number, numbers, "Live balance above threshold must be included")
        self.assertNotIn(excluded.license_number, numbers, "Live balance below threshold must be excluded")
