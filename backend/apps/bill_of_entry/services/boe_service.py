"""
boe_service.py — domain logic for the Bill of Entry app.

All functions accept model instances, dicts, and primitives.
No DRF Request objects enter this module.
Raises ValueError for invalid domain operations.
"""
from __future__ import annotations

from typing import Any


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

def merge_boe(target_boe, source_boe_id: int) -> dict[str, Any]:
    """
    Merge a source BOE into target_boe.

    - Moves RowDetails from source to target (skips duplicate sr_number+transaction_type)
    - Transfers allotments from source to target
    - Updates target's port to source's port
    - Deletes source BOE

    The merge runs inside a single DB transaction.

    Args:
        target_boe:    BillOfEntryModel instance (the merge destination).
        source_boe_id: PK of the BOE to merge from (will be deleted).

    Returns:
        dict with: success, message, boe (serialized target).

    Raises:
        ValueError: When source_boe_id is not provided, source == target, or source not found.
    """
    from django.db import transaction as db_transaction
    from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
    from apps.bill_of_entry.serializers import BillOfEntrySerializer

    if not source_boe_id:
        raise ValueError("source_boe_id is required")

    try:
        source_boe = BillOfEntryModel.objects.prefetch_related(
            "item_details", "allotment"
        ).get(id=source_boe_id)
    except BillOfEntryModel.DoesNotExist:
        raise ValueError(f"Source BOE with id={source_boe_id} not found")

    if target_boe.id == source_boe.id:
        raise ValueError("Cannot merge a BOE with itself")

    with db_transaction.atomic():
        # Find combos already in target to avoid unique-constraint violations
        existing_combos = set(
            target_boe.item_details.values_list("sr_number_id", "transaction_type")
        )

        rows_to_move = []
        skipped_count = 0
        for row in source_boe.item_details.values("id", "sr_number_id", "transaction_type"):
            combo = (row["sr_number_id"], row["transaction_type"])
            if combo not in existing_combos:
                rows_to_move.append(row["id"])
                existing_combos.add(combo)
            else:
                skipped_count += 1

        # Use queryset .update() to bypass RowDetails.save() frozen-row guard —
        # we are only reassigning the BOE FK, not editing financial data.
        moved_count = RowDetails.objects.filter(id__in=rows_to_move).update(bill_of_entry=target_boe)

        # Transfer allotments
        for allotment in source_boe.allotment.all():
            target_boe.allotment.add(allotment)

        source_port = source_boe.port

        # Delete source BOE (frees unique constraint; unmoved rows cascade-delete)
        source_boe.delete()

        # Update target port to the correct port from source
        target_boe.port = source_port
        target_boe.save(update_fields=["port"])

    refreshed = BillOfEntryModel.objects.select_related(
        "company", "port"
    ).prefetch_related("item_details").get(id=target_boe.id)
    serializer = BillOfEntrySerializer(refreshed)
    return {
        "success": True,
        "message": (
            f"Merged successfully. {moved_count} item(s) moved, "
            f"{skipped_count} skipped (duplicate)."
        ),
        "boe": serializer.data,
    }


# ---------------------------------------------------------------------------
# Invoice-number update
# ---------------------------------------------------------------------------

def update_invoice_no(boe, invoice_no: str) -> dict[str, Any]:
    """
    Update only the invoice_no field on a BOE.

    Args:
        boe:        BillOfEntryModel instance.
        invoice_no: New invoice number string (may be empty to clear).

    Returns:
        dict with: id, invoice_no, message.
    """
    invoice_no = (invoice_no or "").strip()
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
# touches.
#
# `CrossLicenseBoeError` is a safety guard, not part of the product spec: a
# single physical BOE can span multiple licences (`BillOfEntryModel.
# get_licenses`) — 161 such BOEs exist in this app's data, one spanning 13
# licences. Hiding one for a "previous owner" reason on licence A would
# silently zero out its debit against unrelated licences B, C, D... too,
# with no compensating credit. Hiding is refused when this would happen;
# remove this guard if that blast radius is actually intended.


