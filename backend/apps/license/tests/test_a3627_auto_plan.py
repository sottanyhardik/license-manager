"""A3627 is executed by the same persisted generic planner as every SION."""
from decimal import Decimal

from apps.license.services.sion_planning_execution import solve_unit_value_mix
from apps.license.tests.planning_contract_support import compute, rule


def test_configured_price_band_selects_full_quantity_when_funded(monkeypatch):
    result = compute(monkeypatch, rules=[rule(key="rutile", output="RUTILE", price="3.5")], records=[{
        "record_id": "r", "item_key": "rutile", "quantity": 8, "available_quantity": 8,
    }], balance_cif="28")
    assert [(line.quantity, line.value) for line in result.rows] == [(Decimal("8"), Decimal("28"))]


def test_unit_value_mix_is_decimal_and_consumes_available_cif():
    low, high = (rule(key="low", output="LOW", price="2.5"), rule(key="high", output="HIGH", price="3.5"))
    rows = solve_unit_value_mix([low, high], Decimal("10"), Decimal("30"))
    quantities = {row.execution_output: quantity for row, quantity in rows}
    assert quantities == {"LOW": Decimal("5"), "HIGH": Decimal("5")}
