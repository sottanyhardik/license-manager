"""Item Report — Planning Status filter (owner 2026-11-20).

Planned = linked to at least one valid plan (active, not deleted, not cancelled): the plan line's own import item, or one of
the plan's source items (``allocation_provenance.source_item_ids``) on the plan's own licence. Filtering is server-side;
counts are per status within the other filters; existing figures are unchanged.
"""
from decimal import Decimal

import pytest

from apps.license.models import LicenseItemPlan
from apps.license.tests.test_item_report_view import (  # noqa: F401 — pytest fixtures
    REPORT_URL, _make_import_item, _make_license, item_report_masters, report_viewer_client,
)


def _plan(lic, item, name, qty="10.000", cif="50.00", **extra):
    return LicenseItemPlan.objects.create(license=lic, import_item=item, item_name=name, planned_quantity=Decimal(qty),
                                          unit_price=Decimal("5.00"), planned_cif_fc=Decimal(cif), **extra)


@pytest.fixture
def planning_data(db, item_report_masters):
    m = item_report_masters
    lic = _make_license("ITEM-PLAN-001", m["parle"])
    other = _make_license("ITEM-PLAN-002", m["other"], expiry_days=40)
    planned = _make_import_item(lic, m["hs_code"], serial=1, item_names=[m["wheat"]])
    multi = _make_import_item(lic, m["hs_code"], serial=2, item_names=[m["milk"]])
    source_only = _make_import_item(lic, m["hs_code"], serial=3)
    unplanned = _make_import_item(lic, m["hs_code"], serial=4, item_names=[m["wheat"]])
    cancelled = _make_import_item(lic, m["hs_code"], serial=5)
    foreign = _make_import_item(other, m["hs_code"], serial=1)
    _plan(lic, planned, m["wheat"])
    _plan(lic, multi, m["milk"])
    _plan(lic, multi, m["wheat"], qty="5.000", cif="25.00")  # two plans on one item → one row, never duplicated
    # A split plan whose line sits on `multi` but which plans from `source_only` too (and names a foreign licence's item,
    # which is ignored: a plan only covers its own licence's items).
    _plan(lic, multi, m["wheat"], qty="1.000", cif="5.00",
          allocation_provenance={"strategy": "SPLIT_BY_PERCENT", "source_item_ids": [multi.pk, source_only.pk, foreign.pk]})
    _plan(lic, cancelled, m["wheat"], is_active=False, is_cancelled=True)
    _plan(lic, cancelled, m["milk"], is_active=False, is_deleted=True)
    _plan(lic, cancelled, m["milk"], is_active=False)
    return {"planned": planned, "multi": multi, "source_only": source_only, "unplanned": unplanned, "cancelled": cancelled,
            "foreign": foreign}


def _get(client, **params):
    response = client.get(REPORT_URL, {"min_balance": 0, **params})
    assert response.status_code == 200, response.content
    return response.json()


@pytest.mark.django_db
def test_all_is_the_default_and_includes_planned_and_unplanned(report_viewer_client, planning_data):
    data = _get(report_viewer_client)
    ids = [row["id"] for row in data["items"]]
    assert data["planning_status"] == "all"
    assert set(ids) == {item.pk for item in planning_data.values()}
    assert len(ids) == len(set(ids)) == data["total_items"]  # the item with three plans appears once
    flags = {row["id"]: row["is_planned"] for row in data["items"]}
    d = planning_data
    assert flags == {d["planned"].pk: True, d["multi"].pk: True, d["source_only"].pk: True, d["unplanned"].pk: False,
                     d["cancelled"].pk: False, d["foreign"].pk: False}
    assert data["planning_counts"] == {"all": 6, "planned": 3, "unplanned": 3}
    assert _get(report_viewer_client, planning_status="all")["items"] == data["items"]


@pytest.mark.django_db
def test_planned_and_unplanned_are_disjoint_and_cover_all(report_viewer_client, planning_data):
    d = planning_data
    planned = _get(report_viewer_client, planning_status="planned")
    unplanned = _get(report_viewer_client, planning_status="unplanned")
    assert {r["id"] for r in planned["items"]} == {d["planned"].pk, d["multi"].pk, d["source_only"].pk}
    assert {r["id"] for r in unplanned["items"]} == {d["unplanned"].pk, d["cancelled"].pk, d["foreign"].pk}
    assert all(r["is_planned"] for r in planned["items"]) and not any(r["is_planned"] for r in unplanned["items"])
    # counts describe the whole filtered population, whichever status is selected; total_items is the filtered list
    for data in (planned, unplanned):
        assert data["planning_counts"] == {"all": 6, "planned": 3, "unplanned": 3}
    assert planned["total_items"] == 3 and unplanned["total_items"] == 3
    # server order (expiry date, licence, serial) is kept inside each status
    all_rows = [r["id"] for r in _get(report_viewer_client)["items"]]
    assert [r["id"] for r in planned["items"]] == [i for i in all_rows if i in {r["id"] for r in planned["items"]}]


@pytest.mark.django_db
def test_status_combines_with_search_and_other_filters(report_viewer_client, item_report_masters, planning_data):
    d, m = planning_data, item_report_masters
    by_name = _get(report_viewer_client, planning_status="unplanned", item_names=str(m["wheat"].pk))
    assert [r["id"] for r in by_name["items"]] == [d["unplanned"].pk]
    assert by_name["planning_counts"] == {"all": 2, "planned": 1, "unplanned": 1}  # within the item-name filter
    by_desc = _get(report_viewer_client, planning_status="planned", product_description="Import item 3")
    assert [r["id"] for r in by_desc["items"]] == [d["source_only"].pk]
    by_company = _get(report_viewer_client, planning_status="planned", company_ids=str(m["other"].pk))
    assert by_company["items"] == [] and by_company["planning_counts"] == {"all": 1, "planned": 0, "unplanned": 1}


@pytest.mark.django_db
def test_existing_figures_are_unchanged_by_the_status_filter(report_viewer_client, planning_data):
    keys = ("quantity", "available_quantity", "available_balance", "unit_price", "balance_cif", "planned_quantity", "planned_cif",
            "plan_source", "planned_splits", "item_names")
    full = {r["id"]: {k: r[k] for k in keys} for r in _get(report_viewer_client)["items"]}
    for status in ("planned", "unplanned"):
        for row in _get(report_viewer_client, planning_status=status)["items"]:
            assert {k: row[k] for k in keys} == full[row["id"]]
    assert full[planning_data["multi"].pk]["planned_quantity"] == pytest.approx(16.0)  # 10 + 5 + 1, every plan line once


@pytest.mark.django_db
def test_invalid_status_is_a_400_and_excel_honours_the_filter(report_viewer_client, planning_data):
    assert report_viewer_client.get(REPORT_URL, {"min_balance": 0, "planning_status": "maybe"}).status_code == 400
    import io

    import openpyxl
    response = report_viewer_client.get(REPORT_URL, {"min_balance": 0, "planning_status": "unplanned", "_format": "excel"})
    assert response.status_code == 200
    content = b"".join(response.streaming_content) if hasattr(response, "streaming_content") else response.content
    sheet = openpyxl.load_workbook(io.BytesIO(content)).active
    text = " ".join(str(c) for row in sheet.iter_rows(values_only=True) for c in row if c is not None)
    # unplanned rows only: serial 4 and 5 of ITEM-PLAN-001 and the other licence's item; planned serials 2 and 3 are absent
    assert "Import item 4" in text and "Import item 5" in text and "ITEM-PLAN-002" in text
    assert "Import item 2" not in text and "Import item 3" not in text