class CrossLicenseBoeError(ValueError):
    """Raised when hide/restore would affect a BOE that spans more than
    one licence — see the module-level note above `hide_boe`."""


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

    Raises `CrossLicenseBoeError` if this BOE spans more than one licence
    — see module docstring.

    Returns `(license_ids, previous_invoice_no)`.
    """
    from django.db import transaction

    from apps.bill_of_entry.models import OTH_INVOICE_MARKER
    from apps.reconciliation.models import ReconciliationLog

    license_ids = _licenses_touched_by(boe)
    if len(license_ids) > 1:
        raise CrossLicenseBoeError(
            f"BOE {boe.bill_of_entry_number} spans {len(license_ids)} licences — "
            "hiding it would affect all of them. Refused."
        )

    previous_invoice_no = boe.invoice_no
    was_hidden = previous_invoice_no == OTH_INVOICE_MARKER

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


def _apply_restore(boe, user, reason: str) -> tuple[list[int], str | None] | None:
    """
    The actual mutation + audit log for restoring ONE BOE — factored out
    of `restore_boe` so `restore_boes_bulk` can call it per-item and defer
    `update_license_flags` (see `_apply_hide`'s docstring for the same
    reasoning). Returns `None` (no-op) if `boe.invoice_no` isn't currently
    `OTH_INVOICE_MARKER`. Does NOT call `update_license_flags` itself.

    Returns `(license_ids, restored_invoice_no)` or `None`.
    """
    from django.db import transaction

    from apps.bill_of_entry.models import OTH_INVOICE_MARKER
    from apps.reconciliation.models import ReconciliationLog

    if boe.invoice_no != OTH_INVOICE_MARKER:
        return None

    license_ids = _licenses_touched_by(boe)

    last_hide = (
        ReconciliationLog.objects
        .filter(bill_of_entry=boe, action=ReconciliationLog.ACTION_HIDE_BOE)
        .order_by("-created_on")
        .first()
    )
    restored_invoice_no = None
    if last_hide and isinstance(last_hide.before, dict):
        preserved = last_hide.before.get("invoice_no")
        if preserved and preserved != OTH_INVOICE_MARKER:
            restored_invoice_no = preserved

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

    Refuses (raises `CrossLicenseBoeError`) if this BOE's `RowDetails` span
    more than one licence — see module docstring.

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
    Un-hides `boe`: only acts when `invoice_no` currently equals
    `OTH_INVOICE_MARKER` (an already-visible BOE is left untouched).
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


def hide_boes_bulk(boe_ids, user, reason: str = "") -> dict[str, Any]:
    """
    Bulk sibling of `hide_boe` — processes every id in `boe_ids`
    independently (one bad BOE, e.g. a `CrossLicenseBoeError`, does not
    roll back the others; see module docstring for that guard), but
    recomputes each AFFECTED LICENCE only ONCE at the end regardless of
    how many selected BOEs touch it — a genuine batch, not N sequential
    calls to `hide_boe` (which would call `update_license_flags` once per
    BOE per licence).

    Args:
        boe_ids: iterable of `BillOfEntryModel` pks.
        user: acting User for the audit fields (may be None).
        reason: free-text reason, stored on every affected `ReconciliationLog` entry.

    Returns:
        dict with: hidden (list of per-BOE result dicts, same shape as
        `hide_boe`'s return), failed (list of `{id, error}`),
        licenses_refreshed (list of licence ids recomputed once).
    """
    from django.utils import timezone

    from apps.bill_of_entry.models import BillOfEntryModel

    reason = (reason or "").strip()
    now = timezone.now()

    boes = {boe.id: boe for boe in BillOfEntryModel.objects.filter(pk__in=list(boe_ids))}
    hidden: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    all_license_ids: set[int] = set()

    for boe_id in boe_ids:
        boe = boes.get(boe_id)
        if boe is None:
            failed.append({"id": boe_id, "error": "No BOE matches that id."})
            continue
        try:
            license_ids, previous_invoice_no = _apply_hide(boe, user, reason)
        except CrossLicenseBoeError as exc:
            failed.append({"id": boe_id, "error": str(exc)})
            continue
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
    hidden is simply skipped (not an error, same as `restore_boe`'s own
    no-op case)."""
    from django.utils import timezone

    from apps.bill_of_entry.models import BillOfEntryModel

    reason = (reason or "").strip()
    now = timezone.now()

    boes = {boe.id: boe for boe in BillOfEntryModel.objects.filter(pk__in=list(boe_ids))}
    restored: list[dict[str, Any]] = []
    skipped: list[int] = []
    failed: list[dict[str, Any]] = []
    all_license_ids: set[int] = set()

    for boe_id in boe_ids:
        boe = boes.get(boe_id)
        if boe is None:
            failed.append({"id": boe_id, "error": "No BOE matches that id."})
            continue
        result = _apply_restore(boe, user, reason)
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
