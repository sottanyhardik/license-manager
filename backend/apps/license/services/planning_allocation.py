"""
Shared dynamic-pricing primitive for the norm utilization planners
(``e1_plan.py``, ``e5_plan.py``, ``milk_planner.py``).

Keeping this in one place means every planner's "maximise utilization
without breaching the remaining balance" rule stays byte-for-byte
identical — no risk of the waterfalls drifting out of sync.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def d(value) -> Decimal:
    """Tolerant Decimal coercion — handles None / Decimal / str / float."""
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def quantize_money(value: Decimal) -> float:
    """4-dp quantization for display + comparison stability."""
    return float(value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def allocate_step(util_qty: Decimal, max_price: Decimal, balance: Decimal) -> tuple[Decimal, Decimal]:
    """Allocate one waterfall step at a dynamic price in ``[0, max_price]``.

    Returns ``(planned_cif, unit_price)``:

      * if balance can cover ``util_qty × max_price`` → use max_price
      * else                                          → use ``balance / util_qty``
      * util_qty == 0 or balance == 0                 → planned_cif is 0
    """
    if util_qty <= 0 or balance <= 0 or max_price <= 0:
        return Decimal('0'), max_price
    requested = util_qty * max_price
    if requested <= balance:
        return requested, max_price
    # Cap at remaining balance; effective rate drops below max.
    return balance, balance / util_qty
