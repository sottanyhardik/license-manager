"""E126 display sequence, canonical labels and classification regressions.

The authoritative classifier is product_classification.E5_PRODUCT_CONDITIONS (via classify_product).
The E126 display sequence is NORM_DISPLAY_SEQUENCES["E126"], read only by the pivot sort key.
Changing the display sequence must never change a classification result.
"""
import io
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import openpyxl
import pytest
from django.core.cache import cache
from django.test import RequestFactory

from apps.core.constants import GE
from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, PurchaseStatus, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services import product_classification as pc
from apps.license.services.product_classification import (
    E5_PRODUCT_CONDITIONS,
    classify_product,
    get_classification_priority,
    pivot_category_sort_key,
)
from apps.license.views import item_pivot_report as pivot_view_module
from apps.license.views.item_pivot_report import ItemPivotReportView

E126_LEADING = ["FOOD FLAVOUR", "OLIVE OIL", "PKO", "ALUMINIUM FOIL"]
E126_OTHER = ["RBD PAL", "DIETARY FIBRE", "CMC", "SUGAR", "CEREALS"]

# (HSN, description, expected) for E126. Preserves the registry's existing matching and precedence.
E126_MATCHING = [
    # OLIVE OIL: HSN 1509/1510 or description 1509/1510
    ("1509", "", "OLIVE OIL"),
    ("1510", "", "OLIVE OIL"),
    ("", "olive oil 1509 blend", "OLIVE OIL"),
    # PKO: HSN 1513 or description 1513, but never with 1509/1510
    ("1513", "", "PKO"),
    ("", "1513 palm kernel", "PKO"),
    ("1513", "palm kernel oil", "PKO"),
    ("1513", "palm kernel oil 1509", "OLIVE OIL"),  # PKO excludes description 1509
    ("1510", "palm kernel 1513", "OLIVE OIL"),  # conflicting HSN/desc: OLIVE OIL rule is earlier
    # RBD PAL: HSN 1511 without 1509/1510/1513 signals
    ("1511", "palm olein", "RBD PAL"),
    ("1511", "palm olein 1513", "PKO"),  # RBD PAL excludes description 1513; PKO matches
    # ALUMINIUM FOIL: HSN 7607
    ("7607", "aluminium foil", "ALUMINIUM FOIL"),
    ("7607", "", "ALUMINIUM FOIL"),
    # FOOD FLAVOUR: nut products (0802) and related fruit/food codes
    ("0802", "nut mix", "FOOD FLAVOUR"),
    ("0804", "dates", "FOOD FLAVOUR"),
    ("2010", "fruit 2009 mix", "FOOD FLAVOUR"),  # JUICE is HSN 2009 only
    ("0813", "FOOD ADDITIVES apple", "FOOD FLAVOUR"),  # APPLE DIES excludes FOOD ADDITIVES
    # Other valid E126 categories remain available
    ("0802", "dietary fibre nut", "DIETARY FIBRE"),
    ("3912", "cmc", "CMC"),
    ("", "sugar", "SUGAR"),
    ("0813", "dried apple", "APPLE DIES"),
    ("2009", "juice", "JUICE"),
    # Missing HSN or description
    ("", "", None),
    ("1000", "", None),
    # Unrelated products
    ("1000", "wheat grain", None),
    # Documented gap: the registry has no PACKING keyword rule for aluminium, so description-only
    # aluminium foil is not classified. Revisit only if the business defines that rule.
    ("", "aluminium foil packing", None),
]


@pytest.mark.parametrize("hsn, description, expected", E126_MATCHING)
def test_e126_matching_is_unchanged(hsn, description, expected):
    assert classify_product(hsn, description, "E126") == expected


