"""Mapping-change propagation (owner Part 15, decided 2026-11-19: both mappings, automatic re-planning).

APPROVE MAPPING → RECORD VERSION (``MappingChange``, plan lines + canonical CIF archived) → the mapping write fires the
existing re-plan signals (licence ``planning_source_revision`` advances = marked stale; ``planning.replan_license``
REPLACEs the generated plan in the background, with its own retry / idempotency) → this module derives PROPAGATING /
PUBLISHED / FAILED from that pipeline, captures the published result once, and reports before vs after.

Nothing here computes a quantity or CIF: plans come from the deterministic planning engine and balances from
``LicenseBalanceCalculator``. Superseded plan lines are preserved in the change's ``before`` archive (the engine
itself REPLACEs generated lines; changing that is out of scope — see the decision record).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseItemPlan, LicenseReplanRequest, MappingChange

OPEN = (MappingChange.PROPAGATING, MappingChange.FAILED)


def _s(value) -> str:
    return str(value if value is not None else Decimal("0"))


def licences_for_items(import_item_ids) -> list[int]:
    return sorted(set(LicenseImportItemsModel.objects.filter(pk__in=list(import_item_ids or [])).values_list("license_id", flat=True)))


def capture_state(license_ids: list[int]) -> dict:
    """Active plan lines + canonical actual CIF per licence (archive of what the re-plan will supersede)."""
    from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC

    ids = sorted(set(license_ids))
    if not ids:
        return {"licences": {}}
    boe, allot, avail = (LBC.calculate_debit_for_licenses(ids), LBC.calculate_allotment_for_licenses(ids),
                         LBC.calculate_financial_balance_for_licenses(ids))
    lines = defaultdict(list)
    for p in (LicenseItemPlan.objects.filter(license_id__in=ids, is_active=True, is_deleted=False, is_cancelled=False)
              .select_related("item_name").order_by("pk")):
        lines[p.license_id].append({
            "id": p.pk, "import_item_id": p.import_item_id, "item_name_id": p.item_name_id, "item_name": getattr(p.item_name, "name", None),
            "planned_quantity": _s(p.planned_quantity), "planned_cif_fc": _s(p.planned_cif_fc), "rule_id": p.planning_rule_id,
        })
    revisions = dict(LicenseDetailsModel.objects.filter(pk__in=ids).values_list("pk", "planning_source_revision"))
    return {"captured_on": timezone.now().isoformat(), "licences": {str(i): {
        "plan_lines": lines.get(i, []), "boe_cif": _s(boe.get(i)), "allotment_cif": _s(allot.get(i)), "available_cif": _s(avail.get(i)),
        "source_revision": revisions.get(i)} for i in ids}}


def record_change(*, kind: str, user=None, source_model: str = "", source_refs=None, import_item_ids=None, license_ids=None,
                  detail: dict | None = None, plan_impact: bool = True) -> MappingChange:
    """Record a mapping version BEFORE the mapping is written (so the archive holds the superseded plan)."""
    ids = sorted(set(license_ids or []) | set(licences_for_items(import_item_ids)))
    return MappingChange.objects.create(
        kind=kind, created_by=user, source_model=source_model, source_refs=list(source_refs or []), detail=detail or {},
        import_item_ids=sorted(set(import_item_ids or [])), license_ids=ids,
        before=capture_state(ids) if plan_impact else {}, status=MappingChange.PROPAGATING if plan_impact and ids else MappingChange.NO_PLANNING_IMPACT,
        completed_on=None if plan_impact and ids else timezone.now(),
    )


ACTIVE = (LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED, LicenseReplanRequest.STATUS_RUNNING,
          LicenseReplanRequest.STATUS_RETRY_PENDING)


def _latest_requests(change: MappingChange) -> dict[int, LicenseReplanRequest]:
    """Latest re-plan request per licence, whatever its date: a change made while a request was already active is
    coalesced INTO that older request (review 2026-11-19), so filtering by date would hide it."""
    latest: dict[int, LicenseReplanRequest] = {}
    for req in LicenseReplanRequest.objects.filter(license_id__in=change.license_ids).order_by("pk"):
        latest[req.license_id] = req
    return latest


def refresh(change: MappingChange) -> MappingChange:
    """Derive the propagation status from the re-plan pipeline; capture the published result exactly once."""
    if change.status not in OPEN:
        return change
    revisions = {pk: (src, applied) for pk, src, applied in LicenseDetailsModel.objects.filter(pk__in=change.license_ids)
                 .values_list("pk", "planning_source_revision", "planning_applied_revision")}
    stale = sorted(pk for pk, (src, applied) in revisions.items() if src > applied)
    latest = _latest_requests(change)
    failed = {pk: req for pk, req in latest.items() if pk in stale and req.status == LicenseReplanRequest.STATUS_FAILED}
    orphaned = [pk for pk in stale if pk not in failed and getattr(latest.get(pk), "status", None) not in ACTIVE]
    if orphaned:
        # Stale but nothing queued (request purged / signal missed): request it rather than wait forever.
        from apps.license.services.replan_requests import request_license_replan
        for license_id in orphaned:
            request_license_replan(license_id=license_id, reason="mapping_change_propagation", source_model="license.MappingChange",
                                   source_pk=change.pk, dispatch=True)
    if not stale:
        change.status, change.after, change.completed_on, change.error = MappingChange.PUBLISHED, capture_state(change.license_ids), timezone.now(), ""
        change.save(update_fields=["status", "after", "completed_on", "error"])
    elif failed:
        change.status = MappingChange.FAILED
        change.error = "; ".join(f"licence {pk}: {req.last_error_message or req.last_error or 'failed'}"[:300] for pk, req in failed.items())[:4000]
        change.save(update_fields=["status", "error"])
    elif change.status == MappingChange.FAILED:
        change.status = MappingChange.PROPAGATING  # a retry is running again
        change.save(update_fields=["status"])
    return change


def refresh_open(limit: int = 50) -> list[MappingChange]:
    return [refresh(c) for c in MappingChange.objects.filter(status__in=OPEN).order_by("pk")[:limit]]


def stale_licence_ids(license_ids) -> set[int]:
    """Licences whose plan is still being recalculated (source revision ahead of the applied one)."""
    return {pk for pk, src, applied in LicenseDetailsModel.objects.filter(pk__in=list(license_ids))
            .values_list("pk", "planning_source_revision", "planning_applied_revision") if src > applied}


def retry(change: MappingChange, *, user) -> MappingChange:
    """Re-request re-planning for licences still stale (coalesced + idempotent in the existing pipeline)."""
    from apps.license.services.replan_requests import request_license_replan

    if change.status not in OPEN:
        return change
    for license_id in sorted(stale_licence_ids(change.license_ids)):
        request_license_replan(license_id=license_id, reason="mapping_change_retry", source_model="license.MappingChange", source_pk=change.pk, dispatch=True)
    change.retries += 1
    change.status, change.error = MappingChange.PROPAGATING, ""
    change.save(update_fields=["retries", "status", "error"])
    return change


def _by_item(lines: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {"planned_quantity": Decimal("0"), "planned_cif_fc": Decimal("0"), "lines": 0})
    for line in lines:
        row = out[line.get("item_name") or "(no item)"]
        row["planned_quantity"] += Decimal(line["planned_quantity"])
        row["planned_cif_fc"] += Decimal(line["planned_cif_fc"])
        row["lines"] += 1
    return out


def impact(change: MappingChange) -> dict:
    """Before vs after per licence and debit item; actual utilisation and active planning reported separately."""
    refresh(change)
    after = change.after if change.status == MappingChange.PUBLISHED else capture_state(change.license_ids)
    stale = stale_licence_ids(change.license_ids)
    latest = _latest_requests(change)
    licences = dict(LicenseDetailsModel.objects.filter(pk__in=change.license_ids).values_list("pk", "license_number"))
    rows, totals = [], defaultdict(Decimal)
    for lid in change.license_ids:
        b = (change.before.get("licences") or {}).get(str(lid), {})
        a = (after.get("licences") or {}).get(str(lid), {})
        bi, ai = _by_item(b.get("plan_lines", [])), _by_item(a.get("plan_lines", []))
        items = []
        for name in sorted(set(bi) | set(ai)):
            x, y = bi.get(name, {}), ai.get(name, {})
            items.append({"item": name, "before_qty": _s(x.get("planned_quantity")), "after_qty": _s(y.get("planned_quantity")),
                          "before_cif": _s(x.get("planned_cif_fc")), "after_cif": _s(y.get("planned_cif_fc")),
                          "changed": (x.get("planned_quantity"), x.get("planned_cif_fc")) != (y.get("planned_quantity"), y.get("planned_cif_fc"))})
        for key, src in (("before_planned_cif", bi), ("after_planned_cif", ai)):
            totals[key] += sum((v["planned_cif_fc"] for v in src.values()), Decimal("0"))
        for field in ("boe_cif", "allotment_cif", "available_cif"):
            totals[f"before_{field}"] += Decimal(b.get(field) or "0")
            totals[f"after_{field}"] += Decimal(a.get(field) or "0")
        req = latest.get(lid)
        rows.append({
            "license_id": lid, "license_number": licences.get(lid), "stale": lid in stale, "items": items,
            "superseded_lines": len(b.get("plan_lines", [])), "active_lines": len(a.get("plan_lines", [])),
            "actual": {f: {"before": b.get(f), "after": a.get(f)} for f in ("boe_cif", "allotment_cif", "available_cif")},
            "replan": {"status": getattr(req, "status", None), "error": getattr(req, "last_error_message", "") or getattr(req, "last_error", "") or "",
                       "failures": ((getattr(req, "result", None) or {}).get("failures") or [])[:5]},
        })
    return {"change": serialise(change), "licences": rows, "totals": {k: _s(v) for k, v in totals.items()},
            "provisional": change.status != MappingChange.PUBLISHED}


def serialise(c: MappingChange) -> dict:
    return {"version": c.pk, "kind": c.kind, "status": c.status, "source_model": c.source_model, "source_refs": c.source_refs,
            "detail": c.detail, "import_items": len(c.import_item_ids), "licences": len(c.license_ids), "error": c.error,
            "retries": c.retries, "created_by": getattr(c.created_by, "username", None), "created_on": c.created_on.isoformat(),
            "completed_on": c.completed_on.isoformat() if c.completed_on else None}
