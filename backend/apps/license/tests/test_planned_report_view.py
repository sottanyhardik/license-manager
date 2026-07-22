"""
Tests for the Planned Report (backend/apps/license/views/planned_report.py).

This report is rooted on LicenseItemPlan (opposite of the Item Report): only
import items with at least one plan line should appear, and the `item_names`
filter targets the plan's own item_name — not the import item's M2M tags.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan


User = get_user_model()

REPORT_URL = "/api/reports/planned-report/"
AVAILABLE_ITEMS_URL = "/api/planned-report/available-items/"


@pytest.fixture
def report_viewer_client(db):
    user = User.objects.create_user(
        username="planned-report-viewer",
        email="planned-report-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    group, _ = Group.objects.get_or_create(name="REPORT_VIEWER")
    user.groups.add(group)
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def planned_report_masters(db):
    return {
        "parle": CompanyModel.objects.create(iec="4111111111", name="Planned Report Parle"),
        "hs_code": HSCodeModel.objects.create(hs_code="19053100", product_description="Biscuits"),
        "wheat": ItemNameModel.objects.create(name="Wheat Flour - Planned Report"),
        "milk": ItemNameModel.objects.create(name="Milk Powder - Planned Report"),
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
    )
    if item_names:
        item.items.set(item_names)
    return item


@pytest.mark.django_db
def test_planned_report_only_returns_items_with_a_plan(report_viewer_client, planned_report_masters):
    lic = _make_license("PLANNED-REPORT-001", planned_report_masters["parle"])
    planned_item = _make_import_item(
        lic, planned_report_masters["hs_code"], serial=1, item_names=[planned_report_masters["wheat"]]
    )
    unplanned_item = _make_import_item(
        lic, planned_report_masters["hs_code"], serial=2, item_names=[planned_report_masters["milk"]]
    )

    LicenseItemPlan.objects.create(
        import_item=planned_item,
        item_name=planned_report_masters["wheat"],
        planned_quantity=Decimal("10.000"),
        unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("50.00"),
    )

    response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    assert response.status_code == 200
    ids = {r["id"] for r in response.json()["items"]}
    assert planned_item.id in ids
    assert unplanned_item.id not in ids


@pytest.mark.django_db
def test_planned_report_item_names_filters_by_plan_item_name_not_import_tag(
    report_viewer_client, planned_report_masters
):
    lic = _make_license("PLANNED-REPORT-002", planned_report_masters["parle"])
    # Import item is tagged with BOTH wheat and milk, but the plan line is only
    # for wheat — the filter must key off the plan, not the M2M tags.
    item = _make_import_item(
        lic,
        planned_report_masters["hs_code"],
        serial=1,
        item_names=[planned_report_masters["wheat"], planned_report_masters["milk"]],
    )
    plan = LicenseItemPlan.objects.create(
        import_item=item,
        item_name=planned_report_masters["wheat"],
        planned_quantity=Decimal("10.000"),
        unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("50.00"),
    )

    matching = report_viewer_client.get(
        REPORT_URL, {"min_balance": 0, "item_names": str(planned_report_masters["wheat"].id)}
    )
    assert [r["plan_id"] for r in matching.json()["items"]] == [plan.id]

    non_matching = report_viewer_client.get(
        REPORT_URL, {"min_balance": 0, "item_names": str(planned_report_masters["milk"].id)}
    )
    assert non_matching.json()["items"] == []


@pytest.mark.django_db
def test_planned_report_available_items_only_lists_plan_scoped_names(
    report_viewer_client, planned_report_masters
):
    lic = _make_license("PLANNED-REPORT-003", planned_report_masters["parle"])
    planned_item = _make_import_item(
        lic, planned_report_masters["hs_code"], serial=1, item_names=[planned_report_masters["wheat"]]
    )
    _make_import_item(
        lic, planned_report_masters["hs_code"], serial=2, item_names=[planned_report_masters["milk"]]
    )  # no plan for this one

    LicenseItemPlan.objects.create(
        import_item=planned_item,
        item_name=planned_report_masters["wheat"],
        planned_quantity=Decimal("10.000"),
        unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("50.00"),
    )

    response = report_viewer_client.get(AVAILABLE_ITEMS_URL)
    assert response.status_code == 200
    names = {row["name"] for row in response.json()}
    assert planned_report_masters["wheat"].name in names
    assert planned_report_masters["milk"].name not in names
