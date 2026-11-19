"""Multi-product classification (owner spec 2026-11-19 "multi-product selection and final classification").

A source description that lists several products ("PP / LDPE", "Olive oil / Sunflower oil / PKO") is split
into detected product phrases. A reviewer selects which of them — each with its own canonical master — form
the record's final approved classification. Every selection is validated independently (master exists and is
legitimate for the SION, HSN chapter, entitlement, single-product phrase, duplicates); a conflicting selection is
never approved.

Financial safety: such a record carries ONE shared quantity / CIF. Approval records classification rows
(``ProductMatchSelection``) only — the import items' master links (which feed Auto Plan) are not changed and no
quantity is attributed to any product. Item Pivot shows the record once, as "multi-product, allocation pending".
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import ProductIntelAuditEvent, ProductMatchSelection
from apps.license.services.product_intelligence.aliases import legit_sions
from apps.license.services.product_matching import (
    HIGH, REVIEW, MatchValidationError, _entitlement_targets, normalise, product_segments, segment_pairs, text_score,
)

CANDIDATES_PER_PRODUCT = 5
MIN_CANDIDATE_SCORE = 40


def detected_products(text: str | None) -> list[tuple[str, str]]:
    """[(display phrase, normalised phrase)] in description order — the shared splitter (``segment_pairs``)."""
    return segment_pairs(text)


def _hsn_list(hsn: str | list[str] | None) -> list[str]:
    return [h for h in ([hsn] if isinstance(hsn, str) else (hsn or [])) if h]


def phrase_entitlement(sion: str | None, phrase: str, hsn: str | list[str] | None) -> str | None:
    """Entitlement a phrase requires: its own alias wording first; the record HSN(s) only when the phrase names none."""
    hits = _entitlement_targets(sion, phrase)
    if not hits:
        for code in _hsn_list(hsn):
            hits.update(_entitlement_targets(sion, "", code))
    values = set(hits.values())
    return next(iter(values)) if len(values) == 1 else ("|".join(sorted(values)) if values else None)


def check_product(phrase: str, item: ItemNameModel, *, sion: str | None, hsn: str | list[str], chapters: set[str]) -> tuple[list[str], dict]:
    """Conflicts + checks for one (phrase, master) pair. Empty conflicts = compatible."""
    conflicts: list[str] = []
    legit = sion in legit_sions(item) if sion else False
    if not sion:
        conflicts.append("SION not identified for this record")
    elif not legit:
        conflicts.append(f"{item.name} is not a legitimate item for {sion}")
    if len(product_segments(phrase)) > 1:
        conflicts.append("The phrase still names several products — select them separately")
    codes = _hsn_list(hsn)  # every HSN of the (possibly merged) source group, not only the first
    foreign = sorted({c[:2] for c in codes if chapters and c[:2] not in chapters})
    hsn_ok = not foreign
    if not hsn_ok:
        conflicts.append(f"HSN chapter {', '.join(foreign)} differs from {item.name}'s existing chapters {', '.join(sorted(chapters))}")
    required = phrase_entitlement(sion, phrase, hsn)
    if required and "|" in required:
        conflicts.append(f"'{phrase}' names products of different entitlements ({required.replace('|', ', ')})")
    elif required and item.name.upper() != required.upper():
        conflicts.append(f"Entitlement profile requires {required} for '{phrase}', not {item.name}")
    checks = {
        "sion": {"ok": legit, "detail": f"{item.name} {'is' if legit else 'is not'} legitimate for {sion or '—'} (ItemNameModel.norms)"},
        "hsn": {"ok": hsn_ok, "detail": f"Source HSN {', '.join(codes) or '—'} vs master chapters {', '.join(sorted(chapters)) or 'none yet'}"},
        "entitlement": {"ok": not required or ("|" not in required and item.name.upper() == required.upper()),
                        "detail": f"Requires {required}" if required else "No entitlement-profile rule for this phrase"},
    }
    return conflicts, checks


def _to_int(value) -> int | None:
    """Strict integer from JSON input: bools, floats with fractions and non-numeric strings are rejected."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        return int(value.strip())
    return None


