"""HTTP contract tests for asynchronous licence Auto Plan."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseItemPlan, LicenseReplanRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager_client():
    company = CompanyModel.objects.create(iec="AUTOPLAN01", name="Auto Plan Test")
    user = get_user_model().objects.create_user(username="auto-plan-user", company=company)
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user)
    return client, company


def make_license(company, number="TEST-AUTO-PLAN"):
    return LicenseDetailsModel.objects.create(
        exporter=company, license_number=number,
        license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
    )


def test_auto_plan_queues_durable_request_without_inline_planning(manager_client):
    client, company = manager_client
    license_obj = make_license(company)
    with patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion") as planner, patch("apps.license.tasks.dispatch_replan_requests.delay"):
        response = client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", format="json")
    assert response.status_code == 202, response.data
    assert response.data["planning_state"] == "REPLAN_PENDING"
    request = LicenseReplanRequest.objects.get(pk=response.data["replan_request_id"])
    assert request.license_id == license_obj.pk
    assert request.reason == "manual_auto_plan"
    assert not LicenseItemPlan.objects.filter(license=license_obj).exists()
    planner.assert_not_called()


def test_repeated_auto_plan_clicks_coalesce(manager_client):
    client, company = manager_client
    license_obj = make_license(company, "TEST-AUTO-COALESCE")
    with patch("apps.license.tasks.dispatch_replan_requests.delay"):
        first = client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", format="json")
        second = client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", format="json")
    assert first.status_code == second.status_code == 202
    assert first.data["replan_request_id"] == second.data["replan_request_id"]
    assert LicenseReplanRequest.objects.filter(license=license_obj).count() == 1


def test_auto_plan_rejects_missing_or_foreign_license(manager_client):
    client, company = manager_client
    assert client.post("/api/licenses/999999/auto-plan/", format="json").status_code == 404
    foreign = CompanyModel.objects.create(iec="AUTOPLAN02", name="Foreign")
    foreign_license = make_license(foreign, "TEST-AUTO-FOREIGN")
    assert client.post(f"/api/licenses/{foreign_license.pk}/auto-plan/", format="json").status_code == 404


def test_auto_plan_requires_license_manager_role(manager_client):
    _, company = manager_client
    license_obj = make_license(company, "TEST-AUTO-PERMISSION")
    user = get_user_model().objects.create_user(username="auto-plan-viewer", company=company)
    client = APIClient()
    client.force_authenticate(user)
    assert client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", format="json").status_code == 403
