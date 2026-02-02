from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """Register signal handlers when Django starts."""
        # Import cache invalidation signals
        try:
            from core import cache_signals  # noqa: F401
            # Connect M2M signals after models are loaded
            cache_signals.connect_m2m_signals()
        except ImportError:
            pass  # Signals not available yet (during initial migration)
