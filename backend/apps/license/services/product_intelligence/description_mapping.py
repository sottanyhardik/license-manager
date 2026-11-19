"""Saved licence import description → Item Name(s) mappings (owner spec 2026-11-19, "automatic licence item name mapping").

The user maps each unique import description ONCE (one or several existing Item Names). The mapping is:

* keyed by a deterministic, *strict* normalisation of the original description (``description_key``) — whitespace,
  case and punctuation spacing only; no word is ever dropped, no fuzzy / semantic merge;
* applied with REPLACE semantics (``LicenseImportItemsModel.items.set``) to every existing import item with exactly that
  key, and automatically to future ones (``auto_apply`` from the import-item post_save hook);
* checked per record against its licence's SION (every selected Item Name must be legitimate for it) and HSN (the
  record's HSN chapter must be one the selected Item Names already use, when known) — a conflicting record is flagged
  ``CONFLICT`` and left unchanged, never silently assigned;
* versioned (``ImportDescriptionMappingVersion``, previous → new ids) and propagated through the existing mapping-change
  pipeline (``record_change`` archives the affected plans; each licence re-plans once).

Classification only: descriptions, quantities, CIF, debits and balances are never written. Several Item Names on one
record do not multiply its quantity or CIF (they stay at source-record level).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict

from django.db import transaction

from apps.core.models import ItemNameModel
from apps.license.models import (
    ImportDescriptionMapping, ImportDescriptionMappingVersion, ImportItemDescriptionMapping, LicenseImportItemsModel, MappingChange,
    ProductIntelAuditEvent,
)
from apps.license.services.product_matching import MatchValidationError

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"'}
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿"), None)
MAX_ITEMS = 20
MAX_DESCRIPTION = 2000  # LicenseImportItemsModel.description max_length


def description_key(text: str | None) -> str:
    """Deterministic identity of a description. Safe changes only: Unicode compatibility form, invisible characters,
    case, dash / quote variants, repeated whitespace, the space before "," ";" ")" "]" and after "(" "[", one space
    after a word-separating comma / semicolon, trailing full stop / comma. Every word and every "." ":" "/" stays where
    it is (so "0 .5" ≠ "0.5"; "1,000" is kept), and CRUDE / REFINED / RBD / PKO / OLIVE … always distinguish descriptions."""
    s = unicodedata.normalize("NFKC", text or "").translate(_INVISIBLE).translate(_DASHES).translate(_QUOTES).upper()
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,;)\]])", r"\1", s)                  # "OIL ," → "OIL,"
    s = re.sub(r"([(\[])\s+", r"\1", s)                    # "( CRUDE" → "(CRUDE"
    s = re.sub(r"(?<!\d)([,;])(?=[^\s\d])", r"\1 ", s)     # "OIL,PKO" → "OIL, PKO"; "1,000" untouched
    return s.rstrip(" .,")


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# --- context checks -----------------------------------------------------------------------------------------------

def _licence_sions(license_ids) -> dict[int, set[str]]:
    from apps.license.models import LicenseExportItemModel

    out: dict[int, set[str]] = defaultdict(set)
    for lic, code in (LicenseExportItemModel.objects.filter(license_id__in=set(license_ids), norm_class__isnull=False)
                      .values_list("license_id", "norm_class__norm_class").distinct()):
        out[lic].add(code)
    return out


def _legit_sions(items) -> dict[int, set[str] | None]:
    """Item Name id → SION codes it is legitimate for (``norms``, else the FK); None = unrestricted (no norm data)."""
    out = {}
    for item in items:
        codes = {n.norm_class for n in item.norms.all()} or ({item.sion_norm_class.norm_class} if item.sion_norm_class_id else set())
        out[item.pk] = codes or None
    return out


def _conflict(record, items, legit, chapters, sions) -> str:
    """'' when the selected Item Names fit this record's licence SION and HSN, else the reason (record is not changed)."""
    licence_sions = sions.get(record.license_id, set())
    if licence_sions:
        wrong = [i.name for i in items if legit[i.pk] is not None and not (legit[i.pk] & licence_sions)]
        if wrong:
            return f"{', '.join(wrong)} not legitimate for licence SION {', '.join(sorted(licence_sions))}"
    hsn = (record.hs_code.hs_code if record.hs_code_id else "") or ""
    known = [chapters.get(i.pk, set()) for i in items]
    if hsn and known and all(known) and not any(hsn[:2] in c for c in known):
        return f"HSN {hsn} differs from the chapters used by {', '.join(i.name for i in items)} ({', '.join(sorted(set().union(*known)))})"
    return ""


