from dataclasses import dataclass
from decimal import Decimal

from django.test import SimpleTestCase

from apps.license.services.e1_plan import E1Item, classify_e1_item, plan_e1_items
from apps.license.services.e5_plan import E5Item, classify_e5_item, plan_e5_items
from apps.license.services.sion_planner_config.e1_e5 import get_legacy_planner_config
from apps.license.services.sion_planning_execution import (
    PlannerConfigurationError, ResolvedPlannerConfiguration,
    SionPlanningExecutionService,
)


@dataclass(frozen=True)
class _Rule:
    stable_key: str
    expression: dict
    priority: int


def _configuration(code):
    document = get_legacy_planner_config(code)
    specs = next(action["config"]["rules"] for action in document["actions"] if action["action_type"] == "MATCH")
    rules = tuple(_Rule(f"{code}:RULE:{index:03d}", spec["expression"], index) for index, spec in enumerate(specs, 1))
    outputs = {rule.stable_key: spec["category"] for rule, spec in zip(rules, specs)}
    return ResolvedPlannerConfiguration(code, rules, outputs)


def _rows():
    return [
        {"record_id": "a", "item_key": "other confectionery", "hs_code": "080211", "description": "almond", "quantity": "100"},
        {"record_id": "b", "item_key": "dietary fibre", "hs_code": "2106", "description": "dietary fibre", "quantity": "70"},
        {"record_id": "c", "item_key": "milk", "hs_code": "0404", "description": "milk powder 0404", "quantity": "80"},
        {"record_id": "d", "item_key": "wheat flour", "hs_code": "11010000", "description": "wheat flour", "quantity": "60"},
    ]


class SionPlanningExecutionTests(SimpleTestCase):
    def test_e1_db_classification_preserves_legacy_waterfall_exactly(self):
        records = _rows()
        legacy_items = []
        for row in records:
            category = classify_e1_item(row["item_key"], row["hs_code"], row["description"])
            if category:
                legacy_items.append(E1Item(row["record_id"], category, Decimal(row["quantity"])))
        legacy = plan_e1_items(legacy_items, Decimal("1000"))
        bridged = SionPlanningExecutionService.execute(
            type("Sion", (), {"norm_class": "E1"})(), records, "1000",
            configuration=_configuration("E1"),
        )
        self.assertEqual(legacy, bridged)

    def test_e5_db_classification_preserves_legacy_waterfall_exactly(self):
        records = _rows()
        legacy_items = []
        for row in records:
            category = classify_e5_item(row["item_key"], row["hs_code"], row["description"])
            if category:
                legacy_items.append(E5Item(row["record_id"], category, Decimal(row["quantity"])))
        legacy = plan_e5_items(legacy_items, Decimal("1000"))
        bridged = SionPlanningExecutionService.execute(
            type("Sion", (), {"norm_class": "E5"})(), records, "1000",
            configuration=_configuration("E5"),
        )
        self.assertEqual(legacy, bridged)

    def test_db_rule_order_is_first_match_authority(self):
        config = _configuration("E5")
        reversed_config = ResolvedPlannerConfiguration(
            "E5", tuple(reversed(config.rules)), config.output_by_rule_key,
        )
        record = {"item_key": "wheat flour dietary fibre", "hs_code": "11010000", "description": "", "quantity": "60"}
        self.assertEqual(config.classify(record), "DIETARY FIBRE")
        self.assertEqual(reversed_config.classify(record), "WHEAT FLOUR")

    def test_rule_without_output_mapping_is_rejected(self):
        config = _configuration("E1")
        broken = ResolvedPlannerConfiguration("E1", config.rules, {})
        with self.assertRaisesRegex(PlannerConfigurationError, "no execution output mapping"):
            broken.classify(_rows()[0])

    def test_registry_has_no_dispatch_branches(self):
        self.assertEqual(set(SionPlanningExecutionService._registry), {"E1", "E5"})

