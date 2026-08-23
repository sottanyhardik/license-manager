"""
Sync API Serializers (Module 04)

DRF serializers for the peer-to-peer sync API endpoints.
"""
from __future__ import annotations

from rest_framework import serializers


class SyncEventSerializer(serializers.Serializer):
    """Single sync event in a push/pull payload."""
    model_label = serializers.CharField(max_length=100)
    op = serializers.ChoiceField(choices=["create", "update", "delete"])
    data = serializers.DictField()
    source_server = serializers.CharField(max_length=100)
    source_version = serializers.IntegerField(min_value=1, default=1)
    # UUID is the durable idempotency key.  Optional only while rolling out to
    # older peers; the receiver derives a deterministic legacy key otherwise.
    event_id = serializers.UUIDField(required=False)
    at = serializers.DateTimeField(required=False)
    media = serializers.DictField(required=False, default=dict)


class SyncPushSerializer(serializers.Serializer):
    """Batch push payload from a peer server."""
    events = SyncEventSerializer(many=True)
    source_server = serializers.CharField(max_length=100)


class SyncPullRequestSerializer(serializers.Serializer):
    """Pull request: give me changes since this timestamp."""
    since = serializers.DateTimeField(required=False, allow_null=True)
    model_labels = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )


class SyncResultSerializer(serializers.Serializer):
    """Result of a single sync event application."""
    model_label = serializers.CharField()
    natural_key = serializers.CharField()
    op = serializers.CharField()
    success = serializers.BooleanField()
    conflict = serializers.BooleanField()
    conflict_detail = serializers.CharField(allow_blank=True)
    error = serializers.CharField(allow_blank=True)


class SyncBatchResultSerializer(serializers.Serializer):
    """Result of a batch sync operation."""
    applied = SyncResultSerializer(many=True)
    skipped = SyncResultSerializer(many=True)
    errors = SyncResultSerializer(many=True)
    total = serializers.IntegerField()
    ok = serializers.BooleanField()


class DeleteCheckSerializer(serializers.Serializer):
    """Request to check if a delete is safe (no FK references)."""
    model_label = serializers.CharField(max_length=100)
    natural_key = serializers.DictField()


class DeleteCheckResultSerializer(serializers.Serializer):
    """Result of a delete safety check."""
    model_label = serializers.CharField()
    natural_key = serializers.CharField()
    safe = serializers.BooleanField()
    references = serializers.ListField(child=serializers.CharField())


class MediaInfoSerializer(serializers.Serializer):
    """Media field metadata for sync."""
    path = serializers.CharField(allow_null=True)
    sha256 = serializers.CharField(allow_blank=True, allow_null=True)


class SyncStatusSerializer(serializers.Serializer):
    """Overall sync status for monitoring."""
    server_id = serializers.CharField()
    registered_masters = serializers.IntegerField()
    peers = serializers.IntegerField()
    pending_media_tasks = serializers.IntegerField()
    failed_media_tasks = serializers.IntegerField()
    recent_conflicts = serializers.IntegerField()
    last_sync_at = serializers.DateTimeField(allow_null=True)
    pending_event_deliveries = serializers.IntegerField()
    failed_event_deliveries = serializers.IntegerField()
    oldest_pending_event_at = serializers.DateTimeField(allow_null=True)
