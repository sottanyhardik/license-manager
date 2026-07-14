# tests/dashboard/test_dashboard.py
"""
Integration tests for the dashboard API.

Endpoints under test:
  GET /api/v1/dashboard/stats/                -> 200 all expected keys
  GET /api/v1/dashboard/stats/ (unauthenticated) -> 401
  GET /api/v1/dashboard/expiring-licenses/    -> 200 (with license fixture)
  GET /api/v1/dashboard/charts/utilisation/   -> 200
  GET /api/v1/dashboard/charts/activity/      -> 200

Models are managed=False in production; test.py patches Meta.managed=True
at import time so SQLite creates the tables.
"""
from datetime import date, timedelta

import factory
import pytest
from factory.django import DjangoModelFactory
from rest_framework import status

from apps.license.models.license import LicenseBalance, LicenseDetailsModel, LicenseFlags


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

class LicenseDetailsFactory(DjangoModelFactory):
    class Meta:
        model = LicenseDetailsModel

    license_number = factory.Sequence(lambda n: f"LIC-TEST-{n:05d}")
    license_date = factory.LazyFunction(date.today)
    license_expiry_date = factory.LazyFunction(lambda: date.today() + timedelta(days=60))


class LicenseBalanceFactory(DjangoModelFactory):
    class Meta:
        model = LicenseBalance

    license = factory.SubFactory(LicenseDetailsFactory)
    balance_cif = factory.LazyAttribute(lambda _: "5000.00")


class LicenseFlagsFactory(DjangoModelFactory):
    class Meta:
        model = LicenseFlags

    license = factory.SubFactory(LicenseDetailsFactory)
    is_active = True
    is_expired = False
    is_null = False


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

STATS_URL = "/api/v1/dashboard/stats/"
EXPIRING_URL = "/api/v1/dashboard/expiring-licenses/"
UTILISATION_URL = "/api/v1/dashboard/charts/utilisation/"
ACTIVITY_URL = "/api/v1/dashboard/charts/activity/"


@pytest.mark.django_db
class TestDashboardStats:
    """Tests for GET /api/v1/dashboard/stats/."""

    def test_stats_returns_expected_keys(self, authenticated_client):
        response = authenticated_client.get(STATS_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        expected_keys = [
            "total_licenses",
            "active_licenses",
            "expired_licenses",
            "null_licenses",
            "expiring_soon",
            "total_balance_cif",
            "recent_boes",
            "recent_allotments",
            "low_balance_licenses",
        ]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_stats_numeric_defaults(self, authenticated_client):
        """With no license data the counts should be zero."""
        response = authenticated_client.get(STATS_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_licenses"] == 0
        assert data["active_licenses"] == 0
        assert data["total_balance_cif"] == "0.00"

    def test_stats_second_call_returns_200(self, authenticated_client):
        """Both calls should succeed (second call hits cache)."""
        r1 = authenticated_client.get(STATS_URL)
        r2 = authenticated_client.get(STATS_URL)
        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK

    def test_unauthenticated_blocked(self, api_client):
        response = api_client.get(STATS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestExpiringLicenses:
    """Tests for GET /api/v1/dashboard/expiring-licenses/."""

    def test_expiring_license_appears_in_response(self, authenticated_client):
        """A license expiring in 15 days with sufficient balance should appear."""
        lic = LicenseDetailsFactory(
            license_number="EXPIRE-001",
            license_expiry_date=date.today() + timedelta(days=15),
        )
        LicenseBalanceFactory(license=lic, balance_cif="500.00")
        LicenseFlagsFactory(license=lic, is_active=True, is_expired=False, is_null=False)

        response = authenticated_client.get(EXPIRING_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        numbers = [item["license_number"] for item in data]
        assert "EXPIRE-001" in numbers

    def test_non_expiring_license_excluded(self, authenticated_client):
        """A license expiring in 90 days should NOT appear in the 30-day window."""
        lic = LicenseDetailsFactory(
            license_number="FAR-FUTURE-001",
            license_expiry_date=date.today() + timedelta(days=90),
        )
        LicenseBalanceFactory(license=lic, balance_cif="500.00")
        LicenseFlagsFactory(license=lic, is_active=True, is_expired=False, is_null=False)

        response = authenticated_client.get(EXPIRING_URL)
        assert response.status_code == status.HTTP_200_OK
        numbers = [item["license_number"] for item in response.json()]
        assert "FAR-FUTURE-001" not in numbers

    def test_unauthenticated_blocked(self, api_client):
        response = api_client.get(EXPIRING_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestChartEndpoints:
    """Tests for GET /api/v1/dashboard/charts/*."""

    def test_utilisation_chart_returns_200(self, authenticated_client):
        response = authenticated_client.get(UTILISATION_URL)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)

    def test_activity_chart_returns_200(self, authenticated_client):
        response = authenticated_client.get(ACTIVITY_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # Should always have exactly 12 months
        assert len(data) == 12

    def test_activity_chart_month_keys(self, authenticated_client):
        """Each month entry must have the expected keys."""
        response = authenticated_client.get(ACTIVITY_URL)
        assert response.status_code == status.HTTP_200_OK
        for entry in response.json():
            assert "month" in entry
            assert "boe_count" in entry
            assert "allotment_count" in entry

    def test_utilisation_chart_unauthenticated(self, api_client):
        response = api_client.get(UTILISATION_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activity_chart_unauthenticated(self, api_client):
        response = api_client.get(ACTIVITY_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
