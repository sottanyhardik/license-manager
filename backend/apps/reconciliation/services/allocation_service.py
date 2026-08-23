# reconciliation/services/allocation_service.py
"""
Partial-allocation ledger service for the BOE / Invoice Reconciliation
workbench (Phase A).

Business rule this replaces: `calculate_debit()` / `calculate_allotment()`
(apps.license.services.balance_calculator) used to exclude a RowDetails
row's contribution with a BINARY check ("is ANY BOE linked at all?"). In
production one invoice can be split across many BOEs, one BOE can back many
invoices, and amounts rarely divide evenly -- this module records actual
PARTIAL allocations so the calculator can exclude exactly the allocated
portion of a row, never the whole row.

Two INDEPENDENT consumption tracks, not a shared pool:
  - `InvoiceBOEAllocation` -- how much of a RowDetails row is "explained"
    by a LicenseTradeLine (invoice side).
  - `BOEAllotmentAllocation` -- how much of a RowDetails row is "sourced
    from" an AllotmentItems row (allotment side).
A RowDetails row's CIF is debited once physically, but it can
simultaneously be explained by an invoice AND sourced from an allotment --
these are two different questions, so `remaining_for_row_details_invoice_side`
subtracts ONLY InvoiceBOEAllocation sums and `remaining_for_row_details_allotment_side`
subtracts ONLY BOEAllotmentAllocation sums. Neither function subtracts the
other's allocations. See `apps.reconciliation.models` module-level comment
for the full reasoning.

Every create/edit/reverse function here is wrapped in `transaction.atomic()`
and writes a `ReconciliationLog` row inside the SAME transaction, so the
audit log can never diverge from what really happened (same pattern as
`apps.reconciliation.views`). Row-level locking (`select_for_update`) is
used on the trade_line/row_details/allotment_item being allocated against,
to close the race window between reading "remaining" and writing the new
allocation row -- this is a financial ledger, so a lost-update race here
would silently create an over-allocation.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.constants import DEC_0
from apps.core.utils.decimal_utils import to_decimal


def _floor0(value: Decimal) -> Decimal:
    """Never let a remaining-balance component go negative."""
    return value if value > DEC_0 else DEC_0


def _sum_allocations(queryset) -> tuple[Decimal, Decimal, Decimal]:
    row = queryset.aggregate(
        qty=Coalesce(Sum("allocated_qty"), Value(DEC_0), output_field=DecimalField()),
        cif_fc=Coalesce(Sum("allocated_cif_fc"), Value(DEC_0), output_field=DecimalField()),
        cif_inr=Coalesce(Sum("allocated_cif_inr"), Value(DEC_0), output_field=DecimalField()),
    )
    return row["qty"], row["cif_fc"], row["cif_inr"]


# ---------------------------------------------------------------------------
# Remaining-balance helpers
# ---------------------------------------------------------------------------

def remaining_for_trade_line(trade_line, *, exclude_allocation_id=None) -> tuple[Decimal, Decimal, Decimal]:
    """
    `(qty, cif_fc, cif_inr)` remaining on this LicenseTradeLine, i.e. its own
    totals minus the sum of its ACTIVE, current `InvoiceBOEAllocation` rows.
    Each component is floored at 0.

    `exclude_allocation_id`: when recomputing "remaining as if this
    allocation didn't exist" for an edit/supersede, pass the id of the
    allocation being replaced so its own consumption isn't counted against
    itself.
    """
    from apps.reconciliation.models import InvoiceBOEAllocation

    qs = InvoiceBOEAllocation.objects.filter(
        trade_line=trade_line,
        status=InvoiceBOEAllocation.STATUS_ACTIVE,
        is_current=True,
    )
    if exclude_allocation_id is not None:
        qs = qs.exclude(pk=exclude_allocation_id)
    allocated_qty, allocated_cif_fc, allocated_cif_inr = _sum_allocations(qs)

    return (
        _floor0(to_decimal(trade_line.qty_kg, DEC_0) - allocated_qty),
        _floor0(to_decimal(trade_line.cif_fc, DEC_0) - allocated_cif_fc),
        _floor0(to_decimal(trade_line.cif_inr, DEC_0) - allocated_cif_inr),
    )


def remaining_for_row_details_invoice_side(row_details, *, exclude_allocation_id=None, exclude_external_link_id=None) -> tuple[Decimal, Decimal, Decimal]:
    """
    `(qty, cif_fc, cif_inr)` remaining on this RowDetails row for INVOICE
    matching purposes -- its own totals minus the sum of its ACTIVE, current
    `InvoiceBOEAllocation` rows AND its ACTIVE, current `ExternalInvoiceLink`
    rows (an out-of-system invoice mark consumes the same "invoice side"
    capacity as a real `InvoiceBOEAllocation` would -- both answer "how much
    of this BOE is explained by *an* invoice," so they share one remaining
    balance; without subtracting both, a row could be marked fully external
    and then still get a full system allocation on top, double-counting).

    Deliberately does NOT also subtract `BOEAllotmentAllocation` sums: the
    invoice track and the allotment track are independent consumption
    tracks against the same row (see module docstring / `apps.reconciliation
    .models` module comment) -- a RowDetails row's CIF is debited once
    physically but can be simultaneously "explained" by an invoice and
    "sourced from" an allotment, so mixing the two tracks into one number
    would double-subtract capacity that was never actually shared.
    """
    from apps.reconciliation.models import ExternalInvoiceLink, InvoiceBOEAllocation

    qs = InvoiceBOEAllocation.objects.filter(
        row_details=row_details,
        status=InvoiceBOEAllocation.STATUS_ACTIVE,
        is_current=True,
    )
    if exclude_allocation_id is not None:
        qs = qs.exclude(pk=exclude_allocation_id)
    allocated_qty, allocated_cif_fc, allocated_cif_inr = _sum_allocations(qs)

    ext_qs = ExternalInvoiceLink.objects.filter(
        row_details=row_details,
        status=ExternalInvoiceLink.STATUS_ACTIVE,
        is_current=True,
    )
    if exclude_external_link_id is not None:
        ext_qs = ext_qs.exclude(pk=exclude_external_link_id)
    ext_row = ext_qs.aggregate(
        qty=Coalesce(Sum("qty"), Value(DEC_0), output_field=DecimalField()),
        cif_fc=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
        cif_inr=Coalesce(Sum("cif_inr"), Value(DEC_0), output_field=DecimalField()),
    )

    return (
        _floor0(to_decimal(row_details.qty, DEC_0) - allocated_qty - ext_row["qty"]),
        _floor0(to_decimal(row_details.cif_fc, DEC_0) - allocated_cif_fc - ext_row["cif_fc"]),
        _floor0(to_decimal(row_details.cif_inr, DEC_0) - allocated_cif_inr - ext_row["cif_inr"]),
    )


def remaining_for_row_details_allotment_side(row_details, *, exclude_allocation_id=None) -> tuple[Decimal, Decimal, Decimal]:
    """
    `(qty, cif_fc, cif_inr)` remaining on this RowDetails row for ALLOTMENT
    matching purposes -- its own totals minus ONLY the sum of its ACTIVE,
    current `BOEAllotmentAllocation` rows. Independent from
    `remaining_for_row_details_invoice_side` by design -- see that
    function's docstring and the module docstring.
    """
    from apps.reconciliation.models import BOEAllotmentAllocation

    qs = BOEAllotmentAllocation.objects.filter(
        row_details=row_details,
        status=BOEAllotmentAllocation.STATUS_ACTIVE,
        is_current=True,
    )
    if exclude_allocation_id is not None:
        qs = qs.exclude(pk=exclude_allocation_id)
    allocated_qty, allocated_cif_fc, allocated_cif_inr = _sum_allocations(qs)

    return (
        _floor0(to_decimal(row_details.qty, DEC_0) - allocated_qty),
        _floor0(to_decimal(row_details.cif_fc, DEC_0) - allocated_cif_fc),
        _floor0(to_decimal(row_details.cif_inr, DEC_0) - allocated_cif_inr),
    )


def remaining_for_allotment_item(allotment_item, *, exclude_allocation_id=None) -> tuple[Decimal, Decimal, Decimal]:
    """
    `(qty, cif_fc, cif_inr)` remaining on this AllotmentItems row -- its own
    totals minus the sum of its ACTIVE, current `BOEAllotmentAllocation`
    rows. Each component floored at 0.
    """
    from apps.reconciliation.models import BOEAllotmentAllocation

    qs = BOEAllotmentAllocation.objects.filter(
        allotment_item=allotment_item,
        status=BOEAllotmentAllocation.STATUS_ACTIVE,
        is_current=True,
    )
    if exclude_allocation_id is not None:
        qs = qs.exclude(pk=exclude_allocation_id)
    allocated_qty, allocated_cif_fc, allocated_cif_inr = _sum_allocations(qs)

    return (
        _floor0(to_decimal(allotment_item.qty, DEC_0) - allocated_qty),
        _floor0(to_decimal(allotment_item.cif_fc, DEC_0) - allocated_cif_fc),
        _floor0(to_decimal(allotment_item.cif_inr, DEC_0) - allocated_cif_inr),
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_non_negative(qty: Decimal, cif_fc: Decimal, cif_inr: Decimal) -> None:
    if qty < DEC_0 or cif_fc < DEC_0 or cif_inr < DEC_0:
        raise ValidationError(
            "Allocation amounts must not be negative "
            f"(got qty={qty}, cif_fc={cif_fc}, cif_inr={cif_inr})."
        )


def _validate_fits(*, qty, cif_fc, cif_inr, remaining, side_label: str) -> None:
    remaining_qty, remaining_cif_fc, remaining_cif_inr = remaining
    if qty > remaining_qty or cif_fc > remaining_cif_fc or cif_inr > remaining_cif_inr:
        raise ValidationError(
            f"Allocation exceeds {side_label}'s remaining amount "
            f"(requested qty={qty}, cif_fc={cif_fc}, cif_inr={cif_inr}; "
            f"remaining qty={remaining_qty}, cif_fc={remaining_cif_fc}, "
            f"cif_inr={remaining_cif_inr})."
        )


# ---------------------------------------------------------------------------
# Invoice-side (InvoiceBOEAllocation)
# ---------------------------------------------------------------------------

def create_invoice_boe_allocation(trade_line, row_details, qty, cif_fc, cif_inr, user, notes=""):
    """
    Create a new ACTIVE `InvoiceBOEAllocation` linking `trade_line` (a SALE
    LicenseTradeLine) to `row_details` (a RowDetails debit row), for the
    given amounts.

    Validates:
      - same licence on both sides (`trade_line.sr_number.license_id ==
        row_details.sr_number.license_id`);
      - non-negative amounts;
      - amounts fit within BOTH the trade line's remaining
        (`remaining_for_trade_line`) AND the row details' remaining on the
        invoice side (`remaining_for_row_details_invoice_side`);
      - no existing ACTIVE, current allocation already exists for this
        exact `(trade_line, row_details)` pair (use
        `edit_invoice_boe_allocation` instead).
    """
    from apps.reconciliation.models import InvoiceBOEAllocation, ReconciliationLog

    qty = to_decimal(qty, DEC_0)
    cif_fc = to_decimal(cif_fc, DEC_0)
    cif_inr = to_decimal(cif_inr, DEC_0)
    _validate_non_negative(qty, cif_fc, cif_inr)

    trade_line_license_id = trade_line.sr_number.license_id
    row_details_license_id = row_details.sr_number.license_id
    if trade_line_license_id != row_details_license_id:
        raise ValidationError(
            "Cross-licence allocation rejected: trade_line's sr_number "
            f"belongs to licence {trade_line_license_id}, row_details' "
            f"sr_number belongs to licence {row_details_license_id}."
        )

    with transaction.atomic():
        # Lock both sides for the duration of the check-then-write to close
        # the race window between reading "remaining" and creating the row.
        trade_line = type(trade_line).objects.select_for_update().get(pk=trade_line.pk)
        row_details = type(row_details).objects.select_for_update().get(pk=row_details.pk)

        if InvoiceBOEAllocation.objects.filter(
            trade_line=trade_line,
            row_details=row_details,
            status=InvoiceBOEAllocation.STATUS_ACTIVE,
            is_current=True,
        ).exists():
            raise ValidationError(
                "An active allocation already exists for this trade line / "
                "row details pair. Use edit_invoice_boe_allocation to change "
                "it instead of creating a duplicate."
            )

        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_trade_line(trade_line),
            side_label="the invoice line",
        )
        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_row_details_invoice_side(row_details),
            side_label="the BOE row (invoice side)",
        )

        allocation = InvoiceBOEAllocation.objects.create(
            trade_line=trade_line,
            row_details=row_details,
            allocated_qty=qty,
            allocated_cif_fc=cif_fc,
            allocated_cif_inr=cif_inr,
            status=InvoiceBOEAllocation.STATUS_ACTIVE,
            is_current=True,
            version=1,
            notes=notes,
            created_by=user,
        )

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_ALLOCATE,
            license_item=trade_line.sr_number,
            before=None,
            after=_invoice_allocation_snapshot(allocation),
            reason=notes,
            user=user,
        )

    return allocation


def edit_invoice_boe_allocation(allocation, qty, cif_fc, cif_inr, user, notes=""):
    """
    Supersede `allocation` (an `InvoiceBOEAllocation`) with a new row
    carrying the new amounts. The OLD row is never mutated (other than
    `is_current`/`superseded_by`) -- a brand new row is created with
    `version = allocation.version + 1`.

    Validates the new amounts the same way `create_invoice_boe_allocation`
    does, EXCLUDING `allocation` itself from the "remaining" calculation
    (it's being replaced, so its own consumption must not count against
    itself).
    """
    from apps.reconciliation.models import InvoiceBOEAllocation, ReconciliationLog

    qty = to_decimal(qty, DEC_0)
    cif_fc = to_decimal(cif_fc, DEC_0)
    cif_inr = to_decimal(cif_inr, DEC_0)
    _validate_non_negative(qty, cif_fc, cif_inr)

    with transaction.atomic():
        allocation = InvoiceBOEAllocation.objects.select_for_update().get(pk=allocation.pk)
        if not allocation.is_current or allocation.status != InvoiceBOEAllocation.STATUS_ACTIVE:
            raise ValidationError(
                "Only a current, ACTIVE allocation can be edited/superseded."
            )

        trade_line = type(allocation.trade_line).objects.select_for_update().get(
            pk=allocation.trade_line_id
        )
        row_details = type(allocation.row_details).objects.select_for_update().get(
            pk=allocation.row_details_id
        )

        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_trade_line(trade_line, exclude_allocation_id=allocation.pk),
            side_label="the invoice line",
        )
        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_row_details_invoice_side(row_details, exclude_allocation_id=allocation.pk),
            side_label="the BOE row (invoice side)",
        )

        before = _invoice_allocation_snapshot(allocation)

        new_allocation = InvoiceBOEAllocation.objects.create(
            trade_line=trade_line,
            row_details=row_details,
            allocated_qty=qty,
            allocated_cif_fc=cif_fc,
            allocated_cif_inr=cif_inr,
            status=InvoiceBOEAllocation.STATUS_ACTIVE,
            is_current=True,
            version=allocation.version + 1,
            notes=notes,
            created_by=user,
        )

        allocation.is_current = False
        allocation.superseded_by = new_allocation
        allocation.modified_by = user
        allocation.save(update_fields=["is_current", "superseded_by", "modified_by", "modified_on"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_EDIT_ALLOCATION,
            license_item=trade_line.sr_number,
            before=before,
            after=_invoice_allocation_snapshot(new_allocation),
            reason=notes,
            user=user,
        )

    return new_allocation


def reverse_invoice_boe_allocation(allocation, user, reason):
    """
    Reverse an `InvoiceBOEAllocation`: sets `status=REVERSED`,
    `is_current=False`. Never deletes the row -- the previously-allocated
    amount becomes visible again to `remaining_for_trade_line` /
    `remaining_for_row_details_invoice_side` (and therefore to
    `calculate_debit()`), since both only sum ACTIVE + current rows.
    """
    from apps.reconciliation.models import InvoiceBOEAllocation, ReconciliationLog

    with transaction.atomic():
        allocation = InvoiceBOEAllocation.objects.select_for_update().get(pk=allocation.pk)
        before = _invoice_allocation_snapshot(allocation)

        allocation.status = InvoiceBOEAllocation.STATUS_REVERSED
        allocation.is_current = False
        allocation.modified_by = user
        allocation.save(update_fields=["status", "is_current", "modified_by", "modified_on"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_REVERSE_ALLOCATION,
            license_item=allocation.trade_line.sr_number,
            before=before,
            after=_invoice_allocation_snapshot(allocation),
            reason=reason,
            user=user,
        )

    return allocation


def _invoice_allocation_snapshot(allocation) -> dict:
    return {
        "type": "InvoiceBOEAllocation",
        "allocation_id": allocation.id,
        "trade_line_id": allocation.trade_line_id,
        "row_details_id": allocation.row_details_id,
        "allocated_qty": str(allocation.allocated_qty),
        "allocated_cif_fc": str(allocation.allocated_cif_fc),
        "allocated_cif_inr": str(allocation.allocated_cif_inr),
        "status": allocation.status,
        "is_current": allocation.is_current,
        "version": allocation.version,
    }


# ---------------------------------------------------------------------------
# Allotment-side (BOEAllotmentAllocation)
# ---------------------------------------------------------------------------

def create_boe_allotment_allocation(row_details, allotment_item, qty, cif_fc, cif_inr, user, notes=""):
    """
    Create a new ACTIVE `BOEAllotmentAllocation` linking `row_details` (a
    RowDetails debit row) to `allotment_item` (an AllotmentItems row), for
    the given amounts. Mirrors `create_invoice_boe_allocation`'s validation
    on the allotment side.

    `AllotmentItems.item` is nullable -- an allotment item with no `item`
    set has no licence to compare against, so it is rejected with a clear
    `ValidationError` rather than raising `AttributeError`.
    """
    from apps.reconciliation.models import BOEAllotmentAllocation, ReconciliationLog

    qty = to_decimal(qty, DEC_0)
    cif_fc = to_decimal(cif_fc, DEC_0)
    cif_inr = to_decimal(cif_inr, DEC_0)
    _validate_non_negative(qty, cif_fc, cif_inr)

    if allotment_item.item is None:
        raise ValidationError(
            "Cannot allocate against an AllotmentItems row with no `item` "
            "set -- it has no licence to validate against."
        )

    row_details_license_id = row_details.sr_number.license_id
    allotment_item_license_id = allotment_item.item.license_id
    if row_details_license_id != allotment_item_license_id:
        raise ValidationError(
            "Cross-licence allocation rejected: row_details' sr_number "
            f"belongs to licence {row_details_license_id}, allotment_item's "
            f"item belongs to licence {allotment_item_license_id}."
        )

    with transaction.atomic():
        row_details = type(row_details).objects.select_for_update().get(pk=row_details.pk)
        allotment_item = type(allotment_item).objects.select_for_update().get(pk=allotment_item.pk)

        if BOEAllotmentAllocation.objects.filter(
            row_details=row_details,
            allotment_item=allotment_item,
            status=BOEAllotmentAllocation.STATUS_ACTIVE,
            is_current=True,
        ).exists():
            raise ValidationError(
                "An active allocation already exists for this row details / "
                "allotment item pair. Use edit_boe_allotment_allocation to "
                "change it instead of creating a duplicate."
            )

        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_row_details_allotment_side(row_details),
            side_label="the BOE row (allotment side)",
        )
        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_allotment_item(allotment_item),
            side_label="the allotment item",
        )

        allocation = BOEAllotmentAllocation.objects.create(
            row_details=row_details,
            allotment_item=allotment_item,
            allocated_qty=qty,
            allocated_cif_fc=cif_fc,
            allocated_cif_inr=cif_inr,
            status=BOEAllotmentAllocation.STATUS_ACTIVE,
            is_current=True,
            version=1,
            notes=notes,
            created_by=user,
        )

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_ALLOCATE,
            license_item=allotment_item.item,
            before=None,
            after=_allotment_allocation_snapshot(allocation),
            reason=notes,
            user=user,
        )

    return allocation


def edit_boe_allotment_allocation(allocation, qty, cif_fc, cif_inr, user, notes=""):
    """Mirrors `edit_invoice_boe_allocation` for `BOEAllotmentAllocation`."""
    from apps.reconciliation.models import BOEAllotmentAllocation, ReconciliationLog

    qty = to_decimal(qty, DEC_0)
    cif_fc = to_decimal(cif_fc, DEC_0)
    cif_inr = to_decimal(cif_inr, DEC_0)
    _validate_non_negative(qty, cif_fc, cif_inr)

    with transaction.atomic():
        allocation = BOEAllotmentAllocation.objects.select_for_update().get(pk=allocation.pk)
        if not allocation.is_current or allocation.status != BOEAllotmentAllocation.STATUS_ACTIVE:
            raise ValidationError(
                "Only a current, ACTIVE allocation can be edited/superseded."
            )

        row_details = type(allocation.row_details).objects.select_for_update().get(
            pk=allocation.row_details_id
        )
        allotment_item = type(allocation.allotment_item).objects.select_for_update().get(
            pk=allocation.allotment_item_id
        )

        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_row_details_allotment_side(row_details, exclude_allocation_id=allocation.pk),
            side_label="the BOE row (allotment side)",
        )
        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_allotment_item(allotment_item, exclude_allocation_id=allocation.pk),
            side_label="the allotment item",
        )

        before = _allotment_allocation_snapshot(allocation)

        new_allocation = BOEAllotmentAllocation.objects.create(
            row_details=row_details,
            allotment_item=allotment_item,
            allocated_qty=qty,
            allocated_cif_fc=cif_fc,
            allocated_cif_inr=cif_inr,
            status=BOEAllotmentAllocation.STATUS_ACTIVE,
            is_current=True,
            version=allocation.version + 1,
            notes=notes,
            created_by=user,
        )

        allocation.is_current = False
        allocation.superseded_by = new_allocation
        allocation.modified_by = user
        allocation.save(update_fields=["is_current", "superseded_by", "modified_by", "modified_on"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_EDIT_ALLOCATION,
            license_item=allotment_item.item,
            before=before,
            after=_allotment_allocation_snapshot(new_allocation),
            reason=notes,
            user=user,
        )

    return new_allocation


def reverse_boe_allotment_allocation(allocation, user, reason):
    """Mirrors `reverse_invoice_boe_allocation` for `BOEAllotmentAllocation`."""
    from apps.reconciliation.models import BOEAllotmentAllocation, ReconciliationLog

    with transaction.atomic():
        allocation = BOEAllotmentAllocation.objects.select_for_update().get(pk=allocation.pk)
        before = _allotment_allocation_snapshot(allocation)

        allocation.status = BOEAllotmentAllocation.STATUS_REVERSED
        allocation.is_current = False
        allocation.modified_by = user
        allocation.save(update_fields=["status", "is_current", "modified_by", "modified_on"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_REVERSE_ALLOCATION,
            license_item=allocation.allotment_item.item,
            before=before,
            after=_allotment_allocation_snapshot(allocation),
            reason=reason,
            user=user,
        )

    return allocation


def _allotment_allocation_snapshot(allocation) -> dict:
    return {
        "type": "BOEAllotmentAllocation",
        "allocation_id": allocation.id,
        "row_details_id": allocation.row_details_id,
        "allotment_item_id": allocation.allotment_item_id,
        "allocated_qty": str(allocation.allocated_qty),
        "allocated_cif_fc": str(allocation.allocated_cif_fc),
        "allocated_cif_inr": str(allocation.allocated_cif_inr),
        "status": allocation.status,
        "is_current": allocation.is_current,
        "version": allocation.version,
    }


# ---------------------------------------------------------------------------
# Dispatcher: reverse either allocation type
# ---------------------------------------------------------------------------

def reverse_allocation(allocation, user, reason):
    """
    Reverse either an `InvoiceBOEAllocation` or a `BOEAllotmentAllocation`.
    Thin dispatcher over `reverse_invoice_boe_allocation` /
    `reverse_boe_allotment_allocation` -- prefer calling those directly when
    the type is already known (e.g. from typed call sites in Phase B);
    this exists for call sites that only have "an allocation" generically.
    """
    from apps.reconciliation.models import BOEAllotmentAllocation, InvoiceBOEAllocation

    if isinstance(allocation, InvoiceBOEAllocation):
        return reverse_invoice_boe_allocation(allocation, user, reason)
    if isinstance(allocation, BOEAllotmentAllocation):
        return reverse_boe_allotment_allocation(allocation, user, reason)
    raise TypeError(
        f"reverse_allocation() expects an InvoiceBOEAllocation or "
        f"BOEAllotmentAllocation, got {type(allocation)!r}."
    )


# ---------------------------------------------------------------------------
# External (out-of-system) invoice marking
# ---------------------------------------------------------------------------

def mark_boe_as_external_invoice(row_details, invoice_number, qty, cif_fc, cif_inr, user, notes=""):
    """
    Mark `row_details` (a RowDetails debit row) as explained by an invoice
    that is NOT a system `LicenseTradeLine` -- e.g. a supplier's paper
    invoice never entered as a trade. Creates an ACTIVE `ExternalInvoiceLink`.

    `invoice_number` is a required, user-entered free-text reference (e.g.
    "OTH-001245" or a supplier invoice number) -- validated non-blank here
    since it's the only identifying information for an otherwise-untracked
    invoice.

    Shares the same "remaining on the invoice side" capacity as
    `InvoiceBOEAllocation` (see `remaining_for_row_details_invoice_side`),
    so this cannot over-allocate a row beyond its own qty/CIF regardless of
    how the remainder is split between system and external invoices.
    """
    from apps.reconciliation.models import ExternalInvoiceLink, ReconciliationLog

    if not invoice_number or not invoice_number.strip():
        raise ValidationError("An invoice number is required to mark a BOE as an external invoice.")

    qty = to_decimal(qty, DEC_0)
    cif_fc = to_decimal(cif_fc, DEC_0)
    cif_inr = to_decimal(cif_inr, DEC_0)
    _validate_non_negative(qty, cif_fc, cif_inr)

    with transaction.atomic():
        row_details = type(row_details).objects.select_for_update().get(pk=row_details.pk)

        _validate_fits(
            qty=qty, cif_fc=cif_fc, cif_inr=cif_inr,
            remaining=remaining_for_row_details_invoice_side(row_details),
            side_label="the BOE row (invoice side)",
        )

        link = ExternalInvoiceLink.objects.create(
            row_details=row_details,
            invoice_number=invoice_number.strip(),
            qty=qty,
            cif_fc=cif_fc,
            cif_inr=cif_inr,
            status=ExternalInvoiceLink.STATUS_ACTIVE,
            is_current=True,
            notes=notes,
            created_by=user,
        )

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_MARK_EXTERNAL_INVOICE,
            license_item=row_details.sr_number,
            before=None,
            after=_external_invoice_link_snapshot(link),
            reason=notes,
            user=user,
        )

    return link


def reverse_external_invoice_link(link, user, reason):
    """
    Reverse an `ExternalInvoiceLink`: sets `status=REVERSED`,
    `is_current=False`. Never deletes the row -- the previously-marked
    amount becomes visible again to `remaining_for_row_details_invoice_side`,
    and the BOE reappears in `missing_invoice` detection if nothing else
    covers it.
    """
    from apps.reconciliation.models import ExternalInvoiceLink, ReconciliationLog

    with transaction.atomic():
        link = ExternalInvoiceLink.objects.select_for_update().get(pk=link.pk)
        before = _external_invoice_link_snapshot(link)

        link.status = ExternalInvoiceLink.STATUS_REVERSED
        link.is_current = False
        link.modified_by = user
        link.save(update_fields=["status", "is_current", "modified_by", "modified_on"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_REVERSE_EXTERNAL_INVOICE,
            license_item=link.row_details.sr_number,
            before=before,
            after=_external_invoice_link_snapshot(link),
            reason=reason,
            user=user,
        )

    return link


def _external_invoice_link_snapshot(link) -> dict:
    return {
        "type": "ExternalInvoiceLink",
        "link_id": link.id,
        "row_details_id": link.row_details_id,
        "invoice_number": link.invoice_number,
        "qty": str(link.qty),
        "cif_fc": str(link.cif_fc),
        "cif_inr": str(link.cif_inr),
        "status": link.status,
        "is_current": link.is_current,
    }
