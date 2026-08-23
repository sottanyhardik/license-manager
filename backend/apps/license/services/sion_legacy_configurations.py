"""Audited, deterministic configuration for legacy SION planner migration.

This module is data only.  It deliberately does not import or call a legacy
planner, and it contains no execution branches by norm.  Importers persist the
definitions into the generic profile/action/mapping models; the shadow runner
uses ``GOLDEN_CASES`` to prove that the generic primitives retain the legacy
Decimal semantics before a profile is activated.

Sources (audited 2026-08-17): ``e126_plan.py``, ``e126_auto_plan.py``,
``e132_plan.py``, ``e132_auto_plan.py`` and ``a3627_auto_plan.py``.
"""
from __future__ import annotations


def leaf(field: str, comparator: str, value: str) -> dict:
    return {"field": field, "operator": comparator, "value": value}


def group(operator: str, *conditions: dict) -> dict:
    return {"operator": operator, "conditions": list(conditions)}


def _profile(norm: str, *, quantity_rounding: str, quantity_precision: int) -> dict:
    return {
        "stable_key": f"{norm}:PROFILE",
        "strategy_type": "ACTION_PIPELINE",
        "version": 1,
        "is_active": False,  # activation is blocked until shadow equivalence passes
        "config": {
            "input_quantity_field": "available_quantity",
            "balance_field": "get_balance_cif",
            "record_order": ["serial_number", "id"],
            "classification": "FIRST_MATCH_WINS",
            "decimal_mode": "EXACT",
            "quantity_policy": {
                "precision": quantity_precision,
                "rounding": quantity_rounding,
            },
        },
    }


E126 = {
    "profile": _profile("E126", quantity_rounding="FLOOR", quantity_precision=0),
    "rules": [
        {
            "stable_key": "E126:RULE:001:NUTS",
            "name": "Nuts",
            "priority": 1,
            "expression": group("AND",
                group("OR", leaf("HSN", "STARTS_WITH", "0802"),
                      leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0802")),
                group("OR", leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "nut"),
                      leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "nuts")),
            ),
            "max_unit_price": "3.00", "unit": "KG", "output_key": "NUTS",
        },
        {
            "stable_key": "E126:RULE:002:PKO_OLIVE_SPLIT",
            "name": "Palm Kernel / Olive Oil split",
            "priority": 2,
            "expression": group("AND",
                group("OR", leaf("HSN", "STARTS_WITH", "1513"),
                      leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "1513")),
                group("OR", leaf("HSN", "STARTS_WITH", "1509"),
                      leaf("PRODUCT_DESCRIPTION", "CONTAINS", "1500"),
                      leaf("PRODUCT_DESCRIPTION", "CONTAINS", "1509"),
                      leaf("PRODUCT_DESCRIPTION", "CONTAINS", "1510")),
            ),
            "max_unit_price": "5.00", "unit": "KG", "output_key": "PKO_OLIVE_SPLIT",
        },
        {
            "stable_key": "E126:RULE:003:PKO", "name": "Palm Kernel Oil",
            "priority": 3,
            "expression": group("OR", leaf("HSN", "STARTS_WITH", "1513"),
                                leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "1513")),
            "max_unit_price": "1.80", "unit": "KG", "output_key": "PKO",
        },
        {
            "stable_key": "E126:RULE:004:OLIVE", "name": "Olive Oil",
            "priority": 4,
            "expression": group("OR", leaf("HSN", "STARTS_WITH", "1509"),
                leaf("PRODUCT_DESCRIPTION", "CONTAINS", "1500"),
                leaf("PRODUCT_DESCRIPTION", "CONTAINS", "1509"),
                leaf("PRODUCT_DESCRIPTION", "CONTAINS", "1510")),
            "max_unit_price": "5.00", "unit": "KG", "output_key": "OLIVE",
        },
    ],
    "actions": [
        {"stable_key": "E126:ACTION:001:MATCH", "priority": 1, "action_type": "MATCH",
         "config": {"mode": "ORDERED_FIRST_MATCH", "normalization": {"hsn": "DIGITS_ONLY", "description": "CASEFOLD_COLLAPSE_SPACE"}}},
        {"stable_key": "E126:ACTION:002:SPLIT", "priority": 2, "action_type": "SPLIT",
         "config": {"source_output": "PKO_OLIVE_SPLIT", "basis": "RECORD_AVAILABLE_QUANTITY", "targets": {"PKO": "0.5", "OLIVE": "0.5"}}},
        {"stable_key": "E126:ACTION:003:GROUP", "priority": 3, "action_type": "GROUP",
         "config": {"mode": "PHYSICAL_PRODUCT", "identity": "HSN_DESCRIPTION_UNIT_WITH_ITEM_NAME_FALLBACK", "representative": "LOWEST_SERIAL_NUMBER", "quantity": "SUM_AVAILABLE_QUANTITY", "output_order": ["NUTS", "PKO", "OLIVE"]}},
        {"stable_key": "E126:ACTION:004:ALLOCATE", "priority": 4, "action_type": "ALLOCATE",
         "config": {"mode": "SEQUENTIAL_CIF_WATERFALL", "consume_remaining": True, "partial_mode": "REDUCE_EFFECTIVE_RATE", "order": ["NUTS", "PKO", "OLIVE"]}},
        {"stable_key": "E126:ACTION:005:REBALANCE", "priority": 5, "action_type": "REBALANCE",
         "config": {"mode": "VALUE_GAIN_SHIFT", "source": "PKO", "target": "OLIVE", "eligible_source": "PKO_OLIVE_SPLIT", "record_order": "INPUT", "stop_at_balance": True}},
        {"stable_key": "E126:ACTION:006:ROUND", "priority": 6, "action_type": "ROUND", "config": {"quantity": {"precision": 0, "rounding": "FLOOR"}, "planned_cif": {"precision": 2, "rounding": "ROUND_HALF_EVEN"}, "recompute_value_after_quantity_rounding": True}},
        {"stable_key": "E126:ACTION:007:MAP", "priority": 7, "action_type": "MAP_OUTPUT", "config": {"omit_zero_value": True, "existing_split_policy": "PRESERVE_GROUP_WIDE_ONCE_GENERATED"}},
    ],
    "mappings": [
        {"stable_key": "E126:OUTPUT:001:NUTS", "priority": 1, "source_key": "NUTS", "output_name": "NUTS - E126", "rate": "3.00", "conversion_factor": "1", "unit": "KG"},
        {"stable_key": "E126:OUTPUT:002:PKO", "priority": 2, "source_key": "PKO", "output_name": "PALM KERNEL OIL - E126", "rate": "1.80", "conversion_factor": "1", "unit": "KG"},
        {"stable_key": "E126:OUTPUT:003:OLIVE", "priority": 3, "source_key": "OLIVE", "output_name": "OLIVE OIL - E126", "rate": "5.00", "conversion_factor": "1", "unit": "KG"},
    ],
}


