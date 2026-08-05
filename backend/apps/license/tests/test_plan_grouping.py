from datetime import date
from decimal import Decimal

import pytest

from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.plan_grouping import (
    group_ids_of,
    merge_items_for_classification,
    plan_group_key,
    validate_fresh_plan_lines,
    validate_group_plan_lines,
)


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


@pytest.fixture
def company():
    return CompanyModel.objects.create(iec="3234567890", name="Grouping Exporter")


@pytest.fixture
def port():
    return PortModel.objects.create(code="INGRP1", name="Grouping Port")


@pytest.fixture
def license_obj(company, port):
    return LicenseDetailsModel.objects.create(
        license_number="PLAN-GROUP-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )


def _import_item(license_obj, serial_number, description="", hs_code=None):
    return LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=serial_number,
        description=description,
        hs_code=hs_code,
        quantity=Decimal("10.000"),
        available_quantity=Decimal("10.000"),
    )


@pytest.mark.django_db
def test_plan_grouping_uses_trimmed_uppercase_description(license_obj):
    item_a = _import_item(license_obj, 1, "  Refined Sugar ")
    item_b = _import_item(license_obj, 2, "refined sugar")
    item_c = _import_item(license_obj, 3, "Raw Sugar")

    # No HSN set on any of these — key is "|<description>" (empty HSN part).
    assert plan_group_key(item_a) == "|REFINED SUGAR"
    assert group_ids_of(item_a) == [item_a.id, item_b.id]
    assert group_ids_of(item_c) == [item_c.id]


@pytest.mark.django_db
def test_plan_grouping_falls_back_to_sorted_item_names(license_obj):
    borax = ItemNameModel.objects.create(name="borax")
    rutile = ItemNameModel.objects.create(name="Rutile")
    item = _import_item(license_obj, 1)
    item.items.add(rutile, borax)

    assert plan_group_key(item) == "|N:BORAX, RUTILE"
    assert group_ids_of(item) == [item.id]


@pytest.mark.django_db
def test_plan_grouping_never_merges_when_hsn_differs(license_obj):
    # Same normalized description, DIFFERENT HSN — must be two separate
    # groups even though the old (description-only) key would have pooled
    # them. This is the real-world scenario this change targets.
    item_a = _import_item(license_obj, 1, "Cane Sugar", hs_code=_hs("17029020"))
    item_b = _import_item(license_obj, 2, "Cane Sugar", hs_code=_hs("17029090"))

    assert plan_group_key(item_a) != plan_group_key(item_b)
    assert group_ids_of(item_a) == [item_a.id]
    assert group_ids_of(item_b) == [item_b.id]


@pytest.mark.django_db
def test_plan_grouping_merges_same_hsn_and_normalized_description(license_obj):
    hsn = _hs("29181400")
    item_a = _import_item(license_obj, 1, "  Tartaric Acid ", hs_code=hsn)
    item_b = _import_item(license_obj, 2, "tartaric  acid", hs_code=hsn)  # double space + case
    item_c = _import_item(license_obj, 3, "Tartaric Acid", hs_code=_hs("29181200"))

    assert plan_group_key(item_a) == plan_group_key(item_b)
    assert group_ids_of(item_a) == [item_a.id, item_b.id]
    # Same description, different HSN -> never grouped with a or b.
    assert item_c.id not in group_ids_of(item_a)
    assert group_ids_of(item_c) == [item_c.id]


@pytest.mark.django_db
def test_plan_grouping_real_world_mixed_hsn_description_group(license_obj):
    # Reproduces license 0311009149's real shape: three import items share
    # one description but split across two HSNs (29181400 / 29181200). The
    # old description-only key pooled all three into one group (capacity
    # 9458.810 + 153.000 + 549.110 = 10160.920, and a real saved plan used
    # exactly that pooled total). Under the new HSN-aware key, the HSN
    # 29181400 item is its own group with its own smaller capacity — this
    # regression pins that split so a `bulk_upsert` capacity check exercised
    # against it is provably correct, not accidentally still pooling.
    desc = "RELEVANT TARTARIC ACID (FOOD GRADE RELEVANT )"
    item_29181400 = _import_item(license_obj, 4, desc, hs_code=_hs("29181400"))
    item_29181200_a = _import_item(license_obj, 14, desc, hs_code=_hs("29181200"))
    item_29181200_b = _import_item(license_obj, 24, desc, hs_code=_hs("29181200"))

    assert group_ids_of(item_29181400) == [item_29181400.id]
    assert group_ids_of(item_29181200_a) == sorted([item_29181200_a.id, item_29181200_b.id])


def test_plan_grouping_handles_invalid_inputs_without_queries():
    assert plan_group_key(None) == "ID:None"
    assert group_ids_of(None) == []
    assert group_ids_of(LicenseImportItemsModel(description="Unsaved")) == []


