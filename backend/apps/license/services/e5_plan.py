"""
E5 (biscuits) utilization-planning waterfall.

Processing order (each rule draws down the same running balance):

    Rule 1  DIETARY FIBRE          @ 3.00
    ── Special Validation ── (immediately after Rule 1) ──────────────────
        milk_total = Milk Products (0404) + Egg Albumin/WPC (3502) util qty.
        If remaining < milk_total × 1.50: plan the ENTIRE milk quantity as
        SWP-E5 @ 1.50 right here, then run Rule 2, and SKIP Rule 3 below.
    Rule 2  EDIBLE OILS WATERFALL
        Case 2.1  PALM KERNEL OIL   @ 1.80  (HSN 1513 / desc "Vegetable Oil")
        Case 2.2  RBD PALMOLEIN     @ 1.20  (HSN 15119020 / "RBD")
        Case 2.3  REMAINING OILS    @ 5.00  (all other edible oils)
    Rule 3  MILK & MILK PRODUCTS  (only when Special Validation did NOT fire)
        Delegated to the shared milk-planning engine
        (``services/milk_planner.py``, configured via ``MILK_CONFIG_E5``):
          * 0404 only  → DWP-E5 @ 5.00, then SWP-E5 @ 1.50 (full qty, not split)
          * 3502 only  → WPC-E5, full qty @ 25.00
          * both       → average-price banded split across SWP/DWP/WPC(@20)
    Final   WHEAT FLOUR mop-up     dynamic  (legacy step, preserved — absorbs
                                              any balance left after Rule 3)

All calculations use Decimal. Every step's utilization is capped at the
remaining balance — if a step would exceed it, only the portion that fits
is allocated (dynamic rate = balance / util_qty), and later steps see zero.
"""
from __future__ import annotations

from decimal import Decimal

from apps.license.services.milk_planner import MILK_CONFIG_E5, plan_milk
from apps.license.services.planning_allocation import (
    allocate_step,
    d as _d,
    quantize_money as _quantize_money,
)


# Classification buckets, in the new spec's priority order (Wheat Flour is a
# preserved legacy bucket, not part of the new spec, appended at the end —
# real licences still carry wheat-flour import items that must stay planned).
E5_CATS: tuple[str, ...] = (
    'DIETARY FIBRE',
    'MILK PRODUCTS',
    'EGG ALBUMIN / WPC',
    'PALM KERNEL OIL',
    'RBD PALMOLEIN',
    'REMAINING OILS',
    'WHEAT FLOUR',
)
E5_PLAN_CATS: tuple[str, ...] = E5_CATS

# Fixed unit prices for the plain fixed-rate steps. Milk Products / Egg
# Albumin-WPC prices live in MILK_CONFIG_E5 (shared with the Auto-Plan /
# E1 engines); Wheat Flour is a dynamic mop-up so it has no fixed price.
E5_UNIT_PRICES: dict[str, Decimal] = {
    'DIETARY FIBRE':    Decimal('3.00'),
    'PALM KERNEL OIL':  Decimal('1.80'),
    'RBD PALMOLEIN':    Decimal('1.20'),
    'REMAINING OILS':   Decimal('5.00'),
}

# Hard-coded reference balance used in the original spec for hand-calculations
# and unit tests. Production callers pass the per-licence balance in instead.
BALANCE_CIF_USD: Decimal = Decimal('69046.90')


def _norm(value) -> str:
    """Lower-case + strip for case-insensitive substring matching."""
    return (value or '').strip().lower()


