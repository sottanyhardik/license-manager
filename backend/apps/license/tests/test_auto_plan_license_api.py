"""Integration tests for license-first Auto Plan API endpoints.

Tests for plan-license and plan-licenses actions that resolve SION norms from
license export manifest and execute planning through Module 06.

NOTE: Tests for plan-licenses endpoint are marked as deprecated (skipped) because
the endpoint was removed in Phase 2D.6 consolidation. All bulk planning should now
route through /planning page via plan-sion endpoint.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, HSCodeModel, SionNormClassModel,
)
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    LicenseItemPlan, LicenseReplanRequest, SionPlanningRule,
)
from apps.license.services.sion_planner_config.importer import import_e1_e5_profiles


pytestmark = pytest.mark.django_db


def _assert_queued(response, license_obj, mode):
    assert response.status_code == 202, response.data
    assert response.data["license_id"] == license_obj.pk
    assert response.data["license_number"] == license_obj.license_number
    assert response.data["planning_state"] == "REPLAN_PENDING"
    assert isinstance(response.data["replan_request_id"], int)
    request = LicenseReplanRequest.objects.get(pk=response.data["replan_request_id"])
    assert request.license_id == license_obj.pk
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0
    return request


def _assert_auto_plan_completed(response, license_obj):
    """The interactive licence endpoint returns only after planning commits."""
    assert response.status_code == 200, response.data
    assert response.data["license_id"] == license_obj.pk
    assert response.data["license_number"] == license_obj.license_number
    assert response.data["planning_state"] == "COMPLETED"
    assert response.data["force"] is True
    assert "replan_request_id" not in response.data
    assert response.data["message"] == "Licence planning has completed."
    # SION-wide/source-change replans remain durable, but the interactive
    # endpoint must not create a second manual request in addition to its
    # committed inline replacement.
    assert not LicenseReplanRequest.objects.filter(
        license=license_obj, reason="manual_auto_plan",
    ).exists()
    return response.data


def _complete_auto_plan(client, license_obj):
    """Call the synchronous, forced licence Auto Plan contract."""
    response = client.post(
        f"/api/licenses/{license_obj.pk}/auto-plan/", {"force": True}, format="json",
    )
    return _assert_auto_plan_completed(response, license_obj)


@pytest.fixture
def setup_planning_env():
    """Set up SION norms, company, user, and DB rules for planning tests."""
    head = HeadSIONNormsModel.objects.create(name="Test Planning")
    sions = {
        norm: SionNormClassModel.objects.create(
            head_norm=head, norm_class=norm, is_active=True,
        )
        for norm in ("E1", "E5")
    }
    # Load E1/E5 profiles and activate their rules
    import_e1_e5_profiles(activate=True)
    SionPlanningRule.objects.filter(sion=sions["E1"]).update(is_active=True)
    SionPlanningRule.objects.filter(sion=sions["E5"]).update(is_active=True)

    # IEC is a statutory 10-character identifier; keep this fixture valid so
    # the API contract, rather than database validation, is exercised.
    company = CompanyModel.objects.create(iec="AUTOPLAN01", name="AutoPlan Test")
    user = get_user_model().objects.create_user(username="autoplan-user")
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)

    client = APIClient()
    client.force_authenticate(user)

    return {
        "sions": sions,
        "company": company,
        "user": user,
        "client": client,
        "head": head,
    }


def _make_test_license(company, license_number, sion=None, cif=Decimal("1000")):
    """Helper to create a license with optional export item."""
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number=license_number,
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    if sion:
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=sion, cif_fc=cif,
        )
    return license_obj


def _add_import_items_to_license(license_obj, hsn, description, unit, qty):
    """Helper to add import items to a license."""
    hs = HSCodeModel.objects.get_or_create(
        hs_code=hsn, defaults={
            "product_description": description,
            "unit": unit,
        }
    )[0]
    return LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs,
        description=description, unit=unit,
        quantity=qty, available_quantity=qty,
    )


def test_plan_license_single_sion_e1(setup_planning_env):
    """Test planning a single license with E1 SION."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-E1-1", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_license_single_sion_e5(setup_planning_env):
    """Test planning a single license with E5 SION."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-E5-1", sion=env["sions"]["E5"]
    )
    _add_import_items_to_license(
        license_obj, "210600", "Dietary fibre", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_license_multiple_sions(setup_planning_env):
    """Test planning a license with multiple SION norms on export."""
    env = setup_planning_env
    license_obj = _make_test_license(env["company"], "TEST-MULTI-1")
    # Add both E1 and E5 to export
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=env["sions"]["E1"], cif_fc=Decimal("500"),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=env["sions"]["E5"], cif_fc=Decimal("500"),
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_license_not_found(setup_planning_env):
    """Test plan-license with non-existent license."""
    env = setup_planning_env
    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": 99999, "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 404
    assert response.data["code"] == "LICENSE_NOT_FOUND"


def test_plan_license_no_export_manifest(setup_planning_env):
    """Test plan-license with license that has no export items."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-NO-EXPORT", sion=None  # No export items
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_license_no_sion_norms(setup_planning_env):
    """Test plan-license with export items but no SION norms assigned."""
    env = setup_planning_env
    license_obj = LicenseDetailsModel.objects.create(
        exporter=env["company"],
        license_number="TEST-NO-SION",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    # Create export item with NULL norm_class
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=None, cif_fc=Decimal("1000"),
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_license_allows_role_authorized_license(setup_planning_env):
    """Planning access is role based after removal of ``User.company``."""
    env = setup_planning_env
    other_company = CompanyModel.objects.create(
        iec="OTHERCOMP1", name="Other Company"
    )
    license_obj = _make_test_license(
        other_company, "TEST-OTHER-COMPANY", sion=env["sions"]["E1"]
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_license_all_mode_replans_existing(setup_planning_env):
    """Test that ALL mode replans even if license is already planned."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-REPLAN", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    # Plan once
    response1 = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )
    _assert_queued(response1, license_obj, "NEW")

    # Plan again with ALL mode
    response2 = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "ALL"},
        format="json",
    )
    _assert_queued(response2, license_obj, "ALL")
    # The second click coalesces onto the one current durable request.
    assert response2.data["replan_request_id"] == response1.data["replan_request_id"]


def test_plan_licenses_bulk_single_license(setup_planning_env):
    """The licence action synchronously commits one forced replacement."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-BULK-1", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    data = _complete_auto_plan(env["client"], license_obj)
    assert data["write_results"] >= 0


def test_plan_licenses_bulk_multiple_licenses_same_sion(setup_planning_env):
    """Each explicit licence action commits independently without queuing."""
    env = setup_planning_env
    licenses = []
    for i in range(2):
        lic = _make_test_license(
            env["company"], f"TEST-BULK-{i}", sion=env["sions"]["E1"]
        )
        _add_import_items_to_license(
            lic, "080211", "Almond", "kg", Decimal("100")
        )
        licenses.append(lic)

    results = [_complete_auto_plan(env["client"], license) for license in licenses]
    assert {result["license_id"] for result in results} == {license.pk for license in licenses}


def test_plan_licenses_bulk_multiple_licenses_multiple_sions(setup_planning_env):
    """Each action resolves and commits all SIONs for its own licence."""
    env = setup_planning_env
    # License 1: E1 only
    lic1 = _make_test_license(
        env["company"], "TEST-BULK-E1", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        lic1, "080211", "Almond", "kg", Decimal("100")
    )

    # License 2: E5 only
    lic2 = _make_test_license(
        env["company"], "TEST-BULK-E5", sion=env["sions"]["E5"]
    )
    _add_import_items_to_license(
        lic2, "210600", "Dietary fibre", "kg", Decimal("100")
    )

    # License 3: Both E1 and E5
    lic3 = _make_test_license(env["company"], "TEST-BULK-BOTH")
    LicenseExportItemModel.objects.create(
        license=lic3, norm_class=env["sions"]["E1"], cif_fc=Decimal("500"),
    )
    LicenseExportItemModel.objects.create(
        license=lic3, norm_class=env["sions"]["E5"], cif_fc=Decimal("500"),
    )
    _add_import_items_to_license(
        lic3, "080211", "Almond", "kg", Decimal("100")
    )

    results = [_complete_auto_plan(env["client"], license) for license in (lic1, lic2, lic3)]
    assert {result["license_id"] for result in results} == {lic1.pk, lic2.pk, lic3.pk}
    # The synchronous action resolves all configured SIONs before responding.
    assert LicenseExportItemModel.objects.filter(license=lic3).count() == 2


def test_plan_licenses_empty_list(setup_planning_env):
    """The single-licence endpoint rejects a missing object identifier."""
    env = setup_planning_env
    response = env["client"].post("/api/licenses/not-a-license/auto-plan/", {"mode": "NEW"}, format="json")

    assert response.status_code == 404


def test_plan_licenses_one_license_fails(setup_planning_env):
    """An unknown licence creates no durable request."""
    env = setup_planning_env
    bad_id = 99999

    response = env["client"].post(
        f"/api/licenses/{bad_id}/auto-plan/", {"mode": "NEW"},
        format="json",
    )

    assert response.status_code == 404
    assert not LicenseReplanRequest.objects.filter(license_id=bad_id).exists()


def test_plan_license_requires_license_manager_role(setup_planning_env):
    """Test that plan-license requires LICENSE_MANAGER role."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-PERMS", sion=env["sions"]["E1"]
    )

    # Create a user without LICENSE_MANAGER role
    viewer_user = get_user_model().objects.create_user(username="viewer")
    role, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    viewer_user.groups.add(role)

    viewer_client = APIClient()
    viewer_client.force_authenticate(viewer_user)

    response = viewer_client.post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 403


def test_plan_license_default_mode_is_new(setup_planning_env):
    """Test that default mode is NEW when not specified."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-DEFAULT-MODE", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk},  # mode not specified
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")


def test_plan_licenses_default_mode_is_forced(setup_planning_env):
    """The licence action remains forced when the optional field is omitted."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-BULK-DEFAULT-MODE", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        f"/api/licenses/{license_obj.pk}/auto-plan/", {}, format="json",
    )
    data = _assert_auto_plan_completed(response, license_obj)
    assert data["force"] is True


def test_plan_license_response_structure(setup_planning_env):
    """Test the exact response structure of plan-license endpoint."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-RESPONSE", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    _assert_queued(response, license_obj, "NEW")
    assert response.data["message"] == "Licence replanning has been queued."


def test_plan_licenses_response_structure(setup_planning_env):
    """Response represents the committed synchronous planning result."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-BULK-RESPONSE", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        f"/api/licenses/{license_obj.pk}/auto-plan/", {"force": True}, format="json",
    )
    data = _assert_auto_plan_completed(response, license_obj)
    assert set(data) >= {
        "license_id", "license_number", "planning_state", "force",
        "write_results", "rules_executed", "message",
    }
