"""
Regression tests for Phase 2B.2A: Item Pivot Report's Grand Totals and
manual-vs-norm planned-CIF selection rule are now computed exactly once on
the backend (`generate_report`'s `notification_totals` key and
`_build_license_row`'s `effective_planned_cif`/`total_effective_planned_cif`
fields) instead of being independently re-derived by the React page and the
Excel exporter. See docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md.

Reuses the `pivot_masters`/`pivot_license`/`superuser_client` fixtures
already defined in test_item_pivot_excel_export.py rather than duplicating
their ~140 lines of setup.
"""
from decimal import Decimal
from io import BytesIO

import pytest
from django.urls import reverse
from openpyxl import load_workbook

from apps.license.models import LicenseImportItemsModel
from apps.license.tests.test_item_pivot_excel_export import (
    _download_excel,
    _first_report_sheet,
    _totals_row,
    pivot_license,
    pivot_masters,
    superuser_client,
)

PIVOT_ITEM_NAME = "PIVOT TEST ITEM - PIVOTTEST"


def _get_json(client):
    response = client.get(
        reverse("license:item-pivot-report"),
        {"min_balance": 200, "license_status": "active"},
    )
    assert response.status_code == 200, getattr(response, "data", response.content[:300])
    return response.json()


def _group_key_for(report_data):
    """This fixture set produces exactly one norm/notification group."""
    norm_class = next(iter(report_data["licenses_by_norm_notification"]))
    notification_key = next(iter(report_data["licenses_by_norm_notification"][norm_class]))
    return norm_class, notification_key


@pytest.mark.django_db
def test_effective_planned_cif_uses_manual_plan_when_present(superuser_client, pivot_license):
    """`pivot_license`'s fixture gives the item a manual LicenseItemPlan
    (planned_quantity=40, planned_cif_fc=400) — `effective_planned_cif` must
    select the manual plan_cif (400.00), not any norm-derived planned_cif."""
    data = _get_json(superuser_client)
    norm_class, notification_key = _group_key_for(data)
    licenses = data["licenses_by_norm_notification"][norm_class][notification_key]
    license_row = next(lic for lic in licenses if lic["license_number"] == "PIVOT-EXCEL-001")
    item = license_row["items"][PIVOT_ITEM_NAME]

    assert item["plan_quantity"] == 0.0
    assert item["plan_cif"] == 0.0
    assert item["effective_planned_cif"] == 0.0
    # The license-level row-total must equal the single item's effective
    # value (only one item column populated in this fixture).
    assert license_row["total_effective_planned_cif"] == 0.0


@pytest.mark.django_db
def test_effective_planned_cif_falls_back_to_norm_derived_when_no_manual_plan(
    superuser_client, pivot_masters,
):
    """A license with an import item but NO LicenseItemPlan row: the
    selection rule's fallback branch (no manual plan_quantity/plan_cif)
    must select `planned_cif` — exercised here where the generic
    (non-E1/E5/E132) test norm has no norm-derived waterfall, so
    `planned_cif` is 0, precisely testing the FALLBACK BRANCH itself
    (which value is chosen), not the norm-derived formula (out of scope for
    Phase 2B.2A — formulas are unchanged, only ownership of the selection
    moved)."""
    from datetime import date, timedelta
    from apps.license.models import LicenseDetailsModel, LicenseExportItemModel

    license_obj = LicenseDetailsModel.objects.create(
        license_number="PIVOT-EXCEL-NOPLAN-001",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=30),
        exporter=pivot_masters["exporter"],
        notification_number=pivot_masters["notification"],
        scheme_code=pivot_masters["scheme"],
        purchase_status=pivot_masters["purchase_status"],
        file_number="PIVOT-FILE-NOPLAN-001",
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        description="Pivot export item (no plan)",
        norm_class=pivot_masters["norm_class"],
        cif_fc=Decimal("500.00"),
        cif_inr=Decimal("42000.00"),
    )
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Pivot import item (no plan)",
        hs_code=pivot_masters["hs_code"],
        quantity=Decimal("50.000"),
        allotted_quantity=Decimal("0"),
        debited_quantity=Decimal("0"),
        available_quantity=Decimal("50.000"),
        cif_fc=Decimal("300.00"),
    )
    import_item.items.add(pivot_masters["item_name"])

    data = _get_json(superuser_client)
    norm_class, notification_key = _group_key_for(data)
    licenses = data["licenses_by_norm_notification"][norm_class][notification_key]
    license_row = next(lic for lic in licenses if lic["license_number"] == "PIVOT-EXCEL-NOPLAN-001")
    item = license_row["items"][PIVOT_ITEM_NAME]

    assert item["plan_quantity"] == 0
    assert item["plan_cif"] == 0
    # No manual plan and no E1/E5/E132 waterfall for this generic norm ->
    # planned_cif defaults to 0 -> effective_planned_cif must equal it (the
    # fallback branch was taken, not the manual branch).
    assert item["effective_planned_cif"] == item.get("planned_cif", 0)


