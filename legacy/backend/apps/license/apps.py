from django.apps import AppConfig


class LicenseConfig(AppConfig):
    name = "apps.license"
    label = "license"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        try:
            import apps.license.signals  # noqa: F401
        except Exception:
            pass
