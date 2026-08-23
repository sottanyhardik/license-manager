"""Authorization contracts for the shared License Ledger export endpoint."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_export_rejects_unauthenticated_requests():
    response = APIClient().get(
        reverse("license:license-ledger-export"),
        {"file_format": "pdf"},
    )

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_export_allows_role_authorized_company_reporting_filter(test_company, test_company_2):
    user = get_user_model().objects.create_user(
        username="ledger-export-cross-company",
        password="test-password",
    )
    user.groups.add(Group.objects.get_or_create(name="TRADE_VIEWER")[0])
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(
        reverse("license:license-ledger-export"),
        {
            "file_format": "xlsx",
            "buying_company_id": test_company_2.id,
        },
    )

    assert response.status_code in {200, 404}


@pytest.mark.django_db
def test_export_allows_role_authorized_license(
    test_company, test_company_2, test_license,
):
    """The ledger export authorization boundary is the caller's role."""
    user = get_user_model().objects.create_user(
        username="ledger-export-idor",
        password="test-password",
    )
    user.groups.add(Group.objects.get_or_create(name="TRADE_VIEWER")[0])
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(
        reverse("license:license-ledger-export"),
        {
            "file_format": "pdf",
            "license_id": test_license.id,
            "license_type": "DFIA",
        },
    )

    assert response.status_code in {200, 404}


@pytest.mark.django_db
def test_export_rejects_invalid_license_type(authenticated_client, test_license):
    response = authenticated_client.get(
        reverse("license:license-ledger-export"),
        {"file_format": "pdf", "license_id": test_license.id, "license_type": "INVALID"},
    )

    assert response.status_code == 400
    assert "license_type" in response.json()