def _records_for(key: str, *, lock: bool = False) -> list:
    """Every import item whose description has exactly this key (raw wordings are normalised once each)."""
    raw_hits = [d for d in LicenseImportItemsModel.objects.exclude(description__isnull=True).exclude(description="")
                .values_list("description", flat=True).distinct() if description_key(d) == key]
    qs = LicenseImportItemsModel.objects.filter(description__in=raw_hits)
    if lock:
        list(qs.select_for_update(of=("self",)).order_by("pk").values_list("pk", flat=True))
    return list(qs.select_related("hs_code").prefetch_related("items").order_by("pk"))


# --- apply ----------------------------------------------------------------------------------------------------------

def _apply(mapping: ImportDescriptionMapping, records: list, *, user, status: str, change_detail: dict, plan_impact: bool = True) -> dict:
    """REPLACE the records' Item Names with the mapping's set (conflicts flagged). Caller holds the transaction."""
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    from apps.license.services.product_matching import _master_hsn_chapters

    items = list(mapping.items.prefetch_related("norms").select_related("sion_norm_class").order_by("pk"))
    item_ids = [i.pk for i in items]
    legit, chapters = _legit_sions(items), _master_hsn_chapters(set(item_ids))
    sions = _licence_sions(r.license_id for r in records)
    existing = {a.import_item_id: a for a in ImportItemDescriptionMapping.objects.filter(import_item_id__in=[r.pk for r in records])}
    to_link, conflicts, unchanged = [], [], 0
    for r in records:
        reason = _conflict(r, items, legit, chapters, sions)
        current = sorted(i.pk for i in r.items.all())
        app = existing.get(r.pk)
        if reason:
            conflicts.append((r, reason, current))
        elif current == item_ids and app and app.mapping_id == mapping.pk and app.applied_version == mapping.version and app.status != app.CONFLICT:
            unchanged += 1  # idempotent / retry-safe
        else:
            to_link.append((r, current))
    change = None
    if to_link:
        # One mapping version per call, recorded BEFORE any link is written (the archive holds the superseded plans).
        change = record_change(kind=MappingChange.DESCRIPTION_MAPPING, user=user, source_model="license.ImportDescriptionMapping",
                               source_refs=[mapping.pk], import_item_ids=[r.pk for r, _ in to_link],
                               detail={**change_detail, "mapping": mapping.pk, "version": mapping.version, "item_ids": item_ids},
                               plan_impact=plan_impact)
    for r, current in to_link:
        if current != item_ids:
            r.items.set(item_ids)  # REPLACE
        app = existing.get(r.pk)
        ImportItemDescriptionMapping.objects.update_or_create(import_item=r, defaults={
            "mapping": mapping, "applied_version": mapping.version, "status": status, "detail": "",
            "previous_item_ids": app.previous_item_ids if app else current})
    for r, reason, current in conflicts:
        app = existing.get(r.pk)
        ImportItemDescriptionMapping.objects.update_or_create(import_item=r, defaults={
            "mapping": mapping, "applied_version": mapping.version, "status": ImportItemDescriptionMapping.CONFLICT, "detail": reason[:1000],
            "previous_item_ids": app.previous_item_ids if app else current})
    for license_id in sorted({r.license_id for r, _ in to_link}):
        mark_license_replan_source_changed(license_id=license_id, reason="item_master_link_changed", source_model="license.MappingChange",
                                           source_pk=change.pk if change else None)
    return {"applied": len(to_link), "unchanged": unchanged, "conflicts": len(conflicts), "mapping_change": change.pk if change else None,
            "conflict_details": [{"import_item_id": r.pk, "license_id": r.license_id, "reason": reason} for r, reason, _ in conflicts[:50]]}


