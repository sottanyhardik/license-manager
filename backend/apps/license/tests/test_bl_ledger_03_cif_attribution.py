"""BL-LEDGER-03: import-credit CIF attribution is per item, not per licence."""
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.models import LicenseExportItemModel
from apps.license.services.balance_calculator import (
    ItemBalanceCalculator,
    LicenseBalanceCalculator,
)
from apps.license.services.condition_pool import available_value_bulk_map
from apps.license.services.plan_grouping import plan_group_key
from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class Ledger03CifAttributionTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """Exercise the central property and its batched equivalent together."""

    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("30000.00"))
        self.a = self.make_item(self.license, 1)
        self.b = self.make_item(self.license, 2)
        self.c = self.make_item(self.license, 3)
        self.a.description = self.b.description = "Sibling product"
        self.c.description = "Unrelated product"
        for item, cif in ((self.a, "10000.00"), (self.b, "5000.00"), (self.c, "8000.00")):
            item.cif_fc = Decimal(cif)
            item.cif_inr = Decimal(cif) * Decimal("84.5")
            item.save()
        self.allotment = AllotmentModel.objects.create(company=self.company, item_name="BL-LEDGER-03 CIF")

    def _allot(self, item, cif, qty="10"):
        return AllotmentItems.objects.create(
            allotment=self.allotment,
            item=item,
            qty=Decimal(qty),
            cif_fc=Decimal(cif),
            cif_inr=Decimal(cif) * Decimal("84.5"),
        )

    def test_positive_item_cif_is_item_scoped_for_siblings_and_unrelated_items(self):
        self.assertEqual(plan_group_key(self.a), plan_group_key(self.b))
        self.assertNotEqual(plan_group_key(self.a), plan_group_key(self.c))
        self._allot(self.b, "2000.00")

        self.assertEqual(self.a.available_value_calculated, Decimal("10000.00"))
        self.assertEqual(self.b.available_value_calculated, Decimal("3000.00"))
        self.assertEqual(self.c.available_value_calculated, Decimal("8000.00"))
        # Quantity is independently item-scoped and unchanged by the CIF rule.
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.a), Decimal("1000.000"))
        self.assertEqual(ItemBalanceCalculator.calculate_available_quantity(self.b), Decimal("990.000"))

    def test_mixed_zero_item_uses_live_fallback_without_changing_positive_items(self):
        self.c.cif_fc = Decimal("0.00")
        self.c.cif_inr = Decimal("0.00")
        self.c.save()
        self._allot(self.b, "2000.00")

        self.assertEqual(self.a.available_value_calculated, Decimal("10000.00"))
        self.assertEqual(self.b.available_value_calculated, Decimal("3000.00"))
        self.assertEqual(
            self.c.available_value_calculated,
            LicenseBalanceCalculator.calculate_financial_balance(self.license),
        )

    def test_single_positive_item_remains_attributed_and_all_zero_items_fall_back_live(self):
        self.b.cif_fc = self.b.cif_inr = Decimal("0.00")
        self.b.save()
        self.c.cif_fc = self.c.cif_inr = Decimal("0.00")
        self.c.save()
        self._allot(self.a, "1000.00")

        self.assertEqual(self.a.available_value_calculated, Decimal("9000.00"))
        self.assertEqual(
            self.b.available_value_calculated,
            LicenseBalanceCalculator.calculate_financial_balance(self.license),
        )
        self.assertEqual(
            self.c.available_value_calculated,
            LicenseBalanceCalculator.calculate_financial_balance(self.license),
        )

    def test_all_zero_items_retain_live_license_financial_ledger_fallback(self):
        for item in (self.a, self.b, self.c):
            item.cif_fc = item.cif_inr = Decimal("0.00")
            item.save()
        self._allot(self.b, "2000.00")
        live = LicenseBalanceCalculator.calculate_financial_balance(self.license)
        self.assertEqual(live, Decimal("28000.00"))
        self.assertEqual(self.a.available_value_calculated, live)
        self.assertEqual(self.b.available_value_calculated, live)
        self.assertEqual(self.c.available_value_calculated, live)

    def test_percent_pool_remains_separate_while_au_and_open_use_attributed_cif(self):
        self.a.condition_type = "10%"
        self.a.save()
        self.b.condition_type = "AU"
        self.b.save()
        self._allot(self.b, "2000.00")

        # % is still its export-CIF pool (3000), not the item's 10000 CIF.
        self.assertEqual(self.a.available_value_calculated, Decimal("3000.00"))
        self.assertEqual(self.b.available_value_calculated, Decimal("3000.00"))
        self.assertEqual(self.c.available_value_calculated, Decimal("8000.00"))

    def test_bulk_map_matches_property_and_stays_flat_for_item_count(self):
        self._allot(self.b, "2000.00")
        with CaptureQueriesContext(connection) as one_item_queries:
            one = available_value_bulk_map([self.a])
        with CaptureQueriesContext(connection) as three_item_queries:
            many = available_value_bulk_map([self.a, self.b, self.c])

        self.assertEqual(one[self.a.id], self.a.available_value_calculated)
        self.assertEqual(many[self.a.id], self.a.available_value_calculated)
        self.assertEqual(many[self.b.id], self.b.available_value_calculated)
        self.assertEqual(many[self.c.id], self.c.available_value_calculated)
        self.assertEqual(len(three_item_queries), len(one_item_queries))
