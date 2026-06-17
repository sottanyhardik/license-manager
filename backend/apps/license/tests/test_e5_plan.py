"""Unit tests for the E5 utilization-planning waterfall."""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.e5_plan import (
    BALANCE_CIF_USD,
    E5_CATS,
    E5_UNIT_PRICES,
    WPC_MAX_PRICE,
    WPC_MIN_PRICE,
    classify_e5_hsn,
    classify_e5_item,
    compute_e5_plan,
    is_wheat_flour,
)


def _totals(**kwargs) -> dict[str, float]:
    """Build a complete E5 totals dict, defaulting missing categories to 0."""
    base = {cat: 0.0 for cat in E5_CATS}
    base.update(kwargs)
    return base


def _planned_sum(planned: dict[str, float]) -> float:
    return sum(planned.values())


class TestClassifyE5Item(TestCase):
    """Item / HSN / description bucketing."""

    def test_dietary_fibre_item_routes_to_dietary_fibre(self):
        # The "DIETARY FIBRE - E5, WALNUT - E5" combo (the real-world pattern)
        # has 'dietary fibre' in its item key.
        assert classify_e5_item('DIETARY FIBRE - E5, WALNUT - E5', '08029900', '') == 'DIETARY FIBRE'

    def test_dietary_fibre_description_routes_to_dietary_fibre(self):
        assert classify_e5_item('FOOD ITEM', '', 'Dietary Fibre') == 'DIETARY FIBRE'

    def test_walnut_alone_does_not_match_dietary_fibre(self):
        # 'FOOD FLAVOUR - E5, FRUIT JUICE - E5, WALNUT - E5' contains 'walnut'
        # but is NOT a dietary-fibre row — must not fold into DIETARY FIBRE.
        assert classify_e5_item(
            'FOOD FLAVOUR - E5, FRUIT JUICE - E5, WALNUT - E5',
            '08022200',
            'Food Flavour - Fruit Flavour',
        ) is None

    def test_swp_item_matches(self):
        assert classify_e5_item('SWP', '', '') == 'SWP'

    def test_hsn_0404_routes_to_swp(self):
        assert classify_e5_item('SOMETHING', '04041010', '') == 'SWP'

    def test_description_0404_routes_to_swp(self):
        assert classify_e5_item('OTHER', '', 'Milk product (0404)') == 'SWP'

    def test_pko_item_matches(self):
        assert classify_e5_item('PKO', '', '') == 'PKO'

    def test_hsn_1513_routes_to_pko(self):
        assert classify_e5_item('OTHER', '15132110', '') == 'PKO'

    def test_rbd_item_matches(self):
        assert classify_e5_item('RBD', '', '') == 'RBD'

    def test_hsn_1511_routes_to_rbd(self):
        assert classify_e5_item('OTHER', '15119020', '') == 'RBD'

    def test_olive_oil_matches(self):
        assert classify_e5_item('Olive Oil', '', '') == 'OLIVE OIL'

    def test_wpc_requires_item_and_3502_signal(self):
        # Item + HSN 3502 → WPC.
        assert classify_e5_item('WPC', '35021100', '') == 'WPC'
        # Item + description containing 3502 → WPC.
        assert classify_e5_item('WPC', '', 'milk albumin (3502)') == 'WPC'

    def test_wpc_item_alone_does_not_match_wpc_bucket(self):
        # An item literally named "WPC" but with no 3502 signal should NOT
        # be routed to WPC. It falls through and ends unclassified (or hits
        # another bucket if the HSN matches one).
        assert classify_e5_item('WPC', '', '') is None
        # With an HSN 0404 it should fall through to SWP because 'wpc' alone
        # isn't enough — SWP's 0404 rule wins.
        assert classify_e5_item('WPC', '04041010', '') == 'SWP'

    def test_3502_signal_alone_does_not_match_wpc(self):
        # 3502 without a "WPC" item name should not classify as WPC — only
        # the joint condition counts.
        assert classify_e5_item('SOMETHING_ELSE', '35021100', '') is None

    def test_wheat_flour_item_matches(self):
        assert classify_e5_item('Wheat Flour', '', '') == 'WHEAT FLOUR'

    def test_wheat_flour_legacy_hsn_matches(self):
        assert classify_e5_item('OTHER', '11010000', '') == 'WHEAT FLOUR'

    def test_unclassified_returns_none(self):
        assert classify_e5_item('CARDBOARD', '4819', 'Packing box') is None

    def test_classify_hsn_compat_shim_still_works(self):
        # HSN-only classifier still handles the SWP/PKO/RBD/WF buckets.
        assert classify_e5_hsn('04041010') == 'SWP'
        assert classify_e5_hsn('15132110') == 'PKO'
        assert classify_e5_hsn('15119020') == 'RBD'
        assert classify_e5_hsn('11010000') == 'WHEAT FLOUR'
        # WPC requires the item name, so HSN-only is None.
        assert classify_e5_hsn('35021100') is None

    def test_is_wheat_flour_legacy_helper(self):
        assert is_wheat_flour('11010000') is True
        assert is_wheat_flour('1101 00 00') is False  # spaces not stripped
        assert is_wheat_flour('0404') is False


