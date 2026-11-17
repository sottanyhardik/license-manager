from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounting"
    label = "accounting"
    verbose_name = "Accounting"

    def ready(self) -> None:
        # Guards on trade models live here (accounting -> trade only; trade never imports accounting).
        from apps.accounting import signals  # noqa: F401
