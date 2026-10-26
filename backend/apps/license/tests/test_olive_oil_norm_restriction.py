"""Business rule: norm classes A3627 and E132 must never be classified as Olive Oil."""
import pytest
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.core.models import HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.auto_plan_shared import ensure_plan_item_names
from apps.license.services.product_classification import classify_product
from apps.license.services.product_norm_guard import (
    guard_product_for_norm,
    is_olive_oil_allowed,
    is_olive_oil_item_name_allowed,
)
from apps.license.utils.item_matcher import match_import_item_to_items

PACKING_MATERIAL_DESCRIPTION = (
    "Packing Material:- (A) HDPE/LDPE/PP (B) Wooden Sheet / Pallets (HSN Code 44151000 ) "
    "1. 39021000 - PP 2. 48070030 - BB-Board 2/S Glazed-900 gsm in sheet form, "
    "3. 48115900 - PP Laminated board-380 gsm to 580 gsm roll form, "
    "4. 48041100 - Kraft Liner-135 gsm to 160 gsm roll form - (2,03,167.39) "
    "5. Wooden sheets / Pallets - (1,26,957.00)"
)


@pytest.fixture
def a3627_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="A3627 Norms")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="A3627")


@pytest.fixture
def e132_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="E132 Norms")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E132")


@pytest.fixture
def e5_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="E5 Norms")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E5")


# ─── Central validation rule ────────────────────────────────────────────────


@pytest.mark.parametrize("norm", ["A3627", "E132", "  a3627 ", "e132", "\tE132\n"])
@pytest.mark.parametrize("product", ["OLIVE OIL", "  olive   oil ", "Olive Oil"])
def test_restricted_norms_reject_olive_oil_regardless_of_case_and_whitespace(norm, product):
    assert is_olive_oil_allowed(norm, product) is False


@pytest.mark.parametrize("norm", ["E5", "E126", "E1", "", None])
def test_valid_olive_oil_norms_are_allowed(norm):
    assert is_olive_oil_allowed(norm, "OLIVE OIL") is True


@pytest.mark.parametrize("norm", ["A3627", "E132"])
def test_restricted_norms_still_allow_other_products(norm):
    assert is_olive_oil_allowed(norm, "PP") is True
    assert is_olive_oil_allowed(norm, "RBD PALMOLEIN OIL") is True


def test_guard_returns_none_instead_of_substituting_another_product():
    assert guard_product_for_norm("E132", "OLIVE OIL") is None
    assert guard_product_for_norm("E5", "OLIVE OIL") == "OLIVE OIL"


# ─── Product classification path ────────────────────────────────────────────


@pytest.mark.parametrize("norm", ["A3627", "E132", " a3627 "])
def test_classify_product_hsn_prefix_never_yields_olive_oil_for_restricted_norm(norm):
    assert classify_product("15091000", "EXTRA VIRGIN", norm) is None
    assert classify_product("15101000", "OLIVE OIL", norm) is None


def test_classify_product_description_substring_never_yields_olive_oil_for_restricted_norm():
    assert classify_product("", "EDIBLE OIL HS 1510", "E132") is None


def test_classify_product_fallback_cannot_turn_restricted_olive_into_another_olive_rule():
    # HSN 1509 is olive by rule; for a restricted norm the result is manual review (None),
    # not a silent fallthrough to a lower-priority product.
    # The guard is about Olive Oil only: the line may fall to PP (matcher agrees), never OLIVE OIL.
    assert classify_product("15091000", "PP GRANULES 1509", "A3627") != "OLIVE OIL"


def test_classify_product_packing_material_is_not_olive_oil_under_restricted_norms():
    assert classify_product("44151000", PACKING_MATERIAL_DESCRIPTION, "E132") != "OLIVE OIL"
    assert classify_product("44151000", PACKING_MATERIAL_DESCRIPTION, "A3627") != "OLIVE OIL"
    assert classify_product("39021000", "PP (Polypropylene)", "A3627") == "PP"


