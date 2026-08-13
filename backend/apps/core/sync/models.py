"""
Sync-specific models (Module 04)

- SyncConflictLog:  audit trail of sync conflicts
- SyncPeer:         registered peer servers for sync
- SyncCursor:       per-peer high-water mark for delta pull
- MediaSyncTask:    pending media file transfers
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class SyncConflictLog(models.Model):
    """Append-only log of sync conflicts for audit and debugging."""

    model_label = models.CharField(max_length=100, db_index=True)
    natural_key = models.CharField(max_length=255)
    op = models.CharField(max_length=10)
    source_server = models.CharField(max_length=100)
    source_version = models.PositiveBigIntegerField(default=0)
    local_version = models.PositiveBigIntegerField(default=0)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = "core"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Conflict {self.op} {self.model_label}[{self.natural_key}] "
            f"v{self.source_version} from {self.source_server} @ {self.created_at:%Y-%m-%d %H:%M}"
        )


class SyncPeer(models.Model):
    """Registered peer server for sync push/pull."""

    server_id = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(help_text="Base URL of the peer's sync API")
    auth_token = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Bearer token for authenticating with this peer",
    )
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "core"

    def __str__(self):
        return f"Peer {self.server_id} ({self.base_url})"


class SyncCursor(models.Model):
    """Per-peer high-water mark for delta sync.

    Tracks the last successfully synced timestamp for each peer,
    enabling offline recovery: when a peer reconnects, we pull
    all changes since its cursor.
    """

    peer = models.OneToOneField(
        SyncPeer, on_delete=models.CASCADE, related_name="cursor",
    )
    last_synced_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of the last change successfully received from this peer",
    )
    last_pull_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When we last pulled from this peer",
    )

    class Meta:
        app_label = "core"

    def __str__(self):
        return f"Cursor for {self.peer.server_id}: {self.last_synced_at}"


class MediaSyncTask(models.Model):
    """Pending media file transfer task.

    Created when a sync event references a media file that hasn't been
    transferred yet.  A background worker picks these up and downloads
    the file from the source peer.
    """

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
    ]

    model_label = models.CharField(max_length=100)
    natural_key = models.CharField(max_length=255)
    field_name = models.CharField(max_length=100)
    source_server = models.CharField(max_length=100)
    source_path = models.CharField(max_length=500)
    expected_sha256 = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "core"
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"Media {self.status}: {self.model_label}[{self.natural_key}].{self.field_name} "
            f"from {self.source_server}"
        )
