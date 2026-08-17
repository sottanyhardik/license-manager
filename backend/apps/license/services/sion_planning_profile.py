"""Validation and immutable snapshot support for DB-driven SION profiles."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.license.models import SionPlanningProfile


class SionPlanningProfileService:
    @staticmethod
    def validate(profile):
        profile.full_clean()
        actions = list(profile.actions.filter(is_active=True).order_by("priority", "pk"))
        if not actions:
            raise ValidationError("A planning profile requires at least one active action.")
        expected = list(range(1, len(actions) + 1))
        if [action.priority for action in actions] != expected:
            raise ValidationError("Active action priorities must be contiguous from 1.")
        for action in actions:
            action.full_clean()
        for mapping in profile.output_mappings.filter(is_active=True).select_related(
            "source_rule", "output_item",
        ):
            mapping.full_clean()
        return profile

    @classmethod
    @transaction.atomic
    def activate(cls, profile):
        profile = SionPlanningProfile.objects.select_for_update().get(pk=profile.pk)
        cls.validate(profile)
        SionPlanningProfile.objects.filter(
            sion_id=profile.sion_id, is_active=True,
        ).exclude(pk=profile.pk).update(is_active=False)
        profile.is_active = True
        profile.save(update_fields=("is_active", "modified_on"))
        return profile

    @staticmethod
    def snapshot(profile):
        """Return normalized JSON-safe execution configuration for audit runs."""
        return {
            "profile": {
                "uid": str(profile.uid),
                "stable_key": profile.stable_key,
                "strategy_type": profile.strategy_type,
                "version": profile.version,
                "config": profile.config,
            },
            "actions": [{
                "uid": str(action.uid),
                "stable_key": action.stable_key,
                "type": action.action_type,
                "priority": action.priority,
                "version": action.version,
                "config": action.config,
            } for action in profile.actions.filter(is_active=True).order_by("priority", "pk")],
            "output_mappings": [{
                "uid": str(mapping.uid),
                "stable_key": mapping.stable_key,
                "source_rule_id": mapping.source_rule_id,
                "output_item_id": mapping.output_item_id,
                "conversion_factor": str(mapping.conversion_factor),
                "rate": str(mapping.rate) if mapping.rate is not None else None,
                "unit": mapping.unit,
                "priority": mapping.priority,
                "version": mapping.version,
                "config": mapping.config,
            } for mapping in profile.output_mappings.filter(is_active=True).order_by("priority", "pk")],
        }
