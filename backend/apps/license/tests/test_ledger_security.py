"""Authorization regression tests for the public License Ledger contract.

The ledger API was consolidated onto ``license-wise``, ``summary``,
``ledger-detail`` and ``export``. These tests deliberately exercise those
routes with real trades and trade lines: ledger visibility is based on a
user's company participating in a trade, rather than on the licence exporter.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.accounts.models import User
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.trade.models import LicenseTrade, LicenseTradeLine


class LicenseLedgerSecurityTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.company_a = self._company("Company A", "COMP_A")
        self.company_b = self._company("Company B", "COMP_B")
        self.supplier = self._company("Supplier", "SUPPLIER")
        self.user_a = self._user("user_a", self.company_a)
        self.user_without_company = self._user("no_company", None)
        self.user_without_role = User.objects.create_user(
            username="no_role", password="testpass123", company=self.company_a,
        )
        self.superuser = User.objects.create_superuser(
            username="ledger_superuser", password="testpass123",
        )
        self.license_a = self._licensed_trade("LEDGER-A", self.company_a, "100.00")
        self.license_b = self._licensed_trade("LEDGER-B", self.company_b, "200.00")

    @staticmethod
    def _company(name, iec):
        return CompanyModel.objects.create(
            name=name, iec=iec, pan=f"PAN-{iec}", gst_number=f"GST-{iec}",
        )

    @staticmethod
    def _user(username, company):
        user = User.objects.create_user(username=username, password="testpass123", company=company)
        role, _ = Group.objects.get_or_create(name="TRADE_VIEWER")
        user.groups.add(role)
        return user

    def _licensed_trade(self, number, buyer, amount):
        licence = LicenseDetailsModel.objects.create(
            exporter=self.supplier,
            license_number=number,
            license_date=date(2025, 1, 1),
            license_expiry_date=date(2026, 1, 1),
        )
        item = LicenseImportItemsModel.objects.create(
            license=licence, serial_number=1, description=f"Item {number}",
            quantity=Decimal("10.000"), available_quantity=Decimal("10.000"),
        )
        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE,
            license_type=LicenseTrade.LICENSE_TYPE_DFIA,
            from_company=self.supplier,
            to_company=buyer,
            invoice_number=f"PUR-{number}",
            invoice_date=date(2025, 2, 1),
        )
        LicenseTradeLine.objects.create(
            trade=trade, sr_number=item, mode=LicenseTradeLine.MODE_QTY,
            qty_kg=Decimal("1.0000"), rate_inr_per_kg=Decimal(amount),
        )
        return licence

    def _get_as(self, user, url):
        self.client.force_authenticate(user=user)
        return self.client.get(url)

    def test_collection_is_scoped_to_callers_trade_company(self):
        response = self._get_as(self.user_a, "/api/license-ledger/")
        assert response.status_code == status.HTTP_200_OK
        assert [row["license_id"] for row in response.data["licenses"]] == [self.license_a.id]

        response = self._get_as(self.user_a, "/api/license-ledger/license-wise/")
        assert response.status_code == status.HTTP_200_OK
        assert [row["license_id"] for row in response.data["licenses"]] == [self.license_a.id]

    def test_summary_is_scoped_to_callers_trade_company(self):
        response = self._get_as(self.user_a, "/api/license-ledger/summary/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["dfia"]["total_licenses"] == 1
        assert response.data["incentive"]["total_licenses"] == 0

    def test_detail_denies_foreign_licence_and_allows_linked_licence(self):
        foreign = self._get_as(self.user_a, f"/api/license-ledger/{self.license_b.id}/ledger_detail/")
        assert foreign.status_code == status.HTTP_403_FORBIDDEN

        own = self._get_as(self.user_a, f"/api/license-ledger/{self.license_a.id}/ledger_detail/")
        assert own.status_code == status.HTTP_200_OK
        assert own.data["license_id"] == self.license_a.id

    def test_export_rechecks_direct_licence_authorization(self):
        foreign = self._get_as(
            self.user_a,
            f"/api/license-ledger/export/?file_format=xlsx&license_id={self.license_b.id}",
        )
        assert foreign.status_code == status.HTTP_403_FORBIDDEN

        own = self._get_as(
            self.user_a,
            f"/api/license-ledger/export/?file_format=xlsx&license_id={self.license_a.id}",
        )
        assert own.status_code == status.HTTP_200_OK

    def test_company_filter_cannot_expand_non_superuser_scope(self):
        foreign = self._get_as(
            self.user_a, f"/api/license-ledger/?buying_company_id={self.company_b.id}",
        )
        assert foreign.status_code == status.HTTP_403_FORBIDDEN
        invalid = self._get_as(self.user_a, "/api/license-ledger/?buying_company_id=not-an-id")
        assert invalid.status_code == status.HTTP_400_BAD_REQUEST

    def test_superuser_can_view_all_trade_linked_licences(self):
        response = self._get_as(self.superuser, "/api/license-ledger/")
        assert response.status_code == status.HTTP_200_OK
        assert {row["license_id"] for row in response.data["licenses"]} == {
            self.license_a.id, self.license_b.id,
        }

    def test_authentication_role_and_company_assignment_are_required(self):
        response = self.client.get("/api/license-ledger/")
        assert response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}
        assert self._get_as(self.user_without_role, "/api/license-ledger/").status_code == status.HTTP_403_FORBIDDEN
        assert self._get_as(self.user_without_company, "/api/license-ledger/").status_code == status.HTTP_403_FORBIDDEN

    def test_retired_legacy_routes_are_not_silently_reintroduced(self):
        response = self._get_as(self.user_a, "/api/license-ledger/company-ledger/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
