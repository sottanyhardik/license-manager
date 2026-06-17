"""
Reset the django_migrations table to match the consolidated single-initial layout.

WHAT THIS DOES
--------------
The migration files for the apps below were collapsed into a single
"0001_initial" (with "0002_initial" companions where cross-app FK cycles
required it). Existing production databases still have rows in
django_migrations referencing the OLD migration names — those files no
longer exist on disk, which makes Django refuse to start.

This command detects orphan migration rows (applied in DB but no file on
disk) for our apps and replaces them with rows for the new initial
migrations. Everything happens in a single transaction.

IT IS IDEMPOTENT.

- Fresh DB (no django_migrations table or no rows for our apps)  -> no-op.
- DB already on the new layout (no orphans)                      -> no-op.
- DB on the old layout (orphans present)                         -> reset.

It does NOT touch django.* or third-party apps' migration history, so
admin/contenttypes/auth/sessions/token_blacklist rows stay intact.
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader

OUR_APPS = [
    "accounts",
    "core",
    "license",
    "allotment",
    "bill_of_entry",
    "trade",
    "tasks",
]


class Command(BaseCommand):
    help = "Reset migration history to the consolidated single-initial layout. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without modifying the database.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        if not self._django_migrations_table_exists():
            self.stdout.write("django_migrations table does not exist. Fresh DB; nothing to do.")
            return

        loader = MigrationLoader(connection, ignore_no_migrations=True)
        disk = {(app, name) for (app, name) in loader.disk_migrations if app in OUR_APPS}
        applied = self._applied_for_our_apps()

        orphans = applied - disk
        missing = disk - applied

        if not orphans and not missing:
            self.stdout.write("Migration history is already in sync with disk. Nothing to do.")
            return

        if orphans:
            self.stdout.write(
                self.style.WARNING(f"Found {len(orphans)} orphan migration record(s) to remove:")
            )
            for app, name in sorted(orphans):
                self.stdout.write(f"  - {app}.{name}")

        if missing:
            self.stdout.write(
                self.style.WARNING(f"Found {len(missing)} new migration(s) to record as applied:")
            )
            for app, name in sorted(missing):
                self.stdout.write(f"  + {app}.{name}")

        if dry:
            self.stdout.write(self.style.NOTICE("--dry-run set; not modifying database."))
            return

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM django_migrations WHERE app = ANY(%s)",
                    [OUR_APPS],
                )
                for app, name in sorted(disk):
                    cursor.execute(
                        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
                        [app, name],
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Migration history reset complete. {len(disk)} row(s) now recorded."
            )
        )

    def _django_migrations_table_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'django_migrations'
                )
                """
            )
            return bool(cursor.fetchone()[0])

    def _applied_for_our_apps(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT app, name FROM django_migrations WHERE app = ANY(%s)",
                [OUR_APPS],
            )
            return {(row[0], row[1]) for row in cursor.fetchall()}
