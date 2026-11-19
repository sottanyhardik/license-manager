"""Semantic candidate discovery for product matching (local MiniLM embeddings).

Runs only inside the Celery ``matching`` task. Embeddings are persisted once per
(model version, prepared-text hash). Similarity *proposes* candidates; it never
approves: a semantic-only pick is capped at the REVIEW band (≤ 89) and is
re-validated with the same SION / HSN / entitlement / multi-product checks as
the deterministic matcher. Approved mappings stay in ``ProductMatchDecision``.
"""
from __future__ import annotations

import os
import logging
import time
from collections import defaultdict
from datetime import timedelta

import numpy as np
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import ItemNameModel
from apps.license.models import ProductMatchingJob, ProductMatchSuggestion, ProductTextEmbedding
from apps.license.services import product_embedding as pe
from apps.license.services.product_matching import REVIEW, STRONG, _band, master_label, matching_groups, normalise, suggest

SEMANTIC_MIN = float(os.environ.get("PRODUCT_MATCH_SEMANTIC_MIN", "0.60"))
STALE_AFTER = timedelta(hours=1)  # > the task's hard time limit (1900 s)
logger = logging.getLogger(__name__)
SEMANTIC_CAP = STRONG - 1  # 89: semantic evidence alone never reaches STRONG / HIGH
MIN_AVAILABLE_MB = float(os.environ.get("PRODUCT_MATCH_MIN_AVAILABLE_MB", "350"))
TOP_K = 5


class JobPaused(Exception):
    pass


def embedding_text(text: str) -> str:
    """Original wording plus the deterministic abbreviation / spelling expansion (PP → polypropylene)."""
    original = pe.prepare_text(text)
    expanded = normalise(text)
    return original if not expanded or expanded == original.lower() else f"{original} | {expanded}"


def _vectors(kind: str, items: list[tuple[str, str]], version: str, *, batch_size: int, guard) -> tuple[dict[str, np.ndarray], int]:
    """{ref: vector} for (ref, text) pairs; reuses persisted rows, embeds only new texts."""
    prepared = [(ref, embedding_text(text)) for ref, text in items]
    hashes = {ref: pe.text_hash(text) for ref, text in prepared}
    stored = {row.text_hash: pe.from_bytes(bytes(row.vector)) for row in
              ProductTextEmbedding.objects.filter(model_version=version, kind=kind, text_hash__in=set(hashes.values()))}
    missing = list({hashes[ref]: (ref, text) for ref, text in prepared if hashes[ref] not in stored}.values())
    if missing:
        vectors = pe.embed([text for _, text in missing], batch_size=batch_size, before_batch=guard)
        ProductTextEmbedding.objects.bulk_create([
            ProductTextEmbedding(model_version=version, kind=kind, text_hash=hashes[ref], ref=str(ref)[:600], vector=pe.to_bytes(v))
            for (ref, _), v in zip(missing, vectors, strict=True)
        ], ignore_conflicts=True)
        stored.update({hashes[ref]: v for (ref, _), v in zip(missing, vectors, strict=True)})
    return {ref: stored[h] for ref, h in hashes.items()}, len(missing)


def _legit_masters(sion_codes: set[str]) -> dict[str, list[ItemNameModel]]:
    out: dict[str, list[ItemNameModel]] = defaultdict(list)
    for name in ItemNameModel.objects.filter(is_active=True).prefetch_related("norms").select_related("sion_norm_class"):
        legit = {n.norm_class for n in name.norms.all()} or ({name.sion_norm_class.norm_class} if name.sion_norm_class_id else set())
        for code in legit & sion_codes:
            out[code].append(name)
    return out


