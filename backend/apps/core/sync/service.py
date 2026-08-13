"""
Master Sync Service (Module 04)

Core engine for multi-server Master synchronization.

Responsibilities:
- Apply inbound sync events (create / update / delete)
- Conflict resolution (last-writer-wins with version vector)
- Duplicate reconciliation (natural-key based)
- Delete protection (reject deletes when FK references exist)
- Change-feed emission (MasterChange records)
- Offline recovery (delta pull by timestamp)

All operations are idempotent: replaying the same event produces no change.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.db import models, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.core.models import MasterChange
from .registry import get_entry, get_all_entries, MasterSyncEntry
from .mixins import SERVER_ID

logger = logging.getLogger("sync.service")


# ── Result types ────────────────────────────────────────────────────────

@dataclass
class SyncResult:
    """Outcome of a single sync event application."""
    model_label: str
    natural_key: str
    op: str                          # "create" | "update" | "delete" | "noop"
    success: bool = True
    conflict: bool = False
    conflict_detail: str = ""
    error: str = ""


@dataclass
class SyncBatchResult:
    """Outcome of a batch sync operation."""
    applied: list[SyncResult] = field(default_factory=list)
    skipped: list[SyncResult] = field(default_factory=list)
    errors: list[SyncResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.applied) + len(self.skipped) + len(self.errors)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ── Helpers ─────────────────────────────────────────────────────────────

def _get_model(model_label: str) -> type[models.Model]:
    """Resolve a model_label like 'core.CompanyModel' to the Django model class."""
    return apps.get_model(model_label)


def _natural_key_filter(entry: MasterSyncEntry, data: dict) -> dict:
    """Build a queryset filter dict from the natural key fields in data.

    If a natural-key field is a FK (e.g. ``ProductDescriptionModel.hs_code``),
    the payload carries the *related* natural key — never the local surrogate
    id, which is meaningless on another server — so the filter is expressed as
    a related lookup (``hs_code__hs_code="98765432"``).
    """
    Model = _get_model(entry.model_label)
    filt = {}
    for k in entry.natural_key:
        val = data.get(k)
        if val is None:
            raise ValueError(f"Missing natural key field '{k}' in sync payload")

        # If the NK field is a FK, look up by the related natural key
        nk_field = Model._meta.get_field(k)
        if isinstance(nk_field, models.ForeignKey) and not isinstance(val, models.Model):
            related_entry = get_entry(nk_field.related_model._meta.label)
            if related_entry is None:
                raise ValueError(
                    f"Natural key field '{k}' of {entry.model_label} points at "
                    f"unregistered model {nk_field.related_model._meta.label}"
                )
            for lookup, part in _related_nk_parts(related_entry, val).items():
                filt[f"{k}__{lookup}"] = part
        else:
            filt[k] = val
    return filt


def _related_nk_parts(related_entry: MasterSyncEntry, value) -> dict:
    """Split a transported FK value into {related_nk_field: value}.

    ``_serialize_instance`` joins multi-field related natural keys with "|".
    """
    parts = str(value).split("|")
    if len(parts) != len(related_entry.natural_key):
        raise ValueError(
            f"FK natural key {value!r} does not match "
            f"{related_entry.model_label} key {related_entry.natural_key}"
        )
    return dict(zip(related_entry.natural_key, parts))


def _resolve_related(fk_field: models.ForeignKey, value):
    """Resolve a transported FK natural-key value to a local instance."""
    related_model = fk_field.related_model
    related_entry = get_entry(related_model._meta.label)
    if related_entry is None:
        raise ValueError(
            f"FK '{fk_field.name}' points at unregistered model "
            f"{related_model._meta.label}; it cannot be synced by natural key"
        )
    filt = _related_nk_parts(related_entry, value)
    instance = related_model.objects.filter(**filt).order_by().first()
    if instance is None:
        raise ValueError(
            f"Unresolved FK '{fk_field.name}': no {related_model._meta.label} "
            f"with natural key {value!r} on this server"
        )
    return instance


def _resolve_fk_values(Model: type[models.Model], data: dict) -> dict:
    """Return ``data`` with FK natural-key strings replaced by instances.

    Sync payloads reference parents by natural key (see ``_serialize_instance``).
    A FK whose related model is not in the registry cannot be transported at all
    (a local surrogate id would point at an unrelated row on the peer, or break
    a deferred FK constraint at commit), so such keys are dropped.
    """
    resolved = dict(data)
    for fk_field in Model._meta.get_fields():
        if not isinstance(fk_field, models.ForeignKey):
            continue
        if get_entry(fk_field.related_model._meta.label) is None:
            # Unsyncable reference: drop both "created_by" and "created_by_id".
            resolved.pop(fk_field.name, None)
            resolved.pop(fk_field.attname, None)
            continue
        if fk_field.name not in resolved:
            continue
        value = resolved[fk_field.name]
        if value is None or isinstance(value, models.Model):
            continue
        resolved[fk_field.name] = _resolve_related(fk_field, value)
    return resolved


def _nk_string(entry: MasterSyncEntry, data: dict) -> str:
    """Human-readable natural key string for logging / MasterChange."""
    return "|".join(str(data.get(k, "")) for k in entry.natural_key)


def _check_fk_references(instance: models.Model) -> list[str]:
    """Check if any other model has a FK reference to this instance.

    Returns a list of human-readable reference descriptions.
    Used for delete protection.
    """
    refs = []
    for rel in instance._meta.related_objects:
        related_model = rel.related_model
        related_field = rel.field.name
        count = related_model.objects.filter(**{related_field: instance}).count()
        if count > 0:
            refs.append(
                f"{related_model._meta.label}: {count} record(s) via {related_field}"
            )
    return refs


# ── Core sync operations ───────────────────────────────────────────────

def apply_create_or_update(
    entry: MasterSyncEntry,
    data: dict[str, Any],
    source_server: str,
    source_version: int = 1,
) -> SyncResult:
    """Apply a CREATE or UPDATE sync event.

    Duplicate reconciliation: if a record with the same natural key already
    exists, this becomes an UPDATE (no duplicate created).

    Conflict resolution: if the local version >= source version, the event
    is skipped (last-writer-wins by version).  If versions are equal but
    origin servers differ, the lexicographically greater server ID wins
    (deterministic tie-break).
    """
    Model = _get_model(entry.model_label)
    nk_str = _nk_string(entry, data)

    try:
        # Payload-shape problems (missing natural key, unresolvable parent) are
        # per-event errors, never an exception that aborts the whole batch.
        nk_filter = _natural_key_filter(entry, data)
        data = _resolve_fk_values(Model, data)

        with transaction.atomic():
            # order_by() is required: a Meta.ordering that spans a nullable FK
            # adds an outer join, and Postgres refuses SELECT ... FOR UPDATE on
            # the nullable side of one.
            existing = (
                Model.objects
                .filter(**nk_filter)
                .order_by()
                .select_for_update()
                .first()
            )

            if existing is not None:
                # ── Duplicate reconciliation / UPDATE path ───────────
                local_version = getattr(existing, "sync_version", 0)
                local_origin = getattr(existing, "origin_server", "")

                # Conflict detection
                if local_version > source_version:
                    return SyncResult(
                        model_label=entry.model_label,
                        natural_key=nk_str,
                        op="noop",
                        conflict=True,
                        conflict_detail=(
                            f"Local version {local_version} > source {source_version}; "
                            f"local origin={local_origin}, source={source_server}"
                        ),
                    )

                if local_version == source_version and local_origin >= source_server:
                    return SyncResult(
                        model_label=entry.model_label,
                        natural_key=nk_str,
                        op="noop",
                        conflict=True,
                        conflict_detail=(
                            f"Version tie ({local_version}); "
                            f"local origin '{local_origin}' >= source '{source_server}'"
                        ),
                    )

                # Apply update
                update_fields = []
                for field_name, value in data.items():
                    if field_name in entry.natural_key:
                        continue  # don't update NK fields
                    if field_name in ("id", "pk", "master_uid"):
                        continue
                    if field_name in entry.exclude_fields:
                        continue
                    if hasattr(existing, field_name):
                        setattr(existing, field_name, value)
                        update_fields.append(field_name)

                existing.sync_version = source_version
                existing.origin_server = source_server
                existing.synced_at = timezone.now()
                update_fields.extend(["sync_version", "origin_server", "synced_at"])

                existing.save(update_fields=update_fields)

                # Record change
                MasterChange.objects.create(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op=MasterChange.OP_UPDATE,
                )

                logger.info(
                    "Sync UPDATE %s[%s] v%d from %s",
                    entry.model_label, nk_str, source_version, source_server,
                )
                return SyncResult(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op="update",
                )

            else:
                # ── CREATE path ─────────────────────────────────────
                # Remove fields that shouldn't be set on create
                create_data = {
                    k: v for k, v in data.items()
                    if k not in ("id", "pk") and k not in entry.exclude_fields
                }
                create_data["sync_version"] = source_version
                create_data["origin_server"] = source_server
                create_data["synced_at"] = timezone.now()

                instance = Model(**create_data)
                instance.save()

                MasterChange.objects.create(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op=MasterChange.OP_CREATE,
                )

                logger.info(
                    "Sync CREATE %s[%s] v%d from %s",
                    entry.model_label, nk_str, source_version, source_server,
                )
                return SyncResult(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op="create",
                )

    except Exception as exc:
        logger.exception("Sync error for %s[%s]", entry.model_label, nk_str)
        return SyncResult(
            model_label=entry.model_label,
            natural_key=nk_str,
            op="error",
            success=False,
            error=str(exc),
        )


def apply_delete(
    entry: MasterSyncEntry,
    data: dict[str, Any],
    source_server: str,
    source_version: int = 1,
) -> SyncResult:
    """Apply a DELETE sync event with delete protection.

    If the record has FK references from other models, the delete is
    rejected with a 409-style conflict (no destructive propagation).

    Soft-delete: the record is tombstoned, not physically removed.
    """
    Model = _get_model(entry.model_label)
    nk_str = _nk_string(entry, data)

    try:
        nk_filter = _natural_key_filter(entry, data)

        with transaction.atomic():
            # See apply_create_or_update: order_by() keeps FOR UPDATE legal.
            existing = (
                Model.objects
                .filter(**nk_filter)
                .order_by()
                .select_for_update()
                .first()
            )

            if existing is None:
                return SyncResult(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op="noop",
                )

            # Already tombstoned — idempotent
            if getattr(existing, "is_tombstone", False):
                return SyncResult(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op="noop",
                )

            # Delete protection: check FK references
            refs = _check_fk_references(existing)
            if refs:
                detail = "; ".join(refs)
                logger.warning(
                    "Delete BLOCKED for %s[%s]: %s",
                    entry.model_label, nk_str, detail,
                )
                return SyncResult(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op="delete",
                    success=False,
                    conflict=True,
                    conflict_detail=f"409 CONFLICT: FK references exist — {detail}",
                )

            # Version check
            local_version = getattr(existing, "sync_version", 0)
            if local_version > source_version:
                return SyncResult(
                    model_label=entry.model_label,
                    natural_key=nk_str,
                    op="noop",
                    conflict=True,
                    conflict_detail=(
                        f"Local version {local_version} > source {source_version}"
                    ),
                )

            # Tombstone the record
            existing.is_tombstone = True
            existing.sync_version = source_version
            existing.origin_server = source_server
            existing.synced_at = timezone.now()
            existing.save(update_fields=[
                "is_tombstone", "sync_version", "origin_server", "synced_at",
            ])

            MasterChange.objects.create(
                model_label=entry.model_label,
                natural_key=nk_str,
                op=MasterChange.OP_DELETE,
            )

            logger.info(
                "Sync DELETE (tombstone) %s[%s] v%d from %s",
                entry.model_label, nk_str, source_version, source_server,
            )
            return SyncResult(
                model_label=entry.model_label,
                natural_key=nk_str,
                op="delete",
            )

    except Exception as exc:
        logger.exception("Sync delete error for %s[%s]", entry.model_label, nk_str)
        return SyncResult(
            model_label=entry.model_label,
            natural_key=nk_str,
            op="error",
            success=False,
            error=str(exc),
        )


# ── Batch operations ───────────────────────────────────────────────────

def apply_sync_event(event: dict[str, Any]) -> SyncResult:
    """Apply a single sync event dict.

    Expected event shape:
    {
        "model_label": "core.CompanyModel",
        "op": "create" | "update" | "delete",
        "data": { ... field values ... },
        "source_server": "server-1",
        "source_version": 3,
    }
    """
    model_label = event["model_label"]
    op = event["op"]
    data = event["data"]
    source_server = event.get("source_server", "unknown")
    source_version = event.get("source_version", 1)

    entry = get_entry(model_label)
    if entry is None:
        return SyncResult(
            model_label=model_label,
            natural_key="",
            op=op,
            success=False,
            error=f"Unknown model_label: {model_label}",
        )

    if op in ("create", "update"):
        return apply_create_or_update(entry, data, source_server, source_version)
    elif op == "delete":
        return apply_delete(entry, data, source_server, source_version)
    else:
        return SyncResult(
            model_label=model_label,
            natural_key="",
            op=op,
            success=False,
            error=f"Unknown op: {op}",
        )


def apply_sync_batch(events: list[dict[str, Any]]) -> SyncBatchResult:
    """Apply a batch of sync events in topological order.

    Events are sorted by registry order (parents first) before application.
    """
    # Build ordering index
    label_order = {e.model_label: i for i, e in enumerate(get_all_entries())}

    # Sort events by registry order
    sorted_events = sorted(
        events,
        key=lambda ev: label_order.get(ev.get("model_label", ""), 999),
    )

    result = SyncBatchResult()
    for event in sorted_events:
        r = apply_sync_event(event)
        if not r.success:
            result.errors.append(r)
        elif r.op == "noop":
            result.skipped.append(r)
        else:
            result.applied.append(r)

    return result


# ── Delta pull (offline recovery) ──────────────────────────────────────

def get_changes_since(since: str | None = None) -> list[dict[str, Any]]:
    """Return all MasterChange records since the given ISO timestamp.

    Used by peers to pull missed changes after being offline.
    Returns a list of event dicts ready for `apply_sync_batch`.
    """
    qs = MasterChange.objects.all()
    if since:
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(since)
        if dt:
            qs = qs.filter(at__gt=dt)

    events = []
    for change in qs.order_by("at"):
        entry = get_entry(change.model_label)
        if entry is None:
            continue

        Model = _get_model(change.model_label)

        # For deletes, we only need the natural key
        if change.op == MasterChange.OP_DELETE:
            # Parse the natural key from the stored string
            nk_parts = change.natural_key.split("|")
            data = dict(zip(entry.natural_key, nk_parts))
            events.append({
                "model_label": change.model_label,
                "op": "delete",
                "data": data,
                "source_server": SERVER_ID,
                "source_version": 1,
                "at": change.at.isoformat(),
            })
        else:
            # For create/update, serialize the current state
            nk_parts = change.natural_key.split("|")
            nk_filter = dict(zip(entry.natural_key, nk_parts))
            try:
                instance = Model.objects.get(**nk_filter)
            except Model.DoesNotExist:
                continue  # record was deleted after the change was logged

            data = _serialize_instance(instance, entry)
            version = getattr(instance, "sync_version", 1)
            event = {
                "model_label": change.model_label,
                "op": change.op,
                "data": data,
                "source_server": SERVER_ID,
                "source_version": version,
                "at": change.at.isoformat(),
            }

            # Media metadata (path + SHA256) so the peer can queue the file
            # transfer.  Without this the receiver's MediaSyncTask pipeline is
            # never triggered and media never replicates.
            if entry.media_fields:
                from .media import get_media_info

                media_info = get_media_info(instance, entry)
                if any(v for v in media_info.values()):
                    event["media"] = media_info

            events.append(event)

    return events


def _serialize_instance(instance: models.Model, entry: MasterSyncEntry) -> dict:
    """Serialize a model instance to a dict suitable for sync transport."""
    data = {}
    for f in instance._meta.get_fields():
        if not hasattr(f, "attname"):
            continue  # skip reverse relations
        name = f.name
        if name in ("id", "pk"):
            continue
        if name in entry.exclude_fields:
            continue
        # For FK fields, store the natural key of the related object
        if isinstance(f, models.ForeignKey):
            related_entry = get_entry(f.related_model._meta.label)
            if related_entry is None:
                # A local surrogate id (created_by_id, ...) means nothing on a
                # peer: it would either point at an unrelated row or violate a
                # deferred FK constraint at commit time.  Do not transport it.
                continue
            related_obj = getattr(instance, name, None)
            if related_obj is not None:
                nk_vals = [
                    str(getattr(related_obj, nk_field, ""))
                    for nk_field in related_entry.natural_key
                ]
                data[name] = "|".join(nk_vals)
            else:
                data[name] = None
        elif isinstance(f, (models.ImageField, models.FileField)):
            field_file = getattr(instance, name)
            data[name] = field_file.name if field_file else None
        else:
            data[name] = getattr(instance, f.attname, None)
    return data


# ── Conflict log ───────────────────────────────────────────────────────

def get_conflict_log(since: str | None = None, limit: int = 100) -> list[dict]:
    """Return recent sync conflicts for monitoring/audit.

    Conflicts are SyncResults where conflict=True, stored via the
    SyncConflictLog model (created by the sync API views).
    """
    from .models import SyncConflictLog
    qs = SyncConflictLog.objects.all()
    if since:
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(since)
        if dt:
            qs = qs.filter(created_at__gt=dt)
    return list(qs.order_by("-created_at")[:limit].values())
