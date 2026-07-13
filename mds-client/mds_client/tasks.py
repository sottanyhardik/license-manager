"""
Celery task for scheduled mirror refresh.

Celery is OPTIONAL: the import is guarded so a consumer without Celery can still
install and use the client + management command. When Celery is present, wire
``mds_client.tasks.sync_masters`` into celery-beat (e.g. every 5 minutes — the
polling backstop from ADR-001 Decision 3) and/or trigger it from the MDS
webhook nudge for near-real-time refresh.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("mds_client.tasks")

try:
    from celery import shared_task

    _CELERY_AVAILABLE = True
except ImportError:  # Celery not installed — degrade to a plain callable.
    _CELERY_AVAILABLE = False

    def shared_task(*dargs, **dkwargs):  # type: ignore[misc]
        """No-op decorator so the module imports without Celery. The wrapped
        function stays directly callable; it just isn't a registered task."""

        def wrap(func):
            return func

        # Support both @shared_task and @shared_task(...) forms.
        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]
        return wrap


@shared_task(name="mds_client.sync_masters", bind=False, ignore_result=True)
def sync_masters():
    """Refresh the local mirror for all configured masters. Safe to run on a
    beat schedule and on webhook nudge. Returns a list of per-model summaries."""
    # Import here so the module loads even if Django/consumer settings aren't
    # ready at task-registration import time.
    from .sync import sync_all

    results = sync_all()
    summaries = [str(r) for r in results]
    logger.info("sync_masters complete: %s", summaries)
    return summaries
