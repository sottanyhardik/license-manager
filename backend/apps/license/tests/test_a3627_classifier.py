"""Regression tests for the A3627 classification registry (Sr. Nos. 1, 6, 11, 17, 22).

Serial numbers do not gate classification (see a3627_classifier). The serial
invariance tests below prove that the same description gives the same product
whatever Sr. No. it is filed under.
"""
import pytest

from apps.license.services.a3627_classifier import AMBIGUOUS, CONFIRMED, UNMATCHED, classify_a3627
from apps.license.services.product_classification import classify_product

RUTILE_GLASS_FORMERS = (
    "Glass Formers namely:-(a) Silica (other than Fumed Silica)28110000 (b) Borax 28401900 "
    "(c) Phosphoric Acid 28092010 (d) Arsenic Trioxide 28112920 (e) Rutile 32061190 / 32061110 "
    "[Quantity of Borax do not exceed 10%]"
)


def _category(hsn, description, serial=None):
    return classify_a3627(serial, hsn, description).category


# --- Sr. No. 1: RUTILE --------------------------------------------------------

@pytest.mark.parametrize("hsn, description", [
    ("32061190", RUTILE_GLASS_FORMERS),
    ("32061110", "Glass Formers namely, (a) Silica (other than Fumed Silica) 28110000 (b) Borax 28401900"),
    ("28110000", "GLASS FORMERS NAMELY (A) SILICA (OTHER THAN FUMED SILICA) (B) BORAX / BORIC ACID (NOT EXCEEDING 0.10 PER KG OF EXPORT PRODUCT)"),
    ("28110000", "GLASS FORMERS NAMELY (A) BORAX / BORIC ACID 538643.93 KG (B) RUTILE 2800948.47"),
    ("28110000", "GLASS FORMERS NAMEY (A) SILICA (OTHER THAN FUMED SILICA) (B) BORAX/BORIC ACID"),
    ("3206", "RUTILE"),
    ("32061190", "Titanium Dioxide Rutile Grade"),
])
def test_sr1_glass_former_and_rutile_patterns_are_rutile(hsn, description):
    assert _category(hsn, description, serial=1) == "RUTILE"


def test_sr1_hsn_formatting_variants_are_normalized():
    assert _category("3206.11.90", "Glass Formers namely Rutile", serial=1) == "RUTILE"
    assert _category(" 3206 1190 ", "RUTILE", serial=1) == "RUTILE"


def test_sr1_rutile_is_not_restricted_to_serial_1():
    assert _category("32061190", RUTILE_GLASS_FORMERS, serial=9) == "RUTILE"


def test_sr1_silica_other_than_fumed_is_not_excluded_by_other_than():
    assert classify_a3627(1, "28110000", "SILICA (OTHER THAN FUMED SILICA)").category == "SILICA"


def test_sr1_plain_fumed_silica_is_not_silica():
    result = classify_a3627(None, "28110000", "Fumed Silica")
    assert result.category != "SILICA"


def test_sr1_rutile_hsn_alone_is_ambiguous_not_guessed():
    result = classify_a3627(1, "32061190", "")
    assert result.status == AMBIGUOUS
    assert result.category is None


def test_soda_ash_with_rutile_formers_is_not_rutile():
    assert _category("3206", "Soda Ash with rutile formers") == "SODA ASH"


# --- Sr. No. 17: Titanium Dioxide (mandatory negative test) -------------------

def test_sr17_titanium_dioxide_other_than_rutile_grade_is_not_rutile():
    """Mandatory: Sr. 17, HSN 32061110, 'other than Rutile Grade' must be Titanium Dioxide."""
    result = classify_a3627(17, "32061110", "Nucleating Agents (Titanium Dioxide other than Rutile Grade) 32061110")
    assert result.category == "TITANIUM DIOXIDE"
    assert result.category != "RUTILE"


@pytest.mark.parametrize("description", [
    "Titanium Dioxide other than Rutile Grade",
    "Other Than Rutile Grade",
    "Titanium Dioxide other than Rutile Grade and borax formers",
    "Other Special Additives namely:-(a) Clay 25080000 (b) Selenium 28049000 (c) Nucleating Agents (Titanium Dioxide other than Rutile Grade) 32061110 (d) Barium Carbonate 28366000",
    "OTHER SPECIAL ADDITIVES NAMELY , (A) CLAY (B) SELENIUM (C) NUCLEATING AGENTS (TITRANIUM DIOXIDE) (D) BARIUM CARBONATE",
])
def test_sr17_titanium_dioxide_variants_never_become_rutile(description):
    assert _category("32061110", description, serial=17) == "TITANIUM DIOXIDE"


def test_sr17_titanium_dioxide_with_rutile_and_borax_words_stays_titanium():
    assert _category("32061110", "Titanium Dioxide other than Rutile Grade, borax", serial=17) == "TITANIUM DIOXIDE"


# --- Sr. No. 6: Aluminium Oxide -----------------------------------------------

@pytest.mark.parametrize("hsn", ["28182000", "28170010", "28256010"])
def test_sr6_oxide_list_is_aluminium_oxide(hsn):
    description = "Intermediates namely:-(a) Aluminium Oxide 28182000 (b) Zinc Oxide 28170010 (c) Zirconium Oxide 28256010"
    assert _category(hsn, description, serial=6) == "ALUMINIUM OXIDE"


def test_sr6_requested_class_is_kept_for_zinc_and_zirconium_only_lines():
    assert _category("28170010", "Intermediates namely, Zinc Oxide 28170010", serial=6) == "ALUMINIUM OXIDE"


