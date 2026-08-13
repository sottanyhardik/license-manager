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

from .models import SyncPeer, SyncCursor
from .registry import get_entry
from .service import get_changes_since, _serialize_instance, _get_model
from .media import get_media_info
from .mixins import SERVER_ID

logger = logging.getLogger("sync.push")


def push_to_peer(peer: SyncPeer, events: list[dict[str, Any]]) -> bool:
    """Push a batch of sync events to a single peer.

    Returns True on success, False on failure.
    """
    if not events:
        return True

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
            "Authorization": f"Bearer {peer.auth_token}" if peer.auth_token else "",
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
        return False
    except Exception as exc:
        logger.exception("Unexpected error pushing to %s", peer.server_id)
        return False


def push_to_all_peers(events: list[dict[str, Any]]) -> dict[str, bool]:
    """Push events to all active peers. Returns {server_id: success}."""
    results = {}
    for peer in SyncPeer.objects.filter(is_active=True):
        results[peer.server_id] = push_to_peer(peer, events)
    return results


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
        url = f"{peer.base_url.rstrip('/')}/api/sync/delete-check/"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {peer.auth_token}" if peer.auth_token else "",
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
    since = cursor.last_synced_at.isoformat() if cursor.last_synced_at else ""

    url = f"{peer.base_url.rstrip('/')}/api/sync/pull/"
    if since:
        # Must be percent-encoded: an ISO timestamp ends in "+00:00" and a raw
        # "+" is decoded as a space by the peer, so the cursor would be silently
        # dropped and every pull would return the peer's entire change feed.
        url += "?" + urllib.parse.urlencode({"since": since})

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {peer.auth_token}" if peer.auth_token else "",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            events = data.get("events", [])
            if not events:
                return 0

            result = apply_sync_batch(events)

            # Update cursor
            cursor.last_synced_at = timezone.now()
            cursor.last_pull_at = timezone.now()
            cursor.save()

            # Update peer last_seen
            peer.last_seen = timezone.now()
            peer.save(update_fields=["last_seen"])

            logger.info(
                "Pulled %d events from %s: %d applied, %d skipped, %d errors",
                len(events), peer.server_id,
                len(result.applied), len(result.skipped), len(result.errors),
            )
            return len(result.applied)

    except Exception as exc:
        logger.error("Pull from %s failed: %s", peer.server_id, exc)
        return 0


def sync_from_all_peers() -> dict[str, int]:
    """Pull changes from all active peers. Returns {server_id: events_applied}."""
    results = {}
    for peer in SyncPeer.objects.filter(is_active=True):
        results[peer.server_id] = sync_from_peer(peer)
    return results
