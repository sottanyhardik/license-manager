"""SAT-DEF-150 / C-2: auto-link exact allotment<->BOE matches. Dry run by default.

Also covers rows created via bulk_create, which bypass the post-save trigger.
"""
import csv

from django.core.management.base import BaseCommand, CommandError

from apps.reconciliation.services.allotment_auto_link import (
    apply_exact_links,
    reverse_batch,
)


class Command(BaseCommand):
    help = "Auto-link EXACT allotment/BOE matches (dry run unless --apply); list the rest for review."

    def add_arguments(self, parser):
        parser.add_argument("--license-ids", help="Comma-separated licence ids")
        parser.add_argument("--all", action="store_true", help="All licences")
        parser.add_argument("--apply", action="store_true", help="Perform the links (default: dry run)")
        parser.add_argument("--reverse", metavar="BATCH_ID", help="Reverse a previous batch")
        parser.add_argument("--csv", metavar="PATH", help="Write exact + review rows to CSV")

    def handle(self, *args, **opts):
        if opts["reverse"]:
            res = reverse_batch(opts["reverse"])
            self.stdout.write(f"batch {res['batch_id']}: reversed {len(res['reversed'])} link(s)")
            return
        if opts["all"] == bool(opts["license_ids"]):
            raise CommandError("Specify exactly one of --license-ids or --all")
        ids = None
        if opts["license_ids"]:
            try:
                ids = [int(x) for x in opts["license_ids"].split(",") if x.strip()]
            except ValueError as exc:
                raise CommandError("--license-ids must be integers") from exc
        res = apply_exact_links(ids, dry_run=not opts["apply"])
        review = res["review"]
        self.stdout.write(
            f"mode={'DRY-RUN' if res['dry_run'] else 'APPLY'} batch_id={res['batch_id']} "
            f"exact={len(res['exact'])} review={len(review)} linked={len(res['linked'])}"
        )
        if opts["csv"]:
            with open(opts["csv"], "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["kind", "allotment_id", "boe_id", "reason", "qty_delta", "cif_delta"])
                for r in res["exact"]:
                    w.writerow(["EXACT", r["allotment_id"], r["boe_id"], "EXACT", 0, 0])
                for r in review:
                    w.writerow(["REVIEW", r["allotment_id"], r["boe_id"], r["reason"], r["qty_delta"], r["cif_delta"]])
            self.stdout.write(f"csv written: {opts['csv']}")
