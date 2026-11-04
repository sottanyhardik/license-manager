"""
Regression: GET /api/license-item-plans/planning-norms/ crashed for any licence
whose export manifest carries a SION with planning rules.

Defect: canonical_planning_service.planning_sion_snapshot gated on a
``planner_factory`` module (imported via a string-built name).  That module was
deleted with the per-norm auto-plan engines (git a82df2b9), so every reachable
SION path raised ModuleNotFoundError.  The pre-existing read-only test passed
only because its licence had no SION, so the crashing branch never ran.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    SionPlanningRule,
)

User = get_user_model()
ENDPOINT = "/api/license-item-plans/planning-norms/"


@pytest.fixture
def planning_client(db):
    user = User.objects.create_user(
        username="planning-norms-tester",
        email="planning-norms-tester@example.com",
        password="TestP@ss123",
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def e1_licence(db):
    """A licence whose export manifest declares an E1 SION, with one import item."""
    company = CompanyModel.objects.create(iec="PLANNORM01", name="Planning Norms Co")
    head = HeadSIONNormsModel.objects.create(name="Planning Norms Head")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-NORMS-LIC",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, description="Export E1", norm_class=sion, cif_fc=Decimal("1000"),
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Relevant Vegetable Oil",
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        available_value=Decimal("100000.00"), condition_type="",
    )
    return license_obj, sion


def _add_active_rule(sion):
    return SionPlanningRule.objects.create(
        sion=sion, name="Vegetable Oil", unit="kg", max_unit_price=Decimal("5.00"),
        priority=1, is_active=True,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "1507"},
    )


@pytest.mark.django_db
class TestPlanningNormsSnapshot:
    def test_explicit_sion_with_active_rules_returns_canonical_snapshot(self, planning_client, e1_licence):
        license_obj, sion = e1_licence
        _add_active_rule(sion)

        response = planning_client.get(
            ENDPOINT, {"license_ids": str(license_obj.pk), "sion_id": str(sion.pk)},
        )

        assert response.status_code == 200, response.content
        assert response.data["norm_class"] == "E1"
        assert response.data["license_count"] == 1

    def test_applicable_sions_path_includes_sion_with_active_rules(self, planning_client, e1_licence):
        """No sion_id: the applicable-SION branch must return the E1 snapshot,
        not crash (it previously raised ModuleNotFoundError)."""
        license_obj, sion = e1_licence
        _add_active_rule(sion)

        response = planning_client.get(ENDPOINT, {"license_ids": str(license_obj.pk)})

        assert response.status_code == 200, response.content
        assert [norm["sion_id"] for norm in response.data["norms"]] == [sion.pk]
        assert response.data["summary"]["applicable_norms"] == 1

    def test_applicable_sions_path_skips_sion_without_rules(self, planning_client, e1_licence):
        license_obj, _sion = e1_licence

        response = planning_client.get(ENDPOINT, {"license_ids": str(license_obj.pk)})

        assert response.status_code == 200, response.content
        assert response.data["norms"] == []

    def test_explicit_sion_without_active_rules_is_a_client_error(self, planning_client, e1_licence):
        license_obj, sion = e1_licence

        response = planning_client.get(
            ENDPOINT, {"license_ids": str(license_obj.pk), "sion_id": str(sion.pk)},
        )

        assert response.status_code == 400, response.content
        assert "No active planning rules" in str(response.data)
