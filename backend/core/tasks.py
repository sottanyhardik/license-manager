"""
Core periodic tasks — exchange rate sync from DGFT, etc.
"""
import logging

from celery import shared_task
from django.core.management import call_command


logger = logging.getLogger(__name__)


@shared_task(name="core.tasks.fetch_exchange_rates")
def fetch_exchange_rates():
    """
    Scheduled task to fetch the latest customs exchange rates from DGFT
    and write them to ExchangeRateModel.

    Scheduled daily at 07:30 IST (02:00 UTC).
    """
    try:
        call_command("fetch_exchange_rates", "--quiet")
        logger.info("Exchange rate sync complete")
        return {"success": True}
    except Exception as e:
        logger.exception("Exchange rate sync failed: %s", e)
        return {"success": False, "error": str(e)}
