"""
Master Sync Registry (Module 04)

Central catalog of all syncable Master models. Each entry defines:
- model_label:    Django app_label.ModelName
- natural_key:    field(s) forming the business key (used for duplicate reconciliation)
- uid_field:      field holding the deterministic UUID (None → uses natural_key directly)
- media_fields:   list of ImageField/FileField names requiring media sync
- fk_deps:        list of model_labels this model depends on (sync ordering)
- serializer:     DRF serializer class path for sync payloads (lazy import)

The registry is the single source of truth for sync ordering, duplicate
detection, delete-protection scoping, and media handling.
"""
from __future__ import annotations

import dataclasses
from typing import Sequence


@dataclasses.dataclass(frozen=True)
class MasterSyncEntry:
    model_label: str
    natural_key: tuple[str, ...]
    uid_field: str | None = "uid"          # None → model has no synthetic uid
    media_fields: tuple[str, ...] = ()
    fk_deps: tuple[str, ...] = ()          # model_labels that must sync first
    exclude_fields: tuple[str, ...] = ()   # fields to skip in sync payload


# ── Registry ────────────────────────────────────────────────────────────
# Order matters: parents before children (topological by fk_deps).

MASTER_SYNC_REGISTRY: tuple[MasterSyncEntry, ...] = (
    # ── Standalone masters (no FK deps) ─────────────────────────────────
    MasterSyncEntry(
        model_label="core.CompanyModel",
        natural_key=("iec",),
        uid_field=None,
        media_fields=("logo", "signature", "stamp"),
    ),
    MasterSyncEntry(
        model_label="core.PortModel",
        natural_key=("code",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.HSCodeModel",
        natural_key=("hs_code",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.ItemGroupModel",
        natural_key=("name",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.HeadSIONNormsModel",
        natural_key=("name",),
        uid_field="uid",
    ),
    MasterSyncEntry(
        model_label="core.SchemeCode",
        natural_key=("code",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.NotificationNumber",
        natural_key=("code",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.PurchaseStatus",
        natural_key=("code",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.InvoiceEntity",
        natural_key=("pan_number",),
        uid_field=None,
        media_fields=("logo", "signature", "stamp"),
    ),
    MasterSyncEntry(
        model_label="core.ExchangeRateModel",
        natural_key=("date",),
        uid_field=None,
    ),
    MasterSyncEntry(
        model_label="core.TransferLetterModel",
        natural_key=("name",),
        uid_field=None,
        media_fields=("tl",),
    ),

    # ── Masters with FK deps (level 1) ─────────────────────────────────
    MasterSyncEntry(
        model_label="core.SionNormClassModel",
        natural_key=("norm_class",),
        uid_field=None,
        fk_deps=("core.HeadSIONNormsModel",),
    ),
    MasterSyncEntry(
        model_label="core.ItemHeadModel",
        natural_key=("name",),
        uid_field=None,
        fk_deps=("core.SionNormClassModel",),
    ),
    MasterSyncEntry(
        model_label="core.ItemNameModel",
        natural_key=("name",),
        uid_field=None,
        fk_deps=("core.ItemGroupModel", "core.SionNormClassModel"),
    ),
    MasterSyncEntry(
        model_label="core.ProductDescriptionModel",
        natural_key=("hs_code", "product_description"),
        uid_field="uid",
        fk_deps=("core.HSCodeModel",),
    ),
    MasterSyncEntry(
        model_label="core.UnitPriceModel",
        natural_key=("name", "label"),
        uid_field="uid",
        fk_deps=(),
    ),

    # ── Masters with FK deps (level 2) ─────────────────────────────────
    MasterSyncEntry(
        model_label="core.SIONExportModel",
        natural_key=("norm_class", "description"),
        uid_field="uid",
        fk_deps=("core.SionNormClassModel",),
    ),
    MasterSyncEntry(
        model_label="core.SIONImportModel",
        natural_key=("norm_class", "serial_number"),
        uid_field="uid",
        fk_deps=("core.SionNormClassModel", "core.HSCodeModel"),
    ),
    MasterSyncEntry(
        model_label="core.SionNormNote",
        natural_key=("sion_norm", "display_order"),
        uid_field="uid",
        fk_deps=("core.SionNormClassModel",),
    ),
    MasterSyncEntry(
        model_label="core.SionNormCondition",
        natural_key=("sion_norm", "display_order"),
        uid_field="uid",
        fk_deps=("core.SionNormClassModel",),
    ),
)


def _build_index() -> dict[str, MasterSyncEntry]:
    return {e.model_label: e for e in MASTER_SYNC_REGISTRY}


_INDEX: dict[str, MasterSyncEntry] | None = None


def get_entry(model_label: str) -> MasterSyncEntry | None:
    """Look up a registry entry by model_label (e.g. 'core.CompanyModel')."""
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX.get(model_label)


def get_all_entries() -> Sequence[MasterSyncEntry]:
    """Return all entries in topological (sync-safe) order."""
    return MASTER_SYNC_REGISTRY


def get_media_entries() -> Sequence[MasterSyncEntry]:
    """Return only entries that have media fields."""
    return tuple(e for e in MASTER_SYNC_REGISTRY if e.media_fields)


def get_model_labels() -> tuple[str, ...]:
    """Return all registered model labels in sync order."""
    return tuple(e.model_label for e in MASTER_SYNC_REGISTRY)
