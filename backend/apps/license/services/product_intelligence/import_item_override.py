"""Row-level Item Name correction on Licence Detail -> Import Items (owner decision 2026-11-20).

* A correction is a **row override** (``ImportItemNameOverride``): it applies to that one import item only and is never
  reverted by saved description mappings (``description_mapping._apply`` skips overridden rows).
* One Item Name per row (or none = deliberately Not Mapped). Previous links are audited.
* ``LicenseImportItemsModel.items`` stays the source of truth. Classification only: quantity, CIF, debits and balances
  are never written. Every save is versioned (``record_change``) BEFORE a link is written and re-plans the licence.
* ``_conflict`` blocking reasons (Item Name not legitimate for the licence SION / outside the HSN chapters) refuse the
  whole save; a "Not verified" note is stored in the audit and shown, never blocked (owner HSN/SION policy).
"""
from __future__ import annotations

from collections import defaultdict

from django.db import transaction

from apps.core.models import ItemNameModel
from apps.license.models import (
    ImportItemDescriptionMapping, ImportItemNameOverride, LicenseImportItemsModel, MappingChange, ProductIntelAuditEvent,
)
from apps.license.services.product_intelligence import description_mapping as dm
from apps.license.services.product_intelligence import import_item_approval as ia
from apps.license.services.product_matching import MatchValidationError

MAX_EXPECTED = 50  # an import item's current links (Item Names) — bounded payload
MAX_CHANGES = 200
SOURCE = "licence_detail"
MAPPED, NOT_MAPPED, MULTIPLE, CONFLICT, CLEARED = "MAPPED", "NOT_MAPPED", "MULTIPLE", "CONFLICT", "CLEARED"
GLOBAL, RECORD = "global", "record"


class OverrideConcurrencyError(Exception):
    """The Item Names changed since the user loaded the row(s)."""

    def __init__(self, import_item_ids):
        self.import_item_ids = sorted(import_item_ids)
        super().__init__("These records changed since you loaded them — reload and try again: "
                         + ", ".join(str(i) for i in self.import_item_ids))


def _links(record) -> list[int]:
    return sorted(i.pk for i in record.items.all())


# --- read -------------------------------------------------------------------------------------------------------------

