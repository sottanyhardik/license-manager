import os

# Must be set BEFORE base.py is imported because base.py does os.environ["SECRET_KEY"]
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")  # noqa: S105

from .base import *  # noqa: F401, F403

# Remove health_check sub-apps that are not installed in the test virtualenv.
# health_check itself is installed but health_check.db / health_check.cache are
# optional extras that are not present — strip them to prevent ModuleNotFoundError.
INSTALLED_APPS = [
    app for app in INSTALLED_APPS  # noqa: F405
    if app not in ("health_check.db", "health_check.cache")
]

SECRET_KEY = "test-secret-key-not-for-production-use"  # noqa: S105
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# managed=False patching is handled by the conftest_managed pytest plugin.
# backend/conftest_managed.py runs after django.setup() via pytest_sessionstart,
# setting managed=True on every model so the SQLite test DB can create tables.
# Loaded via: pytest_plugins = ["conftest_managed"] in tests/conftest.py
# ---------------------------------------------------------------------------