def test_sr6_oxide_list_naming_rutile_is_ambiguous_for_review():
    result = classify_a3627(6, "28182000", "INTERMEDIATES NAMELY (A) ALUMINIUM OXIDE (B) ZINC OXIDE (C) RUTILE (D) ZIRCONIUM OXIDE")
    assert result.status == AMBIGUOUS


def test_sr6_hsn_without_description_is_ambiguous():
    assert classify_a3627(6, "28182000", "").status == AMBIGUOUS


# --- Sr. No. 11: Soda Ash -----------------------------------------------------

@pytest.mark.parametrize("hsn", ["25199040", "28362010", "28342990", "28152000", "28342100"])
def test_sr11_modifiers_list_is_soda_ash(hsn):
    description = "Modifiers namely:- (a) Magnesium Oxide 25199040 (b) Soda Ash 28362010 (c) Sodium Nitrate 28342990 (d) Potash 28152000 (e) Potassium Nitrate 28342100"
    assert _category(hsn, description, serial=11) == "SODA ASH"


def test_sr11_soda_ash_hsn_alone_is_soda_ash():
    assert _category("28362010", "", serial=11) == "SODA ASH"


def test_sr11_soda_ash_conflicting_description_stays_soda_ash_by_request():
    assert _category("28362010", "Soda Ash 28362010 (rutile not present)", serial=11) == "SODA ASH"


# --- Sr. No. 22: PP, BB-Board, PP Laminated Board, Kraft Liner, Wooden --------

@pytest.mark.parametrize("description", ["PACKING MATERIAL :- PP", "Packing Material :- PP (146829.64) / Wooden Pallet (3374 pcs.)"])
def test_sr22_hsn_39021000_is_pp(description):
    assert classify_a3627(22, "39021000", description).category == "PP"


@pytest.mark.parametrize("description", [
    "BB-Board 2/S Glazed 900 gsm in sheet form",
    "BB Board 2 S Glazed 900gsm sheet form",
])
def test_sr22_bb_board_hsn_and_description_variants(description):
    assert _category("48070030", description, serial=22) == "BB-BOARD"


@pytest.mark.parametrize("description", [
    "PP Laminated board 380 gsm & 580 gsm in roll form",
    "PP Laminated Board-380 gsm to 580 gsm roll form",
])
def test_sr22_pp_laminated_board_hsn_and_description_variants(description):
    assert _category("48115900", description, serial=22) == "PP LAMINATED BOARD"


def test_sr22_kraft_liner_hsn_and_description():
    assert _category("48041100", "Kraft Liner 135 gsm to 160 gsm roll form", serial=22) == "KRAFT LINER"
    assert _category("", "Kraft Liner 135-160 GSM roll form", serial=22) == "KRAFT LINER"


@pytest.mark.parametrize("hsn, description", [
    ("44152000", "PACKING MATERIAL (B) WOODEN SHEET / PALLETS"),
    ("44150000", "PACKING MATERIAL (B) WOODEN SHEET / PALLETS 44151000"),
    ("", "Wooden Pallets"),
])
def test_sr22_wooden_sheets_pallets_are_not_pp(hsn, description):
    assert _category(hsn, description, serial=22) == "WOODEN SHEETS / PALLETS"


def test_sr22_composite_line_with_several_products_is_flagged_not_split():
    result = classify_a3627(22, "39021000", "PP - 1. 48070030 BB-Board 2/S Glazed 900 gsm, 2. 48115900 PP Laminated board 380 gsm")
    assert result.category == "PP"
    assert result.multi_product is True


# --- Serial invariance and norm isolation -------------------------------------

@pytest.mark.parametrize("serial", [1, 6, 11, 17, 22, 99])
def test_serial_number_never_changes_the_category(serial):
    assert _category("28182000", "Intermediates namely (a) Aluminium Oxide 28182000", serial=serial) == "ALUMINIUM OXIDE"
    assert _category("39021000", "PACKING MATERIAL :- PP", serial=serial) == "PP"


def test_unrelated_hsn_under_a3627_is_unmatched_not_forced():
    result = classify_a3627(3, "84719000", "Computer keyboard")
    assert result.status == UNMATCHED
    assert result.category is None


@pytest.mark.parametrize("hsn, description", [
    ("32061190", "RUTILE"),
    ("28401900", "BORAX"),
    ("28362010", "SODA ASH"),
    ("28182000", "ALUMINIUM OXIDE"),
])
def test_a3627_products_do_not_leak_into_other_norms(hsn, description):
    for norm in ("E1", "E5", "E132", "E126"):
        assert classify_product(hsn, description, norm) not in {"RUTILE", "BORAX", "SODA ASH", "ALUMINIUM OXIDE", "TITANIUM DIOXIDE"}


def test_pivot_categories_agree_with_registry_for_a3627():
    samples = [
        ("32061190", RUTILE_GLASS_FORMERS),
        ("32061110", "Titanium Dioxide other than Rutile Grade"),
        ("28362010", "SODA ASH"),
        ("39021000", "PACKING MATERIAL :- PP"),
        ("48070030", "BB-Board 2/S Glazed 900 gsm"),
        ("44152000", "PACKING MATERIAL (B) WOODEN SHEET / PALLETS"),
    ]
    for hsn, description in samples:
        expected = classify_a3627(None, hsn, description)
        assert classify_product(hsn, description, "A3627") == (expected.category if expected.status == CONFIRMED else None)


def test_chapter_48_paper_packaging_with_pp_word_is_not_pp():
    """HSN 4810 paper lines that also mention PP stay out of PP (the generic PAPER rule applies)."""
    result = classify_a3627(5, "48109900", "PACKAGING MATERIAL (A) PP/HDPE/LDPE/AND PAPER & PAPER BOARD")
    assert result.category != "PP"
    assert result.status == UNMATCHED
