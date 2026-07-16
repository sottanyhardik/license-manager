from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.core.models import (
    CompanyModel,
    HeadSIONNormsModel,
    HSCodeModel,
    NotificationNumber,
    PurchaseStatus,
    SchemeCode,
    SionNormClassModel,
)
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel


User = get_user_model()


@pytest.fixture
def license_viewer_client(db):
    user = User.objects.create_user(
        username="license-report-viewer",
        email="license-report-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def report_masters(db):
    head_norm = HeadSIONNormsModel.objects.create(name="E Norms")
    return {
        "parle": CompanyModel.objects.create(iec="1111111111", name="Parle Products Pvt Ltd"),
        "other": CompanyModel.objects.create(iec="2222222222", name="Other Foods Pvt Ltd"),
        "notification": NotificationNumber.objects.create(code="N24", label="Notification 2024"),
        "scheme": SchemeCode.objects.create(code="DFIA", label="DFIA"),
        "purchase_status": PurchaseStatus.objects.create(code="GE", label="GE Purchase"),
        "hs_code": HSCodeModel.objects.create(hs_code="19053100", product_description="Biscuits"),
        "norm_class": SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E1"),
    }


def _create_report_license(license_number, exporter, masters, *, expired=False, balance=Decimal("250.00")):
    license_obj = LicenseDetailsModel.objects.create(
        license_number=license_number,
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30) if not expired else date.today() - timedelta(days=1),
        exporter=exporter,
        notification_number=masters["notification"],
        scheme_code=masters["scheme"],
        purchase_status=masters["purchase_status"],
        file_number=f"FILE-{license_number}",
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Export Biscuits",
        norm_class=masters["norm_class"],
        cif_fc=Decimal("100.25"),
        cif_inr=Decimal("8400.00"),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Export Biscuits 2",
        norm_class=masters["norm_class"],
        cif_fc=Decimal("50.75"),
        cif_inr=Decimal("4200.00"),
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Import Sugar",
        hs_code=masters["hs_code"],
        quantity=Decimal("10.000"),
        cif_fc=Decimal("15.50"),
        cif_inr=Decimal("1300.00"),
    )
    license_obj.balance.balance_cif = balance
    license_obj.balance.save(update_fields=["balance_cif"])
    return license_obj


@pytest.mark.django_db
def test_parle_license_report_returns_grouped_json(license_viewer_client, report_masters):
    _create_report_license("PARLE-REPORT-001", report_masters["parle"], report_masters)
    _create_report_license("OTHER-REPORT-001", report_masters["other"], report_masters)

    response = license_viewer_client.get(reverse("license:licenses-parle-license-report"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["summary"]["total_licenses"] == 1
    assert response.data["summary"]["grand_total_cif"] == 151.0
    group = response.data["groups"][0]
    assert group["notification_number"] == "N24"
    license_data = group["licenses"][0]
    assert license_data["license_number"] == "PARLE-REPORT-001"
    assert license_data["purchase_status"] == "GE"
    assert license_data["purchase_status_label"] == "GE Purchase"
    assert license_data["export_items"][0]["norm_class"] == "E1"
    assert license_data["import_items"][0]["hs_code"] == "19053100"


@pytest.mark.django_db
def test_parle_license_report_validates_query_params(license_viewer_client):
    response = license_viewer_client.get(
        reverse("license:licenses-parle-license-report"),
        {"exporter": "not-an-id", "is_expired": "definitely"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "exporter" in response.data
    assert "is_expired" in response.data


@pytest.mark.django_db
def test_parle_license_report_filters_boolean_params(license_viewer_client, report_masters):
    active = _create_report_license(
        "PARLE-ACTIVE-001",
        report_masters["parle"],
        report_masters,
        expired=False,
        balance=Decimal("250.00"),
    )
    _create_report_license(
        "PARLE-EXPIRED-001",
        report_masters["parle"],
        report_masters,
        expired=True,
        balance=Decimal("100.00"),
    )

    response = license_viewer_client.get(
        reverse("license:licenses-parle-license-report"),
        {"is_expired": "false", "is_null": "false", "exporter": report_masters["parle"].id},
    )

    assert response.status_code == status.HTTP_200_OK
    licenses = response.data["groups"][0]["licenses"]
    assert [row["id"] for row in licenses] == [active.id]
