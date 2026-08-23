"""
Regression coverage for the "Item Summary" Quantity Summary's new Planned
Quantity field (`LicenseImportItemSerializer.get_planned_quantity`).

Reuses `plan_reporting.plan_map_for_import_items` (the Planning module's own
calculation, batched once per licence detail response via `LicenseDetails
Serializer.to_representation`'s `plan_map` context) — never a second
planning calculation, and Planned Quantity must never feed into Available
Quantity (a purely informational column).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel, LicenseItemPlan
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class PlannedQuantitySerializerTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def test_detail_view_exposes_planned_quantity_from_planning_module(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget A",
            quantity=Decimal("1000.000"), available_quantity=Decimal("1000.000"),
        )
        item_name = ItemNameModel.objects.create(name="Widget A Plan Item", is_active=True)
        LicenseItemPlan.objects.create(
            license=license_obj, import_item=item, item_name=item_name,
            planned_quantity=Decimal("250.500"), planned_cif_fc=Decimal("2500.00"),
        )

        resp = self.client.get(f"/api/licenses/{license_obj.id}/")

        self.assertEqual(resp.status_code, 200, resp.data)
        rows = [row for row in resp.data["import_license"] if row["id"] == item.id]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["planned_quantity"], 250.5)

    def test_planned_quantity_defaults_to_zero_when_no_plan_exists(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Unplanned Item",
            quantity=Decimal("500.000"), available_quantity=Decimal("500.000"),
        )

        resp = self.client.get(f"/api/licenses/{license_obj.id}/")

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["import_license"][0]["planned_quantity"], 0.0)

    def test_planned_quantity_never_reduces_available_quantity(self):
        """A large Planned Quantity must have zero effect on Available
        Quantity — Planning is informational only."""
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget B",
            quantity=Decimal("1000.000"), available_quantity=Decimal("1000.000"),
        )
        item_name = ItemNameModel.objects.create(name="Widget B Plan Item", is_active=True)
        LicenseItemPlan.objects.create(
            license=license_obj, import_item=item, item_name=item_name,
            planned_quantity=Decimal("999.000"), planned_cif_fc=Decimal("9990.00"),
        )

        resp = self.client.get(f"/api/licenses/{license_obj.id}/")

        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data["import_license"][0]
        self.assertEqual(row["planned_quantity"], 999.0)
        self.assertEqual(row["available_quantity"], 1000.0)  # unaffected by the plan

    def test_list_view_does_not_expose_import_items_or_query_plan_map(self):
        """List responses drop `import_license` entirely (existing, unrelated
        optimization) — Planned Quantity must not change that."""
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Widget C",
            quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        )

        resp = self.client.get("/api/licenses/")

        self.assertEqual(resp.status_code, 200, resp.data)
        matching = [lic for lic in resp.data["results"] if lic["id"] == license_obj.id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["import_license"], [])
