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
        """Push local changes to all peers."""
        if not getattr(settings, "SYNC_ENABLED", False):
            return "Sync disabled"
        from .service import get_changes_since
        from .push import push_to_all_peers
        events = get_changes_since(since)
        if events:
            results = push_to_all_peers(events)
            return {k: v for k, v in results.items()}
        return "No changes"

except ImportError:
    # Celery not installed — provide no-op stubs
    def pull_from_peers():
        logger.warning("Celery not installed; sync tasks unavailable")

    def process_media_tasks():
        logger.warning("Celery not installed; sync tasks unavailable")

    def push_changes(since=None):
        logger.warning("Celery not installed; sync tasks unavailable")
