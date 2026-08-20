"""Core execution contracts for profile/rule based SION planning.

The retired assertions in this module compared E1/E5-specific planners to an
adapter.  Those planners are no longer production authorities: persisted rule
priority and the generic execution path are.  These tests retain the business
risks from the former bridge tests without making legacy implementation output
the specification.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.license.tests.planning_contract_support import compute, rule
from apps.license.services.sion_planning_execution import (
    PlannerConfigurationError,
    validate_declarative_rules,
)


def _normalized(result):
    """All business fields: no generated identifiers or timestamps exist here."""
    return [
        (row.record_id, row.category, row.output_key, row.quantity, row.unit_price, row.value)
        for row in result.rows
    ], result.remaining_cif


def test_unmatched_source_is_not_planned(monkeypatch):
    result = compute(monkeypatch, rules=[rule(key="known", output="KNOWN", price="1")], records=[{
        "record_id": "unknown", "item_key": "unknown", "quantity": 10, "available_quantity": 10,
    }], balance_cif="10")
    assert result.rows == []
    assert result.remaining_cif == Decimal("10")


def test_shortage_is_non_fatal_and_later_valid_rows_are_evaluated(monkeypatch):
    result = compute(monkeypatch, rules=[
        rule(key="expensive", output="EXPENSIVE", price="10", priority=1),
        rule(key="cheap", output="CHEAP", price="1", priority=2),
    ], records=[
        {"record_id": "e", "item_key": "expensive", "quantity": 5, "available_quantity": 5},
        {"record_id": "c", "item_key": "cheap", "quantity": 5, "available_quantity": 5},
    ], balance_cif="12")
    assert [(line.output_key, line.quantity) for line in result.rows] == [("EXPENSIVE", Decimal("1.2"))]
    assert result.remaining_cif == Decimal("0")


def test_first_saved_rule_match_is_the_only_owner_of_an_overlapping_source(monkeypatch):
    """A source matching two rules belongs to the earlier persisted rule.

    This is the current replacement for the old E1/E5 classifier comparison:
    saved priority defines ownership, so a later rule cannot create a duplicate
    target from the same physical input.
    """
    result = compute(monkeypatch, rules=[
        rule(key="milk", output="HIGH_PRIORITY", price="2", priority=1),
        rule(key="milk", output="LOW_PRIORITY", price="1", priority=2),
    ], records=[{
        "record_id": "milk-1", "item_key": "milk", "quantity": 10, "available_quantity": 10,
    }], balance_cif="100")

    # 10 eligible units x the priority-1 rule's CIF 2 = 20.  The second
    # matching rule is not an additional entitlement.
    assert [(line.output_key, line.quantity, line.value) for line in result.rows] == [
        ("HIGH_PRIORITY", Decimal("10"), Decimal("20")),
    ]
    assert result.remaining_cif == Decimal("80")


def test_scarce_cif_is_consumed_in_rule_priority_waterfall(monkeypatch):
    """Current canonical generic rule contract: priority, then source order."""
    result = compute(monkeypatch, rules=[
        rule(key="later", output="LATER", price="5", priority=20),
        rule(key="first", output="FIRST", price="5", priority=10),
    ], records=[
        {"record_id": "later-1", "item_key": "later", "quantity": 10, "available_quantity": 10},
        {"record_id": "first-1", "item_key": "first", "quantity": 10, "available_quantity": 10},
    ], balance_cif="60")

    # The priority-10 ask consumes 10 x 5 = 50 first; only 10 CIF remains,
    # independently yielding 10 / 5 = 2 units for priority 20.
    assert [(line.output_key, line.quantity, line.value) for line in result.rows] == [
        ("FIRST", Decimal("10"), Decimal("50")),
        ("LATER", Decimal("2"), Decimal("10")),
    ]
    assert result.remaining_cif == Decimal("0")


def test_synthetic_norm_identities_with_identical_declarative_rules_are_equivalent(monkeypatch):
    """Identity is not a solver input: identical saved-rule shapes plan identically."""
    records = [{"record_id": "source", "item_key": "component", "quantity": 10, "available_quantity": 10}]
    first = compute(monkeypatch, rules=[rule(key="component", output="OUTPUT", price="3", priority=4)], records=records, balance_cif="100")
    second = compute(monkeypatch, rules=[rule(key="component", output="OUTPUT", price="3", priority=4)], records=records, balance_cif="100")
    assert _normalized(first) == _normalized(second)


def test_synthetic_configuration_mutations_change_output_without_norm_code(monkeypatch):
    records = [
        {"record_id": "a", "item_key": "a", "quantity": 10, "available_quantity": 10},
        {"record_id": "b", "item_key": "b", "quantity": 10, "available_quantity": 10},
    ]
    baseline = compute(monkeypatch, rules=[
        rule(key="a", output="A", price="2", priority=1),
        rule(key="b", output="B", price="2", priority=2),
    ], records=records, balance_cif="20")
    changed_price = compute(monkeypatch, rules=[
        rule(key="a", output="A", price="1", priority=1),
        rule(key="b", output="B", price="2", priority=2),
    ], records=records, balance_cif="20")
    changed_priority = compute(monkeypatch, rules=[
        rule(key="a", output="A", price="2", priority=2),
        rule(key="b", output="B", price="2", priority=1),
    ], records=records, balance_cif="20")
    assert _normalized(changed_price) != _normalized(baseline)
    assert [row.output_key for row in changed_priority.rows] == ["B"]


def test_deactivating_a_synthetic_rule_line_removes_its_plan_output(monkeypatch):
    records = [{"record_id": "source", "item_key": "component", "quantity": 10, "available_quantity": 10}]
    active = compute(monkeypatch, rules=[rule(key="component", output="OUTPUT", price="2")], records=records, balance_cif="100")
    inactive = compute(monkeypatch, rules=[], records=records, balance_cif="100")
    assert len(active.rows) == 1
    assert inactive.rows == []
    assert inactive.remaining_cif == Decimal("100")


@pytest.mark.parametrize(("rules", "code"), [
    ([], "NO_ACTIVE_RULE"),
    ([SimpleNamespace(stable_key="same", strategy="STANDARD"), SimpleNamespace(stable_key="same", strategy="STANDARD")], "MULTIPLE_ACTIVE_RULES"),
    ([SimpleNamespace(stable_key="percent", strategy="SPLIT_BY_PERCENT", percentage_rows=[])], "MISSING_RULE_LINES"),
    ([SimpleNamespace(stable_key="percent", strategy="SPLIT_BY_PERCENT", percentage_rows=[SimpleNamespace(import_item_id=1, percentage=Decimal("60"))])], "INVALID_PERCENTAGE_TOTAL"),
    ([SimpleNamespace(stable_key="percent", strategy="SPLIT_BY_PERCENT", percentage_rows=[SimpleNamespace(import_item_id=None, percentage=Decimal("100"))])], "MISSING_CANONICAL_INPUT"),
    ([SimpleNamespace(stable_key="unknown", strategy="NOT_A_STRATEGY")], "UNSUPPORTED_GENERIC_STRATEGY"),
])
def test_generic_configuration_diagnostics_are_machine_readable(rules, code):
    with pytest.raises(PlannerConfigurationError) as raised:
        validate_declarative_rules(rules)
    assert raised.value.code == code