@pytest.mark.django_db
def test_merge_items_for_classification_groups_by_plan_group_key(license_obj):
    hsn = _hs("29181400")
    item_a = _import_item(license_obj, 1, "  Tartaric Acid ", hs_code=hsn)
    item_b = _import_item(license_obj, 2, "tartaric  acid", hs_code=hsn)  # same group as a
    item_c = _import_item(license_obj, 3, "Tartaric Acid", hs_code=_hs("29181200"))  # different HSN -> own group

    groups = merge_items_for_classification(
        LicenseImportItemsModel.objects.filter(license=license_obj).select_related("hs_code").prefetch_related("items")
    )
    by_rep = {g['representative_id']: g for g in groups}

    merged = by_rep[item_a.id]
    assert merged['member_ids'] == [item_a.id, item_b.id]
    assert merged['available_quantity'] == Decimal("20.000")
    assert merged['hs_code'] == "29181400"

    solo = by_rep[item_c.id]
    assert solo['member_ids'] == [item_c.id]
    assert solo['available_quantity'] == Decimal("10.000")


@pytest.mark.django_db
def test_merge_items_for_classification_normalizes_slash_spacing(license_obj):
    # Real DGFT license data carries inconsistent slash-spacing for the SAME
    # physical product (module docstring's "Fruit /Juice" example, HSN
    # 20089991) — `merge_items_for_classification` must pool these into one
    # group, the same way `plan_group_key`/`_normalize_text` already do for
    # the display/enforcement layers, so Auto-Plan never splits one product
    # across multiple lines just because of cosmetic slash spacing.
    hsn = _hs("20089991")
    item_a = _import_item(license_obj, 1, "Fruit /Juice", hs_code=hsn)
    item_b = _import_item(license_obj, 2, "Fruit/ Juice", hs_code=hsn)
    item_c = _import_item(license_obj, 3, "Fruit / Juice", hs_code=hsn)

    groups = merge_items_for_classification(
        LicenseImportItemsModel.objects.filter(license=license_obj).select_related("hs_code").prefetch_related("items")
    )
    assert len(groups) == 1
    assert groups[0]['member_ids'] == [item_a.id, item_b.id, item_c.id]
    assert groups[0]['available_quantity'] == Decimal("30.000")


@pytest.mark.django_db
def test_merge_items_for_classification_representative_is_lowest_serial_not_lowest_id(license_obj):
    # The group's representative must be the LOWEST SERIAL_NUMBER member —
    # this app's own documented convention (module docstring: "a group's
    # plan is stored on its representative import item, lowest serial
    # number"), matching E1/E5's real `auto_plan_shared.group_by_desc`
    # behavior. Create the HIGHER-serial item FIRST (so it gets the LOWER
    # DB id) to prove serial_number decides it, not id or creation order —
    # this is exactly the DGFT-resync shape found in real dev-DB data,
    # where ids and serial numbers can end up in different orders.
    hsn = _hs("17023010")
    higher_serial_lower_id = _import_item(license_obj, 12, "Liquid Glucose", hs_code=hsn)
    lower_serial_higher_id = _import_item(license_obj, 2, "Liquid Glucose", hs_code=hsn)
    assert higher_serial_lower_id.id < lower_serial_higher_id.id  # sanity: ids really are reversed vs serials

    groups = merge_items_for_classification(
        LicenseImportItemsModel.objects.filter(license=license_obj).select_related("hs_code").prefetch_related("items")
    )
    assert len(groups) == 1
    assert groups[0]['representative_id'] == lower_serial_higher_id.id
    assert groups[0]['representative_id'] != higher_serial_lower_id.id


@pytest.mark.django_db
def test_merge_items_for_classification_unions_item_name_tags(license_obj):
    # Two serials of the same physical product (same HSN+description), but
    # only one is M2M-tagged. `classify_e1_item`/`classify_e5_item` partly
    # key off item-name text, so the merged group must expose EVERY tag any
    # member carries, not just the representative's — this is what lets the
    # whole group classify consistently instead of splitting.
    tagged_name = ItemNameModel.objects.create(name="Other Confectionery Ingredients - E1")
    hsn = _hs("99999999")
    item_a = _import_item(license_obj, 1, "Bulk Ingredient Mix", hs_code=hsn)
    item_a.items.add(tagged_name)
    item_b = _import_item(license_obj, 2, "Bulk Ingredient Mix", hs_code=hsn)  # untagged

    groups = merge_items_for_classification(
        LicenseImportItemsModel.objects.filter(license=license_obj).select_related("hs_code").prefetch_related("items")
    )
    assert len(groups) == 1
    group = groups[0]
    assert group['member_ids'] == [item_a.id, item_b.id]
    assert group['item_names'] == ["Other Confectionery Ingredients - E1"]
    assert group['available_quantity'] == Decimal("20.000")