class TestComputeE5PlanFixedSteps(TestCase):
    """Steps 1-5 fixed-rate waterfall."""

    def test_dietary_fibre_allocation(self):
        totals = _totals(**{'DIETARY FIBRE': 1000.0})
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        assert planned['DIETARY FIBRE'] == 2700.0   # 1000 * 2.7

    def test_swp_allocation(self):
        totals = _totals(**{'SWP': 4000.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('10000'))
        # SWP qty>0 + remaining>0 triggers Step 6 recalc → balance is folded in.
        # Original SWP util = 4000*1.5 = 6000. Recalc adds 4000 left, total 10000.
        assert planned['SWP'] == 10000.0

    def test_pko_allocation(self):
        totals = _totals(**{'PKO': 1000.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['PKO'] == 2300.0   # 1000 * 2.3

    def test_rbd_allocation(self):
        totals = _totals(**{'RBD': 1000.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['RBD'] == 1200.0   # 1000 * 1.2

    def test_olive_oil_allocation(self):
        totals = _totals(**{'OLIVE OIL': 100.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['OLIVE OIL'] == 550.0   # 100 * 5.5


class TestSwpReallocation(TestCase):
    """Step 6 SWP rate recalc behaviour."""

    def test_swp_recalc_when_balance_remains_and_swp_present(self):
        totals = _totals(
            **{
                'DIETARY FIBRE': 1000.0,
                'SWP': 5000.0,
                'PKO': 3000.0,
                'RBD': 4000.0,
                'OLIVE OIL': 1000.0,
            }
        )
        planned, rate = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)

        step15 = 2700 + 7500 + 6900 + 4800 + 5500
        remainder = float(BALANCE_CIF_USD) - step15
        expected_swp_plan = 7500 + remainder
        expected_swp_rate = expected_swp_plan / 5000.0

        assert abs(planned['SWP'] - expected_swp_plan) < 1e-4
        assert abs(rate['SWP'] - expected_swp_rate) < 1e-4

    def test_swp_recalc_skipped_when_no_swp_qty(self):
        totals = _totals(**{'DIETARY FIBRE': 100.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('1000'))
        # No recalc → SWP stays at its fixed unit price.
        assert rate['SWP'] == float(E5_UNIT_PRICES['SWP'])


class TestWpcDynamicPricing(TestCase):
    """Step 7 WPC dynamic price band [0, 22]."""

    def test_wpc_at_max_price_when_balance_is_plentiful(self):
        # Balance large enough that 22 * qty fits — cap at max.
        totals = _totals(**{'WPC': 100.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['WPC'] == 2200.0     # 100 * 22
        assert rate['WPC'] == float(WPC_MAX_PRICE)

    def test_wpc_at_min_price_when_balance_is_zero(self):
        # With a 0 floor, an exhausted balance simply means no WPC.
        totals = _totals(**{'WPC': 100.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('0'))
        assert planned['WPC'] == 0.0
        assert rate['WPC'] == float(WPC_MIN_PRICE)

    def test_wpc_within_range_when_balance_in_middle(self):
        # Balance below 22*qty → dynamic rate consumes the whole balance.
        totals = _totals(**{'WPC': 100.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('1800'))
        assert planned['WPC'] == 1800.0
        assert WPC_MIN_PRICE <= Decimal(str(rate['WPC'])) <= WPC_MAX_PRICE
        # Expected rate = 1800 / 100 = 18.
        assert rate['WPC'] == 18.0

    def test_wpc_consumes_full_balance_when_below_max(self):
        # 100 * 22 = 2200 fits comfortably above balance 500 → WPC takes the
        # entire 500 at an effective rate of 5.0 (in band since min is 0).
        totals = _totals(**{'WPC': 100.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('500'))
        assert planned['WPC'] == 500.0
        assert rate['WPC'] == 5.0


class TestWheatFlourMopUp(TestCase):
    """Step 8 final wheat-flour residual consumption."""

    def test_wheat_flour_consumes_remaining_balance(self):
        # No qty in any earlier step → entire balance goes to wheat flour.
        totals = _totals(**{'WHEAT FLOUR': 10000.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('1000'))
        assert planned['WHEAT FLOUR'] == 1000.0
        # Dynamic rate = 1000 / 10000 = 0.1.
        assert rate['WHEAT FLOUR'] == 0.1

    def test_final_balance_zero_when_wheat_flour_present(self):
        totals = _totals(
            **{
                'DIETARY FIBRE': 100.0,
                'PKO': 100.0,
                'WPC': 10.0,
                'WHEAT FLOUR': 50000.0,
            }
        )
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        total_planned = _planned_sum(planned)
        assert abs(total_planned - float(BALANCE_CIF_USD)) < 1e-4

    def test_wheat_flour_skipped_when_no_qty(self):
        totals = _totals(**{'DIETARY FIBRE': 100.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('1000'))
        # Wheat Flour qty = 0 → no allocation. Residual stays unallocated.
        assert planned['WHEAT FLOUR'] == 0.0


class TestFullWaterfall(TestCase):
    """End-to-end checks across the full pipeline."""

    def test_balance_never_exceeded(self):
        totals = _totals(**{cat: 1_000_000.0 for cat in E5_CATS})
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        # Total planned must never exceed the starting balance.
        assert _planned_sum(planned) <= float(BALANCE_CIF_USD) + 1e-4

    def test_zero_quantities_leave_balance_intact(self):
        planned, _ = compute_e5_plan(_totals(), license_balance=BALANCE_CIF_USD)
        assert _planned_sum(planned) == 0.0

    def test_sequential_deduction_order(self):
        # Construct a balance so small that only Step 1 can run — that proves
        # Steps 2+ honour the depleted balance.
        totals = _totals(**{cat: 10.0 for cat in E5_CATS})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('20'))
        # Dietary Fibre eats 10*2.7=27 → clamped at 20.
        assert planned['DIETARY FIBRE'] == 20.0
        # SWP qty=10 + remaining=0 means Step 6 recalc doesn't fire (remaining
        # not > 0), so SWP stays at zero too.
        assert planned['SWP'] == 0.0
        assert planned['PKO'] == 0.0
        assert planned['RBD'] == 0.0
        assert planned['OLIVE OIL'] == 0.0
        assert planned['WPC'] == 0.0
        # Wheat Flour also blocked (remaining is 0).
        assert planned['WHEAT FLOUR'] == 0.0

    def test_step_caps_when_dietary_fibre_overshoots(self):
        totals = _totals(
            **{
                'DIETARY FIBRE': 30000.0,
                'SWP': 5000.0,
                'PKO': 3000.0,
                'RBD': 4000.0,
                'OLIVE OIL': 1000.0,
                'WPC': 200.0,
                'WHEAT FLOUR': 1000.0,
            }
        )
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        assert planned['DIETARY FIBRE'] == float(BALANCE_CIF_USD)
        for cat in ('SWP', 'PKO', 'RBD', 'OLIVE OIL', 'WPC', 'WHEAT FLOUR'):
            assert planned[cat] == 0.0

    def test_full_waterfall_with_wheat_flour_finishing_at_zero(self):
        # SWP qty=0 keeps the recalc step quiet so WPC + Wheat Flour both
        # get exercised end-to-end.
        totals = _totals(
            **{
                'DIETARY FIBRE': 1000.0,
                'PKO': 3000.0,
                'RBD': 4000.0,
                'OLIVE OIL': 1000.0,
                'WPC': 100.0,
                'WHEAT FLOUR': 5000.0,
            }
        )
        planned, rate = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)

        # 1000*2.7 + 3000*2.3 + 4000*1.2 + 1000*5.5 = 2700+6900+4800+5500 = 19900
        # Remaining after step 5 = 69046.90 - 19900 = 49146.90
        # WPC: balance 49146.90 vs qty 100 → max price 22 fits (100*22=2200)
        # → planned WPC = 2200, rate = 22.
        # Remaining after WPC = 49146.90 - 2200 = 46946.90
        # Wheat Flour eats all of it: 46946.90 / 5000 = 9.3894 per unit.
        assert planned['DIETARY FIBRE'] == 2700.0
        assert planned['PKO'] == 6900.0
        assert planned['RBD'] == 4800.0
        assert planned['OLIVE OIL'] == 5500.0
        assert planned['WPC'] == 2200.0
        assert rate['WPC'] == float(WPC_MAX_PRICE)
        assert abs(planned['WHEAT FLOUR'] - 46946.90) < 1e-4
        # Final balance == 0.
        assert abs(_planned_sum(planned) - float(BALANCE_CIF_USD)) < 1e-4

    def test_exact_balance_via_swp_recalc(self):
        totals = _totals(
            **{
                'DIETARY FIBRE': 1000.0,
                'SWP': 5000.0,
                'PKO': 3000.0,
                'RBD': 4000.0,
                'OLIVE OIL': 1000.0,
            }
        )
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        assert abs(_planned_sum(planned) - float(BALANCE_CIF_USD)) < 1e-4

    def test_legacy_wf_qty_override_still_works(self):
        # Legacy call pattern: classifier didn't put wheat flour in totals,
        # caller passed wf_qty separately.
        totals = _totals(**{'DIETARY FIBRE': 100.0})
        planned, _ = compute_e5_plan(
            totals,
            wf_qty=10000.0,
            license_balance=Decimal('1000'),
        )
        # 100*2.7 = 270 → remaining 730 → wheat flour consumes it.
        assert planned['WHEAT FLOUR'] == 730.0

    def test_default_balance_uses_spec_constant(self):
        totals = _totals(**{'DIETARY FIBRE': 10.0})
        planned, _ = compute_e5_plan(totals)  # license_balance omitted
        assert planned['DIETARY FIBRE'] == 27.0
