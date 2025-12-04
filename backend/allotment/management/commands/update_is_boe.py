"""
Management command to update is_boe field for allotments that have bill of entry records.
"""
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from allotment.models import AllotmentModel
from bill_of_entry.models import BillOfEntryModel


class Command(BaseCommand):
    help = 'Update is_boe flag for allotments that have bill of entry records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find allotments that have bill of entry records but is_boe is False
        allotments_with_boe = AllotmentModel.objects.annotate(
            has_boe=Exists(
                BillOfEntryModel.objects.filter(
                    allotment=OuterRef('pk')
                )
            )
        ).filter(has_boe=True, is_boe=False)

        count = allotments_with_boe.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would update {count} allotments with is_boe=True')
            )
            if count > 0:
                self.stdout.write('\nSample allotments that would be updated:')
                for allotment in allotments_with_boe[:10]:
                    boe_count = BillOfEntryModel.objects.filter(allotment=allotment).count()
                    self.stdout.write(
                        f'  - ID: {allotment.id}, Company: {allotment.company.name}, '
                        f'Item: {allotment.item_name}, BOE Count: {boe_count}'
                    )
        else:
            if count == 0:
                self.stdout.write(self.style.SUCCESS('No allotments need updating'))
                return

            # Update is_boe to True for allotments with bill of entry
            updated = allotments_with_boe.update(is_boe=True)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated} allotments with is_boe=True')
            )

        # Also check for allotments with is_boe=True but no bill of entry (optional cleanup)
        allotments_without_boe = AllotmentModel.objects.annotate(
            has_boe=Exists(
                BillOfEntryModel.objects.filter(
                    allotment=OuterRef('pk')
                )
            )
        ).filter(has_boe=False, is_boe=True)

        cleanup_count = allotments_without_boe.count()

        if cleanup_count > 0:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'\nDRY RUN: Found {cleanup_count} allotments with is_boe=True but no bill of entry'
                    )
                )
                self.stdout.write('Use --no-dry-run to reset these to is_boe=False')
            else:
                cleanup_updated = allotments_without_boe.update(is_boe=False)
                self.stdout.write(
                    self.style.WARNING(
                        f'Reset {cleanup_updated} allotments to is_boe=False (no bill of entry found)'
                    )
                )
