"""
Regression coverage for BL-LEDGER-02's stale-balance readers in the
`plan_norms` management command (`apps/license/management/commands/
plan_norms.py`): eligibility used to be filtered at the DB level against
the cached `balance__balance_cif` column (`balance__balance_cif__gt=0`),
and `_is_fully_planned`'s "already planned >= 99%" check read
`license_obj.balance_cif` (same cached column) directly. Both now resolve
against the LIVE, batched-computed balance -- the exact same bug pattern
already fixed in `LicenseItemPlanViewSet.auto_plan_all`
(`test_auto_plan_all_live_balance.py`), just reached via a different,
admin-run entry point.
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class PlanNormsCommandLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def _e126_norm(self):
        head_norm = HeadSIONNormsModel.objects.create(name="Plan Norms Command Live Balance Test")
        return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E126")

    def _make_license_with_live_balance(self, company, norm, *, export_cif, debit_cif):
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=export_cif, norm_class=norm)
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

    def test_eligibility_uses_live_balance_not_stale_cache(self):
        company = self.make_company()
        norm = self._e126_norm()

        eligible_live, _ = self._make_license_with_live_balance(
            company, norm, export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"),
        )
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(eligible_live), Decimal("4000.00"),
        )
        self._stale_cache(eligible_live, Decimal("0.00"))

        not_eligible_live, _ = self._make_license_with_live_balance(
            company, norm, export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"),
        )
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(not_eligible_live), Decimal("0.00"),
        )
        self._stale_cache(not_eligible_live, Decimal("5000.00"))

        out = StringIO()
        call_command("plan_norms", "E126", "--dry-run", stdout=out)
        output = out.getvalue()

        self.assertIn("Total Licenses       : 1", output)

    def test_already_planned_threshold_uses_live_balance_not_stale_cache(self):
        company = self.make_company()
        norm = self._e126_norm()

        license_obj, item = self._make_license_with_live_balance(
            company, norm, export_cif=Decimal("1000.00"), debit_cif=Decimal("0.00"),
        )
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(license_obj), Decimal("1000.00"),
        )
        # Cache stale at 100000: if the "already planned >= 99%" check
        # still read the cached column, a plan of 990 would look nowhere
        # near 99% of 100000 and never trigger already-planned; against
        # the live balance of 1000, 990 IS >= 99%.
        self._stale_cache(license_obj, Decimal("100000.00"))

        LicenseItemPlan.objects.create(
            license=license_obj,
            import_item=item,
            planned_quantity=Decimal("100.000"),
            unit_price=Decimal("9.90"),
            planned_cif_fc=Decimal("990.00"),
        )

        out = StringIO()
        call_command("plan_norms", "E126", "--dry-run", stdout=out)
        output = out.getvalue()

        self.assertIn("Total Licenses       : 1", output)
        self.assertIn("Already Planned      : 1", output)
        self.assertIn("Successfully Planned : 0", output)