def test_valid_olive_oil_classification_under_other_norm_is_unchanged():
    assert classify_product("15101000", "OLIVE OIL", "E5") == "OLIVE OIL"
    assert classify_product("15091000", "EXTRA VIRGIN", "E126") == "OLIVE OIL"


# ─── Item matching path (fallback and HSN-prefix rules) ─────────────────────


@pytest.fixture
def olive_filter_for_all_norms(monkeypatch):
    """Offer Olive Oil to every norm via an HSN-prefix rule, so the guard is the only thing blocking it."""
    monkeypatch.setattr(
        "apps.license.utils.item_matcher.get_item_filters",
        lambda: [{
            "base_name": "OLIVE OIL",
            "norms": ["A3627", "E132", "E5"],
            "filters": [Q(hs_code__hs_code__startswith="1509")],
        }],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("restricted_norm", ["A3627", "E132"])
def test_matcher_never_links_olive_oil_to_restricted_norm_via_hsn_prefix(
    olive_filter_for_all_norms, restricted_norm,
):
    hs_code = HSCodeModel.objects.create(hs_code="15091000")
    license_obj = LicenseDetailsModel.objects.create(license_number=f"RESTRICT-{restricted_norm}-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Olive oil",
    )

    assert not match_import_item_to_items(import_item, [restricted_norm]).exists()


@pytest.mark.django_db
def test_matcher_still_links_olive_oil_for_valid_e5_norm(olive_filter_for_all_norms, e5_norm):
    expected = ItemNameModel.objects.create(name="OLIVE OIL - E5", sion_norm_class=e5_norm)
    hs_code = HSCodeModel.objects.create(hs_code="15091000")
    license_obj = LicenseDetailsModel.objects.create(license_number="RESTRICT-E5-OK-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Olive oil",
    )

    assert list(match_import_item_to_items(import_item, ["E5"])) == [expected]


# ─── Database mapping path (signals + plan item creation) ───────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("norm_code", ["A3627", "E132"])
def test_database_rejects_olive_oil_item_name_on_restricted_norm(norm_code):
    head_norm = HeadSIONNormsModel.objects.create(name=f"{norm_code} head")
    norm_obj = SionNormClassModel.objects.create(head_norm=head_norm, norm_class=norm_code)

    with pytest.raises(ValidationError):
        ItemNameModel.objects.create(name=f"OLIVE OIL - {norm_code}", sion_norm_class=norm_obj)


@pytest.mark.django_db
def test_database_rejects_linking_olive_oil_name_to_restricted_norm(a3627_norm, e5_norm):
    item_name = ItemNameModel.objects.create(name="OLIVE OIL - E5", sion_norm_class=e5_norm)

    with pytest.raises(ValidationError):
        item_name.norms.add(a3627_norm)


@pytest.mark.django_db
def test_plan_item_name_creation_cannot_create_olive_oil_for_restricted_norm(a3627_norm):
    with pytest.raises(ValidationError):
        ensure_plan_item_names([("OLIVE OIL - A3627", "A3627")])


@pytest.mark.django_db
def test_database_still_allows_valid_olive_oil_item_name(e5_norm):
    item_name = ItemNameModel.objects.create(name="OLIVE OIL - E5", sion_norm_class=e5_norm)

    assert item_name.pk is not None


@pytest.mark.django_db
def test_database_still_allows_packing_item_names_on_restricted_norm(a3627_norm, e132_norm):
    ensure_plan_item_names([("PP - A3627", "A3627"), ("PP - E132", "E132")])

    assert ItemNameModel.objects.filter(name="PP - A3627").exists()
    assert ItemNameModel.objects.filter(name="PP - E132").exists()


def test_item_name_guard_ignores_non_olive_names_and_unrestricted_norms():
    assert is_olive_oil_item_name_allowed("PP - A3627", ["A3627"]) is True
    assert is_olive_oil_item_name_allowed("OLIVE OIL - E5", ["E5"]) is True
    assert is_olive_oil_item_name_allowed("OLIVE OIL - A3627", ["A3627"]) is False
