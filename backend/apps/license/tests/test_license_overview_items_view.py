"""
View-level tests for `GET .../overview-items/`
(`apps/license/services/license_overview_items.py` /
`apps/license/views/license_overview.py`).

Mirrors the fixture style of `test_balance_ledger_views.py`'s
`LicenseBalanceLedgerFixtureMixin`.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseImportItemsModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseOverviewItemsViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def test_balance_formula_total_minus_debited_minus_allotted(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Widget A",
            quantity=Decimal("1000.000"),
            cif_fc=Decimal("5000.00"),
            debited_quantity=Decimal("100.000"),
            debited_value=Decimal("500.00"),
            allotted_quantity=Decimal("50.000"),
            allotted_value=Decimal("250.00"),
            available_quantity=Decimal("850.000"),
        )

        with self.assertNumQueries(4):
            resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-items/")

        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], item.id)
        self.assertEqual(row["description"], "Widget A")
        self.assertEqual(row["total_qty"], 1000.0)
        self.assertEqual(row["total_cif"], 5000.0)
        self.assertEqual(row["debited_qty"], 100.0)
        self.assertEqual(row["debited_cif"], 500.0)
        self.assertEqual(row["allotted_qty"], 50.0)
        self.assertEqual(row["allotted_cif"], 250.0)
        self.assertEqual(row["balance_qty"], 850.0)
        self.assertEqual(row["balance_cif"], 4250.0)

    def test_zero_cif_item_keeps_quantity_balance_at_zero(self):
        """
        Spec case: `item.cif_fc == Decimal('0.00')` (unset) — `balance_cif`
        must come out as `0 - debited - allotted` (here: a negative
        number), never blank/None. The quantity balance stays at the live
        zero-floor used by allocation. Deliberately distinct from
        `apps/core/scripts/calculate_balance.py`'s license-level
        `available_value` — the two are allowed to differ.
        """
        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Zero CIF Item",
            quantity=Decimal("100.000"),
            cif_fc=Decimal("0.00"),
            debited_quantity=Decimal("10.000"),
            debited_value=Decimal("300.00"),
            allotted_quantity=Decimal("0.000"),
            allotted_value=Decimal("0.00"),
        )

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-items/")

        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data[0]
        self.assertIsNotNone(row["balance_cif"])
        self.assertEqual(row["balance_cif"], -300.0)
        self.assertEqual(row["total_cif"], 0.0)
        self.assertEqual(row["balance_qty"], 0.0)

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/overview-items/")

        self.assertEqual(resp.status_code, 403)
