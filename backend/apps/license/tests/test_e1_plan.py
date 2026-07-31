"""Unit tests for the E1 utilization-planning waterfall."""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.e1_plan import (
    E1_CATS,
    E1_EXCLUDED_CONDITIONS,
    E1_MAX_PRICES,
    classify_e1_item,
    compute_e1_plan,
    split_display_util_qty,
)


def _zero_qty() -> dict[str, float]:
    return {c: 0.0 for c in E1_CATS}


def _qty(**kwargs) -> dict[str, float]:
    base = _zero_qty()
    base.update(kwargs)
    return base


def _planned_sum(planned: dict[str, float]) -> float:
    # DWP/SWP are folded into MILK PRODUCTS for the bucket-level total, so
    # summing everything would double-count them. Sum only the buckets.
    return sum(v for k, v in planned.items() if k in E1_CATS)


class TestClassifyE1Item(TestCase):

    def test_other_confectionery_item_name(self):
        assert classify_e1_item('OTHER CONFECTIONERY INGREDIENTS - E1', '', '') == \
            'OTHER CONFECTIONERY INGREDIENTS'

    def test_milk_products_by_hsn_0404(self):
        assert classify_e1_item('ANY NAME', '04041000', '') == 'MILK PRODUCTS'

    def test_wpc_item_name_no_longer_classifies_on_its_own(self):
        # The old item-name-based 'wpc' rule is gone — WPC-named items with
        # no 0404/3502 HSN now fall through unclassified.
        assert classify_e1_item('WPC - E1', '', '') is None

    def test_egg_albumin_wpc_by_hsn_3502(self):
        assert classify_e1_item('ANY NAME', '35021100', '') == 'EGG ALBUMIN / WPC'

    def test_fruit_juice_item_name(self):
        assert classify_e1_item('FRUIT JUICE - E1', '', '') == 'FRUIT JUICE'

    def test_aluminium_foil_by_hsn(self):
        assert classify_e1_item('SOMETHING', '76071190', '') == 'ALUMINIUM FOIL'

    def test_aluminium_foil_by_description(self):
        assert classify_e1_item('PACKING', '', 'Aluminium foil 7607 grade') == 'ALUMINIUM FOIL'

    def test_polypropylene_3902_no_7607(self):
        assert classify_e1_item('PP', '39021000', '') == 'POLYPROPYLENE'

    def test_polypropylene_excluded_when_7607_present(self):
        # 3902 alone → POLYPROPYLENE; 3902 + 7607 → ALUMINIUM FOIL wins (7607 check first).
        assert classify_e1_item('PP', '76073902', '') == 'ALUMINIUM FOIL'

    def test_paper_by_4801(self):
        assert classify_e1_item('BOX', '48010000', '') == 'PAPER'

    def test_paper_by_4810(self):
        assert classify_e1_item('BOX', '48109000', '') == 'PAPER'

    def test_paper_by_4802(self):
        assert classify_e1_item('BOX', '48025500', '') == 'PAPER'

    def test_paper_excluded_when_7607_or_3902_or_3901_present(self):
        # If 7607 also appears, ALUMINIUM FOIL wins (checked before paper rule).
        assert classify_e1_item('MIXED', '76074801', '') == 'ALUMINIUM FOIL'
        # If 3902 also appears, POLYPROPYLENE wins (3902 check before paper).
        assert classify_e1_item('MIXED', '39024801', '') == 'POLYPROPYLENE'
        # If only 3901 + paper code: paper rule says exclude → returns None.
        assert classify_e1_item('MIXED', '39014801', '') is None

    def test_priority_0404_beats_fruit_juice_item_name(self):
        # Rule 2 (HSN 0404) is checked before rule 4 (item-name fruit juice).
        assert classify_e1_item('FRUIT JUICE BLEND', '04041000', '') == 'MILK PRODUCTS'

    def test_priority_other_confectionery_beats_0404(self):
        # Rule 1 (item-name) is checked before rule 2 (HSN 0404).
        assert classify_e1_item('OTHER CONFECTIONERY INGREDIENTS - E1', '04041000', '') == \
            'OTHER CONFECTIONERY INGREDIENTS'

    def test_milk_products_hsn_only_not_description(self):
        # Spec: rule 2 checks HSN only, not description.
        assert classify_e1_item('ANY NAME', '', 'contains 0404 in description') is None

    def test_unclassified(self):
        assert classify_e1_item('SUGAR', '17019990', 'Refined Cane Sugar') is None

    def test_null_blank_and_unicode_inputs_are_safe(self):
        assert classify_e1_item(None, None, None) is None
        assert classify_e1_item('', '   ', '   ') is None
        assert classify_e1_item('PACKING', '', 'Aluminium foil \U0001f4e6 7607') == 'ALUMINIUM FOIL'


