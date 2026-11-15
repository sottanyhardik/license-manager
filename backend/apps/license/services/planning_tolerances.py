"""Operational planner tolerances.

These helpers affect planner completion/status only.  They deliberately do
not mutate model balances or participate in theoretical plan generation.
"""
from decimal import Decimal


PLANNING_AVAILABLE_QTY_TOLERANCE = Decimal("200.000")
PLANNING_BALANCE_CIF_TOLERANCE = Decimal("500.00")
PLANNING_REMAINING_QTY_TOLERANCE = Decimal("100.000")


def _decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def effective_planning_available_quantity(value) -> Decimal:
    """Return zero for a non-negative quantity residual strictly below 200."""
    value = _decimal(value)
    if Decimal("0") <= value < PLANNING_AVAILABLE_QTY_TOLERANCE:
        return Decimal("0.000")
    return value


def effective_planning_balance_cif(value) -> Decimal:
    """Return zero for a non-negative CIF residual strictly below 500."""
    value = _decimal(value)
    if Decimal("0") <= value < PLANNING_BALANCE_CIF_TOLERANCE:
        return Decimal("0.00")
    return value


def plannable_capacity_cif(value) -> Decimal:
    """Planning BUDGET/CAPACITY derived from the signed financial balance.

    OD-01 (owner, 2026-11-15): `calculate_financial_balance` /
    `get_balance_cif` are SIGNED - a negative value is real over-utilisation
    and is displayed as such. Capacity for NEW planning/allocation cannot be
    negative, so planners use this instead of the raw balance: negative -> 0,
    any other value returned unchanged (no tolerance applied here - callers
    that use the sub-500 tolerance compose it with
    `effective_planning_balance_cif` themselves). Before OD-01 the engine
    itself floored at 0, so planning inputs are exactly unchanged by this.
    Use ONLY for budgets/ceilings, never for display.
    """
    value = _decimal(value)
    return value if value > Decimal("0") else Decimal("0.00")


def apply_remaining_plan_tolerance(quantity, cif) -> tuple[Decimal, Decimal]:
    """Ignore a strictly-positive final plan residual below 100 quantity.

    Negative values are genuine excess signals and the exact 100 boundary is
    intentionally retained. The raw/model values are never mutated.
    """
    quantity = _decimal(quantity)
    cif = _decimal(cif)
    if Decimal("0") < quantity < PLANNING_REMAINING_QTY_TOLERANCE:
        return Decimal("0.000"), Decimal("0.00")
    return quantity, cif
