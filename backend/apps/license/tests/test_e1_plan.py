"""Unit tests for the E1 utilization-planning engine (``plan_e1_items``)."""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.e1_plan import (
    EGG_ALBUMIN_PRICE,
    E1_CATS,
    E1_UNIT_PRICES,
    E1Item,
    E1PlanLine,
    classify_e1_item,
    plan_e1_items,
)


def _lines_by_step(result, step) -> list[E1PlanLine]:
    return [ln for ln in result.lines if ln.step == step]


def _cif(result, step) -> Decimal:
    return sum((ln.planned_cif for ln in _lines_by_step(result, step)), Decimal('0'))


class TestClassifyE1Item(TestCase):
    """Item / HSN / description bucketing — precedence mirrors the 8-step
    waterfall order exactly."""

    def test_other_confectionery_by_hsn_0802(self):
        assert classify_e1_item('ANY', '08021100', '') == 'OTHER CONFECTIONERY INGREDIENTS'

    def test_other_confectionery_by_item_name(self):
        assert classify_e1_item('Other Confectionery Ingredients', '', '') == \
            'OTHER CONFECTIONERY INGREDIENTS'

    def test_other_confectionery_by_description(self):
        assert classify_e1_item('ANY', '', 'Other Confectionery blend') == \
            'OTHER CONFECTIONERY INGREDIENTS'

    def test_cocoa_mass_by_hsn_1803(self):
        assert classify_e1_item('ANY', '18031000', '') == 'COCOA MASS'

    def test_cocoa_mass_by_description_containing_1803(self):
        assert classify_e1_item('ANY', '', 'Cocoa mass HSN 1803 grade') == 'COCOA MASS'

    def test_milk_products_requires_0404_and_milk_in_description(self):
        assert classify_e1_item('ANY', '04041000', 'Skimmed Milk Powder') == 'MILK PRODUCTS'

    def test_milk_products_hsn_alone_without_milk_word_does_not_classify(self):
        # New rule requires description to actually say "milk" — a bare 0404
        # HSN with no "milk" wording in the description is not enough.
        assert classify_e1_item('ANY', '04041000', 'Whey concentrate') is None

    def test_milk_products_by_description_0404_and_milk(self):
        assert classify_e1_item('ANY', '', 'contains 0404 milk product') == 'MILK PRODUCTS'

    def test_milk_excluded_when_1803_also_present(self):
        # Cocoa (step 2) wins over Milk (step 3) — 1803 excludes milk.
        assert classify_e1_item('ANY', '18030404', 'Milk Chocolate Cocoa 1803') == 'COCOA MASS'

    def test_egg_albumin_by_hsn_3502(self):
        assert classify_e1_item('ANY', '35021100', '') == 'EGG ALBUMIN'

    def test_egg_albumin_excluded_when_0404_present(self):
        assert classify_e1_item('ANY', '', 'contains 0404 and 3502 codes') is None

    def test_fruit_juice_by_hsn_2009(self):
        assert classify_e1_item('ANY', '20091100', '') == 'FRUIT JUICE'

    def test_fruit_juice_by_description(self):
        assert classify_e1_item('ANY', '', 'Mixed Fruit Juice concentrate') == 'FRUIT JUICE'

    def test_tartaric_acid_by_hsn_2918(self):
        assert classify_e1_item('ANY', '29182000', '') == 'TARTARIC ACID'

    def test_tartaric_acid_by_item_name(self):
        assert classify_e1_item('Tartaric Acid', '', '') == 'TARTARIC ACID'

    def test_tartaric_acid_by_description(self):
        assert classify_e1_item('ANY', '', 'Tartaric acid food grade') == 'TARTARIC ACID'

    def test_aluminium_foil_by_hsn_7607(self):
        assert classify_e1_item('ANY', '76071190', '') == 'ALUMINIUM FOIL'

    def test_aluminium_foil_item_name_alone_does_not_classify(self):
        # HSN-only rule now — the words "Aluminium Foil" alone (no HSN 7607,
        # no literal "7607" text) must not classify.
        assert classify_e1_item('Aluminium Foil', '', '') is None

    def test_aluminium_foil_description_words_alone_do_not_classify(self):
        assert classify_e1_item('ANY', '', 'Aluminium Foil 9 micron') is None

    def test_aluminium_foil_by_item_name_containing_7607(self):
        assert classify_e1_item('Foil 7607', '', '') == 'ALUMINIUM FOIL'

    def test_aluminium_foil_by_description_containing_7607(self):
        assert classify_e1_item('ANY', '', 'Packing material 7607') == 'ALUMINIUM FOIL'

    def test_polypropylene_by_hsn_3902(self):
        assert classify_e1_item('ANY', '39021000', '') == 'POLYPROPYLENE'

    def test_polypropylene_by_item_name_pp_alone_does_not_classify(self):
        # HSN-only rule now — the word "PP"/"Polypropylene" alone must not
        # classify without a qualifying HSN 3902 code.
        assert classify_e1_item('PP', '', '') is None

    def test_polypropylene_by_description_word_alone_does_not_classify(self):
        assert classify_e1_item('Polypropylene Granules', '', '') is None

    def test_polypropylene_excluded_when_hsn_is_7607(self):
        assert classify_e1_item('ANY', '76071190', '') == 'ALUMINIUM FOIL'

    def test_polypropylene_excluded_when_description_contains_7607(self):
        # Even with a qualifying 3902 HSN, a 7607 mention in the description
        # routes to Aluminium Foil, never PP.
        assert classify_e1_item('ANY', '39021000', 'PP/Foil laminate 7607') == 'ALUMINIUM FOIL'

    def test_unclassified_returns_none(self):
        assert classify_e1_item('SUGAR', '17019990', 'Refined Cane Sugar') is None

    def test_priority_other_confectionery_beats_everything_else(self):
        assert classify_e1_item('Other Confectionery Ingredients', '04041000', 'Milk') == \
            'OTHER CONFECTIONERY INGREDIENTS'

    def test_priority_aluminium_beats_polypropylene_when_both_present(self):
        assert classify_e1_item('ANY', '76073902', '') == 'ALUMINIUM FOIL'

    def test_case_insensitive_and_trimmed(self):
        assert classify_e1_item('  other confectionery ingredients  ', '', '') == \
            'OTHER CONFECTIONERY INGREDIENTS'
        assert classify_e1_item('  TARTARIC ACID  ', '', '') == 'TARTARIC ACID'

    def test_hsn_prefix_matching_ignores_trailing_digits(self):
        # 18030000 / 18031090 / 18039020 all match prefix "1803".
        for hsn in ('18030000', '18031090', '18039020'):
            assert classify_e1_item('ANY', hsn, '') == 'COCOA MASS'

    def test_hsn_with_spaces_and_dashes_still_matches_prefix(self):
        assert classify_e1_item('ANY', '0802-11-00', '') == 'OTHER CONFECTIONERY INGREDIENTS'

    def test_null_blank_and_unicode_inputs_are_safe(self):
        assert classify_e1_item(None, None, None) is None
        assert classify_e1_item('', '   ', '   ') is None
        assert classify_e1_item('ANY', '', 'Aluminium foil \U0001f4e6 7607') == 'ALUMINIUM FOIL'


