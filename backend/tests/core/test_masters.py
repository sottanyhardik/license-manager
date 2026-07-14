# tests/core/test_masters.py
"""
Integration tests for the core masters API.

All models are managed=False in production. For tests we patch Meta.managed=True
in conftest so SQLite creates the tables in the in-memory DB.

Endpoints under test:
  GET  /api/v1/masters/companies/          -> 200 paginated
  GET  /api/v1/masters/companies/?all=true -> 200 unpaginated
  GET  /api/v1/masters/companies/?search=  -> 200 filtered
  GET  /api/v1/masters/hs-codes/           -> 200
  GET  /api/v1/masters/exchange-rates/?date_from=... -> 200 filtered
  *    (unauthenticated)                   -> 401
"""
import factory
import pytest
from apps.core.models import (
    CompanyModel,
    ExchangeRateModel,
    HSCodeModel,
)
from django.urls import reverse
from factory.django import DjangoModelFactory
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = CompanyModel

    iec = factory.Sequence(lambda n: f"IEC{n:07d}")
    name = factory.Faker("company")
    pan = factory.LazyAttribute(lambda _: "ABCDE1234F")
    gst_number = factory.LazyAttribute(lambda _: "27ABCDE1234F1Z5")
    address_line_1 = factory.Faker("address")
    email = factory.Faker("email")


class HSCodeFactory(DjangoModelFactory):
    class Meta:
        model = HSCodeModel

    hs_code = factory.Sequence(lambda n: f"{n:08d}")
    product_description = factory.Faker("sentence")
    unit_price = factory.LazyAttribute(lambda _: "100.00")
    unit = "KGS"


class ExchangeRateFactory(DjangoModelFactory):
    class Meta:
        model = ExchangeRateModel

    date = factory.Sequence(lambda n: f"2024-{(n % 12) + 1:02d}-01")
    usd = factory.LazyAttribute(lambda _: "83.5000")
    euro = factory.LazyAttribute(lambda _: "90.2000")
    pound_sterling = factory.LazyAttribute(lambda _: "105.7500")
    chinese_yuan = factory.LazyAttribute(lambda _: "11.5000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_token(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="testuser_core",
        password="testpassword123",
        email="coretest@example.com",
    )
    refresh = RefreshToken.for_user(user)
    return {
        "user": user,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@pytest.fixture
def authenticated_client(api_client, auth_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token['access']}")
    return api_client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _url(name, **kwargs):
    """Resolve a core: namespaced URL by basename + action."""
    return reverse(name, kwargs=kwargs)


# ---------------------------------------------------------------------------
# Company tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCompanyList:
    """Tests for GET /api/v1/masters/companies/"""

    def test_company_list_returns_paginated(self, authenticated_client):
        """Paginated list returns 200 with pagination envelope."""
        CompanyFactory.create_batch(5)
        url = "/api/v1/masters/companies/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # StandardPagination wraps under pagination key
        assert "pagination" in data
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_company_list_all_unpaginated(self, authenticated_client):
        """?all=true returns a standard envelope with all results (no pagination)."""
        CompanyFactory.create_batch(3)
        url = "/api/v1/masters/companies/?all=true"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # ?all=true returns envelope with data list, no "pagination" key
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 3

    def test_company_search_filters_by_name(self, authenticated_client):
        """?search=<term> returns only matching companies."""
        CompanyFactory(name="ABCXYZ Industries")
        CompanyFactory(name="Unrelated Corp")
        url = "/api/v1/masters/companies/?search=ABCXYZ"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data)
        assert len(results) >= 1, "Search returned no results"
        assert all("ABCXYZ" in r["name"] for r in results)
        unrelated_names = [r["name"] for r in results if "ABCXYZ" not in r["name"]]
        assert not unrelated_names, f"Non-matching companies in results: {unrelated_names}"

    def test_company_detail(self, authenticated_client):
        """GET /:id/ returns 200 with full company data."""
        company = CompanyFactory()
        url = f"/api/v1/masters/companies/{company.pk}/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["iec"] == company.iec

    def test_company_list_page_size_respected(self, authenticated_client):
        """Pagination page_size param is honoured."""
        CompanyFactory.create_batch(10)
        url = "/api/v1/masters/companies/?page_size=3"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", [])
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# HS Code tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHSCodeList:
    """Tests for GET /api/v1/masters/hs-codes/"""

    def test_hscode_list_returns_200(self, authenticated_client):
        """HS code list returns 200."""
        HSCodeFactory.create_batch(3)
        url = "/api/v1/masters/hs-codes/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_hscode_search_by_code(self, authenticated_client):
        """?search=<code> filters by hs_code field."""
        HSCodeFactory(hs_code="12345678")
        HSCodeFactory(hs_code="99999999")
        url = "/api/v1/masters/hs-codes/?search=12345678"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data)
        hs_codes_in_results = [r["hs_code"] for r in results]
        assert "12345678" in hs_codes_in_results


# ---------------------------------------------------------------------------
# Exchange rate tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExchangeRateFilter:
    """Tests for GET /api/v1/masters/exchange-rates/"""

    def test_exchange_rate_list_returns_200(self, authenticated_client):
        """Exchange rate list returns 200."""
        ExchangeRateFactory()
        url = "/api/v1/masters/exchange-rates/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_exchange_rate_filter_by_date_from(self, authenticated_client):
        """date_from filter returns only rates on or after the given date."""
        ExchangeRateFactory(date="2024-01-01")
        ExchangeRateFactory(date="2024-06-01")
        ExchangeRateFactory(date="2024-12-01")
        url = "/api/v1/masters/exchange-rates/?date_from=2024-06-01"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data)
        for r in results:
            assert r["date"] >= "2024-06-01"

    def test_exchange_rate_filter_by_date_to(self, authenticated_client):
        """date_to filter returns only rates on or before the given date."""
        ExchangeRateFactory(date="2024-01-01")
        ExchangeRateFactory(date="2024-06-01")
        ExchangeRateFactory(date="2024-12-01")
        url = "/api/v1/masters/exchange-rates/?date_to=2024-06-01"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data.get("data", data)
        for r in results:
            assert r["date"] <= "2024-06-01"


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnauthenticatedAccess:
    """All master endpoints must return 401 for unauthenticated requests."""

    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/masters/companies/",
            "/api/v1/masters/ports/",
            "/api/v1/masters/hs-codes/",
            "/api/v1/masters/exchange-rates/",
            "/api/v1/masters/item-groups/",
            "/api/v1/masters/item-names/",
            "/api/v1/masters/sion-norm-classes/",
        ],
    )
    def test_unauthenticated_returns_401(self, api_client, url):
        """No credentials → 401 Unauthorized."""
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
