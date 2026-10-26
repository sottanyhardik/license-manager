"""Item pivot split of C969 lines into named categories (no single UNCLASSIFIED bucket)."""
import pytest

from apps.license.services.c969_product_classifier import (
    C969_CATEGORY_ORDER,
    NO_DESCRIPTION,
    UNRECOGNISED,
    classify_c969_category,
)


@pytest.mark.parametrize(
    "description, category",
    [
        ("Front Wheel Rim", "FRONT WHEELRIM"),
        ("HOT ROLLED STEEL (SHEETS/WIDE COILS) -7208, 7209", "HOT ROLLED STEEL"),
        ("HOT ROLLED / COLD ROLLED STEEL (SHEETS/WIDE COILS) - 7208 & 7209", "COLD ROLLED STEEL"),
        ("Hydrostatic Unit/ Valves for Hydraulic Transmission", "HYDROSTATIC TRANSMISSION"),
        ("frontwheel tyretube", "FRONTWHEEL TYRE"),
        ("rearwheel tyre", "REARWHEEL TYRE"),
        ("Water pump seal", "WATER PUMP"),
        ("Oil Seal (other than Engine) NET TO NET", "OIL SEAL"),
        ("oil seperator", "OIL SEPERATOR"),
        ("Fuel injection pump", "FUEL INJECTION PUMP"),
        ("auxiliary valves", "AUXILIARY VALVES"),
        ("synchropacks", "SYNCHROPACKS"),
        ("Safety neutral switch", "SAFETY NEUTRAL SWITCH"),
        ("'O' Ring", "'O' RING"),
    ],
)
def test_generic_lines_get_their_product_category(description, category):
    assert classify_c969_category(description) == category


@pytest.mark.parametrize("description", [None, "", "   ", "(DELETED)"])
def test_blank_or_deleted_lines_go_to_no_description(description):
    assert classify_c969_category(description) == NO_DESCRIPTION


@pytest.mark.parametrize("description", ["20", "CARBON CONTENTS LESS THAN 2 PERCENT HS CODE 7228"])
def test_lines_that_name_no_product_go_to_unrecognised(description):
    assert classify_c969_category(description) == UNRECOGNISED


def test_twenty_two_mapping_takes_precedence_over_generic_rules():
    assert classify_c969_category("Hydraulic Pump (Including Auxiliary hydraulic Pump)") == "HYDRAULIC PUMP"


def test_every_category_is_in_the_display_order_and_never_none():
    for description in ["Air Filter", "Water Pump", "", "20", "Relevant Radiator line"]:
        assert classify_c969_category(description) in C969_CATEGORY_ORDER


def test_category_order_has_the_22_then_the_generic_then_the_buckets():
    assert C969_CATEGORY_ORDER[0] == "AIR FILTER"
    assert C969_CATEGORY_ORDER[-2:] == (NO_DESCRIPTION, UNRECOGNISED)
    assert "WATER PUMP" in C969_CATEGORY_ORDER
    assert len(C969_CATEGORY_ORDER) == len(set(C969_CATEGORY_ORDER))