class TestUnitPricesTable(TestCase):

    def test_e1_unit_prices(self):
        assert E1_UNIT_PRICES['OTHER CONFECTIONERY INGREDIENTS'] == Decimal('3.00')
        assert E1_UNIT_PRICES['COCOA MASS'] == Decimal('10.00')
        assert E1_UNIT_PRICES['FRUIT JUICE'] == Decimal('2.50')
        assert E1_UNIT_PRICES['TARTARIC ACID'] == Decimal('1.50')
        assert E1_UNIT_PRICES['ALUMINIUM FOIL'] == Decimal('4.50')
        assert E1_UNIT_PRICES['POLYPROPYLENE'] == Decimal('1.20')

    def test_egg_albumin_reuses_shared_milk_config_wpc_price(self):
        assert EGG_ALBUMIN_PRICE == Decimal('25')


class TestGenericStages(TestCase):
    """Steps 1, 2, 4-8 — full balance (max rate) vs partial balance
    (rate = remaining / total qty)."""

    def test_other_confectionery_full_balance_at_max_rate(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('1000'))
        assert _cif(result, 'OTHER CONFECTIONERY INGREDIENTS') == Decimal('300.0000')
        assert result.lines[0].unit_price == Decimal('3.0000')
        assert result.lines[0].planned_qty == Decimal('100')  # full qty always planned

    def test_other_confectionery_partial_balance_reduces_rate_not_qty(self):
        # 100 * 3.00 = 300 > remaining(120) -> rate = 120/100 = 1.20, full qty still planned.
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('120'))
        line = result.lines[0]
        assert line.planned_qty == Decimal('100')
        assert line.unit_price == Decimal('1.2000')
        assert line.planned_cif == Decimal('120.0000')
        assert result.remaining_cif == Decimal('0')

    def test_cocoa_mass_allocation(self):
        items = [E1Item(key='a', category='COCOA MASS', qty=Decimal('10'))]
        result = plan_e1_items(items, Decimal('1000'))
        assert _cif(result, 'COCOA MASS') == Decimal('100.0000')

    def test_egg_albumin_allocation_at_25(self):
        items = [E1Item(key='a', category='EGG ALBUMIN', qty=Decimal('10'))]
        result = plan_e1_items(items, Decimal('5000'))
        assert _cif(result, 'EGG ALBUMIN') == Decimal('250.0000')

    def test_fruit_juice_allocation(self):
        items = [E1Item(key='a', category='FRUIT JUICE', qty=Decimal('200'))]
        result = plan_e1_items(items, Decimal('5000'))
        assert _cif(result, 'FRUIT JUICE') == Decimal('500.0000')  # 200 * $2.50
        assert result.lines[0].unit_price == Decimal('2.5000')

    def test_fruit_juice_partial_balance_reduces_rate_not_qty(self):
        # 200 * 2.50 = 500 > remaining(300) -> rate = 300/200 = 1.50, full qty still planned.
        items = [E1Item(key='a', category='FRUIT JUICE', qty=Decimal('200'))]
        result = plan_e1_items(items, Decimal('300'))
        line = result.lines[0]
        assert line.planned_qty == Decimal('200')
        assert line.unit_price == Decimal('1.5000')
        assert line.planned_cif == Decimal('300.0000')
        assert result.remaining_cif == Decimal('0')

    def test_tartaric_acid_allocation(self):
        items = [E1Item(key='a', category='TARTARIC ACID', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('5000'))
        assert _cif(result, 'TARTARIC ACID') == Decimal('150.0000')

    def test_aluminium_foil_allocation(self):
        items = [E1Item(key='a', category='ALUMINIUM FOIL', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('5000'))
        assert _cif(result, 'ALUMINIUM FOIL') == Decimal('450.0000')

    def test_polypropylene_allocation(self):
        items = [E1Item(key='a', category='POLYPROPYLENE', qty=Decimal('1000'))]
        result = plan_e1_items(items, Decimal('5000'))
        assert _cif(result, 'POLYPROPYLENE') == Decimal('1200.0000')

    def test_generic_stage_shares_one_rate_across_multiple_items(self):
        # Total qty = 100+100=200; 200*3=600 > remaining(300) -> shared rate
        # = 300/200 = 1.50 applied to BOTH items (not each item independently
        # capped against the same starting balance).
        items = [
            E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('100')),
            E1Item(key='b', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('100')),
        ]
        result = plan_e1_items(items, Decimal('300'))
        assert len(result.lines) == 2
        for line in result.lines:
            assert line.unit_price == Decimal('1.5000')
            assert line.planned_qty == Decimal('100')
            assert line.planned_cif == Decimal('150.0000')
        assert result.remaining_cif == Decimal('0')

    def test_zero_quantity_stage_plans_nothing(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('0'))]
        result = plan_e1_items(items, Decimal('1000'))
        assert result.lines == []
        assert result.remaining_cif == Decimal('1000')


