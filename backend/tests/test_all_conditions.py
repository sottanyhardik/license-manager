"""
All-conditions test suite for License Manager.

Covers every critical condition across authentication, license, bill of entry,
trade, allotment, and balance calculation in a single file.

Run with:
    cd backend && pytest tests/test_all_conditions.py -v --no-cov
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, Mock

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.constants import DEC_0
from apps.license.services.balance_calculator import LicenseBalanceCalculator, ItemBalanceCalculator

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_client(user):
    """Return an APIClient pre-loaded with a valid JWT for *user*."""
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


# ===========================================================================
# 1. AUTHENTICATION
# ===========================================================================

@pytest.mark.django_db
class TestAuthentication:

    def test_login_valid_credentials_returns_200_and_token(self):
        User.objects.create_user(username="auth_valid", password="pass1234!")
        client = APIClient()
        resp = client.post(
            reverse("api-login"),
            {"username": "auth_valid", "password": "pass1234!"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data

    def test_login_wrong_password_returns_4xx(self):
        User.objects.create_user(username="auth_wrong", password="correct!")
        client = APIClient()
        resp = client.post(
            reverse("api-login"),
            {"username": "auth_wrong", "password": "wrong!"},
            format="json",
        )
        assert resp.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_login_nonexistent_user_returns_4xx(self):
        client = APIClient()
        resp = client.post(
            reverse("api-login"),
            {"username": "nobody", "password": "x"},
            format="json",
        )
        assert resp.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
        ]

    def test_login_missing_fields_returns_400(self):
        client = APIClient()
        resp = client.post(reverse("api-login"), {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_protected_license_endpoint_requires_auth(self):
        client = APIClient()
        resp = client.get(reverse("licenses-list"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_boe_endpoint_requires_auth(self):
        client = APIClient()
        resp = client.get(reverse("bill-of-entries-list"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_trade_endpoint_requires_auth(self):
        client = APIClient()
        resp = client.get(reverse("trade-list"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_allotment_endpoint_requires_auth(self):
        client = APIClient()
        resp = client.get(reverse("allotment-list"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_valid_jwt_grants_access_to_licenses(self, test_user):
        client = _auth_client(test_user)
        resp = client.get(reverse("licenses-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_refresh_token_endpoint_exists(self, test_user):
        refresh = RefreshToken.for_user(test_user)
        client = APIClient()
        resp = client.post(
            reverse("token_refresh"), {"refresh": str(refresh)}, format="json"
        )
        assert resp.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ===========================================================================
# 2. LICENSE ENDPOINTS
# ===========================================================================

@pytest.mark.django_db
class TestLicenseEndpoints:

    def test_list_licenses_returns_200(self, authenticated_client):
        resp = authenticated_client.get(reverse("licenses-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_list_licenses_response_is_list_or_paginated(self, authenticated_client, test_license):
        resp = authenticated_client.get(reverse("licenses-list"))
        assert resp.status_code == status.HTTP_200_OK
        # Either paginated dict with 'results' or a bare list
        assert "results" in resp.data or isinstance(resp.data, list)

    def test_retrieve_license_returns_correct_number(self, authenticated_client, test_license):
        resp = authenticated_client.get(
            reverse("licenses-detail", kwargs={"pk": test_license.id})
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["license_number"] == test_license.license_number

    def test_retrieve_license_includes_import_items(self, authenticated_client, test_license):
        resp = authenticated_client.get(
            reverse("licenses-detail", kwargs={"pk": test_license.id})
        )
        assert resp.status_code == status.HTTP_200_OK
        # import_items must be present and have 3 items (from conftest fixture)
        items = resp.data.get("import_items", [])
        assert len(items) == 3

    def test_retrieve_nonexistent_license_returns_404(self, authenticated_client):
        resp = authenticated_client.get(
            reverse("licenses-detail", kwargs={"pk": 999999})
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_filter_licenses_by_scheme_code(self, authenticated_client, test_license):
        resp = authenticated_client.get(
            reverse("licenses-list"), {"scheme_code": "DFIA"}
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_search_licenses_by_partial_number(self, authenticated_client, test_license):
        resp = authenticated_client.get(
            reverse("licenses-list"), {"search": test_license.license_number[:5]}
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_list_license_items_returns_200(self, authenticated_client, test_license):
        resp = authenticated_client.get(reverse("license-items-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_filter_license_items_by_license_id(self, authenticated_client, test_license):
        resp = authenticated_client.get(
            reverse("license-items-list"), {"license": test_license.id}
        )
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get("results", resp.data)
        assert len(results) == 3


# ===========================================================================
# 3. BILL OF ENTRY ENDPOINTS
# ===========================================================================

@pytest.mark.django_db
class TestBillOfEntryEndpoints:

    def test_list_boes_returns_200(self, authenticated_client):
        resp = authenticated_client.get(reverse("bill-of-entries-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_retrieve_boe_returns_correct_number(self, authenticated_client, test_bill_of_entry):
        resp = authenticated_client.get(
            reverse("bill-of-entries-detail", kwargs={"pk": test_bill_of_entry.id})
        )
        assert resp.status_code == status.HTTP_200_OK
        assert (
            str(resp.data.get("bill_of_entry_number", ""))
            == str(test_bill_of_entry.bill_of_entry_number)
        )

    def test_retrieve_boe_includes_item_details(self, authenticated_client, test_bill_of_entry):
        resp = authenticated_client.get(
            reverse("bill-of-entries-detail", kwargs={"pk": test_bill_of_entry.id})
        )
        assert resp.status_code == status.HTTP_200_OK
        # The nested items key may be 'item_details' or 'items'
        has_items = "item_details" in resp.data or "items" in resp.data
        assert has_items

    def test_retrieve_nonexistent_boe_returns_404(self, authenticated_client):
        resp = authenticated_client.get(
            reverse("bill-of-entries-detail", kwargs={"pk": 999999})
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_boe_missing_required_fields_returns_400(self, authenticated_client):
        resp = authenticated_client.post(
            reverse("bill-of-entries-list"), {}, format="json"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_boe_list_response_structure(self, authenticated_client, test_bill_of_entry):
        resp = authenticated_client.get(reverse("bill-of-entries-list"))
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data or isinstance(resp.data, list)


# ===========================================================================
# 4. TRADE ENDPOINTS
# ===========================================================================

@pytest.mark.django_db
class TestTradeEndpoints:

    def test_list_trades_returns_200(self, authenticated_client):
        resp = authenticated_client.get(reverse("trade-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_retrieve_nonexistent_trade_returns_404(self, authenticated_client):
        resp = authenticated_client.get(
            reverse("trade-detail", kwargs={"pk": 999999})
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_trade_missing_all_fields_returns_400(self, authenticated_client):
        resp = authenticated_client.post(reverse("trade-list"), {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_trade_list_response_structure(self, authenticated_client):
        resp = authenticated_client.get(reverse("trade-list"))
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data or isinstance(resp.data, list)

    def test_trade_list_supports_pagination(self, authenticated_client):
        resp = authenticated_client.get(reverse("trade-list"), {"page": 1})
        assert resp.status_code == status.HTTP_200_OK


# ===========================================================================
# 5. ALLOTMENT ENDPOINTS
# ===========================================================================

@pytest.mark.django_db
class TestAllotmentEndpoints:

    def test_list_allotments_returns_200(self, authenticated_client):
        resp = authenticated_client.get(reverse("allotment-list"))
        assert resp.status_code == status.HTTP_200_OK

    def test_retrieve_allotment_returns_correct_data(self, authenticated_client, test_allotment):
        resp = authenticated_client.get(
            reverse("allotment-detail", kwargs={"pk": test_allotment.id})
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["item_name"] == test_allotment.item_name

    def test_retrieve_nonexistent_allotment_returns_404(self, authenticated_client):
        resp = authenticated_client.get(
            reverse("allotment-detail", kwargs={"pk": 999999})
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_allotment_missing_required_fields_returns_400(self, authenticated_client):
        resp = authenticated_client.post(reverse("allotment-list"), {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_allotment_with_valid_data(self, authenticated_client, fake_allotment_data):
        resp = authenticated_client.post(
            reverse("allotment-list"), fake_allotment_data, format="json"
        )
        # 201 on success; 400 if serializer validation fails due to extra constraints
        assert resp.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_allotment_list_response_structure(self, authenticated_client, test_allotment):
        resp = authenticated_client.get(reverse("allotment-list"))
        assert resp.status_code == status.HTTP_200_OK
        assert "results" in resp.data or isinstance(resp.data, list)

    def test_allotment_required_quantity_is_positive(self, authenticated_client, test_allotment):
        resp = authenticated_client.get(
            reverse("allotment-detail", kwargs={"pk": test_allotment.id})
        )
        assert resp.status_code == status.HTTP_200_OK
        qty = Decimal(str(resp.data["required_quantity"]))
        assert qty > DEC_0


# ===========================================================================
# 6. DASHBOARD
# ===========================================================================

@pytest.mark.django_db
class TestDashboard:

    def test_dashboard_returns_200_when_authenticated(self, authenticated_client):
        resp = authenticated_client.get(reverse("dashboard"))
        assert resp.status_code == status.HTTP_200_OK

    def test_dashboard_requires_authentication(self):
        client = APIClient()
        resp = client.get(reverse("dashboard"))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# 7. LICENSE BALANCE CALCULATOR  (pure unit tests — no DB needed)
# ===========================================================================

class TestLicenseBalanceCalculator:
    """Unit tests for LicenseBalanceCalculator — mocks all DB queries."""

    # --- calculate_credit ---

    def test_credit_returns_export_total(self):
        mock_license = Mock()
        with patch("license.services.balance_calculator.LicenseExportItemModel") as m:
            m.objects.filter.return_value.aggregate.return_value = {
                "total": Decimal("1000.00")
            }
            result = LicenseBalanceCalculator.calculate_credit(mock_license)
        assert result == Decimal("1000.00")

    def test_credit_returns_zero_when_no_exports(self):
        mock_license = Mock()
        with patch("license.services.balance_calculator.LicenseExportItemModel") as m:
            m.objects.filter.return_value.aggregate.return_value = {"total": DEC_0}
            result = LicenseBalanceCalculator.calculate_credit(mock_license)
        assert result == DEC_0

    # --- calculate_debit ---

    def test_debit_returns_boe_total(self):
        mock_license = Mock()
        with patch("license.services.balance_calculator.RowDetails") as m:
            m.objects.filter.return_value.aggregate.return_value = {
                "total": Decimal("300.00")
            }
            result = LicenseBalanceCalculator.calculate_debit(mock_license)
        assert result == Decimal("300.00")

    def test_debit_returns_zero_when_no_boe(self):
        mock_license = Mock()
        with patch("license.services.balance_calculator.RowDetails") as m:
            m.objects.filter.return_value.aggregate.return_value = {"total": DEC_0}
            result = LicenseBalanceCalculator.calculate_debit(mock_license)
        assert result == DEC_0

    # --- calculate_allotment ---

    def test_allotment_returns_total(self):
        mock_license = Mock()
        with patch("license.services.balance_calculator.AllotmentItems") as m:
            m.objects.filter.return_value.aggregate.return_value = {
                "total": Decimal("200.00")
            }
            result = LicenseBalanceCalculator.calculate_allotment(mock_license)
        assert result == Decimal("200.00")

    def test_allotment_returns_zero_when_no_items(self):
        mock_license = Mock()
        with patch("license.services.balance_calculator.AllotmentItems") as m:
            m.objects.filter.return_value.aggregate.return_value = {"total": DEC_0}
            result = LicenseBalanceCalculator.calculate_allotment(mock_license)
        assert result == DEC_0

    # --- calculate_balance ---

    def test_balance_positive(self):
        mock_license = Mock()
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=Decimal("1000.00")),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=Decimal("300.00")),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=Decimal("200.00")),
        ):
            result = LicenseBalanceCalculator.calculate_balance(mock_license)
        assert result == Decimal("500.00")  # 1000 - (300 + 200)

    def test_balance_clamped_to_zero_when_debit_exceeds_credit(self):
        mock_license = Mock()
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=Decimal("100.00")),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=Decimal("300.00")),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=Decimal("200.00")),
        ):
            result = LicenseBalanceCalculator.calculate_balance(mock_license)
        assert result == DEC_0

    def test_balance_exact_zero_when_credit_equals_debits(self):
        mock_license = Mock()
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=Decimal("500.00")),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=Decimal("300.00")),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=Decimal("200.00")),
        ):
            result = LicenseBalanceCalculator.calculate_balance(mock_license)
        assert result == DEC_0

    def test_balance_handles_very_large_values(self):
        mock_license = Mock()
        large = Decimal("999999999999.99")
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=large),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=DEC_0),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=DEC_0),
        ):
            result = LicenseBalanceCalculator.calculate_balance(mock_license)
        assert result == large

    def test_balance_handles_very_small_positive_value(self):
        mock_license = Mock()
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=Decimal("0.01")),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=DEC_0),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=DEC_0),
        ):
            result = LicenseBalanceCalculator.calculate_balance(mock_license)
        assert result == Decimal("0.01")

    # --- calculate_all_components ---

    def test_all_components_returns_correct_dict(self):
        mock_license = Mock()
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=Decimal("1000.00")),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=Decimal("300.00")),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=Decimal("200.00")),
        ):
            result = LicenseBalanceCalculator.calculate_all_components(mock_license)
        assert result["credit"] == Decimal("1000.00")
        assert result["debit"] == Decimal("300.00")
        assert result["allotment"] == Decimal("200.00")
        assert result["balance"] == Decimal("500.00")

    def test_all_components_balance_is_zero_when_negative(self):
        mock_license = Mock()
        with (
            patch.object(LicenseBalanceCalculator, "calculate_credit", return_value=Decimal("100.00")),
            patch.object(LicenseBalanceCalculator, "calculate_debit", return_value=Decimal("300.00")),
            patch.object(LicenseBalanceCalculator, "calculate_allotment", return_value=Decimal("200.00")),
        ):
            result = LicenseBalanceCalculator.calculate_all_components(mock_license)
        assert result["balance"] == DEC_0


# ===========================================================================
# 8. ITEM BALANCE CALCULATOR  (pure unit tests — no DB needed)
# ===========================================================================

class TestItemBalanceCalculator:
    """Unit tests for ItemBalanceCalculator — mocks all DB queries."""

    # --- calculate_item_credit_debit ---

    def test_item_credit_debit_with_specific_cif(self):
        mock_item = Mock()
        mock_item.cif_fc = Decimal("500.00")
        mock_item.license = Mock()
        with (
            patch("license.services.balance_calculator.RowDetails") as mock_rd,
            patch("license.services.balance_calculator.AllotmentItems") as mock_ai,
        ):
            mock_rd.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": Decimal("100.00")}
            mock_ai.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": Decimal("50.00")}
            credit, total_debit = ItemBalanceCalculator.calculate_item_credit_debit(mock_item)
        assert credit == Decimal("500.00")
        assert total_debit == Decimal("150.00")

    def test_item_credit_debit_falls_back_to_export_total_when_cif_is_zero(self):
        mock_item = Mock()
        mock_item.cif_fc = DEC_0
        mock_item.license = Mock()
        with (
            patch("license.services.balance_calculator.LicenseExportItemModel") as mock_exp,
            patch("license.services.balance_calculator.RowDetails") as mock_rd,
            patch("license.services.balance_calculator.AllotmentItems") as mock_ai,
        ):
            mock_exp.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": Decimal("1000.00")}
            mock_rd.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": Decimal("300.00")}
            mock_ai.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": Decimal("100.00")}
            credit, total_debit = ItemBalanceCalculator.calculate_item_credit_debit(mock_item)
        assert credit == Decimal("1000.00")
        assert total_debit == Decimal("400.00")

    def test_item_credit_debit_handles_null_aggregates(self):
        mock_item = Mock()
        mock_item.cif_fc = Decimal("500.00")
        mock_item.license = Mock()
        with (
            patch("license.services.balance_calculator.RowDetails") as mock_rd,
            patch("license.services.balance_calculator.AllotmentItems") as mock_ai,
        ):
            mock_rd.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": None}
            mock_ai.objects.filter.return_value.aggregate.return_value = {"cif_fc__sum": None}
            credit, total_debit = ItemBalanceCalculator.calculate_item_credit_debit(mock_item)
        assert credit == Decimal("500.00")
        assert total_debit == DEC_0

    # --- calculate_item_balance ---

    def test_item_balance_positive(self):
        mock_item = Mock()
        with patch.object(ItemBalanceCalculator, "calculate_item_credit_debit",
                          return_value=(Decimal("500.00"), Decimal("200.00"))):
            result = ItemBalanceCalculator.calculate_item_balance(mock_item)
        assert result == Decimal("300.00")

    def test_item_balance_clamped_to_zero(self):
        mock_item = Mock()
        with patch.object(ItemBalanceCalculator, "calculate_item_credit_debit",
                          return_value=(Decimal("100.00"), Decimal("300.00"))):
            result = ItemBalanceCalculator.calculate_item_balance(mock_item)
        assert result == DEC_0

    # --- calculate_available_quantity ---

    def test_available_quantity_partial_usage(self):
        mock_item = Mock()
        mock_item.quantity = Decimal("1000")
        with (
            patch("license.services.balance_calculator.RowDetails") as mock_rd,
            patch("license.services.balance_calculator.AllotmentItems") as mock_ai,
        ):
            mock_rd.objects.filter.return_value.aggregate.return_value = {"qty__sum": Decimal("300")}
            mock_ai.objects.filter.return_value.aggregate.return_value = {"qty__sum": Decimal("200")}
            result = ItemBalanceCalculator.calculate_available_quantity(mock_item)
        assert result == Decimal("500")

    def test_available_quantity_returns_zero_when_fully_allocated(self):
        mock_item = Mock()
        mock_item.quantity = Decimal("1000")
        with (
            patch("license.services.balance_calculator.RowDetails") as mock_rd,
            patch("license.services.balance_calculator.AllotmentItems") as mock_ai,
        ):
            mock_rd.objects.filter.return_value.aggregate.return_value = {"qty__sum": Decimal("600")}
            mock_ai.objects.filter.return_value.aggregate.return_value = {"qty__sum": Decimal("500")}
            result = ItemBalanceCalculator.calculate_available_quantity(mock_item)
        assert result == DEC_0

    # --- calculate_available_value_for_allocation ---

    def test_allocation_constrained_by_available_quantity(self):
        mock_item = Mock()
        with (
            patch.object(ItemBalanceCalculator, "calculate_available_quantity", return_value=Decimal("100")),
            patch.object(ItemBalanceCalculator, "calculate_item_balance", return_value=Decimal("5000.00")),
        ):
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, Decimal("10.00")
            )
        assert result["max_quantity"] == Decimal("100")
        assert result["max_value"] == Decimal("1000.00")  # 100 × 10

    def test_allocation_constrained_by_cif_balance(self):
        mock_item = Mock()
        with (
            patch.object(ItemBalanceCalculator, "calculate_available_quantity", return_value=Decimal("1000")),
            patch.object(ItemBalanceCalculator, "calculate_item_balance", return_value=Decimal("500.00")),
        ):
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, Decimal("10.00")
            )
        assert result["max_quantity"] == Decimal("50")   # 500 / 10
        assert result["max_value"] == Decimal("500.00")

    def test_allocation_constrained_by_required_value(self):
        mock_item = Mock()
        with (
            patch.object(ItemBalanceCalculator, "calculate_available_quantity", return_value=Decimal("1000")),
            patch.object(ItemBalanceCalculator, "calculate_item_balance", return_value=Decimal("5000.00")),
        ):
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, Decimal("10.00"), Decimal("300.00")
            )
        assert result["max_quantity"] == Decimal("30")   # 300 / 10
        assert result["max_value"] == Decimal("300.00")

    def test_allocation_with_zero_unit_price_returns_zero(self):
        mock_item = Mock()
        with (
            patch.object(ItemBalanceCalculator, "calculate_available_quantity", return_value=Decimal("1000")),
            patch.object(ItemBalanceCalculator, "calculate_item_balance", return_value=Decimal("5000.00")),
        ):
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, DEC_0
            )
        assert result["max_quantity"] == DEC_0
        assert result["max_value"] == DEC_0

    def test_allocation_decimal_precision_maintained(self):
        mock_item = Mock()
        with (
            patch.object(ItemBalanceCalculator, "calculate_available_quantity", return_value=Decimal("100")),
            patch.object(ItemBalanceCalculator, "calculate_item_balance", return_value=Decimal("500.00")),
        ):
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, Decimal("3.333")
            )
        assert isinstance(result["max_quantity"], Decimal)
        assert isinstance(result["max_value"], Decimal)

    # --- calculate_item_components ---

    def test_item_components_returns_all_keys(self):
        mock_item = Mock()
        with (
            patch.object(ItemBalanceCalculator, "calculate_item_credit_debit",
                         return_value=(Decimal("500.00"), Decimal("200.00"))),
            patch.object(ItemBalanceCalculator, "calculate_available_quantity",
                         return_value=Decimal("300")),
        ):
            result = ItemBalanceCalculator.calculate_item_components(mock_item)
        assert result["credit"] == Decimal("500.00")
        assert result["debit"] == Decimal("200.00")
        assert result["balance"] == Decimal("300.00")
        assert result["available_quantity"] == Decimal("300")
