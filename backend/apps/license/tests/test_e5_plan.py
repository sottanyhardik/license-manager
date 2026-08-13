"""Unit tests for the E5 utilization-planning engine (``plan_e5_items``)."""
from decimal import Decimal
from unittest import TestCase

from apps.license.services.e5_plan import (
    DWP_PRICE,
    E5_UNIT_PRICES,
    E5Item,
    E5PlanLine,
    classify_e5_hsn,
    classify_e5_item,
    is_wheat_flour,
    plan_e5_items,
)

# DWP rate ceiling of the shared milk splitter (``MILK_CONFIG.dwp_price``, which
# E5 aliases as ``DWP_PRICE``), numerically pinned in ``test_milk_planner.py``
# and tied back to the engine by
# ``TestUnitPricesTable.test_milk_dwp_ceiling_matches_shared_milk_config``.
# Milk expectations below are arithmetic against this one constant.
DWP_CEILING = Decimal('6.5')
# 50 kg planned at that ceiling — the recurring figure (50 * 6.50 = 325).
CEILING_CIF_50KG = Decimal('50') * DWP_CEILING


def _lines_by_step(result, step) -> list[E5PlanLine]:
    return [ln for ln in result.lines if ln.step == step]


def _cif(result, step) -> Decimal:
    return sum((ln.planned_cif for ln in _lines_by_step(result, step)), Decimal('0'))


class TestClassifyE5Item(TestCase):
    """Item / HSN / description bucketing — unchanged by the engine rewrite."""

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
        assert classify_e5_item('SWP', '', '') is None
        assert classify_e5_item('WPC', '', '') is None

    def test_wheat_flour_item_beats_milk_hsn(self):
        assert classify_e5_item('Wheat Flour', '04041000', '') == 'WHEAT FLOUR'

    def test_wheat_flour_item_matches(self):
        assert classify_e5_item('Wheat Flour', '', '') == 'WHEAT FLOUR'

    def test_wheat_flour_legacy_hsn_matches(self):
        assert classify_e5_item('OTHER', '11010000', '') == 'WHEAT FLOUR'

    def test_olive_oil_item_beats_palm_kernel_hsn(self):
        assert classify_e5_item('Olive Oil', '15132110', '') == 'REMAINING OILS'

    def test_milk_hsn_beats_olive_oil_item_name(self):
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


class TestFixedRateSteps(TestCase):
    """Dietary Fibre + Edible Oils — unchanged fixed rates."""

    def test_dietary_fibre_allocation(self):
        items = [E5Item(key='a', category='DIETARY FIBRE', qty=Decimal('1000'))]
        result = plan_e5_items(items, Decimal('69046.90'))
        assert _cif(result, 'DIETARY FIBRE') == Decimal('3000.0000')

    def test_palm_kernel_oil_allocation(self):
        items = [E5Item(key='a', category='PALM KERNEL OIL', qty=Decimal('1000'))]
        result = plan_e5_items(items, Decimal('5000'))
        assert _cif(result, 'PALM KERNEL OIL') == Decimal('1800.0000')

    def test_rbd_palmolein_allocation(self):
        items = [E5Item(key='a', category='RBD PALMOLEIN', qty=Decimal('1000'))]
        result = plan_e5_items(items, Decimal('5000'))
        assert _cif(result, 'RBD PALMOLEIN') == Decimal('1200.0000')

    def test_remaining_oils_allocation(self):
        items = [E5Item(key='a', category='REMAINING OILS', qty=Decimal('100'))]
        result = plan_e5_items(items, Decimal('5000'))
        assert _cif(result, 'REMAINING OILS') == Decimal('500.0000')

    def test_e5_unit_prices_table(self):
        assert E5_UNIT_PRICES['DIETARY FIBRE'] == Decimal('3.00')
        assert E5_UNIT_PRICES['PALM KERNEL OIL'] == Decimal('1.80')
        assert E5_UNIT_PRICES['RBD PALMOLEIN'] == Decimal('1.20')
        assert E5_UNIT_PRICES['REMAINING OILS'] == Decimal('5.00')

    def test_milk_dwp_ceiling_matches_shared_milk_config(self):
        # Guard for this module's shared DWP_CEILING constant — if the shared
        # milk config's ceiling moves, this fails instead of silently
        # invalidating the derived milk expectations below.
        assert DWP_CEILING == DWP_PRICE


