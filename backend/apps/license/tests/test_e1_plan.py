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
    return sum(planned.values())


class TestClassifyE1Item(TestCase):

    def test_other_confectionery_item_name(self):
        assert classify_e1_item('OTHER CONFECTIONERY INGREDIENTS - E1', '', '') == \
            'OTHER CONFECTIONERY INGREDIENTS'

    def test_wpc_item_name(self):
        assert classify_e1_item('WPC - E1', '', '') == 'WPC'

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

    def test_unclassified(self):
        assert classify_e1_item('SUGAR', '17019990', 'Refined Cane Sugar') is None


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

    def test_au_excluded_from_wpc_util(self):
        rows = [
            {'category': 'WPC', 'qty': 200, 'condition_type': ''},
            {'category': 'WPC', 'qty': 100, 'condition_type': 'AU'},
        ]
        d, u = split_display_util_qty(rows)
        assert d['WPC'] == 300.0
        assert u['WPC'] == 200.0

    def test_au_excluded_from_fruit_juice_util(self):
        rows = [
            {'category': 'FRUIT JUICE', 'qty': 80, 'condition_type': 'AU'},
            {'category': 'FRUIT JUICE', 'qty': 20, 'condition_type': ''},
        ]
        d, u = split_display_util_qty(rows)
        assert d['FRUIT JUICE'] == 100.0
        assert u['FRUIT JUICE'] == 20.0

    def test_2_percent_NOT_excluded_from_wpc(self):
        # 2% only excludes OTHER CONFECTIONERY INGREDIENTS — for WPC it should
        # still count toward util qty.
        rows = [
            {'category': 'WPC', 'qty': 100, 'condition_type': '2%'},
        ]
        d, u = split_display_util_qty(rows)
        assert d['WPC'] == 100.0
        assert u['WPC'] == 100.0

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

    def test_other_confectionery_at_max_price(self):
        # 100 kg × 2.7 = 270 ≤ balance.
        planned, rate = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0}),
            Decimal('1000'),
        )
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 270.0
        assert rate['OTHER CONFECTIONERY INGREDIENTS'] == 2.7

    def test_wpc_max_price_22(self):
        # qty 50 × 22 = 1100 ≤ balance.
        planned, rate = compute_e1_plan(
            _qty(WPC=50.0), _qty(WPC=50.0), Decimal('5000'),
        )
        assert planned['WPC'] == 1100.0
        assert rate['WPC'] == 22.0

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
        # Step 1 eats 270; step 2 should see balance 730. WPC 30 × 22 = 660 fits.
        planned, _ = compute_e1_plan(
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0, 'WPC': 30.0}),
            _qty(**{'OTHER CONFECTIONERY INGREDIENTS': 100.0, 'WPC': 30.0}),
            Decimal('1000'),
        )
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 270.0
        assert planned['WPC'] == 660.0

    def test_later_steps_get_zero_when_balance_exhausted(self):
        # Step 1 absorbs the whole balance — every later step gets 0.
        planned, _ = compute_e1_plan(
            _qty(**{
                'OTHER CONFECTIONERY INGREDIENTS': 10000.0,
                'WPC': 50.0,
                'FRUIT JUICE': 100.0,
                'ALUMINIUM FOIL': 100.0,
                'POLYPROPYLENE': 100.0,
                'PAPER': 100.0,
            }),
            _qty(**{
                'OTHER CONFECTIONERY INGREDIENTS': 10000.0,
                'WPC': 50.0,
                'FRUIT JUICE': 100.0,
                'ALUMINIUM FOIL': 100.0,
                'POLYPROPYLENE': 100.0,
                'PAPER': 100.0,
            }),
            Decimal('1000'),
        )
        assert planned['OTHER CONFECTIONERY INGREDIENTS'] == 1000.0
        for cat in ('WPC', 'FRUIT JUICE', 'ALUMINIUM FOIL', 'POLYPROPYLENE', 'PAPER'):
            assert planned[cat] == 0.0

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
        # Sanity-check the per-step exclusion sets match the spec.
        assert E1_EXCLUDED_CONDITIONS['OTHER CONFECTIONERY INGREDIENTS'] == frozenset({'2%'})
        assert E1_EXCLUDED_CONDITIONS['WPC'] == frozenset({'AU'})
        assert E1_EXCLUDED_CONDITIONS['FRUIT JUICE'] == frozenset({'AU'})
        assert E1_EXCLUDED_CONDITIONS['ALUMINIUM FOIL'] == frozenset()
        assert E1_EXCLUDED_CONDITIONS['POLYPROPYLENE'] == frozenset()
        assert E1_EXCLUDED_CONDITIONS['PAPER'] == frozenset()

    def test_max_prices_table(self):
        assert E1_MAX_PRICES['OTHER CONFECTIONERY INGREDIENTS'] == Decimal('2.7')
        assert E1_MAX_PRICES['WPC'] == Decimal('22')
        assert E1_MAX_PRICES['FRUIT JUICE'] == Decimal('3')
        assert E1_MAX_PRICES['ALUMINIUM FOIL'] == Decimal('4.5')
        assert E1_MAX_PRICES['POLYPROPYLENE'] == Decimal('0.9')
        assert E1_MAX_PRICES['PAPER'] == Decimal('0.6')
