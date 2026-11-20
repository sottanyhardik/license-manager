"""Global Description + HSN -> Item Name approvals for licence import items (owner amendment 2026-11-20).

An approval (``ImportItemMappingApproval``) is keyed by ``(description_key, hsn_code)``: the strict description key
(``description_mapping.description_key``) plus the trimmed HSN code ("" = no HSN, its own value). It is applied with
REPLACE semantics to every import item (all licences) with that exact combination:

* ``USER_APPROVED``: one existing, active Item Name; ``USER_APPROVED_CLEAR``: deliberately no Item Name.
* Precedence, highest first: row override (``ImportItemNameOverride``, a one-record exception) > this approval > saved
  description-only mapping (``ImportDescriptionMapping``) > every automatic writer. Automatic writers consult
  ``protected_import_item_ids`` / ``approval_for`` and never touch a covered record.
* A record whose Item Name is blocked by ``description_mapping._conflict`` (SION / HSN chapter) is left unchanged and
  reported; a "Not verified" note never blocks (owner HSN/SION policy).
* Classification only: quantity, CIF, debits and balances are never written. ``record_change`` is called BEFORE the first
  link is written; every change is versioned (``ImportItemMappingApprovalVersion``), audited and re-plans each licence.
"""
from __future__ import annotations

from collections import defaultdict

from django.db import transaction
from django.db.models import CharField, Func, Q, Value

from apps.core.models import ItemNameModel
from apps.license.models import (
    ImportItemMappingApproval, ImportItemMappingApprovalVersion, ImportItemNameOverride, LicenseImportItemsModel, MappingChange,
    ProductIntelAuditEvent,
)
from apps.license.services.product_intelligence import description_mapping as dm
from apps.license.services.product_matching import MatchValidationError

class _HsnTrim(Func):
    """SQL twin of ``dm.norm_hsn``: BTRIM(code, HSN_WS) — strips exactly the characters Python strips."""

    function = "BTRIM"
    output_field = CharField()

    def __init__(self, expression):
        super().__init__(expression, Value(dm.HSN_WS))


A = ImportItemMappingApproval
V = ImportItemMappingApprovalVersion
MAX_HSN = 20
PREVIEW_LICENCES = 10
AUDIT_ACTION = "import_item_approval"
REFUSAL = "{n} record(s) have an approved Description + HSN mapping — revise it in Product Mapping → Approved"


class ApprovalConcurrencyError(Exception):
    """The approval changed since the user loaded it (HTTP 409)."""

    def __init__(self, version: int, approval_id: int | None = None, import_item_ids=None):
        self.version, self.approval_id, self.import_item_ids = version, approval_id, sorted(import_item_ids or [])
        super().__init__("These records changed since you loaded them — reload and try again: " + ", ".join(map(str, self.import_item_ids))
                         if self.import_item_ids else f"This approved mapping was changed by someone else (now version {version}) — reload and try again")


# --- identity ---------------------------------------------------------------------------------------------------------

def _hsn(record) -> str:
    return dm.norm_hsn(record.hs_code.hs_code if record.hs_code_id else "")


def combination(record) -> tuple[str, str, str] | None:
    """``(description_key, key_hash, hsn)`` of an import item, or None when its description is blank (never mappable)."""
    key = dm.description_key(record.description)
    if not key:
        return None
    return key, dm.key_hash(key), _hsn(record)


def clean_hsn(hsn) -> str:
    hsn = dm.norm_hsn(hsn)
    if len(hsn) > MAX_HSN:
        raise MatchValidationError(f"HSN codes are at most {MAX_HSN} characters")
    return hsn


def _identity(description, hsn) -> tuple[str, str, str]:
    if len(description or "") > dm.MAX_DESCRIPTION:
        raise MatchValidationError(f"Descriptions are at most {dm.MAX_DESCRIPTION} characters")
    key = dm.description_key(description)
    if not key:
        raise MatchValidationError("A description is required — a blank description cannot be mapped globally")
    return key, dm.key_hash(key), clean_hsn(hsn)


