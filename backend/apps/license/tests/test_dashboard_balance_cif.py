"""
Regression coverage: the Dashboard's "expiring licenses" card must show the
same live Balance CIF the Customs Ledger/Balance Engine show, not the
denormalized `LicenseBalance.balance_cif` cache — see `_get_expiring_licenses`
in `apps/license/views/dashboard.py`.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseBalance, LicenseDetailsModel, LicenseExportItemModel
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

    def test_expiring_licenses_filter_uses_live_balance_not_stale_cache(self):
        """BL-LEDGER-02: `_get_expiring_licenses` used to filter
        `balance__balance_cif__gte=100` at the DB level (a cached column)
        before ever computing the live balance for display. A license
        whose live balance is >= $100 but whose cache is stale below $100
        would be wrongly excluded entirely; one whose live balance is
        below $100 but whose cache is stale above would be wrongly
        included. Both must now be decided by the live figure."""
        company = self.make_company()

        included = self.make_license(company)
        included.license_expiry_date = date.today() + timedelta(days=10)
        included.save()
        LicenseExportItemModel.objects.create(license=included, cif_fc=Decimal("9000.00"))
        self.make_item(included, 1)
        self.assertEqual(LicenseBalanceCalculator.calculate_balance(included), Decimal("9000.00"))
        LicenseBalance.objects.filter(license=included).update(balance_cif=Decimal("0.00"))

        excluded = self.make_license(company)
        excluded.license_expiry_date = date.today() + timedelta(days=11)
        excluded.save()
        boe = self.make_boe(company)
        LicenseExportItemModel.objects.create(license=excluded, cif_fc=Decimal("9000.00"))
        item = self.make_item(excluded, 1)
        self.make_debit_row(boe, item, cif_fc=Decimal("9000.00"))
        self.assertEqual(LicenseBalanceCalculator.calculate_balance(excluded), Decimal("0.00"))
        LicenseBalance.objects.filter(license=excluded).update(balance_cif=Decimal("9000.00"))

        results = DashboardDataView()._get_expiring_licenses()
        numbers = {r["license_number"] for r in results}
        self.assertIn(included.license_number, numbers, "Live balance >= 100 must be included")
        self.assertNotIn(excluded.license_number, numbers, "Live balance 0 must be excluded")

    def test_expiring_count_stat_uses_live_balance_not_stale_cache(self):
        """Same fix, applied to `_get_license_stats`'s `expiring_soon` count."""
        company = self.make_company()

        counted = self.make_license(company)
        counted.license_expiry_date = date.today() + timedelta(days=5)
        counted.save()
        LicenseExportItemModel.objects.create(license=counted, cif_fc=Decimal("9000.00"))
        self.make_item(counted, 1)
        LicenseBalance.objects.filter(license=counted).update(balance_cif=Decimal("0.00"))

        not_counted = self.make_license(company)
        not_counted.license_expiry_date = date.today() + timedelta(days=6)
        not_counted.save()
        boe = self.make_boe(company)
        LicenseExportItemModel.objects.create(license=not_counted, cif_fc=Decimal("9000.00"))
        item = self.make_item(not_counted, 1)
        self.make_debit_row(boe, item, cif_fc=Decimal("9000.00"))
        LicenseBalance.objects.filter(license=not_counted).update(balance_cif=Decimal("9000.00"))

        before_count = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte=date.today(),
            license_expiry_date__lte=date.today() + timedelta(days=30),
            flags__is_active=True,
        ).exclude(pk__in=[counted.pk, not_counted.pk]).count()

        stats = DashboardDataView()._get_license_stats()
        # Only `counted` (live balance >= 100) should add to the baseline;
        # `not_counted` (live balance 0) must not, regardless of its stale cache.
        self.assertEqual(stats["expiring_soon"], before_count + 1)


class DashboardQueryRegressionTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """Query budgets for the dashboard's request-local read paths.

    The financial-balance service has its own documented bulk-query budget;
    these tests isolate the dashboard ORM work so a future related-manager
    call cannot reintroduce an N+1 query for every expiring licence.
    """

    def test_expiring_license_rows_use_the_prefetched_norms(self):
        company = self.make_company()
        head_norm = HeadSIONNormsModel.objects.create(name="Dashboard query budget")
        norm = SionNormClassModel.objects.create(head_norm=head_norm, norm_class="DASHQ")
        licenses = []
        for offset in range(3):
            license_obj = self.make_license(company)
            license_obj.license_expiry_date = date.today() + timedelta(days=offset + 1)
            license_obj.save()
            LicenseExportItemModel.objects.create(license=license_obj, norm_class=norm)
            licenses.append(license_obj)

        balances = {license_obj.id: Decimal("100.00") for license_obj in licenses}
        with patch.object(
            LicenseBalanceCalculator,
            "calculate_financial_balance_for_licenses",
            return_value=balances,
        ):
            # One candidate query plus one targeted export/norm prefetch.
            # Before the regression fix the related-manager filter below
            # executed an additional query for every displayed licence.
            with self.assertNumQueries(2):
                rows = DashboardDataView()._get_expiring_licenses()

        self.assertEqual([row["license_number"] for row in rows], [
            license_obj.license_number for license_obj in licenses
        ])
        self.assertTrue(all(row["sion_norms"] == ["DASHQ"] for row in rows))

    def test_monthly_trend_uses_one_grouped_database_query(self):
        company = self.make_company()
        self.make_boe(company, number="DASHBOARD-TREND-ONE")
        self.make_boe(company, number="DASHBOARD-TREND-TWO")

        with self.assertNumQueries(1):
            trend = DashboardDataView()._get_boe_monthly_trend()

        self.assertEqual(len(trend), 6)
        self.assertEqual(sum(row["count"] for row in trend), 2)
