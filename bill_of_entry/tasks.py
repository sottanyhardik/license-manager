from celery import shared_task

from core.scripts.calculate_balance import update_balance_values
from license.models import LicenseImportItemsModel


@shared_task
def update_balance_values_task(import_item_id):
    import_item = LicenseImportItemsModel.objects.get(id=import_item_id)
    update_balance_values(import_item)
