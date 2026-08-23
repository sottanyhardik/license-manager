"""Integration coverage for the sole supported manual-plan mutation contract.

Individual plan-line POST/PATCH endpoints are deliberately read-only: accepting
them would create a second persistence authority beside ``bulk-upsert`` and the
canonical planner. These tests exercise quantity/CIF validation, replacement,
authorization, and deletion through the supported API instead.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan

User = get_user_model()
PLANS_URL = "/api/license-item-plans/"
BULK_URL = f"{PLANS_URL}bulk-upsert/"


@pytest.fixture
def planned_license(db):
    company = CompanyModel.objects.create(iec="6234567890", name="Plan API Exporter")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PLAN-API-001", license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30), exporter=company,
    )
    LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("1000.00"))
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="Plan API Item",
        quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
    )
    return license_obj, item


@pytest.fixture
def license_manager_client(db, planned_license):
    license_obj, _ = planned_license
    user = User.objects.create_user(
        username="item-plan-api-manager", email="item-plan-api-manager@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(group)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def _bulk(client, license_obj, *lines):
    return client.post(BULK_URL, {"license": license_obj.id, "lines": [
        {
            "import_item": item.id, "item_name": None, "planned_quantity": str(qty),
            "unit_price": str(price), "planned_cif_fc": str(cif), "note": "",
        }
        for item, qty, price, cif in lines
    ]}, format="json")


@pytest.mark.django_db
def test_direct_line_writes_are_prohibited_to_preserve_one_authority(license_manager_client, planned_license):
    _, item = planned_license
    response = license_manager_client.post(PLANS_URL, {
        "import_item": item.id, "planned_quantity": "1.000", "unit_price": "1.00",
        "planned_cif_fc": "1.00",
    }, format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_bulk_exact_capacity_and_cif_persists_canonical_pair(license_manager_client, planned_license):
    license_obj, item = planned_license
    response = _bulk(license_manager_client, license_obj, (item, "100.000", "10.00", "999.99"))
    assert response.status_code == 200, response.data
    row = LicenseItemPlan.objects.get(license=license_obj)
    assert row.planned_quantity == Decimal("100.000")
    # The canonical service derives CIF from qty × price; caller-supplied CIF is not trusted.
    assert row.planned_cif_fc == Decimal("1000.00")


@pytest.mark.django_db
def test_bulk_upsert_accepts_the_item_pivot_manual_plan_payload(license_manager_client, planned_license):
    """Regression for the manual Item Pivot save payload shape.

    ``planned_cif_fc`` is display data; the canonical writer derives the
    persisted amount from quantity × unit price, while retaining the supplied
    valid item-name label.
    """
    license_obj, item = planned_license
    item.quantity = Decimal("6122.740")
    item.available_quantity = Decimal("6122.000")
    item.save(update_fields=["quantity", "available_quantity"])
    LicenseExportItemModel.objects.filter(license=license_obj).update(cif_fc=Decimal("24961.44"))
    item_name = ItemNameModel.objects.create(name="Other confectionery ingredients")

    response = license_manager_client.post(BULK_URL, {
        "license": license_obj.id,
        "lines": [{
            "import_item": item.id,
            "item_name": item_name.id,
            "planned_quantity": 6122,
            "unit_price": 2.7,
            "planned_cif_fc": 16529.4,
            "note": "",
        }],
    }, format="json")

    assert response.status_code == 200, response.data
    row = LicenseItemPlan.objects.get(license=license_obj)
    assert row.item_name_id == item_name.id
    assert row.planned_quantity == Decimal("6122.000")
    assert row.unit_price == Decimal("2.70")
    assert row.planned_cif_fc == Decimal("16529.40")


@pytest.mark.django_db
def test_bulk_upsert_returns_structured_400_for_unknown_item_name(license_manager_client, planned_license):
    license_obj, item = planned_license

    response = license_manager_client.post(BULK_URL, {
        "license": license_obj.id,
        "lines": [{
            "import_item": item.id,
            "item_name": 999999999,
            "planned_quantity": 1,
            "unit_price": 1,
            "planned_cif_fc": 1,
            "note": "",
        }],
    }, format="json")

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_INPUT"
    assert response.data["details"]["item_name_ids"] == [999999999]
    assert not LicenseItemPlan.objects.filter(license=license_obj).exists()


@pytest.mark.django_db
def test_bulk_over_capacity_returns_persisted_valid_portion_and_shortage(license_manager_client, planned_license):
    license_obj, item = planned_license
    response = _bulk(license_manager_client, license_obj, (item, "100.001", "1.00", "100.01"))
    assert response.status_code == 200, response.data
    (line,) = response.data["lines"]
    assert Decimal(str(line["planned_quantity"])) == Decimal("100.000")
    assert Decimal(str(line["capped_qty"])) == Decimal("0.001")
    assert line["was_quantity_capped"] is True


@pytest.mark.django_db
def test_bulk_cif_pool_reduces_effective_rate_without_overspending(license_manager_client, planned_license):
    license_obj, item = planned_license
    response = _bulk(license_manager_client, license_obj, (item, "100.000", "20.00", "2000.00"))
    assert response.status_code == 200, response.data
    row = LicenseItemPlan.objects.get(license=license_obj)
    assert row.planned_quantity == Decimal("100.000")
    assert row.planned_cif_fc <= Decimal("1000.00")
    assert row.planned_cif_fc == row.planned_quantity * row.unit_price


@pytest.mark.django_db
def test_bulk_replace_does_not_double_count_old_lines(license_manager_client, planned_license):
    license_obj, item = planned_license
    assert _bulk(license_manager_client, license_obj, (item, "100.000", "10.00", "1000.00")).status_code == 200
    response = _bulk(license_manager_client, license_obj, (item, "10.000", "10.00", "100.00"))
    assert response.status_code == 200, response.data
    assert list(LicenseItemPlan.objects.filter(license=license_obj).values_list(
        "planned_quantity", "planned_cif_fc",
    )) == [(Decimal("10.000"), Decimal("100.00"))]


@pytest.mark.django_db
def test_delete_frees_plan_and_next_bulk_save_recreates_it(license_manager_client, planned_license):
    license_obj, item = planned_license
    assert _bulk(license_manager_client, license_obj, (item, "100.000", "10.00", "1000.00")).status_code == 200
    row = LicenseItemPlan.objects.get(license=license_obj)
    assert license_manager_client.delete(f"{PLANS_URL}{row.pk}/").status_code == 204
    assert not LicenseItemPlan.objects.filter(license=license_obj).exists()
    assert _bulk(license_manager_client, license_obj, (item, "100.000", "10.00", "1000.00")).status_code == 200


@pytest.mark.django_db
def test_zero_balance_cannot_create_positive_cif_plan(license_manager_client, planned_license):
    license_obj, item = planned_license
    LicenseExportItemModel.objects.filter(license=license_obj).delete()
    response = _bulk(license_manager_client, license_obj, (item, "1.000", "10.00", "10.00"))
    assert response.status_code == 200, response.data
    row = LicenseItemPlan.objects.get(license=license_obj)
    assert row.planned_cif_fc == Decimal("0.00")