def save_mapping(*, description: str, item_ids: list[int], user, expected_version: int | None = None, require_version: bool = False) -> dict:
    """Create or REPLACE the mapping for this description and apply it to every existing record with the same key.
    All-or-nothing; idempotent (same set → nothing rewritten); ``expected_version`` guards concurrent edits
    (``require_version``: an existing mapping can only be edited with the version the user saw)."""
    if len(description or "") > MAX_DESCRIPTION:
        raise MatchValidationError(f"Descriptions are at most {MAX_DESCRIPTION} characters")
    key = description_key(description)
    if not key:
        raise MatchValidationError("A description is required")
    if (not isinstance(item_ids, list) or not item_ids or len(item_ids) > MAX_ITEMS
            or not all(isinstance(i, int) and not isinstance(i, bool) and i > 0 for i in item_ids)):
        raise MatchValidationError(f"Select between 1 and {MAX_ITEMS} existing Item Names")
    wanted = sorted(set(item_ids))
    found = set(ItemNameModel.objects.filter(pk__in=wanted, is_active=True).values_list("pk", flat=True))
    if found != set(wanted):
        raise MatchValidationError("Choose existing, active Item Names (create a missing one in Masters → Item Names first)")
    with transaction.atomic():
        mapping, created = ImportDescriptionMapping.objects.select_for_update(no_key=True).get_or_create(
            key_hash=key_hash(key), defaults={"description_key": key, "description": description.strip()[:5000], "created_by": user, "updated_by": user})
        previous = [] if created else sorted(mapping.items.values_list("pk", flat=True))
        if not created and require_version and expected_version is None:
            raise MatchValidationError("This description already has a mapping — reload it and edit that version")
        if not created and expected_version is not None and expected_version != mapping.version:
            raise MatchValidationError(f"This mapping was changed by someone else (now version {mapping.version}) — reload and try again")
        if created or previous != wanted or not mapping.is_active:
            if not created:
                mapping.version += 1
            mapping.is_active, mapping.updated_by = True, user
            mapping.save()
            mapping.items.set(wanted)
            action = ImportDescriptionMappingVersion.CREATE if created else ImportDescriptionMappingVersion.REPLACE
            version = ImportDescriptionMappingVersion.objects.create(mapping=mapping, version=mapping.version, action=action,
                                                                     item_ids=wanted, previous_item_ids=previous, user=user)
        else:
            action, version = "UNCHANGED", None
        records = _records_for(key, lock=True)
        result = _apply(mapping, records, user=user, status=ImportItemDescriptionMapping.APPLIED,
                        change_detail={"action": action, "previous_item_ids": previous})
        if version is not None and result["mapping_change"]:
            version.mapping_change_id = result["mapping_change"]
            version.save(update_fields=["mapping_change"])
        ProductIntelAuditEvent.objects.create(action="import_description_mapped", user=user, detail={
            "mapping": mapping.pk, "version": mapping.version, "key": key[:300], "action": action, "item_ids": wanted,
            "previous_item_ids": previous, "applied": result["applied"], "conflicts": result["conflicts"]})
    return {"mapping": serialise(mapping), "action": action, **result}


