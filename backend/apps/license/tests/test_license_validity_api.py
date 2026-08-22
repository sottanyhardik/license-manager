"""Regression coverage for the licence validity endpoint."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel


pytestmark = pytest.mark.django_db


def _authenticated_client():
    user = get_user_model().objects.create_user(username="validity-user")
    role, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_check_validity_uses_live_expiry_date_and_active_flag():
    company = CompanyModel.objects.create(iec="VALIDITY01", name="Validity Company")
    client = _authenticated_client()
    today = timezone.localdate()

    valid = LicenseDetailsModel.objects.create(
        license_number="VALIDITY-FUTURE", exporter=company,
        license_expiry_date=today + timedelta(days=10),
    )
    expired = LicenseDetailsModel.objects.create(
        license_number="VALIDITY-EXPIRED", exporter=company,
        license_expiry_date=today - timedelta(days=1),
    )
    inactive = LicenseDetailsModel.objects.create(
        license_number="VALIDITY-INACTIVE", exporter=company,
        license_expiry_date=today + timedelta(days=10),
    )
    inactive.flags.is_active = False
    inactive.flags.save(update_fields=["is_active"])

    valid_response = client.get(f"/api/licenses/{valid.pk}/check-validity/")
    expired_response = client.get(f"/api/licenses/{expired.pk}/check-validity/")
    inactive_response = client.get(f"/api/licenses/{inactive.pk}/check-validity/")

    assert valid_response.status_code == 200
    assert valid_response.data == {
        "license_id": valid.pk,
        "license_number": "VALIDITY-FUTURE",
        "is_valid": True,
        "is_active": True,
        "is_expired": False,
        "license_expiry_date": today + timedelta(days=10),
        "days_until_expiry": 10,
    }
    assert expired_response.status_code == 200
    assert expired_response.data["is_valid"] is False
    assert expired_response.data["is_expired"] is True
    assert expired_response.data["days_until_expiry"] == -1
    assert inactive_response.status_code == 200
    assert inactive_response.data["is_valid"] is False
    assert inactive_response.data["is_active"] is False


def test_license_list_is_not_scoped_by_a_user_company():
    company = CompanyModel.objects.create(iec="LISTACC001", name="List Access Company")
    client = _authenticated_client()
    license_obj = LicenseDetailsModel.objects.create(
        license_number="LIST-ACCESS", exporter=company,
    )

    response = client.get("/api/licenses/", {"page_size": 200})

    assert response.status_code == 200
    assert license_obj.pk in {row["id"] for row in response.data["results"]}
