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


@pytest.mark.django_db
def test_planned_report_generate_report_called_exactly_once_per_request(report_viewer_client, planned_report_masters):
    """Phase 2B.1 regression: the view must compute the Display Dataset
    exactly once and thread the same dict to both the JSON response and the
    Excel exporter — `export_to_excel` must never call `generate_report`
    itself. Wraps the real method (not a stub) so this also still exercises
    genuine report generation, just counts the calls."""
    from unittest.mock import patch

    from apps.license.views.planned_report import PlannedReportView

    lic = _make_license("PLANNED-REPORT-ONCE", planned_report_masters["parle"])
    planned_item = _make_import_item(
        lic, planned_report_masters["hs_code"], item_names=[planned_report_masters["wheat"]]
    )
    LicenseItemPlan.objects.create(
        import_item=planned_item, item_name=planned_report_masters["wheat"],
        planned_quantity=Decimal("10.000"), unit_price=Decimal("5.00"), planned_cif_fc=Decimal("50.00"),
    )

    with patch.object(PlannedReportView, "generate_report", autospec=True, side_effect=PlannedReportView.generate_report) as mocked:
        json_response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
        assert json_response.status_code == 200
        assert mocked.call_count == 1

    with patch.object(PlannedReportView, "generate_report", autospec=True, side_effect=PlannedReportView.generate_report) as mocked:
        excel_response = report_viewer_client.get(REPORT_URL, {"min_balance": 0, "format": "excel"})
        assert excel_response.status_code == 200
        assert mocked.call_count == 1


@pytest.mark.django_db
def test_planned_report_excel_rows_match_json_rows(report_viewer_client, planned_report_masters):
    """Phase 2B.1 regression: JSON and Excel must render the exact same
    per-item figures for the same request — using the shared
    apps.core.tests.report_assertions helper introduced in Phase 2A."""
    from io import BytesIO

    from openpyxl import load_workbook

    from apps.core.tests.report_assertions import assert_excel_rows_match_json_rows

    lic_a = _make_license("PLANNED-REPORT-MATCH-A", planned_report_masters["parle"])
    item_a = _make_import_item(lic_a, planned_report_masters["hs_code"], item_names=[planned_report_masters["wheat"]])
    LicenseItemPlan.objects.create(
        import_item=item_a, item_name=planned_report_masters["wheat"],
        planned_quantity=Decimal("10.000"), unit_price=Decimal("5.00"), planned_cif_fc=Decimal("50.00"),
    )

    lic_b = _make_license("PLANNED-REPORT-MATCH-B", planned_report_masters["parle"])
    item_b = _make_import_item(
        lic_b, planned_report_masters["hs_code"], serial=2, item_names=[planned_report_masters["milk"]],
        available_value=Decimal("300.00"), available_quantity=Decimal("20.000"),
    )
    LicenseItemPlan.objects.create(
        import_item=item_b, item_name=planned_report_masters["milk"],
        planned_quantity=Decimal("4.000"), unit_price=Decimal("2.00"), planned_cif_fc=Decimal("8.00"),
    )

    json_response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    json_items = json_response.json()["items"]
    assert len(json_items) == 2

    excel_response = report_viewer_client.get(REPORT_URL, {"min_balance": 0, "format": "excel"})
    workbook = load_workbook(BytesIO(excel_response.content), data_only=True)

    assert_excel_rows_match_json_rows(
        workbook, json_items, "Not Restricted",
        column_map={
            "available_quantity": 12, "available_balance": 13,
            "planned_quantity": 18, "planned_cif": 20,
        },
        header_row=1, key_field="license_number", key_column=2,
    )


