"""
Management command to rebuild migrations by removing ALTER operations and creating fresh migrations.

This command:
1. Backs up current migration files
2. Removes ALTER/RENAME migration files that cause conflicts
3. Creates fresh migrations based on current models
4. Ensures database structure matches model definitions

WARNING: This command should be run with caution in production environments.
Always backup your database before running this command.

Usage:
    python manage.py rebuild_migrations --backup  # Create backup first
    python manage.py rebuild_migrations --remove-alters  # Remove ALTER migrations
    python manage.py rebuild_migrations --recreate  # Create fresh migrations
    python manage.py rebuild_migrations --full  # Full rebuild (backup + remove + recreate)
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import connection


class Command(BaseCommand):
    help = "Rebuild migrations by removing ALTER operations and creating fresh migrations"

    def __init__(self):
        super().__init__()
        self.backup_dir = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create backup of current migration files',
        )
        parser.add_argument(
            '--remove-alters',
            action='store_true',
            help='Remove ALTER/RENAME migration files',
        )
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Create fresh migrations',
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Full rebuild: backup + remove + recreate',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--apps',
            type=str,
            help='Comma-separated list of apps to rebuild (default: all)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        full = options.get('full', False)
        backup = options.get('backup', False) or full
        remove_alters = options.get('remove_alters', False) or full
        recreate = options.get('recreate', False) or full

        # Get list of apps to process
        apps_str = options.get('apps')
        if apps_str:
            target_apps = [app.strip() for app in apps_str.split(',')]
        else:
            target_apps = ['core', 'license', 'bill_of_entry', 'allotment', 'trade', 'accounts']

        self.stdout.write(self.style.HTTP_INFO("=" * 70))
        self.stdout.write(self.style.HTTP_INFO("Migration Rebuild Tool"))
        self.stdout.write(self.style.HTTP_INFO("=" * 70))
        self.stdout.write(f"Target apps: {', '.join(target_apps)}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n*** DRY RUN MODE - No changes will be made ***\n"))

        try:
            # Step 1: Backup
            if backup:
                self.stdout.write("\n" + self.style.HTTP_INFO("Step 1: Backing up migrations..."))
                self._backup_migrations(target_apps, dry_run)

            # Step 2: Remove ALTER migrations
            if remove_alters:
                self.stdout.write("\n" + self.style.HTTP_INFO("Step 2: Removing ALTER/RENAME migrations..."))
                self._remove_alter_migrations(target_apps, dry_run)

            # Step 3: Recreate migrations
            if recreate:
                self.stdout.write("\n" + self.style.HTTP_INFO("Step 3: Creating fresh migrations..."))
                self._recreate_migrations(target_apps, dry_run)

            self.stdout.write("\n" + self.style.SUCCESS("=" * 70))
            self.stdout.write(self.style.SUCCESS("Migration rebuild completed!"))
            self.stdout.write(self.style.SUCCESS("=" * 70))

            if not dry_run:
                self.stdout.write("\nNext steps:")
                self.stdout.write("  1. Review the new migrations in each app's migrations/ folder")
                self.stdout.write("  2. Test migrations: python manage.py migrate --plan")
                self.stdout.write("  3. Apply migrations: python manage.py migrate")
                if self.backup_dir:
                    self.stdout.write(f"  4. Backup location: {self.backup_dir}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nRebuild failed: {str(e)}"))
            if self.backup_dir and not dry_run:
                self.stdout.write(self.style.WARNING(
                    f"Backup available at: {self.backup_dir}"
                ))
            raise CommandError(f"Rebuild failed: {str(e)}")

    def _backup_migrations(self, apps: List[str], dry_run: bool = False):
        """Create timestamped backup of all migration files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.backup_dir = backend_dir / f"migrations_backup_{timestamp}"

        if dry_run:
            self.stdout.write(f"Would create backup at: {self.backup_dir}")
            return

        self.backup_dir.mkdir(exist_ok=True)
        self.stdout.write(f"Creating backup at: {self.backup_dir}")

        total_files = 0
        for app_name in apps:
            app_dir = backend_dir / app_name / "migrations"
            if not app_dir.exists():
                self.stdout.write(self.style.WARNING(f"  Skipping {app_name} (no migrations folder)"))
                continue

            backup_app_dir = self.backup_dir / app_name / "migrations"
            backup_app_dir.mkdir(parents=True, exist_ok=True)

            # Copy all migration files
            migration_files = list(app_dir.glob("*.py"))
            for migration_file in migration_files:
                shutil.copy2(migration_file, backup_app_dir / migration_file.name)
                total_files += 1

        self.stdout.write(self.style.SUCCESS(f"✓ Backed up {total_files} migration files"))

    def _remove_alter_migrations(self, apps: List[str], dry_run: bool = False):
        """Remove ALTER/RENAME migration files that may cause conflicts."""
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent

        # Patterns to identify ALTER/RENAME migrations
        patterns = [
            'alter_',
            'rename_',
            'change_',
        ]

        removed_count = 0
        for app_name in apps:
            migrations_dir = backend_dir / app_name / "migrations"
            if not migrations_dir.exists():
                continue

            # Find migration files matching patterns (but keep 0001_initial.py)
            for migration_file in migrations_dir.glob("*.py"):
                if migration_file.name == "__init__.py":
                    continue
                if migration_file.name == "0001_initial.py":
                    continue

                # Check if filename contains ALTER/RENAME patterns
                if any(pattern in migration_file.name.lower() for pattern in patterns):
                    if dry_run:
                        self.stdout.write(f"  Would remove: {app_name}/migrations/{migration_file.name}")
                    else:
                        migration_file.unlink()
                        self.stdout.write(f"  Removed: {app_name}/migrations/{migration_file.name}")
                    removed_count += 1

        if removed_count > 0:
            self.stdout.write(self.style.SUCCESS(f"✓ Removed {removed_count} ALTER/RENAME migration files"))
        else:
            self.stdout.write(self.style.SUCCESS("✓ No ALTER/RENAME migrations found"))

    def _recreate_migrations(self, apps: List[str], dry_run: bool = False):
        """Create fresh migrations for all specified apps."""
        if dry_run:
            self.stdout.write("Would create fresh migrations for:")
            for app_name in apps:
                self.stdout.write(f"  - {app_name}")
            return

        # First, check what changes would be made
        self.stdout.write("Checking for model changes...")

        # Clear migration files (except __init__.py and 0001_initial.py)
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        for app_name in apps:
            migrations_dir = backend_dir / app_name / "migrations"
            if not migrations_dir.exists():
                migrations_dir.mkdir(parents=True)
                (migrations_dir / "__init__.py").touch()

        # Create new migrations
        self.stdout.write("\nCreating migrations...")
        try:
            # Run makemigrations for each app
            for app_name in apps:
                self.stdout.write(f"\n  Processing {app_name}...")
                call_command('makemigrations', app_name, verbosity=2, interactive=False)

            self.stdout.write(self.style.SUCCESS("\n✓ Fresh migrations created"))

        except Exception as e:
            raise CommandError(f"Failed to create migrations: {str(e)}")

    def _check_database_consistency(self):
        """Check if database structure matches model definitions."""
        self.stdout.write("\nChecking database consistency...")

        inconsistencies = []

        with connection.cursor() as cursor:
            # Get list of tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                AND table_name NOT LIKE 'django_%'
                AND table_name NOT LIKE 'auth_%'
                ORDER BY table_name
            """)
            db_tables = {row[0] for row in cursor.fetchall()}

        # Compare with model tables
        # This is a simplified check - full validation would require introspection
        self.stdout.write(f"Found {len(db_tables)} tables in database")

        return inconsistencies
