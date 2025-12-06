"""
Management command to update balance_cif field for all licenses.

This command recalculates and updates the balance_cif field for all licenses
using the centralized LicenseBalanceCalculator service.

Usage:
    python manage.py update_balance_cif
    python manage.py update_balance_cif --batch-size 100
    python manage.py update_balance_cif --license-number 0310837441
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from license.models import LicenseDetailsModel
from license.services.balance_calculator import LicenseBalanceCalculator


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

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        license_number = options.get('license_number')

        if license_number:
            # Update specific license
            try:
                license_obj = LicenseDetailsModel.objects.get(license_number=license_number)
                self.update_license_balance(license_obj)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated balance_cif for license {license_number}: {license_obj.balance_cif}'
                    )
                )
            except LicenseDetailsModel.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ License {license_number} not found')
                )
            return

        # Update all licenses in batches
        total_licenses = LicenseDetailsModel.objects.count()
        self.stdout.write(f'Processing {total_licenses} licenses in batches of {batch_size}...')

        updated_count = 0
        error_count = 0

        # Use iterator to avoid loading all licenses into memory
        licenses = LicenseDetailsModel.objects.all().iterator(chunk_size=batch_size)

        for license_obj in licenses:
            try:
                self.update_license_balance(license_obj)
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

    def update_license_balance(self, license_obj):
        """
        Update balance_cif for a single license.
        Uses update() to avoid triggering signals.
        """
        balance = LicenseBalanceCalculator.calculate_balance(license_obj)

        # Use update() to avoid triggering signals (prevents recursion)
        LicenseDetailsModel.objects.filter(pk=license_obj.pk).update(
            balance_cif=balance
        )