@pytest.mark.django_db
def test_planned_report_balance_cif_matches_live_calc_with_allocation(report_viewer_client, planned_report_masters):
    """BL-LEDGER-02 regression: `balance_cif` in the planned-report rows
    must match the LIVE-computed Financial Available Balance -- including
    when a reconciliation allocation exists (`create_invoice_boe_allocation`),
    which never refreshes the cached `LicenseBalance.balance_cif` column."""
    from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
    from apps.core.constants import DEBIT
    from apps.license.models import LicenseExportItemModel
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from apps.reconciliation.services import allocation_service
    from apps.trade.models import LicenseTrade, LicenseTradeLine

    lic = _make_license("PLANNED-REPORT-ALLOC", planned_report_masters["parle"])
    LicenseExportItemModel.objects.create(
        license=lic, description="Export item", cif_fc=Decimal("151.00"), cif_inr=Decimal("12758.50"),
    )
    item = _make_import_item(lic, planned_report_masters["hs_code"], item_names=[planned_report_masters["wheat"]])
    LicenseItemPlan.objects.create(
        import_item=item, item_name=planned_report_masters["wheat"],
        planned_quantity=Decimal("10.000"), unit_price=Decimal("5.00"), planned_cif_fc=Decimal("50.00"),
    )
    lic.balance.balance_cif = Decimal("999.99")  # deliberately stale
    lic.balance.save(update_fields=["balance_cif"])

    boe = BillOfEntryModel.objects.create(
        company=planned_report_masters["parle"], bill_of_entry_number="BOE-PLANNED-ALLOC-001",
        bill_of_entry_date=date.today(), exchange_rate=Decimal("84.50"),
    )
    row = RowDetails.objects.create(
        bill_of_entry=boe, sr_number=item, transaction_type=DEBIT,
        cif_fc=Decimal("100.00"), cif_inr=Decimal("8450.00"), qty=Decimal("1.000"),
    )
    trade = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE, from_company=planned_report_masters["parle"],
        invoice_number="INV-PLANNED-ALLOC-001", invoice_date=date.today(),
    )
    trade_line = LicenseTradeLine.objects.create(
        trade=trade, sr_number=item, description="Sale line",
        mode=LicenseTradeLine.MODE_CIF_INR, cif_fc=Decimal("100.00"),
        cif_inr=Decimal("8450.00"), qty_kg=Decimal("1.0000"),
    )
    allocation_service.create_invoice_boe_allocation(
        trade_line, row, qty=Decimal("0"), cif_fc=Decimal("100.00"), cif_inr=Decimal("8450.00"), user=None,
    )

    expected_live_balance = LicenseBalanceCalculator.calculate_financial_balance(lic)
    assert expected_live_balance == Decimal("51.00")

    response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    assert response.status_code == 200
    row_data = next(r for r in response.json()["items"] if r["license_id"] == lic.id)
    assert row_data["balance_cif"] == pytest.approx(float(expected_live_balance))


@pytest.mark.django_db
def test_planned_report_query_count_stays_flat(report_viewer_client, planned_report_masters):
    """BL-LEDGER-02 regression: the batched `calculate_financial_balance_
    for_licenses()` swap must not reintroduce an N+1 -- query count should
    stay flat as the number of plan rows/licenses grows."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    for i in range(5):
        lic = _make_license(f"PLANNED-QCOUNT-{i:03d}", planned_report_masters["parle"])
        item = _make_import_item(lic, planned_report_masters["hs_code"], item_names=[planned_report_masters["wheat"]])
        LicenseItemPlan.objects.create(
            import_item=item, item_name=planned_report_masters["wheat"],
            planned_quantity=Decimal("10.000"), unit_price=Decimal("5.00"), planned_cif_fc=Decimal("50.00"),
        )

    with CaptureQueriesContext(connection) as ctx:
        response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    assert response.status_code == 200
    small_query_count = len(ctx.captured_queries)

    for i in range(5, 15):
        lic = _make_license(f"PLANNED-QCOUNT-{i:03d}", planned_report_masters["parle"])
        item = _make_import_item(lic, planned_report_masters["hs_code"], item_names=[planned_report_masters["wheat"]])
        LicenseItemPlan.objects.create(
            import_item=item, item_name=planned_report_masters["wheat"],
            planned_quantity=Decimal("10.000"), unit_price=Decimal("5.00"), planned_cif_fc=Decimal("50.00"),
        )

    with CaptureQueriesContext(connection) as ctx:
        response = report_viewer_client.get(REPORT_URL, {"min_balance": 0})
    assert response.status_code == 200
    larger_query_count = len(ctx.captured_queries)

    assert larger_query_count <= small_query_count + 3, (
        f"query count grew from {small_query_count} (5 plans) to "
        f"{larger_query_count} (15 plans) -- looks like an N+1"
    )
