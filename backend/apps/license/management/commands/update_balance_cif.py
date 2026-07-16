"""
Management command to update balance_cif field for all licenses.

This command recalculates and updates the balance_cif field for all licenses
using the centralized LicenseBalanceCalculator service.

Usage:
    python manage.py update_balance_cif
    python manage.py update_balance_cif --batch-size 100
    python manage.py update_balance_cif --license-number 0310837441
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.license.models import LicenseBalance, LicenseDetailsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator


def _validate_batch_size(value):
    if value < 1:
        raise CommandError("--batch-size must be greater than zero.")


def _normalize_license_number(value):
    if value is None:
        return None

    license_number = value.strip()
    if not license_number:
        raise CommandError("--license-number must not be blank.")
    return license_number


class Command(BaseCommand):
    help = 'Update balance_cif field for all licenses (or specific license)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of licenses to process in each batch (default: 100)'
        )
        parser.add_argument(
            '--license-number',
            type=str,
            help='Update only a specific license by license number'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Calculate and report changes without saving them.',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        license_number = _normalize_license_number(options.get('license_number'))
        dry_run = bool(options.get('dry_run'))
        _validate_batch_size(batch_size)

        if license_number:
            # Update specific license
            try:
                license_obj = LicenseDetailsModel.objects.get(license_number=license_number)
                balance = self.update_license_balance(license_obj, dry_run=dry_run)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {"Would update" if dry_run else "Updated"} '
                        f'balance_cif for license {license_number}: {balance}'
                    )
                )
            except LicenseDetailsModel.DoesNotExist as exc:
                raise CommandError(f'License {license_number} not found') from exc
            return

        # Update all licenses in batches
        total_licenses = LicenseDetailsModel.objects.count()
        self.stdout.write(f'Processing {total_licenses} licenses in batches of {batch_size}...')
        self.stdout.write(f'Dry run: {dry_run}')

        updated_count = 0
        error_count = 0

        # Use iterator to avoid loading all licenses into memory
        licenses = LicenseDetailsModel.objects.all().order_by("id").iterator(chunk_size=batch_size)

        for license_obj in licenses:
            try:
                with transaction.atomic():
                    self.update_license_balance(license_obj, dry_run=dry_run)
                updated_count += 1

                # Progress indicator
                if updated_count % batch_size == 0:
                    self.stdout.write(
                        f'  Processed {updated_count}/{total_licenses} licenses...'
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  Warning: Failed to update license {license_obj.license_number}: {str(e)}'
                    )
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully updated {updated_count} licenses'
            )
        )
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'✗ Failed to update {error_count} licenses'
                )
            )
            raise CommandError(f'Failed to update {error_count} license balance(s).')

    def update_license_balance(self, license_obj, *, dry_run):
        """
        Update balance_cif for a single license.
        Writes the LicenseBalance sub-table without saving the parent license.
        """
        balance = LicenseBalanceCalculator.calculate_balance(license_obj)

        if dry_run:
            return balance

        # balance_cif lives on LicenseBalance (OneToOne sub-table). get_or_create
        # repairs legacy rows where the signal-created subrow is missing.
        balance_row, _ = LicenseBalance.objects.get_or_create(license=license_obj)
        balance_row.balance_cif = balance
        balance_row.save(update_fields=["balance_cif"])
        return balance
