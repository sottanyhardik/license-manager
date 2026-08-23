"""Transactional immutable-outbox emission for locally written master data."""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save, pre_delete
from django.apps import apps

from .mixins import SERVER_ID, remote_sync_is_applying
from .registry import get_all_entries, get_entry
from .service import _nk_string, _serialize_instance, record_sync_event


def _entry_for_instance(instance):
    return get_entry(instance._meta.label)


def _emit_save(sender, instance, created, **kwargs):
    if kwargs.get("raw") or remote_sync_is_applying() or getattr(instance, "_sync_inbound_write", False):
        return
    entry = _entry_for_instance(instance)
    if entry is None:
        return
    data = _serialize_instance(instance, entry)
    record_sync_event({
        "model_label": entry.model_label,
        "op": "create" if created else "update",
        "data": data,
        "source_server": SERVER_ID,
        "source_version": getattr(instance, "sync_version", 1),
    }, natural_key=_nk_string(entry, data))


def _capture_delete(sender, instance, **kwargs):
    if remote_sync_is_applying():
        return
    entry = _entry_for_instance(instance)
    if entry is None:
        return
    data = _serialize_instance(instance, entry)
    instance._sync_outbox_delete = (entry, data, getattr(instance, "sync_version", 1))


def _emit_delete(sender, instance, **kwargs):
    if remote_sync_is_applying():
        return
    captured = getattr(instance, "_sync_outbox_delete", None)
    if captured is None:
        return
    entry, data, version = captured
    record_sync_event({
        "model_label": entry.model_label, "op": "delete", "data": data,
        "source_server": SERVER_ID, "source_version": version + 1,
    }, natural_key=_nk_string(entry, data))


def connect_master_outbox_signals():
    for entry in get_all_entries():
        sender = apps.get_model(entry.model_label)
        post_save.connect(_emit_save, sender=sender, dispatch_uid=f"sync-outbox-save:{entry.model_label}")
        pre_delete.connect(_capture_delete, sender=sender, dispatch_uid=f"sync-outbox-pre-delete:{entry.model_label}")
        post_delete.connect(_emit_delete, sender=sender, dispatch_uid=f"sync-outbox-post-delete:{entry.model_label}")
