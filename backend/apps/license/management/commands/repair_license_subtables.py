from django.core.management.base import BaseCommand
from django.db import connection

from apps.license.models import LicenseBalance, LicenseFlags, LicenseNotes, LicenseOwnership


class Command(BaseCommand):
    help = "Create and backfill split license sub-tables when migration state was faked."

    def handle(self, *args, **options):
        existing_tables = set(connection.introspection.table_names())
        models = [LicenseNotes, LicenseBalance, LicenseFlags, LicenseOwnership]

        with connection.schema_editor() as schema_editor:
            for model in models:
                table_name = model._meta.db_table
                if table_name in existing_tables:
                    self.stdout.write(f"{table_name}: exists")
                    continue

                schema_editor.create_model(model)
                existing_tables.add(table_name)
                self.stdout.write(self.style.WARNING(f"{table_name}: created"))

        columns = self._columns("license_licensedetailsmodel")
        has_old_split_columns = {
            "balance_cif",
            "ledger_date",
            "is_active",
            "is_expired",
            "current_owner_id",
            "user_comment",
        }.issubset(columns)

        if has_old_split_columns:
            self._backfill_from_legacy_columns()
        else:
            self._backfill_defaults()

        self._report_counts()

    def _columns(self, table_name):
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
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM license_licensedetailsmodel")
            total = cursor.fetchone()[0]

        counts = {
            "notes": LicenseNotes.objects.count(),
            "balance": LicenseBalance.objects.count(),
            "flags": LicenseFlags.objects.count(),
            "ownership": LicenseOwnership.objects.count(),
        }

        missing = {name: total - count for name, count in counts.items() if count != total}
        if missing:
            raise RuntimeError(f"License sub-table repair incomplete: total={total}, missing={missing}")

        self.stdout.write(
            self.style.SUCCESS(
                "License sub-tables OK: "
                f"{total} licenses, {counts['notes']} notes, {counts['balance']} balances, "
                f"{counts['flags']} flags, {counts['ownership']} ownership rows"
            )
        )
