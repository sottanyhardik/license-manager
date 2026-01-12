"""
Django management command to delete licenses based on exporter name filtering
along with their related allotments and BOEs in batches.

OPTIMIZED VERSION - Uses bulk operations and minimal queries for maximum speed.

Usage:
    # Delete licenses where exporter contains "tractor"
    python manage.py delete_licenses_by_exporter --filter contains --exporter "tractor" --dry-run
    python manage.py delete_licenses_by_exporter --filter contains --exporter "tractor" --confirm

    # Delete licenses where exporter is NOT "International Tractor" (keep only International Tractor)
    python manage.py delete_licenses_by_exporter --filter exclude --exporter "International Tractor" --dry-run
    python manage.py delete_licenses_by_exporter --filter exclude --exporter "International Tractor" --confirm

    # Delete licenses where exporter contains "SION C969"
    python manage.py delete_licenses_by_exporter --filter contains --exporter "SION C969" --confirm --batch-size 100

    # Keep only SION C969, delete all others
    python manage.py delete_licenses_by_exporter --filter exclude --exporter "SION C969" --confirm
"""

from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.db.models import Count, Q

from license.models import LicenseDetailsModel
from allotment.models import AllotmentItems, AllotmentModel
from bill_of_entry.models import BillOfEntryModel, RowDetails


