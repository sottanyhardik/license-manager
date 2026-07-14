import logging
import os

from celery import Celery

# Do NOT provide a fallback — force operators to set this explicitly.
# In production, set DJANGO_SETTINGS_MODULE=config.settings.prod in the
# systemd unit or Docker environment.
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    raise RuntimeError(
        "DJANGO_SETTINGS_MODULE must be set before starting Celery. "
        "Use config.settings.prod in production."
    )

app = Celery("license_manager")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

logger = logging.getLogger(__name__)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    logger.debug("Request: %r", self.request)
