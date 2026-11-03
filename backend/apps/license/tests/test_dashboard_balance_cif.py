"""
Regression coverage: the Dashboard's expiring-licence drill-down and expiry
count must use the same live financial balance the Balance Engine shows, not
the denormalized `LicenseBalance.balance_cif` cache — see
`apps.license.services.dashboard_summary._licence_snapshot`.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseBalance, LicenseDetailsModel, LicenseExportItemModel
from apps.license.services import dashboard_summary as summary
from apps.license.services.balance_calculator import LicenseBalanceCalculator

from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


def _scope():
    return summary.DashboardScope(as_of=date.today())


def _expiring_rows():
    return summary._licence_snapshot(_scope())["expiring_licences"]


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
        # usable-balance threshold so this isolates the DISPLAY discrepancy.
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=Decimal("500.00"))

        row = next(r for r in _expiring_rows() if r["license_number"] == license_obj.license_number)

        self.assertEqual(row["balance_cif"], summary.money(live_balance))
        self.assertNotEqual(row["balance_cif"], "500.00")

    def test_expiring_licenses_filter_uses_live_balance_not_stale_cache(self):
        """BL-LEDGER-02: the usable-balance filter must be decided by the live figure."""
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

        numbers = {r["license_number"] for r in _expiring_rows()}
        self.assertIn(included.license_number, numbers, "Live balance >= 100 must be included")
        self.assertNotIn(excluded.license_number, numbers, "Live balance 0 must be excluded")

    def test_expiring_count_uses_live_balance_not_stale_cache(self):
        """The expiring-usable count is decided by the live balance, like the drill-down."""
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

        portfolio = summary._licence_snapshot(_scope())["portfolio"]
        # Only `counted` (live balance >= 100) should add to the baseline;
        # `not_counted` (live balance 0) must not, regardless of its stale cache.
        self.assertEqual(portfolio["expiring_usable_30d"], before_count + 1)


class DashboardQueryRegressionTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """Query budgets for the dashboard's read paths. Each budget is independent of the row count."""

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

        components = {
            license_obj.id: {
                "credit": Decimal("100.00"), "opening": Decimal("100.00"), "purchase": Decimal("0"),
                "sale": Decimal("0"), "boe": Decimal("0"), "allotment": Decimal("0"),
                "raw": Decimal("100.00"), "available": Decimal("100.00"),
            }
            for license_obj in licenses
        }
        with patch.object(
            LicenseBalanceCalculator,
            "calculate_financial_components_for_licenses",
            return_value=components,
        ):
            # Licence rows (1) + the expiring licences (1) + their prefetched export/norm rows (1).
            # The norms must not add a query per displayed licence.
            with self.assertNumQueries(3):
                rows = summary._licence_snapshot(_scope())["expiring_licences"]

        self.assertEqual([row["license_number"] for row in rows], [
            license_obj.license_number for license_obj in licenses
        ])
        self.assertTrue(all(row["sion_norms"] == ["DASHQ"] for row in rows))

    def test_monthly_trend_uses_one_grouped_database_query(self):
        company = self.make_company()
        self.make_boe(company, number="DASHBOARD-TREND-ONE")
        self.make_boe(company, number="DASHBOARD-TREND-TWO")

        with CaptureQueriesContext(connection) as queries:
            trend = summary.build_boe_activity(summary.DashboardScope(as_of=date.today(), company=company))[
                "monthly_trend"
            ]

        grouped = [q["sql"] for q in queries.captured_queries if "date_trunc" in q["sql"].lower()]
        self.assertEqual(len(grouped), 1, "monthly trend must be a single grouped query")
        self.assertEqual(len(trend), 6)
        self.assertEqual(sum(row["count"] for row in trend), 2)
