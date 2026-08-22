from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Register drf-spectacular extensions.  Importing this module is
        # schema-only and has no effect on API request handling.
        from apps.core import openapi  # noqa: F401
        try:
            from apps.core import cache_signals  # noqa: F401
            cache_signals.connect_m2m_signals()
            from apps.core.sync.signals import connect_master_outbox_signals
            connect_master_outbox_signals()
        except ImportError:
            pass
