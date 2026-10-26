"""Canonical XLSX contract tests for the item-pivot report.

The report has one source of truth: ``ItemPivotService.build``. The JSON
endpoint returns its ``groups`` matrix and the XLSX exporter serializes that
same matrix; these tests protect that parity without using the retired
per-norm report layout.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import (
    CompanyModel,
    HSCodeModel,
    HeadSIONNormsModel,
    ItemNameModel,
    NotificationNumber,
    PurchaseStatus,
    SchemeCode,
    SionNormClassModel,
)
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)


User = get_user_model()


@pytest.fixture
def superuser_client(db):
    user = User.objects.create_superuser(
        username="item-pivot-excel-tester",
        email="item-pivot-excel-tester@example.com",
        password="P@ssw0rd12345",
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def pivot_masters(db):
    head_norm = HeadSIONNormsModel.objects.create(name="Item Pivot Test Head Norm")
    norm_class = SionNormClassModel.objects.create(
        head_norm=head_norm, norm_class="PIVOTTEST", is_active=True,
    )
    item_name = ItemNameModel.objects.create(
        name="PIVOT TEST ITEM - PIVOTTEST",
        sion_norm_class=norm_class,
        is_active=True,
        display_order=1,
    )
    return {
        "exporter": CompanyModel.objects.create(iec="9990001111", name="Pivot Excel Exporter"),
        "notification": NotificationNumber.objects.create(code="PIVN1", label="Pivot Notification"),
        "scheme": SchemeCode.objects.create(code="PIVDFIA", label="Pivot DFIA"),
        "purchase_status": PurchaseStatus.objects.create(code="GE", label="GE Purchase"),
        "hs_code": HSCodeModel.objects.create(hs_code="99999999", product_description="Pivot Test Product"),
        "norm_class": norm_class,
        "item_name": item_name,
    }


@pytest.fixture
def pivot_license(db, pivot_masters):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PIVOT-EXCEL-001",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=pivot_masters["exporter"],
        notification_number=pivot_masters["notification"],
        scheme_code=pivot_masters["scheme"],
        purchase_status=pivot_masters["purchase_status"],
        file_number="PIVOT-FILE-001",
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Pivot export item",
        norm_class=pivot_masters["norm_class"],
        cif_fc=Decimal("777.00"),
        cif_inr=Decimal("65000.00"),
    )
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Pivot import item",
        hs_code=pivot_masters["hs_code"],
        quantity=Decimal("100.000"),
        allotted_quantity=Decimal("10.000"),
        debited_quantity=Decimal("5.000"),
        available_quantity=Decimal("85.000"),
        debited_value=Decimal("50.00"),
        cif_fc=Decimal("1000.00"),
    )
    import_item.items.add(pivot_masters["item_name"])
    LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=import_item,
        item_name=pivot_masters["item_name"],
        planned_quantity=Decimal("40.000"),
        planned_cif_fc=Decimal("400.00"),
    )
    return license_obj


def _report_params(**overrides):
    params = {"min_balance": 200, "license_status": "active"}
    params.update(overrides)
    return params


def _download_excel(client, **overrides):
    response = client.get(reverse("license:item-pivot-report"), _report_params(format="excel", **overrides))
    assert response.status_code == 200, getattr(response, "data", response.content[:300])
    return b"".join(response.streaming_content) if response.streaming else response.content


def _report_json(client, **overrides):
    response = client.get(reverse("license:item-pivot-report"), _report_params(**overrides))
    assert response.status_code == 200, getattr(response, "data", response.content[:300])
    return response.json()


def _number(value):
    return Decimal(str(value))


def _assert_excel_value_matches_json(actual, expected):
    if expected is None:
        assert actual is None
    else:
        assert _number(actual) == _number(expected)


ITEM_SUMMARY_METRIC_HEADERS = [
    "TOTAL QTY", "ALLOTTED QTY", "ALLOTTED CIF", "DEBITED QTY", "DEBITED CIF",
    "BALANCE QTY", "UNIT PRICE", "PLAN QTY", "PLANNED CIF",
]


def _blank_if_zero(value):
    # The Excel Item Summary leaves zero values blank, as the on-screen table does.
    return None if _number(value) == 0 else value


def _fixture_group(report):
    return next(group for group in report["groups"] if group["notification_number"] == "PIVN1")


@pytest.mark.django_db
def test_item_pivot_excel_is_a_valid_workbook_with_canonical_group_sheet(superuser_client, pivot_license):
    report = _report_json(superuser_client)
    assert report["report_version"] == "canonical-item-pivot-v1"
    group = _fixture_group(report)

    workbook = load_workbook(BytesIO(_download_excel(superuser_client)), data_only=True)
    report_sheets = [sheet for sheet in workbook.worksheets if sheet.title != "TOTAL_Summary"]
    assert len(report_sheets) == 1, workbook.sheetnames
    sheet = report_sheets[0]

    metadata = [cell.value for cell in sheet[1]]
    while metadata and metadata[-1] is None:
        metadata.pop()
    assert metadata == [
        "Notification Number: PIVN1", "GE Purchase", "1 Licences",
    ]
    fixed_header = [cell.value for cell in sheet[2]]
    assert fixed_header[:9] == [
        "SR NO", "DFIA NO", "EXPIRY DT", "EXPORTER", "TOTAL CIF",
        "DEBITED CIF", "ALLOTTED CIF", "PLANNED CIF", "BALANCE CIF",
    ]
    # Row 3 carries the item field labels. Fields that are null or 0 everywhere are hidden
    # (this fixture has no allotted, debited, billed or restriction values).
    field_header = [cell.value for cell in sheet[3]]
    while field_header and field_header[-1] is None:
        field_header.pop()
    assert field_header[9:] == [
        "HSN CODE", "DESCRIPTION", "TOTAL QTY", "BALANCE QTY", "PLAN QTY", "PLANNED CIF",
    ]
    assert group["license_count"] == 1


@pytest.mark.django_db
def test_item_pivot_excel_data_and_totals_match_the_canonical_json_matrix(superuser_client, pivot_license):
    group = _fixture_group(_report_json(superuser_client))
    license_row = next(row for row in group["licenses"] if row["license_number"] == pivot_license.license_number)
    item = next(iter(license_row["items"].values()))
    item_total = next(iter(group["totals"]["items"].values()))

    workbook = load_workbook(BytesIO(_download_excel(superuser_client)), data_only=True)
    sheet = next(sheet for sheet in workbook.worksheets if sheet.title != "TOTAL_Summary")
    field_header = [cell.value for cell in sheet[3]]
    data_row = [cell.value for cell in sheet[4]]
    total_row = next(
        [cell.value for cell in row]
        for row in sheet.iter_rows()
        if str(row[0].value).startswith("TOTAL —")
    )

    assert data_row[1] == license_row["license_number"]
    for index, field in ((4, "total_cif"), (5, "debited_cif"), (6, "allotted_cif"), (7, "planned_cif"), (8, "balance_cif")):
        assert _number(data_row[index]) == _number(license_row[field])
        assert _number(total_row[index]) == _number(group["totals"][field])

    assert data_row[field_header.index("HSN CODE", 9)] == item["hsn_code"]
    assert data_row[field_header.index("DESCRIPTION", 9)] == item["description"]
    item_fields = (
        ("TOTAL QTY", "total_qty"), ("ALLOTTED QTY", "allotted_qty"), ("ALLOTTED CIF", "allotted_cif"),
        ("DEBITED QTY", "debited_qty"), ("DEBITED CIF", "boe_used_cif"), ("BILLED QTY", "billed_qty"),
        ("BILLED CIF", "billed_cif"), ("BALANCE QTY", "balance_qty"), ("RESTRICTION %", "restriction_percent"),
        ("RESTRICTION VAL", "restriction_value"), ("PLAN QTY", "plan_qty"), ("PLANNED CIF", "planned_cif"),
    )
    for label, field in item_fields:
        if label in field_header[9:]:
            index = field_header.index(label, 9)
            assert _number(data_row[index]) == _number(item[field] or 0), label
            assert _number(total_row[index]) == _number(item_total[field] or 0), label
        else:
            # Hidden only because every licence cell and the item total for it are null or 0.
            assert _number(item.get(field) or 0) == 0, label
            assert _number(item_total.get(field) or 0) == 0, label
    assert len(total_row) == len(field_header)


@pytest.mark.django_db
def test_item_pivot_excel_item_summary_header_names_its_notification(superuser_client, pivot_license):
    workbook = load_workbook(BytesIO(_download_excel(superuser_client)), data_only=True)
    sheet = next(sheet for sheet in workbook.worksheets if sheet.title != "TOTAL_Summary")

    summary_header = next(
        [cell.value for cell in row]
        for row in sheet.iter_rows()
        if str(row[0].value).startswith("Item Summary")
    )
    while summary_header and summary_header[-1] is None:
        summary_header.pop()
    assert summary_header[0] == "Item Summary — Notification PIVN1 · GE Purchase"
    assert summary_header[1:] == ["SION", "HSN CODES", "LICENCES", *ITEM_SUMMARY_METRIC_HEADERS]


@pytest.mark.django_db
def test_item_pivot_excel_total_summary_matches_grand_total_projection(superuser_client, pivot_license):
    report = _report_json(superuser_client)
    workbook = load_workbook(BytesIO(_download_excel(superuser_client)), data_only=True)
    sheet = workbook["TOTAL_Summary"]

    header = [cell.value for cell in sheet[1]]
    while header and header[-1] is None:
        header.pop()
    assert header == ["TOTAL SUMMARY — ALL NOTIFICATIONS", "SION", "HSN CODES", "LICENCES", *ITEM_SUMMARY_METRIC_HEADERS]

    # One row per grand-total item, then the SUBTOTAL row.
    body = [[cell.value for cell in row] for row in sheet.iter_rows(min_row=2) if row[0].value not in (None, "")]
    assert len(body) == len(report["grand_total"]["item_summary"]) + 1
    subtotal_row = body[-1]
    assert subtotal_row[0] == "SUBTOTAL"
    totals = report["grand_total"]["item_summary_totals"]
    for index, field in ((4, "total_qty"), (5, "allotted_qty"), (6, "allotted_cif"), (7, "boe_used_qty"), (8, "boe_used_cif"), (9, "balance_qty"), (11, "planned_qty"), (12, "planned_cif")):
        _assert_excel_value_matches_json(subtotal_row[index], _blank_if_zero(totals[field]))


@pytest.mark.django_db
def test_item_pivot_excel_company_filter_matches_json_matrix(superuser_client, pivot_license):
    report = _report_json(superuser_client, company_ids=str(pivot_license.exporter_id))
    workbook = load_workbook(
        BytesIO(_download_excel(superuser_client, company_ids=str(pivot_license.exporter_id))),
        data_only=True,
    )

    group = _fixture_group(report)
    sheet = next(sheet for sheet in workbook.worksheets if sheet.title != "TOTAL_Summary")
    exported_numbers = set()
    for row in sheet.iter_rows(min_row=3):
        if str(row[0].value).startswith("TOTAL —"):
            break
        if row[1].value:
            exported_numbers.add(row[1].value)
    assert exported_numbers == {row["license_number"] for row in group["licenses"]}