def _hsn_qs(hsn: str):
    qs = LicenseImportItemsModel.objects.exclude(description__isnull=True).exclude(description="").annotate(_hsn=_HsnTrim("hs_code__hs_code"))
    return qs.filter(Q(hs_code__isnull=True) | Q(_hsn="")) if not hsn else qs.filter(_hsn=hsn)


MAX_RECORDS = 5000  # records one approval may change in one transaction


def records_for(key_hash_value: str, hsn: str, *, lock: bool = False) -> list:
    """Every import item with exactly this (description key, HSN). Raw descriptions are prefiltered by HSN, then re-checked
    against the key (never trusted blindly). No HSN = no HS code OR a blank trimmed code. Ordered by pk (lock order)."""
    hsn = dm.norm_hsn(hsn)
    raws = [d for d in _hsn_qs(hsn).values_list("description", flat=True).distinct() if dm.key_hash(dm.description_key(d)) == key_hash_value]
    qs = _hsn_qs(hsn).filter(description__in=raws)
    if lock:
        list(qs.select_for_update(of=("self",)).order_by("pk").values_list("pk", flat=True))
    return list(qs.select_related("hs_code", "license").prefetch_related("items").order_by("pk"))


# --- protection helpers (used by every writer) -------------------------------------------------------------------------

def coverage(records) -> dict[int, ImportItemMappingApproval]:
    """record pk -> active approval covering it (records need ``hs_code`` loaded). One query."""
    combos = {}
    for r in records:
        c = combination(r)
        if c:
            combos[r.pk] = (c[1], c[2])
    if not combos:
        return {}
    found = {(a.key_hash, a.hsn_code): a for a in A.objects.filter(key_hash__in={h for h, _ in combos.values()}, is_active=True).select_related("item")}
    return {pk: found[c] for pk, c in combos.items() if c in found}


def lock_approvals(hashes) -> None:
    """Lock the active approval rows of these key hashes (pk order) — taken BEFORE any record lock so every writer follows the
    approve() order (approval row, then records) and cannot deadlock with it."""
    hashes = sorted(set(hashes))
    if hashes:
        list(A.objects.select_for_update(no_key=True).filter(key_hash__in=hashes, is_active=True).order_by("pk").values_list("pk", flat=True))


def approval_for(record) -> ImportItemMappingApproval | None:
    return coverage([record]).get(record.pk)


def protected_import_item_ids(ids) -> dict[int, str]:
    """import item id -> why automatic writers must skip it: ``override`` (row override) / ``approved`` / ``cleared``."""
    ids = list(ids or [])
    if not ids:
        return {}
    out: dict[int, str] = {}
    records = list(LicenseImportItemsModel.objects.filter(pk__in=ids).select_related("hs_code"))
    for pk, approval in coverage(records).items():
        out[pk] = "approved" if approval.status == A.USER_APPROVED and approval.item_id else "cleared"
    for pk in ImportItemNameOverride.objects.filter(import_item_id__in=ids).values_list("import_item_id", flat=True):
        out[pk] = "override"
    return out


def unprotected(ids) -> list[int]:
    """``ids`` without the protected ones (for automatic writers that work on id lists)."""
    ids = list(ids or [])
    blocked = protected_import_item_ids(ids)
    return [i for i in ids if i not in blocked]


def refusal(n: int) -> str:
    return REFUSAL.format(n=n)


# --- stats ------------------------------------------------------------------------------------------------------------

