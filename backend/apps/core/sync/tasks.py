"""
Sync Celery Tasks (Module 04)

Periodic tasks for:
- Pulling changes from all peers (offline recovery)
- Processing pending media sync tasks
- Pushing local changes to peers
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("sync.tasks")

try:
    from celery import shared_task

    @shared_task(name="sync.pull_from_peers")
    def pull_from_peers():
        """Pull changes from all active peers."""
        if not getattr(settings, "SYNC_ENABLED", False):
            return "Sync disabled"
        from .push import sync_from_all_peers
        results = sync_from_all_peers()
        return {k: v for k, v in results.items()}

    @shared_task(name="sync.process_media_tasks")
    def process_media_tasks():
        """Process pending media sync downloads."""
        if not getattr(settings, "SYNC_ENABLED", False):
            return "Sync disabled"
        from .media import run_media_sync_worker
        run_media_sync_worker()
        return "OK"

    @shared_task(name="sync.push_changes")
    def push_changes(since=None):
        """Retry every unacknowledged immutable event to every active peer."""
        if not getattr(settings, "SYNC_ENABLED", False):
            return "Sync disabled"
        from .models import SyncPeer, SyncEvent
        from .push import push_pending_to_peer, push_to_all_peers
        # One-release compatibility path for a database that has historical
        # MasterChange rows but has not yet emitted its first immutable event.
        # Once the ledger exists, timestamp reconstruction is never used.
        if not SyncEvent.objects.exists():
            from .service import get_changes_since
            events = get_changes_since(since)
            return push_to_all_peers(events) if events else "No changes"
        return {
            peer.server_id: push_pending_to_peer(peer)
            for peer in SyncPeer.objects.filter(is_active=True)
        }

except ImportError:
    # Celery not installed — provide no-op stubs
    def pull_from_peers():
        logger.warning("Celery not installed; sync tasks unavailable")

    def process_media_tasks():
        logger.warning("Celery not installed; sync tasks unavailable")

    def push_changes(since=None):
        logger.warning("Celery not installed; sync tasks unavailable")