class TestValidateGroupPlanLines:
    """Unit tests for the shared validation gate every Auto-Plan engine
    (E1, E5, E126, E132) runs before accepting a group's plan lines."""

    _PRICES = {"PKO": Decimal("1.80"), "OLIVE OIL": Decimal("5.00")}

    def test_fresh_lines_within_price_and_qty_pass(self):
        lines = [
            {"unit_price": 1.80, "planned_quantity": 40.0},
            {"unit_price": 5.00, "planned_quantity": 60.0},
        ]
        assert validate_group_plan_lines(
            lines, ["PKO", "OLIVE OIL"], Decimal("100"), self._PRICES, is_preserved=False,
        ) is True

    def test_fresh_lines_exceeding_available_quantity_are_rejected(self):
        lines = [{"unit_price": 1.80, "planned_quantity": 150.0}]
        assert validate_group_plan_lines(
            lines, ["PKO"], Decimal("100"), self._PRICES, is_preserved=False,
        ) is False

    def test_price_above_ceiling_is_rejected_even_when_preserved(self):
        # A preserved line's quantity is exempt from the availability check,
        # but a price above the fixed ceiling is NEVER legitimate, preserved
        # or not — this is exactly what caught the reported production bug
        # ($4.84 PKO price, ceiling $1.80).
        lines = [{"unit_price": 4.84, "planned_quantity": 40.0}]
        assert validate_group_plan_lines(
            lines, ["PKO"], Decimal("10"), self._PRICES, is_preserved=True,
        ) is False

    def test_preserved_lines_exceeding_available_quantity_still_pass(self):
        # The core "fixed once generated" business rule: a preserved split's
        # quantity is intentionally NOT re-validated against the group's
        # current available_quantity — only fresh computations are.
        lines = [
            {"unit_price": 1.80, "planned_quantity": 40.0},
            {"unit_price": 5.00, "planned_quantity": 60.0},
        ]
        assert validate_group_plan_lines(
            lines, ["PKO", "OLIVE OIL"], Decimal("10"), self._PRICES, is_preserved=True,
        ) is True

    def test_price_exactly_at_ceiling_passes(self):
        lines = [{"unit_price": 1.80, "planned_quantity": 40.0}]
        assert validate_group_plan_lines(
            lines, ["PKO"], Decimal("100"), self._PRICES, is_preserved=False,
        ) is True

    def test_price_below_ceiling_passes(self):
        # A legitimately capped/reduced effective rate (balance-constrained
        # waterfall) must never be rejected — only prices ABOVE the ceiling.
        lines = [{"unit_price": 0.50, "planned_quantity": 40.0}]
        assert validate_group_plan_lines(
            lines, ["PKO"], Decimal("100"), self._PRICES, is_preserved=False,
        ) is True


class TestValidateFreshPlanLines:
    """Unit tests for the lighter validation gate E1/E5 run — no
    price-ceiling check (see `validate_fresh_plan_lines`'s docstring for
    why), just non-negative values and qty-vs-available."""

    def test_valid_lines_pass(self):
        lines = [
            {"planned_quantity": 40.0, "planned_cif_fc": 72.0},
            {"planned_quantity": 60.0, "planned_cif_fc": 330.0},
        ]
        assert validate_fresh_plan_lines(lines, Decimal("100")) is True

    def test_quantity_exceeding_available_is_rejected(self):
        lines = [{"planned_quantity": 150.0, "planned_cif_fc": 300.0}]
        assert validate_fresh_plan_lines(lines, Decimal("100")) is False

    def test_negative_quantity_is_rejected(self):
        lines = [{"planned_quantity": -1.0, "planned_cif_fc": 10.0}]
        assert validate_fresh_plan_lines(lines, Decimal("100")) is False

    def test_negative_cif_is_rejected(self):
        lines = [{"planned_quantity": 10.0, "planned_cif_fc": -5.0}]
        assert validate_fresh_plan_lines(lines, Decimal("100")) is False

    def test_quantity_exactly_at_available_passes(self):
        lines = [{"planned_quantity": 100.0, "planned_cif_fc": 300.0}]
        assert validate_fresh_plan_lines(lines, Decimal("100")) is True

    def test_no_price_ceiling_check_arbitrarily_high_price_still_passes(self):
        # Unlike validate_group_plan_lines, there's no unit_price_map
        # parameter at all — an arbitrarily high implied rate is not this
        # function's concern (E1/E5 have no fixed ceiling to check).
        lines = [{"planned_quantity": 1.0, "planned_cif_fc": 999999.0}]
        assert validate_fresh_plan_lines(lines, Decimal("100")) is True
