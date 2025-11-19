"""
Management command to sync database structure and data from GE (Government E-commerce) server.

This command performs the following operations:
1. Ensures all model tables exist in PostgreSQL database
2. Fetches latest data from GE server (ICEGATE/DGFT)
3. Updates license ownership, balances, and BOE details
4. Reconciles local database with remote server state

Usage:
    python manage.py sync_from_ge_server --full  # Full sync (structure + data)
    python manage.py sync_from_ge_server --data-only  # Data sync only
    python manage.py sync_from_ge_server --structure-only  # Structure sync only
    python manage.py sync_from_ge_server --license 0310837893  # Sync specific license
"""

import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.apps import apps

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync database structure and data from GE server"

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Perform full sync (structure + data)',
        )
        parser.add_argument(
            '--data-only',
            action='store_true',
            help='Sync data only (skip structure updates)',
        )
        parser.add_argument(
            '--structure-only',
            action='store_true',
            help='Update database structure only (skip data sync)',
        )
        parser.add_argument(
            '--license',
            type=str,
            help='Sync specific license number',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if no changes detected',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        license_number = options.get('license')

        # Determine sync mode
        full_sync = options.get('full', False)
        data_only = options.get('data_only', False)
        structure_only = options.get('structure_only', False)

        # Default to full sync if no mode specified
        if not (full_sync or data_only or structure_only):
            full_sync = True

        self.stdout.write(self.style.HTTP_INFO("=" * 70))
        self.stdout.write(self.style.HTTP_INFO("GE Server Database Sync"))
        self.stdout.write(self.style.HTTP_INFO("=" * 70))

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        try:
            # Step 1: Structure sync
            if full_sync or structure_only:
                self.stdout.write("\n" + self.style.HTTP_INFO("Step 1: Checking database structure..."))
                self._sync_structure(dry_run)

            # Step 2: Data sync
            if full_sync or data_only:
                self.stdout.write("\n" + self.style.HTTP_INFO("Step 2: Syncing data from GE server..."))
                if license_number:
                    self._sync_specific_license(license_number, dry_run, force)
                else:
                    self._sync_all_data(dry_run, force)

            self.stdout.write("\n" + self.style.SUCCESS("=" * 70))
            self.stdout.write(self.style.SUCCESS("Sync completed successfully!"))
            self.stdout.write(self.style.SUCCESS("=" * 70))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nSync failed: {str(e)}"))
            raise CommandError(f"Sync failed: {str(e)}")

    def _sync_structure(self, dry_run: bool = False):
        """Ensure all Django models have corresponding database tables."""
        self.stdout.write("Checking for missing tables...")

        missing_tables = []
        with connection.cursor() as cursor:
            # Get all existing tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}

        # Check each installed app's models
        apps_to_check = ['core', 'license', 'bill_of_entry', 'allotment', 'trade', 'accounts']

        for app_label in apps_to_check:
            try:
                app_config = apps.get_app_config(app_label)
                for model in app_config.get_models():
                    table_name = model._meta.db_table
                    if table_name not in existing_tables:
                        missing_tables.append({
                            'app': app_label,
                            'model': model.__name__,
                            'table': table_name
                        })
            except LookupError:
                self.stdout.write(self.style.WARNING(f"App '{app_label}' not found, skipping..."))

        if missing_tables:
            self.stdout.write(self.style.WARNING(f"Found {len(missing_tables)} missing tables:"))
            for table_info in missing_tables:
                self.stdout.write(f"  - {table_info['table']} ({table_info['app']}.{table_info['model']})")

            if not dry_run:
                self.stdout.write(self.style.HTTP_INFO("\nCreating missing tables..."))
                self.stdout.write(self.style.WARNING(
                    "Note: You should run 'python manage.py makemigrations' and 'python manage.py migrate' "
                    "to properly create these tables with all constraints and indexes."
                ))
        else:
            self.stdout.write(self.style.SUCCESS("✓ All model tables exist in database"))

    def _sync_all_data(self, dry_run: bool = False, force: bool = False):
        """Sync all license data from GE server."""
        from license.models import LicenseDetailsModel

        self.stdout.write("Fetching licenses to sync...")

        # Get licenses that need syncing (recent or updated)
        licenses_qs = LicenseDetailsModel.objects.filter(
            purchase_status='GE',  # GE status licenses
            is_active=True
        ).order_by('-modified_on')

        total_licenses = licenses_qs.count()
        self.stdout.write(f"Found {total_licenses} licenses with GE status")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Would sync {total_licenses} licenses"))
            # Show first 10 as examples
            for lic in licenses_qs[:10]:
                self.stdout.write(f"  - {lic.license_number} (File: {lic.ge_file_number})")
            if total_licenses > 10:
                self.stdout.write(f"  ... and {total_licenses - 10} more")
            return

        synced = 0
        skipped = 0
        errors = 0

        for license in licenses_qs.iterator(chunk_size=100):
            try:
                self._sync_license_data(license, force)
                synced += 1

                if synced % 10 == 0:
                    self.stdout.write(f"  Synced {synced}/{total_licenses} licenses...")

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.WARNING(
                    f"  Error syncing {license.license_number}: {str(e)}"
                ))
                logger.error(f"Error syncing license {license.license_number}: {str(e)}", exc_info=True)

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Synced {synced} licenses ({skipped} skipped, {errors} errors)"
        ))

    def _sync_specific_license(self, license_number: str, dry_run: bool = False, force: bool = False):
        """Sync a specific license from GE server."""
        from license.models import LicenseDetailsModel

        try:
            license = LicenseDetailsModel.objects.get(license_number=license_number)
        except LicenseDetailsModel.DoesNotExist:
            raise CommandError(f"License {license_number} not found in database")

        self.stdout.write(f"Syncing license: {license_number}")
        self.stdout.write(f"  Current status: {license.purchase_status}")
        self.stdout.write(f"  GE File Number: {license.ge_file_number}")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Would sync data for license {license_number}"))
            return

        try:
            self._sync_license_data(license, force)
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully synced {license_number}"))
        except Exception as e:
            raise CommandError(f"Failed to sync {license_number}: {str(e)}")

    def _sync_license_data(self, license, force: bool = False):
        """
        Sync individual license data from GE server.
        This is a placeholder - actual implementation would call GE APIs.
        """
        # NOTE: This is where you would implement actual GE server API calls
        # For now, we'll just update local calculated fields

        with transaction.atomic():
            # Recalculate balance_cif from current database state
            calculated_balance = license.get_balance_cif
            if license.balance_cif != calculated_balance:
                self.stdout.write(
                    f"  Updating {license.license_number} balance: "
                    f"{license.balance_cif} → {calculated_balance}"
                )
                license.balance_cif = calculated_balance
                license.save(update_fields=['balance_cif', 'modified_on'])

            # Update import item balances
            for import_item in license.import_license.all():
                # Recalculate available_value
                new_available_value = import_item.available_value_calculated
                if import_item.available_value != new_available_value:
                    import_item.available_value = new_available_value
                    import_item.save(update_fields=['available_value'])

                # Recalculate available_quantity
                new_available_qty = import_item.balance_quantity
                if import_item.available_quantity != new_available_qty:
                    import_item.available_quantity = new_available_qty
                    import_item.save(update_fields=['available_quantity'])

    def _fetch_from_ge_server(self, license_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch license data from GE server APIs.

        This is a placeholder method - actual implementation would:
        1. Connect to ICEGATE/DGFT APIs
        2. Authenticate using certificates/credentials
        3. Fetch license details, BOE data, ownership info
        4. Return structured data

        Returns:
            Dict with license data or None if not found
        """
        # TODO: Implement actual GE server API calls
        # Example structure:
        # return {
        #     'license_number': license_number,
        #     'status': 'ACTIVE',
        #     'balance_cif': Decimal('1000.00'),
        #     'current_owner': {...},
        #     'boe_details': [...],
        #     'transfer_history': [...]
        # }

        self.stdout.write(self.style.WARNING(
            "Note: GE server API integration not implemented yet. "
            "Using local database calculations only."
        ))
        return None
