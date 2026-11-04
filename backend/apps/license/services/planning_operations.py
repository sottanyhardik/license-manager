"""
Read models and bulk-operation bookkeeping for the SION Planning workbench.

Everything here is derived from the canonical tables (SionPlanningRule rows,
LicenseReplanRequest ledger).  This module never calculates allocation,
quantity or CIF; plan arithmetic stays in SionPlanningExecutionService.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from django.db.models import Count, Max, Min, Q

from apps.license.models import LicenseReplanRequest, SionPlanningRule

_ACTIVE_STATUSES = (
    LicenseReplanRequest.STATUS_PENDING,
    LicenseReplanRequest.STATUS_QUEUED,
    LicenseReplanRequest.STATUS_RUNNING,
    LicenseReplanRequest.STATUS_RETRY_PENDING,
)

# Scalar rule fields compared between consecutive versions.  ``is_active`` is
# deliberately not diffed: every edit deactivates the prior row, so its stored
# flag always reflects the present, not the state when it was written.  Each
# version reports its own is_active instead.
_SCALAR_FIELDS = (
    "name", "expression", "max_unit_price", "unit", "priority",
    "execution_output", "import_item_id", "strategy", "percentage_constraint",
    "rule_type", "cif_restriction_percentage",
)


def _iso(value):
    return value.isoformat() if value else None


def _child_fingerprint(rule: SionPlanningRule) -> Dict[str, List[tuple]]:
    """Comparable snapshot of the rule's child rows (bands and percentage rows)."""
    unit_rows = sorted(
        (row.import_item_id, str(row.min_unit_price), str(row.max_unit_price),
         str(row.preferred_unit_price), str(row.cif_restriction_percentage), row.priority)
        for row in rule.unit_value_rows.all()
    )
    pct_rows = sorted(
        (row.import_item_id, str(row.percentage), str(row.unit_price),
         str(row.max_quantity), str(row.cif_restriction_percentage), row.priority)
        for row in rule.percentage_rows.all()
    )
    return {"unit_value_rows": unit_rows, "percentage_rows": pct_rows}


def _snapshot(rule: SionPlanningRule) -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    for field in _SCALAR_FIELDS:
        value = getattr(rule, field)
        snap[field] = str(value) if hasattr(value, "as_tuple") else value
    snap.update(_child_fingerprint(rule))
    return snap


def rule_version_chain(rule: SionPlanningRule) -> List[Dict[str, Any]]:
    """Every version of one logical rule, oldest first, with changed fields.

    Versions share a ``stable_key`` assigned at creation.  Legacy rows created
    before that assignment have no key and can only be chained by name, so a
    legacy rule that was renamed shows as a separate chain.
    """
    rows = SionPlanningRule.objects.filter(sion_id=rule.sion_id)
    if rule.stable_key:
        rows = rows.filter(stable_key=rule.stable_key)
    else:
        rows = rows.filter(stable_key__isnull=True, name=rule.name)
    rows = list(
        rows.select_related("created_by", "modified_by")
        .prefetch_related("unit_value_rows", "percentage_rows")
        .order_by("version", "pk")
    )
    chain: List[Dict[str, Any]] = []
    previous: Dict[str, Any] | None = None
    for row in rows:
        snap = _snapshot(row)
        if previous is None:
            changed: List[str] = []
        else:
            changed = [key for key in snap if snap[key] != previous.get(key)]
        chain.append({
            "id": row.pk,
            "version": row.version,
            "is_active": row.is_active,
            "name": row.name,
            "strategy": row.strategy,
            "priority": row.priority,
            "changed_fields": changed,
            "created_on": _iso(row.created_on),
            "created_by": getattr(row.created_by, "username", None),
            "modified_on": _iso(row.modified_on),
            "modified_by": getattr(row.modified_by, "username", None),
        })
        previous = snap
    return chain


