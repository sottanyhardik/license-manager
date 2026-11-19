"""Item Name mapping for BOE and allotment descriptions (Mapping workspace, owner spec 2026-11-19).

All three mapping sources target the SAME master — ``ItemNameModel`` (the Item Name master Item Pivot uses):

* licence import items → ``LicenseImportItemsModel.items`` (Product Matching approvals, ``product_matching.decide``);
* BOEs → ``BillOfEntryModel.planning_target_item``; allotments → ``AllotmentModel.planning_target_item``.

BOE / allotment targets are validated with the existing domain contract ``validate_explicit_target`` for every
import item the record debits (the target must be a legitimate planning target under that licence's active SION
rules), exactly like the BOE / allotment forms. Writes go through ``save()`` so the existing mapping-change signal
versions the change (``MappingChange``) and re-plans the affected licences. Descriptions, quantities, CIF and debit
rows are never touched — mapping is classification, not a financial transaction.

Suggestions are never approvals: an approved mapping of the same wording in another source (licence import item
decision, approved alias, or a user-selected BOE / allotment target) only raises the suggestion's confidence.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from apps.core.models import ItemNameModel
from apps.license.models import ProductIntelAuditEvent
from apps.license.services.planning_actual_target_mapping import prime_target_cache, resolve_targets_for_source, validate_explicit_target
from apps.license.services.product_matching import MatchValidationError, normalise, product_segments, text_score

PENDING = ("UNMAPPED_AMBIGUOUS", "UNMAPPED_NO_TARGET", "INVALID_PERSISTED_TARGET", "")
KINDS = ("boe", "allotment")
MAX_PAGE = 100
MAX_RECORDS = 2000
COUNTS_CACHE_KEY = "item_name_mapping_counts_v1"


def _models(kind: str):
    from apps.allotment.models import AllotmentItems, AllotmentModel
    from apps.bill_of_entry.models import BillOfEntryModel, RowDetails

    if kind == "boe":
        return BillOfEntryModel, RowDetails, "bill_of_entry_id", "sr_number", "product_name"
    if kind == "allotment":
        return AllotmentModel, AllotmentItems, "allotment_id", "item", "item_name"
    raise MatchValidationError("Unknown mapping source")


def _pending_headers(kind: str, q: str = ""):
    """Pending headers that debit at least one licence import item (nothing debited → nothing to map)."""
    Header, Child, fk, item_field, desc_field = _models(kind)
    debits = Child.objects.filter(**{fk: OuterRef("pk"), f"{item_field}__isnull": False})
    qs = Header.objects.filter(Q(planning_mapping_status__in=PENDING) | Q(planning_mapping_status__isnull=True)).filter(Exists(debits))
    if q:
        qs = qs.filter(**{f"{desc_field}__icontains": q})
    return qs


def _sources(kind: str, record_ids, *, lock: bool = False) -> dict[int, list]:
    """record id → the licence import items it debits (with HSN + master links for target resolution).
    ``lock``: also row-lock the debit rows so a concurrent re-point cannot invalidate the validation.
    Debit rows are read as (record, import item) id pairs; each distinct import item is loaded once."""
    from apps.license.models import LicenseImportItemsModel

    _, Child, fk, item_field, _ = _models(kind)
    rows = Child.objects.filter(**{f"{fk}__in": list(record_ids)}).exclude(**{f"{item_field}__isnull": True})
    if lock:
        list(rows.select_for_update(of=("self",)).order_by("pk").values_list("pk", flat=True))
    pairs = set(rows.values_list(fk, f"{item_field}_id"))
    items = {i.pk: i for i in LicenseImportItemsModel.objects.filter(pk__in={item_id for _, item_id in pairs})
             .select_related("hs_code", "license")
             .only("id", "license_id", "license__license_number", "hs_code_id", "hs_code__hs_code", "description", "quantity",
                   "available_quantity", "unit", "serial_number")
             .prefetch_related("items")}
    out: dict[int, dict] = defaultdict(dict)
    for record_id, item_id in pairs:
        out[record_id][item_id] = items[item_id]
    return {rid: [found[k] for k in sorted(found)] for rid, found in out.items()}


def legitimate_targets(source_items, memo: dict | None = None, resolver_cache: dict | None = None) -> set[int]:
    """Item Names legitimate for EVERY debited import item (intersection) — one target must fit the whole record.
    ``memo``: per import item; ``resolver_cache``: SION + rules loaded once per request (see resolve_targets_for_source)."""
    memo = {} if memo is None else memo
    sets = []
    for item in source_items:
        if item.pk not in memo:  # many BOEs / allotments debit the same import item
            memo[item.pk] = set(resolve_targets_for_source(item, resolver_cache).target_ids)
        sets.append(memo[item.pk])
    return set.intersection(*sets) if sets else set()


def approved_evidence(wordings) -> dict[str, dict[int, list[str]]]:
    """normalised wording → {Item Name id: [why]} from human-approved mappings of every source (suggestions only),
    restricted to the given normalised wordings."""
    from apps.license.models import ProductAlias, ProductMatchDecision

    wordings = set(wordings)
    out: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    if not wordings:
        return out
    approvals = list(ProductMatchDecision.objects.filter(decision=ProductMatchDecision.APPROVED, chosen_item__isnull=False,
                                                         normalized_description__in=wordings).values("pk", "normalized_description", "chosen_item_id"))
    undone = undone_import_decision_ids(d["pk"] for d in approvals)  # an undone approval is no evidence
    for d in approvals:
        if d["pk"] in undone:
            continue
        out[d["normalized_description"]][d["chosen_item_id"]].append(f"Licence import item approval #{d['pk']}")
    for a in ProductAlias.objects.filter(deactivated_on__isnull=True, normalized_alias__in=wordings).values("pk", "normalized_alias", "item_id"):
        out[a["normalized_alias"]][a["item_id"]].append(f"Approved alias #{a['pk']}")
    for kind in KINDS:
        Header, _, _, _, desc_field = _models(kind)
        label = "BOE" if kind == "boe" else "Allotment"
        # User-selected targets are a small, human-curated set; wording is normalised in Python (not DB-computable).
        for h in Header.objects.filter(planning_mapping_status="MAPPED_EXPLICIT", planning_mapping_source="USER_SELECTED",
                                       planning_target_item__isnull=False).values("pk", desc_field, "planning_target_item_id"):
            norm = normalise(h[desc_field])
            if norm in wordings:
                out[norm][h["planning_target_item_id"]].append(f"{label} #{h['pk']} approved")
    return out


def _master_chapters(item_ids) -> dict[int, set[str]]:
    from apps.license.services.product_matching import _master_hsn_chapters

    return _master_hsn_chapters(set(item_ids))


def _suggest(description: str, legit: list[int], names: dict[int, str], evidence: dict[int, list[str]]) -> tuple[dict | None, list[dict]]:
    """Best legitimate Item Name + similar ones. Only targets the validator would accept are ever suggested."""
    scored = []
    for item_id in legit:
        score, reasons = text_score(description, names.get(item_id, ""))
        why = evidence.get(item_id)
        if why:
            score, reasons = 100, [f"Same wording approved in another source: {', '.join(why[:3])}", *reasons]
        scored.append({"item_id": item_id, "name": names.get(item_id), "confidence": score, "explanation": "; ".join(reasons) or "Legitimate under the SION rules"})
    scored.sort(key=lambda c: (-c["confidence"], c["name"] or ""))
    if not scored:
        return None, []
    best = dict(scored[0])
    if len(legit) == 1 and best["confidence"] < 100:
        best["explanation"] = f"Only legitimate Item Name under the SION rules; {best['explanation']}"
    return best, scored[1:6]


def queue(kind: str, *, q: str = "", offset: int = 0, limit: int = 50) -> dict:
    """Pending records grouped by distinct normalised description (paged), with suggestions and conflict flags."""
    Header, Child, fk, item_field, desc_field = _models(kind)
    offset, limit = max(0, int(offset)), max(1, min(int(limit), MAX_PAGE))
    extra = ["bill_of_entry_number", "bill_of_entry_date"] if kind == "boe" else []
    headers = list(_pending_headers(kind, q).order_by("-pk").values("pk", desc_field, "planning_mapping_status", *extra))
    by_desc: dict[str, list[dict]] = defaultdict(list)
    normalised: dict[str, str] = {}  # thousands of headers share a few hundred raw wordings
    for h in headers:
        raw = h[desc_field] or ""
        if raw not in normalised:
            normalised[raw] = normalise(raw)
        by_desc[normalised[raw]].append(h)
    ordered = sorted(by_desc.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    page = ordered[offset:offset + limit]
    page_ids = [h["pk"] for _, hs in page for h in hs]
    sources = _sources(kind, page_ids)
    qty: dict[int, Decimal] = defaultdict(Decimal)
    for row in Child.objects.filter(**{f"{fk}__in": page_ids}).exclude(**{f"{item_field}__isnull": True}).values(fk, "qty"):
        qty[row[fk]] += row["qty"] or Decimal("0")
    licence_ids = {i.license_id for items in sources.values() for i in items}
    from apps.license.models import LicenseExportItemModel

    sion_by_licence: dict[int, set[str]] = defaultdict(set)
    for e in LicenseExportItemModel.objects.filter(license_id__in=licence_ids, norm_class__isnull=False).values("license_id", "norm_class__norm_class"):
        sion_by_licence[e["license_id"]].add(e["norm_class__norm_class"])
    memo: dict[int, set[int]] = {}
    resolver_cache = prime_target_cache({}, licence_ids)
    evidence = approved_evidence(norm for norm, _ in page)
    rows = []
    for norm, hs in page:
        split: dict[tuple, list[dict]] = defaultdict(list)  # one row per legitimate-target set: one target must fit every record
        for h in hs:
            split[tuple(sorted(legitimate_targets(sources.get(h["pk"], []), memo, resolver_cache)))].append(h)
        for legit, members in split.items():
            items = [i for h in members for i in sources.get(h["pk"], [])]
            rows.append({"norm": norm, "legit": list(legit), "members": members, "items": items})
    all_ids = {i for r in rows for i in r["legit"]}
    names = dict(ItemNameModel.objects.filter(pk__in=all_ids).values_list("pk", "name"))
    chapters = _master_chapters(all_ids)
    out = []
    for r in rows:
        members, items = r["members"], r["items"]
        description = (members[0][desc_field] or "").strip()
        hsn = sorted({(i.hs_code.hs_code if i.hs_code_id else "") for i in items} - {""})
        sions = sorted({s for i in items for s in sion_by_licence.get(i.license_id, set())})
        suggestion, similar = _suggest(description, r["legit"], names, evidence.get(r["norm"], {}))
        conflicts = []
        if not r["legit"]:
            conflicts.append({"code": "SION", "detail": "No Item Name is a legitimate planning target for every debited import item under the active SION rules"})
        if len(sions) > 1:
            conflicts.append({"code": "SION", "detail": f"Records debit licences of several SION norms ({', '.join(sions)})"})
        if suggestion:
            known = chapters.get(suggestion["item_id"], set())
            if known and hsn and not any(h[:2] in known for h in hsn):
                conflicts.append({"code": "HSN", "detail": f"HSN {', '.join(hsn[:3])} differs from {suggestion['name']}'s chapters {', '.join(sorted(known))}"})
        segments = product_segments(description)
        if len(segments) > 1:
            conflicts.append({"code": "MULTI_PRODUCT", "detail": f"Description names {len(segments)} products ({'; '.join(segments[:4])}) — review individually; never bulk"})
        statuses: dict[str, int] = defaultdict(int)
        for h in members:
            statuses[h["planning_mapping_status"] or "UNMAPPED"] += 1
        record_ids = sorted(h["pk"] for h in members)
        row = {
            "key": f"{kind}:{r['norm']}:{'-'.join(map(str, r['legit']))}", "description": description, "record_ids": record_ids,
            "records": len(record_ids), "statuses": dict(statuses),
            "licence_count": len({i.license_id for i in items}), "licence_numbers": sorted({i.license.license_number for i in items})[:10],
            "hsn_codes": hsn, "sion": sions, "quantity": str(sum((qty[h["pk"]] for h in members), Decimal("0"))),
            "units": sorted({i.unit for i in items if i.unit}),
            "legitimate": [{"item_id": i, "name": names.get(i)} for i in r["legit"]], "mappable": bool(r["legit"]),
            "suggestion": suggestion, "similar": similar, "conflicts": conflicts,
        }
        if kind == "boe":
            dated = sorted(members, key=lambda h: (h["bill_of_entry_date"] is not None, h["bill_of_entry_date"]), reverse=True)  # newest first, undated last
            row["boe_numbers"] = [h["bill_of_entry_number"] for h in dated[:5]]
            row["latest_boe_date"] = next((h["bill_of_entry_date"].isoformat() for h in dated if h["bill_of_entry_date"]), None)
        out.append(row)
    return {"kind": kind, "groups": out, "total_groups": len(ordered), "total_records": len(headers), "offset": offset, "limit": limit}


def apply_entries(*, kind: str, entries: list[dict], user, reason: str = "") -> dict:
    """Map each entry's records to ITS OWN selected, existing, active Item Name. One transaction, all-or-nothing:
    every record of every entry is validated first; any failure → nothing is written (the entries stay pending).
    Idempotent and retry-safe: records already mapped to the chosen Item Name are reported unchanged.

    Only pending records (or records already explicitly mapped to the same Item Name) may be mapped here; a record
    with a deterministic / conditional / other explicit target is changed from its own form. The whole call is ONE
    mapping version (``MappingChange``): affected plans are archived once and each affected licence re-plans once."""
    from apps.license.models import MappingChange
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    Header, _, _, _, desc_field = _models(kind)
    if not entries:
        raise MatchValidationError("Select at least one entry")
    bulk = len(entries) > 1
    clean = []
    for n, entry in enumerate(entries, 1):
        ids, item_id = entry.get("record_ids"), entry.get("item_id")
        ids_ok = isinstance(ids, list) and bool(ids) and all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
        if not ids_ok or not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0:
            raise MatchValidationError(f"Entry {n}: each entry needs its own selected Item Name and records")
        clean.append((sorted(set(ids)), item_id))
    all_ids = [i for ids, _ in clean for i in ids]
    if len(all_ids) != len(set(all_ids)):
        raise MatchValidationError("A record appears in more than one entry")
    if len(all_ids) > MAX_RECORDS:
        raise MatchValidationError(f"At most {MAX_RECORDS} records per approval — approve in smaller batches")
    items = {i.pk: i for i in ItemNameModel.objects.filter(pk__in={item_id for _, item_id in clean}, is_active=True)}
    if {item_id for _, item_id in clean} - set(items):
        raise MatchValidationError("Choose an existing, active Item Name (create it in Masters → Item Names first if it is missing)")
    with transaction.atomic():
        locked = {r.pk: r for r in Header.objects.select_for_update(of=("self",)).filter(pk__in=all_ids).order_by("pk")}
        if len(locked) != len(all_ids):
            raise MatchValidationError("Some records no longer exist")
        sources = _sources(kind, all_ids, lock=True)
        verdicts: dict[tuple[int, int], str | None] = {}  # (import item, Item Name) → None if legitimate, else the reason
        resolver_cache = prime_target_cache({}, {i.license_id for items_ in sources.values() for i in items_})
        failures = []
        for ids, item_id in clean:
            item = items[item_id]
            for pk in ids:
                rec = locked[pk]
                status = rec.planning_mapping_status or ""
                if status not in PENDING and not (status == "MAPPED_EXPLICIT" and rec.planning_target_item_id == item.pk):
                    failures.append(f"#{pk}: already mapped ({status.replace('_', ' ').lower()}) — change it from its own record")
                    continue
                if bulk and len(product_segments(getattr(rec, desc_field))) > 1:
                    failures.append(f"#{pk}: multi-product description — map it individually")
                    continue
                debited = sources.get(pk, [])
                if not debited:
                    failures.append(f"#{pk}: debits no licence import item yet")
                    continue
                for source in debited:
                    key = (source.pk, item.pk)
                    if key not in verdicts:
                        try:
                            validate_explicit_target(source, item.pk, resolver_cache)
                            verdicts[key] = None
                        except ValueError as exc:
                            verdicts[key] = str(exc)
                    if verdicts[key] is not None:
                        failures.append(f"#{pk}: {item.name} is not a legitimate planning target for import item #{source.pk} "
                                        f"({(source.description or '')[:60]}) under its SION rules ({verdicts[key]})")
                        break
        if failures:
            raise MatchValidationError(f"{len(failures)} record(s) failed validation — nothing was mapped. " + " | ".join(failures[:5]))
        pending_writes, unchanged = [], 0
        for ids, item_id in clean:
            for pk in ids:
                rec = locked[pk]
                if rec.planning_target_item_id == item_id and rec.planning_mapping_status == "MAPPED_EXPLICIT":
                    unchanged += 1  # idempotent / retry-safe
                else:
                    pending_writes.append((rec, items[item_id]))
        if not pending_writes:
            return {"kind": kind, "mapped": 0, "unchanged": unchanged, "item_ids": sorted(items),
                    "item": items[clean[0][1]].name if len(items) == 1 else None, "mapping_versions": []}
        licence_ids = sorted({i.license_id for rec, _ in pending_writes for i in sources.get(rec.pk, [])})
        from apps.license.models import LicenseExportItemModel

        sion_by_licence: dict[int, set[str]] = defaultdict(set)
        for e in LicenseExportItemModel.objects.filter(license_id__in=licence_ids, norm_class__isnull=False).values("license_id", "norm_class__norm_class"):
            sion_by_licence[e["license_id"]].add(e["norm_class__norm_class"])
        changed = []
        for rec, item in pending_writes:
            debited = sources.get(rec.pk, [])
            changed.append({"id": rec.pk, "description": (getattr(rec, desc_field) or "")[:200], "item_id": item.pk, "item": item.name,
                            "previous_target": rec.planning_target_item_id, "previous_status": rec.planning_mapping_status, "new_target": item.pk,
                            "hsn_codes": sorted({i.hs_code.hs_code for i in debited if i.hs_code_id}),
                            "sion": sorted({sn for i in debited for sn in sion_by_licence.get(i.license_id, set())}),
                            "import_item_ids": sorted(i.pk for i in debited), "licence_ids": sorted({i.license_id for i in debited}),
                            "validation": "PASSED: legitimate planning target for every debited import item (validate_explicit_target)"})
        # ONE mapping version for the whole approval, recorded BEFORE any write (the archive holds the superseded plans).
        change = record_change(kind=MappingChange.BOE_TARGET if kind == "boe" else MappingChange.ALLOTMENT_TARGET, user=user,
                               source_model=Header._meta.label, source_refs=[c["id"] for c in changed], license_ids=licence_ids,
                               detail={"source": "mapping_workspace", "bulk": bulk, "records": [
                                   {k: c[k] for k in ("id", "previous_target", "previous_status", "new_target")} for c in changed]})
        for rec, item in pending_writes:
            rec.planning_target_item = item
            rec.planning_mapping_status, rec.planning_mapping_source = "MAPPED_EXPLICIT", "USER_SELECTED"
            rec._orig_debit_target = item.pk  # versioned above as one change — the per-record signal must not re-version it
            fields = ["planning_target_item", "planning_mapping_status", "planning_mapping_source"]
            if hasattr(rec, "modified_by"):
                rec.modified_by = user
                fields.append("modified_by")
            # update_fields only: the models' save() recomputes money fields in memory (exchange rate / CIF) — never persisted here.
            rec.save(update_fields=fields + (["modified_on"] if hasattr(rec, "modified_on") else []))
        for license_id in licence_ids:
            mark_license_replan_source_changed(license_id=license_id, reason="debit_target_changed", source_model="license.MappingChange", source_pk=change.pk)
        for c in changed:
            c["mapping_version"] = change.pk
        ProductIntelAuditEvent.objects.create(action=f"{kind}_item_name_mapped", user=user, detail={
            "items": sorted({i.name for i in items.values()}), "item_ids": sorted(items), "bulk": bulk, "reason": reason[:500],
            "mapping_version": change.pk, "records": changed})
        transaction.on_commit(drop_counts_cache)
    return {"kind": kind, "mapped": len(changed), "unchanged": unchanged, "item_ids": sorted(items),
            "item": items[clean[0][1]].name if len(items) == 1 else None, "mapping_versions": [change.pk]}


def apply_target(*, kind: str, record_ids: list[int], item_id: int, user, reason: str = "") -> dict:
    """Map the records to one existing, active Item Name (single entry of ``apply_entries``)."""
    if not record_ids:
        raise MatchValidationError("Select at least one record")
    return apply_entries(kind=kind, entries=[{"record_ids": record_ids, "item_id": item_id}], user=user, reason=reason)


def history(kind: str, *, offset: int = 0, limit: int = 50) -> dict:
    """Approved mapping history (newest first): import-item decisions, or BOE / allotment mapping audit events."""
    offset, limit = max(0, int(offset)), max(1, min(int(limit), MAX_PAGE))
    if kind == "import":
        from apps.license.models import ProductMatchDecision

        qs = ProductMatchDecision.objects.filter(decision=ProductMatchDecision.APPROVED).select_related("chosen_item", "decided_by", "sion").order_by("-pk")
        page = list(qs[offset:offset + limit])
        undone = undone_import_decision_ids(d.pk for d in page)
        rows = [{"id": d.pk, "description": d.source_description[:300], "item_id": d.chosen_item_id, "item": getattr(d.chosen_item, "name", None),
                 "hsn_codes": [d.hsn_code] if d.hsn_code else [], "sion": getattr(d.sion, "norm_class", None), "records": len(d.import_item_ids),
                 "previous": d.previous_links, "by": getattr(d.decided_by, "username", None), "on": d.decided_on.isoformat(),
                 "undone": d.pk in undone} for d in page]
        return {"kind": kind, "rows": rows, "total": qs.count()}
    _models(kind)
    # Paged by mapped RECORD (one bulk event can hold many records), newest event first.
    rows, total = [], 0
    events = ProductIntelAuditEvent.objects.filter(action=f"{kind}_item_name_mapped").select_related("user").order_by("-pk")
    for ev in events.iterator(chunk_size=200):
        for rec in ev.detail.get("records", []):
            if offset <= total < offset + limit:
                rows.append({"id": rec.get("id"), "event": ev.pk, "description": rec.get("description"), "item_id": rec.get("item_id", rec.get("new_target")),
                             "item": rec.get("item"), "hsn_codes": rec.get("hsn_codes", []), "sion": ", ".join(rec.get("sion") or []) or None,
                             "previous": rec.get("previous_target"), "mapping_version": rec.get("mapping_version"),
                             "by": getattr(ev.user, "username", None), "on": ev.created_on.isoformat()})
            total += 1
    return {"kind": kind, "rows": rows, "total": total}


UNDO_ACTION = "import_item_mapping_undone"


def undone_import_decision_ids(ids=None) -> set[int]:
    """Licence import item approvals (``ProductMatchDecision`` ids) reversed by Undo. The approval row itself is never
    changed or deleted — the reversal is its own audit event (user + timestamp), so the history stays complete."""
    qs = ProductIntelAuditEvent.objects.filter(action=UNDO_ACTION)
    if ids is not None:
        ids = list(ids)
        if not ids:
            return set()
        qs = qs.filter(detail__decision_id__in=ids)
    return {int(v) for v in qs.values_list("detail__decision_id", flat=True) if v is not None}


def _undone_ids_subquery():
    from django.db.models import IntegerField
    from django.db.models.fields.json import KT
    from django.db.models.functions import Cast

    # NULL-free: a NULL in a NOT IN list would exclude every row.
    return (ProductIntelAuditEvent.objects.filter(action=UNDO_ACTION, detail__decision_id__isnull=False)
            .annotate(decision_pk=Cast(KT("detail__decision_id"), IntegerField())).values("decision_pk"))


def _later_approvals(source_key, pk):
    """Approvals of the same source after ``pk`` that are still in force (an undone later approval does not count)."""
    from apps.license.models import ProductMatchDecision

    return (ProductMatchDecision.objects.filter(source_key=source_key, decision=ProductMatchDecision.APPROVED, pk__gt=pk)
            .exclude(pk__in=_undone_ids_subquery()))


def _active_import_approvals():
    """Approved import-item decisions that are still the active mapping of their source: not undone, and no later
    approval of the same source key that is itself still in force."""
    from apps.license.models import ProductMatchDecision

    return (ProductMatchDecision.objects.filter(decision=ProductMatchDecision.APPROVED, chosen_item__isnull=False)
            .exclude(pk__in=_undone_ids_subquery()).filter(~Exists(_later_approvals(OuterRef("source_key"), OuterRef("pk")))))


def import_approved(*, q: str = "", offset: int = 0, limit: int = 50) -> dict:
    """Active licence import item mappings (Approved Mappings table), newest first, searchable and paged."""
    offset, limit = max(0, int(offset)), max(1, min(int(limit), MAX_PAGE))
    qs = _active_import_approvals().select_related("chosen_item", "decided_by", "sion")
    if q:
        qs = qs.filter(Q(source_description__icontains=q) | Q(chosen_item__name__icontains=q) | Q(hsn_code__icontains=q) | Q(sion__norm_class__icontains=q))
    qs = qs.order_by("-decided_on", "-pk")
    rows = [{"id": d.pk, "description": d.source_description, "hsn_code": d.hsn_code or None, "sion": getattr(d.sion, "norm_class", None),
             "item_id": d.chosen_item_id, "item": d.chosen_item.name, "records": len(d.import_item_ids or []), "status": "APPROVED",
             "by": getattr(d.decided_by, "username", None), "on": d.decided_on.isoformat()} for d in qs[offset:offset + limit]]
    return {"rows": rows, "total": qs.count(), "offset": offset, "limit": limit}


def undo_import_approval(*, decision_id: int, user) -> dict:
    """Reverse one active licence import item approval (Mapping workspace → Approved Mappings → Undo).

    All-or-nothing and idempotent: the approval row is locked, so concurrent / repeated Undo requests serialise and
    every request after the first returns ``already_undone``. The import items get back exactly the links they had
    before the approval (``previous_links``), and only while they still hold the approval's links. The approval row,
    Item Name master, mapping versions and audit history are never changed or deleted; the reversal is versioned
    (``MappingChange``) and the affected licences re-plan. Descriptions, quantities and CIF are never touched.
    """
    from apps.license.models import LicenseImportItemsModel, MappingChange, ProductAlias, ProductMatchDecision
    from apps.license.services.product_intelligence.propagation import record_change
    from apps.license.services.replan_requests import mark_license_replan_source_changed

    with transaction.atomic():
        decision = (ProductMatchDecision.objects.select_for_update().select_related("chosen_item")
                    .filter(pk=decision_id, decision=ProductMatchDecision.APPROVED, chosen_item__isnull=False).first())
        if decision is None:
            raise MatchValidationError("Unknown approved mapping")
        if undone_import_decision_ids([decision.pk]):
            return {"decision_id": decision.pk, "undone": False, "already_undone": True, "restored": 0}
        ids = sorted({int(i) for i in decision.import_item_ids or []})
        items = {str(i.pk): i for i in LicenseImportItemsModel.objects.select_for_update().filter(pk__in=ids).order_by("pk").prefetch_related("items")}
        # Checked AFTER the record locks: an approval of the same source committed while we waited is seen here.
        if _later_approvals(decision.source_key, decision.pk).exists():
            raise MatchValidationError("A later approval replaced this mapping — undo that one instead")
        changed = [k for k in map(str, ids) if k not in items or sorted(n.pk for n in items[k].items.all()) != sorted((decision.new_links or {}).get(k) or [])]
        if changed:
            raise MatchValidationError(f"{len(changed)} source record(s) changed since this approval — nothing was undone")
        restored = {k: sorted((decision.previous_links or {}).get(k) or []) for k in items}
        change = record_change(kind=MappingChange.MATCH_DECISION, user=user, source_model="license.ProductMatchDecision",
                               source_refs=[decision.pk], import_item_ids=ids,
                               detail={"undo_of": decision.pk, "description": decision.source_description[:200],
                                       "previous": decision.new_links, "new": restored})
        for k, item in items.items():
            item.items.set(restored[k])
        for licence_id in sorted({i.license_id for i in items.values()}):
            mark_license_replan_source_changed(license_id=licence_id, reason="item_master_link_changed",
                                               source_model="license.MappingChange", source_pk=change.pk, dispatch=True)
        # The alias this approval created would keep suggesting the undone Item Name at 100 % — deactivate it (kept, audited).
        from django.utils import timezone
        # A re-approval reactivates the existing alias without re-pointing its ``decision`` — match the wording too.
        aliases = list(ProductAlias.objects.filter(is_active=True).filter(
            Q(decision=decision) | Q(source=ProductAlias.DECISION, normalized_alias=normalise(decision.source_description)[:500],
                                     item_id=decision.chosen_item_id, sion_id=decision.sion_id)).values_list("pk", flat=True))
        ProductAlias.objects.filter(pk__in=aliases).update(is_active=False, deactivated_on=timezone.now())
        ProductIntelAuditEvent.objects.create(action=UNDO_ACTION, user=user, detail={
            "decision_id": decision.pk, "source_key": decision.source_key, "description": decision.source_description[:300],
            "item_id": decision.chosen_item_id, "item": decision.chosen_item.name, "import_item_ids": ids,
            "links_before_undo": decision.new_links, "links_after_undo": restored, "aliases_deactivated": aliases,
            "mapping_version": change.pk})
        transaction.on_commit(drop_counts_cache)
    return {"decision_id": decision.pk, "undone": True, "already_undone": False, "restored": len(items), "mapping_version": change.pk}


def counts(*, fresh: bool = False) -> dict:
    """Pending counts per source: BOE / allotment records + distinct names without a saved name mapping; licence import items whose master
    link is missing or ambiguous (0 or several Item Names), as distinct descriptions. Cached 60 s (dropped on approval)."""
    from django.core.cache import cache

    cached = None if fresh else cache.get(COUNTS_CACHE_KEY)
    if cached is not None:
        return cached
    out = _counts()
    cache.set(COUNTS_CACHE_KEY, out, 60)
    return out


def drop_counts_cache() -> None:
    from django.core.cache import cache

    cache.delete(COUNTS_CACHE_KEY)


def _counts() -> dict:
    from apps.license.models import ImportDescriptionMapping, LicenseImportItemsModel, SourceNameMapping
    from apps.license.services.product_intelligence.description_mapping import description_key, key_hash

    out = {}
    for kind in KINDS:
        # Unique BOE Product Names / Allotment Item Names (strict key) without a saved name mapping ("Mapping Required").
        Header, _, _, _, desc_field = _models(kind)
        code = SourceNameMapping.BOE if kind == "boe" else SourceNameMapping.ALLOTMENT
        saved = set(SourceNameMapping.objects.filter(kind=code, is_active=True).values_list("key_hash", flat=True))
        name_keys: dict[str, str] = {}
        records = 0
        for name in Header.objects.exclude(**{desc_field: ""}).values_list(desc_field, flat=True):
            if name not in name_keys:
                name_keys[name] = description_key(name)
            if name_keys[name] and key_hash(name_keys[name]) not in saved:
                records += 1
        out[kind] = {"records": records, "descriptions": len({k for k in name_keys.values() if k and key_hash(k) not in saved})}
    # Licence import items: unique descriptions (strict key) without a saved description mapping ("Mapping Required").
    mapped = set(ImportDescriptionMapping.objects.filter(is_active=True).values_list("key_hash", flat=True))
    keys: dict[str, str] = {}
    records = 0
    for desc in LicenseImportItemsModel.objects.exclude(description__isnull=True).exclude(description="").values_list("description", flat=True):
        if desc not in keys:
            keys[desc] = description_key(desc)
        if keys[desc] and key_hash(keys[desc]) not in mapped:
            records += 1
    out["import"] = {"records": records, "descriptions": len({k for k in keys.values() if k and key_hash(k) not in mapped})}
    return out
