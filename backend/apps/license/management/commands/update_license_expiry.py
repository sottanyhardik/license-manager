"""
Management command to update license expiry dates from CSV file.

Usage:
    python manage.py update_license_expiry <csv_file_path>

CSV Format:
    license_number,license_expiry_date
    0111004570,17/03/26
    0111083935,18/03/26
    ...

Date formats supported: DD/MM/YY, DD/MM/YYYY, YYYY-MM-DD
"""

from datetime import datetime
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.models import LicenseDetailsModel


DATE_FORMATS = (
    "%d/%m/%y",      # 17/03/26
    "%d/%m/%Y",      # 17/03/2026
    "%Y-%m-%d",      # 2026-03-17
    "%d-%m-%Y",      # 17-03-2026
    "%d-%m-%y",      # 17-03-26
)

HEADER_FIELDS = ("license_number", "license_expiry_date")
MAX_DISPLAYED_MESSAGES = 10


class Command(BaseCommand):
    help = "Update license expiry dates from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to CSV file with license_number and license_expiry_date columns",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without actually updating",
        )

    def parse_date(self, date_str):
        """Parse date string in various formats."""
        if date_str is None:
            raise ValueError("Date value is required")

        date_str = date_str.strip()
        if not date_str:
            raise ValueError("Date value is required")

        for fmt in DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                if parsed_date.year < 2000:
                    parsed_date = parsed_date.replace(year=parsed_date.year + 100)
                return parsed_date
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date: {date_str}")

    def _resolve_csv_path(self, csv_file):
        csv_file = (csv_file or "").strip()
        if not csv_file:
            raise CommandError("CSV file path must not be blank")

        csv_path = Path(csv_file).expanduser()
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")
        if not csv_path.is_file():
            raise CommandError(f"CSV path is not a file: {csv_path}")

        return csv_path

    def _read_csv_rows(self, csv_path):
        rows = []
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.reader(csv_file)
                first_data_row_seen = False
                for physical_row_num, row in enumerate(reader, start=1):
                    if not row or all(not value.strip() for value in row):
                        continue

                    normalized = tuple(value.strip().lower() for value in row[:2])
                    if not first_data_row_seen and normalized == HEADER_FIELDS:
                        first_data_row_seen = True
                        continue

                    first_data_row_seen = True
                    rows.append((physical_row_num, row))
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise CommandError(f"Error reading CSV file: {exc}") from exc

        if not rows:
            raise CommandError("CSV file does not contain any license expiry rows")

        return rows

    def _prepare_updates(self, rows):
        errors = []
        skipped = []
        parsed_rows = []
        seen_license_numbers = set()

        for row_num, row in rows:
            if len(row) != 2:
                errors.append(f"Row {row_num}: Expected 2 columns, found {len(row)} - {row}")
                continue

            license_number = row[0].strip()
            expiry_date_str = row[1].strip()

            if not license_number:
                errors.append(f"Row {row_num}: License number is required")
                continue
            if not expiry_date_str:
                errors.append(f"Row {row_num} ({license_number}): Expiry date is required")
                continue
            if license_number in seen_license_numbers:
                errors.append(f"Row {row_num} ({license_number}): Duplicate license number in CSV")
                continue

            seen_license_numbers.add(license_number)

            try:
                parsed_rows.append((row_num, license_number, self.parse_date(expiry_date_str)))
            except ValueError as exc:
                errors.append(f"Row {row_num} ({license_number}): {exc}")

        license_numbers = [license_number for _, license_number, _ in parsed_rows]
        licenses_by_number = (
            LicenseDetailsModel.objects.in_bulk(license_numbers, field_name="license_number")
            if license_numbers
            else {}
        )

        updates = []
        not_found = []
        for _, license_number, new_expiry_date in parsed_rows:
            license_obj = licenses_by_number.get(license_number)
            if license_obj is None:
                not_found.append(f"{license_number}: License not found in database")
                continue

            old_expiry = license_obj.license_expiry_date
            if old_expiry == new_expiry_date:
                skipped.append(f"{license_number}: Already has expiry date {new_expiry_date}")
                continue

            updates.append(
                {
                    "license": license_obj,
                    "old_expiry": old_expiry,
                    "new_expiry": new_expiry_date,
                    "license_number": license_number,
                }
            )

        return updates, errors, not_found, skipped

    def _write_limited_messages(self, heading, messages, style=None):
        if not messages:
            return

        writer = self.stdout.write
        writer(style(heading) if style else heading)
        for message in messages[:MAX_DISPLAYED_MESSAGES]:
            writer(f"  - {message}")
        if len(messages) > MAX_DISPLAYED_MESSAGES:
            writer(f"  ... and {len(messages) - MAX_DISPLAYED_MESSAGES} more")

    def _write_summary(self, updates, errors, not_found, skipped):
        total_rows = len(updates) + len(errors) + len(not_found) + len(skipped)
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"Total rows processed: {total_rows}"))
        self.stdout.write(self.style.SUCCESS(f"Updates to be applied: {len(updates)}"))
        self.stdout.write(self.style.WARNING(f"Licenses not found: {len(not_found)}"))
        self.stdout.write(self.style.WARNING(f"Skipped (no change needed): {len(skipped)}"))
        self.stdout.write(self.style.ERROR(f"Errors: {len(errors)}"))
        self.stdout.write("=" * 80 + "\n")

        self._write_limited_messages(
            "\nErrors encountered:",
            errors,
            self.style.ERROR,
        )
        self._write_limited_messages(
            "\nLicenses not found in database:",
            not_found,
            self.style.WARNING,
        )

        if updates:
            self.stdout.write("\nSample updates (showing first 10):")
            for update in updates[:MAX_DISPLAYED_MESSAGES]:
                old_str = str(update["old_expiry"]) if update["old_expiry"] else "None"
                self.stdout.write(
                    f"  {update['license_number']}: {old_str} -> {update['new_expiry']}"
                )
            if len(updates) > MAX_DISPLAYED_MESSAGES:
                self.stdout.write(
                    f"  ... and {len(updates) - MAX_DISPLAYED_MESSAGES} more updates"
                )

    def handle(self, *args, **options):
        csv_path = self._resolve_csv_path(options["csv_file"])
        dry_run = options.get("dry_run", False)

        self.stdout.write(f"\nReading CSV file: {csv_path}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved\n"))

        rows = self._read_csv_rows(csv_path)
        updates, errors, not_found, skipped = self._prepare_updates(rows)
        self._write_summary(updates, errors, not_found, skipped)

        if errors or not_found:
            raise CommandError("CSV validation failed; no license expiry dates were updated")

        if updates and not dry_run:
            self.stdout.write("\nApplying updates...")

            try:
                with transaction.atomic():
                    updated_count = 0
                    for update in updates:
                        license_obj = update["license"]
                        license_obj.license_expiry_date = update["new_expiry"]
                        license_obj.save(update_fields=["license_expiry_date", "modified_on"])
                        updated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(f"\nSuccessfully updated {updated_count} licenses!")
                    )

            except Exception as exc:
                raise CommandError(f"Error updating licenses: {exc}") from exc

        elif updates and dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN: Would have updated {len(updates)} licenses"
            ))
            self.stdout.write("Run without --dry-run to apply changes")

        elif not updates:
            self.stdout.write(self.style.WARNING("\nNo updates to apply"))

        self.stdout.write("")
