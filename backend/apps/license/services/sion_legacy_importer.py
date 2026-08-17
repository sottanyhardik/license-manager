"""Idempotent persistence adapter for audited legacy planner definitions."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import (
    SionPlanningAction,
    SionPlanningOutputMapping,
    SionPlanningProfile,
    SionPlanningRule,
)


@transaction.atomic
def import_planner_definition(norm_code: str, definition: dict, *, user=None) -> dict:
    """Upsert one audited definition without activating it.

    Stable profile/action/mapping keys are the write identity.  The pre-existing
    rule schema has no stable-key column, so migrated rules use their immutable
    audited name + version identity; their separate stable key is retained in
    each output mapping's config until the canonical rule model gains that
    field.  This importer never deletes rows or activates a profile.
    """
    sion = SionNormClassModel.objects.select_for_update().get(norm_class__iexact=norm_code)
    profile_data = definition["profile"]
    profile, profile_created = SionPlanningProfile.objects.update_or_create(
        stable_key=profile_data["stable_key"],
        defaults={
            "sion": sion,
            "strategy_type": profile_data["strategy_type"],
            "config": profile_data["config"],
            "version": profile_data["version"],
            "is_active": False,
            **({"created_by": user, "modified_by": user} if user else {}),
        },
    )

    rules_by_output = {}
    rule_created_count = 0
    for data in definition["rules"]:
        rule, created = SionPlanningRule.objects.update_or_create(
            sion=sion, name=data["name"], version=1,
            defaults={
                "expression": data["expression"],
                "max_unit_price": Decimal(data["max_unit_price"]),
                "unit": data["unit"],
                "priority": data["priority"],
                # Shadow configuration must never enter production rule execution.
                "is_active": False,
                **({"created_by": user, "modified_by": user} if user else {}),
            },
        )
        rule_created_count += int(created)
        rules_by_output[data["output_key"]] = (rule, data["stable_key"])

    action_created_count = 0
    for data in definition["actions"]:
        _, created = SionPlanningAction.objects.update_or_create(
            profile=profile, stable_key=data["stable_key"],
            defaults={
                "action_type": data["action_type"], "priority": data["priority"],
                "config": data["config"], "version": 1, "is_active": True,
                **({"created_by": user, "modified_by": user} if user else {}),
            },
        )
        action_created_count += int(created)

    mapping_created_count = 0
    for data in definition["mappings"]:
        output_item, _ = ItemNameModel.objects.get_or_create(
            name=data["output_name"], defaults={"sion_norm_class": sion},
        )
        source = rules_by_output.get(data["source_key"])
        source_rule, source_rule_key = source if source else (None, None)
        _, created = SionPlanningOutputMapping.objects.update_or_create(
            profile=profile, stable_key=data["stable_key"],
            defaults={
                "source_rule": source_rule, "output_item": output_item,
                "conversion_factor": Decimal(data["conversion_factor"]),
                "rate": Decimal(data["rate"]) if data["rate"] is not None else None,
                "unit": data["unit"], "priority": data["priority"],
                "config": {
                    "source_key": data["source_key"], "output_name": data["output_name"],
                    "source_rule_stable_key": source_rule_key,
                },
                "version": 1, "is_active": True,
                **({"created_by": user, "modified_by": user} if user else {}),
            },
        )
        mapping_created_count += int(created)

    return {
        "norm": norm_code,
        "profile_created": profile_created,
        "rules_created": rule_created_count,
        "actions_created": action_created_count,
        "mappings_created": mapping_created_count,
        "profile_id": profile.pk,
    }