def run_job(job: ProductMatchingJob) -> ProductMatchingJob:
    from apps.license.services.item_pivot_intelligence import build_intelligence
    from apps.license.services.item_pivot_selection import select_pivot_licenses
    from apps.license.api.views.item_pivot_intelligence import _filters

    started = time.perf_counter()
    metrics = {"min_available_mb": pe.available_memory_mb(), "embedded_new": 0}
    # Atomic claim: only one worker runs a job; a RUNNING job whose worker died (no finish for STALE_AFTER)
    # can be re-claimed, so a crash never leaves it stuck forever.
    claimable = Q(status__in=[ProductMatchingJob.QUEUED, ProductMatchingJob.PAUSED, ProductMatchingJob.FAILED]) | Q(
        status=ProductMatchingJob.RUNNING, started_on__lt=timezone.now() - STALE_AFTER)
    if not ProductMatchingJob.objects.filter(claimable, pk=job.pk).update(status=ProductMatchingJob.RUNNING, started_on=timezone.now(), error=""):
        job.refresh_from_db()
        return job
    try:
        version = pe.model_version()
    except pe.EmbeddingUnavailable as exc:
        ProductMatchingJob.objects.filter(pk=job.pk).update(status=ProductMatchingJob.FAILED, error=str(exc), finished_on=timezone.now())
        job.refresh_from_db()
        return job

    def guard():
        available = pe.available_memory_mb()
        if available is not None:
            metrics["min_available_mb"] = min(metrics["min_available_mb"] or available, available)
            if available < MIN_AVAILABLE_MB:
                raise JobPaused(f"Memory pressure: {available:.0f} MB available < {MIN_AVAILABLE_MB:.0f} MB")
        if ProductMatchingJob.objects.filter(pk=job.pk, pause_requested=True).exists():
            raise JobPaused("Paused by user")

    ProductMatchingJob.objects.filter(pk=job.pk).update(model_version=version)
    try:
        groups = matching_groups(build_intelligence(select_pivot_licenses(**_filters(job.filters))))
        pending = [s for s in suggest(groups) if s["band"] != "APPROVED"]
        ProductMatchingJob.objects.filter(pk=job.pk).update(total=len(pending), processed=0)
        masters = _legit_masters({s["sion"] for s in pending if s.get("sion")})
        master_vecs, new_m = _vectors(ProductTextEmbedding.MASTER, [(str(m.pk), master_label(m.name)) for ms in masters.values() for m in ms],
                                      version, batch_size=job.batch_size, guard=guard)
        metrics["embedded_new"] += new_m
        step = max(job.batch_size * 5, 20)
        for start in range(0, len(pending), step):
            part = pending[start:start + step]
            source_vecs, new_s = _vectors(ProductTextEmbedding.SOURCE, [(s["source_key"], s["description"]) for s in part],
                                          version, batch_size=job.batch_size, guard=guard)
            metrics["embedded_new"] += new_s
            with transaction.atomic():
                for s in part:
                    pool = masters.get(s.get("sion") or "", [])
                    if not pool:
                        continue
                    matrix = np.stack([master_vecs[str(m.pk)] for m in pool])
                    sims = matrix @ source_vecs[s["source_key"]]
                    order = np.argsort(-sims)[:TOP_K]
                    top = [{"item_id": pool[i].pk, "name": pool[i].name, "similarity": round(float(sims[i]), 4)} for i in order]
                    ProductMatchSuggestion.objects.update_or_create(
                        source_key=s["source_key"], model_version=version,
                        defaults={"job": job, "semantic_item_id": top[0]["item_id"], "similarity": top[0]["similarity"], "semantic_candidates": top},
                    )
            ProductMatchingJob.objects.filter(pk=job.pk).update(processed=min(start + step, len(pending)))
        status = ProductMatchingJob.DONE
    except JobPaused as exc:
        status, metrics["paused_reason"] = ProductMatchingJob.PAUSED, str(exc)
    except pe.EmbeddingUnavailable as exc:
        status = ProductMatchingJob.FAILED
        ProductMatchingJob.objects.filter(pk=job.pk).update(error=str(exc))
    except Exception as exc:  # noqa: BLE001 — any failure (DB, soft time limit, bug) is recorded, never left RUNNING
        logger.exception("Product matching job %s failed", job.pk)
        status = ProductMatchingJob.FAILED
        ProductMatchingJob.objects.filter(pk=job.pk).update(error=f"{type(exc).__name__}: {exc}"[:2000])
    metrics.update({"seconds": round(time.perf_counter() - started, 2), "peak_rss_mb": round(pe.peak_rss_mb()), "batch_size": job.batch_size})
    ProductMatchingJob.objects.filter(pk=job.pk).update(
        status=status, metrics=metrics, pause_requested=False,
        finished_on=timezone.now() if status in {ProductMatchingJob.DONE, ProductMatchingJob.FAILED} else None,
    )
    job.refresh_from_db()
    return job