class TestSplitDisplayUtilQty(TestCase):

    def test_2_percent_excluded_from_other_confectionery_util(self):
        rows = [
            {'category': 'OTHER CONFECTIONERY INGREDIENTS', 'qty': 100, 'condition_type': ''},
            {'category': 'OTHER CONFECTIONERY INGREDIENTS', 'qty': 50,  'condition_type': '2%'},
            {'category': 'OTHER CONFECTIONERY INGREDIENTS', 'qty': 150, 'condition_type': ''},
        ]
        d, u = split_display_util_qty(rows)
        assert d['OTHER CONFECTIONERY INGREDIENTS'] == 300.0
        assert u['OTHER CONFECTIONERY INGREDIENTS'] == 250.0

    def test_milk_products_no_exclusion(self):
        rows = [
            {'category': 'MILK PRODUCTS', 'qty': 200, 'condition_type': ''},
            {'category': 'MILK PRODUCTS', 'qty': 100, 'condition_type': 'AU'},
        ]
        d, u = split_display_util_qty(rows)
        assert d['MILK PRODUCTS'] == 300.0
        assert u['MILK PRODUCTS'] == 300.0  # no exclusions configured for this bucket

    def test_au_excluded_from_fruit_juice_util(self):
        rows = [
            {'category': 'FRUIT JUICE', 'qty': 80, 'condition_type': 'AU'},
            {'category': 'FRUIT JUICE', 'qty': 20, 'condition_type': ''},
        ]
        d, u = split_display_util_qty(rows)
        assert d['FRUIT JUICE'] == 100.0
        assert u['FRUIT JUICE'] == 20.0

    def test_2_percent_NOT_excluded_from_egg_albumin_wpc(self):
        # 2% only excludes OTHER CONFECTIONERY INGREDIENTS — for EGG ALBUMIN
        # / WPC it should still count toward util qty.
        rows = [
            {'category': 'EGG ALBUMIN / WPC', 'qty': 100, 'condition_type': '2%'},
        ]
        d, u = split_display_util_qty(rows)
        assert d['EGG ALBUMIN / WPC'] == 100.0
        assert u['EGG ALBUMIN / WPC'] == 100.0

    def test_aluminium_paper_polypropylene_no_exclusion(self):
        rows = [
            {'category': 'ALUMINIUM FOIL', 'qty': 50, 'condition_type': '2%'},
            {'category': 'POLYPROPYLENE',  'qty': 30, 'condition_type': 'AU'},
            {'category': 'PAPER',          'qty': 70, 'condition_type': '10%'},
        ]
        d, u = split_display_util_qty(rows)
        assert d == {**_zero_qty(), 'ALUMINIUM FOIL': 50.0, 'POLYPROPYLENE': 30.0, 'PAPER': 70.0}
        assert u == d  # no exclusions for any of these


