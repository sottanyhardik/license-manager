"""
One-time backfill: turns existing legacy `trade.boes` links into real
`InvoiceBOEAllocation` records wherever the match is unambiguous, closing
the double-debit gap described in
`apps.reconciliation.services.boe_link_reconciler` (a SALE trade line whose
goods came from an attached BOE, but which was never explicitly allocated,
gets debited once as the raw BOE row and again as the trade row).

Never guesses: only creates an allocation for an exact 1:1 match (see
`reconcile_trade_boe_links`'s docstring for the tolerance rule). Everything
else — no candidate BOE row, more than one candidate, or a CIF/qty mismatch
beyond tolerance — is left untouched and reported for manual review.

SAFETY: defaults to a dry run. Nothing is written to the database unless
`--apply` is passed. Run without `--apply` first, review the CSV report,
and only re-run with `--apply` once the report has been checked — this
changes live licence balances.

Idempotent: re-running only touches trade lines still missing an
allocation, so a partial or repeated `--apply` run never creates
duplicates (the underlying `create_invoice_boe_allocation` also refuses to
create a second ACTIVE allocation for the same trade_line/row_details pair).
Reversible without touching migration history: any allocation created here
can be reversed with `apps.reconciliation.services.allocation_service
.reverse_invoice_boe_allocation`.

Usage:
    python manage.py backfill_boe_allocations              # dry run, writes a report
    python manage.py backfill_boe_allocations --apply       # writes allocations for real
"""
import csv
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.reconciliation.services.boe_link_reconciler import reconcile_trade_boe_links

_REPORT_FIELDS = ["license_id", "trade_id", "invoice_number", "boe_numbers", "trade_line_id", "status", "detail"]


class Command(BaseCommand):
    help = (
        "Backfill InvoiceBOEAllocation records for legacy trade.boes links "
        "that have no matching allocation. Dry-run by default; pass --apply "
        "to write. Always produces a CSV report."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually create allocations. Without this flag, nothing is written.",
        )

    def handle(self, *args, **options):
        from apps.trade.models import LicenseTrade

        apply_changes = bool(options.get("apply"))
        self.stdout.write(self.style.WARNING(
            f"Mode: {'APPLY (writing allocations)' if apply_changes else 'DRY RUN (no writes)'}"
        ))

        trades = (
            LicenseTrade.objects
            .filter(direction=LicenseTrade.DIR_SALE, boes__isnull=False)
            .distinct()
            .order_by("id")
        )

        report_rows = []
        for trade in trades:
            with transaction.atomic():
                results = reconcile_trade_boe_links(trade, user=None, dry_run=not apply_changes)
            for row in results:
                report_rows.append({
                    "license_id": row["license_id"],
                    "trade_id": row["trade_id"],
                    "invoice_number": row["invoice_number"],
                    "boe_numbers": ", ".join(row["boe_numbers"]),
                    "trade_line_id": row["trade_line_id"],
                    "status": row["status"],
                    "detail": row["detail"],
                })

        counts = Counter(row["status"] for row in report_rows)
        self.stdout.write(f"\nExamined {trades.count()} SALE trades with attached BOEs.")
        self.stdout.write(f"Trade lines needing reconciliation: {len(report_rows)}")
        for status in ("auto_migrated", "ambiguous", "mismatch", "no_match"):
            self.stdout.write(f"  {status}: {counts.get(status, 0)}")

        report_path = self._write_report(report_rows)
        self.stdout.write(self.style.SUCCESS(f"\nReport written to {report_path}"))

        if not apply_changes and counts.get("auto_migrated"):
            self.stdout.write(self.style.WARNING(
                f"\n{counts['auto_migrated']} trade line(s) would be auto-migrated. "
                "Review the report above, then re-run with --apply to write them."
            ))

    def _write_report(self, report_rows) -> Path:
        reports_dir = Path(settings.BASE_DIR) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"boe_allocation_backfill_{timestamp}.csv"

        with open(report_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_REPORT_FIELDS)
            writer.writeheader()
            writer.writerows(report_rows)

        return report_path
