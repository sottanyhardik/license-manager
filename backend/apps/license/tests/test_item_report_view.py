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
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan


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


@pytest.mark.django_db
def test_item_report_excel_export_renders_planning_split_sub_rows(
    report_viewer_client, item_report_masters
):
    """A manually-planned, multi-split import item must render one indented
    sub-row per split (Planning Item Name / Unit Price / Planned Qty /
    Planned CIF / "Split N" badge) in the Excel export — the same per-split
    breakdown license_balance_excel.py renders, sourced from the same
    plan_map_for_import_items() map (no second query / divergent source)."""
    from io import BytesIO

    from openpyxl import load_workbook

    lic = _make_license("ITEM-REPORT-SPLIT", item_report_masters["parle"])
    item = _make_import_item(
        lic,
        item_report_masters["hs_code"],
        available_value=Decimal("500.00"),
        item_names=[item_report_masters["wheat"]],
    )
    # Two manual plan lines splitting this import item across two planning
    # item names — mirrors how milk gets split into WPC / SWP in production.
    LicenseItemPlan.objects.create(
        license=lic,
        import_item=item,
        item_name=item_report_masters["wheat"],
        planned_quantity=Decimal("20.000"),
        unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("100.00"),
    )
    LicenseItemPlan.objects.create(
        license=lic,
        import_item=item,
        item_name=item_report_masters["milk"],
        planned_quantity=Decimal("10.000"),
        unit_price=Decimal("7.50"),
        planned_cif_fc=Decimal("75.00"),
    )

    response = report_viewer_client.get(REPORT_URL, {"min_balance": 0, "format": "excel"})
    assert response.status_code == 200, getattr(response, "data", response.content[:300])

    workbook = load_workbook(BytesIO(response.content), data_only=True)
    assert "Not Restricted" in workbook.sheetnames
    ws = workbook["Not Restricted"]

    # Row 2 = the import item's own row; rows 3-4 = one sub-row per split.
    item_name_col, price_col, badge_col, qty_col, cif_col = 11, 10, 8, 18, 19
    split_row_1 = [ws.cell(row=3, column=c).value for c in
                    (badge_col, price_col, item_name_col, qty_col, cif_col)]
    split_row_2 = [ws.cell(row=4, column=c).value for c in
                    (badge_col, price_col, item_name_col, qty_col, cif_col)]

    assert split_row_1 == [
        "Split 1", "@ $5.00/unit", f"  └ {item_report_masters['wheat'].name}", 20.0, 100.0,
    ]
    assert split_row_2 == [
        "Split 2", "@ $7.50/unit", f"  └ {item_report_masters['milk'].name}", 10.0, 75.0,
    ]

    # The item's own row (row 2) keeps the aggregated Plan Qty / Plan CIF
    # totals across both splits — the per-split rows are additive detail,
    # not a replacement of the existing summary values.
    assert ws.cell(row=2, column=qty_col).value == pytest.approx(30.0)
    assert ws.cell(row=2, column=cif_col).value == pytest.approx(175.0)


@pytest.mark.django_db
def test_item_report_excel_export_merges_shared_description_rows(
    report_viewer_client, item_report_masters
):
    """
    Import items that share a description (the same `plan_group_key` group
    `plan_utilization_rows()` uses elsewhere) collapse into ONE Excel row
    per licence, with the Serial Number cell listing every merged serial
    and the split sub-rows carrying the UNION of every member's splits —
    not just the representative (lowest-serial) member's.

    The JSON `items` list is untouched (still one row per raw import item);
    only the Excel writer merges.
    """
    from io import BytesIO

    from openpyxl import load_workbook

    lic = _make_license("ITEM-REPORT-MERGE", item_report_masters["parle"])
    item_23 = _make_import_item(
        lic, item_report_masters["hs_code"], serial=23,
        available_value=Decimal("200.00"), available_quantity=Decimal("20.000"),
    )
    item_23.description = "Refined Cane Sugar"
    item_23.save(update_fields=["description"])
    item_3 = _make_import_item(
        lic, item_report_masters["hs_code"], serial=3,
        available_value=Decimal("300.00"), available_quantity=Decimal("30.000"),
    )
    item_3.description = "refined cane sugar"
    item_3.save(update_fields=["description"])
    item_13 = _make_import_item(
        lic, item_report_masters["hs_code"], serial=13,
        available_value=Decimal("50.00"), available_quantity=Decimal("5.000"),
    )
    item_13.description = " REFINED CANE SUGAR "
    item_13.save(update_fields=["description"])

    # Manual plan saved against the group's representative (lowest serial —
    # item_3), the real convention `bulk_upsert`/`PlanningEditor.tsx` use.
    LicenseItemPlan.objects.create(
        license=lic, import_item=item_3, item_name=item_report_masters["wheat"],
        planned_quantity=Decimal("15.000"), unit_price=Decimal("2.00"),
        planned_cif_fc=Decimal("30.00"),
    )

    response = report_viewer_client.get(REPORT_URL, {"min_balance": 0, "format": "excel"})
    assert response.status_code == 200, getattr(response, "data", response.content[:300])

    # The JSON path (unaffected) still returns 3 raw rows.
    json_response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    assert len(json_response.json()["items"]) == 3

    workbook = load_workbook(BytesIO(response.content), data_only=True)
    ws = workbook["Not Restricted"]

    serial_col, hsn_col, desc_col, avail_qty_col = 7, 9, 10, 12
    item_name_col, price_col, badge_col, qty_col, cif_col = 11, 10, 8, 18, 19

    # One merged row (not 3) for the group; comma-joined, ascending serials.
    assert ws.cell(row=2, column=serial_col).value == "3, 13, 23"
    assert ws.cell(row=2, column=desc_col).value == "refined cane sugar"
    assert ws.cell(row=2, column=hsn_col).value == item_report_masters["hs_code"].hs_code
    # Available Quantity summed across all 3 merged serials.
    assert ws.cell(row=2, column=avail_qty_col).value == pytest.approx(55.0)
    # Plan Qty/CIF aggregated across the group (only the representative had
    # a LicenseItemPlan row; the merge must not lose or double-count it).
    assert ws.cell(row=2, column=qty_col).value == pytest.approx(15.0)
    assert ws.cell(row=2, column=cif_col).value == pytest.approx(30.0)

    # Split sub-row (row 3) reflects the group's unioned splits.
    split_row = [ws.cell(row=3, column=c).value for c in
                 (badge_col, price_col, item_name_col, qty_col, cif_col)]
    assert split_row == [
        "Split 1", "@ $2.00/unit", f"  └ {item_report_masters['wheat'].name}", 15.0, 30.0,
    ]

    # No leftover rows for the other 2 merged serials.
    assert ws.cell(row=4, column=serial_col).value is None
