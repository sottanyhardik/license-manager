"""
Regression coverage for BL-LEDGER-02's remaining stale-balance readers in
`LicenseDetailsViewSet.apply_advanced_filters` (the main `/api/licenses/`
list endpoint): the `is_null` filter and the generic
`balance__balance_cif_min`/`_max` range filter both used to filter directly
against the cached `LicenseBalance.balance_cif` column, which the display
path had already stopped trusting (see `test_license_list_balance_
consistency.py`). A stale cache could put a license in the wrong `is_null`
bucket, or wrongly in/exclude it from a balance-range filter, even though
the displayed "Balance CIF" for that same license was already correct.

Both filters now resolve against the SAME live, batched
`LicenseBalanceCalculator.calculate_financial_balance_for_licenses` figure
used everywhere else in the app.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseAdvancedFiltersLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def _make_license_with_live_balance(self, company, *, export_cif, debit_cif):
        """Build a license whose live balance is (export_cif - debit_cif), then
        return it. Caller is responsible for staling the cache afterwards."""
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=export_cif)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Widget A",
            quantity=Decimal("1000.000"),
            cif_fc=export_cif,
        )
        if debit_cif:
            boe = self.make_boe(company)
            self.make_debit_row(boe, item, cif_fc=debit_cif, qty=Decimal("100.000"))
        return license_obj

    def _stale_cache(self, license_obj, fake_balance_cif):
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=fake_balance_cif)
        license_obj.refresh_from_db()

    def test_is_null_filter_uses_live_balance_not_stale_cache(self):
        company = self.make_company()

        # Live balance = 4000 (>= 200, "non-null"), but cache stale at 0
        # (would wrongly look "null" under the old cached-column filter).
        non_null_live = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"),
        )
        live_balance = LicenseBalanceCalculator.calculate_financial_balance(non_null_live)
        self.assertEqual(live_balance, Decimal("4000.00"))
        self._stale_cache(non_null_live, Decimal("0.00"))

        # Live balance = 0 (< 200, "null"), but cache stale at 5000 (would
        # wrongly look "non-null" under the old cached-column filter).
        null_live = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"),
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(null_live), Decimal("0.00"))
        self._stale_cache(null_live, Decimal("5000.00"))

        non_null_resp = self.client.get("/api/licenses/", {"is_null": "false", "page_size": 200})
        self.assertEqual(non_null_resp.status_code, 200, non_null_resp.data)
        non_null_ids = {row["id"] for row in non_null_resp.data["results"]}
        self.assertIn(non_null_live.id, non_null_ids, "Live balance >= 200 must be classified non-null")
        self.assertNotIn(null_live.id, non_null_ids, "Live balance < 200 must not be classified non-null")

        null_resp = self.client.get("/api/licenses/", {"is_null": "true", "page_size": 200})
        self.assertEqual(null_resp.status_code, 200, null_resp.data)
        null_ids = {row["id"] for row in null_resp.data["results"]}
        self.assertIn(null_live.id, null_ids, "Live balance < 200 must be classified null")
        self.assertNotIn(non_null_live.id, null_ids, "Live balance >= 200 must not be classified null")

    def test_current_flags_query_names_use_live_expiry_and_balance(self):
        """The frontend sends ``flags__is_*`` names from the filter schema.

        They must not be passed through to a direct child-table lookup, because
        those flags are asynchronously refreshed and can be stale.
        """
        company = self.make_company()
        license_obj = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"),
        )
        license_obj.license_expiry_date = date.today() + timedelta(days=10)
        license_obj.save(update_fields=["license_expiry_date"])
        license_obj.flags.is_expired = True
        license_obj.flags.is_null = True
        license_obj.flags.save(update_fields=["is_expired", "is_null"])

        response = self.client.get("/api/licenses/", {
            "flags__is_expired": "false",
            "flags__is_null": "false",
            "page_size": 200,
        })

        self.assertEqual(response.status_code, 200, response.data)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(license_obj.id, ids)

    def test_balance_range_filter_uses_live_balance_not_stale_cache(self):
        company = self.make_company()

        # Live balance = 4000, cache stale at 0 -- a min_balance=1000 filter
        # must still include it (old code would have excluded it).
        high_live = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"),
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(high_live), Decimal("4000.00"))
        self._stale_cache(high_live, Decimal("0.00"))

        # Live balance = 0, cache stale at 9999 -- a max_balance=1000 filter
        # must still include it, and a min_balance=1000 filter must exclude it
        # (old code would have done the opposite for both).
        low_live = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"),
        )
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(low_live), Decimal("0.00"))
        self._stale_cache(low_live, Decimal("9999.00"))

        min_resp = self.client.get(
            "/api/licenses/", {"balance__balance_cif_min": "1000", "page_size": 200}
        )
        self.assertEqual(min_resp.status_code, 200, min_resp.data)
        min_ids = {row["id"] for row in min_resp.data["results"]}
        self.assertIn(high_live.id, min_ids, "Live balance 4000 >= min 1000 must be included")
        self.assertNotIn(low_live.id, min_ids, "Live balance 0 >= min 1000 must be excluded")

        max_resp = self.client.get(
            "/api/licenses/", {"balance__balance_cif_max": "1000", "page_size": 200}
        )
        self.assertEqual(max_resp.status_code, 200, max_resp.data)
        max_ids = {row["id"] for row in max_resp.data["results"]}
        self.assertIn(low_live.id, max_ids, "Live balance 0 <= max 1000 must be included")
        self.assertNotIn(high_live.id, max_ids, "Live balance 4000 <= max 1000 must be excluded")
