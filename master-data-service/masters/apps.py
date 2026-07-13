from django.apps import AppConfig


class MastersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "masters"

    def ready(self):
        # register the change-feed signal handlers
        from . import signals  # noqa: F401
