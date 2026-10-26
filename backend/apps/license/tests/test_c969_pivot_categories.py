"""C969 Item Pivot categories: 22 product-name rules, 12 generic rules, two fallbacks.

Pure tests cover the classifier module. The database test runs the real pivot service and
checks aggregation and column order. Classification comes from the product name only.
"""
from decimal import Decimal

import pytest

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.c969_product_classifier import (
    C969_CATEGORY_ORDER,
    C969_CLASSIFIER_ORDER,
    C969_GENERIC_CATEGORIES,
    NO_DESCRIPTION,
    UNRECOGNISED,
    classify_c969_category,
    classify_c969_product_name,
)

# A: the 22 explicit product-name categories, one example per category.
TWENTY_TWO = [
    ("Air Filter", "AIR FILTER"),
    ("Automotive Battery-8507", "AUTOMOTIVE BATTERY"),
    ("BALL BEARING QTY 3692 - TAPPER ROLLER BEARING QTY 4228", "BEARING"),
    ("Brake Assembly (Prime and / or Secondary)", "BRAKE ASSEMBLY"),
    ("Clutch Assembly (Including Split/ Torque Type)", "CLUTCH ASSEMBLY"),
    ("Internal Combustion Engine Complete", "INTERNAL COMBUSTION ENGINE"),
    ("Front Axle (2 Wheel Drive and/or 4 Wheel Drive) complete", "FRONT AXLE"),
    ("Fuel Filter", "FUEL FILTER"),
    ("Hydraulic Pump (Including Auxiliary hydraulic Pump)", "HYDRAULIC PUMP"),
    ("Hydraulic Cylinder", "HYDRAULIC CYLINDER"),
    ("Hydraulic Valves", "HYDRAULIC VALVES"),
    ("Oil Pump", "OIL PUMP"),
    ("Radiator", "RADIATOR"),
    ("Seat Assembly", "SEAT ASSEMBLY"),
    ("Alternator1", "ALTERNATOR"),
    ("Starter Motor1", "STARTER MOTOR"),
    ("Turbo Charger", "TURBO CHARGER"),
    ("Wiring Hanrness", "WIRING HANRNESS"),
    ("ALLOY STEEL RODS /BAR OF CARBON CONTENT LESS THAN 2 PERCENT HS CODE 7228", "ALLOY STEEL"),
    ("COLD ROLLED STEEL (SHEETS/WIDE COILS) -7208, 7209", "COLD ROLLED STEEL"),
    ("Front Wheel Rim", "FRONT WHEELRIM"),
    ("Rear Wheel Rim", "REAR WHEELRIM"),
]

# B: the 12 generic categories, one example each.
TWELVE_GENERIC = [
    ("HOT ROLLED STEEL (SHEETS/WIDE COILS) -7208, 7209", "HOT ROLLED STEEL"),
    ("Hydrostatic Unit/ Valves for Hydraulic Transmission", "HYDROSTATIC TRANSMISSION"),
    ("rearwheel tyre", "REARWHEEL TYRE"),
    ("frontwheel tyre", "FRONTWHEEL TYRE"),
    ("Water pump", "WATER PUMP"),
    ("auxiliary valves", "AUXILIARY VALVES"),
    ("fuel injection pump", "FUEL INJECTION PUMP"),
    ("synchropacks", "SYNCHROPACKS"),
    ("'O' Ring", "'O' RING"),
    ("Safety neutral switch", "SAFETY NEUTRAL SWITCH"),
    ("oil seperator", "OIL SEPERATOR"),
    ("Oil Seal (other than Engine) NET TO NET", "OIL SEAL"),
]


def test_there_are_22_explicit_and_12_generic_categories():
    assert len({c for _, c in TWENTY_TWO}) == 22
    assert len({c for _, c in TWELVE_GENERIC}) == 12
    assert [name for name, _ in C969_GENERIC_CATEGORIES] == [c for _, c in TWELVE_GENERIC]


@pytest.mark.parametrize("description, category", TWENTY_TWO)
def test_each_explicit_product_name_gets_its_category(description, category):
    assert classify_c969_product_name(description) == category
    assert classify_c969_category(description) == category


@pytest.mark.parametrize("description, category", TWELVE_GENERIC)
def test_each_generic_product_gets_its_category(description, category):
    assert classify_c969_category(description) == category


@pytest.mark.parametrize("description", [None, "", "   ", "(DELETED)", "(deleted)"])
def test_blank_or_deleted_descriptions_go_to_no_description(description):
    assert classify_c969_category(description) == NO_DESCRIPTION


@pytest.mark.parametrize("description", ["20", "CARBON CONTENTS LESS THAN 2 PERCENT HS CODE 7228"])
def test_unknown_nonblank_descriptions_go_to_unrecognised(description):
    assert classify_c969_category(description) == UNRECOGNISED