class TestSpecialValidation(TestCase):
    """Milk-priority gate executed immediately after Dietary Fibre."""

    def test_triggers_when_balance_cannot_cover_milk_at_swp_price(self):
        # milk_total=1000, threshold = 1000*1.5 = 1500 > remaining(1000) → fires.
        items = [
            E5Item(key='milk', category='MILK PRODUCTS', qty=Decimal('1000')),
            E5Item(key='oil', category='PALM KERNEL OIL', qty=Decimal('500')),
        ]
        result = plan_e5_items(items, Decimal('1000'))
        assert result.special_validation_triggered is True
        swp_lines = _lines_by_step(result, 'SWP')
        assert len(swp_lines) == 1
        assert swp_lines[0].key == 'milk'
        assert swp_lines[0].planned_cif == Decimal('1000.0000')
        assert swp_lines[0].unit_price == Decimal('1.0000')   # balance-capped, not 1.5
        assert _lines_by_step(result, 'DWP') == []            # normal milk skipped
        assert _lines_by_step(result, 'PALM KERNEL OIL') == []  # no balance left for oils

    def test_not_triggered_runs_oils_before_milk(self):
        # milk_total=50, threshold=75; balance is plentiful → not triggered.
        items = [
            E5Item(key='milk', category='MILK PRODUCTS', qty=Decimal('50')),
            E5Item(key='oil', category='PALM KERNEL OIL', qty=Decimal('100')),
        ]
        result = plan_e5_items(items, Decimal('5000'))
        assert result.special_validation_triggered is False
        assert _cif(result, 'PALM KERNEL OIL') == Decimal('180.0000')   # 100 * 1.80
        # Oils run first: 5000 - 180 = 4820 left, avg = 4820/50 = 96.40 >= 6.50
        # -> the whole 50 kg goes to DWP at the ceiling (50 * 6.50 = 325).
        assert _cif(result, 'DWP') == CEILING_CIF_50KG

    def test_not_triggered_when_no_milk_present(self):
        items = [E5Item(key='oil', category='PALM KERNEL OIL', qty=Decimal('100'))]
        result = plan_e5_items(items, Decimal('1'))
        assert result.special_validation_triggered is False
        assert _lines_by_step(result, 'SWP') == []
        assert _lines_by_step(result, 'DWP') == []

    def test_special_validation_covers_3502_items_too(self):
        items = [E5Item(key='wpc', category='EGG ALBUMIN / WPC', qty=Decimal('1000'))]
        result = plan_e5_items(items, Decimal('1000'))
        assert result.special_validation_triggered is True
        swp_lines = _lines_by_step(result, 'SWP')
        assert len(swp_lines) == 1
        assert swp_lines[0].key == 'wpc'
        assert _lines_by_step(result, 'WPC') == []

    def test_uses_unfiltered_milk_total_even_below_min_plan_qty(self):
        # A single milk item below the Auto-Plan min-plan-qty threshold still
        # counts toward the Special Validation trigger check (matches the
        # historic Auto-Plan behaviour: the check runs before the threshold
        # skip), even though it won't itself get a plan line.
        items = [E5Item(key='tiny', category='MILK PRODUCTS', qty=Decimal('10'))]
        result = plan_e5_items(items, Decimal('1'), min_plan_qty=Decimal('50'), floor_qty=True)
        assert result.special_validation_triggered is True
        assert result.lines == []   # below threshold — nothing actually planned


