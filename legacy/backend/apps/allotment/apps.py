from django.apps import AppConfig


class AllotmentConfig(AppConfig):
    name = "apps.allotment"
    label = "allotment"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apps.allotment.signals  # noqa: F401
