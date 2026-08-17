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
    LicenseItemPlan, SionPlanningRule,
)
from apps.license.services.sion_planner_config.importer import import_e1_e5_profiles


pytestmark = pytest.mark.django_db


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

    company = CompanyModel.objects.create(iec="AUTOPLAN-TEST", name="AutoPlan Test")
    user = get_user_model().objects.create_user(
        username="autoplan-user", company=company
    )
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

    assert response.status_code == 200
    data = response.data
    assert data["license_id"] == license_obj.pk
    assert data["license_number"] == "TEST-E1-1"
    assert data["mode"] == "NEW"
    assert len(data["applicable_sions"]) == 1
    assert data["applicable_sions"][0]["sion_id"] == env["sions"]["E1"].pk
    assert data["applicable_sions"][0]["sion_code"] == "E1"
    assert data["applicable_sions"][0]["status"] == "EXECUTED"
    assert len(data["applicable_sions"][0]["rules_executed"]) > 0
    assert data["total_results"]["sions_processed"] == 1


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

    assert response.status_code == 200
    data = response.data
    assert data["applicable_sions"][0]["sion_id"] == env["sions"]["E5"].pk
    assert data["applicable_sions"][0]["sion_code"] == "E5"
    assert data["applicable_sions"][0]["status"] == "EXECUTED"


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

    assert response.status_code == 200
    data = response.data
    sion_codes = [s["sion_code"] for s in data["applicable_sions"]]
    assert "E1" in sion_codes
    assert "E5" in sion_codes
    assert data["total_results"]["sions_processed"] == 2


def test_plan_license_not_found(setup_planning_env):
    """Test plan-license with non-existent license."""
    env = setup_planning_env
    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": 99999, "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 400
    assert "not found" in response.data.get("error", "").lower()


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

    assert response.status_code == 400
    assert "export manifest" in response.data.get("error", "").lower()


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

    assert response.status_code == 400
    assert "sion" in response.data.get("error", "").lower()


def test_plan_license_company_isolation(setup_planning_env):
    """Test plan-license respects company isolation."""
    env = setup_planning_env
    other_company = CompanyModel.objects.create(
        iec="OTHER-COMPANY", name="Other Company"
    )
    license_obj = _make_test_license(
        other_company, "TEST-OTHER-COMPANY", sion=env["sions"]["E1"]
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 403
    assert "another company" in response.data.get("error", "").lower()


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
    assert response1.status_code == 200

    # Plan again with ALL mode
    response2 = env["client"].post(
        "/api/sion-planning-rules/plan-license/",
        {"license_id": license_obj.pk, "mode": "ALL"},
        format="json",
    )
    assert response2.status_code == 200
    # Should still execute, not skip
    assert response2.data["applicable_sions"][0]["status"] == "EXECUTED"


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_bulk_single_license(setup_planning_env):
    """Test plan-licenses with a single license in the list (DEPRECATED)."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-BULK-1", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [license_obj.pk], "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 200
    data = response.data
    assert data["mode"] == "NEW"
    assert len(data["licenses_processed"]) == 1
    assert data["licenses_processed"][0]["license_id"] == license_obj.pk
    assert data["summary"]["total_licenses"] == 1
    assert data["summary"]["total_sions"] == 1


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_bulk_multiple_licenses_same_sion(setup_planning_env):
    """Test plan-licenses with multiple licenses, same SION (DEPRECATED)."""
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

    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [lic.pk for lic in licenses], "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 200
    data = response.data
    assert len(data["licenses_processed"]) == 2
    assert data["summary"]["total_licenses"] == 2
    assert data["summary"]["total_sions"] == 1


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_bulk_multiple_licenses_multiple_sions(setup_planning_env):
    """Test plan-licenses with multiple licenses and multiple SIONs (DEPRECATED)."""
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

    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [lic1.pk, lic2.pk, lic3.pk], "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 200
    data = response.data
    assert len(data["licenses_processed"]) == 3
    assert data["summary"]["total_licenses"] == 3
    # Should have both E1 and E5 in the log
    sion_codes = {log["sion_code"] for log in data["summary"]["sion_execution_log"]}
    assert "E1" in sion_codes
    assert "E5" in sion_codes


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_empty_list(setup_planning_env):
    """Test plan-licenses rejects empty license list (DEPRECATED)."""
    env = setup_planning_env
    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [], "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_one_license_fails(setup_planning_env):
    """Test that plan-licenses fails if any license cannot be loaded (DEPRECATED)."""
    env = setup_planning_env
    good_lic = _make_test_license(
        env["company"], "TEST-GOOD", sion=env["sions"]["E1"]
    )
    bad_id = 99999

    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [good_lic.pk, bad_id], "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 400
    assert "not found" in response.data.get("error", "").lower()


def test_plan_license_requires_license_manager_role(setup_planning_env):
    """Test that plan-license requires LICENSE_MANAGER role."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-PERMS", sion=env["sions"]["E1"]
    )

    # Create a user without LICENSE_MANAGER role
    viewer_user = get_user_model().objects.create_user(
        username="viewer", company=env["company"]
    )
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

    assert response.status_code == 200
    assert response.data["mode"] == "NEW"


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_default_mode_is_new(setup_planning_env):
    """Test that default mode is NEW when not specified for bulk endpoint."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-BULK-DEFAULT-MODE", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [license_obj.pk]},  # mode not specified
        format="json",
    )

    assert response.status_code == 200
    assert response.data["mode"] == "NEW"


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

    assert response.status_code == 200
    data = response.data

    # Verify top-level structure
    assert "license_id" in data
    assert "license_number" in data
    assert "mode" in data
    assert "applicable_sions" in data
    assert "total_results" in data

    # Verify applicable_sions structure
    assert isinstance(data["applicable_sions"], list)
    if data["applicable_sions"]:
        sion = data["applicable_sions"][0]
        assert "sion_id" in sion
        assert "sion_code" in sion
        assert "status" in sion
        assert "rules_executed" in sion
        assert "write_results" in sion

    # Verify total_results structure
    assert "sions_processed" in data["total_results"]
    assert "sions_executed" in data["total_results"]
    assert "total_lines_written" in data["total_results"]


@pytest.mark.skip(reason="plan-licenses endpoint removed in Phase 2D.6 consolidation")
def test_plan_licenses_response_structure(setup_planning_env):
    """Test the exact response structure of plan-licenses endpoint (DEPRECATED)."""
    env = setup_planning_env
    license_obj = _make_test_license(
        env["company"], "TEST-BULK-RESPONSE", sion=env["sions"]["E1"]
    )
    _add_import_items_to_license(
        license_obj, "080211", "Almond", "kg", Decimal("100")
    )

    response = env["client"].post(
        "/api/sion-planning-rules/plan-licenses/",
        {"license_ids": [license_obj.pk], "mode": "NEW"},
        format="json",
    )

    assert response.status_code == 200
    data = response.data

    # Verify top-level structure
    assert "mode" in data
    assert "licenses_processed" in data
    assert "summary" in data

    # Verify licenses_processed structure
    assert isinstance(data["licenses_processed"], list)
    if data["licenses_processed"]:
        lic = data["licenses_processed"][0]
        assert "license_id" in lic
        assert "license_number" in lic
        assert "applicable_sions" in lic
        assert "total_lines_written" in lic

    # Verify summary structure
    assert "total_licenses" in data["summary"]
    assert "total_sions" in data["summary"]
    assert "total_lines_written" in data["summary"]
    assert "sion_execution_log" in data["summary"]
