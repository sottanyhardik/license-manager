# license/services/e5_plan.py
"""
E5 (biscuits) utilization-planning waterfall.

Ported verbatim from legacy/backend/apps/license/services/e5_plan.py.
No business-logic changes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Display order of the E5 categories.
E5_CATS: tuple = (
    'DIETARY FIBRE',
    'SWP',
    'PKO',
    'RBD',
    'OLIVE OIL',
    'WPC',
    'WHEAT FLOUR',
)
E5_PLAN_CATS: tuple = E5_CATS

# Fixed unit prices ($/unit) for rate-locked steps.
E5_UNIT_PRICES: dict = {
    'DIETARY FIBRE': Decimal('2.7'),
    'SWP':           Decimal('1.5'),
    'PKO':           Decimal('2.3'),
    'RBD':           Decimal('1.2'),
    'OLIVE OIL':     Decimal('5.5'),
}

WPC_MIN_PRICE: Decimal = Decimal('0')
WPC_MAX_PRICE: Decimal = Decimal('22')

BALANCE_CIF_USD: Decimal = Decimal('69046.90')


def _norm(value) -> str:
    return (value or '').strip().lower()


def _item_tokens(item_key) -> set:
    norm = _norm(item_key)
    if not norm:
        return set()
    return {t.strip() for t in norm.split(',') if t.strip()}


def classify_e5_item(item_key, hs_code, description):
    """Return the E5 planner category for an item, or None if no rule matches."""
    item = _norm(item_key)
    hs = _norm(hs_code)
    desc = _norm(description)
    tokens = _item_tokens(item_key)

    # 1. Unambiguous full-name item signals.
    if 'dietary fibre' in item or 'dietary fibre' in desc:
        return 'DIETARY FIBRE'
    if 'olive oil' in item:
        return 'OLIVE OIL'
    if 'wheat flour' in item:
        return 'WHEAT FLOUR'

    # 2. WPC compound rule.
    if ('wpc' in tokens or 'wpc' in item) and ('3502' in hs or '3502' in desc):
        return 'WPC'

    # 3. SWP / PKO / RBD — acronym OR HSN/desc.
    if 'swp' in tokens or 'swp' in item or '0404' in hs or '0404' in desc:
        return 'SWP'
    if 'pko' in tokens or 'pko' in item or '1513' in hs or '1513' in desc:
        return 'PKO'
    if 'rbd' in tokens or 'rbd' in item or '1511' in hs or '1511' in desc:
        return 'RBD'

    # 4. Wheat-flour legacy HSN.
    if '11010000' in hs:
        return 'WHEAT FLOUR'

    return None


def classify_e5_hsn(hs_code) -> str | None:
    return classify_e5_item(None, hs_code, None)


def is_wheat_flour(hs_code) -> bool:
    return '11010000' in _norm(hs_code)


def _d(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def _allocate_fixed_rate(qty: Decimal, unit_price: Decimal, balance: Decimal) -> Decimal:
    if qty <= 0 or unit_price <= 0 or balance <= 0:
        return Decimal('0')
    requested = qty * unit_price
    return requested if requested <= balance else balance


def _allocate_wpc(qty: Decimal, balance: Decimal):
    if qty <= 0 or balance <= 0:
        return Decimal('0'), WPC_MIN_PRICE
    requested_at_max = qty * WPC_MAX_PRICE
    if balance >= requested_at_max:
        return requested_at_max, WPC_MAX_PRICE
    return balance, balance / qty


def _quantize_money(value: Decimal) -> float:
    return float(value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def compute_e5_plan(e5_totals, wf_qty=None, license_balance=None, pool_10pct=None):
    """Run the E5 waterfall. Returns (planned_per_cat, rate_per_cat)."""
    initial_balance = _d(license_balance) if license_balance is not None else BALANCE_CIF_USD
    remaining = initial_balance

    qty = {cat: _d(e5_totals.get(cat)) for cat in E5_CATS}
    if wf_qty is not None:
        qty['WHEAT FLOUR'] = _d(wf_qty)

    planned = {cat: Decimal('0') for cat in E5_CATS}
    rate = {cat: E5_UNIT_PRICES.get(cat, Decimal('0')) for cat in E5_CATS}
    rate['WPC'] = WPC_MIN_PRICE

    # Steps 1-5 — fixed-rate waterfall.
    for step in ('DIETARY FIBRE', 'SWP', 'PKO', 'RBD', 'OLIVE OIL'):
        used = _allocate_fixed_rate(qty[step], E5_UNIT_PRICES[step], remaining)
        planned[step] = used
        remaining -= used

    # Step 6 — SWP rate recalc.
    if remaining > 0 and qty['SWP'] > 0:
        planned['SWP'] += remaining
        rate['SWP'] = planned['SWP'] / qty['SWP']
        remaining = Decimal('0')

    # Step 7 — WPC dynamic rate.
    wpc_used, wpc_price = _allocate_wpc(qty['WPC'], remaining)
    planned['WPC'] = wpc_used
    rate['WPC'] = wpc_price
    remaining -= wpc_used

    # Step 8 — WHEAT FLOUR mop-up.
    if remaining > 0 and qty['WHEAT FLOUR'] > 0:
        planned['WHEAT FLOUR'] = remaining
        rate['WHEAT FLOUR'] = remaining / qty['WHEAT FLOUR']
        remaining = Decimal('0')

    planned_f = {k: _quantize_money(v) for k, v in planned.items()}
    rate_f = {k: _quantize_money(v) for k, v in rate.items()}
    return planned_f, rate_f