def classify_e5_item(
    item_key: str | None,
    hs_code: str | None,
    description: str | None,
) -> str | None:
    """Return the E5 planner bucket for an item, or None if no rule matches.

    Precedence (high → low):

      1. 'dietary fibre' (item OR description)              → DIETARY FIBRE
         NOTE: a bare 'walnut' substring is NOT enough — the row must be
         explicitly tagged Dietary Fibre.
      2. 'wheat flour' item name (legacy, unambiguous — beats any HSN
         signal, same as the pre-existing behaviour)          → WHEAT FLOUR
      3. HSN contains '0404'                                  → MILK PRODUCTS
      4. HSN contains '3502'                                  → EGG ALBUMIN / WPC
      5. 'olive oil' item name (legacy, unambiguous — beats
         HSN 1513/1511 signals, same as the pre-existing
         behaviour)                                           → REMAINING OILS
      6. HSN contains '1513' / desc contains 'vegetable oil' /
         item 'pko'                                            → PALM KERNEL OIL
      7. HSN contains '1511' / item 'rbd'                      → RBD PALMOLEIN
      8. HSN chapter 15 (fats & oils) / desc contains
         'edible oil'                                          → REMAINING OILS
      9. Wheat-flour legacy HSN '11010000'                     → WHEAT FLOUR
    """
    item = _norm(item_key)
    hs = _norm(hs_code)
    desc = _norm(description)
    hs_digits = hs.replace(' ', '').replace('-', '')

    if 'dietary fibre' in item or 'dietary fibre' in desc:
        return 'DIETARY FIBRE'
    if 'wheat flour' in item:
        return 'WHEAT FLOUR'
    if '0404' in hs:
        return 'MILK PRODUCTS'
    if '3502' in hs:
        return 'EGG ALBUMIN / WPC'
    if 'olive oil' in item:
        return 'REMAINING OILS'

    if '1513' in hs or 'vegetable oil' in desc or 'pko' in item:
        return 'PALM KERNEL OIL'
    if '1511' in hs or 'rbd' in item:
        return 'RBD PALMOLEIN'
    if hs_digits.startswith('15') or 'edible oil' in desc:
        return 'REMAINING OILS'

    if '11010000' in hs:
        return 'WHEAT FLOUR'

    return None


def classify_e5_hsn(hs_code: str | None) -> str | None:
    """Backwards-compatible HSN-only classifier — kept so callers that only
    know an HSN can still bucket common cases. Item-name-only rules (Dietary
    Fibre by name, Wheat Flour by name, Olive Oil by name, PKO/RBD acronyms)
    never fire from an HSN-only call."""
    return classify_e5_item(None, hs_code, None)


def is_wheat_flour(hs_code: str | None) -> bool:
    """Kept for backward compatibility — legacy callers ask this directly."""
    return '11010000' in _norm(hs_code)


