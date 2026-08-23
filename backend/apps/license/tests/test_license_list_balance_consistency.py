"""
Regression coverage for the "License List shows a different Balance CIF
than License Detail/Overview" bug: `LicenseDetailsSerializer` used to serve
the STORED `LicenseBalance.balance_cif` cache column for list responses
(for performance) while every other consumer — detail view, License
Overview, the Financial/Customs Ledger, PDF/Excel exports — computed the
LIVE `LicenseBalanceCalculator.calculate_balance()` value. Whenever the
cache went stale (e.g. no signal fires on `trade.boes` M2M edits, which the
virtual-BOE-match fix in `balance_calculator.py` depends on), the list and
detail/Overview values would diverge for the same license.

Fix: the list view now batch-computes LIVE balances for the current page
via `LicenseBalanceCalculator.calculate_balance_for_licenses` (a fixed
number of queries for the whole page, not one live call per row) and the
serializer uses that instead of the stored column — see
`LicenseDetailsViewSet.paginate_queryset`/`get_serializer_context` and
`LicenseDetailsSerializer.get_get_balance_cif`/`to_representation`.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.license.models import LicenseImportItemsModel
from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class LicenseListBalanceConsistencyTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    def test_list_and_detail_report_the_same_live_balance_even_when_cache_is_stale(self):
        from apps.license.models import LicenseExportItemModel

        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("5000.00"))
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Widget A",
            quantity=Decimal("1000.000"),
            cif_fc=Decimal("5000.00"),
        )
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"), qty=Decimal("100.000"))

        live_balance = LicenseBalanceCalculator.calculate_balance(license_obj)
        self.assertEqual(live_balance, Decimal("4000.00"))

        # Deliberately desynchronize the cache from the live value, exactly
        # as happens in production when a signal doesn't fire for some
        # underlying change (e.g. a `trade.boes` M2M edit).
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=Decimal("0.00"))
        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance.balance_cif, Decimal("0.00"))

        detail_resp = self.client.get(f"/api/licenses/{license_obj.id}/")
        self.assertEqual(detail_resp.status_code, 200, detail_resp.data)
        self.assertEqual(Decimal(str(detail_resp.data["balance_cif"])), live_balance)
        self.assertEqual(Decimal(str(detail_resp.data["get_balance_cif"])), live_balance)

        list_resp = self.client.get("/api/licenses/", {"page_size": 200})
        self.assertEqual(list_resp.status_code, 200, list_resp.data)
        row = next(r for r in list_resp.data["results"] if r["id"] == license_obj.id)
        self.assertEqual(
            Decimal(str(row["balance_cif"])), live_balance,
            "List view must show the SAME live balance as Detail/Overview, not the stale cached column",
        )
        self.assertEqual(Decimal(str(row["get_balance_cif"])), live_balance)
