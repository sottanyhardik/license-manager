"""Unit tests for the shared milk-planning engine (services/milk_planner.py).

E1-only — E5's per-item milk rules (no averaging) live in
``e5_plan.py``/``plan_e5_items`` and are covered by ``test_e5_plan.py``.
"""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.milk_planner import MILK_CONFIG, MilkConfig, plan_milk

# The DWP rate ceiling (``MILK_CONFIG.dwp_price``), pinned numerically by
# ``TestMilkConfigConstants.test_e1_config_prices`` below. Every ceiling-priced
# expectation in this module is arithmetic against this single constant, so a
# future price change lands in exactly one place plus that one pinning test.
DWP_CEILING = Decimal('6.5')
# 50 kg planned at that ceiling — the recurring worked figure below
# (50 * 6.50 = 325).
CEILING_CIF_50KG = Decimal('50') * DWP_CEILING


class TestMilkConfigConstants(TestCase):

    def test_e1_config_prices(self):
        assert MILK_CONFIG.dwp_price == Decimal('6.5')
        assert MILK_CONFIG.dwp_min_price == Decimal('4.40')
        assert MILK_CONFIG.swp_price == Decimal('1.5')
        assert MILK_CONFIG.wpc_price == Decimal('25')

    def test_shared_ceiling_constant_tracks_the_engine(self):
        # Guard: if MILK_CONFIG.dwp_price moves again, this fails alongside the
        # test above instead of silently invalidating every derived expectation.
        assert DWP_CEILING == MILK_CONFIG.dwp_price


class TestPlanMilk0404Only(TestCase):
    """0404 qty is partitioned between DWP and SWP — DWP's quantity is
    maximised subject to its rate staying within [dwp_min_price, dwp_price];
    SWP (fixed 1.5) absorbs whatever's left. See milk_planner._split_milk_0404.
    """

    def test_avg_above_ceiling_all_dwp_at_max_rate_balance_left_over(self):
        # avg = 350/50 = 7.00 >= 6.50 -> DWP takes everything at the 6.50
        # ceiling; qty is exhausted so the surplus balance can't be spent.
        # (Balance raised 300 -> 350 so the case still sits ABOVE the ceiling:
        # at the old 5.00 ceiling 300/50 = 6 cleared it, at 6.50 it would fall
        # into the in-band branch tested immediately below.)
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('350'), MILK_CONFIG)
        assert planned['DWP'] == CEILING_CIF_50KG    # 50 * 6.50 = 325
        assert rate['DWP'] == DWP_CEILING
        assert planned['SWP'] == Decimal('0')
        assert planned['WPC'] == Decimal('0')
        assert remaining == Decimal('25')            # 350 - 325, unavoidable

    def test_avg_in_band_all_dwp_at_blended_rate_zero_remaining(self):
        # avg = 240/50 = 4.80, within [4.40, 6.50] -> full qty to DWP at the
        # blended rate; no room left for SWP and none needed.
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('240'), MILK_CONFIG)
        assert planned['DWP'] == Decimal('240')      # 50 * 4.80
        assert rate['DWP'] == Decimal('4.8')
        assert planned['SWP'] == Decimal('0')
        assert remaining == Decimal('0')

    def test_avg_below_floor_dwp_maximised_at_floor_rate_swp_takes_rest(self):
        # avg = 318.2/100 = 3.182, below the 4.40 floor -> DWP can't take the
        # full qty without its rate dropping below 4.40, so DWP is capped at
        # the largest quantity whose rate is exactly 4.40, and SWP absorbs
        # the remaining 42 units at the fixed 1.50 rate.
        planned, rate, remaining = plan_milk(Decimal('100'), Decimal('0'), Decimal('318.2'), MILK_CONFIG)
        assert planned['DWP'] == Decimal('255.2')    # 58 * 4.40
        assert rate['DWP'] == Decimal('4.40')
        assert planned['SWP'] == Decimal('63')       # 42 * 1.50
        assert remaining == Decimal('0')

    def test_worked_example_from_spec(self):
        # Milk Qty 36,017.67 / Balance 142,301.90 from the HSN 0404 spec.
        planned, rate, remaining = plan_milk(
            Decimal('36017.67'), Decimal('0'), Decimal('142301.90'), MILK_CONFIG,
        )
        assert rate['DWP'] == Decimal('4.40')
        assert planned['DWP'] + planned['SWP'] == Decimal('142301.90')
        assert remaining == Decimal('0')

    def test_avg_below_swp_rate_partial_qty_only_swp_used(self):
        # avg = 30/50 = 0.60, below even the SWP rate -> the balance can't
        # cover the full qty at any allowed rate; spend it all on SWP and
        # leave the rest of the milk qty unplanned (mirrors allocate_step's
        # insufficient-balance behaviour elsewhere in the codebase).
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('0'), Decimal('30'), MILK_CONFIG)
        assert planned['DWP'] == Decimal('0')
        assert planned['SWP'] == Decimal('30')       # 20 units * 1.50, not all 50
        assert remaining == Decimal('0')


