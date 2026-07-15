"""
Local development settings with SQLite and managed=False patch.

Usage:
  DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver 8001

All managed=False models are patched to managed=True so that SQLite tables
are created automatically. This makes the full API work locally without a
production PostgreSQL connection.
"""
import os

from .dev import *  # noqa: F401, F403

# Use dedicated SQLite DB for local dev (separate from test DB)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get(
            "SQLITE_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "local-dev.sqlite3"),
        ),
        "OPTIONS": {"timeout": 20},
    }
}

# Patch all managed=False models to managed=True after app registry loads.
# This is done via a signal so it fires AFTER django.setup() completes.
def _patch_managed(sender, **kwargs):  # noqa: ARG001
    from django.apps import apps
    for model in apps.get_models():
        if not model._meta.managed:
            model._meta.managed = True

from django.db.models.signals import post_migrate  # noqa: E402

# Use post_setup equivalent — run immediately if app registry is already ready
try:
    from django.apps import apps
    if apps.ready:
        _patch_managed(None)
except Exception:
    pass

# Also connect to post_migrate so tables are created on migrate
post_migrate.connect(_patch_managed)

# Relax CORS for local dev
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
