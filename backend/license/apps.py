from django.apps import AppConfig


class LicenseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "license"

    def ready(self):
        try:
            import license.signals  # noqa: F401
        except Exception:
            pass
