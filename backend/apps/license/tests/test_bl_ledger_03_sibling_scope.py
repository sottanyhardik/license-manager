"""BL-LEDGER-03 fallback scope: zero-CIF rows use licence CIF; plans use groups."""
from decimal import Decimal

from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel, LicenseItemPlan
from apps.license.services.balance_calculator import ItemBalanceCalculator
from apps.license.services.plan_enforcement import plan_status_for
from apps.license.services.plan_grouping import plan_group_key
from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class Ledger03SiblingScopeTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("10000.00"))
        self.a = self.make_item(self.license, 1); self.a.description = "Same product"; self.a.quantity = Decimal("100"); self.a.save()
        self.b = self.make_item(self.license, 2); self.b.description = "Same product"; self.b.quantity = Decimal("100"); self.b.save()
        self.c = self.make_item(self.license, 3); self.c.description = "Other product"; self.c.quantity = Decimal("100"); self.c.save()
        self.allotment = AllotmentModel.objects.create(company=self.company, item_name="BL-LEDGER-03")

    def _allot(self, item, qty, cif):
        return AllotmentItems.objects.create(allotment=self.allotment, item=item, qty=Decimal(qty), cif_fc=Decimal(cif), cif_inr=Decimal(cif))

    def test_zero_cif_sibling_quantity_is_item_scoped_but_cif_uses_license_fallback(self):
        self.assertEqual(plan_group_key(self.a), plan_group_key(self.b))
        self.assertNotEqual(plan_group_key(self.a), plan_group_key(self.c))
        # The fixture intentionally leaves import-item CIF at zero, proving
        # the live licence-level fallback only; positive-CIF attribution is
        # covered separately in test_bl_ledger_03_cif_attribution.py.
        before = self.a.available_value_calculated
        self._allot(self.b, "30", "3000")
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.a), Decimal("100"))
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.b), Decimal("70"))
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.c), Decimal("100"))
        self.assertEqual(self.a.available_value_calculated, before - Decimal("3000.00"))

    def test_plan_group_consumes_sibling_quantity_and_cif(self):
        LicenseItemPlan.objects.create(license=self.license, import_item=self.a, planned_quantity=Decimal("100"), planned_cif_fc=Decimal("10000"), baseline_used_quantity=Decimal("0"), baseline_used_cif_fc=Decimal("0"))
        self._allot(self.b, "30", "3000")
        status = plan_status_for(self.a)
        self.assertEqual(status["remaining_quantity"], Decimal("70"))
        self.assertEqual(status["remaining_cif_fc"], Decimal("7000"))
