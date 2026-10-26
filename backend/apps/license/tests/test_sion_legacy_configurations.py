"""Migration contracts for audited E126/E132/A3627 DB configuration."""
from decimal import Decimal

import pytest

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import SionPlanningProfile, SionPlanningRule
from apps.license.services.e126_plan import plan_e126
from apps.license.services.e132_plan import plan_e132
from apps.license.services.sion_legacy_configurations import (
    GOLDEN_CASES,
    LEGACY_PLANNER_CONFIGURATIONS,
)
from apps.license.services.sion_legacy_importer import import_planner_definition


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


@pytest.mark.django_db
def test_importer_is_idempotent_and_never_activates_shadow_profile():
    head = HeadSIONNormsModel.objects.create(name="E126 migration head")
    SionNormClassModel.objects.create(head_norm=head, norm_class="E126")
    definition = LEGACY_PLANNER_CONFIGURATIONS["E126"]

    first = import_planner_definition("E126", definition)
    second = import_planner_definition("E126", definition)

    assert first["profile_created"] is True
    assert second["profile_created"] is False
    assert second["rules_created"] == second["actions_created"] == second["mappings_created"] == 0
    profile = SionPlanningProfile.objects.get(stable_key="E126:PROFILE")
    assert profile.is_active is False
    assert profile.actions.count() == len(definition["actions"])
    assert profile.output_mappings.count() == len(definition["mappings"])
    assert SionPlanningRule.objects.filter(sion=profile.sion, is_active=True).count() == 0


@pytest.mark.parametrize("description, hs_code, expected_output", [
    ("Rutile glass formers with borax", "32061110", "RUTILE"),
    ("Titanium Dioxide other than Rutile Grade, borax formers", "32061190", "TITANIUM"),
    ("Soda Ash in Soda Ash with rutile formers and borax", "28362000", "SODA_ASH"),
    ("RUTILE", "3206", "RUTILE"),
    ("Other Than Rutile Grade", "3206", "TITANIUM"),
    ("Other Than Rutile Titanium Dioxide", "3206", "TITANIUM"),
    ("Other Than Rutile Grade", "32061110", "TITANIUM"),
    ("RUTILE", "32061190", "RUTILE"),
    ("Titanium Dioxide Rutile Grade", "3206", "RUTILE"),
    ("Titanium Dioxide Other Than Rutile Grade", "3206", "TITANIUM"),
])
def test_a3627_first_match_rule_keeps_titanium_and_soda_ash_out_of_rutile(description, hs_code, expected_output):
    from apps.license.services.sion_rule_engine import evaluate_expression

    rules = sorted(LEGACY_PLANNER_CONFIGURATIONS["A3627"]["rules"], key=lambda row: row["priority"])
    context = {"description": description, "hs_code": hs_code}
    first_match = next(row["output_key"] for row in rules if evaluate_expression(row["expression"], context))

    assert first_match == expected_output


def _a3627_rule(output_key):
    from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS

    return next(row for row in LEGACY_PLANNER_CONFIGURATIONS["A3627"]["rules"] if row["output_key"] == output_key)


def _leaves(node, out):
    op = node.get("op")
    if op in {"and", "or", "not"}:
        for child in node.get("args", node.get("conditions", [])):
            _leaves(child, out)
    else:
        out.append((node.get("field"), op, str(node.get("value", "")).strip().casefold()))
    return out


@pytest.mark.parametrize("output_key", ["RUTILE", "TITANIUM"])
def test_a3627_rutile_and_titanium_expressions_pass_the_actual_validator(output_key):
    from apps.license.services.sion_rule_engine import normalize_expression, validate_expression

    expression = _a3627_rule(output_key)["expression"]
    validate_expression(expression)
    validate_expression(normalize_expression(expression))


@pytest.mark.parametrize("output_key", ["RUTILE", "TITANIUM"])
def test_a3627_rutile_and_titanium_expressions_have_no_duplicate_leaves(output_key):
    from apps.license.services.sion_rule_engine import normalize_expression

    leaves = _leaves(normalize_expression(_a3627_rule(output_key)["expression"]), [])

    assert len(leaves) == len(set(leaves))


@pytest.mark.parametrize("description, hs_code, expected", [
    ("Rutile glass formers with borax", "99999999", True),   # legacy BORAX branch preserved
    ("Rutile", "3206", True),                                  # HSN 3206 + RUTILE, no BORAX needed
    ("Rutile", "99999999", False),                             # RUTILE alone, no HSN/glass/borax
    ("Other Than Rutile Grade", "3206", False),                # never the RUTILE branch
    ("Other Than Rutile Titanium Dioxide", "3206", False),
    ("Soda Ash with rutile formers and borax", "3206", False), # soda ash exclusion still applies
])
def test_a3627_rutile_expression_branches(description, hs_code, expected):
    from apps.license.services.sion_rule_engine import evaluate_expression

    context = {"description": description, "hs_code": hs_code}

    assert evaluate_expression(_a3627_rule("RUTILE")["expression"], context) is expected


@pytest.mark.parametrize("description, hs_code, expected", [
    ("Titanium Dioxide other than Rutile Grade, borax formers", "99999999", True),
    ("Other Than Rutile Grade", "3206", True),
    ("Other Than Rutile Titanium Dioxide", "3206", True),
    ("Titanium Dioxide Other Than Rutile Grade", "32061110", True),
    ("3206 other than rutile", "99999999", True),
    ("RUTILE", "3206", False),
    ("Other Than Grade", "3206", False),  # no RUTILE phrase, no TiO2 wording: no TITANIUM
])
def test_a3627_titanium_expression_branches(description, hs_code, expected):
    from apps.license.services.sion_rule_engine import evaluate_expression

    context = {"description": description, "hs_code": hs_code}

    assert evaluate_expression(_a3627_rule("TITANIUM")["expression"], context) is expected


@pytest.mark.parametrize("description, hs_code", [
    ("RUTILE", "3206"),
    ("Other Than Rutile Grade", "3206"),
    ("Titanium Dioxide Other Than Rutile Grade", "32061110"),
    ("Rutile glass formers with borax", "99999999"),
])
def test_a3627_rutile_and_titanium_are_mutually_exclusive(description, hs_code):
    from apps.license.services.sion_rule_engine import evaluate_expression

    context = {"description": description, "hs_code": hs_code}
    rutile = evaluate_expression(_a3627_rule("RUTILE")["expression"], context)
    titanium = evaluate_expression(_a3627_rule("TITANIUM")["expression"], context)

    assert not (rutile and titanium)