def rows_for_licence(license_id: int) -> list[dict]:
    """One row per import item of the licence (see the API contract). Bounded queries, no per-row queries."""
    records = list(LicenseImportItemsModel.objects.filter(license_id=license_id).select_related(
        "hs_code", "item_name_override", "item_name_override__updated_by", "description_mapping", "description_mapping__mapping",
    ).prefetch_related("items", "items__norms", "items__sion_norm_class", "description_mapping__mapping__items").order_by("serial_number", "pk"))
    sions = dm._licence_sions([license_id]).get(license_id, set())
    all_items = {i.pk: i for r in records for i in r.items.all()}
    # Global Description + HSN approvals of this licence's combinations: one query (+ bulk stats), never per row.
    combos = {r.pk: ia.combination(r) for r in records}
    found = {(a.key_hash, a.hsn_code): a for a in ia.A.objects.filter(
        key_hash__in={c[1] for c in combos.values() if c}, is_active=True).select_related("updated_by")} if any(combos.values()) else {}
    approval_of = {pk: found.get((c[1], c[2])) for pk, c in combos.items() if c}
    approval_stats = ia.stats_for(found.values())
    for i in ItemNameModel.objects.filter(pk__in={a.item_id for a in found.values() if a.item_id}).prefetch_related("norms").select_related("sion_norm_class"):
        all_items.setdefault(i.pk, i)
    legit = dm._legit_sions(all_items.values())
    chapters = dm._chapters(all_items, [r.pk for r in records]) if all_items else {}
    names = {pk: i.name for pk, i in all_items.items()}
    out = []
    for r in records:
        links = sorted(r.items.all(), key=lambda i: (i.name, i.pk))
        ov = getattr(r, "item_name_override", None)
        app = getattr(r, "description_mapping", None)
        mapping = app.mapping if app else None
        mapping_items = sorted(mapping.items.all(), key=lambda i: (i.name, i.pk)) if mapping else []
        link_ids = sorted(i.pk for i in links)
        note, conflict = "", False
        if links:
            wrong = [i.name for i in links if legit[i.pk] is not None and sions and not (legit[i.pk] & sions)]
            if wrong:
                conflict, note = True, f"{', '.join(wrong)} not legitimate for licence SION {', '.join(sorted(sions))}"
            else:
                reason, soft = dm._conflict(r, links, legit, chapters, {license_id: sions})
                note = reason or soft
        approval = approval_of.get(r.pk)
        if approval is not None and not ov and approval.item_id and link_ids != [approval.item_id]:
            # The approval could not be applied to this record: show why (blocking SION / HSN reason), never hide the mismatch.
            reason, soft = dm._conflict(r, [all_items[approval.item_id]], legit, chapters, {license_id: sions})
            conflict, note = (True, reason) if reason else (conflict, note or soft)
        elif app and approval is None and not ov and app.status == ImportItemDescriptionMapping.CONFLICT:
            conflict, note = True, app.detail or note
        if ov:
            source = "OVERRIDE"
        elif approval is not None:
            source = "APPROVAL"
        elif app and app.status != ImportItemDescriptionMapping.CONFLICT and link_ids == sorted(i.pk for i in mapping_items) and link_ids:
            source = "AUTO" if app.status == ImportItemDescriptionMapping.AUTO else "DESCRIPTION_MAPPING"
        elif app and app.status == ImportItemDescriptionMapping.CONFLICT:
            source = "DESCRIPTION_MAPPING"
        else:
            source = "OTHER" if links else None
        cleared = approval is not None and not approval.item_id and not links and not ov
        status = CONFLICT if conflict else CLEARED if cleared else MULTIPLE if len(links) > 1 else MAPPED if links else NOT_MAPPED
        out.append({
            "import_item_id": r.pk, "serial_number": r.serial_number, "description": r.description or "",
            "hs_code": r.hs_code.hs_code if r.hs_code_id else "", "unit": r.unit, "sion": sorted(sions),
            "items": [{"id": i.pk, "name": i.name} for i in links], "status": status, "source": source, "note": note,
            "overridden": ov is not None,
            "approval": {"id": approval.pk, "status": approval.status, "version": approval.version,
                         "item": {"id": approval.item_id, "name": all_items[approval.item_id].name} if approval.item_id else None,
                         "records": approval_stats[approval.pk]["records"], "licences": approval_stats[approval.pk]["licences"],
                         "updated_by": getattr(approval.updated_by, "username", None),
                         "updated_on": approval.updated_on.isoformat()} if approval is not None else None,
            "override": {
                "item_ids": ov.item_ids, "previous_item_ids": ov.previous_item_ids,
                "previous_items": [{"id": i, "name": names.get(i, "")} for i in ov.previous_item_ids],
                "updated_by": getattr(ov.updated_by, "username", None), "updated_on": ov.updated_on.isoformat(), "reason": ov.reason,
            } if ov else None,
            "description_mapping": {"id": mapping.pk, "version": mapping.version, "status": app.status,
                                    "items": [{"id": i.pk, "name": i.name} for i in mapping_items]} if mapping else None,
        })
    return out


