import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, acks_late=True, reject_on_worker_lost=True)
def generate_trade_pdf_task(self, trade_id: int, pdf_type: str, user_id: int):
    """Generate purchase invoice or bill of supply PDF asynchronously."""
    task_id = self.request.id
    logger.info(
        "Trade PDF generation: trade=%s type=%s user=%s task=%s",
        trade_id, pdf_type, user_id, task_id,
    )
    try:
        from apps.core.models import CeleryTaskTracker
        CeleryTaskTracker.objects.filter(task_id=task_id).update(status="PENDING")
    except Exception:
        pass
