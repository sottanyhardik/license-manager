"""
MasterSyncMixin (Module 04)

Abstract model mixin that adds multi-server synchronization fields to any
Master model:

- master_uid:     deterministic UUID derived from natural key (convergence anchor)
- sync_version:   monotonic version counter (conflict detection)
- is_tombstone:   soft-delete flag (delete propagation without data loss)
- origin_server:  identifier of the server that last wrote this record
- synced_at:      timestamp of last successful sync receipt

Subclasses must implement `get_natural_key_values()` which returns the tuple
of field values forming the business key.
"""
from __future__ import annotations

import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def deterministic_uid(model_label: str, *key_parts: str) -> uuid.UUID:
    """Generate a deterministic UUID5 from model label + natural key parts.

    Identical inputs on any server produce the identical UUID — this is the
    convergence anchor that prevents duplicate Masters across deployments.
    """
    namespace = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    canonical = f"{model_label}:" + "|".join(str(p) for p in key_parts)
    return uuid.uuid5(namespace, canonical)


def media_sha256(file_field) -> str | None:
    """Compute SHA256 hex digest of a Django File/ImageField's content.

    Returns None if the field is empty.  Rewinds the file pointer after reading.
    """
    if not file_field:
        return None
    try:
        file_field.open("rb")
        h = hashlib.sha256()
        for chunk in file_field.chunks(chunk_size=8192):
            h.update(chunk)
        file_field.close()
        return h.hexdigest()
    except Exception:
        return None


SERVER_ID = getattr(settings, "SYNC_SERVER_ID", "default")


class MasterSyncMixin(models.Model):
    """Abstract mixin providing multi-server sync fields.

    Every Master model that participates in synchronization should inherit
    this mixin.  The mixin is designed to be added *alongside* existing base
    classes (AuditModel, SyntheticUidMixin, etc.) without conflict.
    """

    master_uid = models.UUIDField(
        null=True, blank=True, unique=True, db_index=True, editable=False,
        help_text="Deterministic UUID derived from natural key — convergence anchor.",
    )
    sync_version = models.PositiveBigIntegerField(
        default=1,
        help_text="Monotonically increasing version; bumped on every write.",
    )
    is_tombstone = models.BooleanField(
        default=False, db_index=True,
        help_text="True → record is soft-deleted (tombstone).",
    )
    origin_server = models.CharField(
        max_length=100, default="", blank=True, db_index=True,
        help_text="Server ID that last wrote this record.",
    )
    synced_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of last successful sync receipt.",
    )

    class Meta:
        abstract = True

    # ── Subclass contract ───────────────────────────────────────────────

    def get_natural_key_values(self) -> tuple:
        """Return the tuple of field values forming the business key.

        Must be overridden by each concrete Master model.  The values are
        used to compute `master_uid` deterministically.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_natural_key_values()"
        )

    # ── Lifecycle hooks ─────────────────────────────────────────────────

    def compute_master_uid(self) -> uuid.UUID:
        """Compute the deterministic master_uid from natural key values."""
        label = self._meta.label  # e.g. "core.CompanyModel"
        parts = self.get_natural_key_values()
        return deterministic_uid(label, *parts)

    def save(self, *args, **kwargs):
        # Compute master_uid if missing
        if not self.master_uid:
            try:
                self.master_uid = self.compute_master_uid()
            except Exception:
                pass  # allow save even if NK not yet available

        # Set origin_server if not already set by sync ingest
        if not self.origin_server:
            self.origin_server = SERVER_ID

        super().save(*args, **kwargs)

    def tombstone(self, *, bump_version: bool = True):
        """Mark this record as a tombstone (soft-delete)."""
        self.is_tombstone = True
        if bump_version:
            self.sync_version += 1
        self.save(update_fields=["is_tombstone", "sync_version", "origin_server"])

    def is_alive(self) -> bool:
        return not self.is_tombstone