def _members(approvals) -> tuple[dict[int, list[int]], dict[int, set[int]]]:
    """approval id -> record pks / licence ids, in bulk (one scan limited to the approvals' HSN codes)."""
    wanted = {(a.key_hash, a.hsn_code): a.pk for a in approvals}
    hsns = {a.hsn_code for a in approvals}
    q = Q()
    if "" in hsns:
        q |= Q(hs_code__isnull=True) | Q(_hsn="")
    if hsns - {""}:
        q |= Q(_hsn__in=hsns - {""})
    rows = (LicenseImportItemsModel.objects.exclude(description__isnull=True).exclude(description="").annotate(_hsn=_HsnTrim("hs_code__hs_code"))
            .filter(q).values_list("pk", "description", "_hsn", "license_id"))
    keys: dict[str, str] = {}
    pks: dict[int, list[int]] = defaultdict(list)
    lic: dict[int, set[int]] = defaultdict(set)
    for pk, desc, hsn, lic_id in rows:
        if desc not in keys:
            k = dm.description_key(desc)
            keys[desc] = dm.key_hash(k) if k else ""
        aid = wanted.get((keys[desc], hsn or ""))
        if aid is not None:
            pks[aid].append(pk)
            lic[aid].add(lic_id)
    return pks, lic


def _conflict_counts(approvals, pks, over) -> dict[int, int]:
    """approval id -> records it could not link because of a SION / HSN-chapter conflict (links left unchanged). Bulk: a fixed
    number of queries however many approvals / records (one links query, one records query, one chapters query)."""
    out = {a.pk: 0 for a in approvals}
    live = [a for a in approvals if a.is_active and a.item_id and pks.get(a.pk)]
    if not live:
        return out
    links = _current_links([p for a in live for p in pks[a.pk] if p not in over])
    todo = {a.pk: [p for p in pks[a.pk] if p not in over and links.get(p, []) != [a.item_id]] for a in live}
    live = [a for a in live if todo[a.pk]]
    if not live:
        return out
    items = {i.pk: i for i in ItemNameModel.objects.prefetch_related("norms").select_related("sion_norm_class").filter(pk__in={a.item_id for a in live})}
    recs = {r.pk: r for r in LicenseImportItemsModel.objects.filter(pk__in={p for a in live for p in todo[a.pk]}).select_related("hs_code")}
    sions = dm._licence_sions(r.license_id for r in recs.values())
    legit = dm._legit_sions(items.values())
    history: dict[int, list[tuple[int, str]]] = defaultdict(list)  # item id -> [(record id, HSN chapter)]
    for name_id, rid, hsn in (LicenseImportItemsModel.items.through.objects.filter(itemnamemodel_id__in=list(items))
                              .values_list("itemnamemodel_id", "licenseimportitemsmodel_id", "licenseimportitemsmodel__hs_code__hs_code")):
        if hsn:
            history[name_id].append((rid, str(hsn)[:2]))
    for a in live:
        mine = set(todo[a.pk])  # the records being mapped never vouch for themselves (same rule as dm._chapters)
        chapters = {a.item_id: {ch for rid, ch in history.get(a.item_id, []) if rid not in mine}}
        out[a.pk] = sum(1 for p in todo[a.pk] if dm._conflict(recs[p], [items[a.item_id]], legit, chapters, sions)[0])
    return out


def stats_for(approvals) -> dict[int, dict]:
    """approval id -> {records, licences, overridden, conflicts}, computed in bulk."""
    approvals = list(approvals)
    if not approvals:
        return {}
    pks, lic = _members(approvals)
    every = [p for v in pks.values() for p in v]
    over = set(ImportItemNameOverride.objects.filter(import_item_id__in=every).values_list("import_item_id", flat=True)) if every else set()
    conflicts = _conflict_counts(approvals, pks, over)
    return {a.pk: {"records": len(pks.get(a.pk, [])), "licences": len(lic.get(a.pk, set())), "conflicts": conflicts[a.pk],
                   "overridden": sum(1 for p in pks.get(a.pk, []) if p in over)} for a in approvals}


def all_protected_import_item_ids() -> set[int]:
    """Every record decided by a row override or an active approval / clear (bulk management commands)."""
    approvals = list(A.objects.filter(is_active=True))
    pks, _ = _members(approvals) if approvals else ({}, {})
    return {p for v in pks.values() for p in v} | set(ImportItemNameOverride.objects.values_list("import_item_id", flat=True))


