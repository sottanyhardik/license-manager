"""GET /api/license-item-plans/ must not issue per-row queries (N+1 guard)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.balance_calculator import LicenseBalanceCalculator


class LicenseItemPlanListQueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="ip_admin", password="x", email="ip@example.com")
        company = CompanyModel.objects.create(iec="0123456781", name="Plan QC Co")
        cls.license = LicenseDetailsModel.objects.create(
            license_number="0311111111", license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=365), exporter=company,
        )
        LicenseExportItemModel.objects.create(license=cls.license, cif_fc=Decimal("1000.00"))
        cls.name = ItemNameModel.objects.create(name="Plan QC Item")

    def _add_lines(self, n):
        start = LicenseImportItemsModel.objects.filter(license=self.license).count()
        for i in range(n):
            item = LicenseImportItemsModel.objects.create(
                license=self.license, serial_number=start + i + 1, description=f"I{start + i}",
                quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
            )
            LicenseItemPlan.objects.create(
                license=self.license, import_item=item, item_name=self.name,
                planned_quantity=Decimal("10"), planned_cif_fc=Decimal("50"), modified_by=self.user,
            )

    def _get(self):
        client = APIClient()
        client.force_authenticate(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/api/license-item-plans/?page_size=50")
        self.assertEqual(resp.status_code, 200)
        return resp.json()["results"], len(ctx)

    def test_query_count_constant_in_rows(self):
        self._add_lines(2)
        rows_small, small = self._get()
        self._add_lines(8)
        rows_large, large = self._get()
        self.assertEqual((len(rows_small), len(rows_large)), (2, 10))
        self.assertLessEqual(large, small + 2, f"N+1 regression: {small} -> {large}")

    def test_balance_uses_canonical_batch_value(self):
        self._add_lines(2)
        rows, _ = self._get()
        expected = LicenseBalanceCalculator.calculate_financial_balance(self.license)
        for row in rows:
            self.assertEqual(row["actual_license_balance_cif"], f"{Decimal(expected):.2f}")
            self.assertEqual(row["modified_by_username"], "ip_admin")
            self.assertFalse(row["needs_rebuild"])
