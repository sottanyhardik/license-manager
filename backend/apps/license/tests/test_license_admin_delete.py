import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseReplanRequest


@pytest.mark.django_db
def test_admin_delete_license_with_import_items_succeeds(client):
    """Deleting a licence with child import items must not leave replan rows behind."""
    user = get_user_model().objects.create_superuser("delete-admin", "admin@example.com", "pw-12345!")
    client.force_login(user)
    license_obj = LicenseDetailsModel.objects.create(license_number="3011009642")
    LicenseImportItemsModel.objects.create(license=license_obj, serial_number=1, description="tea")

    response = client.post(f"/admin/license/licensedetailsmodel/{license_obj.pk}/delete/", {"post": "yes"})

    assert response.status_code == 302
    assert not LicenseDetailsModel.objects.filter(pk=license_obj.pk).exists()
    assert not LicenseReplanRequest.objects.filter(license_id=license_obj.pk).exists()


@pytest.mark.django_db
def test_api_delete_license_with_import_items_succeeds():
    """The licence API delete must cascade children without orphaning replan rows."""
    user = get_user_model().objects.create_user("delete-api", "api-delete@example.com", "RoleP@ssw0rd123")
    user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    license_obj = LicenseDetailsModel.objects.create(license_number="3011009642")
    LicenseImportItemsModel.objects.create(license=license_obj, serial_number=1, description="tea")

    response = client.delete(f"/api/licenses/{license_obj.pk}/")

    assert response.status_code == 204
    assert not LicenseDetailsModel.objects.filter(pk=license_obj.pk).exists()
    assert not LicenseReplanRequest.objects.filter(license_id=license_obj.pk).exists()