def serialise(a: ImportItemMappingApproval, stats: dict | None = None) -> dict:
    out = {"id": a.pk, "description": a.description, "hsn_code": a.hsn_code, "status": a.status, "version": a.version, "is_active": a.is_active,
           "source": a.source, "item": {"id": a.item_id, "name": a.item.name} if a.item_id else None,
           "updated_by": getattr(a.updated_by, "username", None), "updated_on": a.updated_on.isoformat() if a.updated_on else None}
    if stats is not None:
        out.update({"records": stats["records"], "licences": stats["licences"], "overridden": stats["overridden"],
                    "conflicts": stats["conflicts"]})
    return out


# --- preview ----------------------------------------------------------------------------------------------------------

def preview(*, description, hsn) -> dict:
    key, kh, hsn = _identity(description, hsn)
    records = records_for(kh, hsn)
    over = set(ImportItemNameOverride.objects.filter(import_item_id__in=[r.pk for r in records]).values_list("import_item_id", flat=True))
    sets: dict[str, int] = defaultdict(int)
    for r in records:
        # Display key: the record's current Item Names ("" = Not Mapped), e.g. {"ZINC": 30, "": 7} — names, never id lists.
        sets[" + ".join(sorted(i.name for i in r.items.all()))] += 1
    numbers = sorted({r.license.license_number or "" for r in records})
    return {"records": len(records), "licences": len({r.license_id for r in records}), "overridden": len(over),
            "licence_numbers": numbers[:PREVIEW_LICENCES], "current_item_sets": dict(sets)}


# --- apply ------------------------------------------------------------------------------------------------------------

def _current_links(pks) -> dict[int, list[int]]:
    """record pk -> sorted Item Name ids, one query (the through table; no per-record prefetch needed)."""
    out: dict[int, list[int]] = defaultdict(list)
    pks = list(pks)
    if pks:
        for rid, nid in (LicenseImportItemsModel.items.through.objects.filter(licenseimportitemsmodel_id__in=pks)
                         .order_by("itemnamemodel_id").values_list("licenseimportitemsmodel_id", "itemnamemodel_id")):
            out[rid].append(nid)
    return out


def _apply_records(approval: ImportItemMappingApproval, records: list, *, user, plan_impact: bool = True, change_detail: dict | None = None) -> dict:
    """REPLACE the records' links with the approval's (one Item Name, or none). Caller holds the transaction and has locked
    the approval then the records. Overridden records are skipped; conflicting records are left unchanged and reported."""
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    all_records = records
    overridden_ids = set(ImportItemNameOverride.objects.filter(import_item_id__in=[r.pk for r in records]).values_list("import_item_id", flat=True))
    records = [r for r in records if r.pk not in overridden_ids]
    ids: list[int] = [approval.item_id] if approval.item_id else []
    current_links = _current_links([r.pk for r in records])
    to_link, conflicts, unchanged, unverified = [], [], 0, 0
    item = None
    if any(current_links.get(r.pk, []) != ids for r in records):  # N4: a no-op pass (licence save) skips the conflict machinery
        item = ItemNameModel.objects.prefetch_related("norms").select_related("sion_norm_class").get(pk=approval.item_id) if approval.item_id else None
        items = [item] if item else []
        legit = dm._legit_sions(items)
        chapters = dm._chapters(ids, [r.pk for r in records]) if items else {}
        sions = dm._licence_sions(r.license_id for r in records) if items else {}
        for r in records:
            reason, note = dm._conflict(r, items, legit, chapters, sions) if items else ("", "")
            current = current_links.get(r.pk, [])
            if reason:
                conflicts.append((r, reason))
                continue
            if note:
                unverified += 1
            if current == ids:
                unchanged += 1
            else:
                to_link.append((r, current))
    else:
        unchanged = len(records)
    change = None
    if to_link:
        change = record_change(kind=MappingChange.IMPORT_ITEM_APPROVAL, user=user, source_model="license.ImportItemMappingApproval",
                               source_refs=[approval.pk], import_item_ids=[r.pk for r, _ in to_link],
                               detail={**(change_detail or {}), "approval": approval.pk, "version": approval.version, "item_id": item.pk if item else None,
                                       "status": approval.status, "records": [{"import_item_id": r.pk, "previous": prev, "new": ids} for r, prev in to_link]},
                               plan_impact=plan_impact)
        for r, _prev in to_link:
            r.items.set(ids)  # REPLACE
        for license_id in sorted({r.license_id for r, _ in to_link}):
            mark_license_replan_source_changed(license_id=license_id, reason="item_master_link_changed", source_model="license.MappingChange",
                                               source_pk=change.pk)
    conflict_licences = sorted({(r.license_id, r.license.license_number) for r, _ in conflicts}, key=lambda x: (x[1] or "", x[0]))
    return {
        "records": len(all_records), "licences": len({r.license_id for r in all_records}), "applied": len(to_link), "unchanged": unchanged,
        "overridden": len(overridden_ids), "conflicts": len(conflicts), "unverified": unverified, "mapping_change": change.pk if change else None,
        "applied_ids": [r.pk for r, _ in to_link],
        "conflict_details": [{"import_item_id": r.pk, "license_id": r.license_id, "license_number": r.license.license_number, "reason": reason}
                             for r, reason in conflicts[:50]],
        "conflict_licences": [{"id": lic, "license_number": number} for lic, number in conflict_licences]}


