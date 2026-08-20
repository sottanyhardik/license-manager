"""Current auto-plan contracts for the generic SION execution boundary."""
from decimal import Decimal

from apps.license.tests.planning_contract_support import compute, rule


def test_auto_plan_caps_quantity_and_cif_together(monkeypatch):
    result = compute(monkeypatch, rules=[rule(key="source", output="E1 INPUT", price="6.5")], records=[{
        "record_id": "source", "item_key": "source", "quantity": 100,
        "available_quantity": 100,
    }], balance_cif="53")
    assert [(row.quantity, row.value) for row in result.rows] == [
        (Decimal("53") / Decimal("6.5"), Decimal("53")),
    ]
    assert result.remaining_cif == Decimal("0")


def test_auto_plan_zero_balance_never_creates_positive_cif(monkeypatch):
    result = compute(monkeypatch, rules=[rule(key="source", output="E1 INPUT", price="6.5")], records=[{
        "record_id": "source", "item_key": "source", "quantity": 100, "available_quantity": 100,
    }], balance_cif="0", force_plan=True)
    assert result.rows == []
    assert result.remaining_cif == Decimal("0")
