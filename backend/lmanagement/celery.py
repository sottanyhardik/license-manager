# FILE: lmanagement/celery.py
# Place this next to settings.py / wsgi.py in your Django project package.

from __future__ import annotations

import os
from celery import Celery
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

    # Update balance_cif every 30 minutes
    "update-balances-every-30-minutes": {
        "task": "update_all_balances_periodic",
        "schedule": crontab(minute='*/30'),  # Every 30 minutes
        "args": (),
        "options": {
            "expires": 1800,  # Task expires after 30 minutes
        }
    },

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


@app.task(bind=True)
def debug_task(self):
    # very small debug helper; not used in production
    print(f"Celery debug task running: request id: {self.request!r}")
    return "debug"