def history(import_item_id: int, license_id: int | None = None) -> list[dict]:
    """Audit events for one record, newest first (previous / new Item Names resolved). Events carry their licence id, so
    the scan is limited to that licence's events (never the whole audit table)."""
    events = []
    qs = ProductIntelAuditEvent.objects.filter(action__in=("import_item_name_override", "import_item_name_override_reverted"))
    if license_id is None:
        license_id = LicenseImportItemsModel.objects.filter(pk=import_item_id).values_list("license_id", flat=True).first()
    qs = qs.filter(detail__license_id=license_id)
    for ev in qs.select_related("user").order_by("-created_on", "-pk"):
        for rec in (ev.detail or {}).get("records") or []:
            if rec.get("import_item_id") == import_item_id:
                events.append((ev, rec))
    ids = {i for _, rec in events for i in (rec.get("previous_item_ids") or []) + (rec.get("new_item_ids") or [])}
    names = dict(ItemNameModel.objects.filter(pk__in=ids).values_list("pk", "name")) if ids else {}
    return [{
        "id": ev.pk, "action": ev.action, "user": getattr(ev.user, "username", None), "time": ev.created_on.isoformat(),
        "previous_item_ids": rec.get("previous_item_ids") or [], "new_item_ids": rec.get("new_item_ids") or [],
        "previous_items": [{"id": i, "name": names.get(i, "")} for i in rec.get("previous_item_ids") or []],
        "new_items": [{"id": i, "name": names.get(i, "")} for i in rec.get("new_item_ids") or []],
        "note": rec.get("note", ""), "reason": (ev.detail or {}).get("reason", ""), "mapping_version": (ev.detail or {}).get("mapping_version"),
    } for ev, rec in events]


# --- write ------------------------------------------------------------------------------------------------------------

def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _clean_changes(changes) -> list[dict]:
    if not isinstance(changes, list) or not changes:
        raise MatchValidationError("Nothing to save")
    if len(changes) > MAX_CHANGES:
        raise MatchValidationError(f"At most {MAX_CHANGES} records per save")
    out, seen = [], set()
    for c in changes:
        if not isinstance(c, dict) or not _int(c.get("import_item_id")):
            raise MatchValidationError("Every change needs an import_item_id")
        item_id, expected = c.get("item_id"), c.get("expected_item_ids")
        if item_id is not None and not _int(item_id):
            raise MatchValidationError("item_id must be an Item Name id or null")
        if not isinstance(expected, list) or len(expected) > MAX_EXPECTED or not all(_int(i) for i in expected):
            raise MatchValidationError("expected_item_ids must be a list of Item Name ids")
        if c["import_item_id"] in seen:
            raise MatchValidationError(f"Record {c['import_item_id']} appears more than once")
        seen.add(c["import_item_id"])
        scope = c.get("scope", GLOBAL)
        if scope not in (GLOBAL, RECORD):
            raise MatchValidationError("scope must be 'global' or 'record'")
        ev = c.get("expected_approval_version")
        if ev is not None and not _int(ev):
            raise MatchValidationError("expected_approval_version must be a positive integer")
        out.append({"import_item_id": c["import_item_id"], "item_id": item_id, "expected": sorted(set(expected)), "scope": scope,
                    "expected_approval_version": ev})
    return out


def _lock(license_id: int, ids) -> dict:
    ids = list(ids)
    list(LicenseImportItemsModel.objects.select_for_update(of=("self",)).filter(pk__in=ids, license_id=license_id)
         .order_by("pk").values_list("pk", flat=True))
    records = {r.pk: r for r in LicenseImportItemsModel.objects.filter(pk__in=ids, license_id=license_id)
               .select_related("hs_code", "license").prefetch_related("items").order_by("pk")}
    if set(records) != set(ids):
        missing = sorted(set(ids) - set(records))
        raise MatchValidationError(f"Record(s) {', '.join(map(str, missing))} do not belong to this licence")
    return records


