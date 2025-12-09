"""
Management command to comprehensively sync database schema with Django models.

This command:
1. Checks all tables and columns against Django models
2. Detects missing columns, extra columns, and type mismatches
3. Can automatically generate and apply migrations to fix issues
4. Backs up database before making changes (optional)

Usage:
    python manage.py sync_database_schema                    # Check only
    python manage.py sync_database_schema --fix              # Generate and apply fixes
    python manage.py sync_database_schema --app license      # Check specific app
    python manage.py sync_database_schema --show-sql         # Show SQL that would be executed
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.core.management import call_command
from collections import defaultdict
from decimal import Decimal
import sys


class Command(BaseCommand):
    help = "Sync database schema with Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='Sync specific app only',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Generate and apply migrations to fix issues',
        )
        parser.add_argument(
            '--show-sql',
            action='store_true',
            help='Show SQL that would be executed',
        )
        parser.add_argument(
            '--skip-backup',
            action='store_true',
            help='Skip database backup (not recommended)',
        )

    def handle(self, *args, **options):
        app_label = options.get('app')
        fix = options.get('fix', False)
        show_sql = options.get('show_sql', False)
        skip_backup = options.get('skip_backup', False)

        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(self.style.HTTP_INFO("Database Schema Synchronization"))
        self.stdout.write(self.style.HTTP_INFO("=" * 80))

        # Step 1: Analyze database vs models
        self.stdout.write("\n📊 Step 1: Analyzing database schema...")
        issues = self._analyze_schema(app_label)

        # Step 2: Report findings
        self._report_issues(issues)

        # Step 3: Fix issues if requested
        if fix and any(issues.values()):
            if not skip_backup:
                self.stdout.write("\n💾 Step 3: Creating database backup...")
                self._create_backup()

            self.stdout.write("\n🔧 Step 4: Fixing schema issues...")
            self._fix_issues(issues, show_sql)
        elif any(issues.values()):
            self.stdout.write("\n💡 To fix these issues, run:")
            self.stdout.write("   python manage.py sync_database_schema --fix")
        else:
            self.stdout.write("\n✅ Database schema is in sync with models!")

        self.stdout.write("\n" + self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("Sync check complete!"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

    def _analyze_schema(self, app_label):
        """Analyze database schema against Django models."""
        issues = {
            'missing_tables': [],
            'missing_columns': defaultdict(list),
            'extra_columns': defaultdict(list),
            'type_mismatches': defaultdict(list),
        }

        # Get all apps to check
        if app_label:
            apps_to_check = [app_label]
        else:
            apps_to_check = ['core', 'license', 'bill_of_entry', 'allotment', 'trade', 'accounts']

        # Get database schema
        db_tables = self._get_database_tables()
        db_columns = self._get_database_columns()

        # Check each model
        for app in apps_to_check:
            try:
                app_config = apps.get_app_config(app)
                for model in app_config.get_models():
                    if model._meta.abstract:
                        continue

                    table_name = model._meta.db_table

                    # Check if table exists
                    if table_name not in db_tables:
                        issues['missing_tables'].append({
                            'table': table_name,
                            'app': app,
                            'model': model.__name__
                        })
                        continue

                    # Check columns
                    model_columns = self._get_model_columns(model)
                    table_columns = db_columns.get(table_name, {})

                    # Find missing columns
                    for col_name, col_info in model_columns.items():
                        if col_name not in table_columns:
                            issues['missing_columns'][table_name].append({
                                'column': col_name,
                                'type': col_info['type'],
                                'null': col_info['null'],
                                'model': model.__name__
                            })

                    # Find extra columns (in DB but not in model)
                    for col_name in table_columns:
                        if col_name not in model_columns and col_name != 'id':
                            issues['extra_columns'][table_name].append({
                                'column': col_name,
                                'type': table_columns[col_name]['type']
                            })

                    # Check type mismatches
                    for col_name, col_info in model_columns.items():
                        if col_name in table_columns:
                            db_type = table_columns[col_name]['type'].lower()
                            model_type = self._django_to_db_type(col_info['type']).lower()

                            if not self._types_compatible(db_type, model_type):
                                issues['type_mismatches'][table_name].append({
                                    'column': col_name,
                                    'db_type': db_type,
                                    'model_type': model_type
                                })

            except LookupError:
                self.stdout.write(self.style.WARNING(f"  App '{app}' not found"))
                continue

        return issues

    def _get_database_tables(self):
        """Get list of all tables in database."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            return {row[0] for row in cursor.fetchall()}

    def _get_database_columns(self):
        """Get detailed column information for all tables."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """)

            columns_by_table = defaultdict(dict)
            for row in cursor.fetchall():
                table_name, column_name, data_type, is_nullable, column_default = row
                columns_by_table[table_name][column_name] = {
                    'type': data_type,
                    'nullable': is_nullable == 'YES',
                    'default': column_default
                }

            return dict(columns_by_table)

    def _get_model_columns(self, model):
        """Get column information from Django model."""
        columns = {}
        for field in model._meta.get_fields():
            # Skip relations that don't have columns
            if not hasattr(field, 'column'):
                continue

            # Skip reverse relations
            if hasattr(field, 'related_model') and not hasattr(field, 'db_column'):
                continue

            column_name = field.column if hasattr(field, 'column') else field.name

            columns[column_name] = {
                'type': field.get_internal_type(),
                'null': getattr(field, 'null', False),
                'field_name': field.name
            }

        return columns

    def _django_to_db_type(self, django_type):
        """Map Django field type to database type."""
        type_mapping = {
            'AutoField': 'integer',
            'BigAutoField': 'bigint',
            'BigIntegerField': 'bigint',
            'BooleanField': 'boolean',
            'CharField': 'character varying',
            'DateField': 'date',
            'DateTimeField': 'timestamp with time zone',
            'DecimalField': 'numeric',
            'FileField': 'character varying',
            'FloatField': 'double precision',
            'IntegerField': 'integer',
            'PositiveIntegerField': 'integer',
            'PositiveSmallIntegerField': 'smallint',
            'SlugField': 'character varying',
            'SmallIntegerField': 'smallint',
            'TextField': 'text',
            'TimeField': 'time without time zone',
            'URLField': 'character varying',
            'UUIDField': 'uuid',
            'ForeignKey': 'integer',
            'OneToOneField': 'integer',
        }
        return type_mapping.get(django_type, 'unknown')

    def _types_compatible(self, db_type, model_type):
        """Check if database type is compatible with model type."""
        # Normalize types
        db_type = db_type.replace('character varying', 'varchar')
        model_type = model_type.replace('character varying', 'varchar')

        # Direct match
        if db_type == model_type:
            return True

        # Compatible types
        compatible_pairs = [
            ('varchar', 'text'),
            ('text', 'varchar'),
            ('integer', 'bigint'),
            ('numeric', 'double precision'),
            ('timestamp with time zone', 'timestamp without time zone'),
        ]

        return (db_type, model_type) in compatible_pairs or (model_type, db_type) in compatible_pairs

    def _report_issues(self, issues):
        """Report all found issues."""
        self.stdout.write("\n📋 Analysis Results:\n")

        total_issues = (
            len(issues['missing_tables']) +
            sum(len(cols) for cols in issues['missing_columns'].values()) +
            sum(len(cols) for cols in issues['extra_columns'].values()) +
            sum(len(cols) for cols in issues['type_mismatches'].values())
        )

        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS("  ✅ No issues found - schema is in sync!"))
            return

        self.stdout.write(self.style.WARNING(f"  Found {total_issues} issues:\n"))

        # Missing tables
        if issues['missing_tables']:
            self.stdout.write(self.style.ERROR(f"\n  ❌ Missing Tables ({len(issues['missing_tables'])}):\n"))
            for item in issues['missing_tables']:
                self.stdout.write(f"     • {item['table']:<45} ({item['app']}.{item['model']})")

        # Missing columns
        if issues['missing_columns']:
            self.stdout.write(self.style.WARNING(
                f"\n  ⚠️  Missing Columns ({sum(len(cols) for cols in issues['missing_columns'].values())}):\n"
            ))
            for table, columns in issues['missing_columns'].items():
                self.stdout.write(f"     📋 {table}:")
                for col in columns:
                    null_str = "NULL" if col['null'] else "NOT NULL"
                    self.stdout.write(f"        - {col['column']:<30} {col['type']:<20} {null_str}")

        # Extra columns
        if issues['extra_columns']:
            self.stdout.write(self.style.WARNING(
                f"\n  ℹ️  Extra Columns ({sum(len(cols) for cols in issues['extra_columns'].values())}):\n"
            ))
            self.stdout.write("     (These exist in database but not in models)\n")
            for table, columns in issues['extra_columns'].items():
                self.stdout.write(f"     📋 {table}:")
                for col in columns:
                    self.stdout.write(f"        - {col['column']:<30} {col['type']}")

        # Type mismatches
        if issues['type_mismatches']:
            self.stdout.write(self.style.ERROR(
                f"\n  ⚠️  Type Mismatches ({sum(len(cols) for cols in issues['type_mismatches'].values())}):\n"
            ))
            for table, columns in issues['type_mismatches'].items():
                self.stdout.write(f"     📋 {table}:")
                for col in columns:
                    self.stdout.write(
                        f"        - {col['column']:<30} DB: {col['db_type']:<20} Model: {col['model_type']}"
                    )

    def _create_backup(self):
        """Create database backup (placeholder - implement based on your backup strategy)."""
        self.stdout.write(self.style.WARNING(
            "  ⚠️  Backup functionality not implemented in this script."
        ))
        self.stdout.write("     Please ensure you have a recent database backup before proceeding.\n")

        response = input("     Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            self.stdout.write("     Cancelled.")
            sys.exit(0)

    def _fix_issues(self, issues, show_sql):
        """Fix schema issues by generating and applying migrations."""
        self.stdout.write("\n  Generating migrations...\n")

        try:
            # Step 1: Make migrations
            call_command('makemigrations', verbosity=2, interactive=False)

            # Step 2: Show SQL if requested
            if show_sql:
                self.stdout.write("\n  SQL to be executed:")
                call_command('sqlmigrate', verbosity=2)

            # Step 3: Apply migrations
            self.stdout.write("\n  Applying migrations...")
            call_command('migrate', verbosity=2, interactive=False)

            self.stdout.write(self.style.SUCCESS("\n  ✅ Schema synchronized successfully!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n  ❌ Error during sync: {str(e)}"))
            self.stdout.write("\n  You may need to:")
            self.stdout.write("     1. Check for migration conflicts")
            self.stdout.write("     2. Review model definitions")
            self.stdout.write("     3. Manually create migrations if auto-detection fails")
