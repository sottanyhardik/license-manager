from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.allotment.models import AllotmentItems


class Command(BaseCommand):
    help = 'Backfill status field for existing AllotmentItems'

    def handle(self, *args, **options):
        count = AllotmentItems.objects.filter(
            Q(status__isnull=True) | Q(status='')
        ).update(status='CREATED')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully backfilled {count} AllotmentItems with status=CREATED'
            )
        )
