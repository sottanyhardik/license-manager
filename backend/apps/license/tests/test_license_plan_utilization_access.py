"""
Regression: GET /api/licenses/<id>/plan-utilization/ (the Planning tab's data)
returned 404 to every non-superuser.

The action compared ``license.exporter_id`` with ``user.company_id``, but the
User model has no such field, so the comparison was always unequal.  Access is
governed by the role permission of the licence viewset, as for the other
overview actions; this test pins that behaviour for role holders and superusers.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def licence(db):
    company = CompanyModel.objects.create(iec="PUACCESS01", name="Plan Utilization Access Co")
    return LicenseDetailsModel.objects.create(license_number="PU-ACCESS-LIC", exporter=company)


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_role_holder_can_read_plan_utilization(licence):
    user = User.objects.create_user(username="pu-role-holder")
    user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    response = _client_for(user).get(f"/api/licenses/{licence.pk}/plan-utilization/")

    assert response.status_code == 200, response.content
    assert response.data["license_number"] == "PU-ACCESS-LIC"
    assert isinstance(response.data["rows"], list)


def test_superuser_can_still_read_plan_utilization(licence):
    user = User.objects.create_superuser(username="pu-superuser", email="pu-superuser@example.com", password="x")

    response = _client_for(user).get(f"/api/licenses/{licence.pk}/plan-utilization/")

    assert response.status_code == 200, response.content
