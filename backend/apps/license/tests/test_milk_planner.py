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
        assert MILK_CONFIG_E1.swp_price == Decimal('1.5')
        assert MILK_CONFIG_E1.wpc_price == Decimal('25')


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
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('5000'), MILK_CONFIG_E1)
        assert planned['DWP'] == Decimal('250')    # 50 * 5
        assert planned['SWP'] == Decimal('75')     # 50 * 1.5
        assert planned['WPC'] == Decimal('250')    # 10 * 25, after DWP+SWP drew down balance
        assert remaining == Decimal('5000') - 250 - 75 - 250


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
        custom = MilkConfig(dwp_price=Decimal('10'), swp_price=Decimal('2'), wpc_price=Decimal('30'))
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('5'), Decimal('1000'), custom)
        assert planned['WPC'] == Decimal('150')   # 5 * 30
