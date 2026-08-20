"""
Sync API Views (Module 04)

Peer-to-peer sync endpoints:
- POST /api/sync/push/       — receive sync events from a peer
- GET  /api/sync/pull/        — return changes since a timestamp
- POST /api/sync/delete-check/ — check if a delete is safe
- GET  /api/sync/status/      — sync health/status
- GET  /api/sync/media/download/ — serve a media file to a peer
- GET  /api/sync/conflicts/   — recent conflict log
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    SyncConflictLog, SyncPeer, SyncCursor, MediaSyncTask, SyncEvent,
    SyncPeerDelivery,
)
from .registry import get_entry, get_all_entries, get_model_labels
from .service import (
    apply_sync_batch,
    get_changes_since,
    _check_fk_references,
    _get_model,
    _natural_key_filter,
    _nk_string,
)
from .media import create_media_tasks
from .mixins import SERVER_ID
from .serializers import (
    SyncPushSerializer,
    SyncBatchResultSerializer,
    SyncPullRequestSerializer,
    DeleteCheckSerializer,
    DeleteCheckResultSerializer,
    SyncStatusSerializer,
)
from .authentication import PeerTokenAuthentication

logger = logging.getLogger("sync.views")

#: Upper bound for GET /api/sync/conflicts/?limit=
MAX_CONFLICT_PAGE = 1000


class PeerSyncAPIView(APIView):
    """Private API surface accessible only to registered sync peers."""

    authentication_classes = [PeerTokenAuthentication]


class SyncPushView(PeerSyncAPIView):
    """Receive a batch of sync events from a peer server.

    POST /api/sync/push/
    Body: { "source_server": "...", "events": [...] }
    """
    def post(self, request):
        serializer = SyncPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        events = serializer.validated_data["events"]
        source_server = serializer.validated_data["source_server"]
        if source_server != request.auth.server_id:
            return Response(
                {"detail": "source_server must match the authenticated sync peer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Override source_server in each event for consistency
        for event in events:
            event["source_server"] = source_server

            # Handle media metadata if present
            media_data = event.pop("media", {})
            if media_data:
                entry = get_entry(event["model_label"])
                if entry and entry.media_fields:
                    nk_str = "|".join(
                        str(event["data"].get(k, "")) for k in entry.natural_key
                    )
                    create_media_tasks(
                        event["model_label"], nk_str, media_data, source_server,
                    )

        result = apply_sync_batch(events)

        # Log conflicts
        for r in result.skipped:
            if r.conflict:
                SyncConflictLog.objects.create(
                    model_label=r.model_label,
                    natural_key=r.natural_key,
                    op=r.op,
                    source_server=source_server,
                    source_version=0,
                    detail=r.conflict_detail,
                )
        for r in result.errors:
            if r.conflict:
                SyncConflictLog.objects.create(
                    model_label=r.model_label,
                    natural_key=r.natural_key,
                    op=r.op,
                    source_server=source_server,
                    source_version=0,
                    detail=r.conflict_detail or r.error,
                )

        # Update peer last_seen
        from django.utils import timezone as tz
        SyncPeer.objects.filter(server_id=source_server).update(
            last_seen=tz.now()
        )

        out = SyncBatchResultSerializer({
            "applied": [vars(r) for r in result.applied],
            "skipped": [vars(r) for r in result.skipped],
            "errors": [vars(r) for r in result.errors],
            "total": result.total,
            "ok": result.ok,
        })
        return Response(out.data, status=status.HTTP_200_OK)


class SyncPullView(PeerSyncAPIView):
    """Return changes since a given timestamp (offline recovery).

    GET /api/sync/pull/?since=2024-01-01T00:00:00Z
    """
    def get(self, request):
        since = request.query_params.get("since")
        raw_cursor = request.query_params.get("cursor")
        try:
            event_cursor = max(0, int(raw_cursor)) if raw_cursor is not None else None
        except (TypeError, ValueError):
            event_cursor = None
        events = get_changes_since(since, cursor=event_cursor)

        # Optionally filter by model_labels
        model_labels = request.query_params.getlist("model_label")
        if model_labels:
            events = [e for e in events if e["model_label"] in model_labels]

        # A receiver must acknowledge the source watermark, never its own wall
        # clock.  Advancing a local cursor to ``now()`` can lose a change that
        # committed on this server while the response was in flight.
        # Integer outbox cursor is an acknowledgement of a concrete immutable
        # record; do not substitute this server's wall clock.
        response = {
            "server_id": SERVER_ID,
            "events": events,
            "count": len(events),
        }
        if event_cursor is not None:
            response["cursor"] = events[-1].get("cursor") if events else event_cursor
        return Response(response)


class DeleteCheckView(PeerSyncAPIView):
    """Check if a delete is safe (no FK references on this server).

    POST /api/sync/delete-check/
    Body: { "model_label": "core.CompanyModel", "natural_key": {"iec": "C001"} }

    Returns 200 with safe=True/False and list of references.
    """
    def post(self, request):
        serializer = DeleteCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        model_label = serializer.validated_data["model_label"]
        nk_data = serializer.validated_data["natural_key"]

        entry = get_entry(model_label)
        if entry is None:
            return Response(
                {"error": f"Unknown model_label: {model_label}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Model = _get_model(model_label)
        nk_str = _nk_string(entry, nk_data)
        try:
            nk_filter = _natural_key_filter(entry, nk_data)
        except ValueError as exc:
            # Incomplete / unusable natural key is a client error, not a 500.
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instance = Model.objects.get(**nk_filter)
        except Model.MultipleObjectsReturned:
            # Ambiguous natural key: refuse the delete rather than guess.
            return Response(
                DeleteCheckResultSerializer({
                    "model_label": model_label,
                    "natural_key": nk_str,
                    "safe": False,
                    "references": [
                        f"Ambiguous natural key: multiple {model_label} rows match"
                    ],
                }).data,
                status=status.HTTP_409_CONFLICT,
            )
        except Model.DoesNotExist:
            return Response(
                DeleteCheckResultSerializer({
                    "model_label": model_label,
                    "natural_key": nk_str,
                    "safe": True,
                    "references": [],
                }).data
            )

        refs = _check_fk_references(instance)
        result = {
            "model_label": model_label,
            "natural_key": nk_str,
            "safe": len(refs) == 0,
            "references": refs,
        }

        resp_status = status.HTTP_200_OK if not refs else status.HTTP_409_CONFLICT
        return Response(
            DeleteCheckResultSerializer(result).data,
            status=resp_status,
        )


class SyncStatusView(PeerSyncAPIView):
    """Sync health and status dashboard.

    GET /api/sync/status/
    """
    def get(self, request):
        from django.utils import timezone as tz
        from datetime import timedelta

        now = tz.now()
        recent_cutoff = now - timedelta(hours=24)

        data = {
            "server_id": SERVER_ID,
            "registered_masters": len(get_model_labels()),
            "peers": SyncPeer.objects.filter(is_active=True).count(),
            "pending_media_tasks": MediaSyncTask.objects.filter(
                status=MediaSyncTask.STATUS_PENDING,
            ).count(),
            "failed_media_tasks": MediaSyncTask.objects.filter(
                status=MediaSyncTask.STATUS_FAILED,
            ).count(),
            "recent_conflicts": SyncConflictLog.objects.filter(
                created_at__gte=recent_cutoff,
            ).count(),
            "last_sync_at": SyncCursor.objects.order_by(
                "-last_synced_at"
            ).values_list("last_synced_at", flat=True).first(),
            "pending_event_deliveries": SyncPeerDelivery.objects.exclude(
                status=SyncPeerDelivery.STATUS_ACKNOWLEDGED,
            ).count(),
            "failed_event_deliveries": SyncPeerDelivery.objects.filter(
                status=SyncPeerDelivery.STATUS_FAILED,
            ).count(),
            "oldest_pending_event_at": SyncEvent.objects.filter(
                deliveries__status__in=[
                    SyncPeerDelivery.STATUS_PENDING,
                    SyncPeerDelivery.STATUS_FAILED,
                ],
            ).order_by("created_at").values_list("created_at", flat=True).first(),
        }
        return Response(SyncStatusSerializer(data).data)


class MediaDownloadView(PeerSyncAPIView):
    """Serve a media file to a peer for media sync.

    GET /api/sync/media/download/?path=companies/logos/abc.png
    """
    def get(self, request):
        media_path = request.query_params.get("path")
        if not media_path:
            return Response(
                {"error": "Missing 'path' parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Security: prevent path traversal
        if ".." in media_path or media_path.startswith("/"):
            return Response(
                {"error": "Invalid path"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        full_path = Path(settings.MEDIA_ROOT) / media_path
        # is_file() (not exists()): a directory would otherwise reach open()
        # and raise IsADirectoryError → 500.
        if not full_path.is_file():
            raise Http404("Media file not found")

        content_type, _ = mimetypes.guess_type(str(full_path))
        return FileResponse(
            open(full_path, "rb"),
            content_type=content_type or "application/octet-stream",
        )


class SyncConflictLogView(PeerSyncAPIView):
    """View recent sync conflicts.

    GET /api/sync/conflicts/?since=2024-01-01T00:00:00Z&limit=50
    """
    def get(self, request):
        since = request.query_params.get("since")
        try:
            limit = int(request.query_params.get("limit", "100"))
        except (TypeError, ValueError):
            return Response(
                {"error": "'limit' must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Guard the slice: a negative bound raises, an unbounded one is a DoS.
        limit = max(1, min(limit, MAX_CONFLICT_PAGE))

        qs = SyncConflictLog.objects.all()
        if since:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(created_at__gt=dt)

        conflicts = list(qs.order_by("-created_at")[:limit].values())
        return Response({
            "conflicts": conflicts,
            "count": len(conflicts),
        })
