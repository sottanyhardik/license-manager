"""
Django management command to delete licenses where exporter is NOT "International Tractor"
along with their related allotments and BOEs in batches.

Usage:
    python manage.py delete_non_international_tractor_licenses --dry-run
    python manage.py delete_non_international_tractor_licenses --confirm
    python manage.py delete_non_international_tractor_licenses --confirm --batch-size 20
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from license.models import LicenseDetailsModel
from allotment.models import AllotmentItems, AllotmentModel
from bill_of_entry.models import BillOfEntryModel, RowDetails


class Command(BaseCommand):
    help = 'Delete all licenses where exporter is NOT "International Tractor" along with related allotments and BOEs'

    def add_arguments(self, parser):
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
            default=20,
            help='Number of licenses to delete per batch (default: 20)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']
        batch_size = options['batch_size']

        if not dry_run and not confirm:
            self.stdout.write(
                self.style.ERROR(
                    'You must specify either --dry-run or --confirm to proceed'
                )
            )
            return

        # Find licenses where exporter is NOT "International Tractor"
        # Handle cases where exporter might be null or the name doesn't match
        licenses_to_delete = LicenseDetailsModel.objects.exclude(
            exporter__name__iexact='International Tractor'
        ).select_related('exporter')

        total_licenses = licenses_to_delete.count()

        if total_licenses == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    'No licenses found where exporter is not "International Tractor"'
                )
            )
            return

        # Display total count
        self.stdout.write(self.style.WARNING('\n=== DELETION SUMMARY ==='))
        self.stdout.write(f'Total licenses to delete: {total_licenses}')
        self.stdout.write(f'Batch size: {batch_size}')
        self.stdout.write(f'Number of batches: {(total_licenses + batch_size - 1) // batch_size}')

        # Show sample licenses
        self.stdout.write(self.style.WARNING('\n=== SAMPLE LICENSES TO DELETE (first 10) ==='))
        for lic in licenses_to_delete[:10]:
            exporter_name = lic.exporter.name if lic.exporter else 'NULL'
            self.stdout.write(
                f'  - {lic.license_number} (Exporter: {exporter_name})'
            )

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
        while True:
            # Get next batch of licenses
            batch_licenses = list(
                LicenseDetailsModel.objects.exclude(
                    exporter__name__iexact='International Tractor'
                ).values_list('id', flat=True)[:batch_size]
            )

            if not batch_licenses:
                break

            batch_num += 1
            self.stdout.write(
                self.style.WARNING(
                    f'\n=== Processing Batch {batch_num} ({len(batch_licenses)} licenses) ==='
                )
            )

            try:
                with transaction.atomic():
                    # Find related data for this batch
                    allotment_items = AllotmentItems.objects.filter(
                        item__license__id__in=batch_licenses
                    )
                    allotment_items_count = allotment_items.count()

                    row_details = RowDetails.objects.filter(
                        sr_number__license__id__in=batch_licenses
                    )
                    row_details_count = row_details.count()

                    # Find BOEs that will become orphaned
                    boe_ids_from_rows = list(
                        row_details.values_list('bill_of_entry_id', flat=True).distinct()
                    )

                    boes_to_delete = []
                    for boe_id in boe_ids_from_rows:
                        if boe_id:
                            remaining_rows = RowDetails.objects.filter(
                                bill_of_entry_id=boe_id
                            ).exclude(sr_number__license__id__in=batch_licenses).count()

                            if remaining_rows == 0:
                                boes_to_delete.append(boe_id)

                    # Find Allotments that will become orphaned
                    allotment_ids_from_items = list(
                        allotment_items.values_list('allotment_id', flat=True).distinct()
                    )

                    allotments_to_delete = []
                    for allotment_id in allotment_ids_from_items:
                        if allotment_id:
                            remaining_items = AllotmentItems.objects.filter(
                                allotment_id=allotment_id
                            ).exclude(item__license__id__in=batch_licenses).count()

                            if remaining_items == 0:
                                allotments_to_delete.append(allotment_id)

                    # Delete in reverse dependency order
                    # 1. Delete AllotmentItems
                    if allotment_items_count > 0:
                        deleted_allotment_items = allotment_items.delete()
                        count = deleted_allotment_items[0]
                        total_deleted['allotment_items'] += count
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Deleted {count} AllotmentItems')
                        )

                    # 2. Delete orphaned Allotments
                    if allotments_to_delete:
                        deleted_allotments = AllotmentModel.objects.filter(
                            id__in=allotments_to_delete
                        ).delete()
                        count = deleted_allotments[0]
                        total_deleted['allotments'] += count
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Deleted {count} orphaned Allotments')
                        )

                    # 3. Delete RowDetails
                    if row_details_count > 0:
                        deleted_row_details = row_details.delete()
                        count = deleted_row_details[0]
                        total_deleted['row_details'] += count
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Deleted {count} RowDetails')
                        )

                    # 4. Delete orphaned BOEs
                    if boes_to_delete:
                        deleted_boes = BillOfEntryModel.objects.filter(
                            id__in=boes_to_delete
                        ).delete()
                        count = deleted_boes[0]
                        total_deleted['boes'] += count
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Deleted {count} orphaned BOEs')
                        )

                    # 5. Delete Licenses (CASCADE will handle export/import items)
                    deleted_licenses = LicenseDetailsModel.objects.filter(
                        id__in=batch_licenses
                    ).delete()
                    count = deleted_licenses[0]
                    total_deleted['licenses'] += count
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Deleted {count} Licenses and related objects')
                    )

                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ Batch {batch_num} completed successfully')
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error in batch {batch_num}: {str(e)}')
                )
                raise

        # Final summary
        self.stdout.write(self.style.SUCCESS('\n=== FINAL SUMMARY ==='))
        self.stdout.write(f'Total Licenses deleted: {total_deleted["licenses"]}')
        self.stdout.write(f'Total AllotmentItems deleted: {total_deleted["allotment_items"]}')
        self.stdout.write(f'Total Allotments deleted: {total_deleted["allotments"]}')
        self.stdout.write(f'Total RowDetails deleted: {total_deleted["row_details"]}')
        self.stdout.write(f'Total BOEs deleted: {total_deleted["boes"]}')
        self.stdout.write(
            self.style.SUCCESS(
                '\n✅ Successfully deleted all licenses where exporter is not "International Tractor"'
            )
        )
