"""Deterministic mapping of actual usage to canonical planning targets.

This module is intentionally configuration-driven.  It never examines product
names, aliases, SION codes, or historical plan rows to guess a split child.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.license.services.sion_rule_engine import evaluate_expression


@dataclass(frozen=True)
class TargetResolution:
    target_ids: tuple[int, ...]

    @property
    def is_unique(self) -> bool:
        return len(self.target_ids) == 1


def resolve_targets_for_source(source_item) -> TargetResolution:
    """Return all active configured targets that can legally own a source.

    A caller may auto-map only an exactly-one result.  Zero or multiple
    targets are deliberately not interpreted as a fallback/default target.
    """
    from apps.license.models import LicenseExportItemModel, SionPlanningRule

    sion_ids = list(
        LicenseExportItemModel.objects.filter(license_id=source_item.license_id)
        .exclude(norm_class_id__isnull=True)
        .values_list("norm_class_id", flat=True).distinct()
    )
    if len(sion_ids) != 1:
        return TargetResolution(())
    record = {
        "hs_code": source_item.hs_code.hs_code if source_item.hs_code_id else "",
        "description": source_item.description or "",
        "item_key": ", ".join(sorted(item.name for item in source_item.items.all())),
        "total_qty": source_item.quantity,
        "available_qty": source_item.available_quantity,
        "unit": source_item.unit or "",
        "serial_number": source_item.serial_number,
    }
    targets: set[int] = set()
    rules = SionPlanningRule.objects.filter(sion_id=sion_ids[0], is_active=True).prefetch_related(
        "unit_value_rows", "percentage_rows"
    )
    for rule in rules:
        if not evaluate_expression(rule.expression or {}, record):
            continue
        def legitimate(item):
            # The M2M is the canonical norm membership.  The FK fallback is
            # only transitional while old master writers are being migrated.
            return item and (
                item.norms.filter(pk=rule.sion_id).exists()
                or item.sion_norm_class_id == rule.sion_id
            )
        if (rule.strategy or "STANDARD") == "SPLIT_BY_PERCENT":
            targets.update(row.import_item_id for row in rule.percentage_rows.select_related("import_item") if legitimate(row.import_item))
        elif (rule.strategy or "STANDARD") == "SPLIT_BY_UNIT_VALUE":
            targets.update(row.import_item_id for row in rule.unit_value_rows.select_related("import_item") if legitimate(row.import_item))
        elif rule.import_item_id and legitimate(rule.import_item):
            targets.add(rule.import_item_id)
    return TargetResolution(tuple(sorted(targets)))


def apply_deterministic_target_mapping(actual_usage, source_item) -> TargetResolution:
    """Populate a new usage record only when its target is unambiguous."""
    resolution = resolve_targets_for_source(source_item)
    if actual_usage.planning_target_item_id:
        if actual_usage.planning_target_item_id in resolution.target_ids:
            actual_usage.planning_mapping_status = "MAPPED_EXPLICIT"
            actual_usage.planning_mapping_source = "USER_SELECTED"
        else:
            # Keep the persisted value for audit, but never feed a target
            # absent from the active configuration into reconciliation.
            actual_usage.planning_mapping_status = "INVALID_PERSISTED_TARGET"
            actual_usage.planning_mapping_source = ""
    elif resolution.is_unique:
        actual_usage.planning_target_item_id = resolution.target_ids[0]
        actual_usage.planning_mapping_status = "MAPPED_DETERMINISTIC"
        actual_usage.planning_mapping_source = "UNIQUE_TARGET"
    elif resolution.target_ids:
        actual_usage.planning_mapping_status = "UNMAPPED_AMBIGUOUS"
        actual_usage.planning_mapping_source = ""
    else:
        actual_usage.planning_mapping_status = "UNMAPPED_NO_TARGET"
        actual_usage.planning_mapping_source = ""
    return resolution


def validate_explicit_target(source_item, target_id: int) -> TargetResolution:
    """Validate a user-selected target against this source's current rules.

    A foreign key alone is not proof of legitimacy: a source can have several
    configured split targets, but it must never be mapped to a target from a
    different rule/SION.  Keeping this in the domain service makes BOE and
    unlinked-allotment writes obey exactly the same contract.
    """
    resolution = resolve_targets_for_source(source_item)
    if int(target_id) not in resolution.target_ids:
        raise ValueError("The selected planning target is not legitimate for this source item.")
    return resolution