class TestMilkPerItemNoAveraging(TestCase):
    """0404 and 3502 are classified and priced per item — never averaged,
    even when both appear on the same licence (the removed Mixed-Milk
    average-price-banding rule)."""

    def test_0404_qty_partitioned_between_dwp_and_swp_not_shared(self):
        # avg = 318.2/100 = 3.182, below the 4.40 floor -> DWP is capped at
        # the largest quantity whose rate stays at exactly 4.40; SWP absorbs
        # the rest of the SAME item's quantity (not a second read of the
        # full 100 units, as the old engine did).
        items = [E5Item(key='m', category='MILK PRODUCTS', qty=Decimal('100'))]
        result = plan_e5_items(items, Decimal('318.2'))
        dwp = _lines_by_step(result, 'DWP')[0]
        swp = _lines_by_step(result, 'SWP')[0]
        assert dwp.planned_qty == Decimal('58')
        assert swp.planned_qty == Decimal('42')
        assert dwp.planned_qty + swp.planned_qty == Decimal('100')  # = item qty
        assert dwp.planned_cif == Decimal('255.2000')    # 58*4.40
        assert swp.planned_cif == Decimal('63.0000')     # 42*1.50
        assert result.remaining_cif == Decimal('0')

    def test_0404_avg_above_ceiling_all_dwp_no_swp(self):
        # avg = 5000/50 = 100 >= 6.50 -> DWP takes the full quantity at the
        # ceiling; nothing is left of the item's qty for SWP to read.
        items = [E5Item(key='m', category='MILK PRODUCTS', qty=Decimal('50'))]
        result = plan_e5_items(items, Decimal('5000'))
        dwp = _lines_by_step(result, 'DWP')[0]
        assert dwp.planned_qty == Decimal('50')
        assert dwp.unit_price == DWP_CEILING
        assert dwp.planned_cif == CEILING_CIF_50KG      # 50 * 6.50 = 325
        assert _lines_by_step(result, 'SWP') == []

    def test_3502_only_full_qty_to_wpc_capped_at_25(self):
        items = [E5Item(key='e', category='EGG ALBUMIN / WPC', qty=Decimal('10'))]
        result = plan_e5_items(items, Decimal('5000'))
        wpc = _lines_by_step(result, 'WPC')[0]
        assert wpc.planned_cif == Decimal('250.0000')  # 10*25
        assert wpc.unit_price == Decimal('25.0000')

    def test_3502_rate_capped_when_balance_would_imply_more_than_25(self):
        items = [E5Item(key='e', category='EGG ALBUMIN / WPC', qty=Decimal('10'))]
        result = plan_e5_items(items, Decimal('400'))   # implied rate 40 > 25 cap
        wpc = _lines_by_step(result, 'WPC')[0]
        assert wpc.unit_price == Decimal('25.0000')
        assert wpc.planned_cif == Decimal('250.0000')
        assert result.remaining_cif == Decimal('150')  # surplus flows onward

    def test_mixed_licence_items_never_blended_into_one_rate(self):
        items = [
            E5Item(key='m', category='MILK PRODUCTS', qty=Decimal('50')),
            E5Item(key='e', category='EGG ALBUMIN / WPC', qty=Decimal('50')),
        ]
        result = plan_e5_items(items, Decimal('375'))
        dwp = _lines_by_step(result, 'DWP')
        swp = _lines_by_step(result, 'SWP')
        wpc = _lines_by_step(result, 'WPC')
        # Balance raised 300 -> 375 so the 0404 leg still clears the (now 6.50)
        # DWP ceiling and still leaves something behind for the 3502 item.
        # The 0404 item is processed first against the full $375: avg = 7.50 >=
        # 6.50, so DWP takes the full 50 kg (50 * 6.50 = 325) and SWP gets
        # nothing (the item's qty is already exhausted). The 3502 item then sees
        # the leftover balance (375 - 325 = 50): 50 kg * $25 = 1250 > 50, so its
        # rate drops to 50/50 = $1.00 — entirely independent of the 0404 item.
        # No averaged rate.
        assert dwp and dwp[0].key == 'm' and dwp[0].planned_cif == CEILING_CIF_50KG
        assert swp == []
        assert wpc and wpc[0].key == 'e' and wpc[0].planned_cif == Decimal('50.0000')
        assert wpc[0].unit_price == Decimal('1.0000')
        assert result.remaining_cif == Decimal('0')

    def test_all_0404_items_processed_before_any_3502_item(self):
        items = [
            E5Item(key='e', category='EGG ALBUMIN / WPC', qty=Decimal('10')),
            E5Item(key='m', category='MILK PRODUCTS', qty=Decimal('10')),
        ]
        result = plan_e5_items(items, Decimal('1000'))
        # avg for milk = 1000/10 = 100 >= 6.50 -> full DWP at the ceiling, no
        # SWP (qty already exhausted); the leftover balance flows to the 3502
        # item afterwards.
        milk_steps = [ln.step for ln in result.lines if ln.category in ('MILK PRODUCTS', 'EGG ALBUMIN / WPC')]
        assert milk_steps == ['DWP', 'WPC']
        # 1000 - 10*6.50 (DWP = 65) - 10*25 (WPC = 250) = 685
        assert result.remaining_cif == Decimal('1000') - Decimal('10') * DWP_CEILING - Decimal('250')

    def test_multiple_0404_items_planned_independently_in_input_order(self):
        items = [
            E5Item(key='m1', category='MILK PRODUCTS', qty=Decimal('50')),
            E5Item(key='m2', category='MILK PRODUCTS', qty=Decimal('50')),
        ]
        result = plan_e5_items(items, Decimal('375'))
        m1_steps = {ln.step for ln in result.lines if ln.key == 'm1'}
        m2_lines = [ln for ln in result.lines if ln.key == 'm2']
        # Balance raised 300 -> 375 so m1 still clears the (now 6.50) ceiling
        # and still leaves a balance for m2: avg = 375/50 = 7.50 >= 6.50 ->
        # full DWP (50 * 6.50 = 325), no SWP — unlike the old engine, DWP no
        # longer also re-reads m1's qty for a second SWP pass, so m1 leaves
        # 375 - 325 = 50 behind for m2 instead of exhausting the balance by
        # itself.
        assert m1_steps == {'DWP'}
        assert _cif(result, 'DWP') == CEILING_CIF_50KG
        # m2 against the leftover 50: avg = 50/50 = 1.0 < 1.5 -> SWP only,
        # 50/1.5 = 33.3333... kg at 1.50 = the whole 50.
        assert {ln.step for ln in m2_lines} == {'SWP'}
        assert m2_lines[0].planned_cif == Decimal('50.0000')
        assert result.remaining_cif == Decimal('0')


