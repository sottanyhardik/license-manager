from django.apps import AppConfig


class BillOfEntryConfig(AppConfig):
    name = "apps.bill_of_entry"
    label = "bill_of_entry"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Ensure model-level side effects (signal decorators) run at startup.
        import apps.bill_of_entry.models  # noqa: F401
