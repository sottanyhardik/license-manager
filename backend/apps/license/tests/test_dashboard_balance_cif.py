"""
Regression coverage: the Dashboard's "expiring licenses" card must show the
same live Balance CIF the Customs Ledger/Balance Engine show, not the
denormalized `LicenseBalance.balance_cif` cache — see `_get_expiring_licenses`
in `apps/license/views/dashboard.py`.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.license.models import LicenseBalance, LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.views.dashboard import DashboardDataView

from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class ExpiringLicensesLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def test_shown_balance_is_live_not_the_stale_stored_cache(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        license_obj.license_expiry_date = date.today() + timedelta(days=10)
        license_obj.save()
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("9000.00"))
        self.make_item(license_obj, 1)

        live_balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        self.assertEqual(live_balance, Decimal("9000.00"))

        # Simulate a stale cache — bypass the recalculation signal so the
        # stored column disagrees with the live formula. Kept above the
        # view's own `balance__balance_cif__gte=100` filter threshold so
        # this isolates the DISPLAY discrepancy, not the filter.
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=Decimal("500.00"))

        results = DashboardDataView()._get_expiring_licenses()
        row = next(r for r in results if r["license_number"] == license_obj.license_number)

        self.assertEqual(row["balance_cif"], float(live_balance))
        self.assertNotEqual(row["balance_cif"], 500.00)
