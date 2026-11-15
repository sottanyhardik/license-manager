"""OD-01 consumer regression tests (from the cif-balance-auditor BLOCK review).

* The licence API (list + detail) returns the SIGNED Available CIF (B1).
* Item-level available value stays non-negative and single == bulk (B2,
  item-level semantics pending OD-13).
* Item pivot licence rows use the canonical financial balance (OD-02, M1).
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseDetailsModel, LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.condition_pool import available_value_bulk_map
from apps.license.services.item_pivot_service import ItemPivotService
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

EXPECTED = Decimal("-5000.00")  # 10,000 original - 15,000 BOE


class Od01ConsumerTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        company = self.make_company()
        self.licence = self.make_license(company)
        LicenseExportItemModel.objects.create(license=self.licence, cif_fc=Decimal("10000.00"))
        # cif_fc = 0 on the import item -> item available value falls back to the licence balance
        self.item = self.make_item(self.licence, 1)
        self.make_debit_row(self.make_boe(company), self.item, cif_fc=Decimal("15000.00"))
        self.client = APIClient()
        self.client.force_authenticate(self.make_superuser())

    def test_engine_is_negative(self):
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(self.licence), EXPECTED)

    def test_licence_detail_api_returns_signed_balance(self):
        response = self.client.get(f"/api/licenses/{self.licence.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(str(response.data["balance_cif"])), EXPECTED)
        self.assertEqual(Decimal(str(response.data["get_balance_cif"])), EXPECTED)

    def test_licence_list_api_returns_signed_balance(self):
        response = self.client.get("/api/licenses/", {"search": self.licence.license_number})
        self.assertEqual(response.status_code, 200)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        row = next(r for r in rows if r["id"] == self.licence.id)
        self.assertEqual(Decimal(str(row["get_balance_cif"])), EXPECTED)
        self.assertEqual(Decimal(str(row["balance_cif"])), EXPECTED)

    def test_item_available_value_non_negative_and_single_equals_bulk(self):
        item = type(self.item).objects.get(pk=self.item.pk)
        single = Decimal(str(item.available_value_calculated))
        bulk = Decimal(str(available_value_bulk_map([item])[item.id]))
        self.assertEqual(single, Decimal("0"))
        self.assertEqual(single, bulk)

    def test_item_pivot_licence_row_uses_canonical_signed_balance(self):
        licence = LicenseDetailsModel.objects.get(pk=self.licence.pk)
        result = ItemPivotService.build([licence])
        rows = [row for group in result["groups"] for row in group["licenses"]]
        row = next(r for r in rows if r["license_id"] == licence.id)
        self.assertEqual(Decimal(str(row["balance_cif"])), EXPECTED)
