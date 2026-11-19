"""Read-only Item Pivot intelligence endpoints (overview / products / licences /
eligibility + Auto Plan recommendations), mounted on ``ItemPivotViewSet``.

Same filters and licence population as the classic report
(``item_pivot_selection.select_pivot_licenses``); nothing is written.
"""
from __future__ import annotations

import logging

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apps.accounts.permissions import ReportPermission
from apps.license.api.views.item_pivot_helpers import _safe_int
from apps.license.api.views.item_report import _ExcelPassthroughRenderer
from apps.license.services.item_pivot_intelligence import build_intelligence, recommend_for_licenses
from apps.license.services.item_pivot_intelligence_export import REC_COLUMNS, SHEETS, workbook_response as _workbook
from apps.license.services.item_pivot_selection import select_pivot_licenses

logger = logging.getLogger(__name__)

FILTER_KEYS = ("sion_norm", "company_ids", "exclude_company_ids", "license_status", "expiry_date_from", "expiry_date_to", "purchase_status")


def _filters(params) -> dict:
    values = {key: params.get(key) or None for key in FILTER_KEYS}
    values["license_status"] = values["license_status"] or "active"
    values["min_balance"] = _safe_int(params.get("min_balance"), 200)
    values["days"] = _safe_int(params.get("days"), 30)
    values["include_norm_links"] = True  # masters legitimate via ItemNameModel.norms count (multi-norm canonical masters)
    return values


class ItemPivotIntelligenceMixin:
    """Actions for ``ItemPivotViewSet``. Permission: the viewset's ReportPermission."""

    # `?format=excel` is DRF's format override: the pass-through renderer lets it reach the view.
    @action(detail=False, methods=["get"], url_path="intelligence", renderer_classes=[JSONRenderer, _ExcelPassthroughRenderer])
    def intelligence(self, request):
        data = build_intelligence(select_pivot_licenses(**_filters(request.query_params)))
        from apps.license.services.product_intelligence.propagation import refresh_open, serialise

        open_changes = [c for c in refresh_open() if c.status in ("PROPAGATING", "FAILED")]
        data["overview"]["mapping_propagation"] = {
            "open": [serialise(c) for c in open_changes[:10]], "propagating": sum(c.status == "PROPAGATING" for c in open_changes),
            "failed": sum(c.status == "FAILED" for c in open_changes)}
        if (request.query_params.get("format") or "").lower() == "excel":
            warnings = [row for row in data["eligibility"] if row["status"] in {"WARNING", "OVERPLANNED", "BLOCKED"}]
            sheets = [(title, cols, data[key]) for title, (key, cols) in SHEETS.items()]
            sheets.append(("Exceptions", SHEETS["Eligibility"][1], warnings))
            return _workbook(sheets)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="recommendations", renderer_classes=[JSONRenderer, _ExcelPassthroughRenderer])
    def recommendations(self, request):
        raw = request.query_params.get("license_ids", "")
        try:
            ids = [int(v) for v in raw.split(",") if v.strip()]
        except ValueError:
            return Response({"license_ids": "Comma-separated licence ids are required."}, status=status.HTTP_400_BAD_REQUEST)
        if not ids:
            return Response({"license_ids": "At least one licence id is required."}, status=status.HTTP_400_BAD_REQUEST)
        data = recommend_for_licenses(ids, limit=25)
        if (request.query_params.get("format") or "").lower() == "excel":
            return _workbook([("Recommendations", REC_COLUMNS, data["recommendations"])])
        return Response(data)


def _job_payload(job):
    if job is None:
        return None
    return {"id": job.pk, "status": job.status, "total": job.total, "processed": job.processed, "batch_size": job.batch_size,
            "model_version": job.model_version, "metrics": job.metrics, "error": job.error, "pause_requested": job.pause_requested,
            "created_on": job.created_on.isoformat(), "finished_on": job.finished_on.isoformat() if job.finished_on else None}


def _clean_filters(raw) -> dict | None:
    """Only the report's own filter keys, as strings; anything else is rejected (None)."""
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        return None
    allowed = set(FILTER_KEYS) | {"min_balance", "days"}
    return {k: str(v) for k, v in raw.items() if k in allowed and v not in (None, "")}


