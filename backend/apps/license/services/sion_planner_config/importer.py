"""Idempotent persistence adapter for audited legacy planner documents."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.core.constants import KG
from apps.license.models import (
    SionPlanningAction,
    SionPlanningOutputMapping,
    SionPlanningProfile,
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
    action_keys = []
    for spec in document["actions"]:
        action_keys.append(spec["stable_key"])
        SionPlanningAction.objects.update_or_create(
            profile=profile,
            stable_key=spec["stable_key"],
            defaults={
                "action_type": spec["action_type"],
                "priority": spec["priority"],
                "config": spec["config"],
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

