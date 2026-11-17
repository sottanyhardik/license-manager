from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.db.models.signals import post_migrate

        from . import signals

        post_migrate.connect(
            signals.sync_superuser_roles_after_migrate, sender=self,
            dispatch_uid="accounts.sync_superuser_roles_after_migrate",
        )
