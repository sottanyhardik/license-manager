"""Bulk canonical-product consolidation (owner request 2026-11-19: E1 Polypropylene → canonical "PP").

Preview → explicit selection → apply → revert, all audited. A record qualifies only when its description names
exactly ONE product whose identity equals the target's (after normalising spelling / abbreviations and removing
packaging / grade / form qualifiers), its HSN chapter fits the target, and the target master is legitimate for the
SION. Multi-product descriptions, extra product words ("board", "bag", "BOPP" …), HSN conflicts and records with
several master links are excluded for human review — never consolidated in bulk.

Only import-item → master links change (previous links recorded). No BOE, invoice, allotment, quantity, CIF or
balance is touched. Owner decision 2026-11-19 (Part 15 overrides the consolidation spec's §7): a consolidation is a
mapping change — it is versioned (``MappingChange``, plans archived first) and the affected licences re-plan
automatically through the existing pipeline.
"""
from __future__ import annotations

import uuid
from collections import Counter

from django.db import transaction

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import LicenseImportItemsModel, ProductAlias, ProductIntelAuditEvent, ProductMatchDecision
from apps.license.services.product_intelligence.aliases import create_alias, legit_sions
from apps.license.services.product_matching import MatchValidationError, master_label, normalise, product_segments, source_key, tokens

MATCHER = "bulk-consolidation-v1"
# Packaging / grade / form words that qualify a product without changing its identity ("PP film grade" = PP).
QUALIFIERS = {
    "packing", "packaging", "material", "matarial", "film", "granule", "moulding", "molding", "injection", "extrusion",
    "virgin", "resin", "homopolymer", "raw", "chip", "pellet", "matrial", "packimg",  # observed typos of packing / material
}
ELIGIBLE, ALREADY, REVIEW, EXCLUDED = "ELIGIBLE", "ALREADY_CONSOLIDATED", "REVIEW", "EXCLUDED"
CHAPTER_SHARE = 0.10  # target chapters = HSN chapters holding ≥ 10 % of the target master's existing links


def identity_tokens(text: str | None) -> set[str]:
    return tokens(normalise(text)) - QUALIFIERS


def _target_chapters(target: ItemNameModel) -> set[str]:
    through = LicenseImportItemsModel.items.through
    counts = Counter(str(h)[:2] for h in through.objects.filter(itemnamemodel_id=target.pk)
                     .values_list("licenseimportitemsmodel__hs_code__hs_code", flat=True) if h)
    total = sum(counts.values())
    return {c for c, n in counts.items() if total and n / total >= CHAPTER_SHARE}


def classify_record(description: str, hsn: str, links: list[ItemNameModel], *, target: ItemNameModel, target_core: set[str],
                    chapters: set[str]) -> tuple[str, str]:
    """(status, reason) for one record. Only ELIGIBLE records can be consolidated."""
    segments = product_segments(description)
    if not segments:
        return EXCLUDED, "No product wording"
    if not (target_core & set().union(*(tokens(s) for s in segments))):
        return EXCLUDED, "Not a candidate"
    if len(segments) > 1:
        return EXCLUDED, f"Multi-product description ({'; '.join(segments[:4])}) — review it in Product Matching"
    core = tokens(segments[0]) - QUALIFIERS
    if core != target_core:
        extra = sorted(core - target_core)
        return REVIEW, f"Extra product words ({', '.join(extra)}) — not proven equivalent to {target.name}"
    if hsn and chapters and hsn[:2] not in chapters:
        return REVIEW, f"HSN chapter {hsn[:2]} differs from {target.name}'s chapters {', '.join(sorted(chapters))}"
    ids = sorted(n.pk for n in links)
    if ids == [target.pk]:
        return ALREADY, f"Already linked to {target.name}"
    if len(ids) > 1:
        return REVIEW, f"Linked to several masters ({', '.join(sorted(n.name for n in links))}) — resolve in Product Matching"
    if ids:
        return ELIGIBLE, f"Replaces {links[0].name} → {target.name}"
    return ELIGIBLE, f"Unlinked → {target.name}"


