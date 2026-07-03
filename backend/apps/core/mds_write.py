"""
Master WRITE CUTOVER glue (ADR-001 Phase 6).

When MDS is enabled, master create/update/delete in this consumer app must flow
to the central Master-Data Service (the write authority) and the local mirror is
then reconciled to match — giving "edit anywhere, same on every server". When MDS
is DISABLED (the default), none of this runs and behavior is byte-for-byte the
local-only behavior that shipped before.

This module holds the decision + the three write operations so the viewset stays
thin and the logic is unit-testable in isolation. It is imported lazily by the
viewset only when the gate is on, so a project without ``mds_client`` installed
never imports it.

Gate (both must hold):
    settings.MDS_ENABLED is truthy AND the model's label is in settings.MDS_MODELS
(the 17 masters — DEFAULT_MDS_MODELS). ``TransferLetterModel`` / ``PurchaseStatus``
use the same viewset factory but are NOT in MDS_MODELS, so they are never routed.

Failure model (ADR-001 Decision 3 degradation contract):
    MDS unreachable -> HTTP 503 (MasterServiceUnavailable) with a clear message, and NO
    local change is left behind (the local write is rolled back). Reads always
    keep working from the local mirror (they never touch MDS).

Loop-safety:
    The mirror-refresh path (mds_client.sync) writes mirror rows DIRECTLY via the
    ORM (update_or_create / queryset.delete), bypassing this viewset entirely, so
    reconciling the mirror after a write does NOT re-enter the cutover. No
    thread-local guard is needed; see the note at ``_refresh_mirror``.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.core import mds_payload

logger = logging.getLogger("apps.core.mds_write")

_UNAVAILABLE_DETAIL = (
    "Master data is centrally managed and the service is unreachable — "
    "try again shortly."
)


class MasterServiceUnavailable(APIException):
    """HTTP 503 raised when a master write cannot reach MDS.

    DRF 3.17 ships no ``ServiceUnavailable``, so we define the 503 here. DRF's
    exception handler turns this into a standard ``{"detail": ...}`` 503 body,
    matching the platform's error shape."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _UNAVAILABLE_DETAIL
    default_code = "master_service_unavailable"


def _model_label(model) -> str:
    return f"{model._meta.app_label}.{model.__name__}"


def mds_active_for(model) -> bool:
    """True when the write cutover should intercept writes for ``model``.

    Requires MDS_ENABLED AND the model to be one of the configured MDS masters.
    Cheap and side-effect free — safe to call on every write."""
    if not getattr(settings, "MDS_ENABLED", False):
        return False
    mds_models = getattr(settings, "MDS_MODELS", None) or {}
    return _model_label(model) in mds_models


def _client_mods():
    """Import the mds_client write helpers lazily (only when the gate is on)."""
    from mds_client.client import MDSUnavailable
    from mds_client.sync import write_master, delete_master, refresh_local
    return MDSUnavailable, write_master, delete_master, refresh_local


def _refresh_mirror(model_label: str) -> None:
    """Reconcile the LOCAL mirror for one model from MDS after a write.

    NOTE (loop-safety): ``refresh_local`` -> ``mds_client.sync.sync_model`` upserts
    mirror rows with ``Model.objects.update_or_create(...)`` and applies deletes
    with ``queryset.delete()`` — direct ORM writes that do NOT go through this
    viewset, so they cannot re-trigger the cutover. If a mirror refresh ever fails
    (e.g. MDS blips right after the write committed), we log and move on: MDS is
    already authoritative and the periodic sync worker will converge the mirror.
    """
    _, _, _, refresh_local = _client_mods()
    try:
        refresh_local(model_label)
    except Exception:  # noqa: BLE001 - never fail the request on a post-write refresh
        logger.warning(
            "MDS mirror refresh for %s failed after write; the sync worker will "
            "reconcile shortly.", model_label, exc_info=True,
        )


def save_through_mds(serializer, *, extra_save_kwargs=None):
    """Create/Update path: persist locally, push to MDS, reconcile the mirror.

    Steps:
      1. Save the validated serializer locally (this also computes the keyless
         ``uid`` via ``SyntheticUidMixin.save``, which we need for the payload).
      2. Build the id-free MDS row from the SAME shared helper the exporter uses.
      3. ``write_master`` -> MDS (the write authority).
      4. Refresh the local mirror from MDS so the local row reflects canonical
         state (server-normalised fields, resolved FKs).

    Steps 1–3 run inside a transaction: if MDS is unreachable, the local write is
    rolled back and a 503 is raised, so there is NEVER a partial write (local
    saved but MDS not). The mirror refresh (step 4) runs AFTER the commit.

    ``extra_save_kwargs`` carries created_by/modified_by exactly as the local-only
    path did, preserving audit behavior.
    """
    MDSUnavailable, write_master, _, _ = _client_mods()
    extra_save_kwargs = extra_save_kwargs or {}

    model = serializer.Meta.model if hasattr(serializer, "Meta") else None
    try:
        with transaction.atomic():
            instance = serializer.save(**extra_save_kwargs)
            model = type(instance)
            model_label, _nk, row = mds_payload.build_row(instance)
            write_master(model_label, row)
    except MDSUnavailable as exc:
        logger.error("MDS write failed (%s); local change rolled back.", model_label)
        raise MasterServiceUnavailable() from exc

    # Committed on MDS + locally; now make the local mirror mirror MDS exactly.
    _refresh_mirror(model_label)
    return instance


def delete_through_mds(instance) -> None:
    """Delete path: delete on MDS FIRST, then delete the local mirror row.

    On MDSUnavailable we raise 503 and do NOT touch the local row (nothing
    half-deleted). ``mds_client.sync.delete_master`` performs both deletes in the
    correct order (MDS then local mirror by natural key)."""
    MDSUnavailable, _, delete_master, _ = _client_mods()
    model_label, _nk, key = mds_payload.natural_key_value(instance)
    try:
        delete_master(model_label, key)
    except MDSUnavailable as exc:
        logger.error("MDS delete failed (%s=%r); local row untouched.", model_label, key)
        raise MasterServiceUnavailable() from exc
