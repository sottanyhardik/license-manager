"""Unit tests for the E5 utilization-planning waterfall."""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.e5_plan import (
    BALANCE_CIF_USD,
    E5_CATS,
    E5_UNIT_PRICES,
    classify_e5_hsn,
    classify_e5_item,
    compute_e5_plan,
    is_wheat_flour,
)
from apps.license.services.milk_planner import MILK_CONFIG_E5


def _totals(**kwargs) -> dict[str, float]:
    """Build a complete E5 totals dict, defaulting missing categories to 0."""
    base = {cat: 0.0 for cat in E5_CATS}
    base.update(kwargs)
    return base


def _planned_sum(planned: dict[str, float]) -> float:
    # DWP/SWP are folded into MILK PRODUCTS / EGG ALBUMIN for the bucket
    # total, so summing everything would double-count them.
    return sum(v for k, v in planned.items() if k in E5_CATS)


class TestClassifyE5Item(TestCase):
    """Item / HSN / description bucketing."""

    def test_dietary_fibre_item_routes_to_dietary_fibre(self):
        assert classify_e5_item('DIETARY FIBRE - E5, WALNUT - E5', '08029900', '') == 'DIETARY FIBRE'

    def test_dietary_fibre_description_routes_to_dietary_fibre(self):
        assert classify_e5_item('FOOD ITEM', '', 'Dietary Fibre') == 'DIETARY FIBRE'

    def test_walnut_alone_does_not_match_dietary_fibre(self):
        assert classify_e5_item(
            'FOOD FLAVOUR - E5, FRUIT JUICE - E5, WALNUT - E5',
            '08022200',
            'Food Flavour - Fruit Flavour',
        ) is None

    def test_milk_products_by_hsn_0404(self):
        assert classify_e5_item('SOMETHING', '04041010', '') == 'MILK PRODUCTS'

    def test_egg_albumin_wpc_by_hsn_3502(self):
        assert classify_e5_item('SOMETHING', '35021100', '') == 'EGG ALBUMIN / WPC'

    def test_swp_wpc_item_names_no_longer_classify_on_their_own(self):
        # The old item-name-based SWP/WPC rules are gone — an item literally
        # named "SWP" or "WPC" with no 0404/3502 HSN now falls unclassified.
        assert classify_e5_item('SWP', '', '') is None
        assert classify_e5_item('WPC', '', '') is None

    def test_wheat_flour_item_beats_milk_hsn(self):
        # Legacy full-name rule is checked BEFORE the new 0404/3502 rules —
        # preserves old precedence exactly (no real item should ever hit
        # this, but the rule ordering itself must not change).
        assert classify_e5_item('Wheat Flour', '04041000', '') == 'WHEAT FLOUR'

    def test_wheat_flour_item_matches(self):
        assert classify_e5_item('Wheat Flour', '', '') == 'WHEAT FLOUR'

    def test_wheat_flour_legacy_hsn_matches(self):
        assert classify_e5_item('OTHER', '11010000', '') == 'WHEAT FLOUR'

    def test_olive_oil_item_beats_palm_kernel_hsn(self):
        # Preserved precedence: an item explicitly named "Olive Oil" still
        # routes to Remaining Oils even with an HSN in the 1513 range.
        assert classify_e5_item('Olive Oil', '15132110', '') == 'REMAINING OILS'

    def test_milk_hsn_beats_olive_oil_item_name(self):
        # New spec priority: Milk Products (rule 2) is checked before the
        # legacy Olive-Oil-by-name rule — milk wins even on an oddly-named row.
        assert classify_e5_item('Olive Oil', '04041000', '') == 'MILK PRODUCTS'

    def test_palm_kernel_oil_by_hsn_1513(self):
        assert classify_e5_item('OTHER', '15132110', '') == 'PALM KERNEL OIL'

    def test_palm_kernel_oil_by_description(self):
        assert classify_e5_item('OTHER', '', 'Vegetable Oil blend') == 'PALM KERNEL OIL'

    def test_palm_kernel_oil_by_item_name(self):
        assert classify_e5_item('PKO', '', '') == 'PALM KERNEL OIL'

    def test_rbd_palmolein_by_hsn(self):
        assert classify_e5_item('OTHER', '15119020', '') == 'RBD PALMOLEIN'

    def test_rbd_palmolein_by_item_name(self):
        assert classify_e5_item('RBD', '', '') == 'RBD PALMOLEIN'

    def test_remaining_oils_by_hsn_chapter_15_catchall(self):
        assert classify_e5_item('OTHER', '15179090', '') == 'REMAINING OILS'

    def test_remaining_oils_by_edible_oil_description(self):
        assert classify_e5_item('OTHER', '', 'Refined Edible Oil') == 'REMAINING OILS'

    def test_unclassified_returns_none(self):
        assert classify_e5_item('CARDBOARD', '4819', 'Packing box') is None

    def test_null_blank_and_unicode_inputs_are_safe(self):
        assert classify_e5_item(None, None, None) is None
        assert classify_e5_item('', '   ', '   ') is None
        assert classify_e5_item('FOOD ITEM', '', 'Dietary Fibre \U0001f330') == 'DIETARY FIBRE'

    def test_classify_hsn_compat_shim_still_works(self):
        assert classify_e5_hsn('04041010') == 'MILK PRODUCTS'
        assert classify_e5_hsn('15132110') == 'PALM KERNEL OIL'
        assert classify_e5_hsn('15119020') == 'RBD PALMOLEIN'
        assert classify_e5_hsn('11010000') == 'WHEAT FLOUR'
        assert classify_e5_hsn('35021100') == 'EGG ALBUMIN / WPC'

    def test_is_wheat_flour_legacy_helper(self):
        assert is_wheat_flour('11010000') is True
        assert is_wheat_flour('1101 00 00') is False  # spaces not stripped
        assert is_wheat_flour('0404') is False