E132 = {
    "profile": _profile("E132", quantity_rounding="FLOOR", quantity_precision=0),
    "rules": [
        {"stable_key": "E132:RULE:001:NUTS", "name": "Nut and Nuts", "priority": 1,
         "expression": group("AND", group("OR", leaf("HSN", "STARTS_WITH", "0802"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0802")), group("OR", leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "nut"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "nuts"))), "max_unit_price": "3.00", "unit": "KG", "output_key": "NUTS"},
        {"stable_key": "E132:RULE:002:YEAST", "name": "Yeast", "priority": 2,
         "expression": group("AND", group("OR", leaf("HSN", "STARTS_WITH", "2106"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "2106")), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "yeast")), "max_unit_price": "5.00", "unit": "KG", "output_key": "YEAST"},
        # Explicit cheese precedes RBD and split exactly as the legacy priority-3 subgroup.
        {"stable_key": "E132:RULE:003:EXPLICIT_CHEESE", "name": "Explicit Cheese", "priority": 3,
         "expression": group("AND", leaf("PRODUCT_DESCRIPTION", "CONTAINS", "cheese"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "vegetable"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "oil")), "max_unit_price": "5.50", "unit": "KG", "output_key": "CHEESE"},
        {"stable_key": "E132:RULE:004:RBD", "name": "RBD", "priority": 4,
         "expression": group("OR", leaf("HSN", "STARTS_WITH", "1510"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "1510")), "max_unit_price": "1.20", "unit": "KG", "output_key": "RBD"},
        {"stable_key": "E132:RULE:005:VEG_OIL_SPLIT", "name": "PKO / Cheese split", "priority": 5,
         "expression": group("AND", group("OR", leaf("HSN", "STARTS_WITH", "1513"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "1513")), group("OR", leaf("HSN", "STARTS_WITH", "0401"), leaf("HSN", "STARTS_WITH", "0405"), leaf("HSN", "STARTS_WITH", "0406"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0401"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0405"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0406")), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "vegetable"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "oil")), "max_unit_price": "5.50", "unit": "KG", "output_key": "VEG_OIL_SPLIT"},
        {"stable_key": "E132:RULE:006:PKO", "name": "PKO", "priority": 6,
         "expression": group("OR", leaf("HSN", "STARTS_WITH", "1513"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "1513")), "max_unit_price": "1.80", "unit": "KG", "output_key": "PKO"},
        {"stable_key": "E132:RULE:007:STRICT_CHEESE", "name": "Strict Cheese", "priority": 7,
         "expression": group("AND", group("OR", leaf("HSN", "STARTS_WITH", "0401"), leaf("HSN", "STARTS_WITH", "0405"), leaf("HSN", "STARTS_WITH", "0406"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0401"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0405"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "0406")), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "vegetable"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "oil")), "max_unit_price": "5.50", "unit": "KG", "output_key": "CHEESE"},
        {"stable_key": "E132:RULE:008:ALUMINIUM", "name": "Aluminium Foil", "priority": 8,
         "expression": group("OR", leaf("HSN", "STARTS_WITH", "7607"), leaf("PRODUCT_DESCRIPTION", "WORD_CONTAINS", "7607"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "aluminium foil"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "aluminum foil")), "max_unit_price": "4.50", "unit": "KG", "output_key": "ALUMINIUM"},
    ],
    "actions": [
        {"stable_key": "E132:ACTION:001:MATCH", "priority": 1, "action_type": "MATCH", "config": {"mode": "ORDERED_FIRST_MATCH", "normalization": {"hsn": "DIGITS_ONLY", "description": "CASEFOLD_COLLAPSE_SPACE"}}},
        {"stable_key": "E132:ACTION:002:SPLIT", "priority": 2, "action_type": "SPLIT", "config": {"source_output": "VEG_OIL_SPLIT", "basis": "RECORD_AVAILABLE_QUANTITY", "targets": {"PKO": "0.4", "CHEESE": "0.6"}}},
        {"stable_key": "E132:ACTION:003:GROUP", "priority": 3, "action_type": "GROUP", "config": {"mode": "PHYSICAL_PRODUCT", "identity": "HSN_DESCRIPTION_UNIT_WITH_ITEM_NAME_FALLBACK", "representative": "LOWEST_SERIAL_NUMBER", "quantity": "SUM_AVAILABLE_QUANTITY", "output_order": ["NUTS", "YEAST", "PKO", "RBD", "CHEESE", "ALUMINIUM"]}},
        {"stable_key": "E132:ACTION:004:ALLOCATE", "priority": 4, "action_type": "ALLOCATE", "config": {"mode": "SEQUENTIAL_CIF_WATERFALL", "consume_remaining": True, "partial_mode": "REDUCE_EFFECTIVE_RATE", "order": ["NUTS", "YEAST", "PKO", "RBD", "CHEESE", "ALUMINIUM"]}},
        {"stable_key": "E132:ACTION:005:REBALANCE", "priority": 5, "action_type": "REBALANCE", "config": {"mode": "VALUE_GAIN_SHIFT", "source": "PKO", "target": "CHEESE", "eligible_source": "VEG_OIL_SPLIT", "record_order": "INPUT", "stop_at_balance": True}},
        {"stable_key": "E132:ACTION:006:ROUND", "priority": 6, "action_type": "ROUND", "config": {"quantity": {"precision": 0, "rounding": "FLOOR"}, "planned_cif": {"precision": 2, "rounding": "ROUND_HALF_EVEN"}, "recompute_value_after_quantity_rounding": True}},
        {"stable_key": "E132:ACTION:007:MAP", "priority": 7, "action_type": "MAP_OUTPUT", "config": {"omit_zero_value": True, "existing_split_policy": "PRESERVE_GROUP_WIDE_ONCE_GENERATED"}},
    ],
    "mappings": [
        {"stable_key": f"E132:OUTPUT:{index:03d}:{key}", "priority": index, "source_key": key, "output_name": name, "rate": rate, "conversion_factor": "1", "unit": "KG"}
        for index, (key, name, rate) in enumerate((
            ("NUTS", "NUT & NUTS - E132", "3.00"), ("YEAST", "Yeast - E132", "5.00"),
            ("PKO", "PKO - E132", "1.80"), ("RBD", "RBD - E132", "1.20"),
            ("CHEESE", "CHEESE CREAM BUTTER AND FATS - E132", "5.50"),
            ("ALUMINIUM", "Aluminium Foil - E132", "4.50")), 1)
    ],
}


A3627 = {
    "profile": _profile("A3627", quantity_rounding="FLOOR", quantity_precision=0),
    "rules": [
        {"stable_key": "A3627:RULE:001:RUTILE", "name": "Rutile", "priority": 1,
         "expression": group("AND", group("OR", leaf("HSN", "STARTS_WITH", "3206"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "glass formers"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "rutile"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "formers")), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "borax")), "max_unit_price": "3.50", "unit": "KG", "output_key": "RUTILE"},
        {"stable_key": "A3627:RULE:002:TITANIUM", "name": "Titanium Dioxide", "priority": 2,
         "expression": group("AND", leaf("PRODUCT_DESCRIPTION", "CONTAINS", "titanium dioxide"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "other than")), "max_unit_price": "2.00", "unit": "KG", "output_key": "TITANIUM"},
        {"stable_key": "A3627:RULE:003:SODA_ASH", "name": "Soda Ash", "priority": 3,
         "expression": leaf("PRODUCT_DESCRIPTION", "CONTAINS", "soda ash"), "max_unit_price": "0.70", "unit": "KG", "output_key": "SODA_ASH"},
        {"stable_key": "A3627:RULE:004:PP", "name": "PP", "priority": 4,
         "expression": group("AND", group("OR", leaf("HSN", "STARTS_WITH", "3902"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "polypropylene"), leaf("PRODUCT_DESCRIPTION", "CONTAINS", "pp granules"), group("AND", leaf("PRODUCT_DESCRIPTION", "CONTAINS", "packing material"), leaf("HSN", "STARTS_WITH", "39"))), leaf("PRODUCT_DESCRIPTION", "NOT_CONTAINS", "bopp"), leaf("PRODUCT_DESCRIPTION", "NOT_CONTAINS", "7607"), leaf("PRODUCT_DESCRIPTION", "NOT_CONTAINS", "aluminium foil"), leaf("HSN", "NOT_STARTS_WITH", "7607"), leaf("HSN", "NOT_STARTS_WITH", "4801")), "max_unit_price": "1.20", "unit": "KG", "output_key": "PP"},
    ],
    "actions": [
        {"stable_key": "A3627:ACTION:001:MATCH", "priority": 1, "action_type": "MATCH", "config": {"mode": "ORDERED_FIRST_MATCH", "normalization": {"description": "CASEFOLD"}}},
        {"stable_key": "A3627:ACTION:002:GROUP", "priority": 2, "action_type": "GROUP", "config": {"mode": "CLASSIFICATION_IDENTITY", "identity_fields": ["description", "hs_code_id", "condition_type", "unit"], "representative": "LOWEST_SERIAL_NUMBER", "quantity": "SUM_AVAILABLE_QUANTITY"}},
        {"stable_key": "A3627:ACTION:003:PRICE", "priority": 3, "action_type": "PRICE", "config": {"mode": "MAPPED_WITH_CONDITIONAL", "prices": {"TITANIUM": "2.00", "SODA_ASH": "0.70", "PP": "1.20"}, "conditional": {"output": "RUTILE", "aggregate": {"operation": "WEIGHTED_AVERAGE", "numerator": "cif_fc", "denominator": "quantity", "scope": "ALL_MATCHED_SOURCE_ROWS"}, "branches": [{"operator": "LT", "value": "3.00", "price": "2.50"}, {"operator": "GTE", "value": "3.00", "price": "3.50"}]}}},
        {"stable_key": "A3627:ACTION:004:ALLOCATE", "priority": 4, "action_type": "ALLOCATE", "config": {"mode": "SEQUENTIAL_CIF_WATERFALL", "consume_remaining": True, "order": ["RUTILE", "TITANIUM", "SODA_ASH", "PP"], "within_output_order": ["serial_number", "id"], "partial_mode": "REDUCE_QUANTITY"}},
        {"stable_key": "A3627:ACTION:005:ROUND", "priority": 5, "action_type": "ROUND", "config": {"quantity": {"precision": 0, "rounding": "FLOOR"}, "planned_cif": {"precision": 2, "rounding": "ROUND_HALF_EVEN"}, "residual": "CARRY_FORWARD"}},
        {"stable_key": "A3627:ACTION:006:MAP", "priority": 6, "action_type": "MAP_OUTPUT", "config": {"omit_zero_value": True}},
    ],
    "mappings": [
        {"stable_key": f"A3627:OUTPUT:{index:03d}:{key}", "priority": index, "source_key": key, "output_name": name, "rate": rate, "conversion_factor": "1", "unit": "KG"}
        for index, (key, name, rate) in enumerate((("RUTILE", "RUTILE - A3627", None), ("TITANIUM", "TITANIUM DIOXIDE - A3627", "2.00"), ("SODA_ASH", "SODA ASH - A3627", "0.70"), ("PP", "PP - A3627", "1.20")), 1)
    ],
}


LEGACY_PLANNER_CONFIGURATIONS = {"E126": E126, "E132": E132, "A3627": A3627}


# JSON-safe golden inputs/outputs. Decimal values are strings intentionally:
# comparison code must parse them as Decimal and compare exactly.
GOLDEN_CASES = {
    "E126": [
        {"name": "priority_and_partial_waterfall", "balance_cif": "50", "records": [
            {"record_id": "nuts", "hs_code": "08021100", "description": "cashew nuts", "quantity": "10"},
            {"record_id": "olive", "hs_code": "1509", "description": "olive oil", "quantity": "10"}],
         "expected": {"rows": [{"output_key": "NUTS", "quantity": "10", "unit_price": "3.00", "value": "30.00"}, {"output_key": "OLIVE", "quantity": "10", "unit_price": "2", "value": "20"}], "remaining_cif": "0"}},
        {"name": "split_rebalance_exact", "balance_cif": "400", "records": [{"record_id": "split", "hs_code": "15132900", "description": "olive 1509 blend", "quantity": "100"}], "expected": {"rows": [{"output_key": "PKO", "quantity": "31.25", "unit_price": "1.80", "value": "56.2500"}, {"output_key": "OLIVE", "quantity": "68.75", "unit_price": "5.00", "value": "343.7500"}], "remaining_cif": "0"}},
    ],
    "E132": [
        {"name": "ordered_classification", "balance_cif": "1000", "records": [{"record_id": "nuts", "hs_code": "08021100", "description": "Cheese Vegetable Oil Nut Blend", "quantity": "2"}, {"record_id": "rbd", "hs_code": "1510", "description": "oil", "quantity": "3"}], "expected": {"rows": [{"output_key": "NUTS", "quantity": "2", "unit_price": "3.00", "value": "6.00"}, {"output_key": "RBD", "quantity": "3", "unit_price": "1.20", "value": "3.60"}], "remaining_cif": "990.40"}},
        {"name": "split_rebalance_exact", "balance_cif": "439", "records": [{"record_id": "split", "hs_code": "15132900", "description": "Vegetable Oil Dairy 0406", "quantity": "100"}], "expected": {"rows": [{"output_key": "PKO", "quantity": "30", "unit_price": "1.80", "value": "54.00"}, {"output_key": "CHEESE", "quantity": "70", "unit_price": "5.50", "value": "385.00"}], "remaining_cif": "0"}},
    ],
    "A3627": [
        {"name": "weighted_price_waterfall_and_floor", "balance_cif": "1000", "records": [{"record_id": "rutile", "serial_number": 1, "hs_code": "32061010", "description": "Rutile Glass Formers with Borax", "quantity": "100", "available_quantity": "100", "cif_fc": "285"}, {"record_id": "titanium", "serial_number": 2, "description": "Titanium Dioxide other than grade", "quantity": "50", "available_quantity": "50"}, {"record_id": "soda", "serial_number": 3, "description": "Soda Ash", "quantity": "200", "available_quantity": "200"}, {"record_id": "pp", "serial_number": 4, "hs_code": "39023000", "description": "Polypropylene Granules", "quantity": "1000", "available_quantity": "1000"}], "expected": {"rows": [{"output_key": "RUTILE", "quantity": "100", "unit_price": "2.50", "value": "250.00"}, {"output_key": "TITANIUM", "quantity": "50", "unit_price": "2.00", "value": "100.00"}, {"output_key": "SODA_ASH", "quantity": "200", "unit_price": "0.70", "value": "140.00"}, {"output_key": "PP", "quantity": "425", "unit_price": "1.20", "value": "510.00"}], "remaining_cif": "0.00"}},
        {"name": "floor_residual", "balance_cif": "10.05", "records": [{"record_id": "soda", "serial_number": 1, "description": "Soda Ash", "quantity": "1000", "available_quantity": "1000"}, {"record_id": "pp", "serial_number": 2, "hs_code": "39023000", "description": "PP granules", "quantity": "1000", "available_quantity": "1000"}], "expected": {"rows": [{"output_key": "SODA_ASH", "quantity": "14", "unit_price": "0.70", "value": "9.80"}], "remaining_cif": "0.25"}},
    ],
}
