"""
Architectural test: Verify /planning is the single entry point for plan writes.

This test ensures that LicenseItemPlan can ONLY be written through:
1. /api/sion-planning-rules/plan-sion/ (SION-first planning)
2. /api/sion-planning-rules/plan-license/ (license-first planning from /planning)
3. /api/license-item-plans/bulk-upsert/ (manual plan via /planning)

All other paths (direct CRUD, signals, exporters, CLI, etc.) must be read-only.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseItemPlan, SionPlanningRule, LicenseDetailsModel, LicenseImportItemsModel

User = get_user_model()


@pytest.fixture
def licensed_client(db):
    """API client with LICENSE_MANAGER role for a test license."""
    company = CompanyModel.objects.create(iec="PLANENTRY1", name="Planning Entry Test")
    license_obj = LicenseDetailsModel.objects.create(license_number="PLAN-ENTRY-TEST", exporter=company)
    LicenseImportItemsModel.objects.create(license=license_obj, serial_number=1, description="Planning test item", quantity=10, available_quantity=10)
    user = User.objects.create_user(
        username="planning-test-user",
        email="planning-test@example.com",
        password="TestP@ss123",
        company=license_obj.exporter,
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client, license_obj


@pytest.fixture
def sion_for_queue(db):
    head = HeadSIONNormsModel.objects.create(name="Planning Entry Head")
    return SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)


class TestPlanningWritePathConsolidation:
    """Verify all plan writes converge at the planning entry points."""

    def test_direct_post_to_license_item_plans_is_disabled(self, licensed_client):
        """POST /api/license-item-plans/ must raise PermissionDenied."""
        client, license_obj = licensed_client

        # Get first import item
        first_item = license_obj.import_license.first()
        assert first_item, "Test license must have import items"

        response = client.post(
            "/api/license-item-plans/",
            {
                "license": license_obj.pk,
                "import_item": first_item.pk,
                "planned_quantity": "10",
                "unit_price": "100",
            },
            format="json",
        )

        assert response.status_code == 403, (
            "Direct POST to license-item-plans should be 403 Forbidden, "
            f"got {response.status_code}: {response.data}"
        )
        assert "not allowed" in str(response.data).lower() or "disabled" in str(response.data).lower()

    def test_direct_patch_to_license_item_plans_is_disabled(self, licensed_client):
        """PATCH /api/license-item-plans/<id>/ must raise PermissionDenied."""
        client, license_obj = licensed_client

        # Create a plan line manually in the DB (bypass the API)
        first_item = license_obj.import_license.first()
        plan_line = LicenseItemPlan.objects.create(
            license=license_obj,
            import_item=first_item,
            planned_quantity=5,
            unit_price=50,
        )

        response = client.patch(
            f"/api/license-item-plans/{plan_line.pk}/",
            {"planned_quantity": "15"},
            format="json",
        )

        assert response.status_code == 403, (
            "Direct PATCH to license-item-plans should be 403 Forbidden, "
            f"got {response.status_code}: {response.data}"
        )
        assert "not allowed" in str(response.data).lower() or "disabled" in str(response.data).lower()

    def test_delete_to_license_item_plans_is_allowed(self, licensed_client):
        """DELETE /api/license-item-plans/<id>/ must be allowed (for split removal)."""
        client, license_obj = licensed_client

        first_item = license_obj.import_license.first()
        plan_line = LicenseItemPlan.objects.create(
            license=license_obj,
            import_item=first_item,
            planned_quantity=5,
            unit_price=50,
        )

        response = client.delete(f"/api/license-item-plans/{plan_line.pk}/")

        # Could be 204 No Content or 200 OK, both are acceptable
        assert response.status_code in (200, 204), (
            f"DELETE should succeed, got {response.status_code}"
        )
        assert not LicenseItemPlan.objects.filter(pk=plan_line.pk).exists()

    def test_get_license_item_plans_is_allowed(self, licensed_client):
        """GET /api/license-item-plans/ must be read-only (allowed)."""
        client, license_obj = licensed_client

        response = client.get(
            "/api/license-item-plans/",
            {"license": license_obj.pk},
        )

        assert response.status_code == 200, f"GET should succeed, got {response.status_code}"

    def test_plan_sion_endpoint_is_allowed(self, licensed_client, sion_for_queue):
        """POST /api/sion-planning-rules/plan-sion/ must be allowed."""
        client, license_obj = licensed_client
        sion = sion_for_queue

        response = client.post(
            "/api/sion-planning-rules/plan-sion/",
            {
                "sion_id": sion.id,
                "license_ids": [license_obj.pk],
                "mode": "NEW",
            },
            format="json",
        )

        assert response.status_code == 202, (
            f"plan-sion should succeed, got {response.status_code}: {response.data}"
        )

    def test_plan_license_endpoint_is_allowed(self, licensed_client):
        """POST /api/sion-planning-rules/plan-license/ must be allowed."""
        client, license_obj = licensed_client

        response = client.post(
            "/api/sion-planning-rules/plan-license/",
            {
                "license_id": license_obj.pk,
                "mode": "NEW",
            },
            format="json",
        )

        # Could be 200 if planning succeeds or error if no rules, but not 404/405
        assert response.status_code in (202, 400), (
            f"plan-license should be callable, got {response.status_code}"
        )

    def test_bulk_upsert_endpoint_is_allowed(self, licensed_client):
        """POST /api/license-item-plans/bulk-upsert/ must be allowed."""
        client, license_obj = licensed_client

        first_item = license_obj.import_license.first()
        assert first_item, "Test license must have import items"

        response = client.post(
            "/api/license-item-plans/bulk-upsert/",
            {
                "license": license_obj.pk,
                "lines": [
                    {
                        "import_item": first_item.pk,
                        "planned_quantity": "5",
                        "unit_price": "100",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 200, (
            f"bulk-upsert should succeed, got {response.status_code}: {response.data}"
        )

    def test_planning_norms_is_read_only(self, licensed_client):
        """GET /api/license-item-plans/planning-norms/ must be read-only."""
        client, license_obj = licensed_client

        response = client.get(
            "/api/license-item-plans/planning-norms/",
            {"license_ids": str(license_obj.pk)},
        )

        assert response.status_code == 200, (
            f"planning-norms GET should succeed, got {response.status_code}"
        )


class TestPlanLicensesEndpointRemoved:
    """Verify orphaned plan-licenses endpoint is gone."""

    def test_plan_licenses_endpoint_does_not_exist(self, licensed_client):
        """POST /api/sion-planning-rules/plan-licenses/ must not exist."""
        client, license_obj = licensed_client

        response = client.post(
            "/api/sion-planning-rules/plan-licenses/",
            {
                "license_ids": [license_obj.pk],
                "mode": "NEW",
            },
            format="json",
        )

        # Should be 404 Method Not Allowed or 404 Not Found
        assert response.status_code in (404, 405), (
            f"plan-licenses should not exist, got {response.status_code}: {response.data}"
        )
