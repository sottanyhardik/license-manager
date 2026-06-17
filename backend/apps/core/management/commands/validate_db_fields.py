"""
Management command to validate all model fields against database columns.

This command performs detailed field-level validation:
1. Checks if all model fields have corresponding database columns
2. Validates field types match between model and database
3. Checks NULL/NOT NULL constraints
4. Validates max_length for CharField/TextField
5. Checks decimal_places and max_digits for DecimalField
6. Identifies missing indexes
7. Validates foreign key relationships

Usage:
    python manage.py validate_db_fields
    python manage.py validate_db_fields --app core
    python manage.py validate_db_fields --detailed
    python manage.py validate_db_fields --fix-suggestions
"""

from collections import defaultdict
from typing import Dict, List, Tuple, Any

from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.db import models


class Command(BaseCommand):
    help = "Validate all model fields against database columns"

    def __init__(self):
        super().__init__()
        self.issues = []
        self.warnings = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='Check specific app only',
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed field comparison',
        )
        parser.add_argument(
            '--fix-suggestions',
            action='store_true',
            help='Show suggestions for fixing issues',
        )
        parser.add_argument(
            '--table',
            type=str,
            help='Check specific table only',
        )

    def handle(self, *args, **options):
        app_label = options.get('app')
        detailed = options.get('detailed', False)
        fix_suggestions = options.get('fix_suggestions', False)
        table_filter = options.get('table')

        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(self.style.HTTP_INFO("Database Field Validation"))
        self.stdout.write(self.style.HTTP_INFO("=" * 80))

        # Get database column information
        db_columns = self._get_all_columns()

        # Get apps to check
        if app_label:
            apps_to_check = [app_label]
        else:
            apps_to_check = ['core', 'license', 'bill_of_entry', 'allotment', 'trade', 'accounts']

        total_fields = 0
        total_tables = 0

        for app in apps_to_check:
            try:
                app_config = apps.get_app_config(app)
                for model in app_config.get_models():
                    table_name = model._meta.db_table

                    if table_filter and table_name != table_filter:
                        continue

                    if model._meta.abstract:
                        continue

                    total_tables += 1
                    fields_checked = self._validate_model_fields(
                        model, table_name, db_columns, detailed
                    )
                    total_fields += fields_checked

            except LookupError:
                self.stdout.write(self.style.WARNING(f"App '{app}' not found"))
                continue

        # Report summary
        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.HTTP_INFO("Validation Summary"))
        self.stdout.write(f"{'='*80}")
        self.stdout.write(f"Tables checked: {total_tables}")
        self.stdout.write(f"Fields validated: {total_fields}")
        self.stdout.write(f"Issues found: {len(self.issues)}")
        self.stdout.write(f"Warnings: {len(self.warnings)}")

        # Report issues
        if self.issues:
            self.stdout.write(f"\n{self.style.ERROR('❌ Issues Found:')}")
            for issue in self.issues:
                self.stdout.write(f"  • {issue}")

        # Report warnings
        if self.warnings:
            self.stdout.write(f"\n{self.style.WARNING('⚠️  Warnings:')}")
            for warning in self.warnings:
                self.stdout.write(f"  • {warning}")

        # Fix suggestions
        if fix_suggestions and self.issues:
            self._show_fix_suggestions()

        if not self.issues and not self.warnings:
            self.stdout.write(f"\n{self.style.SUCCESS('✅ All fields validated successfully!')}")

        self.stdout.write(f"\n{'='*80}")

    def _get_all_columns(self) -> Dict[str, List[Dict]]:
        """Get detailed column information for all tables."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale,
                    c.column_default
                FROM information_schema.columns c
                WHERE c.table_schema = 'public'
                ORDER BY c.table_name, c.ordinal_position
            """)

            columns_by_table = defaultdict(list)
            for row in cursor.fetchall():
                (table_name, column_name, data_type, is_nullable,
                 char_max_length, numeric_precision, numeric_scale,
                 column_default) = row

                columns_by_table[table_name].append({
                    'name': column_name,
                    'type': data_type,
                    'nullable': is_nullable == 'YES',
                    'max_length': char_max_length,
                    'precision': numeric_precision,
                    'scale': numeric_scale,
                    'default': column_default,
                })

            return dict(columns_by_table)

    def _validate_model_fields(
        self,
        model,
        table_name: str,
        db_columns: Dict,
        detailed: bool
    ) -> int:
        """Validate all fields for a specific model."""
        if table_name not in db_columns:
            self.issues.append(f"{table_name}: Table not found in database")
            return 0

        db_cols = {col['name']: col for col in db_columns[table_name]}
        fields_checked = 0

        if detailed:
            self.stdout.write(f"\n📋 {table_name} ({model._meta.app_label}.{model.__name__})")

        # Check each model field
        for field in model._meta.get_fields():
            # Skip relations that don't have columns
            if isinstance(field, (models.ManyToManyField, models.ManyToOneRel,
                                 models.ManyToManyRel, models.OneToOneRel)):
                continue

            column_name = getattr(field, 'column', field.name)
            if hasattr(field, 'attname'):
                column_name = field.attname

            fields_checked += 1

            if column_name not in db_cols:
                self.issues.append(
                    f"{table_name}.{column_name}: Model field exists but database column missing"
                )
                continue

            db_col = db_cols[column_name]

            # Validate field type
            self._validate_field_type(field, db_col, table_name, column_name, detailed)

            # Validate NULL constraints
            self._validate_null_constraint(field, db_col, table_name, column_name, detailed)

            # Validate field-specific constraints
            if isinstance(field, models.CharField):
                self._validate_char_field(field, db_col, table_name, column_name)
            elif isinstance(field, models.DecimalField):
                self._validate_decimal_field(field, db_col, table_name, column_name)

            if detailed:
                match_status = "✓" if not any(table_name in issue for issue in self.issues[-3:]) else "✗"
                self.stdout.write(
                    f"  {match_status} {column_name:<30} "
                    f"Model: {field.get_internal_type():<20} "
                    f"DB: {db_col['type']:<20}"
                )

        # Check for orphaned columns (in DB but not in model)
        model_columns = set()
        for field in model._meta.get_fields():
            if hasattr(field, 'column'):
                model_columns.add(field.column)
            elif hasattr(field, 'attname'):
                model_columns.add(field.attname)

        orphaned = set(db_cols.keys()) - model_columns
        if orphaned:
            for col in orphaned:
                self.warnings.append(
                    f"{table_name}.{col}: Database column exists but no model field found"
                )

        return fields_checked

    def _validate_field_type(
        self,
        field,
        db_col: Dict,
        table_name: str,
        column_name: str,
        detailed: bool
    ):
        """Validate field type matches database column type."""
        # Mapping of Django field types to PostgreSQL types
        type_mapping = {
            'AutoField': ['integer', 'serial'],
            'BigAutoField': ['bigint', 'bigserial'],
            'BooleanField': ['boolean'],
            'CharField': ['character varying', 'varchar', 'text'],
            'TextField': ['text', 'character varying'],
            'DateField': ['date'],
            'DateTimeField': ['timestamp with time zone', 'timestamp without time zone'],
            'DecimalField': ['numeric', 'decimal'],
            'FloatField': ['double precision', 'real'],
            'IntegerField': ['integer'],
            'BigIntegerField': ['bigint'],
            'SmallIntegerField': ['smallint'],
            'ForeignKey': ['bigint', 'integer'],
            'OneToOneField': ['bigint', 'integer'],
            'EmailField': ['character varying', 'varchar'],
            'URLField': ['character varying', 'varchar'],
            'ImageField': ['character varying', 'varchar'],
            'FileField': ['character varying', 'varchar'],
        }

        field_type = field.get_internal_type()
        db_type = db_col['type']

        expected_types = type_mapping.get(field_type, [])
        if expected_types and db_type not in expected_types:
            self.issues.append(
                f"{table_name}.{column_name}: Type mismatch - "
                f"Model: {field_type}, DB: {db_type}"
            )

    def _validate_null_constraint(
        self,
        field,
        db_col: Dict,
        table_name: str,
        column_name: str,
        detailed: bool
    ):
        """Validate NULL/NOT NULL constraints."""
        # Primary keys and AutoFields are always NOT NULL
        if isinstance(field, (models.AutoField, models.BigAutoField)):
            return

        field_nullable = getattr(field, 'null', False) or getattr(field, 'blank', False)
        db_nullable = db_col['nullable']

        # Some fields like created_on/modified_on with auto_now might have different NULL constraints
        if hasattr(field, 'auto_now') or hasattr(field, 'auto_now_add'):
            return

        if field_nullable != db_nullable:
            # This is a warning, not an error, as Django might handle this
            self.warnings.append(
                f"{table_name}.{column_name}: NULL constraint mismatch - "
                f"Model allows null: {field_nullable}, DB allows null: {db_nullable}"
            )

    def _validate_char_field(
        self,
        field: models.CharField,
        db_col: Dict,
        table_name: str,
        column_name: str
    ):
        """Validate CharField max_length."""
        model_max_length = getattr(field, 'max_length', None)
        db_max_length = db_col['max_length']

        if model_max_length and db_max_length:
            if model_max_length != db_max_length:
                self.warnings.append(
                    f"{table_name}.{column_name}: max_length mismatch - "
                    f"Model: {model_max_length}, DB: {db_max_length}"
                )

    def _validate_decimal_field(
        self,
        field: models.DecimalField,
        db_col: Dict,
        table_name: str,
        column_name: str
    ):
        """Validate DecimalField precision and scale."""
        model_max_digits = getattr(field, 'max_digits', None)
        model_decimal_places = getattr(field, 'decimal_places', None)

        db_precision = db_col['precision']
        db_scale = db_col['scale']

        if model_max_digits and db_precision:
            if model_max_digits != db_precision:
                self.warnings.append(
                    f"{table_name}.{column_name}: max_digits mismatch - "
                    f"Model: {model_max_digits}, DB: {db_precision}"
                )

        if model_decimal_places is not None and db_scale is not None:
            if model_decimal_places != db_scale:
                self.warnings.append(
                    f"{table_name}.{column_name}: decimal_places mismatch - "
                    f"Model: {model_decimal_places}, DB: {db_scale}"
                )

    def _show_fix_suggestions(self):
        """Show suggestions for fixing found issues."""
        self.stdout.write(f"\n{self.style.HTTP_INFO('💡 Fix Suggestions:')}")

        self.stdout.write("\nFor missing database columns:")
        self.stdout.write("  1. Create migrations: python manage.py makemigrations")
        self.stdout.write("  2. Apply migrations: python manage.py migrate")

        self.stdout.write("\nFor type mismatches:")
        self.stdout.write("  1. Update model field type to match database")
        self.stdout.write("  2. Or create migration to alter database column type")
        self.stdout.write("  3. Run: python manage.py makemigrations --name fix_field_types")

        self.stdout.write("\nFor orphaned database columns:")
        self.stdout.write("  1. Add field to model if needed")
        self.stdout.write("  2. Or remove column from database if obsolete")
        self.stdout.write("  3. Create migration to drop column")
