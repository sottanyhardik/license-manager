import pytest

from apps.license.services.product_classification import classify_product


def test_packing_material_hsn_44151000_is_pp_not_olive_oil():
    description = "PACKING MATERIAL (B) WOODEN SHEET / PALLETS 44151000"

    assert classify_product("44151000", description, "E5") == "PP"


def test_hsn_fragment_inside_longer_number_does_not_trigger_olive_oil():
    assert classify_product("44150000", "PACKING MATERIAL ITCHS CODE 44150000", "E5") == "PP"


def test_olive_oil_still_matches_standalone_heading_numbers():
    assert classify_product("15101000", "OLIVE OIL", "E5") == "OLIVE OIL"
    assert classify_product("", "15091000 EXTRA VIRGIN", "E5") == "OLIVE OIL"
    assert classify_product("", "15132110 PKO", "E5") == "PKO"
    assert classify_product("", "EDIBLE OIL HS 1510", "E5") == "OLIVE OIL"


PACKING_MATERIAL_DESCRIPTION = (
    "Packing Material:- (A) HDPE/LDPE/PP (B) Wooden Sheet / Pallets (HSN Code 44151000 ) "
    "1. 39021000 - PP 2. 48070030 - BB-Board 2/S Glazed-900 gsm in sheet form, "
    "3. 48115900 - PP Laminated board-380 gsm to 580 gsm roll form, "
    "4. 48041100 - Kraft Liner-135 gsm to 160 gsm roll form - (2,03,167.39) "
    "5. Wooden sheets / Pallets - (1,26,957.00)"
)


def test_e126_olive_signal_ignores_packing_material_with_hsn_44151000():
    from apps.license.services.e126_plan import classify_e126_record

    item, _reason = classify_e126_record("39021000", PACKING_MATERIAL_DESCRIPTION)

    assert item != "OLIVE OIL - E126"


def test_e126_olive_signal_still_matches_hsn_prefix_in_description():
    from apps.license.services.e126_plan import OLIVE_OIL, classify_e126_record

    item, _reason = classify_e126_record("", "15101000 EXTRA VIRGIN OLIVE OIL")

    assert item == OLIVE_OIL


@pytest.mark.parametrize("description, expected", [
    ("PP PACKING 7607 ALUMINIUM LAMINATED", "ALUMINIUM FOIL"),
    ("PP GRANULES PACKING MATERIAL", "PP"),
])
def test_hsn_39021000_is_aluminium_foil_only_when_description_has_7607(description, expected):
    assert classify_product("39021000", description, "A3627") == expected


@pytest.mark.parametrize("description, expected_pp", [
    ("PP PACKING 7607 ALUMINIUM LAMINATED", False),
    ("PP GRANULES PACKING MATERIAL", True),
])
def test_a3627_legacy_pp_rule_skips_7607_descriptions(description, expected_pp):
    from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS
    from apps.license.services.sion_rule_engine import evaluate_expression

    pp_rule = next(row for row in LEGACY_PLANNER_CONFIGURATIONS["A3627"]["rules"] if row["output_key"] == "PP")
    context = {"description": description, "hs_code": "39021000"}

    assert evaluate_expression(pp_rule["expression"], context) is expected_pp


@pytest.mark.parametrize("description", [
    "SUPPLY OF PACKING MATERIAL",
    "APPROX 12 KG PACKING",
])
def test_pp_word_is_whole_word_not_substring(description):
    assert classify_product("", description, "E5") != "PP"


def test_pp_laminated_board_hsn_48115900_is_not_pp():
    assert classify_product("48115900", "PP Laminated board-380 gsm to 580 gsm roll form", "E5") != "PP"


def test_pp_polypropylene_hsn_39021000_is_pp():
    assert classify_product("39021000", "PP (Polypropylene)", "E5") == "PP"


def test_olive_oil_is_not_assigned_from_packing_description_numbers():
    assert classify_product("39021000", PACKING_MATERIAL_DESCRIPTION, "E5") != "OLIVE OIL"


def test_other_confectionery_requires_hsn_0802_and_keyword_for_e1():
    # Spec: (HSN 0802 OR desc 0802) AND (desc CONFECTIONERY OR INGREDIENTS OR NUT), E1 only.
    assert classify_product("0802", "plain item", "E1") == "FOOD FLAVOUR"
    assert classify_product("0802", "confectionery nut mix", "E1") == "OTHER CONFECTIONERY"
    assert classify_product("08021100", "cashew nuts", "E1") == "OTHER CONFECTIONERY"


def test_other_confectionery_is_e1_only():
    assert classify_product("08021100", "cashew nuts", "E5") == "FOOD FLAVOUR"
    assert classify_product("08021100", "cashew nuts", "A3627") != "OTHER CONFECTIONERY"


def test_rutile_hsn_32061190_and_32061110_is_rutile_for_a3627():
    assert classify_product("32061190", "TITANIUM DIOXIDE RUTILE GRADE", "A3627") == "RUTILE"
    assert classify_product("32061110", "RUTILE", "A3627") == "RUTILE"


def test_other_than_rutile_is_never_rutile_in_pivot():
    assert classify_product("32061110", "Other Than Rutile Grade", "A3627") != "RUTILE"


def test_borax_hsn_28401900_is_borax_for_a3627():
    assert classify_product("28401900", "BORAX ANHYDROUS", "A3627") == "BORAX"
    assert classify_product("", "Borax pentahydrate", "A3627") == "BORAX"


def test_rutile_line_mentioning_borax_is_rutile_not_borax():
    assert classify_product("32061190", "Rutile with borax", "A3627") == "RUTILE"


def test_borax_and_rutile_are_a3627_only():
    assert classify_product("28401900", "BORAX", "E5") != "BORAX"
    assert classify_product("32061190", "RUTILE", "E5") != "RUTILE"


@pytest.mark.parametrize("hsn, description, expected", [
    ("32061190", "RUTILE", "RUTILE"),
    ("32061110", "Other Than Rutile Grade", "TITANIUM DIOXIDE"),
    ("3206", "RUTILE", "RUTILE"),
    ("3206", "Rutile glass formers with borax", "RUTILE"),
    ("3206", "Other Than Rutile Titanium Dioxide", "TITANIUM DIOXIDE"),
    ("", "Titanium Dioxide other than grade", "TITANIUM DIOXIDE"),
    ("3206", "Soda Ash with rutile formers", "SODA ASH"),
    ("28110000", "Silica", "SILICA"),
    ("28110000", "Fumed Silica", None),
    ("28401900", "BORAX", "BORAX"),
    ("", "Borax pentahydrate", "BORAX"),
])
def test_a3627_pivot_categories_match_matcher_rules(hsn, description, expected):
    assert classify_product(hsn, description, "A3627") == expected
