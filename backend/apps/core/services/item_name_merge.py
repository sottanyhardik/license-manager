"""Approval-gated, audited, reversible Item Name merge engine.

Owner rule 2026-11-21: similarity is detected automatically, merging never is.
Only an ``ItemNameMerge`` row that the owner approved (with a second, explicit
final confirmation) can execute. The engine:

* discovers every relation to ``ItemNameModel`` by introspection (FKs and
  M2M through rows, including hidden ``related_name='+'`` ones) — nothing is
  hard-coded, so a newly added reference cannot be silently skipped;
* re-points references row by row and writes one audit row per change;
* never deletes an Item Name — sources are deactivated and resolved through
  ``ItemNameMergeSource``;
* snapshots financial values (licence balances via ``LicenseBalanceCalculator``
  plus import-item quantity/CIF aggregates) before and after, and aborts the
  whole transaction unless the difference is exactly zero;
* rolls back from the audit trail, refusing if a record changed since.

It never touches balance formulas.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.apps import apps
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from apps.core.models import (
    ItemNameMerge, ItemNameMergeAudit, ItemNameMergeSource, ItemNameModel, SionNormClassModel,
)

APPROVAL_LABEL = "license.ImportItemMappingApproval"
_ENGINE_MODELS = {ItemNameMerge, ItemNameMergeSource, ItemNameMergeAudit}
_IMPORT_ITEM_DECIMALS = ("quantity", "old_quantity", "cif_fc", "cif_inr", "available_quantity", "available_value",
                         "debited_quantity", "debited_value", "allotted_quantity", "allotted_value")


class MergeError(Exception):
    """Validation/conflict failure — nothing was changed."""


class FinancialInvarianceError(MergeError):
    """Financial snapshot differed after the merge — the transaction was rolled back."""


@dataclass(frozen=True)
class Relation:
    label: str          # "app.Model.field"
    kind: str           # "FK" | "M2M"
    model: type         # model holding the item column (the through model for M2M)
    column: str         # attname of the item column
    owner_column: str = ""  # M2M only: the other side of the through row


def discover_relations() -> list[Relation]:
    """Every concrete reference to ItemNameModel except its own forward ``norms`` M2M and the engine tables."""
    out = []
    for model in apps.get_models():
        if model in _ENGINE_MODELS:
            continue
        for f in list(model._meta.fields) + list(model._meta.many_to_many):
            if not f.is_relation or f.remote_field is None or f.remote_field.model is not ItemNameModel:
                continue
            if model is ItemNameModel:
                continue  # norms/self — handled explicitly
            label = f"{model._meta.label}.{f.name}"
            if f.many_to_many:
                through = f.remote_field.through
                item_col = next(x for x in through._meta.fields if getattr(x.remote_field, "model", None) is ItemNameModel)
                owner_col = next(x for x in through._meta.fields if getattr(x.remote_field, "model", None) is model)
                out.append(Relation(label, "M2M", through, item_col.attname, owner_col.attname))
            else:
                out.append(Relation(label, "FK", model, f.attname))
    return sorted(out, key=lambda r: r.label)


def _table_exists(model) -> bool:
    from django.db import connection
    return model._meta.db_table in connection.introspection.table_names()


def _norm_codes(item: ItemNameModel) -> set[str]:
    return set(item.norms.values_list("norm_class", flat=True))


# ---------------------------------------------------------------- preview
def preview(canonical_id: int, source_ids: list[int], norm_union: list[str] | None = None) -> dict:
    """Read-only impact + conflict report for one proposed merge."""
    norm_union = sorted(set(norm_union or []))
    items = {i.pk: i for i in ItemNameModel.objects.filter(pk__in=[canonical_id, *source_ids])}
    conflicts = []
    if canonical_id in source_ids:
        conflicts.append("canonical is also listed as a source")
    for pk in [canonical_id, *source_ids]:
        if pk not in items:
            conflicts.append(f"item {pk} does not exist")
    if conflicts:
        return {"conflicts": conflicts, "references_moved": None}
    canonical = items[canonical_id]
    if not canonical.is_active:
        conflicts.append(f"canonical {canonical_id} is inactive")
    if ItemNameMergeSource.objects.filter(source_id=canonical_id, is_current=True).exists():
        conflicts.append(f"canonical {canonical_id} is itself merged into another item")
    canonical_norms = _norm_codes(canonical)
    unknown = set(norm_union) - set(SionNormClassModel.objects.filter(norm_class__in=norm_union).values_list("norm_class", flat=True))
    if unknown:
        conflicts.append(f"approved norm_union contains unknown norms {sorted(unknown)}")

    relations = [r for r in discover_relations() if _table_exists(r.model)]
    per_source, total = {}, 0
    for sid in source_ids:
        src = items[sid]
        if ItemNameMergeSource.objects.filter(source_id=sid, is_current=True).exists():
            conflicts.append(f"source {sid} is already merged")
        if ItemNameMerge.objects.filter(canonical_id=sid, status=ItemNameMerge.EXECUTED).exists():
            conflicts.append(f"source {sid} is the canonical of an executed merge (would chain)")
        extra = _norm_codes(src) - canonical_norms - set(norm_union)
        if extra:
            conflicts.append(f"source {sid} has norms {sorted(extra)} not on canonical and not approved for union")
        counts = {}
        for r in relations:
            n = r.model._default_manager.filter(**{r.column: sid}).count()
            if n:
                counts[r.label] = n
                total += n
        per_source[sid] = {"name": src.name, "is_active": src.is_active, "norms": sorted(_norm_codes(src)), "references": counts}
    return {
        "canonical": {"id": canonical_id, "name": canonical.name, "norms": sorted(canonical_norms)},
        "sources": per_source,
        "norm_union_added": sorted(set(norm_union) - canonical_norms),
        "references_moved": total,
        "relations_checked": [r.label for r in relations],
        "relations_missing_table": [r.label for r in discover_relations() if not _table_exists(r.model)],
        "conflicts": conflicts,
    }


# ---------------------------------------------------------------- financial snapshot
def financial_snapshot(member_ids: list[int]) -> dict:
    """Values that must not change: aggregated over the whole member set (canonical + sources), so a correct merge
    — which only moves references between members — leaves every number identical."""
    from apps.allotment.models import AllotmentItems, AllotmentModel
    from apps.bill_of_entry.models import BillOfEntryModel
    from apps.license.models import LicenseImportItemsModel, LicenseItemPlan
    from apps.license.services.balance_calculator import LicenseBalanceCalculator as C

    import_qs = LicenseImportItemsModel.objects.filter(items__in=member_ids).distinct()
    import_ids = sorted(import_qs.values_list("pk", flat=True))
    agg = LicenseImportItemsModel.objects.filter(pk__in=import_ids).aggregate(
        n=Count("pk"), **{f: Sum(f) for f in _IMPORT_ITEM_DECIMALS})
    licence_ids = sorted(set(LicenseImportItemsModel.objects.filter(pk__in=import_ids).values_list("license_id", flat=True)))
    per_licence = {}
    if licence_ids:
        parts = {
            "credit": C.calculate_credit_for_licenses(licence_ids),
            "debit": C.calculate_debit_for_licenses(licence_ids),
            "allotment": C.calculate_allotment_for_licenses(licence_ids),
            "trade": C.calculate_trade_for_licenses(licence_ids),
            "balance": C.calculate_balance_for_licenses(licence_ids),
            "financial_balance": C.calculate_financial_balance_for_licenses(licence_ids),
        }
        for lid in licence_ids:
            per_licence[str(lid)] = {k: str(v.get(lid)) for k, v in parts.items()}
    return {
        "import_items": {k: str(v) for k, v in agg.items()},
        "import_item_ids_sha256": hashlib.sha256(",".join(map(str, import_ids)).encode()).hexdigest(),
        "licences": per_licence,
        "boe_planning_targets": BillOfEntryModel.objects.filter(planning_target_item__in=member_ids).count(),
        "allotment_planning_targets": AllotmentModel.objects.filter(planning_target_item__in=member_ids).count(),
        "allotment_item_planning_targets": AllotmentItems.objects.filter(planning_target_item__in=member_ids).count(),
        "item_plans": LicenseItemPlan.objects.filter(item_name__in=member_ids).count(),
    }


def _diff(before: dict, after: dict) -> list[str]:
    out = []
    for key in sorted(set(before) | set(after)):
        if key == "licences":
            for lid in sorted(set(before[key]) | set(after.get(key, {}))):
                if before[key].get(lid) != after[key].get(lid):
                    out.append(f"licence {lid}: {before[key].get(lid)} -> {after[key].get(lid)}")
        elif before.get(key) != after.get(key):
            out.append(f"{key}: {before.get(key)} -> {after.get(key)}")
    return out


# ---------------------------------------------------------------- execute
def _audit(merge, op, rel_label, field, record_pk, prev, new, *, owner="", phase=ItemNameMergeAudit.EXECUTE, detail=None):
    return ItemNameMergeAudit(merge=merge, phase=phase, operation=op, model_label=rel_label, field_name=field,
                              record_pk=str(record_pk), owner_pk=str(owner), previous_value=str(prev),
                              new_value=str(new), detail=detail or {})


def execute(merge_id: int, *, confirm: bool, executed_by: str, allow_reference_moves: bool = False) -> ItemNameMerge:
    """Execute ONE owner-approved merge. ``confirm`` must be passed explicitly by the caller (final confirmation).

    ``allow_reference_moves`` stays False in production use: re-pointing live references uses raw through-row
    updates that bypass the replan / cache-invalidation receivers, and the financial snapshot does not yet measure
    item-level (pivot split / availability) effects. Until both are wired, only merges whose sources carry no
    references may execute (review 2026-11-21, findings B1/S1)."""
    if confirm is not True:
        raise MergeError("Explicit confirmation is required to execute a merge.")
    try:
        with transaction.atomic():
            merge = ItemNameMerge.objects.select_for_update().get(pk=merge_id)
            if merge.status != ItemNameMerge.APPROVED:
                raise MergeError(f"{merge.group_key}: status is {merge.status}; only APPROVED merges can execute.")
            if not merge.final_confirmation or not merge.approved_by or not merge.approval_reference:
                raise MergeError(f"{merge.group_key}: missing owner approval / final confirmation.")
            src_rows = list(merge.sources.select_for_update().order_by("pk"))
            source_ids = [s.source_id for s in src_rows]
            if not source_ids:
                raise MergeError(f"{merge.group_key}: no source items.")
            member_ids = sorted([merge.canonical_id, *source_ids])
            list(ItemNameModel.objects.select_for_update().filter(pk__in=member_ids).order_by("pk"))  # lock members

            pv = preview(merge.canonical_id, source_ids, merge.norm_union)
            if pv["conflicts"]:
                raise MergeError(f"{merge.group_key}: unresolved conflicts {pv['conflicts']}")
            approved_moves = merge.preview.get("approved_references_moved")
            if approved_moves is None:
                raise MergeError(f"{merge.group_key}: the approved preview has no reference count — re-confirm with the owner.")
            if pv["references_moved"] != approved_moves:
                raise MergeError(f"{merge.group_key}: references changed since approval "
                                 f"({approved_moves} approved, {pv['references_moved']} now) — re-confirm with the owner.")

            if pv["references_moved"] and not allow_reference_moves:
                raise MergeError(f"{merge.group_key}: moves {pv['references_moved']} references; reference-moving merges are "
                                 "disabled until replan/cache propagation and item-level snapshots are implemented.")

            before = financial_snapshot(member_ids)
            canonical = ItemNameModel.objects.get(pk=merge.canonical_id)
            audits = []

            # 1. Mapping approvals move through the existing versioned path (PROTECT FK, has its own history).
            approval_model = apps.get_model(APPROVAL_LABEL)
            if _table_exists(approval_model):
                from apps.license.services.product_intelligence.import_item_approval import repoint_for_merge
                for row in repoint_for_merge(source_ids, canonical.pk, reason=f"item name merge {merge.group_key}"):
                    audits.append(_audit(merge, ItemNameMergeAudit.APPROVAL_REPOINT, APPROVAL_LABEL, "item",
                                         row["approval_id"], row["from_item_id"], row["to_item_id"], detail=row))

            # 2. Every other relation, row by row.
            for rel in discover_relations():
                if rel.label == f"{APPROVAL_LABEL}.item" or not _table_exists(rel.model):
                    continue
                mgr = rel.model._default_manager
                if rel.kind == "FK":
                    rows = list(mgr.filter(**{f"{rel.column}__in": source_ids}).values_list("pk", rel.column))
                    for pk, prev in rows:
                        audits.append(_audit(merge, ItemNameMergeAudit.REPOINT, rel.label, rel.column, pk, prev, canonical.pk))
                    if rows:
                        mgr.filter(pk__in=[r[0] for r in rows]).update(**{rel.column: canonical.pk})
                else:
                    rows = list(mgr.filter(**{f"{rel.column}__in": source_ids}).values_list("pk", rel.owner_column, rel.column))
                    owners_with_canonical = set(mgr.filter(**{rel.owner_column + "__in": [r[1] for r in rows], rel.column: canonical.pk})
                                                .values_list(rel.owner_column, flat=True))
                    move, drop = [], []
                    for pk, owner, prev in rows:
                        if owner in owners_with_canonical:
                            drop.append(pk)  # redundant once identity is merged; canonical link already present
                            audits.append(_audit(merge, ItemNameMergeAudit.M2M_DEDUP, rel.label, rel.column, pk, prev, canonical.pk, owner=owner))
                        else:
                            move.append(pk)
                            owners_with_canonical.add(owner)
                            audits.append(_audit(merge, ItemNameMergeAudit.M2M_MOVE, rel.label, rel.column, pk, prev, canonical.pk, owner=owner))
                    # moves must precede drops only for distinct owners; two sources on the same owner: second becomes a drop
                    if move:
                        mgr.filter(pk__in=move).update(**{rel.column: canonical.pk})
                    if drop:
                        mgr.filter(pk__in=drop).delete()

            # 3. Owner-approved norm union.
            have = _norm_codes(canonical)
            for norm in SionNormClassModel.objects.filter(norm_class__in=merge.norm_union).order_by("norm_class"):
                if norm.norm_class not in have:
                    canonical.norms.add(norm)
                    audits.append(_audit(merge, ItemNameMergeAudit.NORM_ADD, "core.ItemNameModel.norms", "sionnormclassmodel_id",
                                         norm.pk, "", canonical.pk, detail={"norm_class": norm.norm_class}))

            # 4. Deactivate sources (never delete).
            for row in src_rows:
                src = ItemNameModel.objects.get(pk=row.source_id)
                row.original_name, row.previous_is_active = src.name, src.is_active
                row.previous_norms, row.is_current = sorted(_norm_codes(src)), True
                row.save()
                if src.is_active:
                    src.is_active = False
                    src.save()
                audits.append(_audit(merge, ItemNameMergeAudit.DEACTIVATE, "core.ItemNameModel", "is_active",
                                     src.pk, row.previous_is_active, False))
            ItemNameMergeAudit.objects.bulk_create(audits)

            # 5. Verify: no reference left on any source, no duplicate M2M rows, financial delta = 0.
            leftovers = {}
            for rel in discover_relations():
                if _table_exists(rel.model):
                    n = rel.model._default_manager.filter(**{f"{rel.column}__in": source_ids}).count()
                    if n:
                        leftovers[rel.label] = n
            dupes = {}
            for rel in discover_relations():
                if rel.kind == "M2M" and _table_exists(rel.model):
                    n = (rel.model._default_manager.filter(**{rel.column: canonical.pk}).values(rel.owner_column)
                         .annotate(c=Count("pk")).filter(c__gt=1).count())
                    if n:
                        dupes[rel.label] = n
            if leftovers or dupes:
                raise MergeError(f"{merge.group_key}: verification failed leftovers={leftovers} duplicates={dupes}")
            after = financial_snapshot(member_ids)
            diff = _diff(before, after)
            if diff:
                raise FinancialInvarianceError(f"{merge.group_key}: financial difference {diff[:20]}")

            merge.status, merge.executed_on, merge.executed_by = ItemNameMerge.EXECUTED, timezone.now(), executed_by
            merge.financial_before, merge.financial_after = before, after
            merge.preview = {**merge.preview, "executed_preview": pv}
            merge.verification = {"leftover_references": 0, "duplicate_m2m_rows": 0, "financial_difference": 0,
                                  "audit_rows": len(audits), "licences_checked": len(before["licences"])}
            merge.error = ""
            merge.save()
            return merge
    except Exception as exc:  # transaction already rolled back; record why, never retry automatically
        ItemNameMerge.objects.filter(pk=merge_id, status=ItemNameMerge.APPROVED).update(
            status=ItemNameMerge.FAILED if isinstance(exc, FinancialInvarianceError) else ItemNameMerge.APPROVED,
            error=f"{type(exc).__name__}: {exc}"[:5000])
        raise


# ---------------------------------------------------------------- rollback
def rollback(merge_id: int, *, confirm: bool, reversed_by: str) -> ItemNameMerge:
    if confirm is not True:
        raise MergeError("Explicit confirmation is required to roll back a merge.")
    with transaction.atomic():
        merge = ItemNameMerge.objects.select_for_update().get(pk=merge_id)
        if merge.status != ItemNameMerge.EXECUTED:
            raise MergeError(f"{merge.group_key}: status is {merge.status}; only EXECUTED merges can be rolled back.")
        src_rows = list(merge.sources.select_for_update())
        member_ids = sorted([merge.canonical_id, *[s.source_id for s in src_rows]])
        list(ItemNameModel.objects.select_for_update().filter(pk__in=member_ids).order_by("pk"))
        before = financial_snapshot(member_ids)
        by_label = {r.label: r for r in discover_relations()}
        canonical = ItemNameModel.objects.get(pk=merge.canonical_id)
        undo = []
        for a in merge.audit.filter(phase=ItemNameMergeAudit.EXECUTE).order_by("-pk"):
            prev, new = a.previous_value, a.new_value
            if a.operation == ItemNameMergeAudit.REPOINT:
                rel = by_label[a.model_label]
                if not rel.model._default_manager.filter(pk=a.record_pk, **{rel.column: new}).update(**{rel.column: prev}):
                    raise MergeError(f"rollback conflict: {a.model_label} #{a.record_pk} changed since the merge")
            elif a.operation == ItemNameMergeAudit.M2M_MOVE:
                rel = by_label[a.model_label]
                mgr = rel.model._default_manager
                if mgr.filter(**{rel.owner_column: a.owner_pk, rel.column: prev}).exists():
                    raise MergeError(f"rollback conflict: {a.model_label} owner {a.owner_pk} already linked to {prev}")
                if not mgr.filter(pk=a.record_pk, **{rel.column: new}).update(**{rel.column: prev}):
                    raise MergeError(f"rollback conflict: {a.model_label} through row #{a.record_pk} changed since the merge")
            elif a.operation == ItemNameMergeAudit.M2M_DEDUP:
                rel = by_label[a.model_label]
                rel.model._default_manager.get_or_create(**{rel.owner_column: a.owner_pk, rel.column: prev})
            elif a.operation == ItemNameMergeAudit.APPROVAL_REPOINT:
                approval_model = apps.get_model(APPROVAL_LABEL)
                ap = approval_model.objects.select_for_update().get(pk=a.record_pk)
                if str(ap.item_id) != new:
                    raise MergeError(f"rollback conflict: mapping approval #{ap.pk} changed since the merge")
                from apps.license.services.product_intelligence.import_item_approval import repoint
                if not (ap.is_active and repoint(ap.pk, int(prev), user=None, expected_item_id=int(new),
                                                 reason=f"item name merge rollback {merge.group_key}")):
                    ap.item_id, ap.version = int(prev), ap.version + 1
                    ap.save()
            elif a.operation == ItemNameMergeAudit.NORM_ADD:
                canonical.norms.remove(int(a.record_pk))
            elif a.operation == ItemNameMergeAudit.DEACTIVATE:
                src = ItemNameModel.objects.get(pk=a.record_pk)
                restore = prev == "True"
                if src.is_active != restore:
                    src.is_active = restore
                    src.save()
            undo.append(_audit(merge, a.operation, a.model_label, a.field_name, a.record_pk, new, prev,
                               owner=a.owner_pk, phase=ItemNameMergeAudit.ROLLBACK, detail={"reverses_audit": a.pk}))
        ItemNameMergeAudit.objects.bulk_create(undo)
        merge.sources.update(is_current=False)
        after = financial_snapshot(member_ids)
        diff = _diff(before, after)
        if diff:
            raise FinancialInvarianceError(f"{merge.group_key}: financial difference on rollback {diff[:20]}")
        merge.status, merge.reversed_on, merge.reversed_by = ItemNameMerge.REVERSED, timezone.now(), reversed_by
        merge.verification = {**merge.verification, "rollback_audit_rows": len(undo), "rollback_financial_difference": 0}
        merge.save()
        return merge