class TestComputeE1Plan(TestCase):

    def test_zero_quantities_no_utilization(self):
        planned, _ = compute_e1_plan(_zero_qty(), _zero_qty(), Decimal('10000'))
        assert _planned_sum(planned) == 0.0

    def test_invalid_util_quantities_and_negative_balance_plan_zero(self):
        planned, rate = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 10.0, 'EGG ALBUMIN / WPC': 10.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 'bad', 'EGG ALBUMIN / WPC': None}),
            Decimal('-1'),
        )

        assert _planned_sum(planned) == 0.0
        assert rate['OTHER CONFECTIONERY INGREDIENTS'] == 2.7
        assert rate['EGG ALBUMIN / WPC'] == 25.0
        assert rate['DWP'] == 5.0
        assert rate['SWP'] == 1.5

    def test_other_confectionery_at_max_price(self):
        # 100 kg × 2.7 = 270 ≤ balance.
        planned, rate = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0}),
            Decimal('1000'),
        )
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 270.0
        assert rate['OTHER CONFECTIONERY INGREDIENTS'] == 2.7

    def test_milk_products_0404_qty_is_partitioned_not_shared(self):
        # 50 kg of Milk Products, avg = 5000/50 = 100 >= 5 -> DWP takes the
        # full 50 kg at the 5.00 ceiling; nothing is left over for SWP (the
        # qty is exhausted, not shared between the two steps anymore).
        planned, rate = compute_e1_plan(
            _qty(**{'MILK PRODUCTS': 50.0}),
            _qty(**{'MILK PRODUCTS': 50.0}),
            Decimal('5000'),
        )
        assert planned['DWP'] == 250.0
        assert rate['DWP'] == 5.0
        assert planned['SWP'] == 0.0
        assert rate['SWP'] == 1.5
        # MILK PRODUCTS bucket aggregates both sub-steps.
        assert planned['MILK PRODUCTS'] == 250.0
        assert rate['MILK PRODUCTS'] == 6.5

    def test_milk_products_dwp_maximised_at_floor_rate_swp_takes_remainder(self):
        # 50 kg of Milk Products, avg = 133/50 = 2.66 -> below the 4.40
        # floor, so DWP can only take as much of the 50 kg as keeps its rate
        # at exactly 4.40; the rest (30 kg) goes to SWP at the fixed 1.50.
        planned, rate = compute_e1_plan(
            _qty(**{'MILK PRODUCTS': 50.0}),
            _qty(**{'MILK PRODUCTS': 50.0}),
            Decimal('133'),
        )
        assert planned['DWP'] == 88.0    # 20 kg * 4.40
        assert rate['DWP'] == 4.4
        assert planned['SWP'] == 45.0    # 30 kg * 1.50
        assert rate['SWP'] == 1.5
        assert planned['MILK PRODUCTS'] == 133.0

    def test_egg_albumin_wpc_max_price_25(self):
        planned, rate = compute_e1_plan(
            _qty(**{'EGG ALBUMIN / WPC': 10.0}),
            _qty(**{'EGG ALBUMIN / WPC': 10.0}),
            Decimal('5000'),
        )
        assert planned['EGG ALBUMIN / WPC'] == 250.0
        assert rate['EGG ALBUMIN / WPC'] == 25.0

    def test_fruit_juice_max_price_3(self):
        planned, rate = compute_e1_plan(
            _qty(**{'FRUIT JUICE': 200.0}),
            _qty(**{'FRUIT JUICE': 200.0}),
            Decimal('5000'),
        )
        assert planned['FRUIT JUICE'] == 600.0   # 200 * 3
        assert rate['FRUIT JUICE'] == 3.0

    def test_aluminium_foil_max_price_4_point_5(self):
        planned, rate = compute_e1_plan(
            _qty(**{'ALUMINIUM FOIL': 100.0}),
            _qty(**{'ALUMINIUM FOIL': 100.0}),
            Decimal('5000'),
        )
        assert planned['ALUMINIUM FOIL'] == 450.0
        assert rate['ALUMINIUM FOIL'] == 4.5

    def test_polypropylene_max_price_0_point_9(self):
        planned, rate = compute_e1_plan(
            _qty(POLYPROPYLENE=1000.0),
            _qty(POLYPROPYLENE=1000.0),
            Decimal('5000'),
        )
        assert planned['POLYPROPYLENE'] == 900.0
        assert rate['POLYPROPYLENE'] == 0.9

    def test_paper_max_price_0_point_6(self):
        planned, rate = compute_e1_plan(
            _qty(PAPER=2000.0), _qty(PAPER=2000.0), Decimal('5000'),
        )
        assert planned['PAPER'] == 1200.0
        assert rate['PAPER'] == 0.6

    def test_step_capped_when_balance_insufficient(self):
        # 1000 × 2.7 = 2700 but balance is only 500. Step caps at 500;
        # effective rate = 500/1000 = 0.5.
        planned, rate = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 1000.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 1000.0}),
            Decimal('500'),
        )
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 500.0
        assert abs(rate['OTHER CONFECTIONERY INGREDIENTS'] - 0.5) < 1e-4

    def test_sequential_deduction(self):
        # Step 1 eats 270; balance left 730. EGG ALBUMIN/WPC 10 × 25 = 250 fits.
        planned, _ = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0, 'EGG ALBUMIN / WPC': 10.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0, 'EGG ALBUMIN / WPC': 10.0}),
            Decimal('1000'),
        )
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 270.0
        assert planned['EGG ALBUMIN / WPC'] == 250.0

    def test_later_steps_get_zero_when_balance_exhausted(self):
        # Step 1 absorbs the whole balance — every later step gets 0.
        full = {
            'OTHER CONFECTIONERY INGREDIENTS': 10000.0,
            'MILK PRODUCTS': 50.0,
            'EGG ALBUMIN / WPC': 50.0,
            'FRUIT JUICE': 100.0,
            'ALUMINIUM FOIL': 100.0,
            'POLYPROPYLENE': 100.0,
            'PAPER': 100.0,
        }
        planned, rate = compute_e1_plan(_qty(**full), _qty(**full), Decimal('1000'))
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 1000.0
        for key in ('DWP', 'SWP', 'MILK PRODUCTS', 'EGG ALBUMIN / WPC',
                    'FRUIT JUICE', 'ALUMINIUM FOIL', 'POLYPROPYLENE', 'PAPER'):
            assert planned[key] == 0.0
        # Zero-utilization steps still report their default max price.
        assert rate['DWP'] == 5.0
        assert rate['SWP'] == 1.5
        assert rate['EGG ALBUMIN / WPC'] == 25.0

    def test_planned_never_exceeds_balance(self):
        planned, _ = compute_e1_plan(
            _qty(**{c: 1_000_000.0 for c in E1_CATS}),
            _qty(**{c: 1_000_000.0 for c in E1_CATS}),
            Decimal('5000'),
        )
        assert _planned_sum(planned) <= 5000.0 + 1e-4

    def test_util_qty_drives_math_not_display(self):
        # 100 kg display, 50 util (50 was marked as 2%). Plan should use 50.
        planned, _ = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 50.0}),
            Decimal('10000'),
        )
        # 50 * 2.7 = 135, not 100 * 2.7 = 270.
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 135.0

    def test_exact_balance_utilization(self):
        # 500 / 2.7 ≈ 185.185, so 185.185 kg should exactly drain 500.
        qty = float(Decimal('500') / Decimal('2.7'))
        planned, _ = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': qty}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': qty}),
            Decimal('500'),
        )
        assert abs(planned['OTHER CONFECTIONERY INGREDIENTS'] - 500.0) < 1e-3

    def test_excluded_conditions_table(self):
        # Sanity-check the per-bucket exclusion sets match the spec.
        assert E1_EXCLUDED_CONDITIONS['OTHER CONFECTIONERY INGREDIENTS'] == frozenset({'2%'})
        assert E1_EXCLUDED_CONDITIONS['MILK PRODUCTS'] == frozenset()
        assert E1_EXCLUDED_CONDITIONS['EGG ALBUMIN / WPC'] == frozenset()
        assert E1_EXCLUDED_CONDITIONS['FRUIT JUICE'] == frozenset({'AU'})
        assert E1_EXCLUDED_CONDITIONS['ALUMINIUM FOIL'] == frozenset()
        assert E1_EXCLUDED_CONDITIONS['POLYPROPYLENE'] == frozenset()
        assert E1_EXCLUDED_CONDITIONS['PAPER'] == frozenset()

    def test_max_prices_table(self):
        assert E1_MAX_PRICES['OTHER CONFECTIONERY INGREDIENTS'] == Decimal('2.7')
        assert E1_MAX_PRICES['DWP'] == Decimal('5')
        assert E1_MAX_PRICES['SWP'] == Decimal('1.5')
        assert E1_MAX_PRICES['EGG ALBUMIN / WPC'] == Decimal('25')
        assert E1_MAX_PRICES['FRUIT JUICE'] == Decimal('3')
        assert E1_MAX_PRICES['ALUMINIUM FOIL'] == Decimal('4.5')
        assert E1_MAX_PRICES['POLYPROPYLENE'] == Decimal('0.9')
        assert E1_MAX_PRICES['PAPER'] == Decimal('0.6')
