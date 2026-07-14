# reports/tasks.py
"""
Celery tasks for async report generation.

Each task:
  1. Looks up its CeleryTaskTracker (created by the view before .delay())
  2. Updates status to STARTED
  3. Calls the relevant service
  4. Saves the result JSON to media/reports/
  5. Marks tracker SUCCESS (or FAILURE on exception, then retries)

The tracker is managed=False in production; tests must patch managed=True.
"""
import json
import logging
import os
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

REPORT_DIR = os.path.join(settings.MEDIA_ROOT, "reports")


def _ensure_report_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)


def _save_report_file(data: dict, filename: str) -> str:
    """
    Save report data as JSON.
    Returns relative path under MEDIA_ROOT (used as file_url fragment).
    """
    _ensure_report_dir()
    path = os.path.join(REPORT_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, default=str)
    return os.path.relpath(path, settings.MEDIA_ROOT)


def _mark_started(tracker):
    """Set tracker to STARTED and record started_at."""
    if tracker is None:
        return
    tracker.status = "STARTED"
    tracker.started_at = dj_timezone.now()
    tracker.save(update_fields=["status", "started_at"])


def _mark_success(tracker, rel_path: str):
    if tracker is None:
        return
    tracker.status = "SUCCESS"
    tracker.result = {"file_path": rel_path}
    tracker.completed_at = dj_timezone.now()
    tracker.save(update_fields=["status", "result", "completed_at"])


def _mark_failure(tracker, exc: Exception):
    if tracker is None:
        return
    tracker.status = "FAILURE"
    tracker.traceback = str(exc)
    tracker.completed_at = dj_timezone.now()
    tracker.save(update_fields=["status", "traceback", "completed_at"])


def _get_tracker(task_id: str):
    """Fetch CeleryTaskTracker or return None with a warning."""
    from apps.core.models import CeleryTaskTracker

    try:
        return CeleryTaskTracker.objects.get(task_id=task_id)
    except CeleryTaskTracker.DoesNotExist:
        logger.warning("CeleryTaskTracker not found for task %s", task_id)
        return None


# ---------------------------------------------------------------------------
# Balance report
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, acks_late=True, reject_on_worker_lost=True, name="generate_balance_report_task")
def generate_balance_report_task(self, license_ids: list, output_format: str, user_id: int):
    """Generate balance report. Store in media/reports/, update CeleryTaskTracker."""
    from apps.reports.services.balance_report import generate_balance_report

    task_id = self.request.id
    tracker = _get_tracker(task_id)
    _mark_started(tracker)

    try:
        data = generate_balance_report(license_ids, output_format)
        filename = f"balance_{task_id}.json"
        rel_path = _save_report_file(data, filename)
        _mark_success(tracker, rel_path)
        return {"file_path": rel_path}
    except Exception as exc:
        logger.exception("Balance report task %s failed", task_id)
        _mark_failure(tracker, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Item utilisation report
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, acks_late=True, reject_on_worker_lost=True, name="generate_item_report_task")
def generate_item_report_task(self, filters: dict, output_format: str, user_id: int):
    """Generate item utilisation report."""
    from apps.reports.services.item_report import generate_item_report

    task_id = self.request.id
    tracker = _get_tracker(task_id)
    _mark_started(tracker)

    try:
        data = generate_item_report(**filters)
        filename = f"items_{task_id}.json"
        rel_path = _save_report_file(data, filename)
        _mark_success(tracker, rel_path)
        return {"file_path": rel_path}
    except Exception as exc:
        logger.exception("Item report task %s failed", task_id)
        _mark_failure(tracker, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Pivot report
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, acks_late=True, reject_on_worker_lost=True, name="generate_pivot_report_task")
def generate_pivot_report_task(self, filters: dict, output_format: str, user_id: int):
    """Generate item pivot report (grouped by SION norm class)."""
    from apps.reports.services.pivot_report import generate_pivot_report

    task_id = self.request.id
    tracker = _get_tracker(task_id)
    _mark_started(tracker)

    try:
        data = generate_pivot_report(**filters)
        filename = f"pivot_{task_id}.json"
        rel_path = _save_report_file(data, filename)
        _mark_success(tracker, rel_path)
        return {"file_path": rel_path}
    except Exception as exc:
        logger.exception("Pivot report task %s failed", task_id)
        _mark_failure(tracker, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Ledger report
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, acks_late=True, reject_on_worker_lost=True, name="generate_ledger_report_task")
def generate_ledger_report_task(self, license_id: int, output_format: str, user_id: int):
    """Generate ledger report for a single license."""
    from apps.reports.services.ledger_report import generate_ledger_report

    task_id = self.request.id
    tracker = _get_tracker(task_id)
    _mark_started(tracker)

    try:
        data = generate_ledger_report(license_id)
        filename = f"ledger_{task_id}.json"
        rel_path = _save_report_file(data, filename)
        _mark_success(tracker, rel_path)
        return {"file_path": rel_path}
    except Exception as exc:
        logger.exception("Ledger report task %s failed", task_id)
        _mark_failure(tracker, exc)
        raise self.retry(exc=exc)