class TestMilkStageDelegatesToSharedSplitter(TestCase):
    """Step 3 — Milk must reuse ``milk_planner.split_milk_0404`` exactly as
    E5 uses it: per item, sequential, never averaged across items."""

    def test_milk_qty_partitioned_between_dwp_and_swp(self):
        # Same numbers as milk_planner / E5's own per-item milk test:
        # avg = 318.2/100 = 3.182, below the 4.40 floor.
        items = [E1Item(key='m', category='MILK PRODUCTS', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('318.2'))
        dwp = _lines_by_step(result, 'DWP')[0]
        swp = _lines_by_step(result, 'SWP')[0]
        assert dwp.planned_qty == Decimal('58')
        assert swp.planned_qty == Decimal('42')
        assert dwp.planned_cif == Decimal('255.2000')   # 58*4.40
        assert swp.planned_cif == Decimal('63.0000')    # 42*1.50
        assert result.remaining_cif == Decimal('0')

    def test_milk_avg_above_ceiling_all_dwp_no_swp(self):
        items = [E1Item(key='m', category='MILK PRODUCTS', qty=Decimal('50'))]
        result = plan_e1_items(items, Decimal('5000'))
        dwp = _lines_by_step(result, 'DWP')[0]
        assert dwp.planned_qty == Decimal('50')
        assert dwp.planned_cif == Decimal('250.0000')
        assert _lines_by_step(result, 'SWP') == []

    def test_multiple_milk_items_planned_independently_in_order(self):
        items = [
            E1Item(key='m1', category='MILK PRODUCTS', qty=Decimal('50')),
            E1Item(key='m2', category='MILK PRODUCTS', qty=Decimal('50')),
        ]
        result = plan_e1_items(items, Decimal('300'))
        m1_steps = {ln.step for ln in result.lines if ln.key == 'm1'}
        m2_lines = [ln for ln in result.lines if ln.key == 'm2']
        # m1: avg = 300/50 = 6 >= 5 -> full DWP (250), qty exhausted, no SWP.
        assert m1_steps == {'DWP'}
        assert {ln.step for ln in m2_lines} == {'SWP'}   # avg = 50/50 = 1.0 < 1.5
        assert result.remaining_cif == Decimal('0')

    def test_milk_stage_uses_split_milk_0404s_own_rate_ceiling_not_a_generic_rate(self):
        # avg = 5000/50 = 100, way above the 5.00 DWP ceiling. A (wrongly)
        # generically-routed stage would set rate = min(max_rate, remaining/qty)
        # for some max_rate; split_milk_0404 instead caps DWP at exactly its
        # own 5.00 ceiling regardless of how large the implied avg is.
        items = [E1Item(key='m', category='MILK PRODUCTS', qty=Decimal('50'))]
        result = plan_e1_items(items, Decimal('5000'))
        dwp = _lines_by_step(result, 'DWP')[0]
        assert dwp.unit_price == Decimal('5.0000')
        assert result.remaining_cif == Decimal('4750')  # 5000 - 50*5


class TestPriorityAndSequence(TestCase):
    """The 8 stages must run in fixed order and stop as soon as the balance
    is exhausted; each item is classified into exactly one category, so it
    can never be planned twice."""

    def test_all_eight_stages_fire_in_priority_order_given_ample_balance(self):
        items = [
            E1Item(key='conf', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('10')),
            E1Item(key='cocoa', category='COCOA MASS', qty=Decimal('10')),
            E1Item(key='milk', category='MILK PRODUCTS', qty=Decimal('10')),
            E1Item(key='egg', category='EGG ALBUMIN', qty=Decimal('10')),
            E1Item(key='juice', category='FRUIT JUICE', qty=Decimal('10')),
            E1Item(key='tartaric', category='TARTARIC ACID', qty=Decimal('10')),
            E1Item(key='foil', category='ALUMINIUM FOIL', qty=Decimal('10')),
            E1Item(key='pp', category='POLYPROPYLENE', qty=Decimal('10')),
        ]
        result = plan_e1_items(items, Decimal('100000'))
        seen_categories_in_order = []
        for line in result.lines:
            if line.category not in seen_categories_in_order:
                seen_categories_in_order.append(line.category)
        assert seen_categories_in_order == [
            'OTHER CONFECTIONERY INGREDIENTS', 'COCOA MASS', 'MILK PRODUCTS',
            'EGG ALBUMIN', 'FRUIT JUICE', 'TARTARIC ACID', 'ALUMINIUM FOIL',
            'POLYPROPYLENE',
        ]
        # Every key is planned exactly once (milk may still emit up to 2
        # lines — DWP/SWP — for its single item; every other key emits 1).
        for key in ('conf', 'cocoa', 'egg', 'juice', 'tartaric', 'foil', 'pp'):
            assert len([ln for ln in result.lines if ln.key == key]) == 1

    def test_stops_immediately_once_balance_exhausted(self):
        # Step 1 alone absorbs the whole balance -> every later stage gets 0.
        items = [
            E1Item(key='conf', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('10000')),
            E1Item(key='milk', category='MILK PRODUCTS', qty=Decimal('50')),
            E1Item(key='egg', category='EGG ALBUMIN', qty=Decimal('50')),
            E1Item(key='pp', category='POLYPROPYLENE', qty=Decimal('100')),
        ]
        result = plan_e1_items(items, Decimal('1000'))
        assert _cif(result, 'OTHER CONFECTIONERY INGREDIENTS') == Decimal('1000.0000')
        assert result.remaining_cif == Decimal('0')
        for step in ('DWP', 'SWP', 'EGG ALBUMIN', 'POLYPROPYLENE'):
            assert _lines_by_step(result, step) == []

    def test_no_item_is_ever_planned_twice(self):
        # An item classified into one category never appears under another
        # category's step, even if its description could loosely match a
        # later stage's keywords too (classification is exclusive by
        # construction — one category per item).
        items = [
            E1Item(key='a', category='COCOA MASS', qty=Decimal('10')),
        ]
        result = plan_e1_items(items, Decimal('1000'))
        keys_seen = [ln.key for ln in result.lines]
        assert keys_seen.count('a') == 1

    def test_unrecognised_category_is_ignored(self):
        items = [E1Item(key='a', category='SOMETHING ELSE', qty=Decimal('10'))]
        result = plan_e1_items(items, Decimal('1000'))
        assert result.lines == []
        assert result.remaining_cif == Decimal('1000')


class TestZeroAndNegativeBalance(TestCase):

    def test_zero_balance_plans_nothing(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('0'))
        assert result.lines == []
        assert result.remaining_cif == Decimal('0')

    def test_negative_balance_plans_nothing(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('100'))]
        result = plan_e1_items(items, Decimal('-1'))
        assert result.lines == []

    def test_empty_items_list(self):
        result = plan_e1_items([], Decimal('1000'))
        assert result.lines == []
        assert result.remaining_cif == Decimal('1000')


