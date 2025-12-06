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