def planning_dashboard(*, validator) -> Dict[str, Any]:
    """Operational KPIs for the workbench.

    ``validator`` is ``rule -> list[str]`` (the canonical serializer checks); it
    is injected so this module does not import the HTTP layer.
    """
    from apps.core.models import SionNormClassModel

    norms = list(
        SionNormClassModel.objects.filter(is_active=True)
        .only("pk", "norm_class", "description")
        .order_by("norm_class", "pk")
    )
    rules = list(
        SionPlanningRule.objects.select_related("modified_by", "sion", "import_item")
        .prefetch_related("unit_value_rows__import_item", "percentage_rows__import_item")
        .order_by("sion_id", "priority", "pk")
    )

    per_norm: Dict[int, Dict[str, Any]] = {
        norm.pk: {
            "sion_id": norm.pk,
            "norm_class": norm.norm_class,
            "description": norm.description or "",
            "active_rules": 0,
            "inactive_rules": 0,
            "max_rule_version": 0,
            "validation_errors": 0,
            "warnings": 0,
            "last_modified_on": None,
        }
        for norm in norms
    }
    total_errors = total_warnings = 0
    last_rule = None
    for rule in rules:
        if last_rule is None or (rule.modified_on and rule.modified_on > last_rule.modified_on):
            last_rule = rule
        entry = per_norm.get(rule.sion_id)
        if entry is None:
            continue
        entry["max_rule_version"] = max(entry["max_rule_version"], rule.version or 0)
        if rule.modified_on and (entry["last_modified_on"] is None or rule.modified_on.isoformat() > entry["last_modified_on"]):
            entry["last_modified_on"] = rule.modified_on.isoformat()
        if rule.is_active:
            entry["active_rules"] += 1
            errors = validator(rule)
            entry["validation_errors"] += len(errors)
            total_errors += len(errors)
            if _matches_everything(rule.expression):
                entry["warnings"] += 1
                total_warnings += 1
        else:
            entry["inactive_rules"] += 1

    jobs = LicenseReplanRequest.objects.aggregate(
        pending=Count("pk", filter=Q(status__in=_ACTIVE_STATUSES)),
        failed=Count("pk", filter=Q(status=LicenseReplanRequest.STATUS_FAILED)),
        last_success=Max("completed_at", filter=Q(status=LicenseReplanRequest.STATUS_SUCCEEDED)),
        last_requested=Max("requested_at"),
    )
    active_total = sum(entry["active_rules"] for entry in per_norm.values())
    inactive_total = sum(entry["inactive_rules"] for entry in per_norm.values())
    return {
        "totals": {
            "norms": len(norms),
            "norms_with_active_rules": sum(1 for e in per_norm.values() if e["active_rules"]),
            "active_rules": active_total,
            "inactive_rules": inactive_total,
            # The rule model has no draft state; reported as null, not zero,
            # so the UI cannot mistake "not modelled" for "none pending".
            "draft_rules": None,
            "validation_errors": total_errors,
            "warnings": total_warnings,
        },
        "last_rule_change": {
            "modified_on": _iso(last_rule.modified_on) if last_rule else None,
            "modified_by": getattr(getattr(last_rule, "modified_by", None), "username", None) if last_rule else None,
            "rule_id": last_rule.pk if last_rule else None,
        },
        "jobs": {
            "pending": jobs["pending"],
            "failed": jobs["failed"],
            "last_successful_execution": _iso(jobs["last_success"]),
            "last_requested": _iso(jobs["last_requested"]),
        },
        "norms": sorted(per_norm.values(), key=lambda entry: entry["norm_class"]),
    }


def _matches_everything(expression) -> bool:
    """An empty expression matches every import item: flag it as a warning."""
    if not isinstance(expression, dict) or not expression:
        return True
    if "field" in expression:
        return False
    return not expression.get("conditions")


def _failure_rows(row: LicenseReplanRequest) -> List[Dict[str, Any]]:
    """Individual failures for one ledger row (hard failure or per-norm failures)."""
    license_number = getattr(row.license, "license_number", None)
    base = {"request_id": row.pk, "license_id": row.license_id, "license_number": license_number}
    failures = (row.result or {}).get("failures") or []
    if row.status == LicenseReplanRequest.STATUS_FAILED and not failures:
        return [{
            **base, "sion_id": row.sion_id,
            "error_code": row.last_error_code or "FAILED",
            "error_message": row.last_error_message or row.last_error or "Replan failed.",
            "attempts": row.attempts,
        }]
    if row.status in (LicenseReplanRequest.STATUS_SUCCEEDED, LicenseReplanRequest.STATUS_FAILED):
        return [{
            **base, "sion_id": item.get("sion_id"),
            "error_code": item.get("error_code") or "FAILED",
            "error_message": item.get("error") or "Norm planning failed.",
            "attempts": row.attempts,
        } for item in failures]
    return []


