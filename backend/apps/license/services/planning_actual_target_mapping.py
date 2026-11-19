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


def prime_target_cache(cache: dict, license_ids) -> dict:
    """Load the SION ids of many licences in one query into a ``resolve_targets_for_source`` cache."""
    from collections import defaultdict

    from apps.license.models import LicenseExportItemModel

    wanted = set(license_ids) - set(cache.setdefault("sion_ids", {}))
    found: dict[int, set[int]] = defaultdict(set)
    for license_id, sion_id in (LicenseExportItemModel.objects.filter(license_id__in=wanted).exclude(norm_class_id__isnull=True)
                                .values_list("license_id", "norm_class_id").distinct()):
        found[license_id].add(sion_id)
    for license_id in wanted:
        cache["sion_ids"][license_id] = sorted(found.get(license_id, ()))
    return cache


def resolve_targets_for_source(source_item, cache: dict | None = None) -> TargetResolution:
    """Return all active configured targets that can legally own a source.

    A caller may auto-map only an exactly-one result.  Zero or multiple
    targets are deliberately not interpreted as a fallback/default target.

    ``cache`` (optional, per request): a dict reused across calls so a batch of
    sources loads each licence's SION, each SION's active rules (with their
    targets and norm memberships) only once.  Same rules, same result — only
    the number of queries changes.
    """
    from apps.license.models import LicenseExportItemModel, SionPlanningRule

    cache = {} if cache is None else cache
    sions_by_licence = cache.setdefault("sion_ids", {})
    if source_item.license_id not in sions_by_licence:
        sions_by_licence[source_item.license_id] = list(
            LicenseExportItemModel.objects.filter(license_id=source_item.license_id)
            .exclude(norm_class_id__isnull=True)
            .values_list("norm_class_id", flat=True).distinct()
        )
    sion_ids = sions_by_licence[source_item.license_id]
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
    rules_by_sion = cache.setdefault("rules", {})
    if sion_ids[0] not in rules_by_sion:
        rules_by_sion[sion_ids[0]] = list(
            SionPlanningRule.objects.filter(sion_id=sion_ids[0], is_active=True)
            .select_related("import_item")
            .prefetch_related("import_item__norms", "unit_value_rows__import_item__norms", "percentage_rows__import_item__norms")
        )
    targets: set[int] = set()
    for rule in rules_by_sion[sion_ids[0]]:
        if not evaluate_expression(rule.expression or {}, record):
            continue
        def legitimate(item):
            # The M2M is the canonical norm membership.  The FK fallback is
            # only transitional while old master writers are being migrated.
            return item and (
                any(n.pk == rule.sion_id for n in item.norms.all())
                or item.sion_norm_class_id == rule.sion_id
            )
        if (rule.strategy or "STANDARD") == "SPLIT_BY_PERCENT":
            targets.update(row.import_item_id for row in rule.percentage_rows.all() if legitimate(row.import_item))
        elif (rule.strategy or "STANDARD") == "SPLIT_BY_UNIT_VALUE":
            targets.update(row.import_item_id for row in rule.unit_value_rows.all() if legitimate(row.import_item))
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


def validate_explicit_target(source_item, target_id: int, cache: dict | None = None) -> TargetResolution:
    """Validate a user-selected target against this source's current rules.

    A foreign key alone is not proof of legitimacy: a source can have several
    configured split targets, but it must never be mapped to a target from a
    different rule/SION.  Keeping this in the domain service makes BOE and
    unlinked-allotment writes obey exactly the same contract.
    """
    resolution = resolve_targets_for_source(source_item, cache)
    if int(target_id) not in resolution.target_ids:
        raise ValueError("The selected planning target is not legitimate for this source item.")
    return resolution