def _version(approval, *, action, user, previous_item_id, previous_status, result, detail=None) -> ImportItemMappingApprovalVersion:
    return V.objects.create(approval=approval, version=approval.version, action=action, item_id=approval.item_id, previous_item_id=previous_item_id,
                            previous_status=previous_status, status=approval.status if approval.is_active else "REVOKED", records=result["records"],
                            licences=result["licences"], mapping_change_id=result["mapping_change"], user=user,
                            detail={"applied": result["applied"], "unchanged": result["unchanged"], "overridden": result["overridden"],
                                    "conflicts": result["conflicts"], "unverified": result["unverified"], **(detail or {})})


def _audit(approval, version, result, *, user, action, extra=None):
    ProductIntelAuditEvent.objects.create(action=AUDIT_ACTION, user=user, detail={
        "approval": approval.pk, "version": approval.version, "action": action, "key": approval.description_key[:300], "hsn_code": approval.hsn_code,
        "item_id": approval.item_id, "status": approval.status, "records": result["records"], "licences": result["licences"],
        "applied": result["applied"], "conflicts": result["conflicts"], "overridden": result["overridden"],
        "mapping_change": result["mapping_change"], "version_id": version.pk if version else None, **(extra or {})})


def _result(approval, action, result) -> dict:
    return {"approval": serialise(approval), "action": action, **{k: result[k] for k in (
        "records", "licences", "applied", "unchanged", "overridden", "conflicts", "conflict_details", "conflict_licences", "mapping_change")}}


