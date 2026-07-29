"""
View-level tests for `GET .../overview-allotments/`
(`apps/license/services/license_overview_allotments.py` /
`apps/license/views/license_overview.py`).

Proves the endpoint is O(1) queries regardless of allotment count by
asserting the SAME query count at 10 and 50 allotments.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseOverviewAllotmentsViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def make_allotment(self, company, **kwargs):
        return AllotmentModel.objects.create(company=company, item_name="Test Allotment Item", **kwargs)

    def make_allotment_item(self, allotment, item, cif_fc, qty=Decimal("100.000")):
        return AllotmentItems.objects.create(
            item=item, allotment=allotment, cif_fc=cif_fc, cif_inr=cif_fc * Decimal("84.5"), qty=qty,
        )

    def _make_n_allotments(self, license_obj, company, item, n):
        for i in range(n):
            allotment = self.make_allotment(company)
            self.make_allotment_item(allotment, item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))

    def test_returns_allotment_rows_with_expected_shape_and_values(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        allotment = self.make_allotment(company)
        self.make_allotment_item(allotment, item, cif_fc=Decimal("500.00"), qty=Decimal("50.000"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-allotments/")

        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(set(row.keys()), {
            "allotment_number", "date", "customer", "product", "quantity", "cif_fc", "status",
        })
        self.assertEqual(row["allotment_number"], f"ALT-{allotment.id}")
        self.assertEqual(row["customer"], company.name)
        self.assertEqual(row["product"], "Test Allotment Item")
        self.assertEqual(row["cif_fc"], 500.0)
        self.assertEqual(row["quantity"], 50.0)
        # `is_allotted` auto-flips True via `update_is_allotted_on_save` the
        # moment an AllotmentItems row is attached (a precondition for
        # appearing in this list at all) — see `_allotment_status`'s
        # docstring.
        self.assertEqual(row["status"], "Allotted")

    def test_status_derived_from_boolean_flags(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)

        boe_allotment = self.make_allotment(company, is_boe=True)
        self.make_allotment_item(boe_allotment, item, cif_fc=Decimal("100.00"))

        allotted_allotment = self.make_allotment(company, is_allotted=True)
        self.make_allotment_item(allotted_allotment, item, cif_fc=Decimal("100.00"))

        approved_allotment = self.make_allotment(company, is_approved=True)
        self.make_allotment_item(approved_allotment, item, cif_fc=Decimal("100.00"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-allotments/")
        self.assertEqual(resp.status_code, 200, resp.data)
        by_number = {r["allotment_number"]: r for r in resp.data}
        self.assertEqual(by_number[f"ALT-{boe_allotment.id}"]["status"], "Linked to BOE")
        self.assertEqual(by_number[f"ALT-{allotted_allotment.id}"]["status"], "Allotted")
        self.assertEqual(by_number[f"ALT-{approved_allotment.id}"]["status"], "Approved")

    def test_query_count_is_constant_regardless_of_allotment_count(self):
        company_small = self.make_company()
        license_small = self.make_license(company_small)
        item_small = self.make_item(license_small, 1)
        self._make_n_allotments(license_small, company_small, item_small, 10)

        with self.assertNumQueries(4):
            resp_small = self.client.get(f"/api/licenses/{license_small.id}/overview-allotments/")
        self.assertEqual(resp_small.status_code, 200, resp_small.data)
        self.assertEqual(len(resp_small.data), 10)

        company_large = self.make_company()
        license_large = self.make_license(company_large)
        item_large = self.make_item(license_large, 1)
        self._make_n_allotments(license_large, company_large, item_large, 50)

        with self.assertNumQueries(4):
            resp_large = self.client.get(f"/api/licenses/{license_large.id}/overview-allotments/")
        self.assertEqual(resp_large.status_code, 200, resp_large.data)
        self.assertEqual(len(resp_large.data), 50)

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/overview-allotments/")

        self.assertEqual(resp.status_code, 403)
