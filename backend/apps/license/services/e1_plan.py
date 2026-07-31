"""
E1 (confectionery) utilization-planning waterfall.

The E1 norm allocates the licence balance across seven classification
buckets, executed as eight sequential steps (Milk Products splits into two
sub-steps). Each step has:

  * A **Display Quantity** — sum of every matching item (used for reporting).
  * A **Utilization Quantity** — same sum but with certain License-Marked
    items excluded so they don't drive CIF utilization.
  * A **Max Unit Price** — the rate is dynamic in ``[0, max]``; the actual
    rate is the largest value in band that keeps utilization within the
    remaining balance.

Waterfall order (run sequentially against the same running balance):

    Step 1   OTHER CONFECTIONERY INGREDIENTS  @ 2.70  excl 2%
    Step 2A  DWP  (Milk Products, HSN 0404)   @ 5.00
    Step 2B  SWP  (Milk Products, HSN 0404)   @ 1.50
    Step 3   EGG ALBUMIN / WPC (HSN 3502)     @ 25.00
    Step 4   FRUIT JUICE                      @ 0-3   excl AU
    Step 5   ALUMINIUM FOIL                   @ 0-4.5 (HSN/desc contains 7607)
    Step 6   POLYPROPYLENE                    @ 0-0.9 (3902 AND NOT 7607)
    Step 7   PAPER                            @ 0-0.6 (4801/4810/4802 AND NOT 7607/3902/3901)

Steps 2A/2B are delegated to the shared milk-planning engine
(``services/milk_planner.py``, configured via ``MILK_CONFIG_E1``) so E1 and
E5 never carry two independent implementations of the same DWP/SWP/WPC
dynamic-pricing rules. DWP and SWP both draw on the *same* Milk Products
utilization quantity — it is not split between them.

Each step's utilization is capped at the remaining balance — if the
requested ``util_qty × max_price`` would exceed the balance, the rate drops
to ``balance / util_qty`` so the step consumes exactly the balance and
later steps see zero.
"""
from __future__ import annotations

from decimal import Decimal

from apps.license.services.milk_planner import MILK_CONFIG_E1, plan_milk
from apps.license.services.planning_allocation import (
    allocate_step,
    d as _d,
    quantize_money as _quantize_money,
)


# Classification buckets. Every import item is classified into at most one
# of these; `display_qty` / `util_qty` dicts (built by callers) and the
# planned/rate dicts returned by `compute_e1_plan` are always keyed by every
# entry here, so callers can look up an item's bucket directly.
E1_CATS: tuple[str, ...] = (
    'OTHER CONFECTIONERY INGREDIENTS',
    'MILK PRODUCTS',
    'EGG ALBUMIN / WPC',
    'FRUIT JUICE',
    'ALUMINIUM FOIL',
    'POLYPROPYLENE',
    'PAPER',
)
E1_PLAN_CATS: tuple[str, ...] = E1_CATS

# Sequential waterfall steps: (step_key, source_bucket, max_unit_price).
# `source_bucket` is the E1_CATS entry the step draws its utilization
# quantity from. MILK PRODUCTS expands into two steps (DWP, SWP) that both
# read the *same* bucket's quantity rather than splitting it — their prices
# come from MILK_CONFIG_E1, the single source of truth shared with E5.
E1_WATERFALL_STEPS: tuple[tuple[str, str, Decimal], ...] = (
    ('OTHER CONFECTIONERY INGREDIENTS', 'OTHER CONFECTIONERY INGREDIENTS', Decimal('2.7')),
    ('DWP',                             'MILK PRODUCTS',                   MILK_CONFIG_E1.dwp_price),
    ('SWP',                             'MILK PRODUCTS',                   MILK_CONFIG_E1.swp_price),
    ('EGG ALBUMIN / WPC',               'EGG ALBUMIN / WPC',               MILK_CONFIG_E1.wpc_price),
    ('FRUIT JUICE',                     'FRUIT JUICE',                     Decimal('3')),
    ('ALUMINIUM FOIL',                  'ALUMINIUM FOIL',                  Decimal('4.5')),
    ('POLYPROPYLENE',                   'POLYPROPYLENE',                  Decimal('0.9')),
    ('PAPER',                           'PAPER',                           Decimal('0.6')),
)

# Maximum dynamic unit price, keyed by waterfall step (not bucket — DWP/SWP
# share the MILK PRODUCTS bucket but have distinct ceilings).
E1_MAX_PRICES: dict[str, Decimal] = {step: price for step, _src, price in E1_WATERFALL_STEPS}

# `condition_type` values EXCLUDED from the utilization quantity for each
# classification bucket. Display quantity always includes everything. Empty
# set means the bucket has no exclusions.
E1_EXCLUDED_CONDITIONS: dict[str, frozenset[str]] = {
    'OTHER CONFECTIONERY INGREDIENTS': frozenset({'2%'}),
    'MILK PRODUCTS':                   frozenset(),
    'EGG ALBUMIN / WPC':               frozenset(),
    'FRUIT JUICE':                     frozenset({'AU'}),
    'ALUMINIUM FOIL':                  frozenset(),
    'POLYPROPYLENE':                   frozenset(),
    'PAPER':                           frozenset(),
}


def _norm(value) -> str:
    return (value or '').strip().lower()