def approve(*, description, hsn, item_id, user, source: str = A.LICENCE_DETAIL, expected_version: int | None = None,
            expected_links: dict[int, list[int]] | None = None) -> dict:
    """Create or revise the approval for (description, HSN) and apply it to every matching record. ``item_id=None`` is a
    deliberate clear. Idempotent (same item + status = UNCHANGED, no new MappingChange unless a record had drifted)."""
    key, kh, hsn = _identity(description, hsn)
    if item_id is not None and (not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0):
        raise MatchValidationError("item_id must be an Item Name id or null")
    if source not in dict(A.SOURCES):
        raise MatchValidationError("Unknown source")
    if item_id is not None and not ItemNameModel.objects.filter(pk=item_id, is_active=True).exists():
        raise MatchValidationError("Choose an existing, active Item Name (create a missing one in Masters → Item Names first)")
    status = A.USER_APPROVED if item_id else A.USER_APPROVED_CLEAR
    with transaction.atomic():
        # Lock order = save_for_key: the decision row first, then the records.
        approval, created = A.objects.select_for_update(no_key=True).get_or_create(
            key_hash=kh, hsn_code=hsn, defaults={"description_key": key, "description": description.strip()[:5000], "item_id": item_id, "status": status,
                                                 "source": source, "created_by": user, "updated_by": user})
        previous_item, previous_status = (None, "") if created else (approval.item_id, approval.status if approval.is_active else "REVOKED")
        if not created and expected_version is not None and expected_version != approval.version:
            raise ApprovalConcurrencyError(approval.version, approval.pk)
        if created:
            action = V.CLEAR if not item_id else V.CREATE
        elif not approval.is_active:
            action = V.REACTIVATE
        elif approval.item_id != item_id or approval.status != status:
            action = V.CLEAR if not item_id else V.REVISE
        else:
            action = "UNCHANGED"
        if not created and action != "UNCHANGED":
            approval.version += 1
            approval.item_id, approval.status, approval.is_active, approval.source, approval.updated_by = item_id, status, True, source, user
            approval.save()
        approval = A.objects.select_related("item", "updated_by").get(pk=approval.pk)
        records = records_for(kh, hsn, lock=True)
        if len(records) > MAX_RECORDS:
            # Bounded locks / re-plans per decision (largest real combination today: 1,024 records on 600 licences).
            raise MatchValidationError(f"This Description + HSN matches {len(records)} records (limit {MAX_RECORDS}) — contact an administrator")
        if expected_links:  # the row(s) the user clicked: their links must still be what the user saw (checked under the lock)
            now = {r.pk: sorted(i.pk for i in r.items.all()) for r in records}
            stale = [pk for pk, links in expected_links.items() if now.get(pk) != sorted(links)]
            if stale:
                raise ApprovalConcurrencyError(approval.version, approval.pk, import_item_ids=stale)
        result = _apply_records(approval, records, user=user, change_detail={"action": action, "previous_item_id": previous_item, "source": source})
        version = None
        if action != "UNCHANGED":
            version = _version(approval, action=action, user=user, previous_item_id=previous_item, previous_status=previous_status, result=result,
                               detail={"source": source})
        _audit(approval, version, result, user=user, action=action, extra={"previous_item_id": previous_item, "source": source})
        from apps.license.services.product_intelligence.item_name_mapping import drop_counts_cache
        transaction.on_commit(drop_counts_cache)
    return _result(approval, action, result)


def revoke(approval_id: int, user) -> dict:
    """Deactivate the approval (history kept). Records keep their links; an active description-only mapping for the key
    is then applied to the combination's non-overridden records (versioned by ``dm._apply``)."""
    with transaction.atomic():
        approval = A.objects.select_for_update(no_key=True, of=("self",)).select_related("item").filter(pk=approval_id).first()
        if approval is None:
            raise MatchValidationError("Unknown approved mapping")
        if not approval.is_active:
            return {"approval": serialise(approval), "action": "UNCHANGED", "records": 0, "licences": 0, "applied": 0, "unchanged": 0, "overridden": 0,
                    "conflicts": 0, "conflict_details": [], "conflict_licences": [], "mapping_change": None, "reapplied": 0}
        previous_item, previous_status = approval.item_id, approval.status
        approval.version += 1
        approval.is_active, approval.updated_by = False, user
        approval.save()
        # Lock order = save_for_key: description mapping row, then the records.
        mapping = dm.ImportDescriptionMapping.objects.select_for_update(no_key=True).filter(key_hash=approval.key_hash, is_active=True).first()
        records = records_for(approval.key_hash, approval.hsn_code, lock=True)
        over = set(ImportItemNameOverride.objects.filter(import_item_id__in=[r.pk for r in records]).values_list("import_item_id", flat=True))
        result = {"records": len(records), "licences": len({r.license_id for r in records}), "applied": 0, "unchanged": len(records) - len(over),
                  "overridden": len(over), "conflicts": 0, "unverified": 0, "mapping_change": None, "conflict_details": [], "conflict_licences": []}
        reapplied = 0
        if mapping is not None and records:
            res = dm._apply(mapping, records, user=user, status=dm.ImportItemDescriptionMapping.APPLIED,
                            change_detail={"action": "APPROVAL_REVOKE", "approval": approval.pk, "hsn_code": approval.hsn_code})
            reapplied = res["applied"]
            result.update({"applied": res["applied"], "unchanged": res["unchanged"], "conflicts": res["conflicts"], "mapping_change": res["mapping_change"],
                           "conflict_details": res["conflict_details"], "conflict_licences": res["conflict_licences"]})
        version = _version(approval, action=V.REVOKE, user=user, previous_item_id=previous_item, previous_status=previous_status, result=result,
                           detail={"description_mapping_reapplied": reapplied})
        _audit(approval, version, result, user=user, action=V.REVOKE, extra={"previous_item_id": previous_item, "reapplied": reapplied})
        from apps.license.services.product_intelligence.item_name_mapping import drop_counts_cache
        transaction.on_commit(drop_counts_cache)
    return {"approval": serialise(approval), "action": V.REVOKE, **{k: result[k] for k in (
        "records", "licences", "applied", "unchanged", "overridden", "conflicts", "conflict_details", "conflict_licences", "mapping_change")},
            "reapplied": reapplied}


