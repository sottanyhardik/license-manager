"""Lossless, audited E1/E5 planner configuration documents.

Decimal values are strings deliberately.  Conditions are evaluated in list
order with ``first_match`` semantics; this preserves the classifiers in
``e1_plan.classify_e1_item`` and ``e5_plan.classify_e5_item``.  The action
documents describe the complete waterfall, including the reporting/auto-plan
differences, without using a SION-specific action type.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _condition(field: str, operator: str, value: str) -> dict[str, str]:
    return {"field": field, "operator": operator, "value": value}


def _any(*conditions: dict[str, Any]) -> dict[str, Any]:
    return {"operator": "OR", "conditions": list(conditions)}


def _all(*conditions: dict[str, Any]) -> dict[str, Any]:
    return {"operator": "AND", "conditions": list(conditions)}


def _not(condition: dict[str, Any]) -> dict[str, Any]:
    return {"operator": "NOT", "conditions": [condition]}


HSN = "HSN_DIGITS"
ITEM = "ITEM_KEY"
DESCRIPTION = "PRODUCT_DESCRIPTION"


_E1_CLASSIFICATION = (
    {
        "category": "OTHER CONFECTIONERY INGREDIENTS",
        "expression": _all(
            _not(_any(_condition(ITEM, "CONTAINS", "food flavour"), _condition(DESCRIPTION, "CONTAINS", "food flavour"))),
            _any(
                _condition(HSN, "STARTS_WITH", "0802"),
                _condition(ITEM, "CONTAINS", "other confectionery"),
                _condition(DESCRIPTION, "CONTAINS", "other confectionery"),
            ),
        ),
    },
    {
        "category": "COCOA MASS",
        "expression": _any(_condition(HSN, "STARTS_WITH", "1803"), _condition(DESCRIPTION, "CONTAINS", "1803")),
    },
    {
        "category": "MILK PRODUCTS",
        "expression": _all(
            _any(_condition(HSN, "STARTS_WITH", "0404"), _condition(DESCRIPTION, "CONTAINS", "0404")),
            _condition(DESCRIPTION, "CONTAINS", "milk"),
            _not(_any(_condition(HSN, "STARTS_WITH", "1803"), _condition(DESCRIPTION, "CONTAINS", "1803"))),
        ),
    },
    {
        "category": "EGG ALBUMIN",
        "expression": _all(
            _any(_condition(HSN, "STARTS_WITH", "3502"), _condition(DESCRIPTION, "CONTAINS", "3502")),
            _not(_any(_condition(HSN, "STARTS_WITH", "1803"), _condition(DESCRIPTION, "CONTAINS", "1803"))),
            _not(_any(_condition(HSN, "STARTS_WITH", "0404"), _condition(DESCRIPTION, "CONTAINS", "0404"))),
        ),
    },
    {"category": "FRUIT JUICE", "expression": _any(_condition(HSN, "STARTS_WITH", "2009"), _condition(DESCRIPTION, "CONTAINS", "juice"))},
    {"category": "TARTARIC ACID", "expression": _any(_condition(HSN, "STARTS_WITH", "2918"), _condition(DESCRIPTION, "CONTAINS", "2918"), _condition(ITEM, "CONTAINS", "tartaric"), _condition(DESCRIPTION, "CONTAINS", "tartaric"))},
    {"category": "ALUMINIUM FOIL", "expression": _any(_condition(HSN, "STARTS_WITH", "7607"), _condition(ITEM, "CONTAINS", "7607"), _condition(DESCRIPTION, "CONTAINS", "7607"))},
    {"category": "POLYPROPYLENE", "expression": _condition(HSN, "STARTS_WITH", "3902")},
)


_E5_CLASSIFICATION = (
    {"category": "DIETARY FIBRE", "expression": _any(_condition(ITEM, "CONTAINS", "dietary fibre"), _condition(DESCRIPTION, "CONTAINS", "dietary fibre"))},
    {"category": "WHEAT FLOUR", "expression": _condition(ITEM, "CONTAINS", "wheat flour")},
    {"category": "MILK PRODUCTS", "expression": _condition(HSN, "CONTAINS", "0404")},
    {"category": "EGG ALBUMIN / WPC", "expression": _condition(HSN, "CONTAINS", "3502")},
    {"category": "REMAINING OILS", "expression": _condition(ITEM, "CONTAINS", "olive oil")},
    {"category": "PALM KERNEL OIL", "expression": _any(_condition(HSN, "CONTAINS", "1513"), _condition(DESCRIPTION, "CONTAINS", "vegetable oil"), _condition(ITEM, "CONTAINS", "pko"))},
    {"category": "RBD PALMOLEIN", "expression": _any(_condition(HSN, "CONTAINS", "1511"), _condition(ITEM, "CONTAINS", "rbd"))},
    {"category": "REMAINING OILS", "expression": _any(_condition(HSN, "STARTS_WITH", "15"), _condition(DESCRIPTION, "CONTAINS", "edible oil"))},
    {"category": "WHEAT FLOUR", "expression": _condition(HSN, "CONTAINS", "11010000")},
)


def _fixed_action(key: str, priority: int, category: str, rate: str, *, granularity: str) -> dict[str, Any]:
    return {
        "stable_key": key,
        "action_type": "ALLOCATE",
        "priority": priority,
        "config": {
            "algorithm": "CAPPED_FIXED_RATE_WATERFALL",
            "category": category,
            "rate": rate,
            "granularity": granularity,
            "consume_remaining": True,
            "reporting_insufficient_balance": "REDUCE_RATE_KEEP_FULL_QUANTITY",
            "auto_insufficient_balance": "KEEP_RATE_FLOOR_QUANTITY" if granularity == "ITEM" else "REDUCE_RATE_KEEP_FULL_QUANTITY",
        },
    }


E1_PROFILE: dict[str, Any] = {
    "sion_code": "E1",
    "stable_key": "E1:PROFILE",
    "strategy_type": "ACTION_PIPELINE",
    "version": 1,
    "config": {
        "input_order": "SERIAL_NUMBER_ASC",
        "classification_mode": "FIRST_MATCH",
        "consumption_basis": "CIF",
        "consumption_mode": "SEQUENTIAL_WATERFALL",
        "recompute_remaining_after_each_action": True,
        "auto_minimum_quantity": "50",
        "reporting_minimum_quantity": "0",
        "money_output_precision": 4,
        "decimal_rounding": "CONTEXT_DEFAULT",
    },
    "actions": (
        {"stable_key": "E1:ACTION:001:CLASSIFY", "action_type": "MATCH", "priority": 1, "config": {"mode": "FIRST_MATCH", "rules": _E1_CLASSIFICATION}},
        {"stable_key": "E1:ACTION:002:GROUP", "action_type": "GROUP", "priority": 2, "config": {"by": "MATCH_CATEGORY", "preserve_input_order": True}},
        _fixed_action("E1:ACTION:010:CONFECTIONERY", 3, "OTHER CONFECTIONERY INGREDIENTS", "3.00", granularity="CATEGORY_SHARED_RATE"),
        _fixed_action("E1:ACTION:020:COCOA", 4, "COCOA MASS", "10.00", granularity="CATEGORY_SHARED_RATE"),
        {
            "stable_key": "E1:ACTION:030:MILK",
            "action_type": "SPLIT",
            "priority": 5,
            "config": {
                "algorithm": "MILK_0404_MAXIMISE_DWP",
                "category": "MILK PRODUCTS",
                "granularity": "ITEM_SEQUENTIAL",
                "dwp_max_rate": "6.5",
                "dwp_min_rate": "4.40",
                "swp_rate": "1.5",
                "consume_remaining_after_each_output": True,
            },
        },
        _fixed_action("E1:ACTION:040:EGG", 6, "EGG ALBUMIN", "25", granularity="CATEGORY_SHARED_RATE"),
        _fixed_action("E1:ACTION:050:JUICE", 7, "FRUIT JUICE", "2.50", granularity="CATEGORY_SHARED_RATE"),
        _fixed_action("E1:ACTION:060:TARTARIC", 8, "TARTARIC ACID", "1.50", granularity="CATEGORY_SHARED_RATE"),
        _fixed_action("E1:ACTION:070:ALUMINIUM", 9, "ALUMINIUM FOIL", "4.50", granularity="CATEGORY_SHARED_RATE"),
        _fixed_action("E1:ACTION:080:PP", 10, "POLYPROPYLENE", "1.20", granularity="CATEGORY_SHARED_RATE"),
        {"stable_key": "E1:ACTION:090:ROUND", "action_type": "ROUND", "priority": 11, "config": {"fields": ["unit_price", "planned_cif"], "precision": 4, "rounding": "CONTEXT_DEFAULT", "remaining_uses_unrounded_debits": True}},
    ),
    "mappings": (
        {"stable_key": "E1:MAPPING:DWP", "priority": 1, "source": "DWP", "output_key": "DWP"},
        {"stable_key": "E1:MAPPING:SWP", "priority": 2, "source": "SWP", "output_key": "SWP"},
    ),
}


E5_PROFILE: dict[str, Any] = {
    "sion_code": "E5",
    "stable_key": "E5:PROFILE",
    "strategy_type": "ACTION_PIPELINE",
    "version": 1,
    "config": {
        "input_order": "SERIAL_NUMBER_ASC",
        "classification_mode": "FIRST_MATCH",
        "consumption_basis": "CIF",
        "consumption_mode": "SEQUENTIAL_WATERFALL",
        "recompute_remaining_after_each_item": True,
        "auto_minimum_quantity": "50",
        "reporting_minimum_quantity": "0",
        "special_validation_uses_unfiltered_quantity": True,
        "money_output_precision": 4,
    },
    "actions": (
        {"stable_key": "E5:ACTION:001:CLASSIFY", "action_type": "MATCH", "priority": 1, "config": {"mode": "FIRST_MATCH", "rules": _E5_CLASSIFICATION}},
        {"stable_key": "E5:ACTION:002:GROUP", "action_type": "GROUP", "priority": 2, "config": {"by": "MATCH_CATEGORY", "preserve_input_order": True}},
        _fixed_action("E5:ACTION:010:FIBRE", 3, "DIETARY FIBRE", "3.00", granularity="ITEM"),
        {
            "stable_key": "E5:ACTION:020:SPECIAL_VALIDATION",
            "action_type": "ALLOCATE",
            "priority": 4,
            "config": {
                "algorithm": "CONDITIONAL_BRANCH",
                "condition": {
                    "operator": "AND",
                    "conditions": [
                        {"aggregate": "SUM_QUANTITY", "categories": ["MILK PRODUCTS", "EGG ALBUMIN / WPC"], "source": "UNFILTERED", "operator": "GT", "value": "0"},
                        {"field": "REMAINING_CIF", "operator": "GT", "value": "0"},
                        {"left": "REMAINING_CIF", "operator": "LT", "right": {"operation": "MULTIPLY", "arguments": [{"aggregate": "SUM_QUANTITY", "categories": ["MILK PRODUCTS", "EGG ALBUMIN / WPC"], "source": "UNFILTERED"}, {"constant": "1.5"}]}},
                    ],
                },
                "when_true": {"pipeline": "SPECIAL_MILK_THEN_OILS", "milk_rate": "1.5", "milk_categories": ["MILK PRODUCTS", "EGG ALBUMIN / WPC"], "reporting_insufficient_balance": "REDUCE_RATE_KEEP_FULL_QUANTITY", "auto_insufficient_balance": "KEEP_RATE_FLOOR_QUANTITY", "skip_pipeline": "NORMAL_MILK"},
                "when_false": {"pipeline": "OILS_THEN_NORMAL_MILK"},
            },
        },
        {
            "stable_key": "E5:ACTION:030:OILS",
            "action_type": "ALLOCATE",
            "priority": 5,
            "config": {
                "algorithm": "ORDERED_CATEGORY_FIXED_RATE",
                "pipeline_membership": ["SPECIAL_MILK_THEN_OILS", "OILS_THEN_NORMAL_MILK"],
                "categories": [
                    {"category": "PALM KERNEL OIL", "rate": "1.80"},
                    {"category": "RBD PALMOLEIN", "rate": "1.20"},
                    {"category": "REMAINING OILS", "rate": "5.00"},
                ],
                "granularity": "ITEM",
                "reporting_insufficient_balance": "REDUCE_RATE_KEEP_FULL_QUANTITY",
                "auto_insufficient_balance": "KEEP_RATE_FLOOR_QUANTITY",
            },
        },
        {
            "stable_key": "E5:ACTION:040:NORMAL_MILK",
            "action_type": "SPLIT",
            "priority": 6,
            "config": {
                "algorithm": "ORDERED_MILK_0404_THEN_WPC_3502",
                "pipeline_membership": ["OILS_THEN_NORMAL_MILK"],
                "milk_category": "MILK PRODUCTS",
                "wpc_category": "EGG ALBUMIN / WPC",
                "granularity": "ITEM_SEQUENTIAL",
                "dwp_max_rate": "6.5",
                "dwp_min_rate": "4.40",
                "swp_rate": "1.5",
                "wpc_max_rate": "25",
                "wpc_insufficient_balance": "REDUCE_RATE_KEEP_FULL_QUANTITY",
            },
        },
        {
            "stable_key": "E5:ACTION:050:WHEAT_MOP_UP",
            "action_type": "ALLOCATE",
            "priority": 7,
            "config": {
                "algorithm": "REMAINING_BALANCE_SHARED_RATE",
                "category": "WHEAT FLOUR",
                "rate_formula": {"operation": "DIVIDE", "arguments": [{"field": "REMAINING_CIF"}, {"aggregate": "SUM_QUANTITY", "category": "WHEAT FLOUR"}]},
                "granularity": "ITEM_SEQUENTIAL",
                "reporting_insufficient_balance": "KEEP_FULL_QUANTITY",
                "auto_insufficient_balance": "FLOOR_QUANTITY_KEEP_RATE",
            },
        },
        {"stable_key": "E5:ACTION:090:ROUND", "action_type": "ROUND", "priority": 8, "config": {"fields": ["unit_price", "planned_cif"], "precision": 4, "rounding": "CONTEXT_DEFAULT", "remaining_uses_unrounded_debits": True}},
    ),
    "mappings": (
        {"stable_key": "E5:MAPPING:DWP", "priority": 1, "source": "DWP", "output_key": "DWP"},
        {"stable_key": "E5:MAPPING:SWP", "priority": 2, "source": "SWP", "output_key": "SWP"},
        {"stable_key": "E5:MAPPING:WPC", "priority": 3, "source": "WPC", "output_key": "WPC"},
    ),
}


_CONFIGS = {"E1": E1_PROFILE, "E5": E5_PROFILE}


def get_legacy_planner_config(sion_code: str) -> dict[str, Any]:
    """Return an isolated copy so importer normalization cannot mutate source."""
    return deepcopy(_CONFIGS[sion_code.upper()])


LEGACY_PLANNER_CONFIGS = tuple(deepcopy(profile) for profile in _CONFIGS.values())
