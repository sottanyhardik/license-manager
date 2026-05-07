from django.apps import AppConfig


class BillOfEntryConfig(AppConfig):
    name = 'bill_of_entry'

    def ready(self):
        import bill_of_entry.models  # noqa: F401 — ensures signals are registered
