from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.license.services.sion_rule_engine import (
    MAX_DEPTH,
    evaluate_expression,
    validate_expression,
)


def predicate(field, op, value):
    return {"field": field, "op": op, "value": value}


def test_rule_one_nested_and_or_not_boolean_semantics():
    expression = {
        "op": "and",
        "args": [
            predicate("unit", "eq", "KG"),
            {"op": "or", "args": [
                predicate("hs_code", "eq", "0402"),
                predicate("description", "contains", "milk powder"),
            ]},
            {"op": "not", "arg": predicate("is_restricted", "eq", True)},
        ],
    }
    assert evaluate_expression(expression, {
        "unit": "kg", "hs_code": "0402", "description": "SKIMMED MILK POWDER",
        "is_restricted": False,
    }) is True
    assert evaluate_expression(expression, {
        "unit": "KG", "hs_code": "0402", "description": "Milk Powder",
        "is_restricted": True,
    }) is False


def test_rule_two_numeric_decimal_and_leading_zero_hsn_are_preserved():
    expression = {"op": "and", "conditions": [
        predicate("available_qty", "gte", "10.125"),
        predicate("hs_code", "eq", "0402"),
    ]}
    assert evaluate_expression(expression, {
        "available_qty": Decimal("10.125"), "hs_code": "0402",
    }) is True
    assert evaluate_expression(expression, {
        "available_qty": Decimal("10.125"), "hs_code": "402",
    }) is False


@pytest.mark.parametrize("expression", [
    {},
    {"op": "xor", "args": []},
    {"op": "and", "args": []},
    {"op": "not"},
    predicate("__class__", "eq", "anything"),
    {"field": "description", "op": "contains"},
])
def test_invalid_or_empty_expression_is_rejected(expression):
    with pytest.raises(ValidationError):
        validate_expression(expression)


def test_excessive_nesting_is_rejected():
    expression = predicate("unit", "eq", "KG")
    for _ in range(MAX_DEPTH + 1):
        expression = {"op": "not", "arg": expression}
    with pytest.raises(ValidationError):
        validate_expression(expression)


def test_case_and_outer_space_are_normalized_but_inner_text_is_preserved():
    expression = {"op": "and", "args": [
        predicate("unit", "eq", " kg "),
        predicate("description", "contains", " milk powder "),
    ]}
    assert evaluate_expression(expression, {
        "unit": "KG", "description": "Skimmed Milk Powder Grade A",
    }) is True
