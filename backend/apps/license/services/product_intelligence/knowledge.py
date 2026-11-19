"""Historical Product Knowledge Repository: inventory + versioned, reproducible extraction.

Observations are *descriptions with provenance* — never evidence of equivalence on
their own. Only financial-free columns are read (description, HSN, SION, ids, link
provenance). Original records are never modified.

Label trust (owner rule: "historical transactions are observations, not ground truth"):

* VERIFIED  — ``ProductMatchDecision`` (human approve / reject / different) and BOE /
  allotment ``planning_mapping_source = USER_SELECTED`` (a user picked the target item
  for that record).
* RULE      — ``planning_mapping_source = APPROVED_ALIAS`` (an approved alias rule was
  applied); import-item ↔ master links (``LicenseImportItemsModel.items``, set largely by
  the save signal / rules). Usable for *proxy evaluation* only — never training labels,
  because a model trained on them would only re-learn the rules.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Max, Min, Q

from apps.core.models import HSCodeModel, ItemNameModel, SIONImportModel
from apps.license.models import LicenseImportItemsModel, ProductAlias, ProductMatchDecision
from apps.license.services.product_matching import normalise, product_segments

VERIFIED, RULE = "VERIFIED", "RULE"


def artifact_root() -> Path:
    return Path(getattr(settings, "PRODUCT_INTEL_DIR", "") or os.getenv("PRODUCT_INTEL_DIR", "") or Path(settings.BASE_DIR) / "var" / "product_intel")


def inventory_cache_key() -> str:
    """Scoped to the database: test runs and the dev server share one Redis cache."""
    from django.db import connection
    return f"product_intel_inventory_v1:{connection.settings_dict.get('NAME')}"


def _boe_model():
    from apps.bill_of_entry.models import BillOfEntryModel
    return BillOfEntryModel


def _allotment_model():
    from apps.allotment.models import AllotmentModel
    return AllotmentModel


def _source_specs():
    """(source name, queryset, description field, hsn field, sion field, date field, link field, link provenance)."""
    return [
        ("licence_import_item", LicenseImportItemsModel.objects.all(), "description", "hs_code__hs_code",
         "license__export_license__norm_class__norm_class", None, "items", RULE),
        ("sion_import_norm", SIONImportModel.objects.filter(is_tombstone=False), "description", "hsn_code__hs_code",
         "norm_class__norm_class", "created_on", None, None),
        ("bill_of_entry", _boe_model().objects.all(), "product_name", None, None, "created_on", "planning_target_item", None),
        ("allotment", _allotment_model().objects.all(), "item_name", None, None, "created_on", "planning_target_item", None),
    ]


def inventory() -> list[dict]:
    """Per-source counts, period, missing data, duplicates and label trust (dashboard + docs)."""
    rows = []
    for name, qs, desc, hsn, sion, date, link, _ in _source_specs():
        agg = {"n": Count("id")}
        if date:
            agg.update(first=Min(date), last=Max(date))
        stats = qs.order_by().aggregate(**agg, missing=Count("id", filter=Q(**{f"{desc}__isnull": True}) | Q(**{desc: ""})))
        texts = Counter(normalise(t) for t in qs.order_by().values_list(desc, flat=True) if t)
        row = {
            "source": name, "records": stats["n"], "missing_description": stats["missing"],
            "unique_normalised": len(texts), "duplicate_observations": sum(c - 1 for c in texts.values() if c > 1),
            "first": stats.get("first").isoformat() if stats.get("first") else None, "last": stats.get("last").isoformat() if stats.get("last") else None,
            "missing_hsn": qs.filter(**{f"{hsn}__isnull": True}).count() if hsn else None,
        }
        if name in {"bill_of_entry", "allotment"}:
            by = dict(qs.order_by().values_list("planning_mapping_source").annotate(c=Count("id")).values_list("planning_mapping_source", "c"))
            row["labels"] = {"verified_user_selected": by.get("USER_SELECTED", 0), "rule_approved_alias": by.get("APPROVED_ALIAS", 0),
                             "unmapped": stats["n"] - by.get("USER_SELECTED", 0) - by.get("APPROVED_ALIAS", 0)}
            row["trust"] = "USER_SELECTED rows are verified labels; APPROVED_ALIAS rows are rule-derived (proxy only)"
        elif name == "licence_import_item":
            through = LicenseImportItemsModel.items.through
            per_item = Counter(dict(through.objects.order_by().values_list("licenseimportitemsmodel_id").annotate(c=Count("id")).values_list("licenseimportitemsmodel_id", "c")))
            links = Counter(min(c, 2) for c in per_item.values())
            row["master_links"] = {"none": stats["n"] - len(per_item), "one": links.get(1, 0), "several": links.get(2, 0)}
            row["trust"] = "Master links are mostly signal / rule auto-links — proxy only, never training labels"
        else:
            row["trust"] = "Authoritative SION norm catalogue text — reference vocabulary, not equivalence labels"
        rows.append(row)
    decisions = dict(ProductMatchDecision.objects.order_by().values_list("decision").annotate(c=Count("id")).values_list("decision", "c"))
    rows.append({"source": "product_match_decision", "records": sum(decisions.values()), "labels": decisions,
                 "trust": "Human decisions — verified training labels"})
    rows.append({"source": "product_alias", "records": ProductAlias.objects.filter(is_active=True).count(), "trust": "Approved aliases (human)"})
    rows.append({"source": "item_master", "records": ItemNameModel.objects.filter(is_active=True).count(), "trust": "Canonical masters"})
    rows.append({"source": "hsn_dictionary", "records": HSCodeModel.objects.count(), "trust": "Reference HSN descriptions"})
    return rows


def observations():
    """Yield one financial-free observation per source record (stable order)."""
    for name, qs, desc, hsn, sion, _date, link, _ in _source_specs():
        fields = ["id", desc] + ([hsn] if hsn else []) + ([sion] if sion else [])
        if name in {"bill_of_entry", "allotment"}:
            fields += ["planning_target_item_id", "planning_mapping_source"]
        seen: set[int] = set()
        for row in qs.order_by("id").values(*fields):
            if row["id"] in seen:  # the SION join can repeat an import item per export norm
                continue
            seen.add(row["id"])
            text = row.get(desc) or ""
            obs = {"source": name, "source_id": row["id"], "description": text, "normalised": normalise(text),
                   "hsn": str(row.get(hsn) or "") if hsn else "", "sion": row.get(sion) if sion else None,
                   "multi_product": len(product_segments(text)) > 1}
            if name in {"bill_of_entry", "allotment"} and row.get("planning_target_item_id"):
                obs["target_item_id"] = row["planning_target_item_id"]
                obs["target_trust"] = VERIFIED if row["planning_mapping_source"] == "USER_SELECTED" else RULE
            yield obs


def verified_labels() -> list[dict]:
    """Human-verified (description, master) pairs, positives and negatives, with provenance.

    Group = normalised description (so one wording never sits in both train and holdout, whatever its HSN /
    SION / source). Order: BOE / allotment user selections first, then review decisions oldest → newest; for
    the same (wording, master) pair the **latest** human label wins.
    """
    labels = []
    for model, desc, name in ((_boe_model(), "product_name", "BOE"), (_allotment_model(), "item_name", "Allotment")):
        for pk, text, item_id in model.objects.filter(planning_mapping_source="USER_SELECTED", planning_target_item__isnull=False).order_by("pk").values_list("pk", desc, "planning_target_item_id"):
            if text:
                labels.append({"description": text, "hsn": "", "sion": None, "item_id": item_id, "label": 1,
                               "provenance": f"{name}#{pk} USER_SELECTED", "exclude_import_ids": []})
    from apps.license.services.product_intelligence.item_name_mapping import undone_import_decision_ids
    undone = undone_import_decision_ids()  # an approval reversed by Undo is not a positive label
    for d in ProductMatchDecision.objects.select_related("sion").order_by("decided_on", "pk"):
        if d.pk in undone:
            continue
        base = {"description": d.source_description, "hsn": d.hsn_code, "sion": getattr(d.sion, "norm_class", None),
                "provenance": f"ProductMatchDecision#{d.pk}", "exclude_import_ids": list(d.import_item_ids or [])}
        if d.decision == ProductMatchDecision.APPROVED and d.chosen_item_id:
            labels.append({**base, "item_id": d.chosen_item_id, "label": 1})
            if d.suggested_item_id and d.suggested_item_id != d.chosen_item_id:
                labels.append({**base, "item_id": d.suggested_item_id, "label": 0, "provenance": base["provenance"] + " (reviewer chose another master)"})
        elif d.suggested_item_id:
            labels.append({**base, "item_id": d.suggested_item_id, "label": 0})
    from apps.license.models import ProductMatchSelection
    for sel in ProductMatchSelection.objects.filter(status=ProductMatchSelection.APPROVED).select_related("sion").order_by("decided_on", "pk"):
        # A reviewer-approved product phrase of a multi-product record → its master (no links were created by it).
        labels.append({"description": sel.detected_phrase, "hsn": sel.hsn_code, "sion": getattr(sel.sion, "norm_class", None), "item_id": sel.item_id,
                       "label": 1, "provenance": f"ProductMatchSelection#{sel.pk}", "exclude_import_ids": []})
    unique: dict[tuple, dict] = {}
    for lab in labels:
        lab["group"] = normalise(lab["description"])
        unique[(lab["group"], lab["item_id"])] = lab  # later (newer) human label overwrites
    return list(unique.values())


def build_dataset(*, user=None):
    """Write a versioned dataset artifact (observations + verified labels) and register it."""
    from django.utils import timezone

    from apps.license.models import ProductIntelDataset

    version = timezone.now().strftime("ds-%Y%m%d-%H%M%S-%f")
    folder = artifact_root() / "datasets" / version
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    by_source: Counter = Counter()
    unique: set[str] = set()
    multi = 0
    with open(folder / "observations.jsonl", "w", encoding="utf-8") as fh:
        for obs in observations():
            line = json.dumps(obs, sort_keys=True, default=str)
            fh.write(line + "\n")
            digest.update(line.encode())
            by_source[obs["source"]] += 1
            unique.add(obs["normalised"])
            multi += obs["multi_product"]
    labels = verified_labels()
    with open(folder / "labels.jsonl", "w", encoding="utf-8") as fh:
        for lab in labels:
            line = json.dumps(lab, sort_keys=True, default=str)
            fh.write(line + "\n")
            digest.update(line.encode())
    summary = {"by_source": dict(by_source), "multi_product_observations": multi,
               "labels": {"positive": sum(1 for x in labels if x["label"] == 1), "negative": sum(1 for x in labels if x["label"] == 0)},
               "excluded_fields": "quantity, CIF, debits, allotment and plan amounts are never extracted"}
    from django.core.cache import cache
    cache.delete(inventory_cache_key())
    return ProductIntelDataset.objects.create(
        version=version, artifact_path=str(folder), sha256=digest.hexdigest(), observation_count=sum(by_source.values()),
        unique_description_count=len(unique), label_count=len(labels), summary=summary, created_by=user,
    )


class DatasetIntegrityError(ValueError):
    pass


def load_labels(dataset) -> list[dict]:
    """Labels of a dataset, after re-verifying the sha256 over both artifacts (tampering → error)."""
    folder = Path(dataset.artifact_path)
    digest = hashlib.sha256()
    labels = []
    for name in ("observations.jsonl", "labels.jsonl"):
        with open(folder / name, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                digest.update(line.encode())
                if name == "labels.jsonl" and line.strip():
                    labels.append(json.loads(line))
    if digest.hexdigest() != dataset.sha256:
        raise DatasetIntegrityError(f"Dataset {dataset.version} artifacts do not match their recorded sha256")
    return labels
