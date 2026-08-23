"""Golden contracts for the norm-neutral declarative planner."""
from decimal import Decimal

import pytest

from apps.license.services.database_driven_sion_planner import (
    DatabaseDrivenSionPlanner,
    InvalidPlannerConfiguration,
)
from apps.license.services.sion_legacy_configurations import (
    GOLDEN_CASES,
    LEGACY_PLANNER_CONFIGURATIONS,
)
from apps.license.services.sion_planner_config.e1_e5 import E1_PROFILE, E5_PROFILE
from apps.license.services.sion_planner_config.golden_e1_e5 import (
    E1_GOLDEN_CASES,
    E5_GOLDEN_CASES,
)


def _normalized(rows):
    return [
        {
            "record_id": row.record_id,
            "category": row.category,
            "output_key": row.output_key,
            "quantity": row.quantity,
            "unit_price": row.unit_price,
            "value": row.value,
        }
        for row in rows
    ]


@pytest.mark.parametrize("definition,cases", [(E1_PROFILE, E1_GOLDEN_CASES), (E5_PROFILE, E5_GOLDEN_CASES)])
def test_e1_e5_declarative_profiles_match_immutable_golden_contracts(definition, cases):
    planner = DatabaseDrivenSionPlanner()
    for case in cases:
        records = [
            {"record_id": key, "category": category, "quantity": quantity}
            for key, category, quantity in case["items"]
        ]
        result = planner.execute(
            definition,
            records,
            case["balance_cif"],
            options=case.get("options"),
        )
        actual = _normalized(result.rows)
        assert len(actual) == len(case["lines"]), case["name"]
        for row, expected in zip(actual, case["lines"], strict=True):
            key, category, output, quantity, rate, value = expected
            assert row == {
                "record_id": key,
                "category": category,
                "output_key": output,
                "quantity": Decimal(quantity),
                "unit_price": Decimal(rate),
                "value": Decimal(value),
            }, case["name"]
        assert result.remaining_cif == Decimal(case["remaining_cif"]), case["name"]
        if "special_validation_triggered" in case:
            assert result.metadata["special_validation_triggered"] is case["special_validation_triggered"]


@pytest.mark.parametrize("norm", ["E126", "E132", "A3627"])
def test_legacy_configuration_golden_datasets_are_executed_without_norm_branches(norm):
    planner = DatabaseDrivenSionPlanner()
    definition = LEGACY_PLANNER_CONFIGURATIONS[norm]
    for case in GOLDEN_CASES[norm]:
        result = planner.execute(definition, case["records"], case["balance_cif"])
        expected = case["expected"]
        assert len(result.rows) == len(expected["rows"]), case["name"]
        for actual, wanted in zip(result.rows, expected["rows"], strict=True):
            assert actual.output_key == wanted["output_key"]
            assert actual.quantity == Decimal(wanted["quantity"])
            assert actual.unit_price == Decimal(wanted["unit_price"])
            assert actual.value == Decimal(wanted["value"])
        assert result.remaining_cif == Decimal(expected["remaining_cif"]), case["name"]


def test_unsafe_or_unknown_formula_is_rejected_instead_of_evaluated():
    definition = {
        "actions": [{
            "stable_key": "PROFILE:ACTION:001",
            "priority": 1,
            "action_type": "ALLOCATE",
            "config": {
                "algorithm": "CONDITIONAL_BRANCH",
                "condition": {"left": "REMAINING_CIF", "operator": "LT", "right": {"operation": "PYTHON", "arguments": []}},
                "when_true": {"pipeline": "A"},
                "when_false": {"pipeline": "B"},
            },
        }],
    }
    with pytest.raises(InvalidPlannerConfiguration, match="Unsupported safe formula"):
        DatabaseDrivenSionPlanner().execute(definition, [], "1")


def test_source_contains_no_norm_dispatch_branch():
    import inspect

    source = inspect.getsource(DatabaseDrivenSionPlanner)
    for code in ("E1", "E5", "E126", "E132", "A3627"):
        assert f'== "{code}"' not in source
        assert f"== '{code}'" not in source