class TestPlanMilk3502Only(TestCase):

    def test_full_qty_to_wpc_at_configured_price(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('10'), Decimal('5000'), MILK_CONFIG)
        assert planned['WPC'] == Decimal('250')   # 10 * 25
        assert rate['WPC'] == Decimal('25')
        assert planned['DWP'] == Decimal('0')
        assert planned['SWP'] == Decimal('0')
        assert remaining == Decimal('4750')

    def test_wpc_capped_when_balance_insufficient(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('10'), Decimal('100'), MILK_CONFIG)
        assert planned['WPC'] == Decimal('100')
        assert rate['WPC'] == Decimal('10')   # 100 / 10
        assert remaining == Decimal('0')


class TestPlanMilkMixedRunsSequentially(TestCase):
    """E1 has no average-price concept — both present just runs 0404 then
    3502, back to back, against the same shrinking balance."""

    def test_runs_0404_then_3502_sequentially(self):
        # avg for the 0404 leg = 5000/50 = 100 >= 6.50 -> full qty to DWP at the
        # ceiling, no SWP.
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('5000'), MILK_CONFIG)
        assert planned['DWP'] == CEILING_CIF_50KG   # 50 * 6.50 = 325
        assert planned['SWP'] == Decimal('0')
        assert planned['WPC'] == Decimal('250')    # 10 * 25, after DWP drew down balance
        assert remaining == Decimal('5000') - CEILING_CIF_50KG - Decimal('250')   # 4425


class TestPlanMilkEdgeCases(TestCase):

    def test_zero_quantities_and_balance_no_op(self):
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('0'), Decimal('5000'), MILK_CONFIG)
        assert planned['DWP'] == planned['SWP'] == planned['WPC'] == Decimal('0')
        assert remaining == Decimal('5000')

    def test_negative_balance_plans_zero(self):
        planned, rate, remaining = plan_milk(Decimal('50'), Decimal('10'), Decimal('-1'), MILK_CONFIG)
        assert planned['DWP'] == planned['SWP'] == planned['WPC'] == Decimal('0')

    def test_tolerant_type_coercion(self):
        planned, rate, remaining = plan_milk('50', None, '5000', MILK_CONFIG)
        assert planned['DWP'] == CEILING_CIF_50KG   # 50 * 6.50 = 325

    def test_milk_config_is_frozen(self):
        with self.assertRaises(Exception):
            MILK_CONFIG.dwp_price = Decimal('99')  # type: ignore[misc]

    def test_custom_config_is_supported(self):
        custom = MilkConfig(dwp_price=Decimal('10'), dwp_min_price=Decimal('8'), swp_price=Decimal('2'), wpc_price=Decimal('30'))
        planned, rate, remaining = plan_milk(Decimal('0'), Decimal('5'), Decimal('1000'), custom)
        assert planned['WPC'] == Decimal('150')   # 5 * 30