def approval_gate(status: str, reason: str, approval, links: list, target: ItemNameModel) -> tuple[str, str]:
    """Owner amendment 2026-11-20: a consolidation never silently overrides a Description + HSN approval. A record whose approval
    points at the Item Name being replaced stays ELIGIBLE (the approval is re-pointed to the target — versioned + audited); a
    cleared combination, or an approval pointing at anything else, is excluded."""
    if approval is None or status not in {ELIGIBLE}:
        return status, reason
    if not approval.item_id:
        return EXCLUDED, "Approved Description + HSN mapping with no Item Name (cleared) — consolidation never links it"
    if approval.item_id == target.pk:
        return status, reason
    if [n.pk for n in links] == [approval.item_id]:
        return status, f"{reason} (approved Description + HSN mapping is re-pointed to {target.name}, versioned)"
    return EXCLUDED, f"Approved Description + HSN mapping points to another Item Name — not changed by consolidation"


OVERRIDE_REASON = "Row override — change it in Licence Detail → Import Items"


def override_gate(status: str, reason: str, overridden: bool) -> tuple[str, str]:
    """Precedence: a row override (one-record exception) outranks every consolidation — the record is never moved."""
    if overridden and status == ELIGIBLE:
        return EXCLUDED, OVERRIDE_REASON
    return status, reason


def _overridden_ids(ids) -> set[int]:
    from apps.license.models import ImportItemNameOverride

    ids = list(ids)
    return set(ImportItemNameOverride.objects.filter(import_item_id__in=ids).values_list("import_item_id", flat=True)) if ids else set()


def _lock_records(ids, *, extra_combinations=()) -> None:
    """Lock order approval -> records everywhere: lock the active approvals of the records' combinations, then the UNION of
    the records and every record of those approved combinations (a re-point locks them anyway), once, in pk order."""
    from apps.license.services.product_intelligence import import_item_approval as ia

    ids = set(ids)
    probe = list(LicenseImportItemsModel.objects.filter(pk__in=ids).select_related("hs_code"))
    combos = {(a.key_hash, a.hsn_code) for a in ia.coverage(probe).values()} | set(extra_combinations)
    ia.lock_approvals({kh for kh, _ in combos})
    for kh, hsn in sorted(combos):
        ids |= {r.pk for r in ia.records_for(kh, hsn)}
    if ids:
        list(LicenseImportItemsModel.objects.select_for_update(of=("self",)).filter(pk__in=ids).order_by("pk").values_list("pk", flat=True))


def preview(*, sion: str, target_id: int) -> dict:
    """Every candidate record of the SION grouped by (normalised description, HSN), with status and reason."""
    target = ItemNameModel.objects.prefetch_related("norms").select_related("sion_norm_class").filter(pk=target_id, is_active=True).first()
    if target is None:
        raise MatchValidationError("Unknown or inactive canonical master")
    if sion not in legit_sions(target):
        raise MatchValidationError(f"{target.name} is not a legitimate item for {sion}")
    target_core = identity_tokens(master_label(target.name))
    if not target_core:
        raise MatchValidationError(f"{target.name} has no usable product identity")
    chapters = _target_chapters(target)
    from apps.license.services.product_intelligence import import_item_approval as ia

    items = list(LicenseImportItemsModel.objects.filter(license__export_license__norm_class__norm_class=sion).distinct()
                 .select_related("hs_code", "license").prefetch_related("items").order_by("pk"))
    approvals = ia.coverage(items)
    overridden = _overridden_ids(i.pk for i in items)
    groups: dict[str, dict] = {}
    for item in items:
        description = (item.description or "").strip()
        if not (target_core & tokens(normalise(description))):
            continue
        hsn = getattr(item.hs_code, "hs_code", "") if item.hs_code_id else ""
        links = list(item.items.all())
        status, reason = classify_record(description, hsn, links, target=target, target_core=target_core, chapters=chapters)
        if reason == "Not a candidate":
            continue
        status, reason = approval_gate(status, reason, approvals.get(item.pk), links, target)
        status, reason = override_gate(status, reason, item.pk in overridden)
        key = source_key(normalise(description), hsn, sion)
        group = groups.setdefault(key, {
            "key": key, "description": description, "hsn_code": hsn, "sion": sion, "records": [], "statuses": Counter(),
            "reasons": set(), "current_masters": Counter(), "license_numbers": set(),
        })
        group["records"].append({"import_item_id": item.pk, "license_number": item.license.license_number, "status": status,
                                 "current_masters": [n.name for n in links]})
        group["statuses"][status] += 1
        group["reasons"].add(reason)
        group["license_numbers"].add(item.license.license_number)
        for n in links:
            group["current_masters"][n.name] += 1
    rows = []
    order = {ELIGIBLE: 0, REVIEW: 1, ALREADY: 2, EXCLUDED: 3}
    for g in groups.values():
        status = min(g["statuses"], key=lambda st: order[st]) if g["statuses"] else EXCLUDED
        if REVIEW in g["statuses"] and ELIGIBLE in g["statuses"]:
            status = REVIEW  # mixed groups (e.g. some records multi-linked) never move in bulk
        rows.append({
            "key": g["key"], "description": g["description"], "hsn_code": g["hsn_code"], "sion": sion, "status": status,
            "selectable": status == ELIGIBLE, "reasons": sorted(g["reasons"]), "record_count": len(g["records"]),
            "eligible_record_ids": sorted(r["import_item_id"] for r in g["records"] if r["status"] == ELIGIBLE),
            "record_ids": sorted(r["import_item_id"] for r in g["records"]), "license_numbers": sorted(g["license_numbers"])[:20],
            "current_masters": dict(g["current_masters"]), "proposed": target.name,
        })
    rows.sort(key=lambda r: (order[r["status"]], -r["record_count"], r["description"]))
    summary = Counter(r["status"] for r in rows)
    return {"sion": sion, "target": {"item_id": target.pk, "name": target.name, "chapters": sorted(chapters)},
            "summary": {"groups": dict(summary), "records": {st: sum(r["record_count"] for r in rows if r["status"] == st) for st in summary}},
            "rows": rows}


