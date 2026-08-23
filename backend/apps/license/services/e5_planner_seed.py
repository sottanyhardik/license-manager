"""Production-safe installation of the audited E5 declarative profile."""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.core.models import SionNormClassModel
from apps.license.models import SionPlanningProfile, SionPlanningRule
from apps.license.services.sion_planner_config.e1_e5 import E5_PROFILE
from apps.license.services.sion_planner_config.importer import import_profile_document


class E5ConfigurationConflict(RuntimeError):
    """A tenant has an E5 configuration which is not the audited canonical one."""


@dataclass(frozen=True)
class E5SeedResult:
    status: str
    profile: SionPlanningProfile | None


def _canonical_profile_matches(profile: SionPlanningProfile) -> bool:
    """Compare all persisted, active execution inputs without modifying them."""
    if (profile.stable_key, profile.strategy_type, profile.version, profile.config) != (
        E5_PROFILE["stable_key"], E5_PROFILE["strategy_type"], E5_PROFILE["version"], E5_PROFILE["config"],
    ):
        return False
    actions = list(profile.actions.filter(is_active=True).order_by("priority", "pk"))
    expected_actions = list(E5_PROFILE["actions"])
    if len(actions) != len(expected_actions):
        return False
    for actual, expected in zip(actions, expected_actions):
        expected_config = dict(expected["config"])
        if expected["action_type"] == "MATCH":
            expected_config.pop("rules", None)
            expected_config["rule_outputs"] = {
                f"E5:RULE:{priority:03d}": rule["category"]
                for priority, rule in enumerate(expected["config"]["rules"], start=1)
            }
        if (actual.stable_key, actual.action_type, actual.priority, actual.version, actual.config) != (
            expected["stable_key"], expected["action_type"], expected["priority"], E5_PROFILE["version"], expected_config,
        ):
            return False
    rules = list(SionPlanningRule.objects.filter(sion=profile.sion, is_active=True).order_by("priority", "pk"))
    expected_rules = next(action["config"]["rules"] for action in expected_actions if action["action_type"] == "MATCH")
    if len(rules) != len(expected_rules):
        return False
    for priority, (actual, expected) in enumerate(zip(rules, expected_rules), start=1):
        if (actual.stable_key, actual.execution_output, actual.expression, actual.priority) != (
            f"E5:RULE:{priority:03d}", expected["category"], expected["expression"], priority,
        ):
            return False
    mappings = list(profile.output_mappings.filter(is_active=True).order_by("priority", "pk"))
    return [(m.stable_key, m.priority, m.config) for m in mappings] == [
        (row["stable_key"], row["priority"], {"source": row["source"], "output_key": row["output_key"]})
        for row in E5_PROFILE["mappings"]
    ]


@transaction.atomic
def ensure_canonical_e5_configuration() -> E5SeedResult:
    """Install E5 once; never overwrite a configuration created by a user.

    A missing E5 master is normal on an empty database and is intentionally a
    no-op.  Multiple E5 master rows or any divergent profile/rules are explicit
    operational conflicts rather than guesses about which configuration wins.
    """
    sions = list(SionNormClassModel.objects.select_for_update().filter(norm_class__iexact="E5"))
    if not sions:
        return E5SeedResult("missing_sion", None)
    if len(sions) != 1:
        raise E5ConfigurationConflict("E5 configuration conflict: multiple canonical E5 SION rows exist.")
    sion = sions[0]
    profiles = list(SionPlanningProfile.objects.select_for_update().filter(sion=sion))
    rules_exist = SionPlanningRule.objects.select_for_update().filter(sion=sion).exists()
    if profiles or rules_exist:
        if len(profiles) == 1 and _canonical_profile_matches(profiles[0]):
            return E5SeedResult("preserved_equivalent", profiles[0])
        raise E5ConfigurationConflict(
            "E5 configuration conflict: existing E5 planner rows differ from the audited canonical profile; no rows were changed."
        )
    profile = import_profile_document(E5_PROFILE, activate=True)
    # Imported classifier rows are deliberately inactive during profile
    # reconciliation.  This is a first install with no competing E5 rows, so
    # activation is safe and makes the persisted profile executable.
    SionPlanningRule.objects.filter(sion=sion).update(is_active=True)
    return E5SeedResult("created", profile)
