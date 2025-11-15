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


# Optional: example periodic tasks schedule (uncomment & edit in production)
# app.conf.beat_schedule = {
#     "example-every-midnight": {
#         "task": "accounts.tasks.send_daily_report",  # update to your task path
#         "schedule": crontab(minute=0, hour=0),
#         "args": (),
#     },
#}


@app.task(bind=True)
def debug_task(self):
    # very small debug helper; not used in production
    print(f"Celery debug task running: request id: {self.request!r}")
    return "debug"
