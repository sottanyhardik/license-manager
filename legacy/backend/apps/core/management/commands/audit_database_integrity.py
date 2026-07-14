import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = (
        "Read-only database audit: pending migrations, model tables/columns, "
        "row counts, and optional snapshot comparison."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--write-snapshot",
            metavar="PATH",
            help="Write table row counts/checksums to PATH. Does not modify the database.",
        )
        parser.add_argument(
            "--compare-snapshot",
            metavar="PATH",
            help="Compare current table row counts/checksums with a previous snapshot.",
        )
        parser.add_argument(
            "--with-checksums",
            action="store_true",
            help="Hash table contents as well as row counts. Slower, but verifies data equality.",
        )
        parser.add_argument(
            "--fail-on-extra-columns",
            action="store_true",
            help="Fail when database tables have columns not present on the Django model.",
        )
        parser.add_argument(
            "--ignore-table",
            action="append",
            default=[],
            help="Table to ignore during snapshot comparison. Can be repeated.",
        )

    def handle(self, *args, **options):
        self.errors = []
        self.warnings = []

        self._check_pending_migrations()
        self._check_model_schema(options["fail_on_extra_columns"])
        self._check_license_split_counts()

        snapshot = self._build_snapshot(with_checksums=options["with_checksums"])

        if options["write_snapshot"]:
            self._write_snapshot(options["write_snapshot"], snapshot)

        if options["compare_snapshot"]:
            self._compare_snapshot(
                options["compare_snapshot"],
                snapshot,
                ignored_tables=set(options["ignore_table"]),
            )

        for warning in self.warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

        if self.errors:
            for error in self.errors:
                self.stderr.write(self.style.ERROR(f"ERROR: {error}"))
            raise CommandError(f"Database integrity audit failed with {len(self.errors)} error(s).")

        self.stdout.write(self.style.SUCCESS("Database integrity audit passed."))

    def _check_pending_migrations(self):
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        if plan:
            pending = [f"{migration.app_label}.{migration.name}" for migration, _ in plan]
            self.errors.append(f"Pending migrations: {', '.join(pending)}")
            return

        self.stdout.write(self.style.SUCCESS("Migrations: all applied"))

    def _check_model_schema(self, fail_on_extra_columns):
        existing_tables = set(connection.introspection.table_names())
        checked_tables = set()

        for model in apps.get_models(include_auto_created=True):
            if model._meta.proxy or not model._meta.managed:
                continue

            table_name = model._meta.db_table
            if table_name in checked_tables:
                continue
            checked_tables.add(table_name)

            if table_name not in existing_tables:
                self.errors.append(f"Missing table for {model._meta.label}: {table_name}")
                continue

            db_columns = self._columns(table_name)
            model_columns = {
                field.column
                for field in model._meta.local_fields
                if getattr(field, "column", None)
            }

            missing_columns = sorted(model_columns - db_columns)
            if missing_columns:
                self.errors.append(
                    f"{table_name}: missing model column(s): {', '.join(missing_columns)}"
                )

            extra_columns = sorted(db_columns - model_columns)
            if extra_columns:
                message = f"{table_name}: extra database column(s): {', '.join(extra_columns)}"
                if fail_on_extra_columns:
                    self.errors.append(message)
                else:
                    self.warnings.append(message)

        self.stdout.write(
            self.style.SUCCESS(f"Schema: checked {len(checked_tables)} managed model table(s)")
        )

    def _check_license_split_counts(self):
        required_tables = {
            "license_licensedetailsmodel",
            "license_licensenotes",
            "license_licensebalance",
            "license_licenseflags",
            "license_licenseownership",
        }
        existing_tables = set(connection.introspection.table_names())
        missing = sorted(required_tables - existing_tables)
        if missing:
            self.errors.append(f"License split table(s) missing: {', '.join(missing)}")
            return

        counts = {
            table: self._table_count(table)
            for table in sorted(required_tables)
        }
        total = counts["license_licensedetailsmodel"]
        mismatches = {
            table: count
            for table, count in counts.items()
            if table != "license_licensedetailsmodel" and count != total
        }
        if mismatches:
            self.errors.append(
                "License split row count mismatch: "
                f"license_licensedetailsmodel={total}, {mismatches}"
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                "License split tables: "
                f"{total} licenses and matching notes/balance/flags/ownership rows"
            )
        )

    def _build_snapshot(self, with_checksums):
        tables = sorted(connection.introspection.table_names())
        snapshot = {
            "database_vendor": connection.vendor,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "with_checksums": with_checksums,
            "tables": {},
        }

        for table_name in tables:
            table_data = {"row_count": self._table_count(table_name)}
            if with_checksums:
                table_data["checksum"] = self._table_checksum(table_name)
            snapshot["tables"][table_name] = table_data

        self.stdout.write(self.style.SUCCESS(f"Snapshot: scanned {len(tables)} table(s)"))
        return snapshot

    def _write_snapshot(self, path, snapshot):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Snapshot written: {target}"))

    def _compare_snapshot(self, path, current, ignored_tables):
        source = Path(path)
        if not source.exists():
            raise CommandError(f"Snapshot file does not exist: {source}")

        previous = json.loads(source.read_text())
        previous_tables = {
            table: data
            for table, data in previous.get("tables", {}).items()
            if table not in ignored_tables
        }
        current_tables = {
            table: data
            for table, data in current.get("tables", {}).items()
            if table not in ignored_tables
        }

        missing_tables = sorted(set(previous_tables) - set(current_tables))
        new_tables = sorted(set(current_tables) - set(previous_tables))
        if missing_tables:
            self.errors.append(f"Snapshot compare: missing table(s): {', '.join(missing_tables)}")
        if new_tables:
            self.errors.append(f"Snapshot compare: new table(s): {', '.join(new_tables)}")

        for table_name in sorted(set(previous_tables) & set(current_tables)):
            old = previous_tables[table_name]
            new = current_tables[table_name]
            if old.get("row_count") != new.get("row_count"):
                self.errors.append(
                    f"Snapshot compare: {table_name} row count changed "
                    f"{old.get('row_count')} -> {new.get('row_count')}"
                )
            if "checksum" in old or "checksum" in new:
                if old.get("checksum") != new.get("checksum"):
                    self.errors.append(f"Snapshot compare: {table_name} checksum changed")

        self.stdout.write(self.style.SUCCESS(f"Snapshot compared: {source}"))

    def _columns(self, table_name):
        with connection.cursor() as cursor:
            return {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }

    def _table_count(self, table_name):
        quoted_table = connection.ops.quote_name(table_name)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {quoted_table}")
            return cursor.fetchone()[0]

    def _table_checksum(self, table_name):
        columns = self._table_columns_ordered(table_name)
        quoted_table = connection.ops.quote_name(table_name)
        quoted_columns = ", ".join(connection.ops.quote_name(column) for column in columns)
        order_by = ", ".join(connection.ops.quote_name(column) for column in columns)

        hasher = hashlib.sha256()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {quoted_columns} FROM {quoted_table} ORDER BY {order_by}")
            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break
                for row in rows:
                    hasher.update(self._normalize_row(row).encode("utf-8"))
                    hasher.update(b"\n")

        return hasher.hexdigest()

    def _table_columns_ordered(self, table_name):
        with connection.cursor() as cursor:
            return [
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            ]

    def _normalize_row(self, row):
        return json.dumps(
            [self._normalize_value(value) for value in row],
            sort_keys=True,
            separators=(",", ":"),
        )

    def _normalize_value(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, bytes):
            return value.hex()
        return value
