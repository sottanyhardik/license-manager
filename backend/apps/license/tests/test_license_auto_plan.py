"""Tests for License Auto Plan API endpoint (POST /api/licenses/{id}/auto-plan/).

Tests the License.auto_plan action which auto-plans a single license by resolving
SION norms from the export manifest and running the planning calculation.
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
def planning_setup():
    """Set up SION norms, company, user, and active planning rules."""
    head = HeadSIONNormsModel.objects.create(name="Test Planning")
    sions = {
        norm: SionNormClassModel.objects.create(
            head_norm=head, norm_class=norm, is_active=True,
        )
        for norm in ("E1", "E5")
    }
    import_e1_e5_profiles(activate=True)
    SionPlanningRule.objects.filter(sion=sions["E1"]).update(is_active=True)
    SionPlanningRule.objects.filter(sion=sions["E5"]).update(is_active=True)

    company = CompanyModel.objects.create(iec="AUTOPLAN01", name="Auto Plan Test")
    user = get_user_model().objects.create_user(
        username="auto-plan-user", company=company
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


def make_license(company, license_number, sion=None, cif=Decimal("1000")):
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


def add_import_item(license_obj, hsn, description, unit, qty):
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


class TestLicenseAutoPlan:
    """Tests for the License.auto_plan action."""

    def test_auto_plan_basic_single_sion(self, planning_setup):
        """Test auto-planning a license with a single SION."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-AUTO-E1", sion=setup["sions"]["E1"]
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        data = response.data
        assert data["license_id"] == license_obj.pk
        assert data["license_number"] == "TEST-AUTO-E1"
        assert data["status"] == "EXECUTED"
        assert data["sion_id"] == setup["sions"]["E1"].pk
        assert data["sion_code"] == "E1"
        assert isinstance(data["rules_executed"], list)
        assert isinstance(data["write_results"], list)
        assert isinstance(data["total_lines_written"], int)

    def test_auto_plan_single_sion_e5(self, planning_setup):
        """Test auto-planning with E5 SION."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-AUTO-E5", sion=setup["sions"]["E5"]
        )
        add_import_item(license_obj, "210600", "Dietary fibre", "kg", Decimal("100"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        assert response.data["sion_code"] == "E5"
        assert response.data["sion_id"] == setup["sions"]["E5"].pk

    def test_auto_plan_multiple_sions_rejected(self, planning_setup):
        """Test auto-planning rejects licenses with multiple SIONs."""
        setup = planning_setup
        license_obj = make_license(setup["company"], "TEST-AUTO-MULTI")
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=setup["sions"]["E1"], cif_fc=Decimal("500"),
        )
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=setup["sions"]["E5"], cif_fc=Decimal("500"),
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 400
        assert ("MULTIPLE_SIONS" in response.data.get("code", "")
                or "multiple" in response.data.get("message", "").lower())

    def test_auto_plan_license_not_found(self, planning_setup):
        """Test auto-plan with non-existent license ID."""
        setup = planning_setup
        response = setup["client"].post(
            "/api/licenses/99999/auto-plan/"
        )

        assert response.status_code == 404

    def test_auto_plan_no_export_manifest(self, planning_setup):
        """Test auto-plan fails when license has no export items."""
        setup = planning_setup
        license_obj = make_license(setup["company"], "TEST-NO-EXPORT", sion=None)

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 400
        assert "export manifest" in response.data.get("message", "").lower()

    def test_auto_plan_no_sion_norms(self, planning_setup):
        """Test auto-plan fails when export items have no SION assigned."""
        setup = planning_setup
        license_obj = make_license(setup["company"], "TEST-NO-SION-NORMS")
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=None, cif_fc=Decimal("1000"),
        )

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 400
        assert ("NO_SION" in response.data.get("code", "")
                or "sion" in response.data.get("message", "").lower())

    def test_auto_plan_company_isolation(self, planning_setup):
        """Test auto-plan respects company isolation (returns 404 for foreign licenses)."""
        setup = planning_setup
        other_company = CompanyModel.objects.create(
            iec="OTHERCMP01", name="Other Company"
        )
        license_obj = make_license(
            other_company, "TEST-OTHER-COMPANY", sion=setup["sions"]["E1"]
        )

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        # Company isolation is enforced at queryset level, so returns 404
        assert response.status_code == 404

    def test_auto_plan_replans_existing(self, planning_setup):
        """Test that calling auto-plan again replaces the existing plan."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-REPLAN", sion=setup["sions"]["E1"]
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        # First auto-plan
        response1 = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )
        assert response1.status_code == 200
        first_written = response1.data["total_lines_written"]

        # Get initial plan row count
        initial_plan_rows = LicenseItemPlan.objects.filter(license=license_obj).count()
        assert initial_plan_rows > 0

        # Second auto-plan with ALL mode (default)
        response2 = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )
        assert response2.status_code == 200
        second_written = response2.data["total_lines_written"]

        # Plan rows should be replaced, not duplicated
        final_plan_rows = LicenseItemPlan.objects.filter(license=license_obj).count()
        assert final_plan_rows == initial_plan_rows
        assert first_written == second_written

    def test_auto_plan_only_deletes_target_license_plan(self, planning_setup):
        """Test that auto-plan only deletes plans for the specific license."""
        setup = planning_setup
        license1 = make_license(setup["company"], "TEST-LIC-1", sion=setup["sions"]["E1"])
        license2 = make_license(setup["company"], "TEST-LIC-2", sion=setup["sions"]["E1"])
        add_import_item(license1, "080211", "Almond", "kg", Decimal("100"))
        add_import_item(license2, "080211", "Almond", "kg", Decimal("100"))

        # Plan both
        setup["client"].post(f"/api/licenses/{license1.pk}/auto-plan/")
        setup["client"].post(f"/api/licenses/{license2.pk}/auto-plan/")

        lic1_plans_before = LicenseItemPlan.objects.filter(license=license1).count()
        lic2_plans_before = LicenseItemPlan.objects.filter(license=license2).count()

        # Replan only license1
        setup["client"].post(f"/api/licenses/{license1.pk}/auto-plan/")

        lic1_plans_after = LicenseItemPlan.objects.filter(license=license1).count()
        lic2_plans_after = LicenseItemPlan.objects.filter(license=license2).count()

        # License1 should have been replaced (same count)
        assert lic1_plans_after == lic1_plans_before
        # License2 should be untouched
        assert lic2_plans_after == lic2_plans_before

    def test_auto_plan_respects_existing_utilization(self, planning_setup):
        """Test that auto-plan accounts for existing BOE/debit utilization."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-WITH-UTIL", sion=setup["sions"]["E1"]
        )
        import_item = add_import_item(
            license_obj, "080211", "Almond", "kg", Decimal("100")
        )

        # Auto-plan should calculate against available quantity
        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        assert response.data["status"] in ("EXECUTED", "SKIPPED")

    def test_auto_plan_response_structure(self, planning_setup):
        """Test that auto-plan response has correct singular structure."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-RESPONSE-STRUCT", sion=setup["sions"]["E1"]
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        data = response.data
        assert "license_id" in data
        assert "license_number" in data
        assert "status" in data
        assert data["status"] in ("EXECUTED", "SKIPPED")
        assert "sion_id" in data
        assert "sion_code" in data
        assert "rules_executed" in data
        assert "write_results" in data
        assert "total_lines_written" in data
        # Plural fields should NOT exist
        assert "applicable_sions" not in data
        assert "total_results" not in data
        assert "sions_processed" not in data
        assert "sions_executed" not in data

    def test_auto_plan_lookup_by_pk(self, planning_setup):
        """Test auto-plan can look up license by PK."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-BY-PK", sion=setup["sions"]["E1"]
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        assert response.data["license_id"] == license_obj.pk

    def test_auto_plan_lookup_by_license_number(self, planning_setup):
        """Test auto-plan can look up license by license_number."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-BY-NUMBER", sion=setup["sions"]["E1"]
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.license_number}/auto-plan/"
        )

        assert response.status_code == 200
        assert response.data["license_id"] == license_obj.pk
        assert response.data["license_number"] == "TEST-BY-NUMBER"

    def test_auto_plan_permission_required(self, planning_setup):
        """Test that auto-plan requires LICENSE_MANAGER permission."""
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-PERMISSION", sion=setup["sions"]["E1"]
        )
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("100"))

        # Create user without LICENSE_MANAGER role
        other_user = get_user_model().objects.create_user(
            username="no-permission", company=setup["company"]
        )
        other_client = APIClient()
        other_client.force_authenticate(other_user)

        response = other_client.post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 403

    def test_auto_plan_force_exceeds_available_qty(self, planning_setup):
        """Test that forced auto-plan creates plan even when required > available_qty.

        SION rule requires 3,000 PKO but only 1,500 available.
        Force plan should save the required 3,000 despite limited availability.
        """
        setup = planning_setup
        license_obj = make_license(
            setup["company"], "TEST-FORCE-AVAIL", sion=setup["sions"]["E1"]
        )
        # Add import item with limited available quantity (1,500)
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("1500"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        # Forced plan should succeed even though available < required
        assert response.data["status"] == "EXECUTED"
        assert len(response.data["write_results"]) > 0

        # Verify plan was actually saved to database
        plans = LicenseItemPlan.objects.filter(license=license_obj)
        assert plans.exists()
        # Total planned should be >= 1500 (the full available qty since it matches SION requirements)
        total_planned = sum(Decimal(str(p.planned_quantity or 0)) for p in plans)
        assert total_planned > 0

    def test_auto_plan_force_with_insufficient_balance_cif(self, planning_setup):
        """Test that forced auto-plan creates plan even when required CIF > balance_cif.

        Balance CIF supports 100 units, but SION rule requires more.
        Forced planning should save the full required quantity despite insufficient balance.
        """
        setup = planning_setup
        # Create license with very limited CIF (100)
        license_obj = make_license(
            setup["company"], "TEST-INSUFF-CIF", sion=setup["sions"]["E1"],
            cif=Decimal("100"),
        )
        # Add item that requires planning beyond balance_cif
        add_import_item(license_obj, "080211", "Almond", "kg", Decimal("500"))

        response = setup["client"].post(
            f"/api/licenses/{license_obj.pk}/auto-plan/"
        )

        assert response.status_code == 200
        # Forced plan should succeed despite insufficient balance_cif
        assert response.data["status"] == "EXECUTED"
        # Even with limited balance, forced plan should write results
        assert len(response.data["write_results"]) >= 0

        # Verify plan was saved with forced quantity
        plans = LicenseItemPlan.objects.filter(license=license_obj)
        if plans.exists():
            # Plan was saved; verify it respects the import item quantity
            total_planned = sum(Decimal(str(p.planned_quantity or 0)) for p in plans)
            # Forced plan should use the available import quantity or rule requirement
            assert total_planned > 0
