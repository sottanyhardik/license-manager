"""Read-only configuration views for the /planning SION workspace.

Never writes and never executes planning.  It only gathers what already
exists so the UI can show it without hardcoding norm-specific values:

* DB planning rules (``SionPlanningRule``, every version incl. retired rows);
* DB planning profiles / actions / output mappings (``SionPlanningProfile``);
* the code registry (``sion_legacy_configurations.LEGACY_PLANNER_CONFIGURATIONS``)
  — the generic split engine's declared rules, actions and output mappings;
* the entitlement profile (``sion_planner_config.entitlement_profiles``) —
  product → entitlement mapping used by the entitlement planner;
* SION_PLANNING audit events written by ``SionPlanningRuleViewSet._audit``.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Count, Max, Q

from apps.core.models import ActivityLog, SionNormClassModel
from apps.license.models import SionPlanningProfile, SionPlanningRule
from apps.license.services.sion_legacy_configurations import LEGACY_PLANNER_CONFIGURATIONS
from apps.license.services.sion_planner_config.entitlement_profiles import ENTITLEMENT_PROFILES

AUDIT_LIMIT = 200


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _registry(norm: str) -> dict | None:
    return LEGACY_PLANNER_CONFIGURATIONS.get(str(norm or "").strip().upper())


def norm_summaries() -> list[dict[str, Any]]:
    """One row per norm that is active or carries any planning configuration."""
    configured = {k.upper() for k in LEGACY_PLANNER_CONFIGURATIONS} | {k.upper() for k in ENTITLEMENT_PROFILES}
    rule_sion_ids = SionPlanningRule.objects.values_list("sion_id", flat=True).distinct()
    profile_sion_ids = SionPlanningProfile.objects.values_list("sion_id", flat=True).distinct()
    sions = (
        SionNormClassModel.objects.filter(
            Q(is_active=True) | Q(norm_class__in=configured)
            | Q(pk__in=rule_sion_ids) | Q(pk__in=profile_sion_ids),
        )
        .annotate(
            active_rule_count=Count("planning_rules", filter=Q(planning_rules__is_active=True), distinct=True),
            split_rule_count=Count(
                "planning_rules",
                # Explicit split strategies only: NULL / STANDARD rules are single-item.
                filter=Q(planning_rules__is_active=True)
                & Q(planning_rules__strategy__in=("SPLIT_BY_PERCENT", "SPLIT_BY_UNIT_VALUE")),
                distinct=True,
            ),
            rule_row_count=Count("planning_rules", distinct=True),
            max_rule_version=Max("planning_rules__version"),
            last_rule_change=Max("planning_rules__modified_on"),
        )
        .order_by("norm_class")
    )
    active_profiles = {
        p.sion_id: p
        for p in SionPlanningProfile.objects.filter(is_active=True).annotate(
            active_action_count=Count("actions", filter=Q(actions__is_active=True)),
            active_split_count=Count("actions", filter=Q(actions__is_active=True, actions__action_type="SPLIT")),
        )
    }
    rows = []
    for sion in sions:
        norm = sion.norm_class.upper()
        registry = _registry(norm)
        profile = active_profiles.get(sion.pk)
        registry_actions = (registry or {}).get("actions", [])
        rows.append({
            "id": sion.pk,
            "norm_class": sion.norm_class,
            "description": sion.description,
            "is_active": sion.is_active,
            "active_rule_count": sion.active_rule_count,
            "split_rule_count": sion.split_rule_count,
            "rule_version_count": sion.rule_row_count,
            "max_rule_version": sion.max_rule_version,
            "last_updated": _iso(sion.last_rule_change),
            "profile_version": profile.version if profile else None,
            "profile_action_count": profile.active_action_count if profile else 0,
            "registry_rule_count": len((registry or {}).get("rules", [])),
            "registry_action_count": len(registry_actions),
            "registry_split_count": sum(1 for a in registry_actions if a.get("action_type") == "SPLIT"),
            "profile_split_count": profile.active_split_count if profile else 0,
            "has_entitlement_profile": norm in ENTITLEMENT_PROFILES,
        })
    return rows


def _rule_row(rule: SionPlanningRule) -> dict[str, Any]:
    return {
        "id": rule.pk,
        "stable_key": rule.stable_key,
        "name": rule.name,
        "version": rule.version,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "strategy": rule.strategy,
        "created_on": _iso(rule.created_on),
        "created_by_username": getattr(rule.created_by, "username", None),
        "modified_on": _iso(rule.modified_on),
        "modified_by_username": getattr(rule.modified_by, "username", None),
    }


def _profile_row(profile: SionPlanningProfile) -> dict[str, Any]:
    return {
        "id": profile.pk,
        "stable_key": profile.stable_key,
        "strategy_type": profile.strategy_type,
        "version": profile.version,
        "is_active": profile.is_active,
        "modified_on": _iso(profile.modified_on),
        "actions": [
            {"stable_key": a.stable_key, "action_type": a.action_type, "priority": a.priority,
             "version": a.version, "is_active": a.is_active, "config": a.config}
            for a in profile.actions.all().order_by("-is_active", "priority", "pk")
        ],
        "output_mappings": [
            {"stable_key": m.stable_key, "source_rule_id": m.source_rule_id,
             "source_rule_name": getattr(m.source_rule, "name", None),
             "output_item": getattr(m.output_item, "name", None), "rate": str(m.rate) if m.rate is not None else None,
             "unit": m.unit, "priority": m.priority, "is_active": m.is_active}
            for m in profile.output_mappings.select_related("source_rule", "output_item").order_by("-is_active", "priority", "pk")
        ],
    }


def _registry_view(norm: str) -> dict | None:
    registry = _registry(norm)
    if not registry:
        return None
    return {
        "source": "sion_legacy_configurations.LEGACY_PLANNER_CONFIGURATIONS",
        "rules": [
            {k: rule.get(k) for k in ("stable_key", "name", "priority", "expression", "max_unit_price", "unit", "output_key")}
            for rule in registry.get("rules", [])
        ],
        "actions": [
            {k: action.get(k) for k in ("stable_key", "priority", "action_type", "config")}
            for action in registry.get("actions", [])
        ],
        "mappings": list(registry.get("mappings", [])),
    }


def _entitlement_view(norm: str) -> dict | None:
    profile = ENTITLEMENT_PROFILES.get(norm)
    if not profile:
        return None
    return {
        "source": "sion_planner_config.entitlement_profiles",
        "groups": [
            {
                "key": g.get("key"), "label": g.get("label"),
                "entitlement_items": list(g.get("entitlement_items", [])),
                "source_rule": g.get("source_rule"), "split_action": g.get("split_action"),
                "products": [
                    {"name": p.get("name"), "entitlement": p.get("entitlement"), "aliases": list(p.get("aliases", []))}
                    for p in g.get("products", [])
                ],
            }
            for g in profile.get("groups", [])
        ],
        "entitlements": [
            {"item": item, **{k: v for k, v in spec.items()}}
            for item, spec in profile.get("entitlements", {}).items()
        ],
    }


def _audit(sion_id: int) -> list[dict[str, Any]]:
    logs = ActivityLog.objects.filter(module="SION_PLANNING", extra__sion_id=sion_id).order_by("-timestamp")[:AUDIT_LIMIT]
    return [
        {
            "id": log.pk, "timestamp": _iso(log.timestamp), "username": log.username or None,
            "event": (log.extra or {}).get("event") or log.description,
            "rule_id": (log.extra or {}).get("rule_id"), "rule_version": (log.extra or {}).get("rule_version"),
        }
        for log in logs
    ]


def norm_configuration(sion: SionNormClassModel) -> dict[str, Any]:
    norm = sion.norm_class.upper()
    rules = SionPlanningRule.objects.filter(sion=sion).select_related("created_by", "modified_by").order_by(
        "stable_key", "-version", "-pk",
    )
    profiles = SionPlanningProfile.objects.filter(sion=sion).prefetch_related("actions").order_by("-is_active", "-version")
    return {
        "sion": {"id": sion.pk, "norm_class": sion.norm_class, "description": sion.description, "is_active": sion.is_active},
        "rule_versions": [_rule_row(rule) for rule in rules],
        "profiles": [_profile_row(p) for p in profiles],
        "registry": _registry_view(norm),
        "entitlement_profile": _entitlement_view(norm),
        "audit": _audit(sion.pk),
    }
