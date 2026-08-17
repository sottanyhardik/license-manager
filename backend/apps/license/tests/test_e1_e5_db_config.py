"""Contract tests for audited E1/E5 DB migration documents and goldens."""

from decimal import Decimal

import pytest
from django.test import SimpleTestCase

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import (
    SionPlanningAction, SionPlanningOutputMapping, SionPlanningProfile,
    SionPlanningRule,
)
from apps.license.services.e1_plan import E1Item, plan_e1_items
from apps.license.services.e5_plan import E5Item, plan_e5_items
from apps.license.services.sion_planner_config.e1_e5 import LEGACY_PLANNER_CONFIGS, get_legacy_planner_config
from apps.license.services.sion_planner_config.golden_e1_e5 import E1_GOLDEN_CASES, E5_GOLDEN_CASES
from apps.license.services.sion_planner_config.importer import import_e1_e5_profiles


def _line_tuple(line):
    return tuple(str(getattr(line, field)) for field in ("key", "category", "step", "planned_qty", "unit_price", "planned_cif"))


class E1E5MigrationConfigTests(SimpleTestCase):
    def test_stable_keys_and_priorities_are_unique(self):
        for profile in LEGACY_PLANNER_CONFIGS:
            actions = profile["actions"]
            mappings = profile["mappings"]
            self.assertEqual(len({a["stable_key"] for a in actions}), len(actions))
            self.assertEqual(len({a["priority"] for a in actions}), len(actions))
            self.assertEqual(list(actions), sorted(actions, key=lambda action: action["priority"]))
            self.assertEqual(len({m["stable_key"] for m in mappings}), len(mappings))

    def test_config_documents_do_not_contain_float_values(self):
        def walk(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for child in value.values():
                    walk(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    walk(child)

        walk(LEGACY_PLANNER_CONFIGS)

    def test_config_getter_returns_isolated_copy(self):
        first = get_legacy_planner_config("e1")
        first["config"]["input_order"] = "MUTATED"
        self.assertEqual(get_legacy_planner_config("E1")["config"]["input_order"], "SERIAL_NUMBER_ASC")

    def test_e1_legacy_matches_literal_golden_rows(self):
        for case in E1_GOLDEN_CASES:
            with self.subTest(case=case["name"]):
                items = [E1Item(key, category, Decimal(qty)) for key, category, qty in case["items"]]
                result = plan_e1_items(items, Decimal(case["balance_cif"]))
                self.assertEqual(tuple(map(_line_tuple, result.lines)), case["lines"])
                self.assertEqual(Decimal(result.remaining_cif), Decimal(case["remaining_cif"]))

    def test_e5_legacy_matches_literal_golden_rows(self):
        for case in E5_GOLDEN_CASES:
            with self.subTest(case=case["name"]):
                items = [E5Item(key, category, Decimal(qty)) for key, category, qty in case["items"]]
                result = plan_e5_items(
                    items,
                    Decimal(case["balance_cif"]),
                    min_plan_qty=Decimal(case["options"]["min_plan_qty"]),
                    floor_qty=case["options"]["floor_qty"],
                )
                self.assertEqual(tuple(map(_line_tuple, result.lines)), case["lines"])
                self.assertEqual(Decimal(result.remaining_cif), Decimal(case["remaining_cif"]))
                self.assertEqual(result.special_validation_triggered, case["special_validation_triggered"])


@pytest.mark.django_db(transaction=True)
def test_e1_e5_import_is_idempotent_and_does_not_activate_cutover():
    head = HeadSIONNormsModel.objects.create(name="Legacy migration fixtures")
    for code in ("E1", "E5"):
        SionNormClassModel.objects.create(head_norm=head, norm_class=code, is_active=True)

    first = import_e1_e5_profiles()
    second = import_e1_e5_profiles()

    assert [profile.pk for profile in first] == [profile.pk for profile in second]
    assert SionPlanningProfile.objects.count() == 2
    assert SionPlanningAction.objects.count() == 19
    assert SionPlanningOutputMapping.objects.count() == 5
    assert SionPlanningRule.objects.count() == 17
    assert all(SionPlanningRule.objects.values_list("stable_key", flat=True))
    assert not SionPlanningRule.objects.filter(is_active=True).exists()
    assert not SionPlanningProfile.objects.filter(is_active=True).exists()
    assert list(first[0].actions.filter(is_active=True).values_list("priority", flat=True)) == list(range(1, 12))
    assert list(first[1].actions.filter(is_active=True).values_list("priority", flat=True)) == list(range(1, 9))