@pytest.mark.parametrize("hsn, description, norm, expected", [
    ("0802", "confectionery nut mix", "E1", "OTHER CONFECTIONERY"),
    # E1-only rule does not leak to E126. FOOD FLAVOUR excludes CONFECTIONERY, so the E126 item is unclassified.
    ("0802", "confectionery nut mix", "E126", None),
])
def test_e126_rules_do_not_leak_into_other_norms(hsn, description, norm, expected):
    assert classify_product(hsn, description, norm) == expected


def test_e126_leading_labels_are_canonical_registry_names():
    names = {cond["name"] for cond in E5_PRODUCT_CONDITIONS}
    assert set(E126_LEADING) <= names


def test_e126_leading_sequence_is_exact():
    ordered = sorted(E126_LEADING + E126_OTHER, key=lambda name: (pivot_category_sort_key(name, "E126"), name))
    assert ordered[:4] == ["FOOD FLAVOUR", "OLIVE OIL", "PKO", "ALUMINIUM FOIL"]


def test_e126_other_categories_follow_the_leading_four():
    leading_key = max(pivot_category_sort_key(name, "E126") for name in E126_LEADING)
    for name in E126_OTHER:
        assert pivot_category_sort_key(name, "E126") > leading_key


def test_e126_unclassified_sorts_last_within_the_norm():
    unclassified = pivot_category_sort_key(None, "E126")
    for name in E126_LEADING + E126_OTHER:
        assert pivot_category_sort_key(name, "E126") < unclassified


def test_unrelated_norm_orders_are_unchanged():
    e1 = ["OTHER CONFECTIONERY", "DWP/SWP", "WPC", "RBD PAL", "ESSENTIAL OIL", "APPLE DIES",
          "CITRIC ACID", "PP", "PAPER", "CMC"]
    e132 = ["FOOD FLAVOUR", "YEAST", "PKO", "CHEESE", "APPLE DIES", "CEREALS", "CMC", "ALUMINIUM FOIL", "PP"]
    assert sorted(e1, key=lambda name: pivot_category_sort_key(name, "E1")) == e1
    assert sorted(e132, key=lambda name: pivot_category_sort_key(name, "E132")) == e132


def test_display_sequence_does_not_change_e126_classification(monkeypatch):
    before = [classify_product(h, d, "E126") for h, d, _ in E126_MATCHING]
    reversed_sequence = dict(pc.NORM_DISPLAY_SEQUENCES)
    reversed_sequence["E126"] = tuple(reversed(pc.NORM_DISPLAY_SEQUENCES["E126"]))
    monkeypatch.setattr(pc, "NORM_DISPLAY_SEQUENCES", reversed_sequence)
    after = [classify_product(h, d, "E126") for h, d, _ in E126_MATCHING]
    assert before == after


def test_classification_priority_is_rule_order_not_display_order():
    # OLIVE OIL is tested before PKO, so the PKO exclusion keeps 1509 items out of PKO.
    assert get_classification_priority("OLIVE OIL") < get_classification_priority("PKO")
    assert get_classification_priority("NOT A CATEGORY") is None


# --- Pivot JSON and Excel order -------------------------------------------------

# Serial order is deliberately not the display order, so the sort must do the work.
E126_LINES = [
    (1, "1513", "palm kernel oil", "PKO"),
    (2, "7607", "aluminium foil", "ALUMINIUM FOIL"),
    (3, "3912", "cmc", "CMC"),
    (4, "1509", "olive oil", "OLIVE OIL"),
    (5, "0802", "nut mix", "FOOD FLAVOUR"),
    (6, "1511", "palm olein", "RBD PAL"),
    (7, "", "sugar", "SUGAR"),
]
E126_EXPECTED_ORDER = ["FOOD FLAVOUR", "OLIVE OIL", "PKO", "ALUMINIUM FOIL", "RBD PAL", "CMC", "SUGAR"]


