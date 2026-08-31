"""Celery entry points for the durable licence replan ledger."""
from __future__ import annotations

import logging
import hashlib
import json
import os
import tempfile
import uuid
from datetime import timedelta

from celery import shared_task
from django.db import DatabaseError, OperationalError, transaction
from django.utils import timezone

from apps.license.models import LicenseReplanRequest

logger = logging.getLogger(__name__)
# Run durable replans on the default worker queue.  Local and existing server
# workers consume `celery`; a separate queue leaves accepted HTTP requests
# pending unless every worker is explicitly reconfigured.
QUEUE = "celery"
MAX_RETRIES = 3
STALE_RUNNING_AFTER = timedelta(minutes=10)

# Package jobs deliberately stay on the normal queue: deployers bound worker
# concurrency there, rather than relying on an unconsumed special-purpose
# queue.  The task payloads are database identifiers only.
PACKAGE_MAX_RETRIES = 3
PACKAGE_STALE_AFTER = timedelta(minutes=15)


def _package_key(job, *parts: str) -> str:
    """Return a storage-safe key; job keys are generated and validated at API creation."""
    safe = [str(part).replace("..", "").replace("\\", "_").replace("/", "_") for part in parts]
    return "/".join(["license-ledger-packages", job.key, *safe])


def _promote_storage_file(storage, key: str, source_path: str) -> None:
    """Publish a complete local staging file only after it has been written.

    Object storage uploads are atomic at object visibility level.  For Django's
    filesystem storage use ``os.replace`` as an actual atomic promotion.
    """
    from django.core.files import File
    from django.core.files.storage import FileSystemStorage
    if isinstance(storage, FileSystemStorage):
        destination = storage.path(key)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        os.replace(source_path, destination)
        return
    temporary_key = f"{key}.uploading-{uuid.uuid4().hex}"
    try:
        with open(source_path, "rb") as src:
            storage.save(temporary_key, File(src))
        # Storage backends do not provide a portable rename primitive.  Saving
        # the final object from a fully uploaded staging object keeps incomplete
        # local files invisible; S3-style backends publish a PUT atomically.
        with storage.open(temporary_key, "rb") as src:
            storage.save(key, File(src))
    finally:
        if storage.exists(temporary_key):
            storage.delete(temporary_key)
        if os.path.exists(source_path):
            os.unlink(source_path)


