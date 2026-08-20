"""
Regression coverage for BL-LEDGER-02's stale-balance readers in the
`plan_norms` management command.  The command now retains the complete
manifest universe for an auditable preview, then applies the live financial
balance as the hard per-licence planning ceiling.  It must not use the cached
``LicenseBalance.balance_cif`` to manufacture a positive plan.  The previous
``already planned >= 99%`` shortcut was retired: preview always calculates
the revision-safe proposed replacement instead of treating a cached ratio as
authoritative.
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan, SionPlanningRule
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class PlanNormsCommandLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def _e126_norm(self):
        head_norm = HeadSIONNormsModel.objects.create(name="Plan Norms Command Live Balance Test")
        norm = SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E126")
        target = ItemNameModel.objects.create(name="Plan Norms Widget", sion_norm_class=norm)
        SionPlanningRule.objects.create(
            sion=norm, name="Widget", import_item=target, strategy="STANDARD",
            priority=1, max_unit_price=Decimal("1.00"), unit="kg", is_active=True,
            expression={"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "widget"},
        )
        return norm

    def _make_license_with_live_balance(self, company, norm, *, export_cif, debit_cif):
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=export_cif, norm_class=norm)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget A",
            quantity=Decimal("1000.000"), available_quantity=Decimal("1000.000"),
            cif_fc=export_cif,
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

        # Both manifest rows are reported, but only the licence whose live
        # balance is $4,000 can produce a planning line.  The other cache is
        # deliberately positive ($5,000) while its actual balance is zero.
        self.assertIn("Total Licenses       : 2", output)
        self.assertIn("Successfully Planned : 1", output)
        self.assertIn("Skipped             : 1", output)
        self.assertEqual(LicenseItemPlan.objects.count(), 0)  # dry-run is read-only

    def test_already_planned_threshold_uses_live_balance_not_stale_cache(self):
        company = self.make_company()
        norm = self._e126_norm()

        license_obj, item = self._make_license_with_live_balance(
            company, norm, export_cif=Decimal("1000.00"), debit_cif=Decimal("0.00"),
        )
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(license_obj), Decimal("1000.00"),
        )
        # Cache stale at 100000.  A preview must calculate the current live
        # $1,000 proposal, rather than accepting/rejecting a replacement from
        # a ratio against this denormalized cache.
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
        self.assertIn("Total Licenses       : 1", output)
        self.assertIn("Successfully Planned : 1", output)
        self.assertIn("Already Planned      : 0", output)
        existing = LicenseItemPlan.objects.get()
        self.assertEqual(existing.planned_cif_fc, Decimal("990.00"))
