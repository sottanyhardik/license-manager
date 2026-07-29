"""
Read-only data-health diagnostic for the Invoice<->BOE reconciliation ledger.

Safe to run anytime, including in production — it never writes anything.
Run this before/after `backfill_boe_allocations` to see the current state of:

- Trades with `.boes` attached whose SALE lines are unresolved (no
  unambiguous matching `InvoiceBOEAllocation` yet) — see
  `apps.reconciliation.services.boe_link_reconciler` for what "unresolved"
  means and why `trade.boes` alone was never enough to prevent a double
  debit (a BOE row and the SALE trade line it belongs to both counting
  towards the license's debit).
- Allocations that exceed either side's own CIF (a BOE allocated for more
  than its own value, or a trade line allocated for more than its own
  value) — should never happen given `create_invoice_boe_allocation`'s own
  validation, but this is an independent, defensive check.
- Duplicate ACTIVE allocations for the same (trade_line, row_details) pair
  — likewise defensive; the service layer already prevents new duplicates.
- The existing Reconciliation-panel detection queries (near-duplicate BOEs,
  multi-BOE/multi-invoice links, CIF/qty comparison) — reused, not
  reimplemented.

Usage:
    python manage.py check_allocation_health
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.reconciliation.services import queries as reconciliation_queries
from apps.reconciliation.services.boe_link_reconciler import reconcile_trade_boe_links

_DEC_0 = Decimal("0.00")


class Command(BaseCommand):
    help = (
        "Read-only diagnostic: reports data-health issues in the "
        "Invoice<->BOE allocation ledger. Never writes anything."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Allocation Health Check (read-only) ==="))
        self._check_unresolved_boe_links()
        self._check_over_allocations()
        self._check_duplicate_allocations()
        self._check_reused_queries()

    def _check_unresolved_boe_links(self):
        from apps.trade.models import LicenseTrade

        trades = LicenseTrade.objects.filter(direction=LicenseTrade.DIR_SALE, boes__isnull=False).distinct()
        unresolved = []
        for trade in trades:
            for row in reconcile_trade_boe_links(trade, dry_run=True):
                if row["status"] != "auto_migrated":
                    unresolved.append(row)

        self.stdout.write(f"\n[1] Trades with .boes linked but unresolved SALE lines: {len(unresolved)}")
        for row in unresolved[:50]:
            self.stdout.write(
                f"    Trade {row['trade_id']} ({row['invoice_number']}) line {row['trade_line_id']} "
                f"BOE(s) {', '.join(row['boe_numbers']) or '-'} -> {row['status']}: {row['detail']}"
            )
        if len(unresolved) > 50:
            self.stdout.write(f"    ... and {len(unresolved) - 50} more")

    def _check_over_allocations(self):
        from apps.reconciliation.models import InvoiceBOEAllocation

        active = InvoiceBOEAllocation.objects.filter(
            status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True,
        )

        boe_over = (
            active.values(
                "row_details_id", "row_details__cif_fc",
                "row_details__bill_of_entry__bill_of_entry_number",
            )
            .annotate(total=Coalesce(Sum("allocated_cif_fc"), Value(_DEC_0), output_field=DecimalField()))
        )
        boe_over_flagged = [r for r in boe_over if r["total"] > (r["row_details__cif_fc"] or _DEC_0)]
        self.stdout.write(f"\n[2] BOE rows allocated beyond their own CIF: {len(boe_over_flagged)}")
        for r in boe_over_flagged:
            self.stdout.write(
                f"    BOE {r['row_details__bill_of_entry__bill_of_entry_number']} row {r['row_details_id']}: "
                f"allocated {r['total']} > row CIF {r['row_details__cif_fc']}"
            )

        trade_over = (
            active.values("trade_line_id", "trade_line__cif_fc", "trade_line__trade__invoice_number")
            .annotate(total=Coalesce(Sum("allocated_cif_fc"), Value(_DEC_0), output_field=DecimalField()))
        )
        trade_over_flagged = [r for r in trade_over if r["total"] > (r["trade_line__cif_fc"] or _DEC_0)]
        self.stdout.write(f"\n[3] Trade lines allocated beyond their own CIF: {len(trade_over_flagged)}")
        for r in trade_over_flagged:
            self.stdout.write(
                f"    Trade {r['trade_line__trade__invoice_number']} line {r['trade_line_id']}: "
                f"allocated {r['total']} > line CIF {r['trade_line__cif_fc']}"
            )

    def _check_duplicate_allocations(self):
        from apps.reconciliation.models import InvoiceBOEAllocation

        dupes = (
            InvoiceBOEAllocation.objects.filter(status=InvoiceBOEAllocation.STATUS_ACTIVE, is_current=True)
            .values("trade_line_id", "row_details_id")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )
        self.stdout.write(f"\n[4] Duplicate ACTIVE allocations for the same (trade line, BOE row): {len(dupes)}")
        for r in dupes:
            self.stdout.write(
                f"    trade_line {r['trade_line_id']} / row_details {r['row_details_id']}: "
                f"{r['count']} active rows"
            )

    def _check_reused_queries(self):
        checks = [
            ("Duplicate BOE records (near-duplicate detection)", reconciliation_queries.duplicate_boes),
            ("Trades linking more than one BOE", reconciliation_queries.multi_boe_per_invoice),
            ("BOEs linked from more than one trade", reconciliation_queries.multi_invoice_per_boe),
            ("Invoice vs linked-BOE CIF mismatch", reconciliation_queries.cif_comparison),
            ("Invoice vs linked-BOE quantity mismatch", reconciliation_queries.qty_comparison),
        ]
        self.stdout.write("\n[5] Existing reconciliation-panel detection queries:")
        for label, fn in checks:
            rows = fn()
            self.stdout.write(f"    {label}: {len(rows)}")