def replan_batch_status(request_ids: Iterable[int]) -> Dict[str, Any]:
    """Honest aggregate for a set of replan requests.

    A batch is ``SUCCEEDED`` only when every requested record succeeded with no
    per-norm failures.  Any failed, partially failed or unknown record makes it
    ``PARTIAL_FAILURE`` (some succeeded) or ``FAILED`` (none succeeded).
    Superseded records are reported as ``skipped``: a newer request now owns
    that licence's work, so they are neither success nor failure.
    """
    ids = list(dict.fromkeys(int(pk) for pk in request_ids))
    rows = list(
        LicenseReplanRequest.objects.filter(pk__in=ids)
        .select_related("license", "initiated_by")
        .order_by("pk")
    )
    found = {row.pk for row in rows}
    unknown = [pk for pk in ids if pk not in found]

    counts = {"active": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    errors: List[Dict[str, Any]] = []
    partial = 0
    for row in rows:
        if row.status in _ACTIVE_STATUSES:
            counts["active"] += 1
        elif row.status == LicenseReplanRequest.STATUS_SUPERSEDED:
            counts["skipped"] += 1
        else:
            row_failures = _failure_rows(row)
            if row.status == LicenseReplanRequest.STATUS_FAILED or row_failures:
                counts["failed"] += 1
                if (row.result or {}).get("failures"):
                    partial += 1
                errors.extend(row_failures)
            elif row.status == LicenseReplanRequest.STATUS_SUCCEEDED:
                counts["succeeded"] += 1
    # Unknown ids are never reported as success.
    failed_total = counts["failed"] + len(unknown)

    if counts["active"]:
        state = "RUNNING"
    elif failed_total == 0:
        state = "SUCCEEDED"
    elif counts["succeeded"] == 0 and not any(row.status == LicenseReplanRequest.STATUS_SUCCEEDED for row in rows):
        state = "FAILED"
    else:
        state = "PARTIAL_FAILURE"

    started = [row.started_at for row in rows if row.started_at]
    completed = [row.completed_at for row in rows if row.completed_at]
    initiator = next((row.initiated_by.username for row in rows if row.initiated_by_id), None)
    return {
        "state": state,
        "requested": len(ids),
        "processed": len(rows) - counts["active"],
        "succeeded": counts["succeeded"],
        "failed": failed_total,
        "skipped": counts["skipped"],
        "active": counts["active"],
        "partial_failures": partial,
        "unknown_request_ids": unknown,
        "initiated_by": initiator,
        "started_at": _iso(min(started)) if started else None,
        "completed_at": _iso(max(completed)) if completed and state != "RUNNING" else None,
        "errors": errors,
        "request_ids": ids,
    }


def failed_request_licences(request_ids: Iterable[int]) -> Dict[str, Any]:
    """Which requests need a retry: hard failures and succeeded-with-norm-failures.

    Returns the licence/scope to requeue per failed row.  Rows that are still
    active or succeeded cleanly are reported as skipped, never retried.
    """
    ids = list(dict.fromkeys(int(pk) for pk in request_ids))
    rows = LicenseReplanRequest.objects.filter(pk__in=ids).select_related("license").order_by("pk")
    retry: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    seen_licences = set()
    for row in rows:
        needs_retry = row.status == LicenseReplanRequest.STATUS_FAILED or (
            row.status == LicenseReplanRequest.STATUS_SUCCEEDED and bool((row.result or {}).get("failures"))
        )
        if not needs_retry or row.license_id in seen_licences:
            reason = "already in progress" if row.status in _ACTIVE_STATUSES else "no failure to retry"
            if row.license_id in seen_licences:
                reason = "duplicate licence in this retry"
            skipped.append({"request_id": row.pk, "license_id": row.license_id, "reason": reason})
            continue
        seen_licences.add(row.license_id)
        retry.append({
            "request_id": row.pk,
            "license_id": row.license_id,
            "scope": row.scope,
            "sion_id": row.sion_id,
        })
    missing = [pk for pk in ids if pk not in {row.pk for row in rows}]
    return {"retry": retry, "skipped": skipped, "unknown_request_ids": missing}
