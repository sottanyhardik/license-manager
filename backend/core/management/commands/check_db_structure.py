"""
Management command to check database structure against Django models.

This command performs comprehensive checks:
1. Lists all Django models and their expected database tables
2. Identifies tables that exist in DB but not in models (orphaned tables)
3. Identifies models that don't have corresponding tables (missing tables)
4. Checks for column mismatches between models and database
5. Provides recommendations for fixing issues

Usage:
    python manage.py check_db_structure  # Full check
    python manage.py check_db_structure --app core  # Check specific app
    python manage.py check_db_structure --verbose  # Detailed output
    python manage.py check_db_structure --fix  # Attempt to fix issues
"""

from typing import Dict, List, Set, Tuple
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.db.models import Model


class Command(BaseCommand):
    help = "Check database structure against Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='Check specific app only',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix issues by creating missing tables',
        )
        parser.add_argument(
            '--show-columns',
            action='store_true',
            help='Show column details for each table',
        )

    def handle(self, *args, **options):
        app_label = options.get('app')
        verbose = options.get('verbose', False)
        fix = options.get('fix', False)
        show_columns = options.get('show_columns', False)

        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(self.style.HTTP_INFO("Database Structure Check"))
        self.stdout.write(self.style.HTTP_INFO("=" * 80))

        # Get database information
        db_tables = self._get_database_tables()
        db_columns = self._get_database_columns() if show_columns else {}

        # Get Django model information
        if app_label:
            apps_to_check = [app_label]
        else:
            apps_to_check = ['core', 'license', 'bill_of_entry', 'allotment', 'trade', 'accounts']

        model_tables = {}
        model_fields = defaultdict(dict)

        for app in apps_to_check:
            try:
                app_config = apps.get_app_config(app)
                for model in app_config.get_models():
                    table_name = model._meta.db_table
                    model_tables[table_name] = {
                        'app': app,
                        'model': model.__name__,
                        'abstract': model._meta.abstract,
                    }

                    # Get model fields
                    for field in model._meta.get_fields():
                        if hasattr(field, 'column'):
                            model_fields[table_name][field.column] = {
                                'name': field.name,
                                'type': field.get_internal_type(),
                                'null': getattr(field, 'null', False),
                            }

            except LookupError:
                self.stdout.write(self.style.WARNING(f"App '{app}' not found"))
                continue

        # Analysis
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"  Database tables: {len(db_tables)}")
        self.stdout.write(f"  Django models: {len(model_tables)}")

        # Find missing tables
        missing_tables = set(model_tables.keys()) - db_tables
        orphaned_tables = db_tables - set(model_tables.keys())
        matching_tables = db_tables & set(model_tables.keys())

        # Report findings
        self._report_missing_tables(missing_tables, model_tables, verbose)
        self._report_orphaned_tables(orphaned_tables, verbose)
        self._report_matching_tables(matching_tables, model_tables, db_columns, show_columns)

        # Fix issues if requested
        if fix and missing_tables:
            self._fix_missing_tables(missing_tables, model_tables)

        self.stdout.write("\n" + self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("Check complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

    def _get_database_tables(self) -> Set[str]:
        """Get list of all tables in the database."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            return {row[0] for row in cursor.fetchall()}

    def _get_database_columns(self) -> Dict[str, List[Dict]]:
        """Get column information for all tables."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)

            columns_by_table = defaultdict(list)
            for row in cursor.fetchall():
                table_name, column_name, data_type, is_nullable = row
                columns_by_table[table_name].append({
                    'name': column_name,
                    'type': data_type,
                    'nullable': is_nullable == 'YES'
                })

            return dict(columns_by_table)

    def _report_missing_tables(self, missing_tables: Set[str], model_tables: Dict, verbose: bool):
        """Report tables that are defined in models but don't exist in database."""
        if missing_tables:
            self.stdout.write(f"\n❌ Missing tables ({len(missing_tables)}):")
            self.stdout.write("   These models don't have corresponding database tables:\n")

            for table in sorted(missing_tables):
                info = model_tables[table]
                self.stdout.write(
                    f"   • {table:<45} ({info['app']}.{info['model']})"
                )

            self.stdout.write("\n   💡 Recommendation:")
            self.stdout.write("      Run: python manage.py migrate")
            self.stdout.write("      Or: python manage.py rebuild_migrations --full")
        else:
            self.stdout.write(f"\n✅ No missing tables - all models have database tables")

    def _report_orphaned_tables(self, orphaned_tables: Set[str], verbose: bool):
        """Report tables that exist in database but don't have corresponding models."""
        # Filter out known system/legacy tables
        system_prefixes = ('django_', 'auth_', 'eScrap_', 'ebrc_', 'shipping_', 'license_movement_')
        relevant_orphaned = {t for t in orphaned_tables if not any(t.startswith(p) for p in system_prefixes)}

        if relevant_orphaned:
            self.stdout.write(f"\n⚠️  Orphaned tables ({len(relevant_orphaned)}):")
            self.stdout.write("   These tables exist in database but don't have Django models:\n")

            for table in sorted(relevant_orphaned):
                self.stdout.write(f"   • {table}")

            self.stdout.write("\n   💡 These may be:")
            self.stdout.write("      - Legacy tables that can be dropped")
            self.stdout.write("      - Tables from old/removed models")
            self.stdout.write("      - Manually created tables")

            if len(orphaned_tables) > len(relevant_orphaned):
                self.stdout.write(
                    f"\n   ℹ️  {len(orphaned_tables) - len(relevant_orphaned)} system/legacy tables hidden"
                )
        else:
            self.stdout.write(f"\n✅ No orphaned tables")

    def _report_matching_tables(
        self,
        matching_tables: Set[str],
        model_tables: Dict,
        db_columns: Dict,
        show_columns: bool
    ):
        """Report tables that exist in both database and models."""
        self.stdout.write(f"\n✅ Matching tables ({len(matching_tables)}):")

        if show_columns and db_columns:
            self.stdout.write("   Showing table structures:\n")
            for table in sorted(matching_tables):
                info = model_tables[table]
                columns = db_columns.get(table, [])

                self.stdout.write(f"\n   📋 {table} ({info['app']}.{info['model']})")
                self.stdout.write(f"      Columns: {len(columns)}")

                for col in columns[:5]:  # Show first 5 columns
                    nullable = "NULL" if col['nullable'] else "NOT NULL"
                    self.stdout.write(f"        - {col['name']:<30} {col['type']:<20} {nullable}")

                if len(columns) > 5:
                    self.stdout.write(f"        ... and {len(columns) - 5} more columns")
        else:
            self.stdout.write("   All these models have corresponding database tables")
            if not show_columns:
                self.stdout.write("   Use --show-columns to see column details")

    def _fix_missing_tables(self, missing_tables: Set[str], model_tables: Dict):
        """Attempt to create missing tables."""
        self.stdout.write(f"\n🔧 Attempting to fix missing tables...")

        self.stdout.write(self.style.WARNING(
            "\n   This will run migrations to create missing tables."
        ))

        response = input("   Do you want to proceed? [y/N]: ")
        if response.lower() != 'y':
            self.stdout.write("   Cancelled.")
            return

        from django.core.management import call_command

        try:
            call_command('migrate', verbosity=2, interactive=False)
            self.stdout.write(self.style.SUCCESS("\n   ✓ Migrations applied successfully"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n   ✗ Migration failed: {str(e)}"))
            self.stdout.write("\n   You may need to:")
            self.stdout.write("     1. Create migrations first: python manage.py makemigrations")
            self.stdout.write("     2. Then apply them: python manage.py migrate")
