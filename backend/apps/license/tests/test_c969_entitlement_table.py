"""C969 flat entitlement table: standard columns, every category, complete entitlement,
product-name classification, status filter, and no change for other norms."""
from decimal import Decimal

import pytest

from apps.core.models import HeadSIONNormsModel, HSCodeModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.c969_product_classifier import C969_CATEGORY_ORDER, NO_DESCRIPTION, UNRECOGNISED
from apps.license.services.item_pivot_service import (
    C969_ENTITLEMENT_COLUMNS,
    ItemPivotService,
    c969_balance_qty,
)

EIGHT_COLUMNS = [
    "HSN CODE", "DESCRIPTION", "TOTAL QTY", "ALLOTTED QTY", "ALLOTTED CIF", "DEBITED QTY", "DEBITED CIF", "BALANCE QTY",
]


@pytest.fixture
def norms():
    head = HeadSIONNormsModel.objects.create(name="C969 entitlement")
    return {code: SionNormClassModel.objects.create(head_norm=head, norm_class=code) for code in ("C969", "E5")}


def _licence(number, norm, expiry=None):
    from apps.core.models import PurchaseStatus
    status, _ = PurchaseStatus.objects.get_or_create(code="GE", defaults={"label": "Global Exim"})
    licence = LicenseDetailsModel.objects.create(
        license_number=number, license_expiry_date=expiry, purchase_status=status,
    )
    LicenseExportItemModel.objects.create(license=licence, norm_class=norm, cif_fc=Decimal("1000.00"))
    return licence


def _line(licence, serial, description, qty, hs=None):
    return LicenseImportItemsModel.objects.create(
        license=licence, serial_number=serial, description=description, quantity=Decimal(str(qty)), unit="kg", hs_code=hs,
    )


def _rows(report):
    return {row["category"]: row for row in report["c969_entitlement"]["rows"]}


# A. Column structure

def test_table_has_exactly_the_eight_standard_columns_in_order():
    assert [label for _, label in C969_ENTITLEMENT_COLUMNS] == EIGHT_COLUMNS


# D. Calculation helper (same formula as the unplanned path of build())

@pytest.mark.parametrize(
    "total, debited, allotted, billed, expected",
    [
        (Decimal("10"), Decimal("2"), Decimal("3"), Decimal("0"), Decimal("5")),
        (Decimal("10"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("10")),
        (Decimal("10"), Decimal("6"), Decimal("6"), Decimal("0"), Decimal("0")),   # over-used floors at zero
        (Decimal("0.001"), Decimal("0.0005"), Decimal("0"), Decimal("0"), Decimal("0.0005")),
    ],
)
def test_balance_is_total_less_used_floored_at_zero(total, debited, allotted, billed, expected):
    assert c969_balance_qty(total, debited, allotted, billed) == expected


# B, C. All categories, complete entitlement, fallback handling

@pytest.mark.django_db
def test_every_configured_category_is_listed_and_fallbacks_only_when_present(norms):
    licence = _licence("C969-ENT-001", norms["C969"])
    _line(licence, 1, "Front Wheel Rim", 10)

    report = ItemPivotService.build([licence])
    rows = _rows(report)

    assert "UNCLASSIFIED" not in rows
    assert len(rows) == len(C969_CATEGORY_ORDER) - 2  # 34 configured rows; fallbacks only when present
    for name in C969_CATEGORY_ORDER:
        if name in (NO_DESCRIPTION, UNRECOGNISED):
            continue
        assert name in rows, name
    assert NO_DESCRIPTION not in rows
    assert UNRECOGNISED not in rows


@pytest.mark.django_db
def test_fallback_categories_appear_only_for_matching_lines(norms):
    licence = _licence("C969-ENT-002", norms["C969"])
    _line(licence, 1, "", 3)
    _line(licence, 2, "(DELETED)", 2)
    _line(licence, 3, "20", 7)

    rows = _rows(ItemPivotService.build([licence]))

    assert rows[NO_DESCRIPTION]["line_count"] == 2
    assert rows[NO_DESCRIPTION]["total_qty"] == "5.000"
    assert rows[UNRECOGNISED]["line_count"] == 1
    assert rows[UNRECOGNISED]["total_qty"] == "7.000"


@pytest.mark.django_db
def test_unplanned_and_never_used_lines_keep_their_full_entitlement(norms):
    licence = _licence("C969-ENT-003", norms["C969"])
    _line(licence, 1, "Air Filter", 500)
    rows = _rows(ItemPivotService.build([licence]))
    air = rows["AIR FILTER"]
    assert air["total_qty"] == "500.000"
    assert air["allotted_qty"] == "0.000"
    assert air["debited_qty"] == "0.000"
    assert air["balance_qty"] == "500.000"
    assert air["license_count"] == 1


# E. Product-name classification with a shared HSN code

@pytest.mark.django_db
def test_shared_hsn_code_does_not_decide_the_category(norms):
    licence = _licence("C969-ENT-004", norms["C969"])
    shared = HSCodeModel.objects.create(hs_code="84821020")
    _line(licence, 1, "Hydraulic Pump (Including Auxiliary hydraulic Pump)", 10, hs=shared)
    _line(licence, 2, "Oil Pump", 20, hs=shared)
    _line(licence, 3, "Gear housing part", 30, hs=shared)

    rows = _rows(ItemPivotService.build([licence]))

    assert rows["HYDRAULIC PUMP"]["line_count"] == 1
    assert rows["OIL PUMP"]["line_count"] == 1
    assert rows["BEARING"]["line_count"] == 0
    assert rows["HYDRAULIC PUMP"]["hsn_code"] == "84821020"


# F. Status filter: `all` includes expired licences

@pytest.mark.django_db
def test_status_all_includes_expired_licences_and_active_does_not(norms):
    from datetime import date

    from apps.license.views.item_pivot_report import ItemPivotReportView

    expired = _licence("C969-EXP-001", norms["C969"], expiry=date(2013, 8, 31))
    _line(expired, 1, "Radiator", 5)
    view = ItemPivotReportView()

    def licences(status):
        data = view.generate_report(30, "C969", None, None, 0, status, None, None, None)
        return {lic.get("license_number") for group in data.get("groups", []) for lic in group.get("licenses", [])}

    assert "C969-EXP-001" in licences("all")
    assert "C969-EXP-001" not in licences("active")


# G. Other norms keep their output

@pytest.mark.django_db
def test_other_norms_do_not_gain_the_c969_table(norms):
    licence = _licence("E5-ENT-001", norms["E5"])
    _line(licence, 1, "Front Wheel Rim", 10)
    report = ItemPivotService.build([licence])
    assert "c969_entitlement" not in report


# H. Unclassified lines are listed for classification

@pytest.mark.django_db
def test_unclassified_lines_are_listed_and_named_lines_are_not(norms):
    licence = _licence("C969-ENT-UNR-001", norms["C969"])
    _line(licence, 1, "20", 7)
    _line(licence, 2, "Air Filter", 500)
    _line(licence, 3, "", 3)

    items = ItemPivotService.build([licence])["c969_entitlement"]["unrecognised_items"]

    assert [(i["licence_number"], i["description"], i["quantity"]) for i in items] == [
        ("C969-ENT-UNR-001", "20", "7.000"),
    ]
    assert items[0]["import_item_id"] and items[0]["current_classifiers"] == []
