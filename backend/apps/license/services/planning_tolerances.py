"""Operational planner tolerances.

These helpers affect planner completion/status only.  They deliberately do
not mutate model balances or participate in theoretical plan generation.
"""
from decimal import Decimal


PLANNING_AVAILABLE_QTY_TOLERANCE = Decimal("200.000")
PLANNING_BALANCE_CIF_TOLERANCE = Decimal("500.00")


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