def _drop_mapping_counts() -> None:
    """Import-item links changed → Mapping workspace pending counts are stale (after commit)."""
    from apps.license.services.product_intelligence.item_name_mapping import drop_counts_cache

    transaction.on_commit(drop_counts_cache)


def _can_approve(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.has_any_role(["LICENSE_MANAGER"])))


class ItemPivotMatchingMixin:
    """Product-matching review (deterministic matcher; owner decision 2026-11-18)."""

    @action(detail=False, methods=["get"], url_path="matching")
    def matching(self, request):
        from apps.license.models import ProductMatchDecision, ProductMatchingJob
        from apps.license.services.product_matching import matching_groups, matching_summary, suggest
        from apps.license.services.product_matching_semantic import finalise

        suggestions = finalise(suggest(matching_groups(build_intelligence(select_pivot_licenses(**_filters(request.query_params))))))
        decisions = ProductMatchDecision.objects.select_related("chosen_item", "suggested_item", "decided_by", "sion")[:200]
        job = ProductMatchingJob.objects.first()
        return Response({
            "matcher": "deterministic-v1 + local MiniLM semantic candidates", "can_approve": _can_approve(request.user),
            "summary": matching_summary(suggestions), "suggestions": suggestions, "latest_job": _job_payload(job),
            "decisions": [{
                "id": d.pk, "decision": d.decision, "source_description": d.source_description, "hsn_code": d.hsn_code,
                "sion": getattr(d.sion, "norm_class", None), "suggested_item": getattr(d.suggested_item, "name", None),
                "chosen_item": getattr(d.chosen_item, "name", None), "confidence": d.confidence, "explanation": d.explanation,
                "import_item_ids": d.import_item_ids, "previous_links": d.previous_links, "new_links": d.new_links,
                "decided_by": getattr(d.decided_by, "username", None), "decided_on": d.decided_on.isoformat(),
            } for d in decisions],
        })

    @action(detail=False, methods=["get", "post"], url_path="matching/jobs", permission_classes=[])
    def matching_jobs(self, request):
        """GET: latest jobs. POST: start a background classification job (LICENSE_MANAGER)."""
        from apps.license.models import ProductMatchingJob

        if request.method == "GET":
            if not ReportPermission().has_permission(request, self):
                return Response(status=status.HTTP_403_FORBIDDEN if request.user.is_authenticated else status.HTTP_401_UNAUTHORIZED)
            return Response({"jobs": [_job_payload(j) for j in ProductMatchingJob.objects.all()[:20]]})
        if not _can_approve(request.user):
            return Response({"detail": "Starting classification requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        if ProductMatchingJob.objects.filter(status__in=[ProductMatchingJob.QUEUED, ProductMatchingJob.RUNNING]).exists():
            return Response({"detail": "A classification job is already queued or running."}, status=status.HTTP_409_CONFLICT)
        batch = max(1, min(_safe_int((request.data or {}).get("batch_size"), 4), 8))
        filters = _clean_filters((request.data or {}).get("filters"))
        if filters is None:
            return Response({"filters": "Must be an object of report filters."}, status=status.HTTP_400_BAD_REQUEST)
        from apps.license.services.product_matching_semantic import create_job

        job = create_job(filters=filters, batch_size=batch, user=request.user)
        return Response(_job_payload(job), status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["post"], url_path=r"matching/jobs/(?P<job_id>\d+)/(?P<command>pause|resume)", permission_classes=[])
    def matching_job_control(self, request, job_id=None, command=None):
        from apps.license.models import ProductMatchingJob

        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        job = ProductMatchingJob.objects.filter(pk=job_id).first()
        if job is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        from apps.license.services.product_matching_semantic import request_pause, resume_job

        if command == "pause":
            request_pause(job)
        else:
            resume_job(job)
        job.refresh_from_db()
        return Response(_job_payload(job))

    @action(detail=False, methods=["get"], url_path="matching/health")
    def matching_health(self, request):
        from django.core.cache import cache

        from apps.license.services import product_embedding as pe

        cached = cache.get("product_matching_health_v1")
        if cached is not None:  # the worker inspect is a broadcast — at most once per 30 s
            return Response(cached)

        try:
            files = pe.files_status()
            model = {"ok": files["onnx"]["verified"] and files["tokenizer"]["verified"], "version": pe.model_version(), **files}
        except pe.EmbeddingUnavailable as exc:
            model = {"ok": False, "error": str(exc)}
        worker = {"ok": False}
        try:
            from lmanagement.celery import app as celery_app
            replies = celery_app.control.inspect(timeout=1.0).active_queues() or {}
            consumers = [name for name, queues in replies.items() if any(q.get("name") == "matching" for q in queues)]
            worker = {"ok": bool(consumers), "consumers": consumers}
        except Exception as exc:  # noqa: BLE001 — health reports, never raises
            logger.warning("Matching worker health check failed: %s", exc)
            worker["error"] = type(exc).__name__
        payload = {"model": model, "worker": worker, "available_memory_mb": pe.available_memory_mb()}
        cache.set("product_matching_health_v1", payload, 30)
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="matching/decide", permission_classes=[])
    def matching_decide(self, request):
        from apps.license.services.product_matching import MatchValidationError, decide, matching_groups, suggest

        if not _can_approve(request.user):
            return Response({"detail": "Product matching decisions require LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        body = request.data if isinstance(request.data, dict) else None
        if body is None:
            return Response({"detail": "A JSON object is required."}, status=status.HTTP_400_BAD_REQUEST)
        keys = body.get("source_keys") or []
        decision = body.get("decision")
        if not isinstance(keys, list) or not keys:
            return Response({"source_keys": "At least one source key is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not all(isinstance(k, str) for k in keys) or decision not in {"APPROVED", "REJECTED", "DIFFERENT"}:
            return Response({"detail": "source_keys must be strings and decision APPROVED / REJECTED / DIFFERENT."}, status=status.HTTP_400_BAD_REQUEST)
        clean = _clean_filters(body.get("filters"))
        if clean is None:
            return Response({"filters": "Must be an object of report filters."}, status=status.HTTP_400_BAD_REQUEST)
        # Recompute server-side: the client can never approve something the validator would not.
        filters = _filters(clean)
        from apps.license.services.product_matching_semantic import finalise
        wanted = set(keys)
        groups = [g for g in matching_groups(build_intelligence(select_pivot_licenses(**filters))) if g["source_key"] in wanted]
        raw = suggest(groups)
        evaluators = {r["source_key"]: r["_evaluate"] for r in raw if "_evaluate" in r}
        by_key = {s["source_key"]: s for s in finalise(raw)}
        missing = [k for k in keys if k not in by_key]
        if missing:
            return Response({"source_keys": f"Unknown or already resolved: {missing[:5]}"}, status=status.HTTP_400_BAD_REQUEST)
        item_id = body.get("item_id")
        if item_id is not None and (not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0):
            return Response({"item_id": "Must be an Item Name id."}, status=status.HTTP_400_BAD_REQUEST)
        raw_ids = body.get("item_ids") or {}
        if not isinstance(raw_ids, dict) or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in raw_ids.values()):
            return Response({"item_ids": "Must map each source key to an Item Name id."}, status=status.HTTP_400_BAD_REQUEST)
        item_ids = {str(k): v for k, v in raw_ids.items()}
        if decision == "APPROVED":
            # Mapping workspace spec (2026-11-19): a suggestion is never an approval — every approved source carries an
            # explicitly selected Item Name id (``item_id`` for one key, ``item_ids`` per key for bulk).
            unpicked = [k for k in keys if not (item_ids.get(k) or (item_id and len(keys) == 1))]
            if unpicked:
                return Response({"detail": f"Select an Item Name for every approved entry ({len(unpicked)} without one)."}, status=status.HTTP_400_BAD_REQUEST)
            multi = [k for k in keys if len(keys) > 1 and len(by_key[k].get("segments") or []) > 1]
            if multi:
                return Response({"detail": "Multi-product descriptions are approved individually, never in bulk."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = decide(suggestions=[by_key[k] for k in keys], decision=decision, user=request.user,
                          item_id=item_id if len(keys) == 1 else None, item_ids=item_ids, bulk=len(keys) > 1, evaluators=evaluators,
                          replace_links=body.get("replace_links") is True)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _drop_mapping_counts()
        return Response({"recorded": [r.pk for r in rows], "decision": decision,
                         "alias_skipped": [{"decision_id": r.pk, "reason": r.alias_skipped} for r in rows if getattr(r, "alias_skipped", None)]},
                        status=status.HTTP_201_CREATED)


class ItemPivotMultiProductMixin:
    """Multi-product selection and final classification (owner spec 2026-11-19)."""

    @action(detail=False, methods=["post"], url_path="matching/decide-products", permission_classes=[])
    def matching_decide_products(self, request):
        from apps.license.services.product_intelligence.multi_product import SelectionRejected, decide_products
        from apps.license.services.product_matching import MatchValidationError, matching_groups, suggest

        if not _can_approve(request.user):
            return Response({"detail": "Product classification requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        body = request.data or {}
        key, selections = body.get("source_key"), body.get("selections")
        if not isinstance(key, str) or not isinstance(selections, list) or not all(isinstance(x, dict) for x in selections):
            return Response({"detail": "source_key (string) and selections (list of {index | phrase, item_id}) are required."}, status=status.HTTP_400_BAD_REQUEST)
        clean = _clean_filters(body.get("filters"))
        if clean is None:
            return Response({"filters": "Must be an object of report filters."}, status=status.HTTP_400_BAD_REQUEST)
        # Recompute server-side: detected products, SION / HSN / entitlement context come from the data, never the client.
        groups = [g for g in matching_groups(build_intelligence(select_pivot_licenses(**_filters(clean)))) if g["source_key"] == key]
        rows = [r for r in suggest(groups) if r.get("segments")]
        if not rows:
            return Response({"detail": "Unknown source, or its description does not list several products."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = decide_products(suggestion=rows[0], selections=selections, user=request.user, partial=body.get("partial") is True,
                                     clear=body.get("clear") is True)
        except SelectionRejected as exc:
            return Response({"detail": str(exc), "results": [r.as_dict() for r in exc.results]}, status=status.HTTP_400_BAD_REQUEST)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _drop_mapping_counts()
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="matching/masters")
    def matching_masters(self, request):
        """Active canonical masters legitimate for a SION (searchable), for manual selection."""
        from django.db.models import Q

        from apps.core.models import ItemNameModel

        sion = (request.query_params.get("sion") or "").strip()
        q = (request.query_params.get("q") or "").strip()
        rows = ItemNameModel.objects.filter(is_active=True)
        if sion:
            rows = rows.filter(Q(norms__norm_class=sion) | Q(norms__isnull=True, sion_norm_class__norm_class=sion))
        if q:
            rows = rows.filter(name__icontains=q)
        return Response({"masters": [{"item_id": pk, "name": name} for pk, name in rows.distinct().order_by("name").values_list("pk", "name")[:200]]})


class ItemPivotConsolidationMixin:
    """Bulk canonical-product consolidation: preview → apply (selected eligible groups) → revert (owner request 2026-11-19)."""

    @action(detail=False, methods=["get"], url_path="matching/consolidation")
    def matching_consolidation(self, request):
        from apps.license.services.product_intelligence.consolidation import batches, preview
        from apps.license.services.product_matching import MatchValidationError

        sion, target = (request.query_params.get("sion") or "").strip(), _safe_int(request.query_params.get("target_id"), 0)
        if not sion or not target:
            return Response({"detail": "sion and target_id are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = preview(sion=sion, target_id=target)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**data, "can_apply": _can_approve(request.user), "batches": batches() if _can_approve(request.user) else []})

    @action(detail=False, methods=["post"], url_path="matching/consolidation/apply", permission_classes=[])
    def matching_consolidation_apply(self, request):
        from apps.license.services.product_intelligence.consolidation import apply
        from apps.license.services.product_matching import MatchValidationError

        if not _can_approve(request.user):
            return Response({"detail": "Bulk consolidation requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        body = request.data or {}
        keys = body.get("keys")
        if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            return Response({"keys": "A list of candidate group keys is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = apply(sion=str(body.get("sion") or ""), target_id=_safe_int(body.get("target_id"), 0), keys=keys,
                           user=request.user, reason=str(body.get("reason") or ""))
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _drop_mapping_counts()
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="matching/consolidation/revert", permission_classes=[])
    def matching_consolidation_revert(self, request):
        from apps.license.services.product_intelligence.consolidation import revert
        from apps.license.services.product_matching import MatchValidationError

        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        try:
            result = revert(batch=str((request.data or {}).get("batch") or ""), user=request.user)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _drop_mapping_counts()
        return Response(result)


class ItemPivotMappingChangeMixin:
    """Mapping-change versions, propagation status, impact report and retry (Part 15)."""

    @action(detail=False, methods=["get"], url_path="matching/mapping-changes")
    def mapping_changes(self, request):
        from apps.license.models import MappingChange
        from apps.license.services.product_intelligence.propagation import refresh_open, serialise

        refresh_open()
        rows = MappingChange.objects.select_related("created_by")[:100]
        return Response({"changes": [serialise(c) for c in rows], "can_retry": _can_approve(request.user)})

    @action(detail=False, methods=["get"], url_path=r"matching/mapping-changes/(?P<version>\d+)")
    def mapping_change_impact(self, request, version=None):
        from apps.license.models import MappingChange
        from apps.license.services.product_intelligence.propagation import impact

        change = MappingChange.objects.select_related("created_by").filter(pk=version).first()
        if change is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(impact(change))

    @action(detail=False, methods=["post"], url_path=r"matching/mapping-changes/(?P<version>\d+)/retry", permission_classes=[])
    def mapping_change_retry(self, request, version=None):
        from apps.license.models import MappingChange
        from apps.license.services.product_intelligence.propagation import retry, serialise

        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        change = MappingChange.objects.filter(pk=version).first()
        if change is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(serialise(retry(change, user=request.user)))


class ItemPivotItemNameMappingMixin:
    """Mapping workspace (owner spec 2026-11-19): BOE / allotment description → Item Name queues, approval, history and
    pending counts. Same ``ItemNameModel`` master as licence import items (``matching`` / ``matching/decide``).
    Reads: the viewset's ReportPermission. Writes: LICENSE_MANAGER."""

    @action(detail=False, methods=["get"], url_path="matching/item-name-mapping/counts")
    def item_name_mapping_counts(self, request):
        from apps.license.services.product_intelligence.item_name_mapping import counts

        return Response(counts())

    @action(detail=False, methods=["get"], url_path=r"matching/item-name-mapping/(?P<kind>import|boe|allotment)/history")
    def item_name_mapping_history(self, request, kind=None):
        from apps.license.services.product_intelligence.item_name_mapping import history

        params = request.query_params
        return Response(history(kind, offset=_safe_int(params.get("offset"), 0), limit=_safe_int(params.get("limit"), 50)))

    @action(detail=False, methods=["get"], url_path="matching/item-name-mapping/import/approved")
    def item_name_mapping_import_approved(self, request):
        """Active licence import item mappings (Approved Mappings table) — ``?q&offset&limit``."""
        from apps.license.services.product_intelligence.item_name_mapping import import_approved

        params = request.query_params
        data = import_approved(q=(params.get("q") or "").strip()[:200], offset=_safe_int(params.get("offset"), 0), limit=_safe_int(params.get("limit"), 50))
        return Response({**data, "can_undo": _can_approve(request.user)})

    @action(detail=False, methods=["post"], url_path=r"matching/item-name-mapping/import/approved/(?P<decision_id>\d+)/undo", permission_classes=[])
    def item_name_mapping_import_undo(self, request, decision_id=None):
        """Undo one active licence import item approval: the records return to Pending (idempotent, audited)."""
        from apps.license.services.product_intelligence.item_name_mapping import undo_import_approval
        from apps.license.services.product_matching import MatchValidationError

        if not _can_approve(request.user):
            return Response({"detail": "Undoing a mapping requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        try:
            result = undo_import_approval(decision_id=int(decision_id), user=request.user)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path=r"matching/item-name-mapping/(?P<kind>boe|allotment)")
    def item_name_mapping_queue(self, request, kind=None):
        from apps.license.services.product_intelligence.item_name_mapping import queue

        params = request.query_params
        data = queue(kind, q=(params.get("q") or "").strip()[:200], offset=_safe_int(params.get("offset"), 0), limit=_safe_int(params.get("limit"), 50))
        return Response({**data, "can_apply": _can_approve(request.user)})

    @action(detail=False, methods=["post"], url_path=r"matching/item-name-mapping/(?P<kind>boe|allotment)/apply", permission_classes=[])
    def item_name_mapping_apply(self, request, kind=None):
        """Body: ``{record_ids, item_id}`` (one entry) or ``{entries: [{record_ids, item_id}, ...]}`` (bulk — every
        entry carries its own selected Item Name id). All-or-nothing."""
        from apps.license.services.product_intelligence.item_name_mapping import apply_entries
        from apps.license.services.product_matching import MatchValidationError

        if not _can_approve(request.user):
            return Response({"detail": "Item Name mapping requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        body = request.data if isinstance(request.data, dict) else None
        if body is None:
            return Response({"detail": "A JSON object is required."}, status=status.HTTP_400_BAD_REQUEST)
        raw = body.get("entries") if "entries" in body else [{"record_ids": body.get("record_ids"), "item_id": body.get("item_id")}]

        def _ints(v):
            return isinstance(v, list) and bool(v) and all(isinstance(i, int) and not isinstance(i, bool) for i in v)

        if (not isinstance(raw, list) or not raw or len(raw) > 200
                or not all(isinstance(e, dict) and _ints(e.get("record_ids")) and isinstance(e.get("item_id"), int)
                           and not isinstance(e.get("item_id"), bool) for e in raw)):
            return Response({"entries": "Each entry needs a list of record ids and its own selected Item Name id."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = apply_entries(kind=kind, entries=raw, user=request.user, reason=str(body.get("reason") or ""))
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


def _model_payload(m):
    return {"id": m.pk, "version": m.version, "status": m.status, "algorithm": m.algorithm, "dataset": m.dataset.version,
            "metrics": m.metrics, "comparison": m.comparison, "notes": m.notes, "feature_names": m.feature_names,
            "trained_on": m.trained_on.isoformat(), "promoted_on": m.promoted_on.isoformat() if m.promoted_on else None,
            "trained_by": getattr(m.trained_by, "username", None)}


class ProductIntelligenceMixin:
    """Product Intelligence administration, alias registry and the reusable resolver (owner spec 2026-11-19)."""

    @action(detail=False, methods=["get"], url_path="matching/admin")
    def matching_admin(self, request):
        from django.core.cache import cache

        from apps.license.models import ProductAlias, ProductIntelAuditEvent, ProductIntelDataset, ProductIntelModel
        from apps.license.services.product_intelligence import knowledge, lifecycle

        key = knowledge.inventory_cache_key()
        inventory = cache.get(key)
        # A forced refresh scans four source tables — managers only; everyone else gets the cached copy.
        if inventory is None or (request.query_params.get("refresh") == "1" and _can_approve(request.user)):
            inventory = knowledge.inventory()
            cache.set(key, inventory, 600)
        active = ProductIntelModel.objects.filter(status=ProductIntelModel.ACTIVE).select_related("dataset").first()
        labels = cache.get(key + ":labels")
        if labels is None:
            labels = [{"label": x["label"]} for x in knowledge.verified_labels()]
            cache.set(key + ":labels", labels, 60)
        last_ds = ProductIntelDataset.objects.first()
        return Response({
            "can_manage": _can_approve(request.user), "inventory": inventory,
            "labels": {"verified": len(labels), "positive": sum(1 for x in labels if x["label"] == 1),
                       "negative": sum(1 for x in labels if x["label"] == 0),
                       "required": {"total": lifecycle.MIN_LABELS, "per_class": lifecycle.MIN_PER_CLASS},
                       "new_since_last_dataset": max(0, len(labels) - (last_ds.label_count if last_ds else 0))},
            "active_model": _model_payload(active) if active else None, "promotion_gate": lifecycle.PROMOTION_GATE,
            "models": [_model_payload(m) for m in ProductIntelModel.objects.select_related("dataset", "trained_by")[:20]],
            "datasets": [{"id": d.pk, "version": d.version, "observations": d.observation_count, "unique": d.unique_description_count,
                          "labels": d.label_count, "sha256": d.sha256, "summary": d.summary, "created_on": d.created_on.isoformat()}
                         for d in ProductIntelDataset.objects.all()[:10]],
            "aliases": ProductAlias.objects.filter(is_active=True).count(),
            # The audit trail (usernames, details) is for managers only.
            "events": [{"id": e.pk, "action": e.action, "detail": e.detail, "user": getattr(e.user, "username", None), "on": e.created_on.isoformat()}
                       for e in ProductIntelAuditEvent.objects.select_related("user")[:30]] if _can_approve(request.user) else [],
        })

    @action(detail=False, methods=["post"], url_path="matching/admin/train", permission_classes=[])
    def matching_admin_train(self, request):
        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        from apps.license.services.product_intelligence.lifecycle import TrainingRequestError, request_training

        raw = (request.data or {}).get("train", True)
        train = raw if isinstance(raw, bool) else str(raw).strip().lower() in {"1", "true", "yes"}
        try:
            task_id = request_training(user=request.user, train=train)
        except TrainingRequestError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)
        return Response({"task_id": task_id, "train": train}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["post"], url_path=r"matching/admin/models/(?P<model_id>\d+)/(?P<command>promote|reject)", permission_classes=[])
    def matching_admin_model(self, request, model_id=None, command=None):
        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        from apps.license.models import ProductIntelModel
        from apps.license.services.product_intelligence import lifecycle

        model = ProductIntelModel.objects.select_related("dataset").filter(pk=model_id).first()
        if model is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            model = lifecycle.promote(model, user=request.user) if command == "promote" else lifecycle.reject(model, user=request.user)
        except lifecycle.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_model_payload(model))

    @action(detail=False, methods=["post"], url_path="matching/admin/rollback", permission_classes=[])
    def matching_admin_rollback(self, request):
        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        from apps.license.services.product_intelligence import lifecycle

        try:
            target = lifecycle.rollback(user=request.user)
        except lifecycle.LifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"active_model": _model_payload(target) if target else None})

    @action(detail=False, methods=["get", "post"], url_path="matching/aliases", permission_classes=[])
    def matching_aliases(self, request):
        from apps.license.models import ProductAlias
        from apps.license.services.product_intelligence.aliases import create_alias
        from apps.license.services.product_matching import MatchValidationError

        if request.method == "GET":
            if not ReportPermission().has_permission(request, self):
                return Response(status=status.HTTP_403_FORBIDDEN if request.user.is_authenticated else status.HTTP_401_UNAUTHORIZED)
            q = (request.query_params.get("q") or "").strip()
            rows = ProductAlias.objects.filter(is_active=True).select_related("item", "sion", "created_by")
            if q:
                rows = rows.filter(normalized_alias__icontains=q.lower()) | rows.filter(item__name__icontains=q)
            return Response({"aliases": [{"id": a.pk, "alias": a.alias_text, "normalised": a.normalized_alias, "item_id": a.item_id, "item": a.item.name,
                                          "sion": getattr(a.sion, "norm_class", None), "source": a.source, "decision_id": a.decision_id,
                                          "created_by": getattr(a.created_by, "username", None), "created_on": a.created_on.isoformat()}
                                         for a in rows[:300]]})
        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        body = request.data or {}
        try:
            alias = create_alias(text=str(body.get("text") or ""), item_id=_safe_int(body.get("item_id"), 0), sion=body.get("sion") or None, user=request.user)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": alias.pk, "item_id": alias.item_id, "normalised": alias.normalized_alias}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path=r"matching/aliases/(?P<alias_id>\d+)/deactivate", permission_classes=[])
    def matching_alias_deactivate(self, request, alias_id=None):
        if not _can_approve(request.user):
            return Response({"detail": "Requires LICENSE_MANAGER."}, status=status.HTTP_403_FORBIDDEN)
        from apps.license.services.product_intelligence.aliases import deactivate_alias
        from apps.license.services.product_matching import MatchValidationError

        try:
            deactivate_alias(alias_id=int(alias_id), user=request.user)
        except MatchValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response({"id": int(alias_id), "is_active": False})

    @action(detail=False, methods=["get"], url_path="matching/resolve")
    def matching_resolve(self, request):
        """Reusable resolver (Licence Planning, Product Master, SION configuration): description + HSN + SION → candidates."""
        from apps.license.services.product_intelligence.resolver import resolve

        description = (request.query_params.get("description") or "").strip()
        if not description:
            return Response({"description": "A description is required."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resolve(description, hsn=request.query_params.get("hsn") or "", sion=request.query_params.get("sion") or None))
