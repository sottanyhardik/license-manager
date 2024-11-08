# your_app/tasks.py
from celery import shared_task
from datetime import datetime, timedelta

from license.models import LicenseImportItemsModel


@shared_task
def update_items():
    current_date = datetime.now()
    date_90_days_ago = current_date - timedelta(days=90)
    items = LicenseImportItemsModel.objects.filter(license__license_expiry_date__gte=date_90_days_ago)
    for item in items:
        from bill_of_entry.tasks import update_balance_values_task
        update_balance_values_task(item.id)