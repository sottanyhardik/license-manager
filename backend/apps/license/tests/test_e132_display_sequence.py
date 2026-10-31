"""E132 display sequence, canonical labels, classification and cache regressions.

The E132 display sequence (column order in the item pivot) is configured once, in
NORM_DISPLAY_SEQUENCES. Classification (E5_PRODUCT_CONDITIONS) is separate: changing the
display sequence must never change which category an item is assigned to.
"""
import hashlib
import io
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from apps.core.constants import GE
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, PurchaseStatus, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services import a3627_classifier
from apps.license.services import product_classification as pc
from apps.license.services.product_classification import (
    E5_PRODUCT_CONDITIONS,
    NORM_DISPLAY_SEQUENCES,
    classify_product,
    get_classification_priority,
    pivot_category_sort_key,
)
from apps.license.views.item_pivot_report import ItemPivotReportView

E132_SEQUENCE = [
    "FOOD FLAVOUR",
    "YEAST",
    "PKO",
    "CHEESE",
    "APPLE DIES",
    "CEREALS",
    "CMC",
    "ALUMINIUM FOIL",
    "PP",
]

# (HSN, description, expected E132 category) — one representative line per category.
E132_MATCHING = [
    ("0805", "orange peel", "FOOD FLAVOUR"),
    ("2106", "yeast extract", "YEAST"),
    ("1513", "palm kernel oil", "PKO"),
    ("0406", "cheese block", "CHEESE"),
    ("0813", "dried apple", "APPLE DIES"),
    ("1104", "oat flakes", "CEREALS"),
    ("3912", "cmc powder", "CMC"),
    ("7607", "aluminium foil roll", "ALUMINIUM FOIL"),
    ("3902", "PP granules", "PP"),
    ("1511", "palm olein", "RBD PAL"),  # valid E132 category outside the nine: sorts after them
]

# Every E132 line of the full licence, in REVERSE display order so the sort is what orders them.
E132_LINES = [
    (1, "3902", "PP granules", "PP"),
    (2, "7607", "aluminium foil roll", "ALUMINIUM FOIL"),
    (3, "3912", "cmc powder", "CMC"),
    (4, "1104", "oat flakes", "CEREALS"),
    (5, "0813", "dried apple", "APPLE DIES"),
    (6, "0406", "cheese block", "CHEESE"),
    (7, "1513", "palm kernel oil", "PKO"),
    (8, "2106", "yeast extract", "YEAST"),
    (9, "0805", "orange peel", "FOOD FLAVOUR"),
    (10, "1511", "palm olein", "RBD PAL"),
]

# --- Configuration and labels -----------------------------------------------------

def test_e132_display_sequence_is_exact_and_complete():
    assert NORM_DISPLAY_SEQUENCES["E132"] == tuple(E132_SEQUENCE)
    assert len(set(E132_SEQUENCE)) == 9


def test_e132_sequence_sorts_into_required_order_regardless_of_input_order():
    shuffled = list(reversed(E132_SEQUENCE))
    assert sorted(shuffled, key=lambda name: pivot_category_sort_key(name, "E132")) == E132_SEQUENCE


def test_e132_sequence_names_are_registry_categories():
    registry = {cond["name"] for cond in E5_PRODUCT_CONDITIONS}
    assert set(E132_SEQUENCE) <= registry


def test_canonical_labels_are_cereals_and_apple_dies_with_no_misspelled_duplicates():
    registry = {cond["name"] for cond in E5_PRODUCT_CONDITIONS}
    for label in ("CEREALS", "APPLE DIES"):
        assert label in registry
    for misspelling in ("CERELS", "APPLE DRIES"):
        assert misspelling not in registry
        assert misspelling not in NORM_DISPLAY_SEQUENCES["E132"]
    # Exactly one category per classification: CEREALS is the only cereal label.
    assert sum(1 for cond in E5_PRODUCT_CONDITIONS if "CEREAL" in cond["name"]) == 1


def test_e132_remaining_categories_follow_the_nine_in_deterministic_order():
    remaining = ["SUGAR", "RBD PAL", "DIETARY FIBRE"]
    ordered = sorted(remaining, key=lambda name: (pivot_category_sort_key(name, "E132"), name))
    # Fallback order is registry sort_order: DIETARY FIBRE 1, RBD PAL 4, SUGAR 99.
    assert ordered == ["DIETARY FIBRE", "RBD PAL", "SUGAR"]
    for name in remaining:
        assert pivot_category_sort_key(name, "E132") > pivot_category_sort_key("PP", "E132")


def test_unknown_category_sorts_after_the_nine_for_e132():
    assert pivot_category_sort_key(None, "E132") > pivot_category_sort_key("PP", "E132")


# --- Classification is unchanged --------------------------------------------------

@pytest.mark.parametrize("hsn, description, expected", E132_MATCHING)
def test_e132_classification_is_unchanged(hsn, description, expected):
    assert classify_product(hsn, description, "E132") == expected


def test_display_sequence_does_not_change_e132_classification(monkeypatch):
    before = [classify_product(h, d, "E132") for h, d, _ in E132_MATCHING]
    monkeypatch.setitem(NORM_DISPLAY_SEQUENCES, "E132", tuple(reversed(E132_SEQUENCE)))
    after = [classify_product(h, d, "E132") for h, d, _ in E132_MATCHING]
    assert before == after


def test_classification_priority_is_still_rule_order_not_display_order():
    assert get_classification_priority("APPLE DIES") < get_classification_priority("FOOD FLAVOUR")
    assert get_classification_priority("CEREALS") is not None


# --- Other norms are unaffected -------------------------------------------------

