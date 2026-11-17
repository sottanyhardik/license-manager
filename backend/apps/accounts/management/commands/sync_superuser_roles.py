"""Give every superuser every role (Django Group). Idempotent.

Signals keep this true for normal saves; run this after bulk paths that bypass model
signals (``QuerySet.update(is_superuser=True)``, raw SQL, ``loaddata``).

    python manage.py sync_superuser_roles
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.superuser_roles import sync_all_superusers


class Command(BaseCommand):
    help = "Assign every existing role to every superuser (never touches non-superusers)."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default", help="Database alias (default: default).")

    def handle(self, *args, **options):
        using = options["database"]
        with transaction.atomic(using=using):
            added = sync_all_superusers(using)
        self.stdout.write(self.style.SUCCESS(f"Superuser role sync complete: {added} assignment(s) added."))
