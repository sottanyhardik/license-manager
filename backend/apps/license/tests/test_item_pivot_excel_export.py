"""
Regression tests for the Item Pivot Report's live Excel export
(`ItemPivotReportView.export_to_excel_streaming`, hit via
`GET /api/license/reports/item-pivot/?format=excel`).

These guard against a class of bug that has recurred multiple times in this
report's various Excel-export implementations: the TOTAL row's cells being
built with the wrong number of leading/trailing placeholder `None`s, so
values land under the wrong header (e.g. a CIF sum rendering under "Notes"
instead of "Total CIF"). We assert the totals row has exactly as many cells
as the header row, and that named CIF/quantity totals land under their
correctly-named header column.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model

from apps.core.models import (
    CompanyModel,
    HSCodeModel,
    ItemNameModel,
    HeadSIONNormsModel,
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
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
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
    """A single active, sufficiently-balanced license with one import item
    that is both physically present (quantity/allotted/debited/available) and
    manually planned (LicenseItemPlan) — exercising the manual-plan branch of
    the Plan Qty / Planned CIF totals-row logic."""
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
    # balance_cif is a DERIVED field (see LicenseBalanceCalculator /
    # apps.license.signals.update_license_flags) recomputed as
    # credit(export CIF) - debit - allotment - trade on every save of the
    # license or its child rows — any direct write to it gets clobbered by
    # the next signal. Get a non-zero, known balance by giving the license
    # a real export item instead of poking the balance field directly.
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

    # Manual utilization plan for the same item: 40 units / 400 CIF-FC ->
    # effective rate of 10.00, distinct from any norm-derived rate so the
    # test can tell the two apart.
    LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=import_item,
        item_name=pivot_masters["item_name"],
        planned_quantity=Decimal("40.000"),
        planned_cif_fc=Decimal("400.00"),
    )
    return license_obj


@pytest.fixture
def pivot_license_with_multi_split(db, pivot_masters):
    """A second, separate license whose single import item is split across
    TWO manual-plan lines (same pivot item-name column, distinct unit price/
    qty/cif per split) — exercising the "Planning Splits" sheet, which lists
    every visible split flat rather than folding them into the pivot cell's
    summed plan_quantity/plan_cif."""
    license_obj = LicenseDetailsModel.objects.create(
        license_number="PIVOT-EXCEL-SPLIT-001",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=pivot_masters["exporter"],
        notification_number=pivot_masters["notification"],
        scheme_code=pivot_masters["scheme"],
        purchase_status=pivot_masters["purchase_status"],
        file_number="PIVOT-FILE-SPLIT-001",
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Pivot split export item",
        norm_class=pivot_masters["norm_class"],
        cif_fc=Decimal("500.00"),
        cif_inr=Decimal("42000.00"),
    )
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Pivot split import item",
        hs_code=pivot_masters["hs_code"],
        quantity=Decimal("50.000"),
        allotted_quantity=Decimal("0"),
        debited_quantity=Decimal("0"),
        available_quantity=Decimal("50.000"),
        debited_value=Decimal("0"),
        cif_fc=Decimal("300.00"),
    )
    import_item.items.add(pivot_masters["item_name"])

    LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=import_item,
        item_name=pivot_masters["item_name"],
        planned_quantity=Decimal("20.000"),
        unit_price=Decimal("5.00"),
        planned_cif_fc=Decimal("100.00"),
    )
    LicenseItemPlan.objects.create(
        license=license_obj,
        import_item=import_item,
        item_name=pivot_masters["item_name"],
        planned_quantity=Decimal("10.000"),
        unit_price=Decimal("7.50"),
        planned_cif_fc=Decimal("75.00"),
    )
    return license_obj


def _download_excel(superuser_client):
    response = superuser_client.get(
        reverse("license:item-pivot-report"),
        {"format": "excel", "min_balance": 200, "license_status": "active"},
    )
    assert response.status_code == 200, getattr(response, "data", response.content[:300])
    content = b"".join(response.streaming_content) if response.streaming else response.content
    return content


def _first_report_sheet(workbook):
    # Only one norm/notification combination is present in this fixture set,
    # so there should be exactly one norm/notification report sheet, plus the
    # always-appended "Planning Splits" sheet (see
    # test_item_pivot_excel_has_planning_splits_sheet below).
    report_sheets = [ws for ws in workbook.worksheets if ws.title != "Planning Splits"]
    assert len(report_sheets) == 1, [ws.title for ws in workbook.worksheets]
    return report_sheets[0]


@pytest.mark.django_db
def test_item_pivot_excel_totals_row_matches_header_column_count(superuser_client, pivot_license):
    """The TOTAL row must have exactly as many cells as the header row —
    a mismatch here is exactly the class of bug that caused CIF sums (and
    every later item's totals) to land under the wrong header."""
    content = _download_excel(superuser_client)
    workbook = load_workbook(BytesIO(content), data_only=True)
    sheet = _first_report_sheet(workbook)

    header_row = [cell.value for cell in sheet[3]]  # row1=title, row2=blank, row3=headers
    totals_row = [cell.value for cell in sheet[sheet.max_row]]

    assert totals_row[0] == "TOTAL"
    assert len(totals_row) == len(header_row), (
        f"totals row has {len(totals_row)} cells but header row has {len(header_row)}; "
        "a stray/missing None in the totals-row assembly shifts every later "
        "column's value out from under its header"
    )


@pytest.mark.django_db
def test_item_pivot_excel_base_cif_totals_land_under_correct_headers(superuser_client, pivot_license):
    """Total/Debited/Alloted/Balance CIF sums must appear under their
    same-named header columns, not shifted by the DFIA No/DFIA Dt/Expiry Dt/
    Exporter skip (previously extended by 6 Nones instead of 4)."""
    content = _download_excel(superuser_client)
    workbook = load_workbook(BytesIO(content), data_only=True)
    sheet = _first_report_sheet(workbook)

    header_row = [cell.value for cell in sheet[3]]
    totals_row = [cell.value for cell in sheet[sheet.max_row]]

    base_headers = ['Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt', 'Exporter',
                     'Total CIF', 'Debited CIF', 'Alloted CIF', 'Balance CIF',
                     'Notes', 'Condition Sheet']
    assert header_row[:len(base_headers)] == base_headers

    for label in ("Total CIF", "Debited CIF", "Alloted CIF", "Balance CIF", "Notes", "Condition Sheet"):
        idx = header_row.index(label)
        # Only the four CIF columns carry a numeric sum; Notes/Condition
        # Sheet must stay blank in the totals row.
        if label in ("Notes", "Condition Sheet"):
            assert totals_row[idx] in (None, ""), f"{label} totals cell should be blank, got {totals_row[idx]!r}"

    total_cif_idx = header_row.index("Total CIF")
    debited_cif_idx = header_row.index("Debited CIF")
    alloted_cif_idx = header_row.index("Alloted CIF")
    balance_cif_idx = header_row.index("Balance CIF")

    # "Total CIF" / "Balance CIF" are computed from the license's EXPORT item(s)
    # (the credit side), not the import item's cif_fc — see _build_license_row's
    # "Calculate total CIF from export license items" block. The fixture's
    # export item carries 777.00, with no debit/allotment/trade against it, so
    # balance_cif (a derived field recomputed by apps.license.signals on every
    # save) settles at the same 777.00.
    assert totals_row[total_cif_idx] == pytest.approx(777.00)
    assert totals_row[debited_cif_idx] == pytest.approx(50.00)
    assert totals_row[alloted_cif_idx] == pytest.approx(0.0)  # no AllotmentItems created
    assert totals_row[balance_cif_idx] == pytest.approx(777.00)

    # And DFIA No / DFIA Dt / Expiry Dt / Exporter must stay blank.
    for label in ("DFIA No", "DFIA Dt", "Expiry Dt", "Exporter"):
        idx = header_row.index(label)
        assert totals_row[idx] in (None, ""), f"{label} totals cell should be blank, got {totals_row[idx]!r}"


@pytest.mark.django_db
def test_item_pivot_excel_plan_qty_total_is_literal_sum(superuser_client, pivot_license):
    """The per-item 'Plan Qty' totals-row cell must hold a literal sum of
    `plan_quantity` across licenses — matching the on-screen report's
    `totalPlanQty` total — not a blended rate. Rows with no manual plan
    (norm-derived, shown as a unit-price rate per-row) contribute 0 rather
    than being folded into a rate."""
    content = _download_excel(superuser_client)
    workbook = load_workbook(BytesIO(content), data_only=True)
    sheet = _first_report_sheet(workbook)

    header_row = [cell.value for cell in sheet[3]]
    totals_row = [cell.value for cell in sheet[sheet.max_row]]

    item_name = "PIVOT TEST ITEM - PIVOTTEST"
    plan_qty_idx = header_row.index(f"{item_name} Plan Qty")
    planned_cif_idx = header_row.index(f"{item_name} Planned CIF")

    # planned_cif = 400.00 (manual plan), plan_quantity = 40.000 -> literal sum = 40.00
    assert totals_row[planned_cif_idx] == pytest.approx(400.00)
    assert totals_row[plan_qty_idx] == pytest.approx(40.00)


@pytest.mark.django_db
def test_item_pivot_excel_has_planning_splits_sheet_with_expected_rows(
    superuser_client, pivot_license_with_multi_split
):
    """A "Planning Splits" sheet must always be present (additive detail
    alongside the pivot grid, which can't host inline child rows) and must
    list one flat row per visible LicenseItemPlan split — sourced from
    `rows_for_splits()`, not re-derived filtering."""
    content = _download_excel(superuser_client)
    workbook = load_workbook(BytesIO(content), data_only=True)

    assert "Planning Splits" in workbook.sheetnames
    ws = workbook["Planning Splits"]

    header_row = [cell.value for cell in ws[1]]
    assert header_row == [
        "License No", "Product", "Item Name", "Split",
        "Unit Price", "Planned Qty", "Planned CIF",
    ]

    item_name = "PIVOT TEST ITEM - PIVOTTEST"
    data_rows = [
        [cell.value for cell in row]
        for row in ws.iter_rows(min_row=2)
        if row[0].value == "PIVOT-EXCEL-SPLIT-001"
    ]
    assert data_rows == [
        ["PIVOT-EXCEL-SPLIT-001", item_name, item_name, "Split 1", 5.0, 20.0, 100.0],
        ["PIVOT-EXCEL-SPLIT-001", item_name, item_name, "Split 2", 7.5, 10.0, 75.0],
    ]


@pytest.mark.django_db
def test_item_pivot_excel_planning_splits_sheet_lists_single_split_license(
    superuser_client, pivot_license
):
    """A license with exactly one (unpriced) manual-plan line still
    contributes exactly one visible-split row — the sheet lists every
    visible split regardless of how many lines an item was split into,
    matching `rows_for_splits()`'s per-item filter (qty>0 or cif>0), not a
    "must have 2+ splits" heuristic."""
    content = _download_excel(superuser_client)
    workbook = load_workbook(BytesIO(content), data_only=True)

    assert "Planning Splits" in workbook.sheetnames
    ws = workbook["Planning Splits"]

    item_name = "PIVOT TEST ITEM - PIVOTTEST"
    data_rows = [
        [cell.value for cell in row]
        for row in ws.iter_rows(min_row=2)
        if row[0].value == "PIVOT-EXCEL-001"
    ]
    # unit_price defaults to 0 (not set by this fixture) -> unit_price 0.0.
    assert data_rows == [
        ["PIVOT-EXCEL-001", item_name, item_name, "Split 1", 0.0, 40.0, 400.0],
    ]
