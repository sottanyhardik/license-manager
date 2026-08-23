"""Current generic-planner regression contracts replacing retired E1 adapter tests."""
from decimal import Decimal

from apps.license.tests.planning_contract_support import compute, rule


def test_generic_rule_classifies_hsn_shaped_source_and_uses_persisted_price(monkeypatch):
    result = compute(monkeypatch, rules=[rule(key="almond", output="ALMOND", price="4.25")], records=[{
        "record_id": "source-1", "item_key": "almond", "hs_code": "080211",
        "description": "Almond", "quantity": Decimal("12"), "available_quantity": Decimal("12"),
    }], balance_cif="100")

    assert [(line.quantity, line.value, line.output_key) for line in result.rows] == [
        (Decimal("12"), Decimal("51.00"), "ALMOND"),
    ]
    assert result.remaining_cif == Decimal("49.00")


def test_generic_waterfall_obeys_persisted_priority(monkeypatch):
    result = compute(monkeypatch, rules=[
        rule(key="first", output="FIRST", price="5", priority=1),
        rule(key="second", output="SECOND", price="5", priority=2),
    ], records=[
        {"record_id": "second", "item_key": "second", "quantity": 10, "available_quantity": 10},
        {"record_id": "first", "item_key": "first", "quantity": 10, "available_quantity": 10},
    ], balance_cif="60")

    assert [(line.output_key, line.quantity) for line in result.rows] == [
        ("FIRST", Decimal("10")), ("SECOND", Decimal("2")),
    ]
    assert result.remaining_cif == Decimal("0")
