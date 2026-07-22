"""
Tests for the Item Report (backend/apps/license/views/item_report.py).

Regression coverage for the 962f17af revert: the report must be rooted on
LicenseImportItemsModel (every import item, plan or no plan), and the
`item_names` filter must match the import item's own M2M tag — not a
LicenseItemPlan row.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel


User = get_user_model()

REPORT_URL = "/api/reports/item-report/"
AVAILABLE_ITEMS_URL = "/api/item-report/available-items/"


@pytest.fixture
def report_viewer_client(db):
    user = User.objects.create_user(
        username="item-report-viewer",
        email="item-report-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="REPORT_VIEWER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def item_report_masters(db):
    return {
        "parle": CompanyModel.objects.create(iec="3111111111", name="Item Report Parle"),
        "other": CompanyModel.objects.create(iec="3222222222", name="Item Report Other"),
        "hs_code": HSCodeModel.objects.create(hs_code="19053100", product_description="Biscuits"),
        "wheat": ItemNameModel.objects.create(name="Wheat Flour - Item Report"),
        "milk": ItemNameModel.objects.create(name="Milk Powder - Item Report"),
    }


def _make_license(number, exporter, *, expiry_days=30):
    return LicenseDetailsModel.objects.create(
        license_number=number,
        license_date=date.today() - timedelta(days=60),
        license_expiry_date=date.today() + timedelta(days=expiry_days),
        exporter=exporter,
    )


def _make_import_item(
    license_obj,
    hs_code,
    *,
    serial=1,
    available_value=Decimal("500.00"),
    available_quantity=Decimal("50.000"),
    condition_type="",
    item_names=None,
):
    item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=serial,
        description=f"Import item {serial}",
        hs_code=hs_code,
        quantity=Decimal("100.000"),
        available_quantity=available_quantity,
        available_value=available_value,
        condition_type=condition_type,
    )
    if item_names:
        item.items.set(item_names)
    return item


@pytest.mark.django_db
def test_item_report_includes_import_item_with_no_plan_and_filters_by_own_tag(
    report_viewer_client, item_report_masters
):
    license_obj = _make_license("ITEM-REPORT-001", item_report_masters["parle"])
    item = _make_import_item(
        license_obj,
        item_report_masters["hs_code"],
        item_names=[item_report_masters["wheat"]],
    )
    # Deliberately no LicenseItemPlan row for this item.

    response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()["items"]}

    assert item.id in rows, "import item with no plan must still appear in the report"
    row = rows[item.id]
    assert row["planned_quantity"] == 0
    assert row["planned_cif"] == 0
    assert row["plan_source"] == ""
    assert row["planned_splits"] == []
    assert row["item_names"] == [
        {"id": item_report_masters["wheat"].id, "name": item_report_masters["wheat"].name}
    ]

    # item_names filter matches the import item's own M2M tag (not a plan).
    matching = report_viewer_client.get(
        REPORT_URL, {"min_balance": 0, "item_names": str(item_report_masters["wheat"].id)}
    )
    assert [r["id"] for r in matching.json()["items"]] == [item.id]

    non_matching = report_viewer_client.get(
        REPORT_URL, {"min_balance": 0, "item_names": str(item_report_masters["milk"].id)}
    )
    assert non_matching.json()["items"] == []


@pytest.mark.django_db
def test_item_report_filters_min_balance_and_company_ids(report_viewer_client, item_report_masters):
    lic_a = _make_license("ITEM-REPORT-A", item_report_masters["parle"])
    lic_b = _make_license("ITEM-REPORT-B", item_report_masters["other"])
    item_a = _make_import_item(lic_a, item_report_masters["hs_code"], serial=1, available_value=Decimal("500.00"))
    item_b = _make_import_item(lic_b, item_report_masters["hs_code"], serial=1, available_value=Decimal("50.00"))

    # Default min_balance=200 excludes item_b (available_value=50).
    response = report_viewer_client.get(REPORT_URL)
    ids = {r["id"] for r in response.json()["items"]}
    assert item_a.id in ids
    assert item_b.id not in ids

    # With min_balance=0 both appear, but company_ids narrows to Parle only.
    response = report_viewer_client.get(
        REPORT_URL, {"min_balance": 0, "company_ids": str(item_report_masters["parle"].id)}
    )
    ids = {r["id"] for r in response.json()["items"]}
    assert ids == {item_a.id}


@pytest.mark.django_db
def test_item_report_filters_is_restricted_combined_with_item_names(report_viewer_client, item_report_masters):
    lic = _make_license("ITEM-REPORT-RESTRICT", item_report_masters["parle"])
    restricted = _make_import_item(
        lic,
        item_report_masters["hs_code"],
        serial=1,
        condition_type="AU",
        item_names=[item_report_masters["wheat"]],
    )
    not_restricted = _make_import_item(
        lic,
        item_report_masters["hs_code"],
        serial=2,
        item_names=[item_report_masters["wheat"]],
    )

    response = report_viewer_client.get(
        REPORT_URL,
        {
            "min_balance": 0,
            "is_restricted": "true",
            "item_names": str(item_report_masters["wheat"].id),
        },
    )
    ids = [r["id"] for r in response.json()["items"]]
    assert ids == [restricted.id]
    assert not_restricted.id not in ids


@pytest.mark.django_db
def test_item_report_available_items_includes_name_with_no_plan(report_viewer_client, item_report_masters):
    lic = _make_license("ITEM-REPORT-AVAIL", item_report_masters["parle"])
    _make_import_item(
        lic,
        item_report_masters["hs_code"],
        available_value=Decimal("500.00"),
        item_names=[item_report_masters["wheat"]],
    )
    # No LicenseItemPlan created anywhere for this item name.

    response = report_viewer_client.get(AVAILABLE_ITEMS_URL)
    assert response.status_code == 200
    names = {row["name"] for row in response.json()}
    assert item_report_masters["wheat"].name in names