E1_SEQUENCE = [
    "OTHER CONFECTIONERY", "DWP/SWP", "WPC", "RBD PAL", "ESSENTIAL OIL",
    "APPLE DIES", "CITRIC ACID", "PP", "PAPER", "CMC",
]


@pytest.mark.parametrize("norm", ["E5", ""])
def test_norms_without_a_configured_sequence_keep_the_global_order(norm):
    names = [cond["name"] for cond in E5_PRODUCT_CONDITIONS]
    by_key = sorted(names, key=lambda name: (pivot_category_sort_key(name, norm), name))
    by_global = sorted(names, key=lambda name: (pc.get_product_category_sort_order(name), name))
    assert by_key == by_global


def test_e1_display_sequence_is_unchanged_under_the_norm_aware_key():
    assert sorted(E1_SEQUENCE, key=lambda name: pivot_category_sort_key(name, "E1")) == E1_SEQUENCE


def test_e132_and_e1_blocks_do_not_interleave_in_mixed_groups():
    # Each norm's categories keep their own sequence even when one notification group mixes norms.
    mixed = [(name, "E1") for name in reversed(E1_SEQUENCE)] + [(name, "E132") for name in reversed(E132_SEQUENCE)]
    ordered = sorted(mixed, key=lambda pair: (pivot_category_sort_key(pair[0], pair[1]), pair[0]))
    assert [name for name, norm in ordered if norm == "E1"] == E1_SEQUENCE
    assert [name for name, norm in ordered if norm == "E132"] == E132_SEQUENCE
    assert all(norm == "E1" for _, norm in ordered[: len(E1_SEQUENCE)])


# --- Cache fingerprint ----------------------------------------------------------

def test_registry_version_fingerprints_the_display_configuration_file():
    services = Path(a3627_classifier.__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ("a3627_classifier.py", "product_classification.py"):
        digest.update((services / name).read_bytes())
    assert a3627_classifier.registry_version() == digest.hexdigest()[:16]


# --- Pivot JSON and Excel -------------------------------------------------------

def _e132_licence(number, lines):
    company, _ = CompanyModel.objects.get_or_create(iec="9832000001", defaults={"name": "E132 Sequence Exporter"})
    status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
    head, _ = HeadSIONNormsModel.objects.get_or_create(name="E132 SEQUENCE HEAD", defaults={})
    e132, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E132", defaults={"head_norm": head, "is_active": True},
    )
    lic = LicenseDetailsModel.objects.create(
        license_number=number, license_date=date.today() - timedelta(days=1),
        license_expiry_date=date.today() + timedelta(days=30), exporter=company, purchase_status=status,
    )
    LicenseExportItemModel.objects.create(license=lic, norm_class=e132, cif_fc=Decimal("100000"))
    for serial, hsn, description, _ in lines:
        code, _ = HSCodeModel.objects.get_or_create(hs_code=hsn)
        LicenseImportItemsModel.objects.create(
            license=lic, serial_number=serial, hs_code=code, description=description,
            quantity=Decimal("100"), available_quantity=Decimal("100"), cif_fc=Decimal("50"),
        )
    return lic


def _licence_groups(report, number):
    return [g for g in report["groups"] if any(row["license_number"] == number for row in g["licenses"])]


@pytest.fixture
def e132_full_licence(db):
    return _e132_licence("E132-SEQ-FULL", E132_LINES)


@pytest.fixture
def e132_partial_licence(db):
    # Absent categories: only CHEESE and PP. A zero-available line is kept as its own row.
    lines = [
        (1, "3902", "PP granules", "PP"),
        (2, "0406", "cheese block", "CHEESE"),
    ]
    return _e132_licence("E132-SEQ-PART", lines)


@pytest.mark.django_db
def test_pivot_json_orders_all_nine_e132_categories_exactly(e132_full_licence):
    report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
    (group,) = _licence_groups(report, "E132-SEQ-FULL")
    categories = [item["product_category"] for item in group["item_groups"]]
    assert categories == E132_SEQUENCE + ["RBD PAL"]


@pytest.mark.django_db
def test_pivot_items_list_matches_item_groups_order(e132_full_licence):
    report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
    (group,) = _licence_groups(report, "E132-SEQ-FULL")
    group_order = [item["key"] for item in group["item_groups"]]
    flat_order = [item["key"] for item in report["items"] if item["key"] in set(group_order)]
    assert flat_order == group_order


@pytest.mark.django_db
def test_absent_categories_are_skipped_and_present_ones_keep_their_order(e132_full_licence, e132_partial_licence):
    report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
    (group,) = _licence_groups(report, "E132-SEQ-PART")
    partial_row = next(row for row in group["licenses"] if row["license_number"] == "E132-SEQ-PART")
    # The group's columns are the union across licences; this licence shows only its own cells, in order.
    own = [item["product_category"] for item in group["item_groups"] if item["key"] in partial_row["items"]]
    assert own == ["CHEESE", "PP"]


@pytest.mark.django_db
def test_excel_columns_follow_the_same_e132_order(e132_full_licence):
    response = ItemPivotReportView().export_to_excel_streaming(min_balance=0, license_status="all")
    workbook = openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)), data_only=True)
    for sheet in workbook.worksheets:
        # Row 1 is the notification title; row 2 carries the merged product-category headers.
        headers = [sheet.cell(2, c).value for c in range(10, sheet.max_column + 1) if sheet.cell(2, c).value]
        if "FOOD FLAVOUR" in headers:
            assert headers == E132_SEQUENCE + ["RBD PAL"]
            assert "CERELS" not in headers and "APPLE DRIES" not in headers
            return
    raise AssertionError("E132 licence not found in the Excel export")