class TestBalanceNeverExceeded(TestCase):

    def test_full_waterfall_balance_never_exceeded(self):
        items = [
            E1Item(key='conf', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('1000')),
            E1Item(key='cocoa', category='COCOA MASS', qty=Decimal('1000')),
            E1Item(key='milk', category='MILK PRODUCTS', qty=Decimal('1000')),
            E1Item(key='egg', category='EGG ALBUMIN', qty=Decimal('1000')),
            E1Item(key='juice', category='FRUIT JUICE', qty=Decimal('1000')),
            E1Item(key='tartaric', category='TARTARIC ACID', qty=Decimal('1000')),
            E1Item(key='foil', category='ALUMINIUM FOIL', qty=Decimal('1000')),
            E1Item(key='pp', category='POLYPROPYLENE', qty=Decimal('1000')),
        ]
        balance = Decimal('5000')
        result = plan_e1_items(items, balance)
        total = sum((ln.planned_cif for ln in result.lines), Decimal('0'))
        assert total <= balance
        assert total + result.remaining_cif == balance


class TestMinPlanQty(TestCase):
    """``min_plan_qty`` — the Auto-Plan-specific threshold."""

    def test_below_min_plan_qty_is_skipped_entirely(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('49'))]
        result = plan_e1_items(items, Decimal('1000'), min_plan_qty=Decimal('50'))
        assert result.lines == []
        assert result.remaining_cif == Decimal('1000')

    def test_at_min_plan_qty_is_included(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('50'))]
        result = plan_e1_items(items, Decimal('1000'), min_plan_qty=Decimal('50'))
        assert len(result.lines) == 1

    def test_default_min_plan_qty_is_zero_for_reporting(self):
        items = [E1Item(key='a', category='OTHER CONFECTIONERY INGREDIENTS', qty=Decimal('1'))]
        result = plan_e1_items(items, Decimal('1000'))
        assert len(result.lines) == 1
