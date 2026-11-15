"""OD-01 companion: the financial balance is SIGNED (negative = over-utilised),
but planning/allocation capacity must never go negative. `plannable_capacity_cif`
reproduces exactly what planners received before OD-01 (when the engine itself
floored at 0) and applies no tolerance of its own."""
from decimal import Decimal

import pytest

from apps.license.services.planning_tolerances import (
    effective_planning_balance_cif,
    plannable_capacity_cif,
)


@pytest.mark.parametrize(
    ("balance", "expected"),
    [
        (Decimal("-5000.00"), Decimal("0.00")),   # over-utilised -> no capacity
        (Decimal("-0.01"), Decimal("0.00")),
        (Decimal("0"), Decimal("0.00")),
        (Decimal("0.01"), Decimal("0.01")),       # no sub-500 tolerance here
        (Decimal("499.99"), Decimal("499.99")),
        (Decimal("12345.67"), Decimal("12345.67")),
        (None, Decimal("0.00")),
        ("250.50", Decimal("250.50")),
    ],
)
def test_plannable_capacity_is_non_negative_and_otherwise_unchanged(balance, expected):
    result = plannable_capacity_cif(balance)
    assert isinstance(result, Decimal)
    assert result == expected


def test_composition_with_tolerance_matches_pre_od01_planner_input():
    # sion_planning_execution composes both: tolerance first, then the clamp.
    assert plannable_capacity_cif(effective_planning_balance_cif(Decimal("-700"))) == Decimal("0.00")
    assert plannable_capacity_cif(effective_planning_balance_cif(Decimal("300"))) == Decimal("0.00")
    assert plannable_capacity_cif(effective_planning_balance_cif(Decimal("800"))) == Decimal("800")
    # The display helper still passes a negative through (excess signal).
    assert effective_planning_balance_cif(Decimal("-700")) == Decimal("-700")
