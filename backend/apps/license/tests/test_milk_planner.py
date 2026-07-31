"""Unit tests for the shared milk-planning engine (services/milk_planner.py).

Exercises the engine directly — independent of E1's / E5's own gating logic
(e.g. E5's Special Validation) — so every band of the average-price split
is covered even where a caller's own rules make a band unreachable through
its own entry point (see test_e5_plan.py's note on Case A).
"""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.milk_planner import MILK_CONFIG_E1, MILK_CONFIG_E5, MilkConfig, plan_milk


class TestMilkConfigConstants(TestCase):

    def test_e1_config_has_no_average_split(self):
        assert MILK_CONFIG_E1.average_split is False
        assert MILK_CONFIG_E1.dwp_price == Decimal('5')
        assert MILK_CONFIG_E1.swp_price == Decimal('1.5')
        assert MILK_CONFIG_E1.wpc_price == Decimal('25')

    def test_e5_config_has_average_split(self):
        assert MILK_CONFIG_E5.average_split is True
        assert MILK_CONFIG_E5.dwp_price == Decimal('5')
        assert MILK_CONFIG_E5.swp_price == Decimal('1.5')
        assert MILK_CONFIG_E5.wpc_price == Decimal('25')
        assert MILK_CONFIG_E5.mixed_wpc_price == Decimal('20')


class TestPlanMilk0404Only(TestCase):

    def test_dwp_then_swp_over_the_same_full_quantity(self):
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('5000'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')     # 50 * 5
        assert planned['SWP'] == Decimal('75')       # 50 * 1.5 (same 50 units)
        assert planned['WPC'] == Decimal('0')
        assert remaining == Decimal('5000') - Decimal('250') - Decimal('75')

    def test_dwp_caps_balance_swp_gets_zero(self):
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('100'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('100')
        assert rate['DWP'] == Decimal('2')     # 100 / 50
        assert planned['SWP'] == Decimal('0')
        assert rate['SWP'] == Decimal('1.5')   # default fallback, balance exhausted
        assert remaining == Decimal('0')

    def test_same_behaviour_regardless_of_average_split_flag(self):
        # 0404-only never reaches the banded path — E1 and E5 configs agree.
        p1, r1, rem1 = plan_milk(Decimal('50'), Decimal('0'), Decimal('5000'), MILK_CONFIG_E1)
        p2, r2, rem2 = plan_milk(Decimal('50'), Decimal('0'), Decimal('5000'), MILK_CONFIG_E5)
        assert p1 == p2
        assert r1 == r2
        assert rem1 == rem2


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


class TestPlanMilkMixedNoAverageSplit(TestCase):
    """E1's config never bands — both-present just runs 0404 then 3502."""

    def test_e1_runs_0404_then_3502_sequentially(self):
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('5000'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')    # 50 * 5
        assert planned['SWP'] == Decimal('75')     # 50 * 1.5
        assert planned['WPC'] == Decimal('250')    # 10 * 25, after DWP+SWP drew down balance
        assert remaining == Decimal('5000') - 250 - 75 - 250


class TestPlanMilkMixedAveragePriceBands(TestCase):
    """E5's config (average_split=True) bands the combined quantity."""

    def test_case_a_avg_below_1_50_all_balance_to_swp(self):
        # total_qty=1000, remaining=1000 → avg=1.0 (< 1.50).
        planned, rate, remaining = plan_milk(Decimal('500'), Decimal('500'), Decimal('1000'), MILK_CONFIG_E5)
        assert planned['SWP'] == Decimal('1000')
        assert rate['SWP'] == Decimal('1.5')   # fixed — this path is NOT balance-capped externally
        assert planned['DWP'] == Decimal('0')
        assert planned['WPC'] == Decimal('0')
        assert remaining == Decimal('0')

    def test_case_b_swp_maximised_dwp_absorbs_exact_residual(self):
        # total_qty=100, remaining=300 → avg=3.0 (1.50 <= avg < 5.00).
        # q_swp = floor((5*100-300)/3.5) = floor(57.14) = 57 -> cif=85.5
        # cif_dwp = 300 - 85.5 = 214.5 (exact residual).
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('50'), Decimal('300'), MILK_CONFIG_E5)
        assert planned['SWP'] == Decimal('85.5')
        assert planned['DWP'] == Decimal('214.5')
        assert planned['WPC'] == Decimal('0')
        assert remaining == Decimal('0')
        assert planned['SWP'] + planned['DWP'] == Decimal('300')

    def test_case_c_dwp_maximised_wpc_absorbs_exact_residual(self):
        # total_qty=100, remaining=1000 → avg=10.0 (5.00 <= avg < 20.00).
        # q_dwp = floor((20*100-1000)/15) = floor(66.67) = 66 -> cif=330
        # cif_wpc = 1000 - 330 = 670 (exact residual, at the MIXED wpc price 20).
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('50'), Decimal('1000'), MILK_CONFIG_E5)
        assert planned['DWP'] == Decimal('330')
        assert planned['WPC'] == Decimal('670')
        assert planned['SWP'] == Decimal('0')
        assert rate['WPC'] == Decimal('20')   # mixed-band WPC price, not the pure 25
        assert remaining == Decimal('0')
        assert planned['DWP'] + planned['WPC'] == Decimal('1000')

    def test_case_d_avg_at_or_above_20_full_qty_to_wpc_surplus_flows_back(self):
        # total_qty=20, remaining=500 → avg=25 (>= 20).
        planned, rate, remaining = plan_milk(Decimal('10'), Decimal('10'), Decimal('500'), MILK_CONFIG_E5)
        assert planned['WPC'] == Decimal('400')    # 20 * 20
        assert rate['WPC'] == Decimal('20')
        assert remaining == Decimal('100')          # surplus flows back, NOT forced to zero

    def test_band_boundary_avg_exactly_1_50_uses_case_b_not_case_a(self):
        # total_qty=100, remaining=150 → avg=1.50 exactly — falls in [1.50, 5.00).
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('50'), Decimal('150'), MILK_CONFIG_E5)
        # Case B formula: q_swp = floor((5*100-150)/3.5) = floor(100) = 100 -> cif=150
        assert planned['SWP'] == Decimal('150')
        assert planned['DWP'] == Decimal('0')
        assert remaining == Decimal('0')


class TestPlanMilkEdgeCases(TestCase):

    def test_zero_quantities_and_balance_no_op(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('0'), Decimal('5000'), MILK_CONFIG_E5)
        assert planned['DWP'] == planned['SWP'] == planned['WPC'] == Decimal('0')
        assert remaining == Decimal('5000')

    def test_negative_balance_plans_zero(self):
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('-1'), MILK_CONFIG_E5)
        assert planned['DWP'] == planned['SWP'] == planned['WPC'] == Decimal('0')

    def test_tolerant_type_coercion(self):
        planned, rate, remaining = plan_milk('50', None, '5000', MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')

    def test_milk_config_is_frozen(self):
        with self.assertRaises(Exception):
            MILK_CONFIG_E1.dwp_price = Decimal('99')  # type: ignore[misc]

    def test_custom_config_is_supported(self):
        custom = MilkConfig(
            dwp_price=Decimal('10'), swp_price=Decimal('2'),
            wpc_price=Decimal('30'), mixed_wpc_price=Decimal('15'),
            average_split=True,
        )
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('5'), Decimal('1000'), custom)
        assert planned['WPC'] == Decimal('150')   # 5 * 30
