"""Current planning freeze gates: no retired per-norm dispatcher is required."""
from decimal import Decimal

from apps.license.services.sion_planning_execution import normalize_plan_mode, select_unit_value_row
from apps.license.tests.planning_contract_support import rule


def test_planning_modes_are_explicit_and_reject_unknown_values():
    assert normalize_plan_mode(None) == "NEW"
    assert normalize_plan_mode("all") == "ALL"
    try:
        normalize_plan_mode("unsafe")
    except ValueError as error:
        assert "Expected NEW or ALL" in str(error)
    else:
        raise AssertionError("unknown planning mode must be rejected")


def test_touching_price_bands_have_one_deterministic_owner():
    lower = rule(key="a", output="A", price="1")
    upper = rule(key="b", output="B", price="2")
    lower.min_unit_price, lower.max_unit_price = Decimal("0"), Decimal("5")
    upper.min_unit_price, upper.max_unit_price = Decimal("5"), Decimal("10")
    assert select_unit_value_row([upper, lower], Decimal("5")) is lower
