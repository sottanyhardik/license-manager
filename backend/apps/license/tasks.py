"""Celery entry points for the durable licence replan ledger."""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import DatabaseError, OperationalError, transaction
from django.utils import timezone

from apps.license.models import LicenseReplanRequest

logger = logging.getLogger(__name__)
QUEUE = "license_planning"
MAX_RETRIES = 3
STALE_RUNNING_AFTER = timedelta(minutes=10)


def _transient(exc: Exception) -> bool:
    """Retry only database/transport classes, never domain validation."""
    return isinstance(exc, (OperationalError, DatabaseError, TimeoutError, ConnectionError))


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
            _, sion_ids = SionPlanningRuleViewSet._resolve_sions_for_license(request.license_id)
            results = [
                SionRulePlanningService.plan_sion(sion_id, license_ids=[request.license_id], mode="ALL", force_plan=True)
                for sion_id in sion_ids
            ]
            summary = {
                "sion_ids": sion_ids,
                "write_results": sum(len(result.get("write_results", [])) for result in results),
                "rules_executed": [rule for result in results for rule in result.get("rules_executed", [])],
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
