"""E5 auto plan now uses the database-driven generic service."""
from decimal import Decimal

from apps.license.tests.planning_contract_support import compute, rule


def test_e5_current_available_quantity_is_the_only_quantity_eligible_for_planning(monkeypatch):
    result = compute(monkeypatch, rules=[rule(key="fibre", output="DIETARY FIBRE", price="4")], records=[{
        "record_id": "f", "item_key": "fibre", "quantity": 100, "available_quantity": 7,
    }], balance_cif="100")
    assert [(line.quantity, line.value) for line in result.rows] == [(Decimal("7"), Decimal("28"))]
    assert result.remaining_cif == Decimal("72")