def merge_semantic(row: dict, semantic: ProductMatchSuggestion | None) -> dict:
    """Fold persisted semantic evidence into a deterministic suggestion (never clears a conflict)."""
    evaluate = row.get("_evaluate")
    out = {k: v for k, v in row.items() if k != "_evaluate"}
    if semantic is None or row["band"] == "APPROVED":
        return out
    rejected = set(row.get("rejected_item_ids") or [])
    candidates = [c for c in semantic.semantic_candidates if c["item_id"] not in rejected]
    out["semantic"] = {"model_version": semantic.model_version, "similarity": semantic.similarity, "candidates": candidates}
    top = candidates[0] if candidates else None
    det = row.get("suggestion")
    if top and det and top["item_id"] == det["item_id"]:
        out["explanation"] = f"{row['explanation']}; semantic similarity {top['similarity']:.2f} agrees"
    elif top and top["similarity"] >= SEMANTIC_MIN and (det is None or row["confidence"] < REVIEW) and evaluate:
        conflicts, checks = evaluate(top["item_id"])
        out.update({
            "suggestion": {"item_id": top["item_id"], "name": top["name"]}, "checks": checks, "conflicts": conflicts,
            "confidence": min(SEMANTIC_CAP, round(top["similarity"] * 100)), "matcher": semantic.model_version,
            "explanation": f"Semantic similarity {top['similarity']:.2f} (local MiniLM) — candidate only, review required",
        })
        out.update(_band(out))
    elif top and det and top["item_id"] != det["item_id"]:
        out["explanation"] = f"{row['explanation']}; semantic model prefers {top['name']} ({top['similarity']:.2f}) — review"
    return out


def finalise(suggestions: list[dict]) -> list[dict]:
    """Deterministic suggestions + latest persisted semantic evidence for the current model version."""
    try:
        version = pe.model_version()
    except pe.EmbeddingUnavailable:
        version = None
    stored = {}
    if version:
        stored = {s.source_key: s for s in ProductMatchSuggestion.objects.filter(
            model_version=version, source_key__in=[r["source_key"] for r in suggestions])}
    return [merge_semantic(row, stored.get(row["source_key"])) for row in suggestions]


# --- Job lifecycle (writes live here, not in views) -------------------------------------------

def create_job(*, filters: dict, batch_size: int, user) -> ProductMatchingJob:
    """Create a QUEUED job and dispatch it to the Celery ``matching`` queue."""
    from apps.license.tasks import run_product_matching_job

    job = ProductMatchingJob.objects.create(filters=filters, batch_size=batch_size, created_by=user)
    run_product_matching_job.delay(job.pk)
    return job


def request_pause(job: ProductMatchingJob) -> None:
    """Ask a queued/running job to pause at its next checkpoint."""
    ProductMatchingJob.objects.filter(pk=job.pk, status__in=[ProductMatchingJob.QUEUED, ProductMatchingJob.RUNNING]).update(pause_requested=True)


def resume_job(job: ProductMatchingJob) -> None:
    """Re-queue a paused/failed job; already-stored embeddings are reused."""
    from apps.license.tasks import run_product_matching_job

    # Conditional update = the guard: a double-click re-queues once.
    if ProductMatchingJob.objects.filter(pk=job.pk, status__in=[ProductMatchingJob.PAUSED, ProductMatchingJob.FAILED]).update(
            status=ProductMatchingJob.QUEUED, pause_requested=False):
        run_product_matching_job.delay(job.pk)