class TestWheatFlourMopUp(TestCase):
    def test_wheat_flour_consumes_remaining_balance(self):
        items = [E5Item(key='wf', category='WHEAT FLOUR', qty=Decimal('10000'))]
        result = plan_e5_items(items, Decimal('1000'))
        wf = _lines_by_step(result, 'WHEAT FLOUR')[0]
        assert wf.planned_cif == Decimal('1000.0000')
        assert wf.unit_price == Decimal('0.1000')
        assert result.remaining_cif == Decimal('0')

    def test_wheat_flour_skipped_when_no_qty(self):
        items = [E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('100'))]
        result = plan_e5_items(items, Decimal('1000'))
        assert _lines_by_step(result, 'WHEAT FLOUR') == []


class TestBalanceRecalculation(TestCase):
    """Every debit must recalculate the balance before the next line runs —
    no step may reuse a stale, pre-debit balance."""

    def test_remaining_cif_decrements_after_every_line(self):
        items = [
            E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('10')),
            E5Item(key='m', category='MILK PRODUCTS', qty=Decimal('10')),
            E5Item(key='wf', category='WHEAT FLOUR', qty=Decimal('1000')),
        ]
        result = plan_e5_items(items, Decimal('100'))
        running = Decimal('100')
        for line in result.lines:
            assert line.planned_cif <= running
            running -= line.planned_cif
        assert running == result.remaining_cif

    def test_full_waterfall_balance_never_exceeded(self):
        items = [
            E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('1000')),
            E5Item(key='pko', category='PALM KERNEL OIL', qty=Decimal('3000')),
            E5Item(key='rbd', category='RBD PALMOLEIN', qty=Decimal('4000')),
            E5Item(key='oil', category='REMAINING OILS', qty=Decimal('1000')),
            E5Item(key='e', category='EGG ALBUMIN / WPC', qty=Decimal('100')),
            E5Item(key='wf', category='WHEAT FLOUR', qty=Decimal('5000')),
        ]
        balance = Decimal('69046.90')
        result = plan_e5_items(items, balance)
        total = sum((ln.planned_cif for ln in result.lines), Decimal('0'))
        assert total <= balance
        assert total + result.remaining_cif == balance

    def test_zero_quantities_leave_balance_intact(self):
        items = [E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('0'))]
        result = plan_e5_items(items, Decimal('69046.90'))
        assert result.lines == []
        assert result.remaining_cif == Decimal('69046.90')

    def test_negative_balance_plans_nothing(self):
        items = [E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('100'))]
        result = plan_e5_items(items, Decimal('-1'))
        assert result.lines == []

    def test_sequential_deduction_order(self):
        # Balance so small only Dietary Fibre can run.
        items = [
            E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('10')),
            E5Item(key='m', category='MILK PRODUCTS', qty=Decimal('10')),
            E5Item(key='e', category='EGG ALBUMIN / WPC', qty=Decimal('10')),
            E5Item(key='pko', category='PALM KERNEL OIL', qty=Decimal('10')),
        ]
        result = plan_e5_items(items, Decimal('20'))
        df = _lines_by_step(result, 'DIETARY FIBRE')[0]
        assert df.planned_cif == Decimal('20.0000')   # 10*3=30 clamped to 20
        assert result.remaining_cif == Decimal('0')
        for step in ('DWP', 'SWP', 'WPC', 'PALM KERNEL OIL', 'WHEAT FLOUR'):
            assert _lines_by_step(result, step) == []