def _band(confidence: int, conflicts: list[str]) -> str:
    if conflicts:
        return "CONFLICT"
    return "HIGH" if confidence >= HIGH else "REVIEW" if confidence >= REVIEW else "LOW"


def segment_rows(*, text: str, hsn: str, sion: str | None, masters: list[ItemNameModel], chapters: dict[int, set[str]],
                 approved: list[ProductMatchSelection], hsn_codes: list[str] | None = None) -> list[dict]:
    """One reviewable row per detected product phrase (suggestion only — nothing is selected automatically)."""
    approved_by_phrase = {sel.normalized_phrase: sel for sel in approved}
    codes = sorted(set(hsn_codes or []) | ({hsn} if hsn else set()))
    rows = []
    for index, (display, norm) in enumerate(detected_products(text)):
        scored = sorted(((text_score(display, m.name)[0], m) for m in masters), key=lambda sm: (-sm[0], sm[1].name))
        candidates = [{"item_id": m.pk, "name": m.name, "score": score} for score, m in scored[:CANDIDATES_PER_PRODUCT] if score >= MIN_CANDIDATE_SCORE]
        best = scored[0] if scored and scored[0][0] >= MIN_CANDIDATE_SCORE else None
        if best:
            conflicts, checks = check_product(display, best[1], sion=sion, hsn=codes, chapters=chapters.get(best[1].pk, set()))
            confidence, explanation = best[0], "; ".join(text_score(display, best[1].name)[1])
        else:
            conflicts, checks, confidence = [], {}, 0
            explanation = f"No legitimate {sion or ''} master resembles '{display}' — choose one manually or leave it excluded"
        current = approved_by_phrase.get(norm)
        rows.append({
            "index": index, "phrase": display, "normalized": norm, "hsn_code": hsn,
            "suggestion": {"item_id": best[1].pk, "name": best[1].name} if best else None, "confidence": confidence,
            "band": _band(confidence, conflicts) if best else "UNMATCHED", "compatible": bool(best) and not conflicts,
            "conflicts": conflicts, "checks": checks, "explanation": explanation, "candidates": candidates,
            "entitlement": phrase_entitlement(sion, display, codes),
            "approved": {"item_id": current.item_id, "name": current.item.name, "by": getattr(current.decided_by, "username", None),
                         "on": current.decided_on.isoformat()} if current else None,
        })
    return rows


@dataclass
class SelectionResult:
    phrase: str
    item_id: int | None
    index: int | None
    ok: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    item_name: str | None = None
    confidence: int = 0
    entitlement: str | None = None
    normalized: str = ""
    manual: bool = False

    def as_dict(self) -> dict:
        return {"index": self.index, "phrase": self.phrase, "item_id": self.item_id, "item": self.item_name, "ok": self.ok,
                "reasons": self.reasons, "checks": self.checks, "confidence": self.confidence, "entitlement": self.entitlement,
                "manual": self.manual}


class SelectionRejected(MatchValidationError):
    def __init__(self, results: list[SelectionResult], message: str):
        super().__init__(message)
        self.results = results