def reapply(mapping_id: int, *, user) -> dict:
    """Retry-safe: re-apply the current version to every record with its key (records already current are skipped)."""
    with transaction.atomic():
        mapping = ImportDescriptionMapping.objects.select_for_update(no_key=True).filter(pk=mapping_id, is_active=True).first()
        if mapping is None:
            raise MatchValidationError("Unknown mapping")
        result = _apply(mapping, _records_for(mapping.description_key, lock=True), user=user,
                        status=ImportItemDescriptionMapping.APPLIED, change_detail={"action": "REAPPLY"})
        ProductIntelAuditEvent.objects.create(action="import_description_reapplied", user=user, detail={
            "mapping": mapping.pk, "version": mapping.version, "applied": result["applied"], "conflicts": result["conflicts"]})
    return {"mapping": serialise(mapping), **result}


def auto_apply(import_item_id: int) -> str | None:
    """Future records: an exact-key saved mapping is applied automatically (status AUTO). Returns the status, or None
    when there is no mapping (the description then shows as Mapping Required). Idempotent."""
    with transaction.atomic():
        record = (LicenseImportItemsModel.objects.select_for_update(of=("self",)).filter(pk=import_item_id)
                  .select_related("hs_code").prefetch_related("items").first())
        if record is None or not (record.description or "").strip():
            return None
        mapping = (ImportDescriptionMapping.objects.select_for_update(no_key=True)
                   .filter(key_hash=key_hash(description_key(record.description)), is_active=True).first())
        if mapping is None:
            return None
        # A new / re-described record: versioned and its licence re-planned, without a per-record plan archive (bulk imports).
        result = _apply(mapping, [record], user=None, status=ImportItemDescriptionMapping.AUTO,
                        change_detail={"action": "AUTO", "import_item": record.pk}, plan_impact=False)
    return ImportItemDescriptionMapping.CONFLICT if result["conflicts"] else ImportItemDescriptionMapping.AUTO


def apply_for_licence(license_id: int) -> int:
    """Bulk saves (incl. ``bulk_create``, which sends no post_save): apply every exact saved description mapping to this
    licence's import items that do not carry its current version yet. Returns the number of records mapped (AUTO)."""
    mapped = 0
    with transaction.atomic():
        records = list(LicenseImportItemsModel.objects.select_for_update(of=("self",)).filter(license_id=license_id)
                       .exclude(description__isnull=True).exclude(description="").select_related("hs_code").prefetch_related("items").order_by("pk"))
        by_hash: dict[str, list] = defaultdict(list)
        for r in records:
            k = description_key(r.description)
            if k:
                by_hash[key_hash(k)].append(r)
        for mapping in (ImportDescriptionMapping.objects.select_for_update(no_key=True)
                        .filter(key_hash__in=list(by_hash), is_active=True).order_by("pk")):
            result = _apply(mapping, by_hash[mapping.key_hash], user=None, status=ImportItemDescriptionMapping.AUTO,
                            change_detail={"action": "AUTO", "license": license_id}, plan_impact=False)
            mapped += result["applied"]
    return mapped


def serialise(m: ImportDescriptionMapping) -> dict:
    return {"id": m.pk, "version": m.version, "description": m.description, "key": m.description_key,
            "items": [{"item_id": i.pk, "name": i.name} for i in m.items.order_by("name")]}


# --- listing --------------------------------------------------------------------------------------------------------

MAPPING_REQUIRED, APPLIED, CONFLICT, PARTIAL = "MAPPING_REQUIRED", "APPLIED", "CONFLICT", "PARTIAL"