class TestAutoPlanFloorAndThreshold(TestCase):
    """``floor_qty`` / ``min_plan_qty`` — the Auto-Plan-specific options."""

    def test_floor_qty_reduces_quantity_at_a_fixed_rate(self):
        # 1000 balance / 3.00 rate = 333.33 -> floored to 333, CIF re-derived.
        items = [E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('1000'))]
        result = plan_e5_items(items, Decimal('1000'), floor_qty=True)
        df = _lines_by_step(result, 'DIETARY FIBRE')[0]
        assert df.planned_qty == Decimal('333')
        assert df.planned_cif == Decimal('999.0000')
        assert df.unit_price == Decimal('3.0000')   # rate itself never drops
        assert result.remaining_cif == Decimal('1')

    def test_below_min_plan_qty_is_skipped_entirely(self):
        items = [E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('49'))]
        result = plan_e5_items(items, Decimal('1000'), min_plan_qty=Decimal('50'), floor_qty=True)
        assert result.lines == []
        assert result.remaining_cif == Decimal('1000')

    def test_at_min_plan_qty_is_included(self):
        items = [E5Item(key='d', category='DIETARY FIBRE', qty=Decimal('50'))]
        result = plan_e5_items(items, Decimal('1000'), min_plan_qty=Decimal('50'), floor_qty=True)
        assert len(result.lines) == 1

    def test_wheat_flour_mopup_rate_uses_only_qualifying_items(self):
        items = [
            E5Item(key='small', category='WHEAT FLOUR', qty=Decimal('10')),   # below threshold
            E5Item(key='big', category='WHEAT FLOUR', qty=Decimal('100')),
        ]
        result = plan_e5_items(items, Decimal('1000'), min_plan_qty=Decimal('50'), floor_qty=True)
        wf_lines = _lines_by_step(result, 'WHEAT FLOUR')
        assert len(wf_lines) == 1
        assert wf_lines[0].key == 'big'
        assert wf_lines[0].unit_price == Decimal('10.0000')  # 1000 / 100, not / 110