def validate_selections(suggestion: dict, selections: list[dict], *, chapters: dict[int, set[str]]) -> list[SelectionResult]:
    """Validate every selection independently. ``selections``: [{index?: int, phrase?: str, item_id: int}]."""
    segments = {row["index"]: row for row in suggestion.get("segments") or []}
    sion = suggestion.get("sion")
    hsn = sorted(set(suggestion.get("hsn_codes") or []) | ({suggestion["hsn_code"]} if suggestion.get("hsn_code") else set()))
    item_ids = {i for i in (_to_int(s.get("item_id")) for s in selections) if i}
    items = {i.pk: i for i in ItemNameModel.objects.filter(pk__in=item_ids, is_active=True).prefetch_related("norms").select_related("sion_norm_class")}
    seen_phrases: set[str] = set()
    seen_items: set[int] = set()
    results = []
    for sel in selections:
        index = _to_int(sel.get("index")) if sel.get("index") is not None else None
        phrase = segments[index]["phrase"] if index in segments else str(sel.get("phrase") or "").strip()
        item_id = _to_int(sel.get("item_id"))
        # The key is the segment's own normalised phrase (a modifier-merged display "X dense / light" normalises
        # differently) — so an approved product is found again and re-submission stays idempotent.
        norm = segments[index]["normalized"] if index in segments else normalise(phrase)
        result = SelectionResult(phrase=phrase, item_id=item_id, index=index, ok=False, normalized=norm, manual=index is None)
        if sel.get("index") is not None and index not in segments:
            result.reasons.append("Unknown detected product")
        if sel.get("item_id") is not None and item_id is None:
            result.reasons.append("Invalid master id")
        if not phrase:
            result.reasons.append("A manually added product needs a description")
        item = items.get(item_id) if item_id else None
        if item is None:
            result.reasons.append("Choose an existing, active canonical master")
        if norm and norm in seen_phrases:
            result.reasons.append("This product is selected twice")
        if item_id and item_id in seen_items:
            result.reasons.append(f"{getattr(item, 'name', 'This master')} is already selected for another product of this record")
        if item is not None and phrase:
            conflicts, checks = check_product(phrase, item, sion=sion, hsn=hsn, chapters=chapters.get(item.pk, set()))
            result.reasons.extend(conflicts)
            result.checks, result.item_name = checks, item.name
            result.confidence = text_score(phrase, item.name)[0]
            result.entitlement = phrase_entitlement(sion, phrase, hsn)
        result.ok = not result.reasons
        if norm:
            seen_phrases.add(norm)
        if item_id:
            seen_items.add(item_id)
        results.append(result)
    return results


def decide_products(*, suggestion: dict, selections: list[dict], user, partial: bool = False, clear: bool = False) -> dict:
    """Make the submitted, validated selections the record's final approved classification.

    * nothing selected → error, nothing changes;
    * any rejected selection → error with per-selection reasons, nothing changes — unless ``partial``, in which
      case only the compatible selections are applied and the rejected ones are reported;
    * previously approved products that are no longer selected are REVOKED (audited); unchanged ones are kept
      (idempotent — re-submitting the same set writes nothing new);
    * import-item master links, quantities and CIF are never touched.
    """
    from apps.license.services.product_matching import _master_hsn_chapters

    if not selections:
        if clear:
            return _clear_classification(suggestion, user)
        raise MatchValidationError("Select at least one product — nothing was approved")
    chapters = _master_hsn_chapters({i for i in (_to_int(s.get("item_id")) for s in selections) if i})
    results = validate_selections(suggestion, selections, chapters=chapters)
    accepted = [r for r in results if r.ok]
    rejected = [r for r in results if not r.ok]
    if rejected and not partial:
        raise SelectionRejected(results, f"{len(rejected)} selected product(s) failed validation — nothing was approved")
    if not accepted:
        raise SelectionRejected(results, "No selected product passed validation — nothing was approved")
    source_key = suggestion["source_key"]
    sion = SionNormClassModel.objects.filter(norm_class=suggestion.get("sion")).first()
    try:
        with transaction.atomic():
            _lock_source(source_key)  # serialise concurrent first submissions for the same record
            current = list(ProductMatchSelection.objects.select_for_update().filter(source_key=source_key, status=ProductMatchSelection.APPROVED).order_by("pk"))
            previous = sorted({c.item_id for c in current})
            wanted = {(r.normalized, r.item_id): r for r in accepted}
            kept = {(c.normalized_phrase, c.item_id) for c in current if (c.normalized_phrase, c.item_id) in wanted}
            revoked = [c for c in current if (c.normalized_phrase, c.item_id) not in wanted]
            new_mapping = sorted({item_id for _, item_id in wanted})
            now = timezone.now()
            for c in revoked:
                c.status, c.revoked_by, c.revoked_on = ProductMatchSelection.REVOKED, user, now
                c.save(update_fields=["status", "revoked_by", "revoked_on"])
            created = []
            for key, r in wanted.items():
                if key in kept:
                    continue
                created.append(ProductMatchSelection.objects.create(
                    source_key=source_key, import_item_ids=sorted(suggestion.get("import_item_ids") or []),
                    source_description=(suggestion.get("description") or "")[:5000], hsn_code=(suggestion.get("hsn_code") or "")[:20],
                    detected_phrase=r.phrase[:500], normalized_phrase=key[0][:500], segment_index=r.index, item_id=r.item_id,
                    confidence=r.confidence, sion=sion, entitlement=(r.entitlement or "")[:120], checks=r.checks,
                    previous_mapping=previous, new_mapping=new_mapping, decided_by=user,
                ))
            # Classification only (no master links) → the mapping version affects Item Pivot grouping, not planning.
            from apps.license.models import MappingChange
            from apps.license.services.product_intelligence.propagation import record_change
            record_change(kind=MappingChange.MULTI_PRODUCT, user=user, source_model="license.ProductMatchSelection",
                          source_refs=[c.pk for c in created] + [c.pk for c in revoked], import_item_ids=suggestion.get("import_item_ids") or [],
                          detail={"source_key": source_key, "previous_mapping": previous, "new_mapping": new_mapping}, plan_impact=False)
            ProductIntelAuditEvent.objects.create(action="products_classified", user=user, detail={
                "source_key": source_key, "import_item_ids": sorted(suggestion.get("import_item_ids") or []),
                "approved": [{"phrase": r.phrase, "item_id": r.item_id, "manual": r.manual} for r in accepted],
                "rejected": [r.as_dict() for r in rejected], "revoked": [c.pk for c in revoked], "created": [c.pk for c in created],
                "previous_mapping": previous, "new_mapping": new_mapping})
    except IntegrityError as exc:
        raise MatchValidationError("These products were just classified by another reviewer — reload and retry") from exc
    return {"results": [r.as_dict() for r in results], "created": [c.pk for c in created], "kept": len(kept),
            "revoked": [c.pk for c in revoked], "previous_mapping": previous, "new_mapping": new_mapping}