def _write_bytes(storage, key: str, content: bytes) -> tuple[int, str]:
    fd, path = tempfile.mkstemp(prefix="ledger-package-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        digest = hashlib.sha256(content).hexdigest()
        _promote_storage_file(storage, key, path)
        return len(content), digest
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _safe_error(exc: Exception) -> str:
    """Persist a useful but non-sensitive worker error."""
    message = str(exc).replace("\n", " ")[:500]
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def _set_job_status(job) -> None:
    from apps.license.models import LicenseLedgerPackageItem, LicenseLedgerPackageJob
    statuses = list(job.items.values_list("status", flat=True))
    if statuses and all(value == LicenseLedgerPackageItem.STATUS_SERVER_READY for value in statuses):
        return
    if any(value in (LicenseLedgerPackageItem.STATUS_GENERATING, LicenseLedgerPackageItem.STATUS_VALIDATING_SOURCES,
                     LicenseLedgerPackageItem.STATUS_MERGING) for value in statuses):
        status = LicenseLedgerPackageJob.STATUS_GENERATING
    elif any(value == LicenseLedgerPackageItem.STATUS_FAILED for value in statuses):
        status = LicenseLedgerPackageJob.STATUS_PARTIAL_FAILED if any(value == LicenseLedgerPackageItem.STATUS_SERVER_READY for value in statuses) else LicenseLedgerPackageJob.STATUS_FAILED
    else:
        status = LicenseLedgerPackageJob.STATUS_QUEUED
    if job.status != status:
        job.status = status
        job.save(update_fields=["status", "updated_at"])


def _transient(exc: Exception) -> bool:
    """Retry only database/transport classes, never domain validation."""
    return isinstance(exc, (OperationalError, DatabaseError, TimeoutError, ConnectionError))


@shared_task(
    bind=True,
    name="license.process_single_license",
    queue="celery",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_single_license_task(self, dict_data: dict) -> dict:
    """Create or update one licence parsed from an uploaded ledger file."""
    from scripts.parse_ledger import create_object

    license_no = dict_data.get("lic_no", "Unknown")
    logger.info("Processing uploaded ledger licence %s (task=%s)", license_no, self.request.id)
    license_number = create_object(dict_data)
    return {
        "status": "SUCCESS",
        "license_number": license_number,
        "lic_no": license_no,
    }


@shared_task(name="planning.dispatch_replan_requests", queue=QUEUE, acks_late=True, reject_on_worker_lost=True)
def dispatch_replan_requests(request_ids: list[int]):
    """Fan out one serialisable request identifier per licence task."""
    dispatched = 0
    for request_id in tuple(dict.fromkeys(int(pk) for pk in request_ids))[:1000]:
        with transaction.atomic():
            request = LicenseReplanRequest.objects.select_for_update().filter(pk=request_id).first()
            if not request or request.status not in (LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_RETRY_PENDING):
                continue
            request.status, request.queued_at = LicenseReplanRequest.STATUS_QUEUED, timezone.now()
            request.save(update_fields=["status", "queued_at"])
        try:
            result = replan_license_task.apply_async(args=[request_id], queue=QUEUE)
        except Exception:
            logger.exception("Could not dispatch replan worker request=%s", request_id)
            LicenseReplanRequest.objects.filter(pk=request_id, status=LicenseReplanRequest.STATUS_QUEUED).update(status=LicenseReplanRequest.STATUS_PENDING, queued_at=None)
            continue
        LicenseReplanRequest.objects.filter(pk=request_id, status=LicenseReplanRequest.STATUS_QUEUED).update(celery_task_id=str(result.id or ""), task_id=str(result.id or ""))
        dispatched += 1
    return {"dispatched": dispatched}


@shared_task(name="planning.replan_sion_batch", queue=QUEUE, acks_late=True, reject_on_worker_lost=True)
def replan_sion_batch(request_ids: list[int]):
    """Run one SION-wide user request serially, in the supplied licence order."""
    results = []
    for request_id in tuple(dict.fromkeys(int(pk) for pk in request_ids)):
        results.append(replan_license_task.run(request_id))
    return {"processed": len(results), "results": results}


@shared_task(bind=True, name="planning.replan_license", queue=QUEUE, acks_late=True, reject_on_worker_lost=True)
def replan_license_task(self, request_id: int):
    """Atomically REPLACE a single licence's generated plan under a row lock."""
    try:
        with transaction.atomic():
            request = LicenseReplanRequest.objects.select_for_update().select_related("license").get(pk=request_id)
            if request.status not in (LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED, LicenseReplanRequest.STATUS_RETRY_PENDING):
                return {"status": request.status, "request_id": request_id, "idempotent": True}
            license_obj = type(request.license).objects.select_for_update().get(pk=request.license_id)
            # Tasks carry no stale model snapshot: always calculate current data.
            request.source_revision = license_obj.planning_source_revision
            request.started_source_revision = license_obj.planning_source_revision
            request.status, request.started_at = LicenseReplanRequest.STATUS_RUNNING, timezone.now()
            request.attempts += 1
            request.celery_task_id = str(self.request.id or request.celery_task_id)
            request.task_id = request.celery_task_id
            request.save(update_fields=["source_revision", "started_source_revision", "status", "started_at", "attempts", "celery_task_id", "task_id"])

            from apps.license.views.sion_planning_rule import SionPlanningRuleViewSet
            from apps.license.services.sion_rule_engine import SionRulePlanningService
            # A licence can legitimately carry several SIONs.  The worker
            # owns their complete REPLACE calculation; rejecting it as a
            # single-SION HTTP shortcut would strand a durable request.
            if request.scope == LicenseReplanRequest.SCOPE_SION:
                # A SION-wide batch has already selected and scoped the
                # licence universe.  Re-resolving every SION attached to a
                # licence broadens the request and can fail on an unrelated
                # norm configuration.
                if request.sion_id is None:
                    raise ValueError("SION scope requires sion_id")
                sion_ids = [request.sion_id]
            else:
                if request.sion_id is not None:
                    raise ValueError("LICENSE scope must not include sion_id")
                try:
                    _, sion_ids = SionPlanningRuleViewSet._resolve_sions_for_license(request.license_id)
                except Exception as exc:
                    # Ledger-only licences are financially valid but have no
                    # planning domain.  Treat exactly the canonical resolver's
                    # NO_SION_NORMS outcome as a successful no-op; all other
                    # planning errors retain the existing failure semantics.
                    if getattr(exc, "code", None) != "NO_SION_NORMS":
                        raise
                    summary = {"planning_not_applicable": True, "sion_ids": [], "write_results": 0, "rules_executed": [], "failures": []}
                    request.status, request.completed_at = LicenseReplanRequest.STATUS_SUCCEEDED, timezone.now()
                    request.planned_revision, request.result = request.started_source_revision, summary
                    request.last_error = request.last_error_code = request.last_error_message = ""
                    request.save(update_fields=["status", "completed_at", "planned_revision", "result", "last_error", "last_error_code", "last_error_message"])
                    type(license_obj).objects.filter(pk=license_obj.pk).update(planning_applied_revision=request.started_source_revision)
                    logger.info("license_replan_not_applicable request=%s license=%s", request.pk, request.license_id)
                    return {"status": request.status, "request_id": request_id, **summary}
            results = []
            failures = []
            for sion_id in sion_ids:
                try:
                    results.append(SionRulePlanningService.plan_sion(
                        sion_id, license_ids=[request.license_id], mode="ALL", force_plan=True,
                    ))
                except Exception as exc:
                    # Licence scope is intentionally best-effort per norm: an
                    # invalid unrelated norm must not suppress a valid one.
                    if request.scope == LicenseReplanRequest.SCOPE_SION:
                        raise
                    failures.append({"sion_id": sion_id, "error": str(exc), "error_code": type(exc).__name__})
            summary = {
                "sion_ids": sion_ids,
                "write_results": sum(len(result.get("write_results", [])) for result in results),
                "rules_executed": [rule for result in results for rule in result.get("rules_executed", [])],
                "failures": failures,
            }

            # Do not acknowledge a calculation for an obsolete source
            # generation.  Source writers normally serialize on this licence
            # row, but a signal can run inside this task's transaction (and
            # tests intentionally exercise that path), so re-read before
            # moving the applied revision.  A replay is safe; claiming CURRENT
            # for a different source revision is not.
            current_source_revision = type(license_obj).objects.select_for_update().get(
                pk=license_obj.pk,
            ).planning_source_revision
            if current_source_revision != request.started_source_revision:
                request.status, request.completed_at = LicenseReplanRequest.STATUS_SUPERSEDED, timezone.now()
                request.result = summary
                request.save(update_fields=["status", "completed_at", "result"])

                # The source mutation may have coalesced onto this RUNNING
                # row.  Once it is terminal, create a fresh durable request
                # for the newer revision; its after-commit dispatch performs
                # the canonical REPLACE rather than reusing stale output.
                from apps.license.services.replan_requests import request_license_replan
                replacement = request_license_replan(
                    license_id=request.license_id,
                    reason="source_revision_superseded",
                )
                logger.info(
                    "license_replan_superseded request=%s license=%s started_revision=%s current_revision=%s replacement=%s",
                    request.pk, request.license_id, request.started_source_revision,
                    current_source_revision, replacement.pk,
                )
                return {
                    "status": request.status,
                    "request_id": request_id,
                    "replacement_request_id": replacement.pk,
                    **summary,
                }

            request.status, request.completed_at = LicenseReplanRequest.STATUS_SUCCEEDED, timezone.now()
            request.planned_revision, request.result = request.started_source_revision, summary
            request.last_error = request.last_error_code = request.last_error_message = ""
            request.save(update_fields=["status", "completed_at", "planned_revision", "result", "last_error", "last_error_code", "last_error_message"])
            type(license_obj).objects.filter(pk=license_obj.pk).update(planning_applied_revision=request.started_source_revision)
            logger.info("license_replan_succeeded request=%s license=%s revision=%s task=%s", request.pk, request.license_id, request.started_source_revision, self.request.id)
            return {"status": request.status, "request_id": request_id, **summary}
    except Exception as exc:
        logger.exception("license_replan_failed request=%s task=%s", request_id, self.request.id)
        retryable = _transient(exc)
        with transaction.atomic():
            request = LicenseReplanRequest.objects.select_for_update().filter(pk=request_id).first()
            if request:
                # The RUNNING transition is inside the replacement atomic
                # block, so it is rolled back with a failed calculation.
                # Persist the attempted delivery in this separate failure
                # transaction for audit/recovery decisions.
                request.attempts += 1
                request.retry_count += int(retryable)
                request.status = LicenseReplanRequest.STATUS_RETRY_PENDING if retryable and request.retry_count <= MAX_RETRIES else LicenseReplanRequest.STATUS_FAILED
                request.next_retry_at = timezone.now() + timedelta(seconds=2 ** request.retry_count) if request.status == LicenseReplanRequest.STATUS_RETRY_PENDING else None
                request.completed_at = timezone.now()
                request.last_error_code, request.last_error_message, request.last_error = type(exc).__name__, str(exc), str(exc)
                request.save(update_fields=["attempts", "retry_count", "status", "next_retry_at", "completed_at", "last_error_code", "last_error_message", "last_error"])
        return {"status": LicenseReplanRequest.STATUS_RETRY_PENDING if retryable else LicenseReplanRequest.STATUS_FAILED, "request_id": request_id, "error": str(exc)}


@shared_task(name="planning.recover_pending_replan_requests", queue=QUEUE, acks_late=True, reject_on_worker_lost=True)
def recover_pending_replan_requests(limit: int = 100):
    """Recover broker publication loss, vanished tasks and abandoned workers."""
    now, cap = timezone.now(), max(1, min(int(limit), 1000))
    with transaction.atomic():
        LicenseReplanRequest.objects.filter(status=LicenseReplanRequest.STATUS_RUNNING, started_at__lt=now - STALE_RUNNING_AFTER).update(status=LicenseReplanRequest.STATUS_RETRY_PENDING, next_retry_at=now)
        LicenseReplanRequest.objects.filter(status=LicenseReplanRequest.STATUS_QUEUED, queued_at__lt=now - STALE_RUNNING_AFTER).update(status=LicenseReplanRequest.STATUS_PENDING, queued_at=None)
        pending = list(LicenseReplanRequest.objects.filter(status=LicenseReplanRequest.STATUS_PENDING).order_by("requested_at", "pk").values_list("pk", flat=True)[:cap])
        retry = list(LicenseReplanRequest.objects.filter(status=LicenseReplanRequest.STATUS_RETRY_PENDING, next_retry_at__lte=now).order_by("requested_at", "pk").values_list("pk", flat=True)[:cap])
    return dispatch_replan_requests.run(list(dict.fromkeys(pending + retry))[:cap])


# Backwards compatible symbols for older operational callers.
run_license_replan = replan_license_task
dispatch_pending_license_replans = recover_pending_replan_requests


# ---------------------------------------------------------------------------
# Asynchronous licence-ledger package jobs
# ---------------------------------------------------------------------------
@shared_task(name="license.enqueue_license_ledger_package", queue=QUEUE, acks_late=True, reject_on_worker_lost=True)
def enqueue_license_ledger_package_job(job_pk: int, item_ids: list[int] | None = None) -> dict:
    """Fan out serialisable per-licence tasks after the job transaction commits."""
    from apps.license.models import LicenseLedgerPackageItem, LicenseLedgerPackageJob
    query = LicenseLedgerPackageItem.objects.filter(job_id=job_pk, status=LicenseLedgerPackageItem.STATUS_QUEUED)
    if item_ids is not None:
        query = query.filter(pk__in=list(dict.fromkeys(int(value) for value in item_ids)))
    ids = list(query.values_list("pk", flat=True))
    for item_id in ids:
        result = build_license_ledger_package_item.apply_async(args=[item_id], queue=QUEUE)
        LicenseLedgerPackageItem.objects.filter(pk=item_id, status=LicenseLedgerPackageItem.STATUS_QUEUED).update(celery_task_id=str(result.id or ""))
    return {"job_id": job_pk, "dispatched": len(ids)}


def _build_item_sections(item) -> tuple[bytes, dict]:
    """Render the four canonical sections once, retaining a compact audit manifest."""
    from io import BytesIO
    from pypdf import PdfWriter
    from apps.license.services.canonical_ledger_service import CanonicalLedgerService
    from apps.license.services import license_ledger_package as package

    licence = item.license
    dataset = CanonicalLedgerService.build_canonical_ledger_dataset(licence.pk, "DFIA")
    # The package service is the sole renderer/selector.  Recording candidates
    # separately is audit-only and does not alter selection or presentation.
    purchase_records = package._purchase_candidates(licence.pk)
    sales_records = package._final_party_sales_candidates(licence.pk)
    rendered_sections = package.LicenseLedgerPackageService.build_sections(
        dataset=dataset, requested_by=item.job.requested_by, base_url="",
    )
    content_by_name = dict(rendered_sections)
    sections = [(name, content_by_name.get(name, b""), records) for name, records in (
        ("01-custom-ledger.pdf", []), ("02-financial-ledger.pdf", []),
        ("03-main-purchase-invoices.pdf", purchase_records), ("04-final-party-sales-invoices.pdf", sales_records),
    )]
    # Resolve the immutable document identities separately from selection.
    # The package renderer and this audit use different code paths so an
    # accidentally omitted source cannot validate itself merely by sharing a
    # selector result.
    from apps.trade.models import LicenseTrade
    from apps.trade.services.invoice_document_service import InvoiceDocumentService
    expected_purchase_ids, expected_sales_ids, excluded_interlinked_ids = set(), set(), set()
    for record in purchase_records:
        if record.get("selection_result") == "INCLUDED":
            expected_purchase_ids.add(f"trade:{record['source_id']}")
    for record in sales_records:
        if record.get("is_interlinked"):
            excluded_interlinked_ids.add(record["source_id"])
        if record.get("selection_result") == "INCLUDED":
            trade = LicenseTrade.objects.get(pk=record["source_id"])
            document = InvoiceDocumentService.get_persisted_sale_document(trade)
            if document is None or not document.file or not document.file.name:
                raise package.PackageDocumentError(f"MISSING_FINAL_PARTY_SALES_INVOICE sale {trade.pk}")
            source = package._read_upload(document.file)
            if not source or not source.startswith(b"%PDF-"):
                raise package.PackageDocumentError(f"MISSING_FINAL_PARTY_SALES_INVOICE unreadable document sale {trade.pk}")
            record.update(document_id=document.pk, source_page_count=package._page_count(source),
                          sha256=hashlib.sha256(source).hexdigest())
            expected_sales_ids.add(document.pk)

    writer, section_manifest = PdfWriter(), []
    for name, content, records in sections:
        if content:
            page_start = len(writer.pages) + 1
            package._append_normalized_pdf(writer, content)
            included_records = [r for r in records if str(r.get("selection_result", "")).lower().startswith("included")]
            documents, cursor = [], page_start
            for record in included_records:
                pages = int(record.get("source_page_count") or 0)
                if pages:
                    documents.append({"document_id": record.get("document_id"), "invoice_number": record.get("invoice_number", ""),
                                      "source_pages": pages, "final_page_start": cursor, "final_page_end": cursor + pages - 1,
                                      "sha256": record.get("sha256", "")})
                    cursor += pages
            section_manifest.append({"filename": name, "status": "included", "page_count": package._page_count(content), "document_count": len(included_records), "final_page_start": page_start, "final_page_end": len(writer.pages), "documents": documents})
        else:
            section_manifest.append({"filename": name, "status": "not_applicable", "page_count": 0, "document_count": 0})
    output = BytesIO(); writer.write(output)
    if not writer.pages:
        raise ValueError("No canonical package pages were rendered")
    manifest = {
        "license_id": item.license_id, "licence_number": item.licence_number,
        "sections": section_manifest,
        "purchase_candidates": purchase_records, "sales_candidates": sales_records,
        "warnings": [],
        "document_counts": {entry["filename"]: entry["document_count"] for entry in section_manifest},
        "expected_main_purchase_document_ids": sorted(expected_purchase_ids),
        "expected_final_party_sales_document_ids": sorted(expected_sales_ids),
        "excluded_interlinked_sales_document_ids": sorted(excluded_interlinked_ids),
        "included_purchase_document_ids": sorted(expected_purchase_ids),
        "included_final_party_sales_document_ids": sorted(expected_sales_ids),
    }
    if (set(manifest["included_purchase_document_ids"]) != set(manifest["expected_main_purchase_document_ids"])
            or set(manifest["included_final_party_sales_document_ids"]) != set(manifest["expected_final_party_sales_document_ids"])
            or set(manifest["included_final_party_sales_document_ids"]) & set(manifest["excluded_interlinked_sales_document_ids"])):
        raise package.PackageDocumentError("PACKAGE_DOCUMENT_COMPLETENESS_INVARIANT_FAILED")
    return output.getvalue(), manifest, [(name, content) for name, content, _records in sections if content]


@shared_task(bind=True, name="license.build_license_ledger_package_item", queue=QUEUE, acks_late=True, reject_on_worker_lost=True,
             soft_time_limit=240, time_limit=300)
def build_license_ledger_package_item(self, item_pk: int) -> dict:
    """Idempotently create one final ``<licence-number>.pdf`` in shared storage."""
    from django.core.files.storage import default_storage
    from apps.license.models import LicenseLedgerPackageItem, LicenseLedgerPackageJob
    try:
        with transaction.atomic():
            item = LicenseLedgerPackageItem.objects.select_for_update().select_related("job", "license", "job__requested_by").get(pk=item_pk)
            if item.status == LicenseLedgerPackageItem.STATUS_SERVER_READY and item.output_key and default_storage.exists(item.output_key):
                return {"item_id": item.pk, "status": "server_ready", "idempotent": True}
            # Package data can be repaired asynchronously.  Do not render an
            # incomplete PDF and call it a task error; retain a specific,
            # re-evaluable data blocker instead.
            from apps.license.services.ledger_package_recovery import licence_readiness
            readiness = licence_readiness(item.license)
            if readiness["status"] != "READY":
                item.status = readiness["status"].lower()
                item.error = json.dumps(readiness, sort_keys=True)
                item.completed_at = None
                item.save(update_fields=["status", "error", "completed_at"])
                transaction.on_commit(lambda: finalize_license_ledger_package_job.delay(item.job_id))
                return {"item_id": item.pk, "status": item.status, "blockers": readiness}
            item.status, item.started_at, item.attempts, item.error = LicenseLedgerPackageItem.STATUS_GENERATING, timezone.now(), item.attempts + 1, ""
            item.celery_task_id = str(self.request.id or item.celery_task_id)
            item.save(update_fields=["status", "started_at", "attempts", "error", "celery_task_id"])
            job = item.job
            if not job.started_at:
                job.started_at = timezone.now()
                job.status = LicenseLedgerPackageJob.STATUS_GENERATING
                job.save(update_fields=["started_at", "status", "updated_at"])
        LicenseLedgerPackageItem.objects.filter(pk=item_pk).update(status=LicenseLedgerPackageItem.STATUS_VALIDATING_SOURCES)
        content, manifest, sections = _build_item_sections(item)
        # Publish immutable component files before the final merged output;
        # callers only receive the final file endpoint, never raw storage keys.
        LicenseLedgerPackageItem.objects.filter(pk=item_pk).update(status=LicenseLedgerPackageItem.STATUS_MERGING)
        for name, section in sections:
            _write_bytes(default_storage, _package_key(item.job, "licences", item.licence_number, name), section)
        key = _package_key(item.job, "output", f"{item.licence_number}.pdf")
        size, checksum = _write_bytes(default_storage, key, content)
        from pypdf import PdfReader
        page_count = len(PdfReader(__import__("io").BytesIO(content)).pages)
        with transaction.atomic():
            item = LicenseLedgerPackageItem.objects.select_for_update().get(pk=item_pk)
            item.status, item.completed_at = LicenseLedgerPackageItem.STATUS_SERVER_READY, timezone.now()
            item.output_key, item.output_size, item.output_checksum, item.output_page_count = key, size, checksum, page_count
            item.section_manifest, item.error = manifest, ""
            item.save(update_fields=["status", "completed_at", "output_key", "output_size", "output_checksum", "output_page_count", "section_manifest", "error"])
        finalize_license_ledger_package_job.delay(item.job_id)
        return {"item_id": item_pk, "status": "server_ready", "page_count": page_count}
    except Exception as exc:
        logger.exception("license package item failed item=%s", item_pk)
        transient = _transient(exc)
        item = LicenseLedgerPackageItem.objects.filter(pk=item_pk).select_related("job").first()
        if item and transient and self.request.retries < PACKAGE_MAX_RETRIES:
            LicenseLedgerPackageItem.objects.filter(pk=item_pk).update(status=LicenseLedgerPackageItem.STATUS_QUEUED, error=_safe_error(exc))
            raise self.retry(exc=exc, countdown=2 ** self.request.retries, max_retries=PACKAGE_MAX_RETRIES)
        if item:
            LicenseLedgerPackageItem.objects.filter(pk=item_pk).update(status=LicenseLedgerPackageItem.STATUS_FAILED, completed_at=timezone.now(), error=_safe_error(exc))
            finalize_license_ledger_package_job.delay(item.job_id)
        return {"item_id": item_pk, "status": "failed", "error": _safe_error(exc)}


@shared_task(name="license.finalize_license_ledger_package", queue=QUEUE, acks_late=True, reject_on_worker_lost=True,
             soft_time_limit=300, time_limit=360)
def finalize_license_ledger_package_job(job_pk: int) -> dict:
    """Create exactly one file-backed ZIP after every licence has succeeded."""
    from django.core.files.storage import default_storage
    from apps.license.models import LicenseLedgerPackageItem, LicenseLedgerPackageJob
    with transaction.atomic():
        job = LicenseLedgerPackageJob.objects.select_for_update().get(pk=job_pk)
        items = list(job.items.select_for_update().order_by("pk"))
        if not items:
            job.status, job.completed_at = LicenseLedgerPackageJob.STATUS_FAILED, timezone.now()
            job.error = "Package contains no licences"
            job.save(update_fields=["status", "completed_at", "error", "updated_at"])
            return {"job_id": job_pk, "status": "failed"}
        if any(item.status != LicenseLedgerPackageItem.STATUS_SERVER_READY for item in items):
            _set_job_status(job)
            return {"job_id": job_pk, "status": job.status}
        if job.archive_key == "__building__":
            return {"job_id": job_pk, "status": "finalizing", "idempotent": True}
        if job.archive_key and default_storage.exists(job.archive_key):
            return {"job_id": job_pk, "status": "server_ready", "idempotent": True}
        # An in-DB sentinel is a portable finalization lock across workers and
        # hosts.  It is not a downloadable key and is cleared on failure.
        job.archive_key = "__building__"
        job.save(update_fields=["archive_key", "updated_at"])
    # No DB lock while reading/zip-writing potentially large shared files.
    fd, path = tempfile.mkstemp(prefix="ledger-package-", suffix=".zip")
    try:
        from zipfile import ZIP_DEFLATED, ZipFile
        with os.fdopen(fd, "wb") as raw:
            with ZipFile(raw, "w", ZIP_DEFLATED, allowZip64=True) as archive:
                for item in items:
                    with default_storage.open(item.output_key, "rb") as source:
                        archive.writestr(f"{item.licence_number}.pdf", source.read())
                audit = {"job_id": job.key, "licences": [{"id": item.license_id, "licence_number": item.licence_number, "pages": item.output_page_count, "checksum": item.output_checksum} for item in items]}
                archive.writestr("manifest.json", json.dumps(audit, sort_keys=True, separators=(",", ":")))
        # The storage-side audit manifest deliberately contains logical names
        # and document identifiers only; it must never disclose media paths.
        job_manifest = {
            "job_id": job.key,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "licences": [{
                "id": item.license_id,
                "licence_number": item.licence_number,
                "status": item.status,
                "output": {"filename": f"{item.licence_number}.pdf", "size": item.output_size,
                           "sha256": item.output_checksum, "page_count": item.output_page_count},
                "sections": (item.section_manifest or {}).get("sections", []),
            } for item in items],
        }
        manifest_key = _package_key(job, "manifest.json")
        _write_bytes(default_storage, manifest_key, json.dumps(job_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        archive_key = _package_key(job, f"license-ledger-package-{job.key}.zip")
        _promote_storage_file(default_storage, archive_key, path)
        with transaction.atomic():
            job = LicenseLedgerPackageJob.objects.select_for_update().get(pk=job_pk)
            if job.archive_key == "__building__":
                job.archive_key, job.manifest_key, job.status, job.completed_at, job.error = archive_key, manifest_key, LicenseLedgerPackageJob.STATUS_SERVER_READY, timezone.now(), ""
                job.save(update_fields=["archive_key", "manifest_key", "status", "completed_at", "error", "updated_at"])
        return {"job_id": job_pk, "status": "server_ready"}
    except Exception as exc:
        logger.exception("license package archive finalization failed job=%s", job_pk)
        LicenseLedgerPackageJob.objects.filter(pk=job_pk, archive_key="__building__").update(
            archive_key="", status=LicenseLedgerPackageJob.STATUS_PARTIAL_FAILED, error=_safe_error(exc),
        )
        raise
    finally:
        if os.path.exists(path):
            os.unlink(path)


@shared_task(name="license.cleanup_expired_ledger_packages", queue=QUEUE)
def cleanup_expired_license_ledger_packages(limit: int = 100) -> dict:
    """Delete only expired terminal artifacts; never touches a running package."""
    from django.core.files.storage import default_storage
    from apps.license.models import LicenseLedgerPackageJob
    terminal = [LicenseLedgerPackageJob.STATUS_SERVER_READY, LicenseLedgerPackageJob.STATUS_FAILED, LicenseLedgerPackageJob.STATUS_PARTIAL_FAILED]
    jobs = list(LicenseLedgerPackageJob.objects.filter(expires_at__lte=timezone.now(), status__in=terminal).order_by("pk")[:max(1, min(int(limit), 1000))])
    for job in jobs:
        # Storage has no portable recursive delete.  Delete database-known keys;
        # component keys are deterministic and are removed alongside finals.
        keys = [job.manifest_key, job.archive_key, *job.items.values_list("output_key", flat=True)]
        for item in job.items.all():
            for section in (item.section_manifest or {}).get("sections", []):
                if section.get("status") == "included":
                    keys.append(_package_key(job, "licences", item.licence_number, section["filename"]))
        for key in keys:
            if key and default_storage.exists(key):
                default_storage.delete(key)
        job.delete()
    return {"deleted": len(jobs)}


@shared_task(name="license.recover_license_ledger_package_jobs", queue=QUEUE, acks_late=True, reject_on_worker_lost=True)
def recover_license_ledger_package_jobs(limit: int = 100) -> dict:
    """Recover commit-to-broker gaps and tasks lost during a worker restart."""
    from apps.license.models import LicenseLedgerPackageItem, LicenseLedgerPackageJob
    now, cap = timezone.now(), max(1, min(int(limit), 1000))
    stale = now - PACKAGE_STALE_AFTER
    # A lost worker is safe to replay: existing complete output short-circuits
    # in the idempotent item task.  Do not reset a completed item.
    LicenseLedgerPackageItem.objects.filter(status__in=[LicenseLedgerPackageItem.STATUS_GENERATING, LicenseLedgerPackageItem.STATUS_VALIDATING_SOURCES, LicenseLedgerPackageItem.STATUS_MERGING], started_at__lt=stale).update(
        status=LicenseLedgerPackageItem.STATUS_QUEUED, error="Worker recovery requeued incomplete task", started_at=None,
    )
    jobs = list(LicenseLedgerPackageJob.objects.filter(
        status__in=[LicenseLedgerPackageJob.STATUS_QUEUED, LicenseLedgerPackageJob.STATUS_GENERATING, LicenseLedgerPackageJob.STATUS_PARTIAL_FAILED],
    ).order_by("created_at", "pk")[:cap])
    dispatched = 0
    for job in jobs:
        ids = list(job.items.filter(status=LicenseLedgerPackageItem.STATUS_QUEUED).values_list("pk", flat=True))
        if ids:
            enqueue_license_ledger_package_job.delay(job.pk, ids)
            dispatched += len(ids)
        elif job.items.exists() and not job.items.exclude(status=LicenseLedgerPackageItem.STATUS_SERVER_READY).exists():
            finalize_license_ledger_package_job.delay(job.pk)
    return {"jobs": len(jobs), "dispatched": dispatched}
