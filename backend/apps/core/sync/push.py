"""
Sync Push Client (Module 04)

Pushes local Master changes to all registered peer servers.

Used by:
- Post-save signals (when SYNC_PUSH_ON_SAVE=True)
- Celery periodic task (batch push)
- Management command (manual push)
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import SyncPeer, SyncCursor, SyncEvent, SyncPeerDelivery
from .registry import get_entry
from .service import get_changes_since, _serialize_instance, _get_model
from .media import get_media_info
from .mixins import SERVER_ID
from .credentials import token_for_peer

logger = logging.getLogger("sync.push")


def push_to_peer(peer: SyncPeer, events: list[dict[str, Any]]) -> bool:
    """Push a batch of sync events to a single peer.

    Returns True on success, False on failure.
    """
    if not events:
        return True
    token = token_for_peer(peer.server_id)
    if token is None:
        logger.error("Refusing sync push to %s: peer credential is not configured", peer.server_id)
        return False

    payload = json.dumps({
        "source_server": SERVER_ID,
        "events": events,
    }, default=str).encode("utf-8")

    url = f"{peer.base_url.rstrip('/')}/api/sync/push/"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Sync-Server-ID": SERVER_ID,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            logger.info(
                "Pushed %d events to %s: %d applied, %d skipped, %d errors",
                len(events), peer.server_id,
                len(result.get("applied", [])),
                len(result.get("skipped", [])),
                len(result.get("errors", [])),
            )
            return result.get("ok", False)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.error("Push to %s failed: %s", peer.server_id, exc)
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
        return False
    except Exception as exc:
        logger.exception("Unexpected error pushing to %s", peer.server_id)
        return False


def push_to_all_peers(events: list[dict[str, Any]]) -> dict[str, bool]:
    """Push events to all active peers. Returns {server_id: success}."""
    results = {}
    for peer in SyncPeer.objects.filter(is_active=True):
        result = push_to_peer(peer, events)
        results[peer.server_id] = result
        _record_delivery_result(peer, events, result)
    return results


def _record_delivery_result(peer: SyncPeer, events: list[dict[str, Any]], succeeded: bool) -> None:
    """Persist peer acknowledgement/failure; a failed push remains retryable."""
    now = timezone.now()
    for payload in events:
        raw_id = payload.get("event_id")
        if not raw_id:
            continue
        try:
            event = SyncEvent.objects.get(event_id=raw_id)
        except (SyncEvent.DoesNotExist, ValueError):
            continue
        delivery, _ = SyncPeerDelivery.objects.get_or_create(peer=peer, event=event)
        delivery.attempts += 1
        delivery.status = (SyncPeerDelivery.STATUS_ACKNOWLEDGED if succeeded else SyncPeerDelivery.STATUS_FAILED)
        delivery.acknowledged_at = now if succeeded else None
        delivery.last_error = "" if succeeded else "Peer push failed; retained for retry"
        delivery.save(update_fields=["attempts", "status", "acknowledged_at", "last_error"])


def pending_events_for_peer(peer: SyncPeer, *, limit: int = 100) -> list[dict[str, Any]]:
    """Materialise undelivered immutable events; safe after offline recovery."""
    delivered = SyncPeerDelivery.objects.filter(
        peer=peer, status=SyncPeerDelivery.STATUS_ACKNOWLEDGED,
    ).values("event_id")
    events = []
    for event in SyncEvent.objects.exclude(
        id__in=delivered,
    ).exclude(source_server=peer.server_id).order_by("id")[:limit]:
        payload = dict(event.payload)
        payload["event_id"] = str(event.event_id)
        payload.setdefault("source_server", event.source_server)
        payload.setdefault("source_version", event.source_version)
        payload.setdefault("at", event.occurred_at.isoformat())
        events.append(payload)
    return events


def push_pending_to_peer(peer: SyncPeer, *, limit: int = 100) -> bool:
    events = pending_events_for_peer(peer, limit=limit)
    if not events:
        return True
    succeeded = push_to_peer(peer, events)
    _record_delivery_result(peer, events, succeeded)
    return succeeded


def check_delete_on_peers(model_label: str, natural_key: dict) -> list[dict]:
    """Check all peers for FK references before allowing a delete.

    Returns a list of conflict responses from peers that have references.
    """
    conflicts = []
    # default=str: natural keys may hold dates/Decimals (e.g. ExchangeRateModel).
    payload = json.dumps({
        "model_label": model_label,
        "natural_key": natural_key,
    }, default=str).encode("utf-8")

    for peer in SyncPeer.objects.filter(is_active=True):
        token = token_for_peer(peer.server_id)
        if token is None:
            conflicts.append({
                "server": peer.server_id,
                "references": ["Peer credential is not configured"],
            })
            continue
        url = f"{peer.base_url.rstrip('/')}/api/sync/delete-check/"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "X-Sync-Server-ID": SERVER_ID,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if not result.get("safe", True):
                    conflicts.append({
                        "server": peer.server_id,
                        "references": result.get("references", []),
                    })
        except urllib.error.HTTPError as exc:
            try:
                if exc.code == 409:
                    result = json.loads(exc.read())
                    conflicts.append({
                        "server": peer.server_id,
                        "references": result.get("references", []),
                    })
                else:
                    logger.error("Delete check on %s failed: %s", peer.server_id, exc)
                    conflicts.append({
                        "server": peer.server_id,
                        "references": [f"Peer unreachable: {exc}"],
                    })
            finally:
                exc.close()
        except Exception as exc:
            logger.error("Delete check on %s failed: %s", peer.server_id, exc)
            conflicts.append({
                "server": peer.server_id,
                "references": [f"Peer unreachable: {exc}"],
            })

    return conflicts


def sync_from_peer(peer: SyncPeer) -> int:
    """Pull changes from a peer since our last cursor.

    Returns the number of events applied.
    """
    from .service import apply_sync_batch

    cursor, _ = SyncCursor.objects.get_or_create(peer=peer)
    token = token_for_peer(peer.server_id)
    if token is None:
        logger.error("Refusing sync pull from %s: peer credential is not configured", peer.server_id)
        return 0
    url = f"{peer.base_url.rstrip('/')}/api/sync/pull/"
    # The cursor identifies the peer's append-only outbox row, not time.  It
    # survives equal timestamps, reordering and local clock skew.
    if cursor.remote_event_cursor or not cursor.last_synced_at:
        url += "?" + urllib.parse.urlencode({"cursor": cursor.remote_event_cursor})
    else:
        # Upgrade compatibility for installations whose old cursor predates
        # migration 0018.  New durable cursors never take this branch.
        url += "?" + urllib.parse.urlencode({"since": cursor.last_synced_at.isoformat()})

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Sync-Server-ID": SERVER_ID,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            events = data.get("events", [])
            if not events:
                return 0

            result = apply_sync_batch(events)

            # Never acknowledge a partial batch.  The source's integer cursor
            # identifies an immutable event, so replay is safe and does not
            # depend on either machine's wall clock.
            if not result.errors:
                source_cursor = data.get("cursor")
                try:
                    source_cursor = int(source_cursor)
                except (TypeError, ValueError):
                    source_cursor = cursor.remote_event_cursor
                    # Compatibility status only for an old timestamp-only
                    # peer.  This value is never used to select future events.
                    watermark = data.get("cursor") or max(
                        (item.get("at") for item in events if item.get("at")), default=None,
                    )
                    cursor.last_synced_at = (
                        parse_datetime(watermark) if isinstance(watermark, str) else timezone.now()
                    )
                if source_cursor < cursor.remote_event_cursor:
                    logger.warning("Peer %s attempted to regress sync cursor", peer.server_id)
                    source_cursor = cursor.remote_event_cursor
                cursor.remote_event_cursor = source_cursor
                cursor.last_pull_at = timezone.now()
                cursor.save(update_fields=["remote_event_cursor", "last_synced_at", "last_pull_at"])
            else:
                logger.warning(
                    "Pull from %s had %d rejected event(s); cursor was not advanced",
                    peer.server_id, len(result.errors),
                )

            # Update peer last_seen
            peer.last_seen = timezone.now()
            peer.save(update_fields=["last_seen"])

            logger.info(
                "Pulled %d events from %s: %d applied, %d skipped, %d errors",
                len(events), peer.server_id,
                len(result.applied), len(result.skipped), len(result.errors),
            )
            return len(result.applied)

    except urllib.error.HTTPError as exc:
        logger.error("Pull from %s failed: %s", peer.server_id, exc)
        exc.close()
        return 0
    except Exception as exc:
        logger.error("Pull from %s failed: %s", peer.server_id, exc)
        return 0


def sync_from_all_peers() -> dict[str, int]:
    """Pull changes from all active peers. Returns {server_id: events_applied}."""
    results = {}
    for peer in SyncPeer.objects.filter(is_active=True):
        results[peer.server_id] = sync_from_peer(peer)
    return results
