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

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from license.models import LicenseDetailsModel
from datetime import datetime
import csv
import os


class Command(BaseCommand):
    help = 'Update license expiry dates from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to CSV file with license_number and license_expiry_date columns'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )

    def parse_date(self, date_str):
        """Parse date string in various formats."""
        date_str = date_str.strip()

        # Try different date formats
        date_formats = [
            '%d/%m/%y',      # 17/03/26
            '%d/%m/%Y',      # 17/03/2026
            '%Y-%m-%d',      # 2026-03-17
            '%d-%m-%Y',      # 17-03-2026
            '%d-%m-%y',      # 17-03-26
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                # If year is less than 2000, assume it's 20xx
                if parsed_date.year < 2000:
                    parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
                return parsed_date
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date: {date_str}")

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options.get('dry_run', False)

        # Check if file exists
        if not os.path.exists(csv_file):
            raise CommandError(f"CSV file not found: {csv_file}")

        self.stdout.write(f"\nReading CSV file: {csv_file}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved\n"))

        updates = []
        errors = []
        not_found = []
        skipped = []

        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                # Detect if file has headers
                sample = f.read(1024)
                f.seek(0)
                has_header = csv.Sniffer().has_header(sample)

                reader = csv.reader(f)

                # Skip header if present
                if has_header:
                    next(reader)

                for row_num, row in enumerate(reader, start=2 if has_header else 1):
                    if len(row) < 2:
                        errors.append(f"Row {row_num}: Insufficient columns - {row}")
                        continue

                    license_number = row[0].strip()
                    expiry_date_str = row[1].strip()

                    if not license_number or not expiry_date_str:
                        skipped.append(f"Row {row_num}: Empty license number or date")
                        continue

                    try:
                        # Parse the date
                        new_expiry_date = self.parse_date(expiry_date_str)

                        # Find the license
                        try:
                            license_obj = LicenseDetailsModel.objects.get(license_number=license_number)

                            old_expiry = license_obj.license_expiry_date

                            # Check if update is needed
                            if old_expiry == new_expiry_date:
                                skipped.append(f"{license_number}: Already has expiry date {new_expiry_date}")
                                continue

                            updates.append({
                                'license': license_obj,
                                'old_expiry': old_expiry,
                                'new_expiry': new_expiry_date,
                                'license_number': license_number
                            })

                        except LicenseDetailsModel.DoesNotExist:
                            not_found.append(f"{license_number}: License not found in database")

                    except ValueError as e:
                        errors.append(f"Row {row_num} ({license_number}): {str(e)}")

        except Exception as e:
            raise CommandError(f"Error reading CSV file: {str(e)}")

        # Display summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"Total rows processed: {len(updates) + len(errors) + len(not_found) + len(skipped)}"))
        self.stdout.write(self.style.SUCCESS(f"Updates to be applied: {len(updates)}"))
        self.stdout.write(self.style.WARNING(f"Licenses not found: {len(not_found)}"))
        self.stdout.write(self.style.WARNING(f"Skipped (no change needed): {len(skipped)}"))
        self.stdout.write(self.style.ERROR(f"Errors: {len(errors)}"))
        self.stdout.write("=" * 80 + "\n")

        # Show errors
        if errors:
            self.stdout.write(self.style.ERROR("\nErrors encountered:"))
            for error in errors[:10]:  # Show first 10 errors
                self.stdout.write(f"  - {error}")
            if len(errors) > 10:
                self.stdout.write(f"  ... and {len(errors) - 10} more errors")

        # Show not found
        if not_found:
            self.stdout.write(self.style.WARNING("\nLicenses not found in database:"))
            for nf in not_found[:10]:  # Show first 10
                self.stdout.write(f"  - {nf}")
            if len(not_found) > 10:
                self.stdout.write(f"  ... and {len(not_found) - 10} more")

        # Show sample updates
        if updates:
            self.stdout.write("\nSample updates (showing first 10):")
            for update in updates[:10]:
                old_str = str(update['old_expiry']) if update['old_expiry'] else 'None'
                self.stdout.write(
                    f"  {update['license_number']}: {old_str} → {update['new_expiry']}"
                )
            if len(updates) > 10:
                self.stdout.write(f"  ... and {len(updates) - 10} more updates")

        # Perform updates
        if updates and not dry_run:
            self.stdout.write("\nApplying updates...")

            try:
                with transaction.atomic():
                    updated_count = 0
                    for update in updates:
                        license_obj = update['license']
                        license_obj.license_expiry_date = update['new_expiry']
                        license_obj.save(update_fields=['license_expiry_date', 'updated_at'])
                        updated_count += 1

                    self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully updated {updated_count} licenses!"))

            except Exception as e:
                raise CommandError(f"Error updating licenses: {str(e)}")

        elif updates and dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN: Would have updated {len(updates)} licenses"
            ))
            self.stdout.write("Run without --dry-run to apply changes")

        elif not updates:
            self.stdout.write(self.style.WARNING("\nNo updates to apply"))

        self.stdout.write("")
