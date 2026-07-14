"""
E1 (confectionery) utilization-planning waterfall.

The E1 norm allocates the licence balance across six input categories. Each
step has:

  * A **Display Quantity** — sum of every matching item (used for reporting).
  * A **Utilization Quantity** — same sum but with certain License-Marked
    items excluded so they don't drive CIF utilization.
  * A **Max Unit Price** — the rate is dynamic in ``[0, max]``; the actual
    rate is the largest value in band that keeps utilization within the
    remaining balance.

Waterfall order (run sequentially against the same running balance):

    Step 1  OTHER CONFECTIONERY INGREDIENTS  @ 2.7   excl 2%
    Step 2  WPC                              @ 0-22  excl AU
    Step 3  FRUIT JUICE                      @ 0-3   excl AU
    Step 4  ALUMINIUM FOIL                   @ 0-4.5 (HSN/desc contains 7607)
    Step 5  POLYPROPYLENE                    @ 0-0.9 (3902 AND NOT 7607)
    Step 6  PAPER                            @ 0-0.6 (4801/4810/4802 AND NOT 7607/3902/3901)

Each step's utilization is capped at the remaining balance — if the
requested ``util_qty × max_price`` would exceed the balance, the rate drops
to ``balance / util_qty`` so the step consumes exactly the balance and
later steps see zero.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


# Display order of the E1 categories. The Excel export iterates this tuple.
E1_CATS: tuple[str, ...] = (
    'OTHER CONFECTIONERY INGREDIENTS',
    'WPC',
    'FRUIT JUICE',
    'ALUMINIUM FOIL',
    'POLYPROPYLENE',
    'PAPER',
)
E1_PLAN_CATS: tuple[str, ...] = E1_CATS

# Maximum dynamic unit price per step.
E1_MAX_PRICES: dict[str, Decimal] = {
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
E1_EXCLUDED_CONDITIONS: dict[str, frozenset[str]] = {
    'OTHER CONFECTIONERY INGREDIENTS': frozenset({'2%'}),
    'WPC':                              frozenset({'AU'}),
    'FRUIT JUICE':                      frozenset({'AU'}),
    'ALUMINIUM FOIL':                   frozenset(),
    'POLYPROPYLENE':                    frozenset(),
    'PAPER':                            frozenset(),
}


def _norm(value) -> str:
    return (value or '').strip().lower()


def _item_tokens(item_key: str | None) -> set[str]:
    norm = _norm(item_key)
    if not norm:
        return set()
    return {t.strip() for t in norm.split(',') if t.strip()}


def classify_e1_item(
    item_key: str | None,
    hs_code: str | None,
    description: str | None,
) -> str | None:
    """Return the E1 planner category for an item, or None if no rule matches.

    Precedence (high → low):

      1. Item-name signals:
         * 'other confectionery ingredients' → OTHER CONFECTIONERY INGREDIENTS
         * 'wpc'                             → WPC
         * 'fruit juice'                     → FRUIT JUICE
      2. HSN / description signals:
         * HSN|desc contains '7607'                                   → ALUMINIUM FOIL
         * HSN|desc contains '3902' AND not '7607'                    → POLYPROPYLENE
         * HSN|desc contains '4801'/'4810'/'4802' AND
           not '7607'/'3902'/'3901'                                   → PAPER
    """
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


def _allocate_step(util_qty: Decimal, max_price: Decimal, balance: Decimal) -> tuple[Decimal, Decimal]:
    """Allocate one waterfall step at a dynamic price in ``[0, max_price]``.

    Returns ``(utilization, unit_price)``:

      * if balance can cover ``util_qty × max_price`` → use max_price
      * else                                          → use ``balance / util_qty``
      * util_qty == 0 or balance == 0                 → utilization is 0
    """
    if util_qty <= 0 or balance <= 0 or max_price <= 0:
        return Decimal('0'), max_price
    requested = util_qty * max_price
    if requested <= balance:
        return requested, max_price
    # Cap at remaining balance; effective rate drops below max.
    return balance, balance / util_qty


def compute_e1_plan(
    display_qty: dict[str, float],
    util_qty: dict[str, float],
    license_balance,
) -> tuple[dict[str, float], dict[str, float]]:
    """Run the E1 waterfall.

    Args:
        display_qty: per-category sum of every matching item (incl. marked).
        util_qty:    per-category sum after removing excluded markings.
        license_balance: starting balance the waterfall draws down from.

    Returns:
        (planned_per_cat, rate_per_cat) keyed by every entry in E1_CATS.
        Rates fall back to the category's max price for empty / zero steps.
    """
    remaining = _d(license_balance)
    planned: dict[str, Decimal] = {c: Decimal('0') for c in E1_CATS}
    rate: dict[str, Decimal] = {c: E1_MAX_PRICES[c] for c in E1_CATS}

    for cat in E1_CATS:
        uq = _d(util_qty.get(cat, 0))
        used, r = _allocate_step(uq, E1_MAX_PRICES[cat], remaining)
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
    aggregate into (display_qty, util_qty) per category honouring the
    per-step exclusions in :data:`E1_EXCLUDED_CONDITIONS`.

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
