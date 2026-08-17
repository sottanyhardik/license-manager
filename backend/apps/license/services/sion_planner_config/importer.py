"""Idempotent persistence adapter for audited legacy planner documents."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.core.constants import KG
from apps.license.models import (
    SionPlanningAction,
    SionPlanningOutputMapping,
    SionPlanningProfile,
    SionPlanningRule,
)
from apps.license.services.sion_planner_config.e1_e5 import LEGACY_PLANNER_CONFIGS
from apps.license.services.sion_planning_profile import SionPlanningProfileService
from apps.core.models import SionNormClassModel


@transaction.atomic
def import_profile_document(document, *, activate=False):
    """Upsert one audited document using only immutable stable keys.

    Existing profiles are made inactive while their ordered children are
    reconciled.  Obsolete children are deactivated, never deleted, retaining
    provenance for historical runs.  Activation is an explicit final step so
    configuration import alone cannot cut over a legacy planner.
    """
    sion = SionNormClassModel.objects.select_for_update().get(
        norm_class__iexact=document["sion_code"],
    )
    profile, _ = SionPlanningProfile.objects.select_for_update().update_or_create(
        stable_key=document["stable_key"],
        defaults={
            "sion": sion,
            "strategy_type": document["strategy_type"],
            "config": document["config"],
            "version": document["version"],
            "is_active": False,
        },
    )

    # Avoid transient unique-priority collisions when an audited order changes.
    profile.actions.update(is_active=False)
    match_specs = next(
        (spec["config"].get("rules", ()) for spec in document["actions"] if spec["action_type"] == "MATCH"),
        (),
    )
    category_rates = {
        spec["config"].get("category"): spec["config"].get("rate")
        for spec in document["actions"]
        if spec["action_type"] == "ALLOCATE" and spec["config"].get("category")
    }
    category_rates.update({
        "MILK PRODUCTS": "6.50", "EGG ALBUMIN": "25.00",
        "EGG ALBUMIN / WPC": "25.00", "WHEAT FLOUR": "0.00",
        "PALM KERNEL OIL": "1.80", "RBD PALMOLEIN": "1.20",
        "REMAINING OILS": "5.00", "DIETARY FIBRE": "3.00",
    })
    rule_outputs = {}
    for index, spec in enumerate(match_specs, start=1):
        stable_key = f"{document['sion_code']}:RULE:{index:03d}"
        category = spec["category"]
        rule, _ = SionPlanningRule.objects.update_or_create(
            stable_key=stable_key,
            defaults={
                "sion": sion,
                "name": f"{index:03d} {category}",
                "version": document["version"],
                "expression": spec["expression"],
                "max_unit_price": Decimal(category_rates.get(category, "0")),
                "unit": KG,
                "priority": index,
                "is_active": False,
                "execution_output": category,
            },
        )
        rule_outputs[rule.stable_key] = category

    action_keys = []
    for spec in document["actions"]:
        action_keys.append(spec["stable_key"])
        config = dict(spec["config"])
        if spec["action_type"] == "MATCH":
            config.pop("rules", None)
            config["rule_outputs"] = rule_outputs
        SionPlanningAction.objects.update_or_create(
            profile=profile,
            stable_key=spec["stable_key"],
            defaults={
                "action_type": spec["action_type"],
                "priority": spec["priority"],
                "config": config,
                "version": document["version"],
                "is_active": True,
            },
        )
    profile.actions.exclude(stable_key__in=action_keys).update(is_active=False)

    profile.output_mappings.update(is_active=False)
    mapping_keys = []
    for spec in document["mappings"]:
        mapping_keys.append(spec["stable_key"])
        SionPlanningOutputMapping.objects.update_or_create(
            profile=profile,
            stable_key=spec["stable_key"],
            defaults={
                "source_rule": None,
                "output_item": None,
                "conversion_factor": Decimal("1"),
                "rate": None,
                "unit": KG,
                "priority": spec["priority"],
                "config": {"source": spec["source"], "output_key": spec["output_key"]},
                "version": document["version"],
                "is_active": True,
            },
        )
    profile.output_mappings.exclude(stable_key__in=mapping_keys).update(is_active=False)

    SionPlanningProfileService.validate(profile)
    return SionPlanningProfileService.activate(profile) if activate else profile


def import_e1_e5_profiles(*, activate=False):
    """Persist both profiles; safe to call repeatedly without duplicates."""
    return [import_profile_document(document, activate=activate) for document in LEGACY_PLANNER_CONFIGS]