@pytest.mark.parametrize("description, category", TWENTY_TWO + TWELVE_GENERIC)
def test_known_products_never_fall_into_a_fallback(description, category):
    assert classify_c969_category(description) not in (NO_DESCRIPTION, UNRECOGNISED)


# D: pattern matching.

@pytest.mark.parametrize(
    "variant",
    ["FRONT WHEEL RIM", "front-wheel rim", "  Front   Wheel   Rim ", "Front Wheelrim", "FRONTWHEEL RIM"],
)
def test_case_whitespace_and_punctuation_variants_match(variant):
    assert classify_c969_category(variant) == "FRONT WHEELRIM"


def test_all_patterns_in_a_group_are_required():
    # Hydrostatic needs both words; the transmission word alone is not enough.
    assert classify_c969_category("Hydrostatic unit") != "HYDROSTATIC TRANSMISSION"
    assert classify_c969_category("Hydraulic transmission") != "HYDROSTATIC TRANSMISSION"


def test_alternative_groups_are_or_conditions():
    # Hot rolled OR non-alloy each give the generic hot-rolled category on their own.
    assert classify_c969_category("Hot rolled sheets") == "HOT ROLLED STEEL"
    assert classify_c969_category("Non alloy sheets") == "HOT ROLLED STEEL"


def test_similar_but_unrelated_names_do_not_match():
    assert classify_c969_category("Front Wheel Tyre") == "FRONTWHEEL TYRE"
    assert classify_c969_category("Rear Wheel Rim") == "REAR WHEELRIM"
    assert classify_c969_category("TWO RING") == UNRECOGNISED
    assert classify_c969_category("Hydraulic Oil Pump") == "OIL PUMP"


def test_frontwheel_tyretube_keeps_the_linker_substring_behaviour():
    # The linker's rule is a substring match, so "tyretube" is still a front wheel tyre.
    assert classify_c969_category("frontwheel tyretube") == "FRONTWHEEL TYRE"


# E: steel precedence (hot-rolled and cold-rolled on one line).

def test_line_naming_hot_and_cold_rolled_steel_stays_under_cold_rolled():
    line = "HOT ROLLED / COLD ROLLED STEEL (SHEETS/WIDE COILS) - 7208 & 7209"
    assert classify_c969_category(line) == "COLD ROLLED STEEL"


def test_hot_rolled_only_line_is_hot_rolled():
    assert classify_c969_category("HOT ROLLED STEEL (SHEETS/WIDE COILS) -7208, 7209") == "HOT ROLLED STEEL"


# F: norm isolation. The C969 names must not classify other norms.

@pytest.mark.parametrize("norm", ["E5", "E1", "E126", "E132", "C473", "A3627"])
def test_c969_only_names_do_not_leak_into_other_norms(norm):
    from apps.license.services.product_classification import classify_product

    for description in ("Front Wheel Rim", "Air Filter", "Water pump"):
        assert classify_product("", description, norm) not in C969_CLASSIFIER_ORDER + tuple(
            name for name, _ in C969_GENERIC_CATEGORIES
        ) + (NO_DESCRIPTION, UNRECOGNISED)


# G: pivot aggregation and column order (real service, database).

@pytest.fixture
def c969_norm():
    head = HeadSIONNormsModel.objects.create(name="C969 pivot")
    return SionNormClassModel.objects.create(head_norm=head, norm_class="C969")


def _licence(number, norm):
    licence = LicenseDetailsModel.objects.create(license_number=number)
    LicenseExportItemModel.objects.create(license=licence, norm_class=norm, cif_fc=Decimal("1000.00"))
    return licence


@pytest.mark.django_db
def test_pivot_splits_unknown_lines_and_keeps_quantities(c969_norm):
    from apps.license.services.item_pivot_service import ItemPivotService

    licence = _licence("C969-SPLIT-001", c969_norm)
    lines = [
        ("Front Wheel Rim", Decimal("10")),
        ("Water pump", Decimal("5")),
        ("", Decimal("3")),
        ("(DELETED)", Decimal("2")),
        ("20", Decimal("7")),
    ]
    for serial, (description, qty) in enumerate(lines, start=1):
        LicenseImportItemsModel.objects.create(
            license=licence, serial_number=serial, description=description, quantity=qty, unit="kg",
        )

    rows = ItemPivotService.build([licence])["items"]
    by_category = {}
    for row in rows:
        by_category.setdefault(row.get("product_category"), Decimal("0"))
        by_category[row.get("product_category")] += Decimal(str(row.get("total_qty") or 0))

    assert "UNCLASSIFIED" not in by_category
    assert None not in by_category
    assert by_category["FRONT WHEELRIM"] == Decimal("10")
    assert by_category["WATER PUMP"] == Decimal("5")
    assert by_category[NO_DESCRIPTION] == Decimal("5")
    assert by_category[UNRECOGNISED] == Decimal("7")
