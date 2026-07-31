"""Unit tests for the shared milk-planning engine (services/milk_planner.py).

E1-only — E5's per-item milk rules (no averaging) live in
``e5_plan.py``/``plan_e5_items`` and are covered by ``test_e5_plan.py``.
"""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.milk_planner import MILK_CONFIG_E1, MilkConfig, plan_milk


class TestMilkConfigConstants(TestCase):

    def test_e1_config_prices(self):
        assert MILK_CONFIG_E1.dwp_price == Decimal('5')
        assert MILK_CONFIG_E1.dwp_min_price == Decimal('4.40')
        assert MILK_CONFIG_E1.swp_price == Decimal('1.5')
        assert MILK_CONFIG_E1.wpc_price == Decimal('25')


class TestPlanMilk0404Only(TestCase):
    """0404 qty is partitioned between DWP and SWP — DWP's quantity is
    maximised subject to its rate staying within [dwp_min_price, dwp_price];
    SWP (fixed 1.5) absorbs whatever's left. See milk_planner._split_milk_0404.
    """

    def test_avg_above_ceiling_all_dwp_at_max_rate_balance_left_over(self):
        # avg = 300/50 = 6 >= 5 -> DWP takes everything at the 5.00 ceiling;
        # qty is exhausted so the surplus balance can't be spent.
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('300'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')      # 50 * 5.00
        assert rate['DWP'] == Decimal('5')
        assert planned['SWP'] == Decimal('0')
        assert planned['WPC'] == Decimal('0')
        assert remaining == Decimal('50')            # 300 - 250, unavoidable

    def test_avg_in_band_all_dwp_at_blended_rate_zero_remaining(self):
        # avg = 240/50 = 4.80, within [4.40, 5.00] -> full qty to DWP at the
        # blended rate; no room left for SWP and none needed.
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('240'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('240')      # 50 * 4.80
        assert rate['DWP'] == Decimal('4.8')
        assert planned['SWP'] == Decimal('0')
        assert remaining == Decimal('0')

    def test_avg_below_floor_dwp_maximised_at_floor_rate_swp_takes_rest(self):
        # avg = 318.2/100 = 3.182, below the 4.40 floor -> DWP can't take the
        # full qty without its rate dropping below 4.40, so DWP is capped at
        # the largest quantity whose rate is exactly 4.40, and SWP absorbs
        # the remaining 42 units at the fixed 1.50 rate.
        planned, rate, remaining = plan_milk(Decimal('100'), Decimal('0'), Decimal('318.2'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('255.2')    # 58 * 4.40
        assert rate['DWP'] == Decimal('4.40')
        assert planned['SWP'] == Decimal('63')       # 42 * 1.50
        assert remaining == Decimal('0')

    def test_worked_example_from_spec(self):
        # Milk Qty 36,017.67 / Balance 142,301.90 from the HSN 0404 spec.
        planned, rate, remaining = plan_milk(
            Decimal('36017.67'), Decimal('0'), Decimal('142301.90'), MILK_CONFIG_E1,
        )
        assert rate['DWP'] == Decimal('4.40')
        assert planned['DWP'] + planned['SWP'] == Decimal('142301.90')
        assert remaining == Decimal('0')

    def test_avg_below_swp_rate_partial_qty_only_swp_used(self):
        # avg = 30/50 = 0.60, below even the SWP rate -> the balance can't
        # cover the full qty at any allowed rate; spend it all on SWP and
        # leave the rest of the milk qty unplanned (mirrors allocate_step's
        # insufficient-balance behaviour elsewhere in the codebase).
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('30'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('0')
        assert planned['SWP'] == Decimal('30')       # 20 units * 1.50, not all 50
        assert remaining == Decimal('0')


class TestPlanMilk3502Only(TestCase):

    def test_full_qty_to_wpc_at_configured_price(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('10'), Decimal('5000'), MILK_CONFIG_E1)
        assert planned['WPC'] == Decimal('250')   # 10 * 25
        assert rate['WPC'] == Decimal('25')
        assert planned['DWP'] == Decimal('0')
        assert planned['SWP'] == Decimal('0')
        assert remaining == Decimal('4750')

    def test_wpc_capped_when_balance_insufficient(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('10'), Decimal('100'), MILK_CONFIG_E1)
        assert planned['WPC'] == Decimal('100')
        assert rate['WPC'] == Decimal('10')   # 100 / 10
        assert remaining == Decimal('0')


class TestPlanMilkMixedRunsSequentially(TestCase):
    """E1 has no average-price concept — both present just runs 0404 then
    3502, back to back, against the same shrinking balance."""

    def test_runs_0404_then_3502_sequentially(self):
        # avg for the 0404 leg = 5000/50 = 100 >= 5 -> full qty to DWP, no SWP.
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('5000'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')    # 50 * 5
        assert planned['SWP'] == Decimal('0')
        assert planned['WPC'] == Decimal('250')    # 10 * 25, after DWP drew down balance
        assert remaining == Decimal('5000') - 250 - 250


class TestPlanMilkEdgeCases(TestCase):

    def test_zero_quantities_and_balance_no_op(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('0'), Decimal('5000'), MILK_CONFIG_E1)
        assert planned['DWP'] == planned['SWP'] == planned['WPC'] == Decimal('0')
        assert remaining == Decimal('5000')

    def test_negative_balance_plans_zero(self):
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('-1'), MILK_CONFIG_E1)
        assert planned['DWP'] == planned['SWP'] == planned['WPC'] == Decimal('0')

    def test_tolerant_type_coercion(self):
        planned, rate, remaining = plan_milk('50', None, '5000', MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')

    def test_milk_config_is_frozen(self):
        with self.assertRaises(Exception):
            MILK_CONFIG_E1.dwp_price = Decimal('99')  # type: ignore[misc]

    def test_custom_config_is_supported(self):
        custom = MilkConfig(dwp_price=Decimal('10'), dwp_min_price=Decimal('8'), swp_price=Decimal('2'), wpc_price=Decimal('30'))
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('5'), Decimal('1000'), custom)
        assert planned['WPC'] == Decimal('150')   # 5 * 30
