"""Money helpers. Decimal only; ROUND_HALF_UP to paise (same semantics as trade.q2)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

ZERO = Decimal("0.00")
PAISE = Decimal("0.01")


def to_money(value: object) -> Decimal:
    """Convert to a 2dp Decimal. Floats are rejected to avoid binary rounding drift."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, float):
        raise TypeError("float money values are not accepted; pass str or Decimal")
    try:
        return Decimal(str(value)).quantize(PAISE, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc


def q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PAISE, rounding=ROUND_HALF_UP)


def allocate_pro_rata(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split ``total`` across ``weights`` so the parts sum exactly to ``total``.

    Largest-remainder method on paise; zero/negative weight sum -> ValueError.
    """
    total = q2(total)
    weight_sum = sum(weights, Decimal("0"))
    if weight_sum <= 0:
        raise ValueError("allocation weights must sum to a positive number")
    raw = [total * w / weight_sum for w in weights]
    floored = [r.quantize(PAISE, rounding="ROUND_DOWN") for r in raw]
    remainder = int(((total - sum(floored, ZERO)) / PAISE).to_integral_value())
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floored[i], reverse=True)
    for i in order[:remainder]:
        floored[i] += PAISE
    return floored
