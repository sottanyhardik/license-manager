"""Synchronous Auto Plan regression coverage, including the 430-shaped CIF cap."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel
from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, SionPlanningRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def force_client_and_license():
    company = CompanyModel.objects.create(iec="FORCEPL01", name="Force Plan Test")
    user = get_user_model().objects.create_user(username="force-plan-user")
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user)
    licence = LicenseDetailsModel.objects.create(
        exporter=company, license_number="FORCE-PLAN-430-FIXTURE",
        license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
    )
    return client, licence


def _individual_cif_world(licence, *, override):
    head = HeadSIONNormsModel.objects.create(name="Individual CIF Auto Plan")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="TEST-430", is_active=True)
    target = ItemNameModel.objects.create(name="Dietary Fibre planned target", sion_norm_class=sion)
    SionPlanningRule.objects.create(
        sion=sion, name="Dietary Fibre", import_item=target, strategy="STANDARD",
        priority=1, max_unit_price=Decimal("1.00"), unit="kg", is_active=True,
        expression={"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "Dietary Fibre"},
    )
    licence.individual_item_cif_override = override
    licence.save(update_fields=["individual_item_cif_override"])
    LicenseExportItemModel.objects.create(license=licence, norm_class=sion, cif_fc=Decimal("100.00"))
    return LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, description="Dietary Fibre", unit="kg",
        quantity=Decimal("4080.880"), available_quantity=Decimal("4080.880"), cif_fc=Decimal("1.00"),
    )


@pytest.mark.parametrize("override", [None, False])
def test_null_and_false_use_the_existing_legacy_worker_snapshot(force_client_and_license, override):
    _client, licence = force_client_and_license
    _individual_cif_world(licence, override=override)
    from apps.license.services.sion_planning_execution import SionPlanningExecutionService
    with patch("apps.license.services.balance_snapshot.get_snapshot_bulk") as snapshot:
        result = SionPlanningExecutionService.plan_sion(
            LicenseExportItemModel.objects.get(license=licence).norm_class,
            license_ids=[licence.pk], mode="ALL", force_plan=True,
        )
    snapshot.assert_not_called()
    assert result["write_results"]
