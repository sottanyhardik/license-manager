from django.apps import AppConfig


class BillOfEntryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bill_of_entry"
    label = "bill_of_entry"
    verbose_name = "Bill of Entry"
