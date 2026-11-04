"""
Entitlement ceiling boundaries for allocation (licence-wide CIF).

Exact-equal succeeds; one paisa over is rejected with the requested and available
amounts; a request that mixes a valid and an invalid line persists nothing.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def client(db):
    user = User.objects.create_user(username="ceiling-boundary", password="test-pass-123")
    user.groups.add(Group.objects.get_or_create(name="ALLOTMENT_MANAGER")[0])
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return api


def _world(balance="100.00"):
    company = CompanyModel.objects.create(iec="CEILBOUND1", name="Ceiling Boundary Co")
    licence = LicenseDetailsModel.objects.create(
        license_number="CEIL-LIC-1",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal(balance))
    rows = [
        LicenseImportItemsModel.objects.create(
            license=licence, serial_number=index, description=f"Row {index}",
            quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
            available_value=Decimal("100.00"), condition_type="",
        )
        for index in (1, 2)
    ]
    allotment = AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000.00"))
    return allotment, rows


def _post(client, allotment, lines):
    return client.post(
        f"/api/allotment-actions/{allotment.id}/allocate-items/",
        {"allocations": lines},
        format="json",
    )


def _line(item, cif):
    return {"item_id": item.pk, "qty": "1", "cif_fc": cif}


def test_allocation_exactly_equal_to_available_cif_is_accepted(client):
    allotment, (row, _other) = _world("100.00")

    response = _post(client, allotment, [_line(row, "100.00")])

    assert response.status_code in (200, 201), response.data
    assert AllotmentItems.objects.filter(allotment=allotment).get().cif_fc == Decimal("100.00")


def test_allocation_one_paisa_over_available_cif_is_rejected_with_amounts(client):
    allotment, (row, _other) = _world("100.00")

    response = _post(client, allotment, [_line(row, "100.01")])

    assert response.status_code >= 400 or response.data.get("success") == 0, response.data
    errors = response.data.get("errors", [])
    assert errors and errors[0]["code"] in ("ALLOTMENT_CIF_EXCEEDS_ACTUAL", "INSUFFICIENT_AVAILABLE_CIF"), response.data
    assert "Available: 100.00" in errors[0]["error"] and "Requested: 100.01" in errors[0]["error"]
    assert not AllotmentItems.objects.filter(allotment=allotment).exists()


def test_mixed_request_with_one_invalid_line_persists_nothing(client):
    allotment, (valid, invalid) = _world("100.00")

    response = _post(client, allotment, [_line(valid, "40.00"), _line(invalid, "900.00")])

    assert not AllotmentItems.objects.filter(allotment=allotment).exists(), response.data
    assert response.data.get("success") == 0 or response.status_code >= 400, response.data


def test_two_valid_lines_together_cannot_exceed_the_ceiling(client):
    allotment, (first, second) = _world("100.00")

    response = _post(client, allotment, [_line(first, "60.00"), _line(second, "60.00")])

    total = sum((item.cif_fc for item in AllotmentItems.objects.filter(allotment=allotment)), Decimal("0"))
    assert total <= Decimal("100.00"), response.data
