"""HTTP contract tests for the synchronous licence Auto Plan action."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseReplanRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager_client():
    company = CompanyModel.objects.create(iec="AUTOPLAN01", name="Auto Plan Test")
    user = get_user_model().objects.create_user(username="auto-plan-user")
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


def _post_with_canonical_planner(client, license_obj, *, result=None):
    with patch(
        "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
        return_value=(license_obj, [430]),
    ), patch(
        "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
        return_value=result or {"write_results": [{"license_id": license_obj.pk}], "rules_executed": [99]},
    ) as planner, patch("apps.license.tasks.dispatch_replan_requests.delay") as delay:
        response = client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", {"force": True}, format="json")
    return response, planner, delay


def test_auto_plan_runs_canonical_planner_inline_and_never_enqueues(manager_client):
    client, company = manager_client
    license_obj = make_license(company)
    response, planner, delay = _post_with_canonical_planner(client, license_obj)

    assert response.status_code == 200, response.data
    assert response.data["planning_state"] == "COMPLETED"
    assert response.data["force"] is True
    assert response.data["write_results"] == 1
    planner.assert_called_once_with(430, license_ids=[license_obj.pk], mode="ALL", force_plan=True)
    delay.assert_not_called()
    assert not LicenseReplanRequest.objects.filter(license=license_obj, reason="manual_auto_plan").exists()


def test_auto_plan_force_contract_accepts_only_json_boolean(manager_client):
    client, company = manager_client
    license_obj = make_license(company, "TEST-AUTO-FORCE")
    response, planner, _delay = _post_with_canonical_planner(client, license_obj)
    assert response.status_code == 200
    planner.assert_called_once()
    response = client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", {"force": "true"}, format="json")
    assert response.status_code == 400
    assert response.data == {"force": ["Must be a boolean."]}


def test_repeated_forced_auto_plan_replaces_using_the_canonical_planner(manager_client):
    client, company = manager_client
    license_obj = make_license(company, "TEST-AUTO-REPLACE")
    first, planner_one, _ = _post_with_canonical_planner(client, license_obj)
    second, planner_two, _ = _post_with_canonical_planner(client, license_obj)
    assert first.status_code == second.status_code == 200
    planner_one.assert_called_once()
    planner_two.assert_called_once()


def test_auto_plan_rolls_back_if_canonical_planner_fails(manager_client):
    client, company = manager_client
    license_obj = make_license(company, "TEST-AUTO-ROLLBACK")
    with patch(
        "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
        return_value=(license_obj, [430]),
    ), patch(
        "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
        side_effect=RuntimeError("planner failure"),
    ), patch("apps.license.tasks.dispatch_replan_requests.delay") as delay:
        with pytest.raises(RuntimeError, match="planner failure"):
            client.post(f"/api/licenses/{license_obj.pk}/auto-plan/", {"force": True}, format="json")
    delay.assert_not_called()


def test_auto_plan_rejects_missing_license_and_requires_existing_permission(manager_client):
    client, company = manager_client
    assert client.post("/api/licenses/999999/auto-plan/", format="json").status_code == 404
    license_obj = make_license(company, "TEST-AUTO-PERMISSION")
    user = get_user_model().objects.create_user(username="auto-plan-viewer")
    unauthorised = APIClient()
    unauthorised.force_authenticate(user)
    assert unauthorised.post(f"/api/licenses/{license_obj.pk}/auto-plan/", format="json").status_code == 403


def test_auto_plan_finds_an_expired_license_despite_the_list_default_filter(manager_client):
    client, company = manager_client
    license_obj = make_license(company, "TEST-AUTO-EXPIRED")
    license_obj.license_expiry_date = date.today() - timedelta(days=1)
    license_obj.save(update_fields=["license_expiry_date"])

    response, planner, _delay = _post_with_canonical_planner(client, license_obj)

    assert response.status_code == 200, response.data
    planner.assert_called_once_with(430, license_ids=[license_obj.pk], mode="ALL", force_plan=True)
