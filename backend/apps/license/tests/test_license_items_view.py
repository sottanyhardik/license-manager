from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel


User = get_user_model()


def _client_for_user(user):
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def license_item(db):
    license_obj = LicenseDetailsModel.objects.create(license_number="LIC-ITEM-VIEW-001")
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Unicode item tea \u2615",
    )


@pytest.fixture
def user_with_role(db):
    def create_user(username, *roles):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="RoleP@ssw0rd123",
        )
        for role in roles:
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
        return user

    return create_user


@pytest.mark.django_db
def test_license_items_require_authentication(license_item):
    response = APIClient().get(reverse("license:license-items-list"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_license_items_require_license_role(user_with_role, license_item):
    client = _client_for_user(user_with_role("no-license-role"))

    response = client.get(reverse("license:license-items-list"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_license_viewer_can_list_items_with_null_hs_code(user_with_role, license_item):
    client = _client_for_user(user_with_role("license-viewer", "LICENSE_VIEWER"))

    response = client.get(reverse("license:license-items-list"))

    assert response.status_code == status.HTTP_200_OK
    results = response.data.get("results", response.data)
    assert results[0]["hs_code"] is None
    assert results[0]["label"] == "LIC-ITEM-VIEW-001 - S.No.1"


@pytest.mark.django_db
def test_license_manager_can_patch_condition_type(user_with_role, license_item):
    client = _client_for_user(user_with_role("license-manager", "LICENSE_MANAGER"))

    response = client.patch(
        reverse("license:license-items-detail", args=[license_item.id]),
        {"condition_type": "AU"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    license_item.refresh_from_db()
    assert license_item.condition_type == "AU"
    assert license_item.is_restricted is True


@pytest.mark.django_db
def test_license_items_endpoint_disallows_create_and_delete(user_with_role, license_item):
    client = _client_for_user(user_with_role("license-manager-methods", "LICENSE_MANAGER"))

    create_response = client.post(
        reverse("license:license-items-list"),
        {
            "license": license_item.license_id,
            "serial_number": 2,
            "description": "Unexpected create",
        },
        format="json",
    )
    delete_response = client.delete(reverse("license:license-items-detail", args=[license_item.id]))

    assert create_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert delete_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert LicenseImportItemsModel.objects.filter(pk=license_item.pk).exists()
