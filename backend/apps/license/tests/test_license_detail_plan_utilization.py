"""
Smoke test for the licence-detail endpoint's additive `plan_utilization` key
(see `apps.license.views.license.LicenseDetailsViewSet.retrieve` and
`apps.license.services.plan_utilization.plan_utilization_rows`).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, PortModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)

User = get_user_model()


def _client_for_user(user):
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def viewer(db):
    user = User.objects.create_user(
        username="license-detail-viewer",
        email="license-detail-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    user.groups.add(group)
    return user


@pytest.fixture
def license_with_split_serials(db):
    company = CompanyModel.objects.create(iec="5234567890", name="Detail Exporter")
    port = PortModel.objects.create(code="INDET1", name="Detail Port")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="LIC-DETAIL-PU-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )
    for serial in (23, 3, 13):
        LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=serial,
            description="Refined Cane Sugar",
            quantity=Decimal("10.000"),
            available_quantity=Decimal("10.000"),
        )
    LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=5,
        description="Raw Sugar",
        quantity=Decimal("4.000"),
        available_quantity=Decimal("4.000"),
    )
    return license_obj


@pytest.mark.django_db
def test_license_detail_adds_grouped_plan_utilization_without_changing_import_license(
    viewer, license_with_split_serials,
):
    client = _client_for_user(viewer)

    response = client.get(reverse("license:licenses-detail", args=[license_with_split_serials.pk]))

    assert response.status_code == status.HTTP_200_OK
    data = response.data

    # Existing raw, ungrouped shape is untouched — still one entry per S.No.
    assert len(data["import_license"]) == 4

    # New grouped view: Refined Cane Sugar's 3 S.No rows collapse into one.
    util_rows = data["plan_utilization"]
    assert len(util_rows) == 2
    sugar_row = next(r for r in util_rows if r["description"] == "Refined Cane Sugar")
    assert sugar_row["serials"] == [3, 13, 23]
    assert sugar_row["available_quantity"] == "30.000"
    assert sugar_row["has_plan"] is False


@pytest.mark.django_db
def test_operational_reconciliation_excludes_superseded_plan_rows(
    viewer, license_with_split_serials,
):
    """Historical replaced plans must not create a false CIF overdraw."""
    license_obj = license_with_split_serials
    source = license_obj.import_license.order_by("pk").first()
    # The authorised CIF is the import item's CIF: the canonical balance reads it, so the planning balance does too.
    source.cif_fc = Decimal("100.00")
    source.save(update_fields=["cif_fc"])
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100.00"))
    active = LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=source,
        planned_quantity=Decimal("5.000"),
        unit_price=Decimal("1.00"),
        planned_cif_fc=Decimal("5.00"),
    )
    stale = LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=source,
        planned_quantity=Decimal("100.000"),
        unit_price=Decimal("1.00"),
        planned_cif_fc=Decimal("100.00"),
    )
    stale.is_active = False
    stale.save(update_fields=("is_active",))

    response = _client_for_user(viewer).get(
        reverse("license:licenses-detail", args=[license_obj.pk]),
    )

    assert response.status_code == status.HTTP_200_OK
    reconciliation = response.data["operational_reconciliation"]
    assert reconciliation["new_planned_cif"] == "5.00"
    assert reconciliation["total_accounted_cif"] == "5.00"
    assert reconciliation["overdrawn_cif"] == "0"
    assert active.is_active is True


def test_planning_balance_is_the_canonical_balance_less_only_new_planned_cif(viewer, license_with_split_serials):
    """Planning shows the canonical licence balance and deducts only new planned CIF: never negatives hidden, never double counted."""
    license_obj = license_with_split_serials
    source = license_obj.import_license.order_by("pk").first()
    source.cif_fc = Decimal("100.00")
    source.save(update_fields=["cif_fc"])
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("100.00"))
    LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=source,
        planned_quantity=Decimal("120.000"),
        unit_price=Decimal("1.00"),
        planned_cif_fc=Decimal("120.00"),
    )

    response = _client_for_user(viewer).get(reverse("license:licenses-detail", args=[license_obj.pk]))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["planning_balance_cif"]["raw_balance_cif"] == "100.00"
    reconciliation = response.data["operational_reconciliation"]
    assert reconciliation["cif_balance_basis"] == "CANONICAL_AVAILABLE"
    assert reconciliation["actual_balance_cif"] == "100.00"
    # Over-planned by 20: the negative is visible, not floored to zero.
    assert reconciliation["final_balance_cif"] == "-20.00"
    assert reconciliation["overdrawn_cif"] == "20.00"
