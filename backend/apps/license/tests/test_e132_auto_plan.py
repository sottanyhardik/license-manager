"""E132 generic execution contracts (60/40 target rules are database data)."""
from decimal import Decimal

from apps.license.services.sion_product_classifier import CanonicalInput, SionProductClassifier
from apps.license.tests.planning_contract_support import compute, rule


def test_e132_aliases_resolve_before_persisted_target_mapping():
    assert SionProductClassifier.resolve_canonical_input("palm kernel oil") is CanonicalInput.PKO
    assert SionProductClassifier.resolve_canonical_input("cheese") is CanonicalInput.CHEESE


def test_e132_generic_rules_keep_other_valid_rows_after_shortage(monkeypatch):
    result = compute(monkeypatch, rules=[
        rule(key="pko", output="PKO", price="2", priority=1),
        rule(key="cheese", output="CHEESE", price="3", priority=2),
    ], records=[
        {"record_id": "p", "item_key": "pko", "quantity": 40, "available_quantity": 40},
        {"record_id": "c", "item_key": "cheese", "quantity": 40, "available_quantity": 40},
    ], balance_cif="100")
    assert [(line.output_key, line.quantity) for line in result.rows] == [
        ("PKO", Decimal("40")), ("CHEESE", Decimal("20") / Decimal("3")),
    ]
    assert result.remaining_cif == Decimal("0")