def apply(*, sion: str, target_id: int, keys: list[str], user, reason: str) -> dict:
    """Consolidate the selected ELIGIBLE groups (re-validated server-side). Idempotent; returns a batch id for revert."""
    reason = (reason or "").strip()
    if not reason:
        raise MatchValidationError("A reason is required for a bulk consolidation")
    if not keys:
        raise MatchValidationError("Select at least one candidate group")
    current = {r["key"]: r for r in preview(sion=sion, target_id=target_id)["rows"]}
    not_eligible = [k for k in keys if current.get(k, {}).get("status") != ELIGIBLE]
    if not_eligible:
        reasons = [f"{current[k]['description'][:60]}: {', '.join(current[k]['reasons'])}" if k in current else f"{k[:60]}: no longer a candidate" for k in not_eligible[:5]]
        raise MatchValidationError(f"{len(not_eligible)} selected group(s) are not eligible — nothing was changed. " + " | ".join(reasons))
    target = ItemNameModel.objects.get(pk=target_id)
    sion_obj = SionNormClassModel.objects.filter(norm_class=sion).first()
    from apps.license.models import MappingChange
    from apps.license.services.product_intelligence.propagation import record_change

    batch = uuid.uuid4().hex
    decisions, aliases, skipped_aliases = [], [], []
    target_core, chapters = identity_tokens(master_label(target.name)), _target_chapters(target)
    from apps.license.services.product_intelligence import import_item_approval as ia

    with transaction.atomic():
        # Lock every record first and re-classify it under the lock: a link / HSN / wording change after the preview
        # aborts the whole batch (all-or-nothing) instead of overwriting it.
        ids = sorted({i for k in keys for i in current[k]["eligible_record_ids"]})
        _lock_records(ids)  # approval rows, then the union of eligible + approved-combination records, pk order
        locked = {i.pk: i for i in LicenseImportItemsModel.objects.select_for_update(of=("self",)).filter(pk__in=ids).order_by("pk")
                  .select_related("hs_code").prefetch_related("items")}
        to_change: dict[int, list[int]] = {}
        approvals = ia.coverage(list(locked.values()))
        overridden = _overridden_ids(locked)
        repoints: dict[int, tuple[int, int]] = {}  # approval id -> (item id it pointed to, its version)
        for item_id in ids:
            item = locked.get(item_id)
            if item is None:
                raise MatchValidationError(f"Record #{item_id} no longer exists — nothing was changed")
            links = list(item.items.all())
            status, why = classify_record((item.description or "").strip(), getattr(item.hs_code, "hs_code", "") if item.hs_code_id else "",
                                          links, target=target, target_core=target_core, chapters=chapters)
            status, why = approval_gate(status, why, approvals.get(item_id), links, target)
            status, why = override_gate(status, why, item_id in overridden)
            if status not in {ELIGIBLE, ALREADY}:
                raise MatchValidationError(f"Record #{item_id} changed since the preview ({why}) — nothing was changed; refresh the preview")
            if status == ELIGIBLE:
                to_change[item_id] = sorted(n.pk for n in links)
                ap = approvals.get(item_id)
                if ap is not None and ap.item_id and ap.item_id != target.pk:
                    repoints[ap.pk] = (ap.item_id, ap.version)
        change = record_change(kind=MappingChange.CONSOLIDATION, user=user, source_model="license.ProductMatchDecision",
                               import_item_ids=set(to_change), detail={"batch": batch, "sion": sion, "target": target.name, "reason": reason})
        for key in keys:
            row = current[key]
            changed = [locked[i] for i in row["eligible_record_ids"] if i in to_change]
            if not changed:
                continue  # idempotent
            previous = {str(i.pk): to_change[i.pk] for i in changed}
            for item in changed:
                item.items.set([target])
            decision = ProductMatchDecision.objects.create(
                source_key=key, source_description=row["description"][:5000], normalized_description=normalise(row["description"])[:500],
                hsn_code=row["hsn_code"][:20], sion=sion_obj, import_item_ids=sorted(i.pk for i in changed), suggested_item=target,
                chosen_item=target, confidence=100, explanation=f"Bulk consolidation {batch}: {reason}"[:5000],
                checks={"bulk": {"ok": True, "detail": "; ".join(row["reasons"])}}, matcher=MATCHER, decision=ProductMatchDecision.APPROVED,
                previous_links={str(i.pk): previous[str(i.pk)] for i in changed}, new_links={str(i.pk): [target.pk] for i in changed},
                decided_by=user,
            )
            decisions.append(decision)
            try:
                with transaction.atomic():
                    aliases.append(create_alias(text=row["description"], item_id=target.pk, sion=sion, user=user,
                                                source=ProductAlias.DECISION, decision=decision).pk)
            except MatchValidationError as exc:
                skipped_aliases.append({"description": row["description"], "reason": str(exc)})
        change.source_refs = [d.pk for d in decisions]
        change.save(update_fields=["source_refs"])
        # Approvals whose Item Name was just replaced follow it to the target: versioned + audited, never silent.
        approval_repoints = []
        for approval_id in sorted(repoints):
            res = ia.repoint(approval_id, target.pk, user=user, expected_item_id=repoints[approval_id][0], expected_version=repoints[approval_id][1],
                             reason=f"bulk consolidation {batch}: {reason}"[:500])
            if res is None:
                raise MatchValidationError("An approved Description + HSN mapping changed during the consolidation — nothing was changed; refresh the preview")
            approval_repoints.append(res)
        ProductIntelAuditEvent.objects.create(action="bulk_consolidation", user=user, detail={"approval_repoints": approval_repoints,
            "batch": batch, "sion": sion, "target_id": target.pk, "target": target.name, "reason": reason, "mapping_change": change.pk,
            "decisions": [d.pk for d in decisions], "aliases": aliases, "skipped_aliases": skipped_aliases,
            "records": sum(len(d.import_item_ids) for d in decisions)})
    return {"batch": batch, "mapping_change": change.pk, "decisions": [d.pk for d in decisions], "records": sum(len(d.import_item_ids) for d in decisions),
            "aliases": aliases, "skipped_aliases": skipped_aliases, "approval_repoints": approval_repoints}


