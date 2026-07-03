"""
Mirror sync + write path.

Read (mirror refresh):
    sync_model(label)  — pull deltas for one model, upsert into its local mirror
                         by natural key, apply deletes from the change feed, and
                         advance the per-model cursor/etag in MDSSyncState.
    sync_all()         — sync every model declared in settings.MDS_MODELS.

Write:
    write_master(label, row) — push one row to MDS via bulk_upsert. On
                         MDSUnavailable it re-raises a clear error so the caller
                         fails loudly (never a silent drop). A TODO hook marks
                         where an optional Celery outbox would enqueue for retry.

Design notes:
- Upserts run inside a transaction per model so a mid-page failure doesn't leave
  a half-applied mirror or an advanced cursor.
- The cursor is ``max(modified_on)`` observed in the pulled rows — robust even if
  MDS returns rows slightly out of order across pages.
- Deletes come only from the change feed (an ``updated_since`` pull cannot see a
  vanished row); we apply ``op == "delete"`` by natural key.
- Mirror models are resolved lazily via ``apps.get_model`` so this package does
  not import the consumer's models at load time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.apps import apps as django_apps
from django.db import transaction
from django.utils import timezone

from . import settings as mds_settings
from .client import MDSClient, MDSUnavailable
from .models import MDSSyncState

logger = logging.getLogger("mds_client.sync")

# Fields that are MDS-internal server state and must not overwrite mirror rows.
# The mirror keeps its own PK/timestamps; we copy business fields + natural key.
_SKIP_FIELDS = {"id", "pk"}


@dataclass
class SyncResult:
    model_label: str
    upserted: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped_unchanged: bool = False

    def __str__(self):
        if self.skipped_unchanged:
            return f"{self.model_label}: unchanged (304)"
        return (
            f"{self.model_label}: upserted={self.upserted} "
            f"(created={self.created}, updated={self.updated}), deleted={self.deleted}"
        )


# --- mirror upsert ----------------------------------------------------------
def _resolve_mirror_model(cfg: dict):
    """Return the local mirror model class for a MDS_MODELS config entry."""
    app_label, model_name = cfg["mirror_model"].split(".", 1)
    return django_apps.get_model(app_label, model_name)


def _clean_row(row: dict, natural_key: str, model) -> dict:
    """Keep only fields that exist on the mirror model; drop server-internal ones.

    This makes the mirror tolerant of MDS adding fields the consumer doesn't have
    yet (additive-v1 API evolution) and never tries to write MDS's ``id`` onto
    the local PK (ids have diverged across servers — ADR-001 Decision 2)."""
    field_names = {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}
    cleaned = {}
    for key, value in row.items():
        if key in _SKIP_FIELDS:
            continue
        if key in field_names:
            cleaned[key] = value
    # The natural key must always survive so update_or_create can match.
    if natural_key in row:
        cleaned[natural_key] = row[natural_key]
    return cleaned


def upsert_rows(model, natural_key: str, rows) -> tuple[int, int]:
    """Upsert an iterable of raw MDS rows into the mirror ``model`` by natural key.

    Returns (created, updated). Runs inside the caller's transaction.
    """
    created = updated = 0
    for row in rows:
        key_value = row.get(natural_key)
        if key_value in (None, ""):
            logger.warning("Skipping %s row without natural key '%s': %r", model.__name__, natural_key, row)
            continue
        defaults = _clean_row(row, natural_key, model)
        defaults.pop(natural_key, None)  # goes in the lookup, not the defaults
        _, was_created = model.objects.update_or_create(
            **{natural_key: key_value}, defaults=defaults
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def _max_modified(rows) -> str | None:
    """Greatest ``modified_on`` string across rows — the next delta cursor."""
    stamps = [r.get("modified_on") for r in rows if r.get("modified_on")]
    return max(stamps) if stamps else None


# --- per-model sync ---------------------------------------------------------
def sync_model(model_label: str, client: MDSClient | None = None) -> SyncResult:
    """Refresh the local mirror for one model from MDS.

    Steps: (1) load/create sync state, (2) ETag short-circuit via a delta pull
    with If-None-Match, (3) upsert all delta pages by natural key, (4) apply
    deletes from the change feed, (5) advance the cursor/etag transactionally.
    """
    cfg = mds_settings.get_model_config(model_label)
    natural_key = cfg["natural_key"]
    mirror_model = _resolve_mirror_model(cfg)
    own_client = client is None
    client = client or MDSClient()
    result = SyncResult(model_label=model_label)

    try:
        state, _ = MDSSyncState.objects.get_or_create(model_label=model_label)

        # 1) Pull the delta as pages; ETag short-circuits an unchanged model.
        first_page = client.fetch_delta(model_label, since=state.cursor, etag=state.etag)
        if first_page.not_modified:
            result.skipped_unchanged = True
            # Still apply deletes: a delete doesn't move max(modified_on), so the
            # collection ETag can be unchanged while a row vanished.
            result.deleted = _apply_deletes(model_label, mirror_model, natural_key, client, state)
            state.touch()
            state.save(update_fields=["changes_cursor", "last_synced_at", "updated_at"])
            return result

        rows = list(first_page.results)
        next_url = first_page.next_url
        new_etag = first_page.etag
        while next_url:
            page = client.fetch_delta_url(next_url)
            rows.extend(page.results)
            next_url = page.next_url

        # 2) Apply upserts + deletes + cursor advance in one transaction.
        with transaction.atomic():
            created, updated = upsert_rows(mirror_model, natural_key, rows)
            result.created, result.updated = created, updated
            result.upserted = created + updated

            deleted = _apply_deletes(model_label, mirror_model, natural_key, client, state)
            result.deleted = deleted

            new_cursor = _max_modified(rows)
            if new_cursor:
                state.cursor = new_cursor
            if new_etag:
                state.etag = new_etag
            state.touch()
            state.save()

        logger.info("mds sync %s", result)
        return result
    finally:
        if own_client:
            client.close()


def _apply_deletes(model_label, mirror_model, natural_key, client, state) -> int:
    """Apply ``op == 'delete'`` changes from the feed to the mirror by natural key,
    advancing ``changes_cursor``. Returns the number of rows deleted."""
    changes = client.get_changes(since=state.changes_cursor)
    deleted = 0
    max_at = state.changes_cursor
    for change in changes:
        at = change.get("at")
        if at and (max_at is None or at > max_at):
            max_at = at
        # Only act on this model's deletes; other models are handled by their own sync.
        if change.get("model_label") != _mds_label_for(model_label):
            continue
        if change.get("op") == "delete":
            key_value = change.get("natural_key")
            count, _ = mirror_model.objects.filter(**{natural_key: key_value}).delete()
            deleted += count
    if max_at:
        state.changes_cursor = max_at
    return deleted


def _mds_label_for(model_label: str) -> str:
    """The change-feed ``model_label`` MDS emits for this model.

    MDS labels changes as ``<app_label>.<ModelClassName>`` (e.g. "masters.Company").
    A consumer's local label (e.g. "core.CompanyModel") differs, so allow an
    explicit override in MDS_MODELS via ``mds_model_label``; otherwise fall back
    to the consumer label (works when they coincide, e.g. in tests)."""
    cfg = mds_settings.get_model_config(model_label)
    return cfg.get("mds_model_label", model_label)


# --- sync everything --------------------------------------------------------
def sync_all(client: MDSClient | None = None) -> list[SyncResult]:
    """Sync every model in settings.MDS_MODELS. Reuses one client/session.

    One model's failure does not abort the rest: MDSUnavailable stops the whole
    run (the service is down); a per-model error is logged and skipped.
    """
    own_client = client is None
    client = client or MDSClient()
    results: list[SyncResult] = []
    try:
        for model_label in mds_settings.get_models():
            try:
                results.append(sync_model(model_label, client=client))
            except MDSUnavailable:
                raise  # service down — no point continuing
            except Exception:  # noqa: BLE001 - isolate one model's failure
                logger.exception("mds sync failed for %s", model_label)
        return results
    finally:
        if own_client:
            client.close()


# --- write path -------------------------------------------------------------
def write_master(model_label: str, row: dict, client: MDSClient | None = None) -> dict:
    """Write ONE master row to MDS (via bulk_upsert of a single-element list).

    Returns MDS's {created, updated}. On MDSUnavailable, re-raises with a clear,
    user-facing message so the write fails loudly — reads keep working from the
    local mirror. NEVER silently drops the write.
    """
    # Validate the model is known before touching the network.
    mds_settings.get_model_config(model_label)
    own_client = client is None
    client = client or MDSClient()
    try:
        return client.bulk_upsert(model_label, [row])
    except MDSUnavailable as exc:
        # TODO(outbox): optionally enqueue (model_label, row) to a Celery-backed
        # outbox here for eventual-consistency retry where acceptable (e.g.
        # exchange-rate ingestion — ADR-001 open question #2). For now, fail loud.
        logger.error("write_master(%s) failed: MDS unreachable", model_label)
        raise MDSUnavailable(
            "Master data is read-only right now — the central service is unreachable. "
            "Your change was NOT saved; please retry shortly."
        ) from exc
    finally:
        if own_client:
            client.close()
