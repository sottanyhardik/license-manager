"""Saved BOE Product Name / Allotment Item Name → Planning Target Item mappings (owner spec 2026-11-19, "BOE & allotment
item to planning target mapping").

Same principles as the licence import description mapping (``description_mapping``):

* one mapping per (source kind, strictly normalised name) — ``description_key`` (case / spacing / dash / quote only, no
  fuzzy or semantic merge); BOE names, allotment names and import descriptions are separate identities;
* the destination is the existing canonical planning target master — ``core.ItemNameModel``, the single
  ``planning_target_item`` FK of ``BillOfEntryModel`` / ``AllotmentModel`` (one target per record, so single select);
* applied (REPLACE) to every existing record with that exact name and automatically to future ones (post_save hooks);
* checked per record with the existing planning contract (``resolve_targets_for_source``: the target must be a
  legitimate planning target for every licence import item the record debits under its licence's SION rules):

  - legitimate for every debited item → ``MAPPED_EXPLICIT`` / source ``NAME_MAPPING`` (planning uses it);
  - not verifiable (no licence debit yet, or no planning rule configured for a debited item's licence) → the target is
    stored as the record's classification, ``verified=False``, and the planning status stays unmapped
    (``UNMAPPED_NO_TARGET``) so reconciliation never consumes an unverified target; re-checked when a debit is recorded
    and on every Save / Retry / bulk run (owner policy 2026-11-19: missing context is shown, not blocked);
  - a real conflict (a configured rule set that excludes the target, or the record already holds another valid target
    while the new one cannot be verified) → ``CONFLICT``: the record is left unchanged (a target this mapping had put
    there is restored to the record's pre-mapping values);
* versioned (``SourceNameMappingVersion``) and propagated through the existing mapping-change pipeline
  (``record_change`` + re-plan of each affected licence).

Classification only: names, quantities, CIF, debit rows, exchange rates and balances are never written — headers are
updated with a queryset ``update`` of the three planning-target fields (+ modified_on / modified_by), never ``save()``.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections import defaultdict

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.core.models import ItemNameModel
from apps.license.models import MappingChange, ProductIntelAuditEvent, SourceNameMapping, SourceNameMappingRecord, SourceNameMappingVersion
from apps.license.services.product_intelligence.description_filters import clean_filters, matches
from apps.license.services.product_intelligence.description_mapping import description_key, key_hash
from apps.license.services.product_matching import MatchValidationError

logger = logging.getLogger(__name__)

SOURCE = "NAME_MAPPING"
VERIFIED_STATUS = "MAPPED_EXPLICIT"
UNVERIFIED_STATUS = "UNMAPPED_NO_TARGET"  # reconciliation treats it as unmapped (planning_usage_reconciliation)
UNMAPPED = ("UNMAPPED_AMBIGUOUS", "UNMAPPED_NO_TARGET", "INVALID_PERSISTED_TARGET", "")
MAX_NAME = 255  # BillOfEntryModel.product_name / AllotmentModel.item_name max_length
MAX_BULK = 150
MAX_LICENCES = 2000
MAPPING_REQUIRED, APPLIED, AUTO, CONFLICT, PARTIAL = "MAPPING_REQUIRED", "APPLIED", "AUTO", "CONFLICT", "PARTIAL"


class Spec:
    def __init__(self, kind: str):
        from apps.allotment.models import AllotmentItems, AllotmentModel
        from apps.bill_of_entry.models import BillOfEntryModel, RowDetails

        if kind == "boe":
            self.Header, self.Child, self.fk, self.item_field, self.name_field = BillOfEntryModel, RowDetails, "bill_of_entry_id", "sr_number", "product_name"
            self.code, self.change_kind, self.label = SourceNameMapping.BOE, MappingChange.BOE_TARGET, "BOE"
        elif kind == "allotment":
            self.Header, self.Child, self.fk, self.item_field, self.name_field = AllotmentModel, AllotmentItems, "allotment_id", "item", "item_name"
            self.code, self.change_kind, self.label = SourceNameMapping.ALLOTMENT, MappingChange.ALLOTMENT_TARGET, "Allotment"
        else:
            raise MatchValidationError("Unknown mapping source")
        self.kind = kind


def validate_target(target_id) -> ItemNameModel:
    if not isinstance(target_id, int) or isinstance(target_id, bool) or target_id <= 0:
        raise MatchValidationError("Select one Planning Target Item")
    target = ItemNameModel.objects.filter(pk=target_id, is_active=True).first()
    if target is None:
        raise MatchValidationError("Choose an existing, active Planning Target Item (create a missing one in Masters → Item Names first)")
    return target


# --- records + verification ---------------------------------------------------------------------------------------

def _records_for(spec: Spec, key: str, *, lock: bool = False, raw_names=None) -> list:
    """Every header whose name has exactly this key (``raw_names`` re-checked against the key, never trusted)."""
    if raw_names is None:
        raw_names = spec.Header.objects.exclude(**{spec.name_field: ""}).values_list(spec.name_field, flat=True).distinct()
    hits = [n for n in raw_names if n and description_key(n) == key]
    qs = spec.Header.objects.filter(**{f"{spec.name_field}__in": hits})
    if lock:
        list(qs.select_for_update(of=("self",)).order_by("pk").values_list("pk", flat=True))
    return list(qs.only("pk", spec.name_field, "planning_target_item_id", "planning_mapping_status", "planning_mapping_source").order_by("pk"))


def _holds_other_valid(record, existing) -> bool:
    """The record holds a planning target in a mapped status that this name mapping did not write (form / alias /
    deterministic) — same id or not. An unverifiable mapping never downgrades it."""
    ours = existing is not None and record.planning_mapping_source == SOURCE
    return bool(record.planning_target_item_id) and not ours and (record.planning_mapping_status or "") not in UNMAPPED


def _verdict(record, target: ItemNameModel, debited: list, existing, memo: dict, resolver_cache: dict) -> tuple[str, str]:
    """→ ("ok" | "unverified" | "kept" | "conflict", reason / note). "kept": the record already holds this target in a valid status
    but it cannot be verified — left exactly as it is (not a conflict)."""
    from apps.license.services.planning_actual_target_mapping import resolve_targets_for_source

    if not debited:
        if _holds_other_valid(record, existing) and record.planning_target_item_id == target.pk:
            return "kept", "Not verified: the record already holds this planning target (no licence debit yet) — kept as it is"
        if _holds_other_valid(record, existing):
            return "conflict", (f"Record already has a valid planning target (#{record.planning_target_item_id}); {target.name} cannot be "
                                "verified yet (no licence debit) — the existing target is kept")
        return "unverified", "Not verified: no licence debit recorded yet — checked when one is recorded"
    unconfigured = []
    for item in debited:
        if item.pk not in memo:
            memo[item.pk] = set(resolve_targets_for_source(item, resolver_cache).target_ids)
        legit = memo[item.pk]
        number = item.license.license_number if item.license_id else "?"
        if legit and target.pk not in legit:
            return "conflict", (f"{target.name} is not a legitimate planning target for import item #{item.pk} of licence {number} "
                                f"under its SION rules")
        if not legit:
            unconfigured.append(number)
    if unconfigured:
        if _holds_other_valid(record, existing) and record.planning_target_item_id == target.pk:
            return "kept", (f"Not verified: the record already holds this planning target (no planning rule for licence "
                            f"{', '.join(sorted(set(unconfigured))[:3])}) — kept as it is")
        if _holds_other_valid(record, existing):
            return "conflict", (f"Record already has a valid planning target (#{record.planning_target_item_id}); {target.name} cannot be "
                                f"verified (no planning rule for licence {', '.join(sorted(set(unconfigured))[:3])})")
        return "unverified", f"Not verified: no planning rule configured for licence {', '.join(sorted(set(unconfigured))[:3])} — planning keeps it unmapped"
    return "ok", ""


def _apply(spec: Spec, mapping: SourceNameMapping, records: list, *, user, status: str, change_detail: dict, plan_impact: bool = True,
           protect_existing: bool = False) -> dict:
    """Apply the mapping's target to the records (caller holds the transaction and the record locks).
    ``protect_existing`` (automatic runs): a record holding a valid target written elsewhere (record form, alias,
    deterministic) is skipped — never silently replaced; the row then shows as needing Retry. Explicit Save / Retry /
    bulk REPLACE it (owner decision "replace")."""
    from apps.license.services.planning_actual_target_mapping import prime_target_cache
    from apps.license.services.product_intelligence.item_name_mapping import _sources
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    target = mapping.target
    ids = [r.pk for r in records]
    debits = _sources(spec.kind, ids, lock=True) if ids else {}
    resolver_cache = prime_target_cache({}, {i.license_id for items in debits.values() for i in items})
    existing = {a.record_id: a for a in SourceNameMappingRecord.objects.filter(kind=spec.code, record_id__in=ids)}
    memo: dict[int, set[int]] = {}
    writes: dict[tuple, list[int]] = defaultdict(list)  # (target, status, source) → record ids
    rows, changed, conflicts, unverified, unchanged, applied, skipped, kept = [], [], [], 0, 0, 0, 0, 0
    for r in records:
        app = existing.get(r.pk)
        if protect_existing and _holds_other_valid(r, app) and r.planning_target_item_id != target.pk:
            skipped += 1
            continue
        state, note = _verdict(r, target, debits.get(r.pk, []), app, memo, resolver_cache)
        current = (r.planning_target_item_id, r.planning_mapping_status or "", r.planning_mapping_source or "")
        previous = (app.previous_target_id, app.previous_status, app.previous_source) if app else current
        if state == "conflict":
            ours = app is not None and r.planning_mapping_source == SOURCE
            wanted = previous if ours else current  # restore what this mapping replaced; never touch anything else
            conflicts.append((r, note))
        elif state == "kept":
            wanted = current  # same target already held in a valid status: never downgraded, never re-sourced
            kept += 1  # its own count: the record is not newly set to "Not verified"
        else:
            wanted = (target.pk, VERIFIED_STATUS if state == "ok" else UNVERIFIED_STATUS, SOURCE)
            unverified += state == "unverified"
        row_status = SourceNameMappingRecord.CONFLICT if state == "conflict" else status
        if (wanted == current and app is not None and app.mapping_id == mapping.pk and app.applied_version == mapping.version
                and (app.status == SourceNameMappingRecord.CONFLICT) == (state == "conflict")
                and app.verified == (state == "ok") and app.detail == note[:1000]):
            unchanged += 1  # idempotent / retry-safe (the record keeps its APPLIED / AUTO status)
            continue
        if wanted != current:
            writes[wanted].append(r.pk)
            changed.append({"id": r.pk, "previous_target": current[0], "previous_status": current[1], "previous_source": current[2],
                            "new_target": wanted[0], "new_status": wanted[1], "state": state,
                            "licence_ids": sorted({i.license_id for i in debits.get(r.pk, [])})})
        applied += state != "conflict"
        rows.append(SourceNameMappingRecord(kind=spec.code, record_id=r.pk, mapping=mapping, applied_version=mapping.version, status=row_status,
                                            verified=state == "ok", detail=note[:1000], previous_target_id=previous[0],
                                            previous_status=previous[1][:32], previous_source=previous[2][:32]))
    change = None
    licence_ids = sorted({lic for c in changed for lic in c["licence_ids"]})
    if changed:
        # One mapping version per call, recorded BEFORE any write (the archive holds the superseded plans).
        change = record_change(kind=spec.change_kind, user=user, source_model=spec.Header._meta.label, source_refs=[c["id"] for c in changed],
                               license_ids=licence_ids, plan_impact=plan_impact,
                               detail={**change_detail, "source": "name_mapping", "mapping": mapping.pk, "version": mapping.version, "target": target.pk,
                                       "records": [{k: c[k] for k in ("id", "previous_target", "previous_status", "new_target", "new_status")} for c in changed[:2000]]})
        now = timezone.now()
        for (target_id, planning_status, source), record_ids in writes.items():
            values = {"planning_target_item_id": target_id, "planning_mapping_status": planning_status, "planning_mapping_source": source, "modified_on": now}
            if user is not None:
                values["modified_by"] = user
            # Queryset update: no save() (money fields never recomputed) and no per-record signal (versioned once above).
            spec.Header.objects.filter(pk__in=record_ids).update(**values)
    if rows:
        SourceNameMappingRecord.objects.bulk_create(rows, update_conflicts=True, unique_fields=["kind", "record_id"], update_fields=[
            "mapping", "applied_version", "status", "verified", "detail", "previous_target_id", "previous_status", "previous_source", "applied_on"])
    for license_id in licence_ids:
        mark_license_replan_source_changed(license_id=license_id, reason="debit_target_changed", source_model="license.MappingChange",
                                           source_pk=change.pk if change else None)
    conflict_licences: dict[int, str] = {}
    for r, _ in conflicts:
        for item in debits.get(r.pk, []):
            conflict_licences[item.license_id] = item.license.license_number
    return {"applied": applied, "unchanged": unchanged, "conflicts": len(conflicts), "unverified": unverified, "skipped": skipped, "kept": kept,
            "mapping_change": change.pk if change else None,
            "conflict_details": [{"record_id": r.pk, "reason": note} for r, note in conflicts[:50]],
            "conflict_licences": [{"id": lic, "license_number": n} for lic, n in sorted(conflict_licences.items(), key=lambda kv: (kv[1] or "", kv[0]))]}


# --- save / retry / automatic ---------------------------------------------------------------------------------------

def serialise(m: SourceNameMapping) -> dict:
    return {"id": m.pk, "version": m.version, "name": m.name, "key": m.name_key, "target": {"item_id": m.target_id, "name": m.target.name}}


def save_mapping(*, kind: str, name: str, target_id, user, expected_version: int | None = None, require_version: bool = False) -> dict:
    """Create or REPLACE the mapping for this exact (normalised) name and apply it to every existing record with it."""
    if not isinstance(name, str) or len(name) > MAX_NAME:
        raise MatchValidationError(f"Names are at most {MAX_NAME} characters")
    key = description_key(name)
    if not key:
        raise MatchValidationError("A name is required")
    return save_for_key(kind=kind, key=key, name=name, target_id=target_id, user=user, expected_version=expected_version, require_version=require_version)


def save_for_key(*, kind: str, key: str, name: str, target_id, user, expected_version: int | None = None, require_version: bool = False,
                 raw_names=None, source: str = "row", batch: str = "", target: ItemNameModel | None = None) -> dict:
    spec = Spec(kind)
    target = target or validate_target(target_id)
    with transaction.atomic():
        mapping, created = SourceNameMapping.objects.select_for_update(no_key=True).get_or_create(
            kind=spec.code, key_hash=key_hash(key),
            defaults={"name_key": key, "name": name.strip()[:5000], "target": target, "created_by": user, "updated_by": user})
        previous = None if created else mapping.target_id
        if not created and require_version and expected_version is None:
            raise MatchValidationError("This name already has a mapping — reload it and edit that version")
        if not created and expected_version is not None and expected_version != mapping.version:
            raise MatchValidationError(f"This mapping was changed by someone else (now version {mapping.version}) — reload and try again")
        version = None
        if created or previous != target.pk or not mapping.is_active:
            if not created:
                mapping.version += 1
            mapping.target, mapping.is_active, mapping.updated_by = target, True, user
            mapping.save()
            action = SourceNameMappingVersion.CREATE if created else SourceNameMappingVersion.REPLACE
            version = SourceNameMappingVersion.objects.create(mapping=mapping, version=mapping.version, action=action, target_id_value=target.pk,
                                                              previous_target_id=previous, user=user)
        else:
            action = "UNCHANGED"
        records = _records_for(spec, key, lock=True, raw_names=raw_names)
        result = _apply(spec, mapping, records, user=user, status=SourceNameMappingRecord.APPLIED,
                        change_detail={"action": action, "previous_target": previous, "origin": source, **({"batch": batch} if batch else {})})
        if version is not None and result["mapping_change"]:
            version.mapping_change_id = result["mapping_change"]
            version.save(update_fields=["mapping_change"])
        ProductIntelAuditEvent.objects.create(action=f"{kind}_name_mapped", user=user, detail={
            "mapping": mapping.pk, "version": mapping.version, "key": key[:300], "action": action, "target": target.pk, "target_name": target.name,
            "previous_target": previous, "applied": result["applied"], "conflicts": result["conflicts"], "unverified": result["unverified"], "kept": result["kept"],
            "mapping_change": result["mapping_change"], "source": source, **({"batch": batch} if batch else {})})
    return {"mapping": serialise(mapping), "action": action, **result}


def reapply(kind: str, mapping_id: int, *, user) -> dict:
    spec = Spec(kind)
    with transaction.atomic():
        mapping = SourceNameMapping.objects.select_for_update(no_key=True).select_related("target").filter(pk=mapping_id, kind=spec.code, is_active=True).first()
        if mapping is None:
            raise MatchValidationError("Unknown mapping")
        result = _apply(spec, mapping, _records_for(spec, mapping.name_key, lock=True), user=user, status=SourceNameMappingRecord.APPLIED,
                        change_detail={"action": "REAPPLY"})
        ProductIntelAuditEvent.objects.create(action=f"{kind}_name_reapplied", user=user, detail={
            "mapping": mapping.pk, "version": mapping.version, "applied": result["applied"], "conflicts": result["conflicts"]})
    return {"mapping": serialise(mapping), **result}


def auto_apply(kind: str, record_id: int) -> str | None:
    """Future / re-named records and newly recorded debits: apply the exact-name saved mapping (status AUTO). Returns
    the record status, or None when there is no mapping (the name then shows as Mapping Required). Idempotent."""
    spec = Spec(kind)
    if not SourceNameMapping.objects.filter(kind=spec.code, is_active=True).exists():
        return None
    name = spec.Header.objects.filter(pk=record_id).values_list(spec.name_field, flat=True).first()
    key = description_key(name) if name else ""
    if not key:
        return None
    with transaction.atomic():
        # Same lock order as Save / Retry (mapping, then records) — never header-then-mapping (deadlock).
        mapping = (SourceNameMapping.objects.select_for_update(no_key=True).select_related("target")
                   .filter(kind=spec.code, key_hash=key_hash(key), is_active=True).first())
        if mapping is None:
            return None
        record = (spec.Header.objects.select_for_update(of=("self",)).filter(pk=record_id)
                  .only("pk", spec.name_field, "planning_target_item_id", "planning_mapping_status", "planning_mapping_source").first())
        if record is None or description_key(getattr(record, spec.name_field, "")) != key:
            return None  # renamed meanwhile — its own post_save schedules the new name
        app = SourceNameMappingRecord.objects.filter(kind=spec.code, record_id=record.pk).first()
        # A record a user mapped (APPLIED) keeps that status when it is re-checked automatically.
        status = app.status if app and app.mapping_id == mapping.pk and app.status == SourceNameMappingRecord.APPLIED else SourceNameMappingRecord.AUTO
        result = _apply(spec, mapping, [record], user=None, status=status, change_detail={"action": "AUTO", "record": record.pk}, plan_impact=False,
                        protect_existing=True)
    if result["skipped"]:
        return None
    return SourceNameMappingRecord.CONFLICT if result["conflicts"] else status


# --- listing ---------------------------------------------------------------------------------------------------------

def name_index(kind: str) -> dict[str, dict]:
    """strict key → {name, wordings, record_ids, refs (licence id → number), values} over every named header."""
    spec = Spec(kind)
    rows = list(spec.Header.objects.exclude(**{spec.name_field: ""}).values_list("pk", spec.name_field))
    refs: dict[int, dict[int, str]] = defaultdict(dict)
    for rid, lic, number in (spec.Child.objects.exclude(**{f"{spec.item_field}__isnull": True})
                             .values_list(spec.fk, f"{spec.item_field}__license_id", f"{spec.item_field}__license__license_number").distinct()):
        refs[rid][lic] = number
    keys: dict[str, str] = {}
    groups: dict[str, dict] = {}
    for pk, name in rows:
        if name not in keys:
            keys[name] = description_key(name)
        k = keys[name]
        if not k:
            continue
        g = groups.setdefault(k, {"key": k, "counts": defaultdict(int), "record_ids": [], "refs": {}})
        g["counts"][name] += 1
        g["record_ids"].append(pk)
        g["refs"].update(refs.get(pk, {}))
    for g in groups.values():
        g["wordings"] = sorted(g["counts"])
        g["name"] = max(g["counts"].items(), key=lambda kv: (kv[1], kv[0]))[0]
        g["values"] = {"description": g["wordings"], "hsn": [], "sion": []}
    return groups


def _refs(group: dict) -> list[dict]:
    return [{"id": lic, "license_number": n} for lic, n in sorted(group["refs"].items(), key=lambda kv: (kv[1] or "", kv[0]))]


def name_rows(kind: str, *, q: str = "", status: str = "", filters=None, index: dict | None = None) -> tuple[list[dict], dict, dict]:
    """One row per unique name: MAPPING_REQUIRED · APPLIED · AUTO · CONFLICT · PARTIAL (records not at the current version
    or whose target was changed elsewhere — Retry re-applies)."""
    spec = Spec(kind)
    groups = name_index(kind) if index is None else index
    mappings = {m.key_hash: m for m in SourceNameMapping.objects.filter(kind=spec.code, is_active=True).select_related("target")}
    apps = {a["record_id"]: a for a in SourceNameMappingRecord.objects.filter(kind=spec.code).values(
        "record_id", "mapping_id", "applied_version", "status", "verified", "detail")}
    targets = dict(spec.Header.objects.filter(pk__in=list(apps)).values_list("pk", "planning_target_item_id"))
    q_key = description_key(q) if q else ""
    out = []
    for k, g in groups.items():
        if q_key and q_key not in k:
            continue
        if filters and not matches(g["values"], filters):
            continue
        m = mappings.get(key_hash(k))
        counts = {"applied": 0, "auto": 0, "conflict": 0, "stale": 0, "unverified": 0}
        reasons, notes = [], []
        if m:
            for rid in g["record_ids"]:
                a = apps.get(rid)
                if not a or a["mapping_id"] != m.pk or a["applied_version"] != m.version:
                    counts["stale"] += 1
                elif a["status"] == SourceNameMappingRecord.CONFLICT:
                    counts["conflict"] += 1
                    reasons.append(a["detail"])
                elif targets.get(rid) != m.target_id:
                    counts["stale"] += 1  # target changed since (record form / another writer) — Retry re-applies
                else:
                    counts["auto" if a["status"] == SourceNameMappingRecord.AUTO else "applied"] += 1
                    if not a["verified"]:
                        counts["unverified"] += 1
                        notes.append(a["detail"])
        row_status = (MAPPING_REQUIRED if m is None else CONFLICT if counts["conflict"] else PARTIAL if counts["stale"]
                      else AUTO if counts["auto"] and not counts["applied"] else APPLIED)
        out.append({"key": k, "name": g["name"], "wordings": len(g["wordings"]), "records": len(g["record_ids"]),
                    "licence_count": len(g["refs"]), "status": row_status, "counts": counts,
                    "conflicts": list(dict.fromkeys(reasons))[:3], "notes": list(dict.fromkeys(notes))[:3],
                    "mapping": {"id": m.pk, "version": m.version, "target": {"item_id": m.target_id, "name": m.target.name}} if m else None})
    summary: dict[str, int] = defaultdict(int)
    for r in out:
        summary[r["status"]] += 1
    if status:
        out = [r for r in out if r["status"] == status]
    order = {MAPPING_REQUIRED: 0, CONFLICT: 1, PARTIAL: 2, AUTO: 3, APPLIED: 4}
    out.sort(key=lambda r: (order[r["status"]], -r["records"], r["key"]))
    return out, dict(summary), groups


def names(kind: str, *, q: str = "", status: str = "", offset: int = 0, limit: int = 50, filters=None) -> dict:
    offset, limit = max(0, int(offset)), max(1, min(int(limit), 100))
    out, summary, index = name_rows(kind, q=q, status=status, filters=filters)
    page = out[offset:offset + limit]
    for r in page:
        r["licences"] = _refs(index[r["key"]])
    return {"kind": kind, "rows": page, "total": len(out), "total_records": sum(r["records"] for r in out), "summary": summary,
            "offset": offset, "limit": limit}


# --- bulk ------------------------------------------------------------------------------------------------------------

def _fingerprint(keys: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(keys)).encode("utf-8")).hexdigest()


def resolve_targets(kind: str, *, mode: str, filters=None, keys=None, status: str = "", q: str = "") -> tuple[list[str], dict]:
    if mode == "filter":
        cleaned = clean_filters(filters)
        status, q = (status or "").strip().upper()[:20], (q or "").strip()[:200]
        if not (cleaned["conditions"] or status or q):
            raise MatchValidationError("Apply a filter (condition, status or search) before updating all matching names")
        rows, _, index = name_rows(kind, q=q, status=status, filters=cleaned)
        targets = [r["key"] for r in rows]
    elif mode == "keys":
        if not isinstance(keys, list) or not keys or not all(isinstance(k, str) and 0 < len(k) <= 1000 for k in keys):
            raise MatchValidationError("Select at least one name")
        index = name_index(kind)
        targets = [k for k in dict.fromkeys(keys) if k in index]
    else:
        raise MatchValidationError("mode must be 'filter' or 'keys'")
    return sorted(targets), index


def bulk_preview(kind: str, *, mode: str, filters=None, keys=None, status: str = "", q: str = "") -> dict:
    targets, index = resolve_targets(kind, mode=mode, filters=filters, keys=keys, status=status, q=q)
    refs: dict[int, str] = {}
    for k in targets:
        refs.update(index[k]["refs"])
    licences = [{"id": lic, "license_number": n} for lic, n in sorted(refs.items(), key=lambda kv: (kv[1] or "", kv[0]))]
    missing = sorted(set(keys or []) - set(targets)) if mode == "keys" else []
    return {"descriptions": len(targets), "records": sum(len(index[k]["record_ids"]) for k in targets), "licence_count": len(licences),
            "licences": licences[:MAX_LICENCES], "licences_truncated": len(licences) > MAX_LICENCES, "fingerprint": _fingerprint(targets),
            "sample": [index[k]["name"] for k in targets[:10]], "missing": missing[:50], "limit": MAX_BULK, "too_many": len(targets) > MAX_BULK}


def bulk_execute(kind: str, *, mode: str, target_id, user, fingerprint: str, filters=None, keys=None, status: str = "", q: str = "") -> dict:
    """Map every target name (its own mapping, own transaction) to one Planning Target Item. Refuses when the target set
    changed since the confirmed preview; one bulk run per source kind at a time."""
    target = validate_target(target_id)
    batch, lock = uuid.uuid4().hex, f"source_name_bulk_lock_v1_{kind}"
    if not cache.add(lock, batch, timeout=15 * 60):
        raise MatchValidationError("Another bulk update is running — try again when it has finished")
    succeeded, skipped, failed = [], [], []
    try:
        targets, index = resolve_targets(kind, mode=mode, filters=filters, keys=keys, status=status, q=q)
        if not targets:
            raise MatchValidationError("No names match — nothing was changed")
        if len(targets) > MAX_BULK:
            raise MatchValidationError(f"{len(targets)} names selected — bulk updates are limited to {MAX_BULK}; narrow the filter or select in batches")
        if not isinstance(fingerprint, str) or fingerprint != _fingerprint(targets):
            raise MatchValidationError("The matching names changed since you reviewed them — review the bulk update again")
        for key in targets:
            name = index[key]["name"]
            try:
                result = save_for_key(kind=kind, key=key, name=name, target_id=target.pk, target=target, user=user,
                                      raw_names=index[key]["wordings"], source="bulk", batch=batch)
            except MatchValidationError as exc:
                failed.append({"key": key, "description": name, "reason": str(exc)})
                continue
            except Exception:  # noqa: BLE001 — one name failing must not lose the report of the others
                logger.exception("Bulk %s name mapping failed for %r (batch %s)", kind, key, batch)
                failed.append({"key": key, "description": name, "reason": "Unexpected error — nothing was changed for this name; retry it"})
                continue
            entry = {"key": key, "description": name, "action": result["action"], "applied": result["applied"], "unchanged": result["unchanged"],
                     "conflicts": result["conflicts"], "unverified": result["unverified"], "kept": result["kept"], "conflict_licences": result["conflict_licences"]}
            (skipped if result["action"] == "UNCHANGED" and not result["applied"] else succeeded).append(entry)
    finally:
        if cache.get(lock) == batch:
            cache.delete(lock)
    missing = sorted(set(keys or []) - set(targets)) if mode == "keys" else []
    skipped += [{"key": k, "description": k, "reason": "no longer exists"} for k in missing]
    try:
        ProductIntelAuditEvent.objects.create(action=f"{kind}_name_bulk", user=user, detail={
            "batch": batch, "mode": mode, "filters": clean_filters(filters) if mode == "filter" else None, "status": status, "q": q,
            "fingerprint": fingerprint, "target": target.pk, "names": len(targets), "succeeded": len(succeeded), "skipped": len(skipped),
            "failed": [f["key"][:300] for f in failed][:200]})
    except Exception:  # noqa: BLE001 — every name already carries its own audit event (with this batch id)
        logger.exception("Bulk summary audit event failed (batch %s)", batch)
    return {"batch": batch, "succeeded": succeeded, "skipped": skipped, "failed": failed, "descriptions": len(targets),
            "records": sum(e["applied"] + e["unchanged"] + e["conflicts"] for e in succeeded + skipped if "applied" in e)}