def save_overrides(*, license_id: int, changes, user, reason: str = "") -> dict:
    """All-or-nothing, idempotent. → {saved, unchanged, mapping_change, import_item_ids}."""
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    changes = _clean_changes(changes)
    reason = (reason or "").strip()[:1000]
    with transaction.atomic():
        records = _lock(license_id, [c["import_item_id"] for c in changes])
        overrides = {o.import_item_id: o for o in ImportItemNameOverride.objects.select_for_update().filter(import_item_id__in=list(records))}
        # Stale rows first: a user whose rows changed must learn that before any other validation message.
        stale = [c["import_item_id"] for c in changes if c["expected"] != _links(records[c["import_item_id"]])]
        if stale:
            raise OverrideConcurrencyError(stale)
        # Targets: existing, active Item Names only.
        wanted_ids = {c["item_id"] for c in changes if c["item_id"] is not None}
        targets = {i.pk: i for i in ItemNameModel.objects.prefetch_related("norms").select_related("sion_norm_class").filter(pk__in=wanted_ids, is_active=True)}
        if wanted_ids - set(targets):
            raise MatchValidationError("Choose existing, active Item Names (create a missing one in Masters → Item Names first)")
        legit = dm._legit_sions(targets.values())
        chapters = dm._chapters(targets, records) if targets else {}
        sions = dm._licence_sions([license_id])
        blocked, notes, work, unchanged = [], {}, [], 0
        for c in changes:
            r = records[c["import_item_id"]]
            wanted = [] if c["item_id"] is None else [c["item_id"]]
            if wanted:
                reason_block, notes[r.pk] = dm._conflict(r, [targets[wanted[0]]], legit, chapters, sions)
                if reason_block:
                    blocked.append(f"record {r.pk}: {reason_block}")
                    continue
            else:
                notes[r.pk] = ""
            ov = overrides.get(r.pk)
            if ov is not None and sorted(ov.item_ids) == wanted and c["expected"] == wanted:
                unchanged += 1
                continue
            work.append((r, c["expected"], wanted))
        if blocked:
            raise MatchValidationError("Nothing was saved — " + "; ".join(blocked[:10]))
        if not work:
            return {"saved": 0, "unchanged": unchanged, "mapping_change": None, "import_item_ids": []}
        ids = [r.pk for r, _, _ in work]
        change = record_change(kind=MappingChange.IMPORT_ITEM_OVERRIDE, user=user, source_model="license.ImportItemNameOverride",
                               source_refs=ids, import_item_ids=ids,
                               detail={"source": SOURCE, "reason": reason, "records": [
                                   {"import_item_id": r.pk, "previous": prev, "new": wanted} for r, prev, wanted in work]})
        audit = []
        for r, previous, wanted in work:
            if previous != wanted:
                r.items.set(wanted)
            ov = overrides.get(r.pk)
            if ov is None:
                ImportItemNameOverride.objects.create(import_item=r, item_ids=wanted, previous_item_ids=previous, reason=reason,
                                                      created_by=user, updated_by=user)
            else:
                ov.item_ids, ov.reason, ov.updated_by = wanted, reason, user
                ov.save(update_fields=["item_ids", "reason", "updated_by", "updated_on"])
            audit.append({"import_item_id": r.pk, "previous_item_ids": previous, "new_item_ids": wanted, "note": notes[r.pk], "source": SOURCE})
        ProductIntelAuditEvent.objects.create(action="import_item_name_override", user=user, detail={
            "license_id": license_id, "records": audit, "reason": reason, "mapping_version": change.pk})
        mark_license_replan_source_changed(license_id=license_id, reason="item_master_link_changed", source_model="license.MappingChange",
                                           source_pk=change.pk, dispatch=True)
    return {"saved": len(work), "unchanged": unchanged, "mapping_change": change.pk, "import_item_ids": ids}


