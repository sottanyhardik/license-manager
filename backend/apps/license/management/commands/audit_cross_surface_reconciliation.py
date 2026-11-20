"""Read-only cross-surface reconciliation audit (Licence Overview / Import Items / Item Pivot / Item Report).

    python manage.py audit_cross_surface_reconciliation [--license NUM ...] [--limit N] [--out /tmp/recon.json]

Never writes: the whole run executes inside a transaction that is always rolled back.
"""
import json

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Read-only reconciliation of licence/item CIF and quantity metrics across every screen"

    def add_arguments(self, parser):
        parser.add_argument("--license", nargs="+", help="Licence numbers (default: every licence with import items)")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--chunk", type=int, default=150)
        parser.add_argument("--no-pivot", action="store_true")
        parser.add_argument("--no-item-report", action="store_true")
        parser.add_argument("--out", default="")

    def handle(self, *args, **opts):
        from apps.license.models import LicenseDetailsModel
        from apps.license.services.cross_surface_reconciliation import ROOT_CAUSES, collect_surfaces

        qs = LicenseDetailsModel.objects.filter(import_license__isnull=False).distinct().order_by("id")
        if opts["license"]:
            qs = qs.filter(license_number__in=opts["license"])
        ids = list(qs.values_list("id", flat=True))
        if opts["limit"]:
            ids = ids[: opts["limit"]]

        with transaction.atomic():
            res = collect_surfaces(ids, chunk=max(1, opts["chunk"]), include_pivot=not opts["no_pivot"],
                                   include_item_report=not opts["no_item_report"])
            transaction.set_rollback(True)

        out = self.stdout.write
        out(f"licences checked: {res.licences_checked}  import items: {res.import_items_checked}  "
            f"pivot product cells: {res.product_combinations}  discrepancies: {len(res.discrepancies)}")
        for note in res.notes:
            out(f"note: {note}")
        for cause, row in res.by_cause().items():
            out(f"{cause:<42} n={row['count']:<6} licences={row['licences']:<5} |Δcif|={row['abs_cif']:.2f} |Δqty|={row['abs_qty']:.3f}")
        if opts["out"]:
            payload = {
                "summary": {"licences": res.licences_checked, "import_items": res.import_items_checked,
                            "product_cells": res.product_combinations, "discrepancies": len(res.discrepancies)},
                "root_causes": ROOT_CAUSES, "by_cause": res.by_cause(), "notes": res.notes,
                "discrepancies": [d.as_dict() for d in res.discrepancies],
                "surface_values": {str(k): {s: {m: str(v) for m, v in vals.items()} for s, vals in sv.items()}
                                   for k, sv in res.surface_values.items()},
            }
            with open(opts["out"], "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1, default=str)
            out(f"written: {opts['out']}")
