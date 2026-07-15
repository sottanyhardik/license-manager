# license/services/e1_plan.py
"""
E1 (confectionery) utilization-planning waterfall.

Ported verbatim from legacy/backend/apps/license/services/e1_plan.py.
No business-logic changes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Display order of the E1 categories. The Excel export iterates this tuple.
E1_CATS: tuple = (
    'OTHER CONFECTIONERY INGREDIENTS',
    'WPC',
    'FRUIT JUICE',
    'ALUMINIUM FOIL',
    'POLYPROPYLENE',
    'PAPER',
)
E1_PLAN_CATS: tuple = E1_CATS

# Maximum dynamic unit price per step.
E1_MAX_PRICES: dict = {
    'OTHER CONFECTIONERY INGREDIENTS': Decimal('2.7'),
    'WPC':                              Decimal('22'),
    'FRUIT JUICE':                      Decimal('3'),
    'ALUMINIUM FOIL':                   Decimal('4.5'),
    'POLYPROPYLENE':                    Decimal('0.9'),
    'PAPER':                            Decimal('0.6'),
}

# `condition_type` values that are EXCLUDED from the utilization quantity for
# each step. Display quantity always includes everything. Empty set means
# the step has no exclusions.
E1_EXCLUDED_CONDITIONS: dict = {
    'OTHER CONFECTIONERY INGREDIENTS': frozenset({'2%'}),
    'WPC':                              frozenset({'AU'}),
    'FRUIT JUICE':                      frozenset({'AU'}),
    'ALUMINIUM FOIL':                   frozenset(),
    'POLYPROPYLENE':                    frozenset(),
    'PAPER':                            frozenset(),
}


def _norm(value) -> str:
    return (value or '').strip().lower()


def _item_tokens(item_key) -> set:
    norm = _norm(item_key)
    if not norm:
        return set()
    return {t.strip() for t in norm.split(',') if t.strip()}


def classify_e1_item(item_key, hs_code, description):
    """Return the E1 planner category for an item, or None if no rule matches."""
    item = _norm(item_key)
    hs = _norm(hs_code)
    desc = _norm(description)
    tokens = _item_tokens(item_key)

    # 1. Item-name signals.
    if 'other confectionery ingredients' in item:
        return 'OTHER CONFECTIONERY INGREDIENTS'
    if 'wpc' in tokens or 'wpc' in item:
        return 'WPC'
    if 'fruit juice' in item:
        return 'FRUIT JUICE'

    # 2. HSN/desc signals.
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


def _d(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def _quantize_money(value: Decimal) -> float:
    return float(value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def _allocate_step(util_qty: Decimal, max_price: Decimal, balance: Decimal):
    """Allocate one waterfall step at a dynamic price."""
    if util_qty <= 0 or balance <= 0 or max_price <= 0:
        return Decimal('0'), max_price
    requested = util_qty * max_price
    if requested <= balance:
        return requested, max_price
    return balance, balance / util_qty


def compute_e1_plan(display_qty, util_qty, license_balance):
    """Run the E1 waterfall. Returns (planned_per_cat, rate_per_cat)."""
    remaining = _d(license_balance)
    planned = {c: Decimal('0') for c in E1_CATS}
    rate = {c: E1_MAX_PRICES[c] for c in E1_CATS}

    for cat in E1_CATS:
        uq = _d(util_qty.get(cat, 0))
        used, r = _allocate_step(uq, E1_MAX_PRICES[cat], remaining)
        planned[cat] = used
        rate[cat] = r
        remaining -= used

    planned_f = {k: _quantize_money(v) for k, v in planned.items()}
    rate_f = {k: _quantize_money(v) for k, v in rate.items()}
    return planned_f, rate_f


def split_display_util_qty(raw_rows):
    """Given {'category', 'qty', 'condition_type'} rows, return (display_qty, util_qty)."""
    display = {c: 0.0 for c in E1_CATS}
    util = {c: 0.0 for c in E1_CATS}
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
