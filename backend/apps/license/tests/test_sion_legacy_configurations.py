"""Migration contracts for audited E126/E132/A3627 DB configuration."""
from decimal import Decimal

import pytest

from apps.license.services.e126_plan import plan_e126
from apps.license.services.e132_plan import plan_e132
from apps.license.services.sion_legacy_configurations import (
    GOLDEN_CASES,
    LEGACY_PLANNER_CONFIGURATIONS,
)


@pytest.mark.parametrize("norm", ["E126", "E132", "A3627"])
def test_configuration_has_stable_unique_ordered_identity(norm):
    definition = LEGACY_PLANNER_CONFIGURATIONS[norm]
    assert definition["profile"]["stable_key"] == f"{norm}:PROFILE"
    assert definition["profile"]["is_active"] is False
    for collection in ("rules", "actions", "mappings"):
        rows = definition[collection]
        assert [row["priority"] for row in rows] == list(range(1, len(rows) + 1))
        assert len({row["stable_key"] for row in rows}) == len(rows)
        assert all(row["stable_key"].startswith(f"{norm}:") for row in rows)


def test_e126_exact_split_and_rebalance_contract():
    case = GOLDEN_CASES["E126"][1]
    result = plan_e126(case["records"], Decimal(case["balance_cif"]))
    rows = {row["planning_item_name"]: row for row in result["items"]}
    assert rows["PALM KERNEL OIL - E126"]["total_quantity"] == Decimal("31.25")
    assert rows["PALM KERNEL OIL - E126"]["planning_value"] == Decimal("56.2500")
    assert rows["OLIVE OIL - E126"]["total_quantity"] == Decimal("68.75")
    assert rows["OLIVE OIL - E126"]["planning_value"] == Decimal("343.7500")
    assert result["wastage"] == Decimal("0")


def test_e132_exact_split_and_rebalance_contract():
    case = GOLDEN_CASES["E132"][1]
    result = plan_e132(case["records"], Decimal(case["balance_cif"]))
    rows = {row["planning_item_name"]: row for row in result["items"]}
    assert rows["PKO - E132"]["total_quantity"] == Decimal("30")
    assert rows["PKO - E132"]["planning_value"] == Decimal("54.00")
    assert rows["CHEESE CREAM BUTTER AND FATS - E132"]["total_quantity"] == Decimal("70")
    assert rows["CHEESE CREAM BUTTER AND FATS - E132"]["planning_value"] == Decimal("385.00")
    assert result["wastage"] == Decimal("0")


def test_a3627_dynamic_price_and_floor_are_configuration_not_code_defaults():
    definition = LEGACY_PLANNER_CONFIGURATIONS["A3627"]
    price = next(a for a in definition["actions"] if a["action_type"] == "PRICE")["config"]
    conditional = price["conditional"]
    assert conditional["aggregate"] == {
        "operation": "WEIGHTED_AVERAGE",
        "numerator": "cif_fc",
        "denominator": "quantity",
        "scope": "ALL_MATCHED_SOURCE_ROWS",
    }
    assert conditional["branches"] == [
        {"operator": "LT", "value": "3.00", "price": "2.50"},
        {"operator": "GTE", "value": "3.00", "price": "3.50"},
    ]
    rounding = next(a for a in definition["actions"] if a["action_type"] == "ROUND")["config"]
    assert rounding["quantity"] == {"precision": 0, "rounding": "FLOOR"}
    assert GOLDEN_CASES["A3627"][1]["expected"]["remaining_cif"] == "0.25"


def test_no_float_in_persistable_configuration():
    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        else:
            assert not isinstance(value, float)

    walk(LEGACY_PLANNER_CONFIGURATIONS)
    walk(GOLDEN_CASES)
