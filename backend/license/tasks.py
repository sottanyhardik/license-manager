# license/tasks.py
from celery import shared_task
from datetime import datetime, timedelta
import logging

from license.models import LicenseImportItemsModel

logger = logging.getLogger(__name__)


@shared_task
def update_items():
    """Update balance values for license items (legacy task)"""
    current_date = datetime.now()
    date_90_days_ago = current_date - timedelta(days=90)
    items = LicenseImportItemsModel.objects.filter(
        license__license_expiry_date__gte=date_90_days_ago
    ).order_by('license__license_expiry_date', 'license__license_date')
    for item in items:
        from bill_of_entry.tasks import update_balance_values_task
        update_balance_values_task(item.id)


@shared_task
def sync_all_licenses():
    """
    Daily task to sync all licenses: update balance_cif, flags, and import item balances.
    Runs at 12:00 AM IST every day via Celery Beat.
    """
    from django.core.management import call_command
    from io import StringIO
    import sys

    logger.info("Starting daily license sync task...")

    # Capture command output
    output = StringIO()
    try:
        # Run the sync_licenses management command
        call_command(
            'sync_licenses',
            batch_size=100,
            stdout=output,
            stderr=output
        )

        output_str = output.getvalue()
        logger.info(f"License sync completed successfully:\n{output_str}")
        return {
            'status': 'success',
            'output': output_str,
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        error_msg = f"License sync failed: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Output: {output.getvalue()}")
        return {
            'status': 'error',
            'error': str(e),
            'output': output.getvalue(),
            'timestamp': datetime.now().isoformat()
        }