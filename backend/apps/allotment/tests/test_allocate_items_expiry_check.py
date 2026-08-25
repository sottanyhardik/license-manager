"""Regression coverage for allocating against expired licences."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel

User = get_user_model()


@pytest.fixture
def allotment_client(db):
    user = User.objects.create_user(username="expired-license-tester", password="RoleP@ssw0rd123")
    group, _ = Group.objects.get_or_create(name="ALLOTMENT_MANAGER")
    user.groups.add(group)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def test_allows_allocation_against_an_expired_license(allotment_client, db):
    company = CompanyModel.objects.create(iec="4011046335", name="Expired License Co")
    licence = LicenseDetailsModel.objects.create(
        license_number="0311046335-EXP-TEST",
        license_date=date.today() - timedelta(days=200),
        license_expiry_date=date.today() - timedelta(days=1),
        exporter=company,
    )
    item = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, description="Milk Products",
        quantity=Decimal("10000.000"), available_quantity=Decimal("9625.000"),
        available_value=Decimal("50000.00"), condition_type="",
    )
    LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("50000.00"))
    allotment = AllotmentModel.objects.create(
        company=company, required_quantity=Decimal("1000000.00"),
    )

    response = allotment_client.post(
        f"/api/allotment-actions/{allotment.id}/allocate-items/",
        {"allocations": [{
            "item_id": item.id, "qty": "100", "cif_fc": "500.00",
            "license_status": "expired",
        }]},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["success"] == 1
    assert response.data["errors"] == []
    assert AllotmentItems.objects.filter(allotment=allotment, item=item).exists()
