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
from django.contrib.auth.hashers import check_password, make_password
import uuid


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
        help_text="Password hash of the peer's server-to-server sync credential",
    )
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "core"

    def __str__(self):
        return f"Peer {self.server_id} ({self.base_url})"

    def set_auth_token(self, raw_token: str) -> None:
        """Hash a peer credential before persisting it."""
        if not isinstance(raw_token, str) or not raw_token.strip():
            raise ValueError("A non-empty sync peer credential is required.")
        self.auth_token = make_password(raw_token)

    def check_auth_token(self, raw_token: str) -> bool:
        """Check a credential without ever exposing the stored hash."""
        return bool(self.auth_token and raw_token and check_password(raw_token, self.auth_token))


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
    # ``last_synced_at`` is retained only for backwards-compatible status
    # reporting.  It is not a safe replication cursor: clocks are neither a
    # total order nor an acknowledgement of an immutable event stream.
    remote_event_cursor = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = "core"

    def __str__(self):
        return f"Cursor for {self.peer.server_id}: {self.last_synced_at}"


class SyncEvent(models.Model):
    """Immutable replication outbox/inbox event.

    ``id`` is the monotonically ordered cursor exposed by the originating
    server.  ``event_id`` remains stable across forwarding through peers, so
    every server can deduplicate delivery independently of wall clocks.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_server = models.CharField(max_length=100, db_index=True)
    model_label = models.CharField(max_length=100, db_index=True)
    natural_key = models.CharField(max_length=255, db_index=True)
    op = models.CharField(max_length=10)
    source_version = models.PositiveBigIntegerField(default=1)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "core"
        ordering = ["id"]
        indexes = [models.Index(fields=["source_server", "event_id"], name="core_syncev_source__3b168d_idx")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise RuntimeError("SyncEvent rows are immutable; append a new event instead.")
        return super().save(*args, **kwargs)


class SyncInboxEvent(models.Model):
    """Idempotency ledger for events received from a peer."""

    source_server = models.CharField(max_length=100)
    event_id = models.UUIDField()
    received_at = models.DateTimeField(default=timezone.now)
    applied_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=20, default="received")
    error = models.TextField(blank=True, default="")

    class Meta:
        app_label = "core"
        constraints = [models.UniqueConstraint(fields=["source_server", "event_id"], name="core_sync_inbox_source_event_unique")]


class SyncPeerDelivery(models.Model):
    """Durable acknowledgement of an immutable event by an outbound peer."""

    STATUS_PENDING = "pending"
    STATUS_ACKNOWLEDGED = "acknowledged"
    STATUS_FAILED = "failed"
    peer = models.ForeignKey(SyncPeer, on_delete=models.CASCADE, related_name="deliveries")
    event = models.ForeignKey(SyncEvent, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=20, default=STATUS_PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "core"
        constraints = [models.UniqueConstraint(fields=["peer", "event"], name="core_sync_peer_event_unique")]


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
