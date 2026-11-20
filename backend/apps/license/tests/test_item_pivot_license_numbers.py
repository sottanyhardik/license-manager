"""Item Pivot report — License Numbers filter (``license_numbers`` query param).

Additive filter only: the pivot engine (``ItemPivotService.build``) and every CIF / quantity figure are unchanged;
the filter just narrows the licence population with one ``IN`` query, AND-ed with the existing filters.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import (
    CompanyModel, HSCodeModel, HeadSIONNormsModel, ItemNameModel, NotificationNumber, PurchaseStatus, SchemeCode,
    SionNormClassModel,
)
from apps.license.api.views.item_pivot_report import ItemPivotReportView
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.item_pivot_selection import MAX_LICENSE_NUMBERS, parse_license_numbers

NORM = "LNFTEST"
OTHER_NORM = "LNFOTHER"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client(db):
    user = get_user_model().objects.create_superuser(username="lnf-tester", email="lnf@example.com", password="P@ssw0rd12345")
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return api


@pytest.fixture
def masters(db):
    head = HeadSIONNormsModel.objects.create(name="LNF Head Norm")
    norm = SionNormClassModel.objects.create(head_norm=head, norm_class=NORM, is_active=True)
    other = SionNormClassModel.objects.create(head_norm=head, norm_class=OTHER_NORM, is_active=True)
    return {
        "norm": norm, "other_norm": other,
        "items": [ItemNameModel.objects.create(name=f"LNF ITEM {i} - {NORM}", sion_norm_class=norm, is_active=True, display_order=i)
                  for i in (1, 2)],
        "other_item": ItemNameModel.objects.create(name=f"LNF ITEM - {OTHER_NORM}", sion_norm_class=other, is_active=True),
        "exporters": [CompanyModel.objects.create(iec=f"99900022{i:02d}", name=f"LNF Exporter {i}") for i in (1, 2)],
        "notification": NotificationNumber.objects.create(code="LNFN1", label="LNF Notification"),
        "scheme": SchemeCode.objects.create(code="LNFDFIA", label="LNF DFIA"),
        "ps": PurchaseStatus.objects.create(code="GE", label="GE Purchase"),
        "hs": HSCodeModel.objects.create(hs_code="99998888", product_description="LNF Product"),
    }


@pytest.fixture
def make_license(masters):
    def _make(number, *, norm_key="norm", exporter=0, expiry_days=60, two_items=True):
        lic = LicenseDetailsModel.objects.create(
            license_number=number, license_date=date.today() - timedelta(days=30),
            license_expiry_date=date.today() + timedelta(days=expiry_days), exporter=masters["exporters"][exporter],
            notification_number=masters["notification"], scheme_code=masters["scheme"], purchase_status=masters["ps"],
        )
        LicenseExportItemModel.objects.create(license=lic, description="exp", norm_class=masters[norm_key],
                                              cif_fc=Decimal("5000.00"), cif_inr=Decimal("400000.00"))
        names = masters["items"] if norm_key == "norm" else [masters["other_item"]]
        for serial, item_name in enumerate(names if two_items else names[:1], 1):
            imp = LicenseImportItemsModel.objects.create(
                license=lic, serial_number=serial, description=f"imp {serial}", hs_code=masters["hs"],
                quantity=Decimal("100.000"), available_quantity=Decimal("100.000"), cif_fc=Decimal("1000.00"),
            )
            imp.items.add(item_name)
        return lic
    return _make


def _get(client, **params):
    base = {"sion_norm": NORM, "min_balance": 200, "license_status": "active"}
    base.update(params)
    return client.get(reverse("license:item-pivot-report"), base)


def _json(client, **params):
    response = _get(client, **params)
    assert response.status_code == 200, response.content[:300]
    return response.json()


def _licence_numbers(report):
    return sorted(row["license_number"] for group in report["groups"] for row in group["licenses"])


def _excel(client, **params):
    response = _get(client, format="excel", **params)
    assert response.status_code == 200
    return load_workbook(BytesIO(b"".join(response.streaming_content)), data_only=True)


# ---- parsing ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    (None, []),
    ("", []),
    (" , ,, ", []),
    ("0510456789", ["0510456789"]),
    ("0510456789, 0510456790,0510456791", ["0510456789", "0510456790", "0510456791"]),
    ("  0510456789  ,   0510456790 ", ["0510456789", "0510456790"]),
    ("0510456789,0510456790,0510456789, 0510456790", ["0510456789", "0510456790"]),
    ("0510456789\n0510456790\r\n0510456791;0510456792\t0510456793",
     ["0510456789", "0510456790", "0510456791", "0510456792", "0510456793"]),
])
def test_parse_license_numbers(raw, expected):
    assert parse_license_numbers(raw) == expected


# ---- report filtering ------------------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_license_numbers_keeps_current_behaviour(client, make_license):
    for n in ("LNF-001", "LNF-002", "LNF-003"):
        make_license(n)
    unfiltered = _json(client)
    assert _licence_numbers(unfiltered) == ["LNF-001", "LNF-002", "LNF-003"]
    assert "license_number_filter" not in unfiltered
    # An empty / blank param is identical to no param.
    blank = _json(client, license_numbers=" , ")
    assert _licence_numbers(blank) == _licence_numbers(unfiltered)
    assert "license_number_filter" not in blank


@pytest.mark.django_db
def test_single_license_number(client, make_license):
    make_license("LNF-001")
    make_license("LNF-002")
    report = _json(client, license_numbers="LNF-002")
    assert _licence_numbers(report) == ["LNF-002"]
    assert report["license_number_filter"]["matched"] == ["LNF-002"]


@pytest.mark.django_db
def test_multiple_numbers_with_spaces_and_duplicates_include_every_licence_and_item(client, make_license):
    for n in ("LNF-001", "LNF-002", "LNF-003", "LNF-004"):
        make_license(n)
    report = _json(client, license_numbers=" LNF-001 ,LNF-003,  LNF-001 , LNF-004,")
    assert _licence_numbers(report) == ["LNF-001", "LNF-003", "LNF-004"]
    summary = report["license_number_filter"]
    assert summary["requested"] == ["LNF-001", "LNF-003", "LNF-004"]
    assert summary["requested_count"] == 3
    assert summary["not_found"] == [] and summary["excluded_by_filters"] == []
    group = report["groups"][0]
    assert group["license_count"] == 3
    # Both import items (100 + 100) of every selected licence are in the pivot.
    for row in group["licenses"]:
        source_ids = [src["import_item_id"] for cell in row["items"].values() for src in cell.get("source_items", [])]
        assert len(source_ids) == 2, row["items"].keys()
        assert sum(Decimal(str(cell["total_qty"])) for cell in row["items"].values()) == Decimal("200.000")


@pytest.mark.django_db
def test_match_is_exact(client, make_license):
    make_license("LNF-001")
    report = _json(client, license_numbers="lnf-001, LNF-00, LNF-0011")
    assert _licence_numbers(report) == []
    assert report["license_number_filter"]["not_found"] == ["lnf-001", "LNF-00", "LNF-0011"]


@pytest.mark.django_db
def test_invalid_and_unmatched_numbers_are_reported_not_errors(client, make_license):
    make_license("LNF-001")
    make_license("LNF-OTHER", norm_key="other_norm")
    make_license("LNF-EXPIRED", expiry_days=-90)
    too_long = "X" * 80
    report = _json(client, license_numbers=f"LNF-001, NOPE-999, {too_long}, LNF-OTHER, LNF-EXPIRED, ;DROP TABLE x")
    assert _licence_numbers(report) == ["LNF-001"]
    summary = report["license_number_filter"]
    assert summary["matched"] == ["LNF-001"]
    assert summary["not_found"] == ["NOPE-999", too_long, "DROP TABLE x"]
    assert summary["excluded_by_filters"] == [
        {"license_number": "LNF-OTHER", "sion_norms": [OTHER_NORM]},
        {"license_number": "LNF-EXPIRED", "sion_norms": [NORM]},
    ]


@pytest.mark.django_db
def test_all_unmatched_returns_an_empty_report(client, make_license):
    make_license("LNF-001")
    report = _json(client, license_numbers="NOPE-1, NOPE-2")
    assert _licence_numbers(report) == []
    assert report["license_number_filter"]["not_found"] == ["NOPE-1", "NOPE-2"]


@pytest.mark.django_db
def test_combines_with_existing_filters(client, make_license, masters):
    make_license("LNF-001", exporter=0)
    make_license("LNF-002", exporter=1)
    make_license("LNF-003", exporter=1, expiry_days=-90)
    numbers = "LNF-001, LNF-002, LNF-003"
    exporter_2 = masters["exporters"][1].pk
    assert _licence_numbers(_json(client, license_numbers=numbers)) == ["LNF-001", "LNF-002"]
    assert _licence_numbers(_json(client, license_numbers=numbers, company_ids=str(exporter_2))) == ["LNF-002"]
    assert _licence_numbers(_json(client, license_numbers=numbers, exclude_company_ids=str(exporter_2))) == ["LNF-001"]
    assert _licence_numbers(_json(client, license_numbers=numbers, license_status="all")) == ["LNF-001", "LNF-002", "LNF-003"]
    assert _licence_numbers(_json(client, license_numbers=numbers, min_balance=10 ** 9)) == []


@pytest.mark.django_db
def test_filtered_figures_equal_the_unfiltered_figures_for_the_same_licences(client, make_license):
    """The filter must not change any number: a licence row is identical with and without the filter."""
    for n in ("LNF-001", "LNF-002", "LNF-003"):
        make_license(n)
    full_rows = {row["license_number"]: row for row in _json(client)["groups"][0]["licenses"]}
    filtered = _json(client, license_numbers="LNF-003,LNF-001")["groups"][0]["licenses"]
    for row in filtered:
        expected = dict(full_rows[row["license_number"]])
        actual = dict(row)
        expected.pop("sr_no", None), actual.pop("sr_no", None)
        assert actual == expected


@pytest.mark.django_db
def test_too_many_numbers_is_a_400(client):
    numbers = ",".join(f"N{i}" for i in range(MAX_LICENSE_NUMBERS + 1))
    response = _get(client, license_numbers=numbers)
    assert response.status_code == 400
    assert "Too many license numbers" in response.json()["error"]


@pytest.mark.django_db
def test_large_list_query_count_does_not_grow_per_requested_number(make_license):
    for i in range(3):
        make_license(f"LNF-{i:03d}")
    view = ItemPivotReportView()

    def queries(numbers):
        with CaptureQueriesContext(connection) as ctx:
            view.generate_report(sion_norm=NORM, license_numbers=numbers)
        return len(ctx.captured_queries)

    few = queries(["LNF-000"])
    many = queries(["LNF-000"] + [f"NOPE-{i}" for i in range(2000)])
    assert many == few


# ---- Excel -----------------------------------------------------------------------------------------------------------

def _sheet_rows(workbook):
    sheets = [s for s in workbook.worksheets if s.title != "TOTAL_Summary"]
    data, totals = [], []
    for sheet in sheets:
        for row in sheet.iter_rows(min_row=4, values_only=True):
            if isinstance(row[0], int) and row[1]:
                data.append(row)
            elif isinstance(row[0], str) and row[0].startswith("TOTAL —"):
                totals.append(row)
    return data, totals


@pytest.mark.django_db
def test_excel_exports_every_matching_licence_with_numeric_cells_and_reconciles_with_json(client, make_license):
    numbers = [f"LNF-{i:03d}" for i in range(12)]
    for n in numbers:
        make_license(n)
    make_license("LNF-NOT-REQUESTED")
    requested = ", ".join(numbers)
    report = _json(client, license_numbers=requested)
    workbook = _excel(client, license_numbers=requested)
    data, totals = _sheet_rows(workbook)

    assert sorted(row[1] for row in data) == numbers == _licence_numbers(report)
    group = report["groups"][0]
    assert len(totals) == 1 and totals[0][0] == "TOTAL — 12 LICENCES"
    # TOTAL CIF … BALANCE CIF columns: numeric cells, and the totals equal the on-screen totals and the row sums.
    for col, key in zip(range(4, 9), ("total_cif", "debited_cif", "allotted_cif", "planned_cif", "balance_cif")):
        column = [row[col] for row in data]
        assert all(isinstance(v, (int, float)) for v in column), key
        assert Decimal(str(totals[0][col] or 0)) == Decimal(str(group["totals"][key] or 0)), key
        assert sum(Decimal(str(v or 0)) for v in column) == Decimal(str(group["totals"][key] or 0)), key
    assert isinstance(data[0][4], (int, float))