class Command(BaseCommand):
    help = 'Delete licenses based on exporter name filtering along with related allotments and BOEs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--filter',
            type=str,
            required=True,
            choices=['contains', 'exclude'],
            help='Filter type: "contains" deletes matching licenses, "exclude" keeps only matching licenses',
        )
        parser.add_argument(
            '--exporter',
            type=str,
            required=True,
            help='Exporter name or pattern to filter by (case-insensitive)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually perform the deletion (required to delete data)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of licenses to delete per batch (default: 100, larger is faster)',
        )
        parser.add_argument(
            '--disable-signals',
            action='store_true',
            help='Disable post_save/post_delete signals for faster deletion (recommended for bulk operations)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']
        batch_size = options['batch_size']
        filter_type = options['filter']
        exporter_pattern = options['exporter']
        disable_signals = options['disable_signals']

        if not dry_run and not confirm:
            self.stdout.write(
                self.style.ERROR(
                    'You must specify either --dry-run or --confirm to proceed'
                )
            )
            return

        # Build query based on filter type
        if filter_type == 'contains':
            licenses_query = Q(exporter__name__icontains=exporter_pattern)
            description = f'exporter contains "{exporter_pattern}"'
        else:  # exclude
            licenses_query = ~Q(exporter__name__iexact=exporter_pattern)
            description = f'exporter is NOT "{exporter_pattern}"'

        # Count total licenses
        total_licenses = LicenseDetailsModel.objects.filter(licenses_query).count()

        if total_licenses == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'No licenses found where {description}'
                )
            )
            return

        # Display total count
        self.stdout.write(self.style.WARNING('\n=== DELETION SUMMARY ==='))
        self.stdout.write(f'Filter: {description}')
        self.stdout.write(f'Total licenses to delete: {total_licenses}')
        self.stdout.write(f'Batch size: {batch_size}')
        self.stdout.write(f'Number of batches: {(total_licenses + batch_size - 1) // batch_size}')

        if disable_signals:
            self.stdout.write(self.style.WARNING('⚡ Signals disabled for faster deletion'))

        # Show sample licenses
        self.stdout.write(self.style.WARNING('\n=== SAMPLE LICENSES TO DELETE (first 10) ==='))
        sample_licenses = LicenseDetailsModel.objects.filter(licenses_query).select_related('exporter')[:10]
        for lic in sample_licenses:
            exporter_name = lic.exporter.name if lic.exporter else 'NULL'
            self.stdout.write(f'  - {lic.license_number} (Exporter: {exporter_name})')

        if total_licenses > 10:
            self.stdout.write(f'  ... and {total_licenses - 10} more')

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n[DRY RUN] No data was deleted. Use --confirm to actually delete.'
                )
            )
            return

        # Confirm deletion
        self.stdout.write(
            self.style.ERROR(
                '\n⚠️  WARNING: This will permanently delete the data listed above!'
            )
        )

        # Perform deletion in batches
        total_deleted = {
            'licenses': 0,
            'allotment_items': 0,
            'allotments': 0,
            'row_details': 0,
            'boes': 0,
        }

        batch_num = 0

        # Optionally disable signals for speed
        disconnected_signals = []
        if disable_signals:
            from django.db.models.signals import post_save, post_delete, pre_delete, pre_save
            from allotment.models import update_stock, delete_stock as allotment_delete_stock
            from bill_of_entry.models import update_stock as boe_update_stock, delete_stock as boe_delete_stock

            # Disable allotment signals
            post_save.disconnect(update_stock, sender=AllotmentItems)
            post_delete.disconnect(allotment_delete_stock, sender=AllotmentItems)
            disconnected_signals.append(('post_save', update_stock, AllotmentItems))
            disconnected_signals.append(('post_delete', allotment_delete_stock, AllotmentItems))

            # Disable BOE signals
            post_save.disconnect(boe_update_stock, sender=RowDetails)
            post_delete.disconnect(boe_delete_stock, sender=RowDetails)
            disconnected_signals.append(('post_save', boe_update_stock, RowDetails))
            disconnected_signals.append(('post_delete', boe_delete_stock, RowDetails))

            # Disable ALL license signals for maximum speed
            try:
                from license.signals import (
                    auto_fetch_import_items,
                    update_license_on_export_item_change,
                    update_license_on_export_item_delete,
                    update_license_on_import_item_change,
                    update_license_on_import_item_delete,
                    update_license_on_allotment_item_change,
                    update_license_on_boe_item_change,
                    update_license_on_trade_line_change,
                )

                # Disconnect license-related signals
                post_save.disconnect(auto_fetch_import_items, sender=LicenseDetailsModel)
                post_save.disconnect(update_license_on_export_item_change, sender='license.LicenseExportItemModel')
                post_delete.disconnect(update_license_on_export_item_delete, sender='license.LicenseExportItemModel')
                post_save.disconnect(update_license_on_import_item_change, sender='license.LicenseImportItemsModel')
                post_delete.disconnect(update_license_on_import_item_delete, sender='license.LicenseImportItemsModel')
                post_save.disconnect(update_license_on_allotment_item_change, sender='allotment.AllotmentItems')
                post_delete.disconnect(update_license_on_allotment_item_change, sender='allotment.AllotmentItems')
                post_save.disconnect(update_license_on_boe_item_change, sender='bill_of_entry.RowDetails')
                post_delete.disconnect(update_license_on_boe_item_change, sender='bill_of_entry.RowDetails')
                post_save.disconnect(update_license_on_trade_line_change, sender='trade.LicenseTradeLine')
                post_delete.disconnect(update_license_on_trade_line_change, sender='trade.LicenseTradeLine')

                self.stdout.write(self.style.SUCCESS('  ✓ Disabled all license balance update signals'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠ Could not disable some license signals: {e}'))

            # Disable allotment signals from allotment/signals.py
            try:
                from allotment.signals import update_is_allotted_on_save, update_is_allotted_on_delete
                post_save.disconnect(update_is_allotted_on_save, sender=AllotmentItems)
                pre_delete.disconnect(update_is_allotted_on_delete, sender=AllotmentItems)
                self.stdout.write(self.style.SUCCESS('  ✓ Disabled allotment is_allotted signals'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠ Could not disable allotment signals: {e}'))

        try:
            while True:
                # Get next batch of license IDs only (fast query)
                batch_licenses = list(
                    LicenseDetailsModel.objects.filter(licenses_query)
                    .values_list('id', flat=True)[:batch_size]
                )

                if not batch_licenses:
                    break

                batch_num += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'\n=== Batch {batch_num}/{(total_licenses + batch_size - 1) // batch_size} ({len(batch_licenses)} licenses) ==='
                    )
                )

                try:
                    with transaction.atomic():
                        # OPTIMIZATION: Use bulk deletes without checking orphaned status
                        # Django CASCADE will clean up related objects automatically

                        # 1. Delete AllotmentItems (faster - no orphan check)
                        allotment_items_count, _ = AllotmentItems.objects.filter(
                            item__license__id__in=batch_licenses
                        ).delete()

                        if allotment_items_count > 0:
                            total_deleted['allotment_items'] += allotment_items_count
                            self.stdout.write(
                                self.style.SUCCESS(f'  ✓ Deleted {allotment_items_count} AllotmentItems')
                            )

                        # 2. Delete orphaned Allotments (items with no remaining allotment_details)
                        orphaned_allotments = AllotmentModel.objects.annotate(
                            item_count=Count('allotment_details')
                        ).filter(item_count=0)
                        allotments_count = orphaned_allotments.count()
                        if allotments_count > 0:
                            orphaned_allotments.delete()
                            total_deleted['allotments'] += allotments_count
                            self.stdout.write(
                                self.style.SUCCESS(f'  ✓ Deleted {allotments_count} orphaned Allotments')
                            )

                        # 3. Delete RowDetails (faster - no orphan check)
                        row_details_count, _ = RowDetails.objects.filter(
                            sr_number__license__id__in=batch_licenses
                        ).delete()

                        if row_details_count > 0:
                            total_deleted['row_details'] += row_details_count
                            self.stdout.write(
                                self.style.SUCCESS(f'  ✓ Deleted {row_details_count} RowDetails')
                            )

                        # 4. Delete orphaned BOEs (BOEs with no remaining item_details)
                        orphaned_boes = BillOfEntryModel.objects.annotate(
                            item_count=Count('item_details')
                        ).filter(item_count=0)
                        boes_count = orphaned_boes.count()
                        if boes_count > 0:
                            orphaned_boes.delete()
                            total_deleted['boes'] += boes_count
                            self.stdout.write(
                                self.style.SUCCESS(f'  ✓ Deleted {boes_count} orphaned BOEs')
                            )

                        # 5. Delete Licenses (CASCADE handles LicenseExportItemModel, LicenseImportItemsModel, etc.)
                        licenses_result = LicenseDetailsModel.objects.filter(
                            id__in=batch_licenses
                        ).delete()
                        licenses_count = licenses_result[0]
                        total_deleted['licenses'] += licenses_count
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Deleted {licenses_count} Licenses and related objects')
                        )

                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ Batch {batch_num} completed')
                    )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Error in batch {batch_num}: {str(e)}')
                    )
                    raise

        finally:
            # Re-enable signals if they were disabled
            if disable_signals:
                from django.db.models.signals import post_save, post_delete, pre_delete
                from allotment.models import update_stock, delete_stock as allotment_delete_stock
                from bill_of_entry.models import update_stock as boe_update_stock, delete_stock as boe_delete_stock

                # Re-enable allotment and BOE signals
                post_save.connect(update_stock, sender=AllotmentItems, dispatch_uid="update_stock")
                post_delete.connect(allotment_delete_stock, sender=AllotmentItems)
                post_save.connect(boe_update_stock, sender=RowDetails, dispatch_uid="update_stock_on_save")
                post_delete.connect(boe_delete_stock, sender=RowDetails)

                # Re-enable license signals
                try:
                    from license.signals import (
                        auto_fetch_import_items,
                        update_license_on_export_item_change,
                        update_license_on_export_item_delete,
                        update_license_on_import_item_change,
                        update_license_on_import_item_delete,
                        update_license_on_allotment_item_change,
                        update_license_on_boe_item_change,
                        update_license_on_trade_line_change,
                    )

                    post_save.connect(auto_fetch_import_items, sender=LicenseDetailsModel)
                    post_save.connect(update_license_on_export_item_change, sender='license.LicenseExportItemModel')
                    post_delete.connect(update_license_on_export_item_delete, sender='license.LicenseExportItemModel')
                    post_save.connect(update_license_on_import_item_change, sender='license.LicenseImportItemsModel')
                    post_delete.connect(update_license_on_import_item_delete, sender='license.LicenseImportItemsModel')
                    post_save.connect(update_license_on_allotment_item_change, sender='allotment.AllotmentItems')
                    post_delete.connect(update_license_on_allotment_item_change, sender='allotment.AllotmentItems')
                    post_save.connect(update_license_on_boe_item_change, sender='bill_of_entry.RowDetails')
                    post_delete.connect(update_license_on_boe_item_change, sender='bill_of_entry.RowDetails')
                    post_save.connect(update_license_on_trade_line_change, sender='trade.LicenseTradeLine')
                    post_delete.connect(update_license_on_trade_line_change, sender='trade.LicenseTradeLine')
                except Exception:
                    pass

                # Re-enable allotment signals
                try:
                    from allotment.signals import update_is_allotted_on_save, update_is_allotted_on_delete
                    post_save.connect(update_is_allotted_on_save, sender=AllotmentItems)
                    pre_delete.connect(update_is_allotted_on_delete, sender=AllotmentItems)
                except Exception:
                    pass

                self.stdout.write(self.style.SUCCESS('\n✓ Re-enabled all signals'))

        # Final summary
        self.stdout.write(self.style.SUCCESS('\n=== FINAL SUMMARY ==='))
        self.stdout.write(f'Filter used: {description}')
        self.stdout.write(f'Total Licenses deleted: {total_deleted["licenses"]}')
        self.stdout.write(f'Total AllotmentItems deleted: {total_deleted["allotment_items"]}')
        self.stdout.write(f'Total Allotments deleted: {total_deleted["allotments"]}')
        self.stdout.write(f'Total RowDetails deleted: {total_deleted["row_details"]}')
        self.stdout.write(f'Total BOEs deleted: {total_deleted["boes"]}')
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully deleted all licenses where {description}'
            )
        )
