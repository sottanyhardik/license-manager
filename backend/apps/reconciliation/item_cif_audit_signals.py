"""
DEC-50 audit, F3 owner decision (2026-11-20): record every change of the
computed item CIF adjustment set AUTOMATICALLY when its inputs change.

Inputs of `compute_item_cif_adjustments` are: visible BOE DEBIT rows, import
item CIF, allotment items (qty/CIF/status), allotment type, formal
`BOEAllotmentAllocation`s, the BOE↔allotment M2M and BOE hide/restore. A change
to any of them marks the affected licence(s); one flush per transaction runs
after commit and calls `refresh_item_cif_adjustment_log` (its own atomic block,
append-only, writes only when the set changed) once per licence.

Never raises into the caller's save path (errors are logged). `bulk_create` /
`QuerySet.update` bypass signals: `manage.py refresh_item_cif_adjustments`
(dry run) reports any licence whose recorded set differs from the live one.
Disable with `settings.ITEM_CIF_ADJUSTMENT_AUDIT_ON_CHANGE = False`.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails

logger = logging.getLogger(__name__)

_STATE_ATTR = "_item_cif_audit_state"


def _enabled() -> bool:
    return getattr(settings, "ITEM_CIF_ADJUSTMENT_AUDIT_ON_CHANGE", True)


def _refresh(license_ids) -> None:
    if not license_ids:
        return
    try:
        from apps.reconciliation.services.item_cif_adjustment_log import refresh_item_cif_adjustment_log

        refresh_item_cif_adjustment_log(sorted(license_ids), dry_run=False)
    except Exception:  # noqa: BLE001 - post-commit; never break the request
        logger.exception("DEC-50 adjustment audit refresh failed for licences %s", sorted(license_ids))


class _FlushState:
    """One per transaction: the queued on_commit callable and its licences."""

    def __init__(self):
        self.pending: set = set()
        self.done = False

        def _flush():
            self.done = True
            _refresh(self.pending)

        self.callback = _flush


def _active_state():
    state = getattr(connection, _STATE_ATTR, None)
    if state is None or state.done:
        return None
    # Django drops on_commit callbacks on rollback: a state whose callback is no
    # longer queued belongs to a rolled-back transaction.
    if not any(entry[1] is state.callback for entry in connection.run_on_commit):
        return None
    return state


def mark_licences(license_ids) -> None:
    """Queue licences for one post-commit audit refresh per transaction."""
    ids = {i for i in license_ids if i}
    if not ids or not _enabled():
        return
    if not connection.in_atomic_block:
        _refresh(ids)  # autocommit: the change is already committed
        return
    state = _active_state()
    if state is None:
        state = _FlushState()
        setattr(connection, _STATE_ATTR, state)
        transaction.on_commit(state.callback)
    state.pending |= ids


def _safe(fn):
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception:  # noqa: BLE001
            logger.exception("DEC-50 audit signal failed")
    wrapper.__name__ = fn.__name__
    return wrapper


def _allotment_licences(allotment_ids) -> set:
    from django.apps import apps as django_apps

    AllotmentItems = django_apps.get_model("allotment", "AllotmentItems")
    return set(AllotmentItems.objects.filter(allotment_id__in=list(allotment_ids)).values_list("item__license_id", flat=True))


def _boe_licences(boe_ids) -> set:
    return set(RowDetails.objects.filter(bill_of_entry_id__in=list(boe_ids)).values_list("sr_number__license_id", flat=True))


@receiver(post_save, sender=RowDetails, dispatch_uid="dec50_audit_rowdetails_save")
@receiver(post_delete, sender=RowDetails, dispatch_uid="dec50_audit_rowdetails_delete")
@_safe
def _on_row(sender, instance, raw=False, **kwargs):
    if raw:
        return
    item_id = instance.sr_number_id
    if item_id:
        from apps.license.models import LicenseImportItemsModel

        mark_licences(LicenseImportItemsModel.objects.filter(pk=item_id).values_list("license_id", flat=True))


@receiver(post_save, sender="license.LicenseImportItemsModel", dispatch_uid="dec50_audit_import_item_save")
@_safe
def _on_import_item(sender, instance, raw=False, **kwargs):
    if not raw:
        mark_licences([instance.license_id])


@receiver(post_save, sender="allotment.AllotmentItems", dispatch_uid="dec50_audit_allotment_item_save")
@receiver(post_delete, sender="allotment.AllotmentItems", dispatch_uid="dec50_audit_allotment_item_delete")
@_safe
def _on_allotment_item(sender, instance, raw=False, **kwargs):
    if raw or not instance.item_id:
        return
    from apps.license.models import LicenseImportItemsModel

    mark_licences(LicenseImportItemsModel.objects.filter(pk=instance.item_id).values_list("license_id", flat=True))


@receiver(post_save, sender="allotment.AllotmentModel", dispatch_uid="dec50_audit_allotment_save")
@_safe
def _on_allotment(sender, instance, raw=False, created=False, **kwargs):
    if not raw and not created:
        mark_licences(_allotment_licences([instance.pk]))


@receiver(post_save, sender="reconciliation.BOEAllotmentAllocation", dispatch_uid="dec50_audit_allocation_save")
@_safe
def _on_allocation(sender, instance, raw=False, **kwargs):
    if raw:
        return
    ids = set()
    if instance.allotment_item_id:
        from django.apps import apps as django_apps

        AllotmentItems = django_apps.get_model("allotment", "AllotmentItems")
        ids |= set(AllotmentItems.objects.filter(pk=instance.allotment_item_id).values_list("item__license_id", flat=True))
    if instance.row_details_id:
        ids |= set(RowDetails.objects.filter(pk=instance.row_details_id).values_list("sr_number__license_id", flat=True))
    mark_licences(ids)


@receiver(m2m_changed, sender=BillOfEntryModel.allotment.through, dispatch_uid="dec50_audit_boe_allotment_m2m")
@_safe
def _on_boe_allotment_link(sender, instance, action, reverse, pk_set, **kwargs):
    if action not in ("post_add", "post_remove", "pre_clear", "post_clear"):
        return
    if reverse:  # instance is an AllotmentModel, pk_set are BOE ids
        ids = _allotment_licences([instance.pk]) | _boe_licences(pk_set or [])
    else:  # instance is a BOE, pk_set are allotment ids
        ids = _boe_licences([instance.pk]) | _allotment_licences(pk_set or [])
        if action == "pre_clear":
            ids |= _allotment_licences(instance.allotment.values_list("pk", flat=True))
    mark_licences(ids)


@receiver(post_save, sender="reconciliation.ReconciliationLog", dispatch_uid="dec50_audit_hide_restore")
@_safe
def _on_hide_restore(sender, instance, created=False, raw=False, **kwargs):
    if raw or not created or instance.action not in ("HIDE_BOE", "RESTORE_BOE") or not instance.bill_of_entry_id:
        return
    mark_licences(_boe_licences([instance.bill_of_entry_id]))
