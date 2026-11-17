"""
boe_service.py — domain logic for the Bill of Entry app.

All functions accept model instances, dicts, and primitives.
No DRF Request objects enter this module.
Raises ValueError for invalid domain operations.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Product-name helpers
# ---------------------------------------------------------------------------

def update_product_name_for_boe(boe) -> dict[str, Any]:
    """
    Generate and save a product name for a single BOE from its item_details.

    Only updates when product_name is currently empty/None.

    Args:
        boe: BillOfEntryModel instance (already fetched by the caller).

    Returns:
        dict with keys: success (bool), product_name (str), message (str).
        On skip (name already filled): success=False.
        On no items found: success=False (caller should return HTTP 400).
    """
    if boe.product_name and boe.product_name.strip():
        return {
            "success": False,
            "product_name": boe.product_name,
            "message": f"Product name already exists: {boe.product_name}. Skipped update.",
        }

    generated_name = boe.generate_product_name_from_items()
    if not generated_name:
        return {
            "success": False,
            "product_name": boe.product_name,
            "message": "No items found to generate product name",
        }

    boe.product_name = generated_name
    boe.save(update_fields=["product_name"])
    return {
        "success": True,
        "product_name": generated_name,
        "message": f"Product name updated successfully to: {generated_name}",
    }


def bulk_update_product_names() -> dict[str, Any]:
    """
    Batch-update product_name for all BOEs where it is empty/None and
    invoice_no is also null (not yet invoiced).

    Returns:
        dict with keys: success, total, updated, skipped, message.
    """
    from django.db.models import Q
    from apps.bill_of_entry.models import BillOfEntryModel

    empty_product_boes = BillOfEntryModel.objects.filter(
        Q(Q(product_name__isnull=True) | Q(product_name="")) & Q(invoice_no__isnull=True)
    ).prefetch_related("item_details__sr_number__items")

    total_count = empty_product_boes.count()
    updated_count = 0
    skipped_count = 0

    for boe in empty_product_boes:
        generated_name = boe.generate_product_name_from_items()
        if generated_name:
            boe.product_name = generated_name
            boe.save(update_fields=["product_name"])
            updated_count += 1
        else:
            skipped_count += 1

    return {
        "success": True,
        "total": total_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "message": (
            f"Processed {total_count} BOEs: "
            f"{updated_count} updated, {skipped_count} skipped (no items found)"
        ),
    }


# ---------------------------------------------------------------------------
# Allotment-details fetch
# ---------------------------------------------------------------------------

def fetch_allotment_item_details(allotment_id: int, boe_id: int | None = None) -> dict[str, Any]:
    """
    Fetch allotment details (exchange_rate, product_name, port, company,
    item_details) for use in the BOE create/edit form.

    Items already present in the current BOE (identified by boe_id) are
    excluded to prevent duplicates when pulling from multiple allotments.

    Args:
        allotment_id: PK of the AllotmentModel to look up.
        boe_id:       PK of the BOE being edited, or None for a new BOE.

    Returns:
        dict suitable for a JSON response — no HttpResponse wrapping.

    Raises:
        AllotmentModel.DoesNotExist: propagated to the caller for 404/500 handling.
    """
    from apps.allotment.models import AllotmentModel
    from apps.bill_of_entry.models import BillOfEntryModel

    allotment = AllotmentModel.objects.select_related("company", "port").prefetch_related(
        "allotment_details__item__license__import_license",
        "allotment_details__item__hs_code",
    ).get(id=allotment_id)

    # Collect license-item IDs already attached to the BOE being edited
    existing_license_item_ids: set[int] = set()
    if boe_id:
        try:
            boe = BillOfEntryModel.objects.prefetch_related("item_details").get(id=boe_id)
            existing_license_item_ids = set(boe.item_details.values_list("sr_number_id", flat=True))
        except BillOfEntryModel.DoesNotExist:
            pass  # New BOE — no existing items

    exchange_rate = float(allotment.exchange_rate) if allotment.exchange_rate else 0.0

    item_details = []
    for allot_item in allotment.allotment_details.select_related("item__license", "item__hs_code").all():
        license_item = allot_item.item
        if not license_item:
            continue
        if license_item.id in existing_license_item_ids:
            continue

        cif_fc = float(allot_item.cif_fc) if allot_item.cif_fc else 0.0
        cif_inr = float(allot_item.cif_inr) if allot_item.cif_inr else (cif_fc * exchange_rate)

        # Fall back to license-item unit price when allotment has no CIF
        if cif_fc == 0.0 and license_item.unit_price and license_item.quantity:
            cif_fc = float(license_item.unit_price * license_item.quantity)
            cif_inr = cif_fc * exchange_rate

        item_details.append({
            "sr_number": license_item.id,
            "license_number": license_item.license.license_number if license_item.license else "",
            "item_description": license_item.description or "",
            "hs_code": license_item.hs_code.hs_code if license_item.hs_code else "",
            "qty": float(allot_item.qty) if allot_item.qty else (
                float(license_item.quantity) if license_item.quantity else 0.0
            ),
            "cif_fc": cif_fc,
            "cif_inr": cif_inr,
        })

    return {
        "exchange_rate": exchange_rate,
        "product_name": allotment.item_name or "",
        "port": allotment.port.id if allotment.port else None,
        "port_name": allotment.port.name if allotment.port else "",
        "company": allotment.company.id if allotment.company else None,
        "company_name": allotment.company.name if allotment.company else "",
        "item_details": item_details,
    }


# ---------------------------------------------------------------------------
# Dispute resolution
# ---------------------------------------------------------------------------

def resolve_dispute(boe) -> dict[str, Any]:
    """
    Clear the is_dispute flag on all RowDetails belonging to a BOE.

    Args:
        boe: BillOfEntryModel instance.

    Returns:
        dict with keys: success (True), cleared (int), message (str).
    """
    from apps.bill_of_entry.models import RowDetails

    cleared = RowDetails.objects.filter(bill_of_entry=boe, is_dispute=True).update(is_dispute=False)
    return {
        "success": True,
        "cleared": cleared,
        "message": f"Resolved {cleared} dispute row(s) on BOE {boe.bill_of_entry_number}",
    }


# ---------------------------------------------------------------------------
# BOE merge
# ---------------------------------------------------------------------------

def _parse_merge_source_id(source_boe_id) -> int:
    if source_boe_id in (None, "") or isinstance(source_boe_id, bool):
        raise ValueError("source_boe_id is required")
    try:
        return int(str(source_boe_id).strip())
    except (TypeError, ValueError):
        raise ValueError("source_boe_id must be an integer id")


def _choose_merge_survivor(requested_target, requested_source, frozen_row_ids) -> tuple[Any, Any, bool]:
    """D4 frozen priority: when exactly one BOE carries frozen (ledger) rows
    it survives, whatever the argument order.  Otherwise the requested target
    survives (existing rule).  Returns ``(survivor, removed, swapped)``."""
    target_frozen = bool(frozen_row_ids.get(requested_target.id))
    source_frozen = bool(frozen_row_ids.get(requested_source.id))
    if source_frozen and not target_frozen:
        return requested_source, requested_target, True
    return requested_target, requested_source, False


def _plan_merge_rows(survivor, removed) -> tuple[list[int], list[int], list[int]]:
    """Split the removed BOE's rows into ``(move, skip, skipped_frozen)``.

    A row whose (sr_number, transaction_type) already exists on the survivor
    (or on an earlier moved row) is skipped and cascade-deletes with the
    removed BOE — the existing rule.  Frozen rows are never deleted, so a
    skipped frozen row is reported separately and blocks the merge."""
    existing_combos = set(survivor.item_details.values_list("sr_number_id", "transaction_type"))
    move, skip, skipped_frozen = [], [], []
    rows = removed.item_details.order_by("id").values("id", "sr_number_id", "transaction_type", "is_frozen")
    for row in rows:
        combo = (row["sr_number_id"], row["transaction_type"])
        if combo not in existing_combos:
            move.append(row["id"])
            existing_combos.add(combo)
            continue
        skip.append(row["id"])
        if row["is_frozen"]:
            skipped_frozen.append(row["id"])
    return move, skip, skipped_frozen


def _reject_protected_duplicates(skipped_row_ids) -> None:
    # A skipped duplicate remains attached to the removed BOE and would
    # therefore be cascade-deleted with it.  Reconciliation annotations
    # deliberately protect their RowDetails FK, so reject the entire merge
    # *before* any row move, allotment transfer, or deletion (one bounded
    # query across all duplicate rows, not N+1 relation checks).
    from django.db.models import Q

    from apps.bill_of_entry.models import RowDetails

    if not skipped_row_ids:
        return
    protected_duplicates = list(
        RowDetails.objects.filter(id__in=skipped_row_ids)
        .filter(
            Q(invoice_allocations__isnull=False)
            | Q(allotment_allocations__isnull=False)
            | Q(external_invoice_links__isnull=False)
        )
        .values("id", "sr_number_id", "transaction_type")
        .distinct()
    )
    if protected_duplicates:
        row_ids = ", ".join(str(row["id"]) for row in protected_duplicates)
        raise ValueError(
            "BOE merge cannot be completed because duplicate source row(s) "
            f"{row_ids} are referenced by reconciliation/allocation records. "
            "Resolve those references before merging."
        )


def _merge_affected_targets(boe_ids, allotment_ids) -> tuple[list[int], list[int]]:
    """Every licence and licence import item whose stored balances a merge
    can change, captured BEFORE any mutation: the rows of both BOEs (moved,
    kept and cascade-deleted), the items allotted by the transferred
    allotments, and the items billed by trades linked to either BOE (the
    removed BOE's trade links go with it).  Returns sorted
    ``(license_ids, item_ids)``."""
    from apps.bill_of_entry.models import RowDetails
    from apps.license.models import LicenseImportItemsModel

    pairs = set(
        RowDetails.objects.filter(bill_of_entry_id__in=boe_ids)
        .values_list("sr_number_id", "sr_number__license_id")
    )
    if allotment_ids:
        pairs.update(
            LicenseImportItemsModel.objects.filter(allotment_details__allotment_id__in=allotment_ids)
            .values_list("id", "license_id")
        )
    pairs.update(
        LicenseImportItemsModel.objects.filter(trade_lines__trade__boes__id__in=boe_ids)
        .values_list("id", "license_id")
    )
    item_ids = sorted({item_id for item_id, _ in pairs if item_id})
    license_ids = sorted({license_id for _, license_id in pairs if license_id})
    return license_ids, item_ids


def _schedule_merge_refresh(license_ids, item_ids) -> None:
    """Refresh the stored balances of every affected licence and item after
    the merge commits, using only the existing refresh helpers
    (``update_license_flags`` via ``_refresh_licenses``; ``update_balance_values``
    via the RowDetails signal helper).  No balance math lives here."""
    from django.db import transaction

    from apps.bill_of_entry.models import _update_balance_sync

    def _job():
        # One guard per licence so a failure on one does not leave the others stale.
        for license_id in license_ids:
            try:
                _refresh_licenses([license_id])
            except Exception:
                logger.exception("BOE merge: licence balance refresh failed for %s", license_id)
        for item_id in item_ids:
            _update_balance_sync(item_id)

    transaction.on_commit(_job)


def _merge_audit_snapshot(boe) -> dict[str, Any]:
    """Header fields of the BOE that a merge deletes, kept in the audit log."""
    return {
        "id": boe.id,
        "bill_of_entry_number": boe.bill_of_entry_number,
        "bill_of_entry_date": boe.bill_of_entry_date.isoformat() if boe.bill_of_entry_date else None,
        "port_id": boe.port_id,
        "company_id": boe.company_id,
        "invoice_no": boe.invoice_no,
        "invoice_date": boe.invoice_date.isoformat() if boe.invoice_date else None,
        "product_name": boe.product_name,
        "exchange_rate": str(boe.exchange_rate),
        "boe_pdf_copy": boe.boe_pdf_copy.name if boe.boe_pdf_copy else None,
    }


def merge_boe(target_boe, source_boe_id: int, *, user=None) -> dict[str, Any]:
    """
    Merge two BOEs into one surviving BOE (owner decision D4).

    Survivor (frozen priority): when exactly one of the two BOEs carries
    ``RowDetails.is_frozen`` (ledger) rows it survives regardless of the
    argument order (``swapped=True`` when that is the requested source);
    otherwise the requested target survives.  Then:

    - RowDetails move from the removed BOE to the survivor; a row whose
      (sr_number, transaction_type) already exists on the survivor is
      skipped and cascade-deletes with the removed BOE (existing rule).
      Frozen rows are never deleted or edited: when a frozen row would be
      skipped (both BOEs frozen with an overlapping item), the merge is
      rejected.  Skipped rows protected by reconciliation records also
      reject the merge.
    - Allotments transfer to the survivor; the survivor takes the requested
      source's port (unchanged rule).
    - The survivor's exchange_rate is recomputed and persisted with the same
      helper the RowDetails signals use.
    - Exactly one ``ReconciliationLog`` (ACTION_MERGE_BOE) on the survivor.
    - Stored balances of every affected licence/item are refreshed on commit.

    Rejected: missing/invalid/same id, a BOE that no longer exists (an
    already-completed merge re-run cannot move rows twice), exactly one of
    the two BOEs genuinely hidden.

    Both BOE rows are locked (``select_for_update``, ordered by id to avoid
    deadlocks) inside one transaction before any read that drives a change.

    Returns:
        dict with: success, message, boe (serialized survivor), and the
        additive keys target_boe_id (survivor id) and swapped (bool).

    Raises:
        ValueError: on every rejection above (message says "not found" only
            when a BOE does not exist).
    """
    from django.db import transaction as db_transaction

    from apps.bill_of_entry.api.serializers import BillOfEntrySerializer
    from apps.bill_of_entry.models import (
        BillOfEntryModel, RowDetails, _recalculate_boe_exchange_rate, genuinely_hidden_boe_ids,
    )
    from apps.license.signals import suppress_boe_allotment_refresh
    from apps.reconciliation.models import ReconciliationLog

    source_id = _parse_merge_source_id(source_boe_id)
    requested_target_id = target_boe.id
    if requested_target_id == source_id:
        raise ValueError("Cannot merge a BOE with itself")
    if not BillOfEntryModel.objects.filter(id=source_id).exists():
        raise ValueError(f"Source BOE with id={source_id} not found")

    with db_transaction.atomic():
        locked = {
            boe.id: boe
            for boe in BillOfEntryModel.objects.select_for_update()
            .filter(id__in=[requested_target_id, source_id])
            .order_by("id")
        }
        if source_id not in locked:
            raise ValueError(f"Source BOE with id={source_id} not found")
        if requested_target_id not in locked:
            raise ValueError(f"Target BOE with id={requested_target_id} not found")
        requested_target = locked[requested_target_id]
        requested_source = locked[source_id]

        hidden_ids = genuinely_hidden_boe_ids(boe_ids=list(locked))
        if len(hidden_ids) == 1:
            raise ValueError(
                "BOE merge rejected: exactly one of the two bills of entry is hidden "
                "(previous-owner utilisation). Restore the hidden bill of entry or hide "
                "the other one before merging."
            )

        frozen_row_ids: dict[int, list[int]] = {}
        for boe_id, row_id in (
            RowDetails.objects.filter(bill_of_entry_id__in=list(locked), is_frozen=True)
            .order_by("id").values_list("bill_of_entry_id", "id")
        ):
            frozen_row_ids.setdefault(boe_id, []).append(row_id)
        survivor, removed, swapped = _choose_merge_survivor(requested_target, requested_source, frozen_row_ids)
        if removed.license_trades.exists() or removed.invoices.exists():
            # Deleting a BOE drops its trade links and cascades its invoices;
            # never drop them silently, in either merge direction.
            reason = (
                f"it carries frozen ledger rows, so bill of entry {survivor.id} must survive, but "
                if swapped else ""
            )
            raise ValueError(
                f"BOE merge rejected: bill of entry {removed.id} would be removed ({reason}"
                f"it is linked to trades/invoices that would be lost). "
                "Move those links first."
            )

        rows_to_move, skipped_row_ids, skipped_frozen = _plan_merge_rows(survivor, removed)
        if skipped_frozen:
            raise ValueError(
                "BOE merge rejected: both bills of entry carry frozen ledger rows for the "
                f"same item(s); frozen row(s) {', '.join(map(str, skipped_frozen))} would be "
                "deleted. Frozen rows cannot be merged away."
            )
        _reject_protected_duplicates(skipped_row_ids)

        removed_allotment_ids = list(removed.allotment.values_list("id", flat=True))
        license_ids, item_ids = _merge_affected_targets(list(locked), removed_allotment_ids)
        port_id = requested_source.port_id
        removed_snapshot = _merge_audit_snapshot(removed)
        removed_id = removed.id

        # Queryset .update() bypasses RowDetails.save()'s frozen-row guard on
        # purpose: only the BOE FK is reassigned, never values or ids.
        moved_count = RowDetails.objects.filter(id__in=rows_to_move).update(bill_of_entry=survivor)
        # Merge schedules its own refresh below; keep the M2M / delete
        # handlers from refreshing the same targets a second time.
        with suppress_boe_allotment_refresh():
            if removed_allotment_ids:
                survivor.allotment.add(*removed_allotment_ids)

            # Frees the (number, date) constraint; skipped rows cascade-delete.
            removed.delete()

        survivor.port_id = port_id
        survivor.save(update_fields=["port"])
        _recalculate_boe_exchange_rate(survivor.id, force=True)
        survivor.refresh_from_db(fields=["exchange_rate"])

        message = (
            f"Merged successfully. {moved_count} item(s) moved, "
            f"{len(skipped_row_ids)} skipped (duplicate)."
        )
        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_MERGE_BOE,
            bill_of_entry=survivor,
            before={
                "target_boe_id": requested_target_id,
                "source_boe_id": source_id,
                "surviving_boe_id": survivor.id,
                "removed_boe_id": removed_id,
                "swapped": swapped,
                "frozen_row_ids": {str(k): v for k, v in frozen_row_ids.items()},
                "removed_boe": removed_snapshot,
            },
            after={
                "message": message,
                "target_boe_id": survivor.id,
                "swapped": swapped,
                "moved_row_ids": rows_to_move,
                "skipped_row_ids": skipped_row_ids,
                "transferred_allotment_ids": removed_allotment_ids,
                "exchange_rate": str(survivor.exchange_rate),
                "refreshed_license_ids": license_ids,
                "refreshed_item_ids": item_ids,
            },
            user=user if getattr(user, "is_authenticated", False) else None,
        )
        _schedule_merge_refresh(license_ids, item_ids)

    refreshed = BillOfEntryModel.objects.select_related(
        "company", "port"
    ).prefetch_related("item_details").get(id=survivor.id)
    serializer = BillOfEntrySerializer(refreshed)
    return {
        "success": True,
        "message": message,
        "boe": serializer.data,
        "target_boe_id": survivor.id,
        "swapped": swapped,
    }


# ---------------------------------------------------------------------------
# Invoice-number update
# ---------------------------------------------------------------------------

HIDDEN_INVOICE_NO_MESSAGE = (
    "This bill of entry is hidden; its invoice number cannot be changed here. "
    "Restore the bill of entry (restore-boe) first."
)


def update_invoice_no(boe, invoice_no: str) -> dict[str, Any]:
    """
    Update only the invoice_no field on a BOE.

    Owner decision D1: on a GENUINELY hidden BOE (``genuinely_hidden_boe_ids``)
    a change is rejected — hiding/un-hiding must go through ``hide_boe`` /
    ``restore_boe`` so the HIDE_BOE/RESTORE_BOE audit and the licence refresh
    happen.  Re-sending the unchanged value is a no-op success.  A legacy
    free-text ``'OTH'`` on a never-hidden BOE stays editable.

    Args:
        boe:        BillOfEntryModel instance.
        invoice_no: New invoice number string (may be empty to clear).

    Returns:
        dict with: id, invoice_no, message.

    Raises:
        ValueError: the BOE is genuinely hidden and the value would change.
    """
    from django.db import transaction

    from apps.bill_of_entry.models import BillOfEntryModel, genuinely_hidden_boe_ids

    if invoice_no is not None and not isinstance(invoice_no, str):
        raise ValueError("invoice_no must be a string")
    invoice_no = (invoice_no or "").strip()
    with transaction.atomic():
        locked = BillOfEntryModel.objects.select_for_update().only("id", "invoice_no").get(pk=boe.pk)
        if locked.id in genuinely_hidden_boe_ids(boe_ids=[locked.id]):
            if invoice_no == (locked.invoice_no or ""):
                boe.invoice_no = locked.invoice_no
                return {
                    "id": boe.id,
                    "invoice_no": boe.invoice_no,
                    "message": "Invoice number unchanged",
                }
            raise ValueError(HIDDEN_INVOICE_NO_MESSAGE)
        boe.invoice_no = invoice_no
        boe.save(update_fields=["invoice_no"])
    return {
        "id": boe.id,
        "invoice_no": boe.invoice_no,
        "message": "Invoice number updated",
    }


# ---------------------------------------------------------------------------
# Hidden BOEs (previous-owner utilisation)
# ---------------------------------------------------------------------------
#
# `BillOfEntryModel.invoice_no == OTH_INVOICE_MARKER` marks a BOE as
# belonging to a previous licence owner — excluded from every balance/
# financial calculation (see `apps.license.services.balance_calculator.
# exclude_hidden` and every call site listed in its docstring) but
# permanently retained and visible in the Customs History audit view
# (`build_customs_ledger`'s `show_hidden` param). Reuses the existing
# `invoice_no` field rather than a new column — deliberately BOE-level, not
# scoped to a licence: hiding a BOE marks it hidden for EVERY licence it
# touches, by design — a BOE legitimately belonging to multiple licences
# is expected, and hide/restore always applies uniformly across all of
# them (every touched licence is recomputed — see `_refresh_licenses`).
# There is deliberately NO validation anywhere in this module that refuses
# or blocks hide/restore based on how many licences a BOE spans.


def _username(user) -> str | None:
    if not user:
        return None
    return getattr(user, "get_username", lambda: None)() or getattr(user, "username", None)


def _licenses_touched_by(boe) -> list[int]:
    from apps.bill_of_entry.models import RowDetails

    return list(
        RowDetails.objects.filter(bill_of_entry=boe)
        .values_list("sr_number__license_id", flat=True)
        .distinct()
    )


def _apply_hide(boe, user, reason: str) -> tuple[list[int], str | None]:
    """
    The actual mutation + audit log for hiding ONE BOE — factored out of
    `hide_boe` so `hide_boes_bulk` can call it per-item and defer
    `update_license_flags` until every item in a batch has been mutated
    (one recompute per affected licence, not one per BOE — see
    `hide_boes_bulk`'s docstring). Does NOT call `update_license_flags`
    itself; the caller is responsible for that.

    Applies regardless of how many licences this BOE spans (see module
    docstring) — every one of them ends up in the returned `license_ids`
    and gets recomputed by the caller.

    Returns `(license_ids, previous_invoice_no)`.
    """
    from django.db import transaction

    from apps.bill_of_entry.models import OTH_INVOICE_MARKER, genuinely_hidden_boe_ids
    from apps.reconciliation.models import ReconciliationLog

    license_ids = _licenses_touched_by(boe)

    previous_invoice_no = boe.invoice_no
    # D6: hidden state comes from the audit history, never from the raw
    # 'OTH' text — a legacy free-text 'OTH' invoice is recorded as
    # not-hidden, so `_apply_restore` can give it back verbatim.
    was_hidden = boe.id in genuinely_hidden_boe_ids(boe_ids=[boe.id])

    with transaction.atomic():
        boe.invoice_no = OTH_INVOICE_MARKER
        boe.save(update_fields=["invoice_no"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_HIDE_BOE,
            bill_of_entry=boe,
            license_item=None,
            reason=reason,
            user=user,
            # `invoice_no` here is the ONLY place the pre-hide value is
            # preserved (no dedicated column) — `restore_boe`/`_apply_
            # restore` read it back from the most recent HIDE_BOE log row
            # for this BOE.
            before={"is_hidden": was_hidden, "invoice_no": previous_invoice_no},
            after={"is_hidden": True, "bill_of_entry_number": boe.bill_of_entry_number},
        )

    return license_ids, previous_invoice_no


def _preserved_invoice_no(boe) -> str | None:
    """The invoice_no to give back on restore (D6).

    Reads the FIRST ``HIDE_BOE`` log of the current hidden episode (every
    HIDE_BOE after the latest RESTORE_BOE): a repeated hide of an already
    hidden BOE records ``'OTH'`` as its "previous" value and must not mask
    the real pre-hide invoice.  A preserved ``'OTH'`` is returned only when
    that log states the BOE was NOT hidden at the time (a legitimate legacy
    'OTH' invoice); otherwise it is ambiguous and ``None`` is returned, as
    before.
    """
    from apps.bill_of_entry.models import OTH_INVOICE_MARKER
    from apps.reconciliation.models import ReconciliationLog

    logs = (
        ReconciliationLog.objects
        .filter(
            bill_of_entry=boe,
            action__in=[ReconciliationLog.ACTION_HIDE_BOE, ReconciliationLog.ACTION_RESTORE_BOE],
        )
        .order_by("-created_on", "-id")
        .values_list("action", "before")
    )
    episode_start = None
    first_ever = True  # no RESTORE_BOE precedes the episode: it is the BOE's first audit log
    for action, before in logs:
        if action == ReconciliationLog.ACTION_RESTORE_BOE:
            first_ever = False
            break
        episode_start = before
    if not isinstance(episode_start, dict):
        return None
    preserved = episode_start.get("invoice_no")
    if not preserved:
        return None
    if (
        preserved == OTH_INVOICE_MARKER
        and episode_start.get("is_hidden") is not False
        and not first_ever
    ):
        return None
    return preserved


def _apply_restore(boe, user, reason: str, *, hidden_ids=None) -> tuple[list[int], str | None] | None:
    """
    The actual mutation + audit log for restoring ONE BOE — factored out
    of `restore_boe` so `restore_boes_bulk` can call it per-item and defer
    `update_license_flags` (see `_apply_hide`'s docstring for the same
    reasoning). Returns `None` (no-op) unless the BOE is GENUINELY hidden
    (`genuinely_hidden_boe_ids`, owner decision D6) — a never-hidden BOE
    whose invoice text happens to be 'OTH' is left untouched. Does NOT call
    `update_license_flags` itself.

    Args:
        hidden_ids: optional pre-computed `genuinely_hidden_boe_ids` result
            (the bulk path computes it once for the whole batch).

    Returns `(license_ids, restored_invoice_no)` or `None`.
    """
    from django.db import transaction

    from apps.bill_of_entry.models import OTH_INVOICE_MARKER, genuinely_hidden_boe_ids
    from apps.reconciliation.models import ReconciliationLog

    if hidden_ids is None:
        hidden_ids = genuinely_hidden_boe_ids(boe_ids=[boe.id])
    if boe.id not in hidden_ids:
        return None

    license_ids = _licenses_touched_by(boe)
    restored_invoice_no = _preserved_invoice_no(boe)

    with transaction.atomic():
        boe.invoice_no = restored_invoice_no
        boe.save(update_fields=["invoice_no"])

        ReconciliationLog.objects.create(
            action=ReconciliationLog.ACTION_RESTORE_BOE,
            bill_of_entry=boe,
            license_item=None,
            reason=reason,
            user=user,
            before={"is_hidden": True, "invoice_no": OTH_INVOICE_MARKER},
            after={
                "is_hidden": False,
                "invoice_no": restored_invoice_no,
                "bill_of_entry_number": boe.bill_of_entry_number,
            },
        )

    return license_ids, restored_invoice_no


def _refresh_licenses(license_ids) -> None:
    """Calls `update_license_flags` once per id — shared by the single-item
    and bulk hide/restore paths so the recompute-on-toggle requirement
    (see `_apply_hide`'s docstring) is expressed in exactly one place."""
    from apps.license.models import LicenseDetailsModel
    from apps.license.signals import update_license_flags

    for touched_license in LicenseDetailsModel.objects.filter(pk__in=license_ids):
        update_license_flags(touched_license)


def hide_boe(boe, user, reason: str = "") -> dict[str, Any]:
    """
    Marks `boe` as belonging to a previous licence owner by setting
    `invoice_no = OTH_INVOICE_MARKER` — BOE-level, not licence-scoped (see
    module docstring). The 3-case business rule (by `boe.invoice_no`'s
    CURRENT value, checked by the caller — see `restore_boe` for the
    inverse):
      1. blank/null -> single-click, no confirmation needed. Nothing to
         preserve.
      2. already `OTH_INVOICE_MARKER` -> idempotent no-op (still logs the
         repeated action); no confirmation needed either.
      3. any other real value -> the CALLER (the view/frontend) is
         responsible for confirming with the user first ("this will
         replace Invoice X with OTH, restored automatically on unhide");
         this function itself never blocks on that value — it always
         preserves it (see `_apply_hide`) so `restore_boe` can put it back
         exactly.

    Applies uniformly no matter how many licences this BOE's `RowDetails`
    span — see module docstring; there is no validation here that blocks
    or refuses based on that count.

    Args:
        boe: BillOfEntryModel instance.
        user: acting User for the audit fields (may be None).
        reason: free-text reason, stored on the `ReconciliationLog` entry.

    Returns:
        dict with: id (boe id), is_hidden (True), invoice_no,
        previous_invoice_no (what was preserved, if anything), hidden_by
        (username or None), hidden_at (ISO datetime string).
    """
    from django.utils import timezone

    reason = (reason or "").strip()
    now = timezone.now()

    license_ids, previous_invoice_no = _apply_hide(boe, user, reason)
    _refresh_licenses(license_ids)

    return {
        "id": boe.id,
        "is_hidden": True,
        "invoice_no": boe.invoice_no,
        "previous_invoice_no": previous_invoice_no,
        "hidden_by": _username(user),
        "hidden_at": now.isoformat(),
    }


def restore_boe(boe, user, reason: str = "") -> dict[str, Any]:
    """
    Un-hides `boe`: only acts when the BOE is GENUINELY hidden
    (`genuinely_hidden_boe_ids` — D6; an already-visible BOE, including one
    with a legitimate legacy 'OTH' invoice, is left untouched).
    Restores `invoice_no` to whatever it was immediately before the most
    recent `hide_boe` call — see `_apply_restore`'s docstring for where
    that's read back from, falling back to blank/`None` if no such log row
    exists (e.g. a BOE hidden before this preserve-on-hide behaviour
    existed).

    Args:
        boe: BillOfEntryModel instance.
        user: acting User for the audit fields (may be None).
        reason: free-text reason, stored on the `ReconciliationLog` entry.

    Returns:
        dict with: id (boe id), is_hidden (False), invoice_no (the
        restored value), restored_by (username or None), restored_at (ISO
        datetime string, or None if the BOE was not hidden to begin with).
    """
    from django.utils import timezone

    reason = (reason or "").strip()
    now = timezone.now()

    result = _apply_restore(boe, user, reason)
    if result is None:
        return {
            "id": boe.id, "is_hidden": False, "invoice_no": boe.invoice_no,
            "restored_by": _username(user), "restored_at": None,
        }
    license_ids, restored_invoice_no = result
    _refresh_licenses(license_ids)

    return {
        "id": boe.id,
        "is_hidden": False,
        "invoice_no": restored_invoice_no,
        "restored_by": _username(user),
        "restored_at": now.isoformat(),
    }


def _normalise_boe_ids(boe_ids) -> tuple[list[int], list[Any]]:
    """Normalise a client-supplied id list for the bulk hide/restore paths.

    Returns ``(ids, unparseable)``: ``ids`` are the ints (``int`` or numeric
    ``str`` input) de-duplicated in first-seen order; ``unparseable`` keeps
    the raw values that are not a whole-number id (bools, floats, ``None``,
    non-numeric strings, ...) so the caller can report them as failed.
    """
    ids: list[int] = []
    seen: set[int] = set()
    unparseable: list[Any] = []
    for raw in boe_ids:
        value = None
        if isinstance(raw, int) and not isinstance(raw, bool):
            value = raw
        elif isinstance(raw, str):
            try:
                value = int(raw.strip())
            except ValueError:
                value = None
        if value is None:
            unparseable.append(raw)
            continue
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids, unparseable


def hide_boes_bulk(boe_ids, user, reason: str = "") -> dict[str, Any]:
    """
    Bulk sibling of `hide_boe` — processes every id in `boe_ids`
    independently (an unknown id doesn't block the rest — see `failed`
    below), but recomputes each AFFECTED LICENCE only ONCE at the end
    regardless of how many selected BOEs touch it — a genuine batch, not N
    sequential calls to `hide_boe` (which would call `update_license_flags`
    once per BOE per licence). No BOE is ever skipped or refused for
    spanning multiple licences — see module docstring.

    Args:
        boe_ids: iterable of `BillOfEntryModel` pks (ints or numeric strings;
            normalised to ints and de-duplicated in order — see
            `_normalise_boe_ids`; unparseable values are reported in `failed`).
        user: acting User for the audit fields (may be None).
        reason: free-text reason, stored on every affected `ReconciliationLog` entry.

    Returns:
        dict with: hidden (list of per-BOE result dicts, same shape as
        `hide_boe`'s return), failed (list of `{id, error}` — only for ids
        that don't resolve to a real BOE), licenses_refreshed (list of
        licence ids recomputed once).
    """
    from django.utils import timezone

    from apps.bill_of_entry.models import BillOfEntryModel

    reason = (reason or "").strip()
    now = timezone.now()

    boe_ids, unparseable = _normalise_boe_ids(boe_ids)
    boes = {boe.id: boe for boe in BillOfEntryModel.objects.filter(pk__in=boe_ids)}
    hidden: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = [
        {"id": raw, "error": "No BOE matches that id."} for raw in unparseable
    ]
    all_license_ids: set[int] = set()

    for boe_id in boe_ids:
        boe = boes.get(boe_id)
        if boe is None:
            failed.append({"id": boe_id, "error": "No BOE matches that id."})
            continue
        license_ids, previous_invoice_no = _apply_hide(boe, user, reason)
        all_license_ids.update(license_ids)
        hidden.append({
            "id": boe.id, "is_hidden": True, "invoice_no": boe.invoice_no,
            "previous_invoice_no": previous_invoice_no,
        })

    _refresh_licenses(all_license_ids)

    return {
        "hidden": hidden,
        "failed": failed,
        "licenses_refreshed": sorted(all_license_ids),
        "hidden_by": _username(user),
        "hidden_at": now.isoformat(),
    }


def restore_boes_bulk(boe_ids, user, reason: str = "") -> dict[str, Any]:
    """Bulk sibling of `restore_boe` — same per-item processing / once-per-
    licence-recompute shape as `hide_boes_bulk`. A BOE that isn't currently
    genuinely hidden (D6) is simply skipped (not an error, same as
    `restore_boe`'s own no-op case)."""
    from django.utils import timezone

    from apps.bill_of_entry.models import BillOfEntryModel, genuinely_hidden_boe_ids

    reason = (reason or "").strip()
    now = timezone.now()

    boe_ids, unparseable = _normalise_boe_ids(boe_ids)
    boes = {boe.id: boe for boe in BillOfEntryModel.objects.filter(pk__in=boe_ids)}
    hidden_ids = genuinely_hidden_boe_ids(boe_ids=list(boes))
    restored: list[dict[str, Any]] = []
    skipped: list[int] = []
    failed: list[dict[str, Any]] = [
        {"id": raw, "error": "No BOE matches that id."} for raw in unparseable
    ]
    all_license_ids: set[int] = set()

    for boe_id in boe_ids:
        boe = boes.get(boe_id)
        if boe is None:
            failed.append({"id": boe_id, "error": "No BOE matches that id."})
            continue
        result = _apply_restore(boe, user, reason, hidden_ids=hidden_ids)
        if result is None:
            skipped.append(boe_id)
            continue
        license_ids, restored_invoice_no = result
        all_license_ids.update(license_ids)
        restored.append({"id": boe.id, "is_hidden": False, "invoice_no": restored_invoice_no})

    _refresh_licenses(all_license_ids)

    return {
        "restored": restored,
        "skipped": skipped,
        "failed": failed,
        "licenses_refreshed": sorted(all_license_ids),
        "restored_by": _username(user),
        "restored_at": now.isoformat(),
    }