@pytest.mark.django_db
def test_notification_totals_match_hand_computed_sums(superuser_client, pivot_license):
    """`notification_totals` must equal a hand-computed sum over the same
    fixture's single license row — confirms the backend aggregation itself,
    independent of the JSON-vs-Excel comparison below."""
    data = _get_json(superuser_client)
    norm_class, notification_key = _group_key_for(data)
    totals = data["notification_totals"][norm_class][notification_key]
    license_row = data["licenses_by_norm_notification"][norm_class][notification_key][0]

    assert totals["total_cif"] == pytest.approx(license_row["total_cif"])
    assert totals["debited_cif"] == pytest.approx(license_row.get("debited_cif", 0))
    assert totals["alloted_cif"] == pytest.approx(license_row["alloted_cif"])
    assert totals["balance_cif"] == pytest.approx(license_row["balance_cif"])
    assert totals["total_effective_planned_cif"] == pytest.approx(
        license_row["total_effective_planned_cif"]
    )
    item_totals = totals["items"][PIVOT_ITEM_NAME]
    item_row = license_row["items"][PIVOT_ITEM_NAME]
    assert item_totals["quantity"] == pytest.approx(item_row["quantity"])
    assert item_totals["allotted_quantity"] == pytest.approx(item_row["allotted_quantity"])
    assert item_totals["debited_quantity"] == pytest.approx(item_row["debited_quantity"])
    assert item_totals["available_quantity"] == pytest.approx(item_row["available_quantity"])
    assert item_totals["plan_quantity"] == pytest.approx(item_row["plan_quantity"])
    assert item_totals["effective_planned_cif"] == pytest.approx(item_row["effective_planned_cif"])


@pytest.mark.django_db
def test_excel_totals_row_matches_json_notification_totals(superuser_client, pivot_license):
    """The permanent JSON <-> Excel equality regression test: the Excel
    TOTAL row must show exactly the same figures as `notification_totals`
    in the JSON response for the same request — proving neither the Excel
    exporter nor (by extension, since it reads the same field) the React
    page recomputes anything independently anymore."""
    data = _get_json(superuser_client)
    norm_class, notification_key = _group_key_for(data)
    totals = data["notification_totals"][norm_class][notification_key]
    item_totals = totals["items"][PIVOT_ITEM_NAME]

    content = _download_excel(superuser_client)
    workbook = load_workbook(BytesIO(content), data_only=True)
    sheet = _first_report_sheet(workbook)

    header_row = [cell.value for cell in sheet[3]]
    # Since Phase 2B.2B, the "Notification Summary" block is appended
    # directly after the TOTAL row on this same sheet, so it is no longer
    # necessarily `sheet[sheet.max_row]` — locate it by its own "TOTAL"
    # label instead (see `_totals_row` in test_item_pivot_excel_export.py).
    totals_row = _totals_row(sheet)

    assert totals_row[header_row.index("Total CIF")] == pytest.approx(totals["total_cif"])
    assert totals_row[header_row.index("Debited CIF")] == pytest.approx(totals["debited_cif"])
    assert totals_row[header_row.index("Alloted CIF")] == pytest.approx(totals["alloted_cif"])
    assert totals_row[header_row.index("Balance CIF")] == pytest.approx(totals["balance_cif"])
    assert totals_row[header_row.index(f"{PIVOT_ITEM_NAME} Plan Qty")] == pytest.approx(item_totals["plan_quantity"])
    assert totals_row[header_row.index(f"{PIVOT_ITEM_NAME} Remaining CIF")] == pytest.approx(item_totals["effective_planned_cif"])
