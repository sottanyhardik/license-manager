# FILE: lmanagement/celery.py
# Place this next to settings.py / wsgi.py in your Django project package.

from __future__ import annotations

import os
import sys

# macOS fork-safety: the prefork pool forks worker processes, and on macOS a
# forked child crashes (SIGSEGV/SIGABRT) the moment it touches an Objective-C /
# system framework unless this flag is set BEFORE the fork. Set it here (in the
# worker's main process, before workers fork) so local dev on macOS doesn't
# segfault. On Linux (production) the variable is meaningless and ignored, so
# this is a no-op there. If workers still crash on macOS/Python 3.14, run the
# worker with a non-forking pool: `--pool=solo` (see run-celery-dev.sh).
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from celery import Celery, signals
from celery.schedules import crontab
from django.conf import settings

# set default Django settings module if not set in environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "lmanagement.settings"))

app = Celery("lmanagement")

# Load configuration from Django settings, using the CELERY_ namespace:
# e.g. in settings.py you can set CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TIMEZONE, etc.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Recommended safe defaults (JSON serializer, accept only json)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)

# Auto-discover tasks from all installed apps (looks for tasks.py modules)
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Periodic tasks schedule
app.conf.beat_schedule = {
    # Sync all licenses daily at 12:00 AM IST (6:30 PM UTC previous day)
    # IST = UTC + 5:30, so 12:00 AM IST = 6:30 PM UTC (18:30)
    "sync-licenses-daily-midnight-ist": {
        "task": "license.tasks.sync_all_licenses",
        "schedule": crontab(minute=30, hour=18),  # 18:30 UTC = 12:00 AM IST
        "args": (),
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        }
    },

    # Update balances twice daily: 11 AM and 8 PM IST
    # 11 AM IST = 5:30 AM UTC (5:30)
    # 8 PM IST = 2:30 PM UTC (14:30)
    "update-balances-11am-ist": {
        "task": "identify_licenses_needing_update",
        "schedule": crontab(minute=30, hour=5),  # 5:30 AM UTC = 11:00 AM IST
        "args": (),
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        }
    },
    "update-balances-8pm-ist": {
        "task": "identify_licenses_needing_update",
        "schedule": crontab(minute=30, hour=14),  # 2:30 PM UTC = 8:00 PM IST
        "args": (),
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        }
    },

    # NOTE: DGFT's WAF blocks our DigitalOcean server IPs (403), so we don't
    # schedule `core.tasks.fetch_exchange_rates` on Celery beat here.  Instead,
    # the fetch runs from a local cron on the dev machine and pushes the result
    # to license-manager; the existing master-sync cron replicates it to the
    # other servers.  See: fetch-and-push-rates.sh

    # Cleanup old task records every hour
    "cleanup-old-tasks-hourly": {
        "task": "cleanup_old_task_records",
        "schedule": crontab(minute=0),  # Every hour at :00
        "args": (),
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        }
    },
}

# ---------------------------------------------------------------------------
# Master-Data Service mirror sync (ADR-001, Decision 3) — OFF by default.
#
# When MDS is enabled, poll the central service every 5 minutes to refresh the
# local read-only mirror (the "polling backstop" that self-heals a missed
# webhook nudge). This is registered ONLY when settings.MDS_ENABLED is true, so
# with MDS off nothing extra is scheduled and behavior is identical to before.
# The task itself (mds_client.sync_masters) is safe to call — it no-ops if the
# client isn't installed — but we still guard here to avoid scheduling a task
# that would never do useful work.
# ---------------------------------------------------------------------------
if getattr(settings, "MDS_ENABLED", False):
    app.conf.beat_schedule["mds-sync-masters-every-5-min"] = {
        "task": "mds_client.sync_masters",
        "schedule": crontab(minute="*/5"),  # every 5 minutes
        "args": (),
        "options": {
            "expires": 300,  # skip a run rather than pile up if a beat is late
        },
    }


@signals.worker_process_init.connect
def reset_db_connections(**kwargs):
    """Close inherited DB connections after each worker fork so psycopg2 gets a fresh connection."""
    from django.db import connections
    for conn in connections.all():
        conn.close()


@app.task(bind=True)
def debug_task(self):
    # very small debug helper; not used in production
    print(f"Celery debug task running: request id: {self.request!r}")
    return "debug"
