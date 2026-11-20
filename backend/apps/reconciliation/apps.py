from django.apps import AppConfig


class ReconciliationConfig(AppConfig):
    name = "apps.reconciliation"
    label = "reconciliation"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401  (registers SAT-DEF-150 / C-2 auto-link trigger)
        from . import item_cif_audit_signals  # noqa: F401  (DEC-50 automatic audit, owner F3)