def classify_e1_item(
    item_key: str | None,
    hs_code: str | None,
    description: str | None,
) -> str | None:
    """Return the E1 planner bucket for an item, or None if no rule matches.

    Precedence (high → low):

      1. Item Name contains 'other confectionery ingredients' → OTHER CONFECTIONERY INGREDIENTS
      2. HSN contains '0404'                                  → MILK PRODUCTS
      3. HSN contains '3502'                                  → EGG ALBUMIN / WPC
      4. Item Name contains 'fruit juice'                     → FRUIT JUICE
      5. HSN or Description contains '7607'                                 → ALUMINIUM FOIL
      6. HSN or Description contains '3902' AND not '7607'                  → POLYPROPYLENE
      7. HSN or Description contains '4801'/'4802'/'4810' AND
         not '7607'/'3902'/'3901'                                           → PAPER
    """
    item = _norm(item_key)
    hs = _norm(hs_code)
    desc = _norm(description)

    if 'other confectionery ingredients' in item:
        return 'OTHER CONFECTIONERY INGREDIENTS'
    if '0404' in hs:
        return 'MILK PRODUCTS'
    if '3502' in hs:
        return 'EGG ALBUMIN / WPC'
    if 'fruit juice' in item:
        return 'FRUIT JUICE'

    has_7607 = '7607' in hs or '7607' in desc
    has_3902 = '3902' in hs or '3902' in desc
    has_3901 = '3901' in hs or '3901' in desc
    has_paper = any(k in hs or k in desc for k in ('4801', '4810', '4802'))

    if has_7607:
        return 'ALUMINIUM FOIL'
    if has_3902 and not has_7607:
        return 'POLYPROPYLENE'
    if has_paper and not (has_7607 or has_3902 or has_3901):
        return 'PAPER'

    return None


def compute_e1_plan(
    display_qty: dict[str, float],
    util_qty: dict[str, float],
    license_balance,
) -> tuple[dict[str, float], dict[str, float]]:
    """Run the E1 waterfall.

    Args:
        display_qty: per-bucket sum of every matching item (incl. marked).
            Reporting only — not consumed here, kept for signature parity
            with callers that build both dicts together.
        util_qty:    per-bucket sum after removing excluded markings. The
            MILK PRODUCTS entry is read by *both* the DWP and SWP steps
            (same quantity, not split between them).
        license_balance: starting balance the waterfall draws down from.

    Returns:
        (planned_per_key, rate_per_key) keyed by every entry in E1_CATS
        (for per-item proration by classification bucket) plus the
        individual DWP / SWP step breakdown. MILK PRODUCTS' planned/rate is
        the DWP+SWP aggregate (sum of both steps' planned CIF / rates).
        Rates fall back to the step's max price for empty / zero steps.
    """
    remaining = _d(license_balance)
    result_keys = [step for step, _src, _price in E1_WATERFALL_STEPS] + ['MILK PRODUCTS']
    planned: dict[str, Decimal] = {k: Decimal('0') for k in result_keys}
    rate: dict[str, Decimal] = {k: Decimal('0') for k in result_keys}

    # Step 1.
    uq = _d(util_qty.get('OTHER CONFECTIONERY INGREDIENTS', 0))
    used, r = allocate_step(uq, E1_MAX_PRICES['OTHER CONFECTIONERY INGREDIENTS'], remaining)
    planned['OTHER CONFECTIONERY INGREDIENTS'] = used
    rate['OTHER CONFECTIONERY INGREDIENTS'] = r
    remaining -= used

    # Steps 2A/2B/3 — shared milk-planning engine (DWP → SWP over the Milk
    # Products bucket, then WPC over the Egg Albumin / WPC bucket).
    qty_0404 = _d(util_qty.get('MILK PRODUCTS', 0))
    qty_3502 = _d(util_qty.get('EGG ALBUMIN / WPC', 0))
    milk_planned, milk_rate, remaining = plan_milk(qty_0404, qty_3502, remaining, MILK_CONFIG_E1)
    planned['DWP'] = milk_planned['DWP']
    rate['DWP'] = milk_rate['DWP']
    planned['SWP'] = milk_planned['SWP']
    rate['SWP'] = milk_rate['SWP']
    planned['EGG ALBUMIN / WPC'] = milk_planned['WPC']
    rate['EGG ALBUMIN / WPC'] = milk_rate['WPC']
    planned['MILK PRODUCTS'] = planned['DWP'] + planned['SWP']
    rate['MILK PRODUCTS'] = rate['DWP'] + rate['SWP']

    # Steps 4-7 — unchanged fixed-bucket dynamic pricing.
    for cat in ('FRUIT JUICE', 'ALUMINIUM FOIL', 'POLYPROPYLENE', 'PAPER'):
        uq = _d(util_qty.get(cat, 0))
        used, r = allocate_step(uq, E1_MAX_PRICES[cat], remaining)
        planned[cat] = used
        rate[cat] = r
        remaining -= used

    planned_f = {k: _quantize_money(v) for k, v in planned.items()}
    rate_f = {k: _quantize_money(v) for k, v in rate.items()}
    return planned_f, rate_f


def split_display_util_qty(
    raw_rows: list[dict],
) -> tuple[dict[str, float], dict[str, float]]:
    """Helper: given a list of {'category', 'qty', 'condition_type'} rows,
    aggregate into (display_qty, util_qty) per bucket honouring the
    per-bucket exclusions in :data:`E1_EXCLUDED_CONDITIONS`.

    Unknown categories are silently ignored (the caller should have
    classified them beforehand).
    """
    display: dict[str, float] = {c: 0.0 for c in E1_CATS}
    util: dict[str, float] = {c: 0.0 for c in E1_CATS}
    for row in raw_rows:
        cat = row.get('category')
        if cat not in display:
            continue
        qty = float(row.get('qty') or 0)
        cond = (row.get('condition_type') or '').strip()
        display[cat] += qty
        if cond not in E1_EXCLUDED_CONDITIONS[cat]:
            util[cat] += qty
    return display, util