def _clear_classification(suggestion: dict, user) -> dict:
    """Explicit reviewer action: revoke every approved product of the record (audited). Approves nothing."""
    source_key = suggestion["source_key"]
    with transaction.atomic():
        _lock_source(source_key)
        current = list(ProductMatchSelection.objects.select_for_update().filter(source_key=source_key, status=ProductMatchSelection.APPROVED).order_by("pk"))
        if not current:
            raise MatchValidationError("Nothing is approved for this record")
        now = timezone.now()
        for c in current:
            c.status, c.revoked_by, c.revoked_on = ProductMatchSelection.REVOKED, user, now
            c.save(update_fields=["status", "revoked_by", "revoked_on"])
        previous = sorted({c.item_id for c in current})
        ProductIntelAuditEvent.objects.create(action="products_classification_cleared", user=user, detail={
            "source_key": source_key, "import_item_ids": sorted(suggestion.get("import_item_ids") or []),
            "revoked": [c.pk for c in current], "previous_mapping": previous, "new_mapping": []})
    return {"results": [], "created": [], "kept": 0, "revoked": [c.pk for c in current], "previous_mapping": previous, "new_mapping": []}


def _lock_source(source_key: str) -> None:
    """Transaction-scoped advisory lock per source key (PostgreSQL); a no-op on other databases."""
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    key = int.from_bytes(hashlib.sha256(source_key.encode()).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


def approved_by_source(source_keys: list[str]) -> dict[str, list[ProductMatchSelection]]:
    out: dict[str, list[ProductMatchSelection]] = {}
    for sel in ProductMatchSelection.objects.filter(source_key__in=source_keys, status=ProductMatchSelection.APPROVED).select_related("item", "decided_by"):
        out.setdefault(sel.source_key, []).append(sel)
    return out


def approved_by_import_item() -> dict[int, list[ProductMatchSelection]]:
    """Approved classifications per import item (Item Pivot aggregation)."""
    out: dict[int, list[ProductMatchSelection]] = {}
    for sel in ProductMatchSelection.objects.filter(status=ProductMatchSelection.APPROVED).select_related("item").order_by("pk"):
        for item_id in sel.import_item_ids or []:
            out.setdefault(int(item_id), []).append(sel)
    return out


__all__ = ["approved_by_import_item", "approved_by_source", "decide_products", "detected_products", "segment_rows",
           "validate_selections", "SelectionRejected"]
