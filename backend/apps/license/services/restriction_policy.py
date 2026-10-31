"""Canonical policy helpers for DFIA licence item restrictions.

This module owns the supported rule-editor percentage values and the shared
Decimal arithmetic used by serializers, condition pools and planning.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

SUPPORTED_CIF_RESTRICTION_PERCENTAGES = (
    Decimal("2"), Decimal("3"), Decimal("5"), Decimal("10"),
)
RESTRICTION_PERCENTAGE_LABELS = ("2%", "3%", "5%", "10%")
AU_CONDITION = "AU"
DECIMAL_ZERO = Decimal("0")
QUANTITY_QUANTUM = Decimal("0.001")


def validate_cif_restriction_percentage(value):
    """Normalize a rule-editor restriction to Decimal or None.

    Blank/zero mean no rule-level override. Only the supported percentage
    options are accepted for newly configured planning rules.
    """
    if value is None or value == "":
        return None
    parsed = Decimal(str(value))
    if parsed == DECIMAL_ZERO:
        return None
    if parsed not in SUPPORTED_CIF_RESTRICTION_PERCENTAGES:
        allowed = ", ".join(str(item) for item in SUPPORTED_CIF_RESTRICTION_PERCENTAGES)
        raise ValueError(f"Restriction percentage must be one of {allowed}, or blank.")
    return parsed


def parse_condition_percentage(condition_type):
    """Parse a legacy/import condition such as '2%' into Decimal.

    Non-percentage conditions (including AU and blank) return None. Malformed
    or out-of-range percentage labels raise ValueError so callers can fail
    closed rather than accidentally treating a bad restriction as unrestricted.
    """
    text = str(condition_type or "").strip().upper()
    if not text.endswith("%"):
        return None
    try:
        value = Decimal(text[:-1].strip())
    except Exception as exc:
        raise ValueError(f"Invalid percentage condition: {condition_type!r}") from exc
    if not value.is_finite() or value <= DECIMAL_ZERO or value > Decimal("100"):
        raise ValueError(f"Percentage condition out of range: {condition_type!r}")
    return value


def restriction_cif_limit(total_cif, percentage):
    """Return the maximum CIF allowed by an item-level percentage restriction."""
    total = max(Decimal(str(total_cif or 0)), DECIMAL_ZERO)
    pct = Decimal(str(percentage))
    return total * pct / Decimal("100")


def cap_quantity_to_cif(quantity, unit_price, remaining_cif):
    """Cap a proposed quantity by remaining CIF, rounding quantity down to 3dp."""
    qty = max(Decimal(str(quantity or 0)), DECIMAL_ZERO)
    price = Decimal(str(unit_price or 0))
    if price <= DECIMAL_ZERO:
        return qty.quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
    budget = max(Decimal(str(remaining_cif or 0)), DECIMAL_ZERO)
    affordable = (budget / price).quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
    return min(qty, affordable).quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
