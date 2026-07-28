# reconciliation/models.py
"""
Models for the BOE / Invoice Reconciliation panel (Phase 1).

Business rule: One physical import may generate multiple documents, but it
must produce exactly one licence debit. This app reads across the
`license`, `bill_of_entry`, and `trade` apps to surface where that rule is
currently violated (missing links, duplicate debits, CIF/qty mismatches)
and provides a small, auditable set of manual-triage actions on top —
never automatic matching (see `services/queries.py` for the detection
queries and `views.py` for the write actions).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.constants import DEC_0
from apps.core.models import AuditModel


class ReconciliationNote(AuditModel):
    """
    A manual triage decision (ignore / mark pending) on a single row
    surfaced by one of the detection queries in `services/queries.py`.

    Exactly one of `trade` / `bill_of_entry` / `license_item` must be set
    per row — enforced in `clean()` (called from the view before save),
    not as a DB constraint, since the three FKs target different tables
    and a DB-level "exactly one of three nullable FKs" check is awkward in
    Postgres without a CHECK constraint referencing multiple columns
    (which we could add later if this proves insufficient in practice).

    Inherits `created_by` / `created_on` / `modified_by` / `modified_on`
    from `AuditModel` (see `apps.core.models.AuditModel`, the same base
    `LicenseTrade` and other domain models use).
    """

    STATUS_IGNORED = "IGNORED"
    STATUS_PENDING = "PENDING"
    STATUS_CHOICES = (
        (STATUS_IGNORED, "Ignored"),
        (STATUS_PENDING, "Pending"),
    )

    trade = models.ForeignKey(
        "trade.LicenseTrade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_notes",
    )
    bill_of_entry = models.ForeignKey(
        "bill_of_entry.BillOfEntryModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_notes",
    )
    license_item = models.ForeignKey(
        "license.LicenseImportItemsModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_notes",
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def clean(self):
        super().clean()
        targets = [self.trade_id, self.bill_of_entry_id, self.license_item_id]
        set_count = sum(1 for target in targets if target is not None)
        if set_count != 1:
            raise ValidationError(
                "Exactly one of trade, bill_of_entry, or license_item must be set "
                f"on a ReconciliationNote (got {set_count})."
            )

    def __str__(self) -> str:
        target = self.trade_id or self.bill_of_entry_id or self.license_item_id
        return f"ReconciliationNote[{self.pk}] {self.status} target={target}"


class ReconciliationLog(models.Model):
    """
    Append-only audit trail of every action taken from the reconciliation
    panel. Rows here are NEVER updated or deleted after creation — this is
    a ledger, not a mutable record, which is why it does NOT extend
    `AuditModel` (no `modified_on` / `modified_by`; only `created_on` and
    the acting `user`). Every write action in `views.py` creates its log
    row inside the same `transaction.atomic()` block as the actual change,
    so the log can never diverge from what really happened.
    """

    ACTION_LINK = "LINK"
    ACTION_MERGE_BOE = "MERGE_BOE"
    ACTION_IGNORE = "IGNORE"
    ACTION_MARK_PENDING = "MARK_PENDING"
    ACTION_RECALCULATE = "RECALCULATE"
    ACTION_ALLOCATE = "ALLOCATE"
    ACTION_EDIT_ALLOCATION = "EDIT_ALLOCATION"
    ACTION_REVERSE_ALLOCATION = "REVERSE_ALLOCATION"
    ACTION_MARK_EXTERNAL_INVOICE = "MARK_EXTERNAL_INVOICE"
    ACTION_REVERSE_EXTERNAL_INVOICE = "REVERSE_EXTERNAL_INVOICE"
    ACTION_WARNING_IGNORED = "WARNING_IGNORED"
    ACTION_WARNING_RESTORED = "WARNING_RESTORED"
    ACTION_CHOICES = (
        (ACTION_LINK, "Link"),
        (ACTION_MERGE_BOE, "Merge BOE"),
        (ACTION_IGNORE, "Ignore"),
        (ACTION_MARK_PENDING, "Mark Pending"),
        (ACTION_RECALCULATE, "Recalculate"),
        (ACTION_ALLOCATE, "Allocate"),
        (ACTION_EDIT_ALLOCATION, "Edit Allocation"),
        (ACTION_REVERSE_ALLOCATION, "Reverse Allocation"),
        (ACTION_MARK_EXTERNAL_INVOICE, "Mark External Invoice"),
        (ACTION_REVERSE_EXTERNAL_INVOICE, "Reverse External Invoice"),
        (ACTION_WARNING_IGNORED, "Warning Ignored"),
        (ACTION_WARNING_RESTORED, "Warning Restored"),
    )

    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)

    trade = models.ForeignKey(
        "trade.LicenseTrade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_logs",
    )
    bill_of_entry = models.ForeignKey(
        "bill_of_entry.BillOfEntryModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_logs",
    )
    license_item = models.ForeignKey(
        "license.LicenseImportItemsModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_logs",
    )

    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliation_logs",
    )
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["action", "created_on"]),
        ]

    def __str__(self) -> str:
        return f"ReconciliationLog[{self.pk}] {self.action} @ {self.created_on}"


# ---------------------------------------------------------------------------
# Phase A -- Partial-allocation ledger
# ---------------------------------------------------------------------------
#
# Business rule this replaces: prior to this phase, `calculate_debit()` /
# `calculate_allotment()` (apps.license.services.balance_calculator) excluded
# a RowDetails row's debit/allotment contribution with a BINARY check ("is
# ANY BOE linked to the trade / allotment at all?"). In production one
# invoice can be split across many BOEs, one BOE can back many invoices, and
# amounts rarely divide evenly -- a binary exclusion either double-counts or
# wrongly suppresses debit for the un-matched remainder.
#
# These two tables record actual PARTIAL allocations, scoped at the
# licence-item (`sr_number`) level rather than the invoice/BOE header level,
# because a single BOE or invoice can span multiple licences via multiple
# RowDetails/LicenseTradeLine rows -- a header-level allocation could not
# express which licence a partial amount belongs to.
#
# IMPORTANT -- independent consumption tracks, NOT a shared pool:
# `InvoiceBOEAllocation` (invoice-side: which LicenseTradeLine "explains"
# how much of a RowDetails row) and `BOEAllotmentAllocation` (allotment-side:
# which AllotmentItems row "sources" how much of a RowDetails row) are two
# SEPARATE, INDEPENDENT consumption tracks against the same RowDetails row's
# totals. A BOE row's CIF gets debited once physically, but it can
# simultaneously be "explained" by an invoice on one hand and "sourced from"
# an allotment on the other -- these are two different questions asked of
# the same row, so they get two different remaining-balances and two
# different allocation tables. See
# `apps.reconciliation.services.allocation_service.remaining_for_row_details_invoice_side`
# and `...remaining_for_row_details_allotment_side` -- each subtracts ONLY
# its own track's allocations, never the other's.
#
# No DB-level over-allocation constraint is attempted on either model: a
# CHECK enforcing "sum of allocations for this row <= row's own total" would
# require cross-row aggregation, which Postgres CHECK constraints cannot
# express. Over-allocation is prevented in the service layer instead
# (`allocation_service.create_invoice_boe_allocation` /
# `create_boe_allotment_allocation`), inside `transaction.atomic()` blocks
# with row-level locking to close the race window between the remaining-
# balance read and the allocation write.


class InvoiceBOEAllocation(AuditModel):
    """
    Invoice-side partial allocation: records how much of a single
    `RowDetails` debit row is "explained" by a single `LicenseTradeLine`
    (a SALE invoice line).

    Rows are never mutated once written (other than the `is_current` /
    `superseded_by` bookkeeping below) and never deleted -- this is a ledger.
    Editing an allocation amount creates a NEW row (see
    `allocation_service.edit_invoice_boe_allocation`) and marks the old row
    `is_current=False` with `superseded_by` pointing at the replacement, so
    the full history of what an allocation used to be is always
    reconstructable. Reversing an allocation (see
    `allocation_service.reverse_invoice_boe_allocation`) sets
    `status=REVERSED` and `is_current=False` -- again, never deleted.

    `calculate_debit()` (apps.license.services.balance_calculator) sums
    `allocated_cif_fc` for `status=ACTIVE, is_current=True` rows per
    `row_details` to compute how much of that row's CIF is already
    explained by an invoice, and excludes only that (floored-at-zero)
    portion from the licence's debit -- never the row's whole amount just
    because SOME allocation exists.

    See the module-level comment above for why this is an independent
    consumption track from `BOEAllotmentAllocation`, and why there is no
    DB-level over-allocation constraint here (see
    `apps.reconciliation.services.allocation_service` for where that's
    enforced instead).
    """

    STATUS_ACTIVE = "ACTIVE"
    STATUS_REVERSED = "REVERSED"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVERSED, "Reversed"),
    )

    trade_line = models.ForeignKey(
        "trade.LicenseTradeLine",
        on_delete=models.PROTECT,
        related_name="boe_allocations",
    )
    row_details = models.ForeignKey(
        "bill_of_entry.RowDetails",
        on_delete=models.PROTECT,
        related_name="invoice_allocations",
    )

    # Precision note: sized to cover the larger of the two source models'
    # precisions on each axis (LicenseTradeLine.qty_kg is 4dp,
    # RowDetails.cif_fc/cif_inr are 3dp) so `remaining_for_*` helpers (plain
    # Python Decimal subtraction) never lose precision regardless of which
    # side is subtracted from which. See `BOEAllotmentAllocation` -- same
    # field defs, kept identical on purpose.
    allocated_qty = models.DecimalField(
        max_digits=20, decimal_places=4, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    allocated_cif_fc = models.DecimalField(
        max_digits=20, decimal_places=3, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    allocated_cif_inr = models.DecimalField(
        max_digits=20, decimal_places=3, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True
    )
    is_current = models.BooleanField(default=True)
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supersedes",
    )
    version = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_current"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(allocated_qty__gte=0)
                    & models.Q(allocated_cif_fc__gte=0)
                    & models.Q(allocated_cif_inr__gte=0)
                ),
                name="invoiceboeallocation_non_negative_amounts",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"InvoiceBOEAllocation[{self.pk}] trade_line={self.trade_line_id} "
            f"row_details={self.row_details_id} {self.status} v{self.version}"
        )


class BOEAllotmentAllocation(AuditModel):
    """
    Allotment-side partial allocation: records how much of a single
    `RowDetails` debit row is "sourced from" a single `AllotmentItems` row
    (a non-BOE allotment being consumed by a physical import).

    Same ledger semantics as `InvoiceBOEAllocation`: rows are never mutated
    or deleted, editing supersedes (new row + old row's `is_current=False` /
    `superseded_by` set), reversing sets `status=REVERSED` and
    `is_current=False`. See `InvoiceBOEAllocation`'s docstring and the
    module-level comment above for the full reasoning -- it applies
    identically here, mirrored onto the allotment side.

    `calculate_allotment()` (apps.license.services.balance_calculator) sums
    `allocated_cif_fc` for `status=ACTIVE, is_current=True` rows per
    `allotment_item` to compute how much of that allotment's CIF has
    already been consumed by a BOE, and excludes only that (floored-at-zero)
    portion from the licence's allotment total.

    This is an INDEPENDENT consumption track from `InvoiceBOEAllocation` --
    both allocate against the same `RowDetails` row's totals, but neither
    one's allocations count against the other's remaining balance. See
    `apps.reconciliation.services.allocation_service.remaining_for_row_details_allotment_side`
    (subtracts only `BOEAllotmentAllocation` sums) vs
    `...remaining_for_row_details_invoice_side` (subtracts only
    `InvoiceBOEAllocation` sums).

    No DB-level over-allocation constraint here either, for the same reason
    as `InvoiceBOEAllocation` -- enforced in the service layer instead.
    """

    STATUS_ACTIVE = "ACTIVE"
    STATUS_REVERSED = "REVERSED"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVERSED, "Reversed"),
    )

    row_details = models.ForeignKey(
        "bill_of_entry.RowDetails",
        on_delete=models.PROTECT,
        related_name="allotment_allocations",
    )
    allotment_item = models.ForeignKey(
        "allotment.AllotmentItems",
        on_delete=models.PROTECT,
        related_name="boe_allocations",
    )

    # Same field defs as InvoiceBOEAllocation -- see that model's docstring
    # for the precision reasoning (kept identical on purpose so
    # `remaining_for_*` helpers never lose precision on either side).
    allocated_qty = models.DecimalField(
        max_digits=20, decimal_places=4, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    allocated_cif_fc = models.DecimalField(
        max_digits=20, decimal_places=3, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    allocated_cif_inr = models.DecimalField(
        max_digits=20, decimal_places=3, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True
    )
    is_current = models.BooleanField(default=True)
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supersedes",
    )
    version = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_current"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(allocated_qty__gte=0)
                    & models.Q(allocated_cif_fc__gte=0)
                    & models.Q(allocated_cif_inr__gte=0)
                ),
                name="boeallotmentallocation_non_negative_amounts",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"BOEAllotmentAllocation[{self.pk}] row_details={self.row_details_id} "
            f"allotment_item={self.allotment_item_id} {self.status} v{self.version}"
        )


class ExternalInvoiceLink(AuditModel):
    """
    Marks a BOE debit row (`RowDetails`) as belonging to an invoice that is
    NOT a system `LicenseTradeLine` — e.g. a supplier/paper invoice that was
    never entered as a trade. This resolves the BOE out of `missing_invoice`
    detection (see `services/queries.py`) without inventing a fake
    `LicenseTradeLine`/`InvoiceBOEAllocation` row for it.

    Deliberately a STRUCTURED relationship (row_details FK + a plain
    `invoice_number` text field + qty/CIF captured at mark time) rather than
    overwriting `BillOfEntryModel.invoice_no` with a sentinel string — this
    preserves the distinction between "a real system invoice number" and
    "a user-entered external reference," keeps referential integrity, and
    lets reporting tell the two apart cleanly.

    Same append-only ledger semantics as `InvoiceBOEAllocation` /
    `BOEAllotmentAllocation`: never mutated or deleted. Reversing sets
    `status=REVERSED, is_current=False` (see
    `apps.reconciliation.services.external_invoice_service`).

    NOTE: this is a purchase-side reconciliation annotation only — it never
    feeds `LicenseBalanceCalculator` (no CIF moves between companies just by
    marking a BOE's invoice as external), unlike `InvoiceBOEAllocation` which
    genuinely reduces `calculate_debit()`'s contribution for a row matched to
    a SALE trade line.
    """

    STATUS_ACTIVE = "ACTIVE"
    STATUS_REVERSED = "REVERSED"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVERSED, "Reversed"),
    )

    row_details = models.ForeignKey(
        "bill_of_entry.RowDetails",
        on_delete=models.PROTECT,
        related_name="external_invoice_links",
    )
    invoice_number = models.CharField(max_length=255)
    qty = models.DecimalField(
        max_digits=20, decimal_places=4, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    cif_fc = models.DecimalField(
        max_digits=20, decimal_places=3, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )
    cif_inr = models.DecimalField(
        max_digits=20, decimal_places=3, default=DEC_0,
        validators=[MinValueValidator(DEC_0)],
    )

    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True
    )
    is_current = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_current"]),
            models.Index(fields=["invoice_number"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(qty__gte=0)
                    & models.Q(cif_fc__gte=0)
                    & models.Q(cif_inr__gte=0)
                ),
                name="externalinvoicelink_non_negative_amounts",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"ExternalInvoiceLink[{self.pk}] row_details={self.row_details_id} "
            f"invoice_number={self.invoice_number!r} {self.status}"
        )


class IgnoredWarning(models.Model):
    """
    Workflow-only "ignore" flag for a Licence Balance Workspace warning
    (`LicenseBalanceLedgerBuilder.build_warnings`).

    Deliberately NOT append-only like `InvoiceBOEAllocation`/
    `BOEAllotmentAllocation`/`ExternalInvoiceLink` — a warning's identity
    (`license`, `warning_type`, `entity_type`, `entity_id`) is stable and
    recomputed fresh on every `build()` call, so there is exactly one row
    per warning identity and `ignored` is toggled in place (restore sets
    `ignored=False` rather than creating a new row) — matches the product
    spec's "Ignored = False -> Returns to Active Warnings" exactly.

    CRITICAL: ignoring a warning is PURE workflow bookkeeping. It must
    NEVER be read by `LicenseBalanceLedgerBuilder`'s financial calculations
    (`build_financial_ledger`/`build_customs_ledger`/`calculate_balance`
    etc.) — those must produce identical numbers whether a warning is
    ignored or not. Only `build_warnings` (via `apply_ignored_status`)
    reads this model, purely to split results into active/ignored for
    display.
    """

    warning_type = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=32, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    license = models.ForeignKey(
        "license.LicenseDetailsModel",
        on_delete=models.CASCADE,
        related_name="ignored_warnings",
    )

    ignored = models.BooleanField(default=True, db_index=True)
    ignored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    ignored_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["license", "warning_type", "entity_type", "entity_id"],
                name="uniq_ignored_warning_identity",
            ),
        ]
        indexes = [
            models.Index(fields=["license", "ignored"]),
        ]

    def __str__(self) -> str:
        return (
            f"IgnoredWarning[{self.pk}] {self.warning_type}/{self.entity_type}:{self.entity_id} "
            f"license={self.license_id} ignored={self.ignored}"
        )
