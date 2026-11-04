"""Reconcile the stored sold / balance / status cache of incentive licences.

The cache must equal what the licence's SALE lines say (``SALE_LINE_FILTERS``:
direction SALE and not a linked trade). This command scans EVERY incentive
licence, classifies each one, and corrects only the cases the trade lines prove.

Categories
----------
CORRECTABLE       Stored cache disagrees with the SALE lines, and sale evidence
                  exists. Applied with ``--apply``. Only the derived
                  sold/balance/status cache changes; no trade line or amount is touched.
NO_SALE_EVIDENCE  Cache says sold, but no SALE line supports it. Manual review.
                  Never zeroed automatically, because the sale might be real but
                  recorded outside the trade model.
OVERSOLD          SALE lines exceed the licence value. Status is YES, balance stays
                  negative. Manual review: the sale amount or the licence value is wrong.
DUPLICATE_SALE_LINES  The same licence appears twice on one SALE trade. The sum may
                  double count. Manual review. PURCHASE duplicates are reported
                  as data quality only: they never affect sold status.

Safety
------
* Dry run unless ``--apply`` is passed.
* Writes a CSV of every non-OK licence to ``--report-dir`` in both modes.
* With ``--apply``, first writes a JSON backup of the before-state of every row
  it is about to change, then recalculates each row through the canonical
  writer ``IncentiveLicense.update_sold_status``.
* Idempotent: a second ``--apply`` finds nothing CORRECTABLE.
* Never deletes, never edits trade lines, amounts or licence values.
"""
import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Sum

from apps.license.models.core import IncentiveLicense, derive_sold_status
from apps.license.services.license_profit import SALE_LINE_FILTERS
from apps.trade.models import IncentiveTradeLine

ZERO = Decimal("0.00")
CSV_FIELDS = [
    "category", "licence_id", "licence_number", "licence_value",
    "stored_sold", "stored_balance", "stored_status",
    "canonical_sold", "canonical_balance", "canonical_status",
    "sale_lines", "differing_fields", "proposed_action", "reason",
]