def repoint(approval_id: int, new_item_id: int, *, user, expected_item_id: int | None = None, expected_version: int | None = None,
            reason: str = "") -> dict | None:
    """Consolidation / item merge: re-point an active approval to the surviving Item Name (CONSOLIDATION version + audit,
    never silent) and apply it to the combination's records. Returns None when the approval no longer matches
    (``expected_*``) — the caller reports it, nothing is changed. Caller holds a transaction."""
    approval = A.objects.select_for_update(no_key=True, of=("self",)).select_related("item").filter(pk=approval_id, is_active=True).first()
    if approval is None or not approval.item_id or approval.item_id == new_item_id:
        return None
    if (expected_item_id is not None and approval.item_id != expected_item_id) or (expected_version is not None and approval.version != expected_version):
        return None
    previous_item, previous_status = approval.item_id, approval.status
    approval.version += 1
    approval.item_id, approval.status, approval.source, approval.updated_by = new_item_id, A.USER_APPROVED, A.CONSOLIDATION, user
    approval.save()
    approval = A.objects.select_related("item", "updated_by").get(pk=approval.pk)
    records = records_for(approval.key_hash, approval.hsn_code, lock=True)
    result = _apply_records(approval, records, user=user, change_detail={"action": V.CONSOLIDATION, "previous_item_id": previous_item, "reason": reason})
    version = _version(approval, action=V.CONSOLIDATION, user=user, previous_item_id=previous_item, previous_status=previous_status, result=result,
                       detail={"reason": reason})
    _audit(approval, version, result, user=user, action=V.CONSOLIDATION, extra={"previous_item_id": previous_item, "reason": reason})
    return {"approval_id": approval.pk, "from_item_id": previous_item, "to_item_id": new_item_id, "version": approval.version,
            "applied": result["applied"], "conflicts": result["conflicts"]}


def active_for_item(item_id: int) -> list[ImportItemMappingApproval]:
    return list(A.objects.filter(item_id=item_id, is_active=True).order_by("pk"))


def apply_for_records(records) -> dict:
    """Automatic path (new / re-described / re-HSN'd records, licence saves): apply active approvals to the records they
    cover (``plan_impact=False`` like ``dm.auto_apply``). Returns ``{covered: {pk}, applied: n, conflicts: n}``. Caller holds
    the transaction and has locked the records."""
    records = list(records)
    cov = coverage(records)
    by_approval: dict[int, list] = defaultdict(list)
    for r in records:
        if r.pk in cov:
            by_approval[cov[r.pk].pk].append(r)
    applied = conflicts = 0
    for approval_id in sorted(by_approval):
        approval = A.objects.select_for_update(no_key=True, of=("self",)).select_related("item").filter(pk=approval_id, is_active=True).first()
        if approval is None:
            for r in by_approval[approval_id]:
                cov.pop(r.pk, None)
            continue
        res = _apply_records(approval, by_approval[approval_id], user=None, plan_impact=False, change_detail={"action": "AUTO"})
        applied += res["applied"]
        conflicts += res["conflicts"]
    return {"covered": set(cov), "applied": applied, "conflicts": conflicts}


# --- listing / history ------------------------------------------------------------------------------------------------