def descriptions(*, q: str = "", status: str = "", sion: str = "", offset: int = 0, limit: int = 50) -> dict:
    """One row per unique description key across all licence import items, with its saved mapping and status:
    MAPPING_REQUIRED (no mapping) · APPLIED (every record carries the current version) · CONFLICT (some records were
    flagged) · PARTIAL (some records not yet at the current version — retry)."""
    offset, limit = max(0, int(offset)), max(1, min(int(limit), 100))
    rows = list(LicenseImportItemsModel.objects.exclude(description__isnull=True).exclude(description="")
                .values_list("pk", "description", "hs_code__hs_code", "license_id", "license__license_number"))
    sions = _licence_sions({r[3] for r in rows})
    keys: dict[str, str] = {}
    groups: dict[str, dict] = {}
    for pk, desc, hsn, lic, number in rows:
        if desc not in keys:
            keys[desc] = description_key(desc)
        k = keys[desc]
        if not k:
            continue
        g = groups.setdefault(k, {"key": k, "wordings": defaultdict(int), "record_ids": [], "hsn": set(), "sion": set(), "licences": set(), "numbers": set()})
        g["wordings"][desc] += 1
        g["record_ids"].append(pk)
        g["licences"].add(lic)
        g["numbers"].add(number)
        if hsn:
            g["hsn"].add(hsn)
        g["sion"] |= sions.get(lic, set())
    mappings = {m.key_hash: m for m in ImportDescriptionMapping.objects.filter(is_active=True).prefetch_related("items")}
    applied_by_item: dict[int, dict] = {a["import_item_id"]: a for a in ImportItemDescriptionMapping.objects.values(
        "import_item_id", "mapping_id", "applied_version", "status", "detail")}
    links: dict[int, set[int]] = defaultdict(set)  # actual links of records that carry a mapping (manual drift → PARTIAL)
    through = LicenseImportItemsModel.items.through
    for item_id, name_id in through.objects.filter(licenseimportitemsmodel_id__in=list(applied_by_item)).values_list("licenseimportitemsmodel_id", "itemnamemodel_id"):
        links[item_id].add(name_id)
    q_key = description_key(q) if q else ""
    out = []
    for k, g in groups.items():
        if q_key and q_key not in k:
            continue
        if sion and sion not in g["sion"]:
            continue
        m = mappings.get(key_hash(k))
        counts = {"applied": 0, "auto": 0, "conflict": 0, "stale": 0}
        reasons = []
        if m:
            wanted = {i.pk for i in m.items.all()}
            for rid in g["record_ids"]:
                a = applied_by_item.get(rid)
                if not a or a["mapping_id"] != m.pk or a["applied_version"] != m.version:
                    counts["stale"] += 1
                elif a["status"] != ImportItemDescriptionMapping.CONFLICT and links.get(rid, set()) != wanted:
                    counts["stale"] += 1  # links changed since (manual edit / another writer) — Retry re-applies
                elif a["status"] == ImportItemDescriptionMapping.CONFLICT:
                    counts["conflict"] += 1
                    reasons.append(a["detail"])
                elif a["status"] == ImportItemDescriptionMapping.AUTO:
                    counts["auto"] += 1
                else:
                    counts["applied"] += 1
        row_status = MAPPING_REQUIRED if m is None else CONFLICT if counts["conflict"] else PARTIAL if counts["stale"] else APPLIED
        out.append({
            "key": k, "description": max(g["wordings"].items(), key=lambda kv: (kv[1], kv[0]))[0], "wordings": len(g["wordings"]),
            "records": len(g["record_ids"]), "licence_count": len(g["licences"]), "licence_numbers": sorted(g["numbers"])[:5],
            "hsn_codes": sorted(g["hsn"])[:5], "sion": sorted(g["sion"]), "status": row_status, "counts": counts,
            "conflicts": list(dict.fromkeys(reasons))[:3],
            "mapping": {"id": m.pk, "version": m.version, "items": [{"item_id": i.pk, "name": i.name} for i in sorted(m.items.all(), key=lambda x: x.name)]} if m else None,
        })
    summary = defaultdict(int)
    for r in out:
        summary[r["status"]] += 1
    if status:
        out = [r for r in out if r["status"] == status]
    order = {MAPPING_REQUIRED: 0, CONFLICT: 1, PARTIAL: 2, APPLIED: 3}
    out.sort(key=lambda r: (order[r["status"]], -r["records"], r["key"]))
    return {"rows": out[offset:offset + limit], "total": len(out), "summary": dict(summary), "offset": offset, "limit": limit}
