"""
Manual mirror refresh: ``python manage.py mds_sync [--model core.CompanyModel]``.

Useful for initial hydration, ad-hoc catch-up, and debugging without Celery.
Exits non-zero if the service is unreachable so cron/ops can alert.
"""

from django.core.management.base import BaseCommand, CommandError

from mds_client.client import MDSClient, MDSUnavailable
from mds_client.sync import sync_all, sync_model


class Command(BaseCommand):
    help = "Refresh the local master-data mirror from the Master-Data Service (MDS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            dest="model_label",
            default=None,
            help="Sync only this model_label (as declared in settings.MDS_MODELS). "
            "Omit to sync all configured models.",
        )

    def handle(self, *args, **options):
        model_label = options["model_label"]
        client = MDSClient()
        try:
            if model_label:
                results = [sync_model(model_label, client=client)]
            else:
                results = sync_all(client=client)
        except MDSUnavailable as exc:
            raise CommandError(f"MDS is unreachable: {exc}") from exc
        finally:
            client.close()

        for result in results:
            self.stdout.write(self.style.SUCCESS(str(result)))
        self.stdout.write(self.style.SUCCESS(f"Done. Synced {len(results)} model(s)."))