def revert_overrides(*, license_id: int, import_item_ids, user) -> dict:
    """Remove the overrides. Records whose description has an active saved mapping get it applied (REPLACE, versioned);
    others keep their links. → {reverted, import_item_ids, reapplied}."""
    raw = import_item_ids if isinstance(import_item_ids, list) else []
    if not raw or len(raw) > MAX_CHANGES or not all(_int(i) for i in raw):
        raise MatchValidationError(f"Select between 1 and {MAX_CHANGES} records")
    ids = sorted(set(raw))
    with transaction.atomic():
        # Lock order = approval -> description mapping -> records (approve() / revoke() / consolidation order).
        descriptions = LicenseImportItemsModel.objects.filter(pk__in=ids, license_id=license_id).values_list("description", flat=True)
        hashes = sorted({dm.key_hash(k) for k in (dm.description_key(d) for d in descriptions) if k})
        ia.lock_approvals(hashes)
        list(dm.ImportDescriptionMapping.objects.select_for_update(no_key=True).filter(key_hash__in=hashes, is_active=True)
             .order_by("pk").values_list("pk", flat=True))
        records = _lock(license_id, ids)
        overrides = {o.import_item_id: o for o in ImportItemNameOverride.objects.select_for_update().filter(import_item_id__in=ids)}
        reverted = sorted(overrides)
        if not reverted:
            return {"reverted": 0, "import_item_ids": [], "reapplied": 0}
        before = {i: _links(records[i]) for i in reverted}
        ImportItemNameOverride.objects.filter(import_item_id__in=reverted).delete()
        by_hash = defaultdict(list)
        for i in reverted:
            k = dm.description_key(records[i].description)
            if k:
                by_hash[dm.key_hash(k)].append(records[i])
        reapplied, versions = 0, []
        # An active Description + HSN approval outranks the description mapping: it decides the reverted record first.
        reapplied += ia.apply_for_records([records[i] for i in reverted])["applied"]
        for mapping in dm.ImportDescriptionMapping.objects.select_for_update(no_key=True).filter(key_hash__in=list(by_hash), is_active=True).order_by("pk"):
            res = dm._apply(mapping, by_hash[mapping.key_hash], user=user, status=ImportItemDescriptionMapping.APPLIED,
                            change_detail={"action": "OVERRIDE_REVERT", "source": SOURCE})
            reapplied += res["applied"]
            if res["mapping_change"]:
                versions.append(res["mapping_change"])
        after = {r.pk: sorted(LicenseImportItemsModel.items.through.objects.filter(licenseimportitemsmodel_id=r.pk)
                              .values_list("itemnamemodel_id", flat=True)) for r in (records[i] for i in reverted)}
        ProductIntelAuditEvent.objects.create(action="import_item_name_override_reverted", user=user, detail={
            "license_id": license_id, "mapping_version": versions[0] if len(versions) == 1 else (versions or None), "records": [
                {"import_item_id": i, "previous_item_ids": before[i], "new_item_ids": after[i], "note": "", "source": SOURCE} for i in reverted]})
    return {"reverted": len(reverted), "import_item_ids": reverted, "reapplied": reapplied}


# --- global (Description + HSN) saves --------------------------------------------------------------------------------------

def _licence_records(license_id: int, ids) -> dict:
    ids = list(ids)
    records = {r.pk: r for r in LicenseImportItemsModel.objects.filter(pk__in=ids, license_id=license_id).select_related("hs_code", "license")}
    if set(records) != set(ids):
        raise MatchValidationError(f"Record(s) {', '.join(map(str, sorted(set(ids) - set(records))))} do not belong to this licence")
    return records


def _combination_or_400(record) -> tuple[str, str, str]:
    combo = ia.combination(record)
    if combo is None:
        raise MatchValidationError(f"Record {record.pk} has no description — it cannot be mapped globally (use scope 'record')")
    return combo


