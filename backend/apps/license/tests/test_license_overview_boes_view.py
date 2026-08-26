"""
View-level tests for `GET .../overview-boes/`
(`apps/license/services/license_overview_boes.py` /
`apps/license/views/license_overview.py`).

Proves the endpoint is O(1) queries regardless of BOE count by asserting
the SAME query count at 10 and 50 BOEs (licenses can have 1000+ BOEs in
production).
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.bill_of_entry.models import RowDetails
from apps.core.constants import DEBIT
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseOverviewBoesViewTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def _make_n_boes(self, license_obj, company, item, n):
        for i in range(n):
            boe = self.make_boe(company, number=f"BOE{i}-{uuid.uuid4().hex[:6]}", invoice_no=f"INV-{i}")
            self.make_debit_row(boe, item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"))

    def test_returns_boe_rows_with_expected_shape_and_values(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company, number="BOE-1", invoice_no="INV-1")
        self.make_debit_row(boe, item, cif_fc=Decimal("500.00"), qty=Decimal("50.000"))

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-boes/")

        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(set(row.keys()), {
            "bill_of_entry_number", "bill_of_entry_date", "port", "supplier",
            "invoice_no", "invoice_date", "cif_fc", "status",
        })
        self.assertEqual(row["bill_of_entry_number"], "BOE-1")
        self.assertEqual(row["supplier"], company.name)
        self.assertEqual(row["cif_fc"], 500.0)
        self.assertEqual(row["status"], "Pending")
        self.assertNotIn("duty_saved", row)

    def test_orders_boes_by_newest_bill_date_first(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)
        older = self.make_boe(company, number="BOE-OLDER")
        newer = self.make_boe(company, number="BOE-NEWER")
        older.bill_of_entry_date = datetime(2026, 1, 1).date()
        newer.bill_of_entry_date = datetime(2026, 2, 1).date()
        older.save(update_fields=["bill_of_entry_date"])
        newer.save(update_fields=["bill_of_entry_date"])
        self.make_debit_row(older, item, cif_fc=Decimal("100.00"))
        self.make_debit_row(newer, item, cif_fc=Decimal("100.00"))

        response = self.client.get(f"/api/licenses/{license_obj.id}/overview-boes/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [row["bill_of_entry_number"] for row in response.data],
            ["BOE-NEWER", "BOE-OLDER"],
        )

    def test_frozen_and_dispute_flags_drive_status(self):
        company = self.make_company()
        license_obj = self.make_license(company)
        item = self.make_item(license_obj, 1)

        frozen_boe = self.make_boe(company, number="BOE-FROZEN")
        RowDetails.objects.create(
            bill_of_entry=frozen_boe, sr_number=item, transaction_type=DEBIT,
            cif_inr=Decimal("8450.00"), cif_fc=Decimal("100.00"), qty=Decimal("10.000"),
            is_frozen=True,
        )

        dispute_boe = self.make_boe(company, number="BOE-DISPUTE")
        RowDetails.objects.create(
            bill_of_entry=dispute_boe, sr_number=item, transaction_type=DEBIT,
            cif_inr=Decimal("8450.00"), cif_fc=Decimal("100.00"), qty=Decimal("10.000"),
            is_dispute=True,
        )

        resp = self.client.get(f"/api/licenses/{license_obj.id}/overview-boes/")
        self.assertEqual(resp.status_code, 200, resp.data)
        by_number = {r["bill_of_entry_number"]: r for r in resp.data}
        self.assertEqual(by_number["BOE-FROZEN"]["status"], "Frozen")
        self.assertEqual(by_number["BOE-DISPUTE"]["status"], "Dispute")

    def test_query_count_is_constant_regardless_of_boe_count(self):
        company_small = self.make_company()
        license_small = self.make_license(company_small)
        item_small = self.make_item(license_small, 1)
        self._make_n_boes(license_small, company_small, item_small, 10)

        with self.assertNumQueries(4):
            resp_small = self.client.get(f"/api/licenses/{license_small.id}/overview-boes/")
        self.assertEqual(resp_small.status_code, 200, resp_small.data)
        self.assertEqual(len(resp_small.data), 10)

        company_large = self.make_company()
        license_large = self.make_license(company_large)
        item_large = self.make_item(license_large, 1)
        self._make_n_boes(license_large, company_large, item_large, 50)

        with self.assertNumQueries(4):
            resp_large = self.client.get(f"/api/licenses/{license_large.id}/overview-boes/")
        self.assertEqual(resp_large.status_code, 200, resp_large.data)
        self.assertEqual(len(resp_large.data), 50)

    def test_denies_authenticated_user_with_no_roles(self):
        company = self.make_company()
        license_obj = self.make_license(company)

        client = APIClient()
        client.force_authenticate(user=self.make_plain_user())
        resp = client.get(f"/api/licenses/{license_obj.id}/overview-boes/")

        self.assertEqual(resp.status_code, 403)