def revert(*, batch: str, user) -> dict:
    """Restore the links a batch replaced (only where they are still the batch's links); deactivate its aliases."""
    from apps.license.models import MappingChange
    from apps.license.services.product_intelligence.propagation import record_change

    restored, conflicts = 0, []
    with transaction.atomic():
        # The batch event row is the lock: two concurrent reverts serialise and the second sees the first.
        event = ProductIntelAuditEvent.objects.select_for_update().filter(action="bulk_consolidation", detail__batch=batch).first()
        if event is None:
            raise MatchValidationError("Unknown consolidation batch")
        if ProductIntelAuditEvent.objects.filter(action="bulk_consolidation_reverted", detail__batch=batch).exists():
            raise MatchValidationError("This batch was already reverted")
        decisions = ProductMatchDecision.objects.filter(pk__in=event.detail.get("decisions") or []).order_by("pk")
        from apps.license.services.product_intelligence import import_item_approval as ia

        repointed = event.detail.get("approval_repoints") or []
        repointed_rows = {a.pk: a for a in ia.A.objects.filter(pk__in=[r["approval_id"] for r in repointed])}
        # Lock order approval -> records: every approval covering a batch record (and the re-pointed ones), then all the records once.
        all_ids = {i for d in decisions for i in d.import_item_ids}
        _lock_records(all_ids, extra_combinations={(a.key_hash, a.hsn_code) for a in repointed_rows.values()})
        list(ia.A.objects.select_for_update(no_key=True).filter(pk__in=[r["approval_id"] for r in repointed]).order_by("pk").values_list("pk", flat=True))
        # Re-pointed approvals that are still exactly what this batch made them (item + version); anything else is a later decision.
        batch_approvals = {r["approval_id"] for r in repointed
                           if (a := ia.A.objects.filter(pk=r["approval_id"]).first()) is not None and a.is_active
                           and a.item_id == r["to_item_id"] and a.version == r["version"]}
        overridden = _overridden_ids(all_ids)
        covering = ia.coverage(list(LicenseImportItemsModel.objects.filter(pk__in=all_ids).select_related("hs_code")))
        change = record_change(kind=MappingChange.CONSOLIDATION_REVERT, user=user, source_model="license.ProductMatchDecision",
                               source_refs=[d.pk for d in decisions], import_item_ids={i for d in decisions for i in d.import_item_ids},
                               detail={"batch": batch})
        for d in decisions:
            items = {str(i.pk): i for i in LicenseImportItemsModel.objects.select_for_update().filter(pk__in=d.import_item_ids).order_by("pk").prefetch_related("items")}
            done: dict[str, list[int]] = {}
            for item_id, previous in (d.previous_links or {}).items():
                item = items.get(item_id)
                if item is None:
                    conflicts.append({"import_item_id": item_id, "reason": "record no longer exists"})
                    continue
                if item.pk in overridden:
                    conflicts.append({"import_item_id": item_id, "reason": "a row override was created since the consolidation — left as is"})
                    continue
                cover = covering.get(item.pk)
                if cover is not None and cover.pk not in batch_approvals:
                    conflicts.append({"import_item_id": item_id, "reason": "an approved Description + HSN mapping now decides this record — left as is"})
                    continue
                now = sorted(n.pk for n in item.items.all())
                if now != (d.new_links or {}).get(item_id):
                    conflicts.append({"import_item_id": item_id, "reason": "links changed since the consolidation — left as is"})
                    continue
                item.items.set(previous)
                done[item_id] = previous
                restored += 1
            if done:  # the audit records exactly what was restored
                ProductMatchDecision.objects.create(
                    source_key=d.source_key, source_description=d.source_description, normalized_description=d.normalized_description,
                    hsn_code=d.hsn_code, sion=d.sion, import_item_ids=sorted(int(k) for k in done), suggested_item=d.chosen_item, chosen_item=None,
                    confidence=0, explanation=f"Revert of bulk consolidation {batch}", matcher=MATCHER, decision=ProductMatchDecision.REJECTED,
                    previous_links={k: (d.new_links or {}).get(k) for k in done}, new_links=done, decided_by=user)
            if len(done) == len(d.previous_links or {}):
                ProductAlias.objects.filter(decision=d).update(is_active=False)  # only aliases of fully restored decisions
        approvals_back = []
        for r in repointed:  # re-point back (versioned) only while the approval is still exactly what the consolidation made it
            res = ia.repoint(r["approval_id"], r["from_item_id"], user=user, expected_item_id=r["to_item_id"], expected_version=r["version"],
                             reason=f"revert of bulk consolidation {batch}")
            if res is None:
                conflicts.append({"approval_id": r["approval_id"], "reason": "approved Description + HSN mapping changed since the consolidation — left as is"})
            else:
                approvals_back.append(res)
        ProductIntelAuditEvent.objects.create(action="bulk_consolidation_reverted", user=user,
                                              detail={"batch": batch, "restored": restored, "conflicts": conflicts, "mapping_change": change.pk,
                                                      "approval_repoints": approvals_back})
    return {"batch": batch, "restored": restored, "conflicts": conflicts, "mapping_change": change.pk}


def batches(limit: int = 20) -> list[dict]:
    reverted = set(ProductIntelAuditEvent.objects.filter(action="bulk_consolidation_reverted").values_list("detail__batch", flat=True))
    out = []
    for e in ProductIntelAuditEvent.objects.filter(action="bulk_consolidation").select_related("user")[:limit]:
        out.append({"batch": e.detail.get("batch"), "sion": e.detail.get("sion"), "target": e.detail.get("target"), "records": e.detail.get("records"),
                    "reason": e.detail.get("reason"), "user": getattr(e.user, "username", None), "on": e.created_on.isoformat(),
                    "reverted": e.detail.get("batch") in reverted})
    return out


__all__ = ["apply", "batches", "classify_record", "identity_tokens", "preview", "revert"]