def save_changes(*, license_id: int, changes, user, reason: str = "") -> dict:
    """Licence Detail save. ``scope`` per change: ``global`` (default) = approve the row's Description + HSN for every matching
    record in every licence; ``record`` = the one-record override. One transaction for the whole request (all-or-nothing).
    Order: global approvals (approval row then records, sorted by combination), then record overrides — so a request can never
    lock against a concurrent approval. → ``save_overrides`` keys plus ``propagation`` (one entry per global change)."""
    cleaned = _clean_changes(changes)
    raw_by_id = {c["import_item_id"]: c for c in changes}
    with transaction.atomic():
        records = _licence_records(license_id, [c["import_item_id"] for c in cleaned])
        global_changes = [c for c in cleaned if c["scope"] == GLOBAL]
        record_changes = [c for c in cleaned if c["scope"] == RECORD]
        combos = {c["import_item_id"]: _combination_or_400(records[c["import_item_id"]]) for c in global_changes}
        seen: dict[tuple, int] = {}
        for pk, (_key, kh, hsn) in combos.items():
            if (kh, hsn) in seen:
                raise MatchValidationError(f"Records {seen[(kh, hsn)]} and {pk} are the same Description + HSN — send one change for it")
            seen[(kh, hsn)] = pk
        for c in record_changes:
            combo = ia.combination(records[c["import_item_id"]])
            if combo and (combo[1], combo[2]) in seen:
                raise MatchValidationError(f"Record {c['import_item_id']} shares its Description + HSN with a global change in this request — save them separately")
        # Pre-lock every existing approval row (active or not) of the request's combinations in pk order — approve() then finds them
        # already held, so the (key_hash, hsn) processing order below can never invert the pk lock order of a concurrent writer.
        if combos:
            list(ia.A.objects.select_for_update(no_key=True).filter(key_hash__in={v[1] for v in combos.values()}).order_by("pk")
                 .values_list("pk", flat=True))
        propagation, saved, unchanged, changes_made, ids = [], 0, 0, [], []
        for c in sorted(global_changes, key=lambda c: (combos[c["import_item_id"]][1], combos[c["import_item_id"]][2])):
            r = records[c["import_item_id"]]
            _key, kh, hsn = combos[r.pk]
            res = ia.approve(description=r.description, hsn=hsn, item_id=c["item_id"], user=user, source=ia.A.LICENCE_DETAIL,
                             expected_version=c["expected_approval_version"], expected_links={r.pk: c["expected"]})
            if res["action"] == "UNCHANGED" and not res["applied"]:
                unchanged += 1
            else:
                saved += 1
                ids.append(r.pk)
            if res["mapping_change"]:
                changes_made.append(res["mapping_change"])
            propagation.append({
                "import_item_id": r.pk, "combination": {"description": r.description or "", "hsn_code": hsn}, "action": res["action"],
                "approval": res["approval"], "records": res["records"], "licences": res["licences"], "applied": res["applied"],
                "unchanged": res["unchanged"], "overridden": res["overridden"], "conflicts": res["conflicts"],
                "conflict_details": res["conflict_details"], "conflict_licences": res["conflict_licences"], "mapping_change": res["mapping_change"]})
        if record_changes:
            res = save_overrides(license_id=license_id, changes=[raw_by_id[c["import_item_id"]] for c in record_changes], user=user, reason=reason)
            saved += res["saved"]
            unchanged += res["unchanged"]
            ids += res["import_item_ids"]
            if res["mapping_change"]:
                changes_made.append(res["mapping_change"])
    return {"saved": saved, "unchanged": unchanged, "mapping_change": changes_made[0] if changes_made else None, "mapping_changes": changes_made,
            "import_item_ids": sorted(ids), "propagation": propagation}


def preview_changes(*, license_id: int, changes) -> list[dict]:
    """What a global save would touch, per change (read-only): records / licences / overridden / licence numbers / current Item Name sets."""
    if not isinstance(changes, list) or not changes:
        raise MatchValidationError("Nothing to preview")
    if len(changes) > MAX_CHANGES:
        raise MatchValidationError(f"At most {MAX_CHANGES} records per preview")
    ids = []
    for c in changes:
        if not isinstance(c, dict) or not _int(c.get("import_item_id")):
            raise MatchValidationError("Every change needs an import_item_id")
        if c.get("item_id") is not None and not _int(c.get("item_id")):
            raise MatchValidationError("item_id must be an Item Name id or null")
        ids.append(c["import_item_id"])
    wanted = {c["item_id"] for c in changes if c.get("item_id") is not None}
    if wanted and set(ItemNameModel.objects.filter(pk__in=wanted, is_active=True).values_list("pk", flat=True)) != wanted:
        raise MatchValidationError("Choose existing, active Item Names (create a missing one in Masters → Item Names first)")
    records = _licence_records(license_id, ids)
    out = []
    for c in changes:
        r = records[c["import_item_id"]]
        _key, _kh, hsn = _combination_or_400(r)
        out.append({"import_item_id": r.pk, "combination": {"description": r.description or "", "hsn_code": hsn},
                    **ia.preview(description=r.description, hsn=hsn)})
    return out
