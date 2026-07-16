from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.bill_of_entry.models import RowDetails


class Command(BaseCommand):
    help = "Fast delete duplicate RowDetails and remove entries with null bill_of_entry + transaction_type = 'D'"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report rows that would be deleted without deleting them.",
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs.get("dry_run", False)
        total_deleted = 0

        # 1. Delete rows where bill_of_entry is NULL and transaction_type is 'D'
        null_be_qs = RowDetails.objects.filter(bill_of_entry__isnull=True, transaction_type='D')
        null_be_count = null_be_qs.count()
        if null_be_count > 0:
            if dry_run:
                self.stdout.write(
                    f"Would delete {null_be_count} rows with null bill_of_entry and transaction_type='D'."
                )
            else:
                null_be_qs.delete()
                total_deleted += null_be_count
                self.stdout.write(f"Deleted {null_be_count} rows with null bill_of_entry and transaction_type='D'.")

        # 2. Handle duplicates (keep only 1 per group)
        self.stdout.write("Finding duplicate RowDetails...")

        duplicates = (
            RowDetails.objects.values('bill_of_entry', 'sr_number', 'transaction_type')
            .annotate(row_count=Count('id'))
            .filter(row_count__gt=1)
        )

        if not duplicates:
            self.stdout.write("No duplicates found.")
        else:
            duplicate_keys = {
                (d['bill_of_entry'], d['sr_number'], d['transaction_type'])
                for d in duplicates
            }

            # Efficiently fetch matching rows
            rows = RowDetails.objects.filter(
                bill_of_entry__in=[k[0] for k in duplicate_keys],
                sr_number__in=[k[1] for k in duplicate_keys],
                transaction_type__in=[k[2] for k in duplicate_keys],
            ).values('id', 'bill_of_entry', 'sr_number', 'transaction_type')

            # Group by key
            grouped = defaultdict(list)
            for row in rows:
                key = (row['bill_of_entry'], row['sr_number'], row['transaction_type'])
                grouped[key].append(row['id'])

            # Collect IDs to delete (skip smallest ID in each group)
            delete_ids = []
            for ids in grouped.values():
                ids.sort()
                delete_ids.extend(ids[1:])

            if delete_ids:
                if dry_run:
                    self.stdout.write(f"Would delete {len(delete_ids)} duplicate rows.")
                else:
                    deleted_count, _ = RowDetails.objects.filter(id__in=delete_ids).delete()
                    total_deleted += deleted_count
                    self.stdout.write(f"Deleted {deleted_count} duplicate rows.")

        if dry_run:
            self.stdout.write("Dry run complete. No rows deleted.")
        else:
            self.stdout.write(f"Done. Total rows deleted: {total_deleted}")
