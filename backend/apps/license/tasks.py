# license/tasks.py
"""
Celery tasks for the License module.

Balance recomputation is always asynchronous — never called inline in a
request/response cycle.  PDF generation is a placeholder that will delegate
to a report-generation service in Phase 8.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def recompute_license_balance_task(self, license_id: int):
    """
    Recompute the CIF balance for *license_id*.

    Retries up to 3 times with a 60-second countdown on failure.
    """
    try:
        from apps.license.services.balance_service import recompute_license_balance

        recompute_license_balance(license_id)
    except Exception as exc:
        logger.exception(
            "Balance recompute failed for license %s (attempt %s/%s): %s",
            license_id,
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=2)
def generate_license_pdf_task(self, license_id: int, report_type: str, user_id: int):
    """
    Placeholder task for async PDF generation.

    Phase 8 will implement actual PDF rendering; this task stores the
    submitted job in CeleryTaskTracker so the frontend can poll for completion.

    Returns: None (result stored externally in CeleryTaskTracker).
    """
    task_id = self.request.id
    logger.info(
        "PDF generation requested: license=%s report_type=%s user=%s task=%s",
        license_id,
        report_type,
        user_id,
        task_id,
    )
    try:
        from apps.core.models import CeleryTaskTracker

        CeleryTaskTracker.objects.filter(task_id=task_id).update(
            status="PENDING",
        )
    except Exception:
        # CeleryTaskTracker may not be populated yet — non-fatal
        pass