class TestComputeE5PlanFixedSteps(TestCase):
    """Rule 1 + Rule 2 fixed-rate steps."""

    def test_dietary_fibre_allocation(self):
        totals = _totals(**{'DIETARY FIBRE': 1000.0})
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        assert planned['DIETARY FIBRE'] == 3000.0   # 1000 * 3.00

    def test_palm_kernel_oil_allocation(self):
        totals = _totals(**{'PALM KERNEL OIL': 1000.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['PALM KERNEL OIL'] == 1800.0   # 1000 * 1.8

    def test_rbd_palmolein_allocation(self):
        totals = _totals(**{'RBD PALMOLEIN': 1000.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['RBD PALMOLEIN'] == 1200.0   # 1000 * 1.2

    def test_remaining_oils_allocation(self):
        totals = _totals(**{'REMAINING OILS': 100.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['REMAINING OILS'] == 500.0   # 100 * 5.00


class TestSpecialValidation(TestCase):
    """Milk-priority gate executed immediately after Rule 1."""

    def test_triggers_when_balance_cannot_cover_milk_at_swp_price(self):
        # milk_total=1000, threshold = 1000*1.5 = 1500 > remaining(1000) → fires.
        totals = _totals(**{'MILK PRODUCTS': 1000.0, 'PALM KERNEL OIL': 500.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('1000'))
        # All milk planned as a flat, balance-capped SWP allocation.
        assert planned['SWP'] == 1000.0
        assert rate['SWP'] == 1.0   # 1000 balance / 1000 qty
        assert planned['MILK PRODUCTS'] == 1000.0
        assert planned['DWP'] == 0.0   # Rule 3 (normal milk optimisation) skipped
        # Oils run AFTER milk, with whatever balance remains (0 here).
        assert planned['PALM KERNEL OIL'] == 0.0

    def test_not_triggered_runs_oils_before_milk(self):
        # milk_total=50, threshold=75; balance is plentiful → not triggered.
        totals = _totals(**{'MILK PRODUCTS': 50.0, 'PALM KERNEL OIL': 100.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['PALM KERNEL OIL'] == 180.0   # 100 * 1.8, ran normally
        assert planned['DWP'] == 250.0   # 50 * 5 — Rule 3 ran (not skipped)

    def test_not_triggered_when_no_milk_present(self):
        totals = _totals(**{'PALM KERNEL OIL': 100.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('1'))
        # milk_total == 0 → special validation never fires; nothing to skip.
        assert planned['SWP'] == 0.0
        assert planned['DWP'] == 0.0


class TestMilkRule3(TestCase):
    """Rule 3 — delegated to the shared milk_planner (MILK_CONFIG_E5)."""

    def test_0404_only_dwp_then_swp_share_same_utilization_qty(self):
        totals = _totals(**{'MILK PRODUCTS': 50.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['DWP'] == 250.0     # 50 * 5
        assert planned['SWP'] == 75.0      # 50 * 1.5 (same 50 units, not split)
        assert planned['MILK PRODUCTS'] == 325.0
        assert rate['MILK PRODUCTS'] == 6.5

    def test_3502_only_full_qty_to_wpc_at_25(self):
        totals = _totals(**{'EGG ALBUMIN / WPC': 10.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('5000'))
        assert planned['EGG ALBUMIN / WPC'] == 250.0   # 10 * 25
        assert rate['EGG ALBUMIN / WPC'] == 25.0
        assert planned['DWP'] == 0.0
        assert planned['SWP'] == 0.0

    def test_mixed_avg_price_band_b_swp_then_dwp_residual(self):
        # total_qty=100, remaining=300 → avg=3.0 (band 1.50<=avg<5.00).
        # q_swp = floor((5*100-300)/3.5) = floor(57.14) = 57 → cif=85.5
        # cif_dwp = 300 - 85.5 = 214.5 (exact residual, balance -> 0).
        totals = _totals(**{'MILK PRODUCTS': 50.0, 'EGG ALBUMIN / WPC': 50.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('300'))
        assert abs(planned['SWP'] - 85.5) < 1e-4
        assert abs(planned['DWP'] - 214.5) < 1e-4
        # Split 50/50 between the two buckets by qty share.
        assert abs(planned['MILK PRODUCTS'] - 150.0) < 1e-4
        assert abs(planned['EGG ALBUMIN / WPC'] - 150.0) < 1e-4

    def test_mixed_avg_below_1_50_is_unreachable_special_validation_wins(self):
        # avg = remaining/total_qty < 1.50 is EXACTLY Special Validation's own
        # trigger condition (remaining < milk_total * 1.50) — so Rule 3A's
        # Case A can never actually fire through compute_e5_plan; Special
        # Validation always intercepts first and plans milk with the
        # standard (balance-capped) dynamic rate instead of the fixed 1.50.
        # See TestMilkPlanner for Case A exercised directly on the shared engine.
        totals = _totals(**{'MILK PRODUCTS': 500.0, 'EGG ALBUMIN / WPC': 500.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('1000'))
        assert planned['SWP'] == 1000.0
        assert planned['DWP'] == 0.0
        assert rate['SWP'] == 1.0   # 1000 balance / 1000 qty, capped — not the fixed 1.5

    def test_mixed_avg_at_or_above_20_full_qty_to_wpc_surplus_flows_back(self):
        # total_qty=20, remaining=500 → avg=25 (>= 20) → WPC takes 20*20=400,
        # the 100 surplus flows back to the caller (here: Wheat Flour mop-up).
        totals = _totals(
            **{'MILK PRODUCTS': 10.0, 'EGG ALBUMIN / WPC': 10.0, 'WHEAT FLOUR': 1000.0},
        )
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('500'))
        assert planned['MILK PRODUCTS'] + planned['EGG ALBUMIN / WPC'] == 400.0
        assert rate['WHEAT FLOUR'] == 0.1   # 100 surplus / 1000 qty


class TestWheatFlourMopUp(TestCase):
    """Legacy final step — preserved unchanged."""

    def test_wheat_flour_consumes_remaining_balance(self):
        totals = _totals(**{'WHEAT FLOUR': 10000.0})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('1000'))
        assert planned['WHEAT FLOUR'] == 1000.0
        assert rate['WHEAT FLOUR'] == 0.1

    def test_wheat_flour_skipped_when_no_qty(self):
        totals = _totals(**{'DIETARY FIBRE': 100.0})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('1000'))
        assert planned['WHEAT FLOUR'] == 0.0

    def test_legacy_wf_qty_override_still_works(self):
        totals = _totals(**{'DIETARY FIBRE': 100.0})
        planned, _ = compute_e5_plan(totals, wf_qty=10000.0, license_balance=Decimal('1000'))
        # 100*3.00 = 300 → remaining 700 → wheat flour consumes it.
        assert planned['WHEAT FLOUR'] == 700.0


class TestFullWaterfall(TestCase):
    """End-to-end checks across the full pipeline."""

    def test_balance_never_exceeded(self):
        totals = _totals(**{cat: 1_000_000.0 for cat in E5_CATS})
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        assert _planned_sum(planned) <= float(BALANCE_CIF_USD) + 1e-4

    def test_zero_quantities_leave_balance_intact(self):
        planned, _ = compute_e5_plan(_totals(), license_balance=BALANCE_CIF_USD)
        assert _planned_sum(planned) == 0.0

    def test_invalid_quantities_and_negative_balance_plan_zero(self):
        totals = _totals(**{'DIETARY FIBRE': 'bad', 'MILK PRODUCTS': None, 'EGG ALBUMIN / WPC': '100'})
        planned, rate = compute_e5_plan(totals, license_balance=Decimal('-1'))
        assert _planned_sum(planned) == 0.0
        assert rate['EGG ALBUMIN / WPC'] == 25.0

    def test_sequential_deduction_order(self):
        # Balance so small only Rule 1 can run.
        totals = _totals(**{cat: 10.0 for cat in E5_CATS})
        planned, _ = compute_e5_plan(totals, license_balance=Decimal('20'))
        # Dietary Fibre eats 10*3.00=30 → clamped at 20.
        assert planned['DIETARY FIBRE'] == 20.0
        for cat in ('PALM KERNEL OIL', 'RBD PALMOLEIN', 'REMAINING OILS', 'WHEAT FLOUR'):
            assert planned[cat] == 0.0
        assert planned['MILK PRODUCTS'] == 0.0
        assert planned['EGG ALBUMIN / WPC'] == 0.0

    def test_step_caps_when_dietary_fibre_overshoots(self):
        totals = _totals(
            **{
                'DIETARY FIBRE': 30000.0,
                'MILK PRODUCTS': 50.0,
                'EGG ALBUMIN / WPC': 10.0,
                'PALM KERNEL OIL': 3000.0,
                'RBD PALMOLEIN': 4000.0,
                'REMAINING OILS': 1000.0,
                'WHEAT FLOUR': 1000.0,
            }
        )
        planned, _ = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)
        assert planned['DIETARY FIBRE'] == float(BALANCE_CIF_USD)
        for cat in ('MILK PRODUCTS', 'EGG ALBUMIN / WPC', 'PALM KERNEL OIL',
                    'RBD PALMOLEIN', 'REMAINING OILS', 'WHEAT FLOUR'):
            assert planned[cat] == 0.0

    def test_full_waterfall_with_wheat_flour_finishing_at_zero(self):
        totals = _totals(
            **{
                'DIETARY FIBRE': 1000.0,
                'PALM KERNEL OIL': 3000.0,
                'RBD PALMOLEIN': 4000.0,
                'REMAINING OILS': 1000.0,
                'EGG ALBUMIN / WPC': 100.0,
                'WHEAT FLOUR': 5000.0,
            }
        )
        planned, rate = compute_e5_plan(totals, license_balance=BALANCE_CIF_USD)

        # 1000*3.00 + 3000*1.80 + 4000*1.20 + 1000*5.00 = 3000+5400+4800+5000 = 18200
        # Remaining after Rule 2 = 69046.90 - 18200 = 50846.90
        # Rule 3: no 0404 → straight to WPC, 100*25 = 2500 fits comfortably.
        # Remaining after WPC = 50846.90 - 2500 = 48346.90 → all to Wheat Flour.
        assert planned['DIETARY FIBRE'] == 3000.0
        assert planned['PALM KERNEL OIL'] == 5400.0
        assert planned['RBD PALMOLEIN'] == 4800.0
        assert planned['REMAINING OILS'] == 5000.0
        assert planned['EGG ALBUMIN / WPC'] == 2500.0
        assert rate['EGG ALBUMIN / WPC'] == 25.0
        assert abs(planned['WHEAT FLOUR'] - 48346.90) < 1e-4
        assert abs(_planned_sum(planned) - float(BALANCE_CIF_USD)) < 1e-4

    def test_default_balance_uses_spec_constant(self):
        totals = _totals(**{'DIETARY FIBRE': 10.0})
        planned, _ = compute_e5_plan(totals)  # license_balance omitted
        assert planned['DIETARY FIBRE'] == 30.0


class TestMilkConfigE5Constants(TestCase):

    def test_prices_match_spec(self):
        assert MILK_CONFIG_E5.dwp_price == Decimal('5')
        assert MILK_CONFIG_E5.swp_price == Decimal('1.5')
        assert MILK_CONFIG_E5.wpc_price == Decimal('25')
        assert MILK_CONFIG_E5.mixed_wpc_price == Decimal('20')
        assert MILK_CONFIG_E5.average_split is True

    def test_e5_unit_prices_table(self):
        assert E5_UNIT_PRICES['DIETARY FIBRE'] == Decimal('3.00')
        assert E5_UNIT_PRICES['PALM KERNEL OIL'] == Decimal('1.80')
        assert E5_UNIT_PRICES['RBD PALMOLEIN'] == Decimal('1.20')
        assert E5_UNIT_PRICES['REMAINING OILS'] == Decimal('5.00')