@pytest.fixture
def e126_licence(db):
    company = CompanyModel.objects.create(iec=f"97{uuid.uuid4().int % 10**8:08d}", name="E126 Sequence Exporter")
    status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
    head = HeadSIONNormsModel.objects.create(name=f"E126S{uuid.uuid4().hex[:6]}")
    e126 = SionNormClassModel.objects.create(head_norm=head, norm_class="E126", is_active=True)
    lic = LicenseDetailsModel.objects.create(
        license_number="E126-SEQ-001", license_date=date.today() - timedelta(days=1),
        license_expiry_date=date.today() + timedelta(days=30), exporter=company, purchase_status=status,
    )
    LicenseExportItemModel.objects.create(license=lic, norm_class=e126, cif_fc=Decimal("100000"))
    for serial, hsn, description, _ in E126_LINES:
        code, _ = HSCodeModel.objects.get_or_create(hs_code=hsn or "99999999")
        LicenseImportItemsModel.objects.create(
            license=lic, serial_number=serial, hs_code=code, description=description,
            quantity=Decimal("100"), available_quantity=Decimal("100"), cif_fc=Decimal("50"),
        )
    return lic


@pytest.mark.django_db
def test_pivot_json_orders_e126_categories_by_display_sequence(e126_licence):
    report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
    group = next(g for g in report["groups"] if any(l["license_number"] == "E126-SEQ-001" for l in g["licenses"]))
    categories = [item["product_category"] for item in group["item_groups"]]
    assert [c for c in categories if c in E126_EXPECTED_ORDER] == E126_EXPECTED_ORDER
    # The flat item list agrees with the per-notification order.
    flat = [item["product_category"] for item in report["items"] if item["sion"] == "E126"]
    assert [c for c in flat if c in E126_EXPECTED_ORDER] == E126_EXPECTED_ORDER


@pytest.mark.django_db
def test_excel_headers_follow_the_same_e126_order(e126_licence):
    response = ItemPivotReportView().export_to_excel_streaming(min_balance=0, license_status="all")
    workbook = openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)), data_only=True)
    for sheet in workbook.worksheets:
        if sheet.title == "TOTAL_Summary":
            continue
        # Category labels sit in the header rows; read each row in column order and keep the first
        # row that carries every E126 category label, so the check does not depend on exact row numbers.
        for row in sheet.iter_rows(values_only=True):
            labels = [value for value in row if value in E126_EXPECTED_ORDER]
            if set(E126_EXPECTED_ORDER) <= set(labels):
                deduped = [label for i, label in enumerate(labels) if i == 0 or labels[i - 1] != label]
                assert deduped == E126_EXPECTED_ORDER
                return
    raise AssertionError("E126 categories not found as Excel headers")


# --- Cache invalidation ---------------------------------------------------------

def test_registry_version_change_misses_the_pivot_json_cache():
    """A changed registry version (classification or display order) cannot serve the old pivot."""
    cache.clear()
    try:
        view = ItemPivotReportView()
        view.generate_report = Mock(side_effect=[{"order": "old"}, {"order": "new"}])
        factory = RequestFactory()
        url = "/item-pivot/?days=30&sion_norm=E126"

        with patch.object(pivot_view_module, "registry_version", return_value="registry-old"):
            first = view.get(factory.get(url))
        with patch.object(pivot_view_module, "registry_version", return_value="registry-new"):
            second = view.get(factory.get(url))

        assert first.content and second.content
        assert json.loads(first.content) == {"order": "old"}
        assert json.loads(second.content) == {"order": "new"}
        assert view.generate_report.call_count == 2
    finally:
        cache.clear()


def test_same_registry_version_reuses_the_pivot_json_cache():
    cache.clear()
    try:
        view = ItemPivotReportView()
        view.generate_report = Mock(return_value={"order": "cached"})
        factory = RequestFactory()
        url = "/item-pivot/?days=30&sion_norm=E126"
        with patch.object(pivot_view_module, "registry_version", return_value="registry-same"):
            view.get(factory.get(url))
            view.get(factory.get(url))
        assert view.generate_report.call_count == 1
    finally:
        cache.clear()
