"""Record DEC-50 item CIF adjustments (append-only). Dry run by default.

    manage.py refresh_item_cif_adjustments --all            # dry run: counts only
    manage.py refresh_item_cif_adjustments --license-ids 1,2 --apply

`--apply` writes audit rows: on a real database it needs owner approval (SAT gate §4).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.license.models import LicenseDetailsModel
from apps.reconciliation.services.item_cif_adjustment_log import refresh_item_cif_adjustment_log


class Command(BaseCommand):
    help = "Record DEC-50 item CIF over-utilisation adjustments (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--license-ids", default="")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        if opts["all"]:
            ids = list(LicenseDetailsModel.objects.values_list("id", flat=True))
        elif opts["license_ids"]:
            ids = [int(x) for x in opts["license_ids"].split(",") if x.strip()]
        else:
            raise CommandError("Pass --license-ids or --all")
        result = refresh_item_cif_adjustment_log(ids, dry_run=not opts["apply"])
        self.stdout.write(
            f"dry_run={result['dry_run']} batch={result['batch_id']} "
            f"licences_changed={len(result['licences_changed'])} transfers={result['transfers']}"
        )
