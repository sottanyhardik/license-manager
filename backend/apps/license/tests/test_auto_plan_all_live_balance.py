"""
Regression coverage for BL-LEDGER-02's stale-balance reader in
`LicenseItemPlanViewSet.auto_plan_all` (`POST /api/license-item-plans/auto-plan-all/`):
eligibility used to be filtered at the DB level against the cached
`balance__balance_cif` column (`balance__balance_cif__gt=0`), and the
"already planned >= 99%" check read `lic.balance_cif` (same cached column)
inside the loop. Both now resolve against the LIVE, batched-computed
balance instead.

These tests don't exercise a full E1/E5/E126/E132 auto-plan computation
(that requires real SION norm/HS-code setup, covered elsewhere) — they
isolate exactly the changed eligibility logic by using licenses with no
recognizable norm class, so both land in `skipped_unknown_norm` (proving
they were considered eligible enough to reach the norm check) rather than
being silently dropped before that check ever runs.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

AUTO_PLAN_ALL_URL = "/api/license-item-plans/auto-plan-all/"


class AutoPlanAllLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def _make_license_with_live_balance(self, company, *, export_cif, debit_cif):
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

    def test_eligibility_uses_live_balance_not_stale_cache(self):
        company = self.make_company()

        # Live balance = 4000 (eligible), cache stale at 0 (old DB filter
        # `balance__balance_cif__gt=0` would have silently excluded this
        # license before it ever reached the norm check).
        eligible_live = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("1000.00"),
        )
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(eligible_live), Decimal("4000.00"),
        )
        self._stale_cache(eligible_live, Decimal("0.00"))

        # Live balance = 0 (not eligible), cache stale at 5000 (old DB
        # filter would have wrongly included this license).
        not_eligible_live = self._make_license_with_live_balance(
            company, export_cif=Decimal("5000.00"), debit_cif=Decimal("5000.00"),
        )
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(not_eligible_live), Decimal("0.00"),
        )
        self._stale_cache(not_eligible_live, Decimal("5000.00"))

        resp = self.client.post(AUTO_PLAN_ALL_URL, {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)

        # Neither license has a recognizable SION norm class, so an
        # eligible-by-live-balance license lands in `skipped_unknown_norm`
        # (it WAS considered) while an ineligible one contributes nothing
        # at all (it was never considered).
        self.assertEqual(
            resp.data["skipped_unknown_norm"], 1,
            "Exactly the live-balance-positive license should reach the norm check "
            "(via live balance), not the stale-cache-positive one",
        )
        self.assertEqual(resp.data["total"], 0)

    def test_already_planned_threshold_uses_live_balance_not_stale_cache(self):
        from apps.core.models import HeadSIONNormsModel, SionNormClassModel
        from apps.license.models import LicenseItemPlan

        company = self.make_company()
        license_obj = self.make_license(company)

        # Give the license a recognizable E126 norm so detect_norm() takes
        # it past the norm check and into the already-planned comparison
        # (compute_e126_auto_plan is never invoked in this test: the
        # already-planned branch `continue`s before that call happens).
        head_norm = HeadSIONNormsModel.objects.create(name="Auto-Plan-All Live Balance Test Norms")
        norm = SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E126")
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("1000.00"), norm_class=norm)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget A",
            quantity=Decimal("1000.000"), cif_fc=Decimal("1000.00"),
        )

        # Live balance = 1000, cache stale at 100000. If the "already
        # planned >= 99%" check still read the cached column, a plan of
        # 990 would look nowhere near 99% of 100000 and never trigger
        # already_planned; against the live balance of 1000, 990 IS >= 99%.
        self.assertEqual(
            LicenseBalanceCalculator.calculate_financial_balance(license_obj), Decimal("1000.00"),
        )
        self._stale_cache(license_obj, Decimal("100000.00"))

        LicenseItemPlan.objects.create(
            license=license_obj,
            import_item=item,
            planned_quantity=Decimal("100.000"),
            unit_price=Decimal("9.90"),
            planned_cif_fc=Decimal("990.00"),
        )

        resp = self.client.post(AUTO_PLAN_ALL_URL, {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["skipped_unknown_norm"], 0)
        self.assertEqual(resp.data["total"], 1)
        self.assertEqual(
            resp.data["already_planned"], 1,
            "990 is >= 99% of the LIVE balance (1000), not the stale cached column (100000)",
        )
        self.assertEqual(resp.data["planned"], 0)
        self.assertEqual(resp.data["failed"], 0)
