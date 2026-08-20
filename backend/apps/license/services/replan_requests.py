"""Durable, transaction-safe asynchronous replanning request creation."""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.license.models import LicenseDetailsModel, LicenseReplanRequest

logger = logging.getLogger(__name__)
_ACTIVE = (LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED,
           LicenseReplanRequest.STATUS_RUNNING, LicenseReplanRequest.STATUS_RETRY_PENDING)


def _publish_after_commit(request_id: int) -> None:
    """Publish only a serialisable id; recovery owns the broker failure gap."""
    try:
        from apps.license.tasks import dispatch_replan_requests
        result = dispatch_replan_requests.delay([request_id])
        # Correlate the durable row with the first task in the chain.  The
        # dispatcher replaces this with the per-licence worker task id later.
        LicenseReplanRequest.objects.filter(
            pk=request_id, status=LicenseReplanRequest.STATUS_PENDING,
        ).update(task_id=str(result.id or ""))
    except Exception:
        # Not silent: audit logs expose the failure while the durable PENDING
        # row remains eligible for Beat recovery.
        logger.exception("Could not publish durable replan request %s; recovery will retry", request_id)


def _coalesce_locked(*, license_obj, reason: str, source_model: str = "", source_pk: str = ""):
    active = LicenseReplanRequest.objects.filter(license_id=license_obj.pk, status__in=_ACTIVE).first()
    if active:
        active.source_revision = license_obj.planning_source_revision
        active.reason = reason
        active.source_model = source_model or active.source_model
        active.source_pk = str(source_pk or active.source_pk)
        active.trigger_count = F("trigger_count") + 1
        active.save(update_fields=["source_revision", "reason", "source_model", "source_pk", "trigger_count"])
        active.refresh_from_db(fields=["trigger_count", "source_revision"])
        return active, False
    try:
        return LicenseReplanRequest.objects.create(
            license_id=license_obj.pk, reason=reason, source_revision=license_obj.planning_source_revision,
            source_model=source_model, source_pk=str(source_pk or ""), status=LicenseReplanRequest.STATUS_PENDING,
        ), True
    except IntegrityError:
        return LicenseReplanRequest.objects.get(license_id=license_obj.pk, status__in=_ACTIVE), False


def request_license_replan(*, license_id: int, reason: str, source_model: str = "", source_pk: str | int | None = None, dispatch: bool = True) -> LicenseReplanRequest:
    """Create/coalesce a request without changing a source generation.

    ``dispatch=False`` is for the explicit HTTP Auto Plan action, which runs
    the same durable request body synchronously and must not also publish a
    duplicate Celery task after the response is returned.
    """
    if not reason or len(reason) > 100:
        raise ValueError("reason must contain between 1 and 100 characters")
    with transaction.atomic():
        license_obj = LicenseDetailsModel.objects.select_for_update().get(pk=license_id)
        request, created = _coalesce_locked(license_obj=license_obj, reason=reason, source_model=source_model, source_pk=str(source_pk or ""))
        if created and dispatch:
            transaction.on_commit(lambda request_id=request.pk: _publish_after_commit(request_id))
        return request


def mark_license_replan_source_changed(*, license_id: int, reason: str, source_model: str = "", source_pk: str | int | None = None) -> LicenseReplanRequest:
    """Advance one source generation and create/coalesce a durable request.

    No planner is imported here: this is safe for signals and web requests.
    """
    if not reason or len(reason) > 100:
        raise ValueError("reason must contain between 1 and 100 characters")
    with transaction.atomic():
        license_obj = LicenseDetailsModel.objects.select_for_update().get(pk=license_id)
        LicenseDetailsModel.objects.filter(pk=license_id).update(planning_source_revision=F("planning_source_revision") + 1)
        license_obj.refresh_from_db(fields=["planning_source_revision"])
        request, created = _coalesce_locked(license_obj=license_obj, reason=reason, source_model=source_model, source_pk=str(source_pk or ""))
        if request.status == LicenseReplanRequest.STATUS_RETRY_PENDING:
            request.status, request.next_retry_at = LicenseReplanRequest.STATUS_PENDING, None
            request.save(update_fields=["status", "next_retry_at"])
        if created or request.status == LicenseReplanRequest.STATUS_PENDING:
            transaction.on_commit(lambda request_id=request.pk: _publish_after_commit(request_id))
        return request