def compute_e5_plan(
    e5_totals: dict[str, float],
    wf_qty=None,
    license_balance=None,
    pool_10pct=None,       # noqa: ARG001 — legacy signature, unused
) -> tuple[dict[str, float], dict[str, float]]:
    """Run the E5 waterfall and return ``(planned_per_cat, rate_per_cat)``.

    ``e5_totals`` maps each category in :data:`E5_CATS` to its aggregated
    utilization quantity (E5 has no exclusion rules, so display == util).
    Missing keys default to zero. ``license_balance`` is the starting
    balance the waterfall draws down from — when omitted the spec's
    reference balance :data:`BALANCE_CIF_USD` is used.

    ``wf_qty`` is a legacy override for the WHEAT FLOUR quantity (kept for
    old call sites that passed it separately); it wins over any
    ``e5_totals['WHEAT FLOUR']`` value. ``pool_10pct`` is unused (legacy
    signature compatibility).

    Returns planned/rate keyed by every entry in E5_CATS (for per-item
    proration by classification bucket) plus the individual DWP / SWP
    milk sub-step breakdown. MILK PRODUCTS' / EGG ALBUMIN's planned CIF are
    each the milk engine's total, attributed back proportionally by
    utilization-quantity share (the two buckets are indistinguishable once
    a mixed 0404+3502 group has been average-price-banded together).
    """
    remaining = _d(license_balance) if license_balance is not None else BALANCE_CIF_USD

    qty = {cat: _d(e5_totals.get(cat)) for cat in E5_CATS}
    if wf_qty is not None:
        qty['WHEAT FLOUR'] = _d(wf_qty)

    result_keys = list(E5_CATS) + ['DWP', 'SWP']
    planned: dict[str, Decimal] = {k: Decimal('0') for k in result_keys}
    rate: dict[str, Decimal] = {k: Decimal('0') for k in result_keys}
    for cat, price in E5_UNIT_PRICES.items():
        rate[cat] = price
    rate['DWP'] = MILK_CONFIG_E5.dwp_price
    rate['SWP'] = MILK_CONFIG_E5.swp_price
    rate['EGG ALBUMIN / WPC'] = MILK_CONFIG_E5.wpc_price

    # Rule 1 — Dietary Fibre.
    used, r = allocate_step(qty['DIETARY FIBRE'], E5_UNIT_PRICES['DIETARY FIBRE'], remaining)
    planned['DIETARY FIBRE'] = used
    rate['DIETARY FIBRE'] = r
    remaining -= used

    def _run_oils() -> None:
        nonlocal remaining
        for cat in ('PALM KERNEL OIL', 'RBD PALMOLEIN', 'REMAINING OILS'):
            used_, r_ = allocate_step(qty[cat], E5_UNIT_PRICES[cat], remaining)
            planned[cat] = used_
            rate[cat] = r_
            remaining -= used_

    def _attribute_milk(total_cif: Decimal, qty_0404: Decimal, qty_3502: Decimal) -> None:
        milk_total = qty_0404 + qty_3502
        if milk_total > 0:
            planned['MILK PRODUCTS'] = total_cif * (qty_0404 / milk_total)
            planned['EGG ALBUMIN / WPC'] = total_cif * (qty_3502 / milk_total)

    # Special Validation — immediately after Rule 1.
    qty_0404 = qty['MILK PRODUCTS']
    qty_3502 = qty['EGG ALBUMIN / WPC']
    milk_total = qty_0404 + qty_3502
    special_triggered = (
        milk_total > 0
        and remaining > 0
        and remaining < milk_total * MILK_CONFIG_E5.swp_price
    )

    if special_triggered:
        used, r = allocate_step(milk_total, MILK_CONFIG_E5.swp_price, remaining)
        planned['SWP'] = used
        rate['SWP'] = r
        remaining -= used
        _attribute_milk(used, qty_0404, qty_3502)
        if qty_0404 > 0:
            rate['MILK PRODUCTS'] = r
        if qty_3502 > 0:
            rate['EGG ALBUMIN / WPC'] = r
        _run_oils()
        # Rule 3 (normal milk optimisation) is skipped — already planned above.
    else:
        _run_oils()
        milk_planned, milk_rate, remaining = plan_milk(qty_0404, qty_3502, remaining, MILK_CONFIG_E5)
        planned['DWP'] = milk_planned['DWP']
        rate['DWP'] = milk_rate['DWP']
        planned['SWP'] = milk_planned['SWP']
        rate['SWP'] = milk_rate['SWP']
        rate['EGG ALBUMIN / WPC'] = milk_rate['WPC']
        total_milk_cif = milk_planned['DWP'] + milk_planned['SWP'] + milk_planned['WPC']
        _attribute_milk(total_milk_cif, qty_0404, qty_3502)
        if qty_0404 > 0:
            rate['MILK PRODUCTS'] = rate['DWP'] + rate['SWP']

    # Final — Wheat Flour mop-up (legacy step, preserved unchanged): absorbs
    # any balance left after Rule 3, at a dynamic rate = balance / qty.
    if remaining > 0 and qty['WHEAT FLOUR'] > 0:
        planned['WHEAT FLOUR'] = remaining
        rate['WHEAT FLOUR'] = remaining / qty['WHEAT FLOUR']
        remaining = Decimal('0')

    planned_f = {k: _quantize_money(v) for k, v in planned.items()}
    rate_f = {k: _quantize_money(v) for k, v in rate.items()}
    return planned_f, rate_f
