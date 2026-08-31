from django.core.management.base import BaseCommand
from apps.trade.services.final_party_classification import backfill_final_party_classifications


class Command(BaseCommand):
    help = "Deterministically backfill final-party sale classifications from canonical graph evidence."

    def handle(self, *args, **options):
        changed = backfill_final_party_classifications()
        self.stdout.write(self.style.SUCCESS(" ".join(f"{key}={value}" for key, value in changed.items())))