def listing(*, q: str = "", status: str = "", offset: int = 0, limit: int = 50) -> dict:
    offset, limit = max(0, int(offset)), max(1, min(int(limit), 100))
    base = A.objects.filter(is_active=True)
    counts = {"approved": base.filter(status=A.USER_APPROVED).count(), "cleared": base.filter(status=A.USER_APPROVED_CLEAR).count()}
    qs = A.objects.all()
    status = (status or "").upper()
    if status == "REVOKED":
        qs = qs.filter(is_active=False)
    else:
        qs = qs.filter(is_active=True)
        if status in ("APPROVED", A.USER_APPROVED):
            qs = qs.filter(status=A.USER_APPROVED)
        elif status in ("CLEARED", A.USER_APPROVED_CLEAR):
            qs = qs.filter(status=A.USER_APPROVED_CLEAR)
    if q:
        k = dm.description_key(q)
        cond = Q(item__name__icontains=q) | Q(hsn_code__startswith=q.strip())
        if k:
            cond |= Q(description_key__contains=k)
        qs = qs.filter(cond)
    qs = qs.select_related("item", "updated_by").order_by("-updated_on", "-pk")
    total = qs.count()
    page = list(qs[offset:offset + limit])
    stats = stats_for(page)
    return {"rows": [serialise(a, stats[a.pk]) for a in page], "total": total, "counts": counts, "offset": offset, "limit": limit}


def history(approval_id: int) -> list[dict]:
    approval = A.objects.filter(pk=approval_id).first()
    if approval is None:
        raise MatchValidationError("Unknown approved mapping")
    versions = list(V.objects.filter(approval=approval).select_related("user").order_by("-version", "-pk"))
    ids = {i for v in versions for i in (v.item_id, v.previous_item_id) if i}
    names = dict(ItemNameModel.objects.filter(pk__in=ids).values_list("pk", "name")) if ids else {}
    return [{"id": v.pk, "version": v.version, "action": v.action, "status": v.status, "previous_status": v.previous_status,
             "item": {"id": v.item_id, "name": names.get(v.item_id, "")} if v.item_id else None,
             "previous_item": {"id": v.previous_item_id, "name": names.get(v.previous_item_id, "")} if v.previous_item_id else None,
             "records": v.records, "licences": v.licences, "mapping_change": v.mapping_change_id, "user": getattr(v.user, "username", None),
             "time": v.created_on.isoformat(), "detail": v.detail} for v in versions]


def repoint_for_merge(duplicate_ids, survivor_id: int, *, user=None, reason: str = "") -> list[dict]:
    """Item Name merge (management commands): every approval pointing at a merged-away Item Name moves to the survivor with a
    CONSOLIDATION version + audit (an ``ImportItemMappingApproval.item`` is PROTECT, so a merge can never skip this). Active
    approvals are also applied to their records; revoked ones only change their reference."""
    out = []
    for a in A.objects.select_for_update(no_key=True).filter(item_id__in=list(duplicate_ids)).exclude(item_id=survivor_id).order_by("pk"):
        if a.is_active:
            res = repoint(a.pk, survivor_id, user=user, reason=reason or "item merge")
            if res:
                out.append(res)
            continue
        previous_item, previous_status = a.item_id, "REVOKED"
        a.version += 1
        a.item_id = survivor_id
        a.save()
        empty = {"records": 0, "licences": 0, "applied": 0, "unchanged": 0, "overridden": 0, "conflicts": 0, "unverified": 0, "mapping_change": None}
        version = _version(a, action=V.CONSOLIDATION, user=user, previous_item_id=previous_item, previous_status=previous_status, result=empty,
                           detail={"reason": reason or "item merge", "revoked_approval": True})
        _audit(a, version, empty, user=user, action=V.CONSOLIDATION, extra={"previous_item_id": previous_item, "reason": reason or "item merge"})
        out.append({"approval_id": a.pk, "from_item_id": previous_item, "to_item_id": survivor_id, "version": a.version, "applied": 0, "conflicts": 0})
    return out