class Command(BaseCommand):
    help = "Reconcile incentive licence sold/balance/status from SALE trade lines (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write CORRECTABLE rows (default: dry run).")
        parser.add_argument(
            "--licence", action="append", default=[], dest="licences",
            help="Limit to this licence_number. Repeatable.",
        )
        parser.add_argument("--report-dir", default="reports", help="Directory for the CSV and backup JSON.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        report_dir = Path(options["report_dir"])
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = "apply" if apply_changes else "dry_run"

        licences = IncentiveLicense.objects.order_by("id")
        if options["licences"]:
            licences = licences.filter(license_number__in=options["licences"])
        licences = list(licences.only("id", "license_number", "license_value", "sold_value", "balance_value", "sold_status"))

        sale_sums, sale_counts = {}, {}
        for row in (
            IncentiveTradeLine.objects.filter(**SALE_LINE_FILTERS)
            .values("incentive_license_id")
            .annotate(total=Sum("license_value"), n=Count("id"))
        ):
            sale_sums[row["incentive_license_id"]] = row["total"] or ZERO
            sale_counts[row["incentive_license_id"]] = row["n"]

        rows, correctable, counts = [], [], {}
        for lic in licences:
            row = self._classify(lic, sale_sums.get(lic.id, ZERO), sale_counts.get(lic.id, 0))
            counts[row["category"]] = counts.get(row["category"], 0) + 1
            if row["category"] != "OK":
                rows.append(row)
            # A stale cache is repaired from SALE lines even when the licence is
            # over-sold. The over-sale itself stays flagged for review.
            if row["category"] == "CORRECTABLE" or (row["category"] == "OVERSOLD" and row["differing_fields"]):
                correctable.append((lic, row))

        rows.extend(self._duplicate_line_rows(None if not options["licences"] else [l.id for l in licences]))

        csv_path = report_dir / f"incentive_status_reconciliation_{mode}_{stamp}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(f"Scanned {len(licences)} incentive licence(s).")
        for category in sorted(counts):
            self.stdout.write(f"  {category}: {counts[category]}")
        self.stdout.write(f"Report: {csv_path}")

        if not apply_changes:
            self.stdout.write(f"Dry run: {len(correctable)} row(s) would be corrected. Re-run with --apply.")
            return

        backup_path = report_dir / f"incentive_status_backup_{stamp}.json"
        backup_path.write_text(
            json.dumps(
                [
                    {
                        "licence_id": lic.id,
                        "licence_number": lic.license_number,
                        "before": {
                            "sold_value": str(lic.sold_value),
                            "balance_value": str(lic.balance_value),
                            "sold_status": lic.sold_status,
                        },
                        "after": {
                            "sold_value": row["canonical_sold"],
                            "balance_value": row["canonical_balance"],
                            "sold_status": row["canonical_status"],
                        },
                    }
                    for lic, row in correctable
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        self.stdout.write(f"Backup of before-state: {backup_path}")

        applied = 0
        for lic, row in correctable:
            with transaction.atomic():
                IncentiveLicense.objects.get(pk=lic.id).update_sold_status()
                # Verify against a fresh SUM taken inside this transaction, not the
                # scan snapshot. Sales made after the scan are then reflected, and a
                # mismatch is reported as a verification failure.
                live = (
                    IncentiveTradeLine.objects.filter(incentive_license_id=lic.id, **SALE_LINE_FILTERS)
                    .aggregate(total=Sum("license_value"))["total"] or ZERO
                )
                licence = IncentiveLicense.objects.get(pk=lic.id)
                expected = (live, licence.license_value - live, derive_sold_status(live, licence.license_value - live))
                actual = (licence.sold_value, licence.balance_value, licence.sold_status)
                if actual != expected:
                    raise CommandError(
                        f"Post-write verification failed for licence {lic.license_number}: "
                        f"stored {actual}, expected {expected}. Earlier rows are committed; re-run is safe."
                    )
            applied += 1
        self.stdout.write(f"Applied {applied} correction(s).")

    def _classify(self, lic, canon_sold, sale_count):
        canon_balance = lic.license_value - canon_sold
        canon_status = derive_sold_status(canon_sold, canon_balance)
        diffs = []
        if lic.sold_value != canon_sold:
            diffs.append("sold_value")
        if lic.balance_value != canon_balance:
            diffs.append("balance_value")
        if lic.sold_status != canon_status:
            diffs.append("sold_status")

        if lic.sold_value > ZERO and canon_sold == ZERO:
            category, action = "NO_SALE_EVIDENCE", "manual review"
            reason = "Stored cache shows a sale but no SALE trade line supports it."
        elif canon_sold > lic.license_value:
            category = "OVERSOLD"
            action = "recalculate cache (--apply); manual review of sale amount" if diffs else "manual review"
            reason = "SALE lines exceed licence value. Status YES, balance negative. Verify the sale amount or the licence value."
        elif diffs:
            category, action = "CORRECTABLE", "recalculate cache (--apply)"
            reason = "Cache differs from SALE lines. Sale evidence present."
        else:
            category, action, reason = "OK", "none", ""

        return {
            "category": category,
            "licence_id": lic.id,
            "licence_number": lic.license_number,
            "licence_value": str(lic.license_value),
            "stored_sold": str(lic.sold_value),
            "stored_balance": str(lic.balance_value),
            "stored_status": lic.sold_status,
            "canonical_sold": str(canon_sold),
            "canonical_balance": str(canon_balance),
            "canonical_status": canon_status,
            "sale_lines": sale_count,
            "differing_fields": ";".join(diffs),
            "proposed_action": action,
            "reason": reason,
        }

    def _duplicate_line_rows(self, licence_ids=None):
        rows = []
        lines = IncentiveTradeLine.objects.all()
        if licence_ids is not None:
            lines = lines.filter(incentive_license_id__in=licence_ids)
        duplicates = (
            lines.values("trade_id", "incentive_license_id", "trade__direction", "trade__invoice_number", "incentive_license__license_number")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
        )
        for d in duplicates:
            is_sale = d["trade__direction"] == "SALE"
            rows.append({
                "category": "DUPLICATE_SALE_LINES" if is_sale else "DATA_QUALITY_DUPLICATE_PURCHASE_LINES",
                "licence_id": d["incentive_license_id"],
                "licence_number": d["incentive_license__license_number"],
                "licence_value": "", "stored_sold": "", "stored_balance": "", "stored_status": "",
                "canonical_sold": "", "canonical_balance": "", "canonical_status": "",
                "sale_lines": d["n"] if is_sale else 0,
                "differing_fields": "",
                "proposed_action": "manual review" if is_sale else "report only",
                "reason": (
                    f"{d['n']} identical lines on {d['trade__direction']} trade {d['trade__invoice_number']}. "
                    + ("A duplicate sale line double counts sold value." if is_sale
                       else "Purchase duplicates do not change sold status but affect purchase totals.")
                ),
            })
        return rows
