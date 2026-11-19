"""Bulk update of licence import description mappings (owner spec 2026-11-19, "advanced filters & bulk update").

The target is either the descriptions matching the applied filters (evaluated here, server-side, with the same
``description_filters.matches`` the listing uses) or an explicit list of description keys. ``preview`` returns the
exact target set and a fingerprint; ``execute`` recomputes the set and refuses when it differs from the fingerprint the
user confirmed, so a changed filter / new data can never silently update a different set of descriptions.

Every target description is processed on its own: its own strict key → its own mapping (create or REPLACE, version
history), applied to every existing import item with exactly that key. A filter never defines a mapping identity and
never merges descriptions. Outcomes are reported per description (succeeded / skipped / failed); failed keys can be
re-submitted (idempotent). Classification only.
"""
from __future__ import annotations

import hashlib
import logging
import uuid

from django.core.cache import cache

from apps.license.models import ProductIntelAuditEvent
from apps.license.services.product_intelligence.description_filters import clean_filters
from apps.license.services.product_intelligence.description_mapping import _chapters, description_index, description_rows, save_for_key, validate_item_ids
from apps.license.services.product_matching import MatchValidationError

logger = logging.getLogger(__name__)
MAX_BULK = 150  # synchronous request: ~50–100 ms per description (measured components) → stays well inside request timeouts
MAX_KEY = 5000
MAX_LICENCES = 2000  # licence references returned in a preview (the count is always exact)
LOCK_KEY = "import_description_bulk_lock_v1"


def _fingerprint(keys: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(keys)).encode("utf-8")).hexdigest()


def resolve_targets(*, mode: str, filters=None, keys=None, status: str = "", q: str = "", sion: str = "") -> tuple[list[str], dict]:
    """→ (sorted target keys, index). ``mode`` "filter": every description the table shows for these criteria (filter
    conditions + status + search + SION — the listing's own computation); "keys": the given keys that still exist."""
    if mode == "filter":
        cleaned = clean_filters(filters)
        status, q, sion = (status or "").strip().upper()[:20], (q or "").strip()[:200], (sion or "").strip()[:20]
        if not (cleaned["conditions"] or status or q or sion):
            raise MatchValidationError("Apply a filter (condition, status or search) before updating all matching descriptions")
        rows, _, index = description_rows(q=q, status=status, sion=sion, filters=cleaned)
        targets = [r["key"] for r in rows]
    elif mode == "keys":
        if (not isinstance(keys, list) or not keys
                or not all(isinstance(k, str) and 0 < len(k) <= MAX_KEY for k in keys)):
            raise MatchValidationError("Select at least one description")
        index = description_index()
        targets = [k for k in dict.fromkeys(keys) if k in index]
    else:
        raise MatchValidationError("mode must be 'filter' or 'keys'")
    return sorted(targets), index


def preview(*, mode: str, filters=None, keys=None, status: str = "", q: str = "", sion: str = "") -> dict:
    targets, index = resolve_targets(mode=mode, filters=filters, keys=keys, status=status, q=q, sion=sion)
    missing = sorted(set(keys or []) - set(targets)) if mode == "keys" else []
    refs: dict[int, str] = {}
    for k in targets:
        refs.update(index[k]["refs"])
    licences = [{"id": lic, "license_number": number} for lic, number in sorted(refs.items(), key=lambda kv: (kv[1] or "", kv[0]))]
    return {"descriptions": len(targets), "records": sum(len(index[k]["record_ids"]) for k in targets),
            "licence_count": len(licences), "licences": licences[:MAX_LICENCES], "licences_truncated": len(licences) > MAX_LICENCES,
            "fingerprint": _fingerprint(targets), "sample": [index[k]["description"] for k in targets[:10]],
            "missing": missing[:50], "limit": MAX_BULK, "too_many": len(targets) > MAX_BULK}


def execute(*, mode: str, item_ids, user, fingerprint: str, filters=None, keys=None, status: str = "", q: str = "", sion: str = "") -> dict:
    """Apply ``item_ids`` (REPLACE) to every target description, each independently (own transaction). Refuses if the
    target set no longer matches the confirmed ``fingerprint``. One bulk update runs at a time; every description is
    audited with the batch id, plus one summary event for the whole request."""
    item_ids = validate_item_ids(item_ids)  # once, before anything is written
    batch = uuid.uuid4().hex
    # One bulk update at a time (shared cache in production), taken BEFORE the targets are resolved so the snapshot
    # used below cannot be overtaken by another bulk run.
    if not cache.add(LOCK_KEY, batch, timeout=15 * 60):
        raise MatchValidationError("Another bulk update is running — try again when it has finished")
    succeeded, skipped, failed = [], [], []
    try:
        targets, index = resolve_targets(mode=mode, filters=filters, keys=keys, status=status, q=q, sion=sion)
        if not targets:
            raise MatchValidationError("No descriptions match — nothing was changed")
        if len(targets) > MAX_BULK:
            raise MatchValidationError(f"{len(targets)} descriptions selected — bulk updates are limited to {MAX_BULK}; narrow the filter or select in batches")
        if not isinstance(fingerprint, str) or fingerprint != _fingerprint(targets):
            raise MatchValidationError("The matching descriptions changed since you reviewed them — review the bulk update again")
        # HSN reference computed once, before any write, excluding every record of the batch: results never depend on
        # the order in which the descriptions are processed.
        chapters = _chapters(item_ids, [rid for k in targets for rid in index[k]["record_ids"]])
        for key in targets:
            description = index[key]["description"]
            try:
                result = save_for_key(key=key, description=description, item_ids=item_ids, user=user, raw_descriptions=index[key]["wordings"],
                                      source="bulk", batch=batch, validated=True, chapters=chapters)
            except MatchValidationError as exc:
                failed.append({"key": key, "description": description, "reason": str(exc)})
                continue
            except Exception:  # noqa: BLE001 — one description failing must not lose the report of the others
                logger.exception("Bulk description mapping failed for %r (batch %s)", key, batch)
                failed.append({"key": key, "description": description, "reason": "Unexpected error — nothing was changed for this description; retry it"})
                continue
            entry = {"key": key, "description": description, "action": result["action"], "applied": result["applied"],
                     "unchanged": result["unchanged"], "conflicts": result["conflicts"], "conflict_details": result.get("conflict_details", [])[:20],
                     "conflict_licences": result.get("conflict_licences", [])}
            (skipped if result["action"] == "UNCHANGED" and not result["applied"] else succeeded).append(entry)
    finally:
        if cache.get(LOCK_KEY) == batch:
            cache.delete(LOCK_KEY)
    missing = sorted(set(keys or []) - set(targets)) if mode == "keys" else []
    skipped += [{"key": k, "description": k, "reason": "no longer exists"} for k in missing]
    try:
        ProductIntelAuditEvent.objects.create(action="import_description_bulk", user=user, detail={
            "batch": batch, "mode": mode, "filters": clean_filters(filters) if mode == "filter" else None, "status": status, "q": q, "sion": sion,
            "fingerprint": fingerprint, "item_ids": item_ids, "descriptions": len(targets),
            "succeeded": len(succeeded), "skipped": len(skipped), "failed": [f["key"][:300] for f in failed][:200]})
    except Exception:  # noqa: BLE001 — every description already carries its own audit event (with this batch id)
        logger.exception("Bulk summary audit event failed (batch %s)", batch)
    return {"batch": batch, "succeeded": succeeded, "skipped": skipped, "failed": failed, "descriptions": len(targets),
            "records": sum(e["applied"] + e["unchanged"] + e["conflicts"] for e in succeeded + skipped if "applied" in e)}
