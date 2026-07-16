from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.core.models import NotificationNumber, SchemeCode
from apps.license.models import (
    LicenseBalance,
    LicenseDetailsModel,
    LicenseFlags,
    LicenseNotes,
    LicenseOwnership,
)

LICENSE_TABLE = LicenseDetailsModel._meta.db_table
SUBTABLE_MODELS = (
    ("notes", LicenseNotes),
    ("balance", LicenseBalance),
    ("flags", LicenseFlags),
    ("ownership", LicenseOwnership),
)
LEGACY_SPLIT_COLUMNS = {
    "balance_cif",
    "ledger_date",
    "is_active",
    "is_expired",
    "current_owner_id",
    "user_comment",
}


class Command(BaseCommand):
    help = "Create and backfill split license sub-tables when migration state was faked."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the schema/data repair plan without making changes.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Apply the schema/data repair. Required unless --dry-run is used.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN - no DB changes will be made."))
        elif not confirm:
            raise CommandError("Pass --dry-run to preview or --confirm to apply repairs.")

        self._validate_required_tables()
        if dry_run:
            self._repair_model_columns(LicenseDetailsModel, dry_run=True)
            self._repair_lookup_fks(dry_run=True)
            self._repair_split_tables(dry_run=True)
            self.stdout.write(self.style.WARNING("DRY-RUN complete - no DB changes made."))
            return

        with transaction.atomic():
            self._repair_model_columns(LicenseDetailsModel, dry_run=False)
            self._repair_lookup_fks(dry_run=False)
            self._repair_split_tables(dry_run=False)
            self._report_counts()

    def _repair_model_columns(self, model, *, dry_run):
        table_name = model._meta.db_table
        columns = self._columns(table_name)
        missing_fields = [
            field
            for field in model._meta.local_fields
            if not field.primary_key and field.column not in columns
        ]
        if not missing_fields:
            self.stdout.write(f"{table_name}: model columns OK")
            return

        if dry_run:
            for field in missing_fields:
                self.stdout.write(
                    self.style.WARNING(f"{table_name}.{field.column}: would create")
                )
            return

        with connection.schema_editor() as schema_editor:
            for field in missing_fields:
                schema_editor.add_field(model, field)
                columns.add(field.column)
                self.stdout.write(
                    self.style.WARNING(f"{table_name}.{field.column}: created")
                )

    def _repair_lookup_fks(self, *, dry_run):
        columns = self._columns(LICENSE_TABLE)
        fields_to_add = []
        if "scheme_code" in columns and "scheme_code_id" not in columns:
            fields_to_add.append(LicenseDetailsModel._meta.get_field("scheme_code"))
        if "notification_number" in columns and "notification_number_id" not in columns:
            fields_to_add.append(LicenseDetailsModel._meta.get_field("notification_number"))

        if fields_to_add:
            if dry_run:
                for field in fields_to_add:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{LICENSE_TABLE}.{field.column}: would create"
                        )
                    )
            else:
                with connection.schema_editor() as schema_editor:
                    for field in fields_to_add:
                        schema_editor.add_field(LicenseDetailsModel, field)
                        self.stdout.write(
                            self.style.WARNING(f"{LICENSE_TABLE}.{field.column}: created")
                        )

        columns = self._columns(LICENSE_TABLE)
        if "scheme_code" in columns and "scheme_code_id" in columns:
            self._backfill_lookup_fk(
                legacy_column="scheme_code",
                fk_column="scheme_code_id",
                model=SchemeCode,
                dry_run=dry_run,
            )
        if "notification_number" in columns and "notification_number_id" in columns:
            self._backfill_lookup_fk(
                legacy_column="notification_number",
                fk_column="notification_number_id",
                model=NotificationNumber,
                dry_run=dry_run,
            )

    def _backfill_lookup_fk(self, legacy_column, fk_column, model, *, dry_run):
        table_name = model._meta.db_table
        q_lookup_table = self._quote_identifier_path(table_name)
        q_license_table = self._quote_identifier_path(LICENSE_TABLE)
        q_code = connection.ops.quote_name("code")
        q_label = connection.ops.quote_name("label")
        q_legacy = connection.ops.quote_name(legacy_column)
        q_fk = connection.ops.quote_name(fk_column)

        with connection.cursor() as cursor:
            if dry_run:
                cursor.execute(
                    f"""
                    SELECT COUNT(DISTINCT {q_legacy})
                    FROM {q_license_table}
                    WHERE {q_legacy} IS NOT NULL AND {q_legacy} != ''
                    """
                )
                distinct_values = cursor.fetchone()[0]
                cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {q_license_table}
                    WHERE {q_legacy} IS NOT NULL
                      AND {q_legacy} != ''
                      AND {q_fk} IS NULL
                    """
                )
                rows_to_backfill = cursor.fetchone()[0]
                self.stdout.write(
                    self.style.WARNING(
                        f"{fk_column}: would ensure {distinct_values} lookup value(s) "
                        f"and backfill {rows_to_backfill} license row(s)"
                    )
                )
                return

            cursor.execute(
                f"""
                INSERT INTO {q_lookup_table} ({q_code}, {q_label})
                SELECT DISTINCT {q_legacy}, {q_legacy}
                FROM {q_license_table}
                WHERE {q_legacy} IS NOT NULL AND {q_legacy} != ''
                ON CONFLICT ({q_code}) DO NOTHING
                """
            )
            cursor.execute(
                f"""
                UPDATE {q_license_table} target
                SET {q_fk} = lookup.id
                FROM {q_lookup_table} lookup
                WHERE target.{q_legacy} = lookup.{q_code}
                  AND target.{q_legacy} IS NOT NULL
                  AND target.{q_legacy} != ''
                  AND target.{q_fk} IS NULL
                """
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{fk_column}: backfilled from {legacy_column} using {table_name}"
            )
        )

    def _repair_split_tables(self, *, dry_run):
        existing_tables = set(connection.introspection.table_names())

        missing_models = [
            model for _, model in SUBTABLE_MODELS if model._meta.db_table not in existing_tables
        ]
        for _, model in SUBTABLE_MODELS:
            table_name = model._meta.db_table
            if table_name in existing_tables:
                self.stdout.write(f"{table_name}: exists")
            elif dry_run:
                self.stdout.write(self.style.WARNING(f"{table_name}: would create"))

        if missing_models and not dry_run:
            with connection.schema_editor() as schema_editor:
                for model in missing_models:
                    table_name = model._meta.db_table
                    schema_editor.create_model(model)
                    existing_tables.add(table_name)
                    self.stdout.write(self.style.WARNING(f"{table_name}: created"))

        columns = self._columns(LICENSE_TABLE)
        has_old_split_columns = LEGACY_SPLIT_COLUMNS.issubset(columns)

        if dry_run:
            action = "legacy-column backfill" if has_old_split_columns else "default sub-row backfill"
            self.stdout.write(self.style.WARNING(f"Would run {action}."))
            return
        if has_old_split_columns:
            self._backfill_from_legacy_columns()
        else:
            self._backfill_defaults()

    def _columns(self, table_name):
        if table_name not in connection.introspection.table_names():
            raise CommandError(f"Required table does not exist: {table_name}")

        with connection.cursor() as cursor:
            return {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }

    def _backfill_from_legacy_columns(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO license_licensenotes (
                    license_id, user_comment, condition_sheet, user_restrictions, balance_report_notes
                )
                SELECT id, user_comment, condition_sheet, user_restrictions, balance_report_notes
                FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO license_licensebalance (license_id, balance_cif, ledger_date)
                SELECT id, COALESCE(balance_cif, 0), ledger_date
                FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO license_licenseflags (
                    license_id, is_active, is_audit, is_mnm, is_not_registered, is_null, is_au,
                    is_incomplete, is_expired, is_individual
                )
                SELECT id, is_active, is_audit, is_mnm, is_not_registered, is_null, is_au,
                       is_incomplete, is_expired, is_individual
                FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO license_licenseownership (
                    license_id, file_transfer_status, last_ownership_fetch, current_owner_id
                )
                SELECT id, file_transfer_status, last_ownership_fetch, current_owner_id
                FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )

    def _backfill_defaults(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO license_licensenotes (license_id)
                SELECT id FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO license_licensebalance (license_id, balance_cif)
                SELECT id, 0 FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO license_licenseflags (license_id)
                SELECT id FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO license_licenseownership (license_id)
                SELECT id FROM license_licensedetailsmodel
                ON CONFLICT (license_id) DO NOTHING
                """
            )

    def _report_counts(self):
        total = LicenseDetailsModel.objects.count()
        counts = {}
        mismatches = {}
        for name, model in SUBTABLE_MODELS:
            counts[name] = model.objects.count()
            missing = self._count_missing_subrows(model)
            orphaned = self._count_orphaned_subrows(model)
            if missing or orphaned:
                mismatches[name] = {
                    "rows": counts[name],
                    "missing": missing,
                    "orphaned": orphaned,
                }

        if mismatches:
            raise CommandError(
                f"License sub-table repair incomplete: total={total}, mismatches={mismatches}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "License sub-tables OK: "
                f"{total} licenses, {counts['notes']} notes, {counts['balance']} balances, "
                f"{counts['flags']} flags, {counts['ownership']} ownership rows"
            )
        )

    def _count_missing_subrows(self, model):
        subtable = self._quote_identifier_path(model._meta.db_table)
        license_table = self._quote_identifier_path(LICENSE_TABLE)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {license_table} parent
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM {subtable} subrow
                    WHERE subrow.license_id = parent.id
                )
                """
            )
            return cursor.fetchone()[0]

    def _count_orphaned_subrows(self, model):
        subtable = self._quote_identifier_path(model._meta.db_table)
        license_table = self._quote_identifier_path(LICENSE_TABLE)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {subtable} subrow
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM {license_table} parent
                    WHERE parent.id = subrow.license_id
                )
                """
            )
            return cursor.fetchone()[0]

    def _validate_required_tables(self):
        self._columns(LICENSE_TABLE)

    def _quote_identifier_path(self, identifier):
        return ".".join(connection.ops.quote_name(part) for part in identifier.split("."))
