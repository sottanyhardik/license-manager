from django.apps import AppConfig


class MDSClientConfig(AppConfig):
    """Django app for the Master-Data Service client + local mirror sync state."""

    name = "mds_client"
    verbose_name = "Master-Data Service client"
    default_auto_field = "django.db.models.BigAutoField"
