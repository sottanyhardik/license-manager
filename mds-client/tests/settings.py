"""
Minimal Django settings for running the mds_client test suite.

No live MDS and no real DB server needed — in-memory SQLite + a tiny local test
app (`tests.mirror_app`) that provides mirror models the sync path upserts into.
"""

SECRET_KEY = "test-secret-key-not-for-production"

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "mds_client",
    "tests.mirror_app",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- mds_client config ------------------------------------------------------
MDS_BASE_URL = "https://masters.test.local/api/v1/"
MDS_TOKEN = "test-write-token"
MDS_TIMEOUT = (1, 5)
MDS_MAX_RETRIES = 0  # keep tests fast/deterministic
MDS_BACKOFF_FACTOR = 0

MDS_MODELS = {
    "mirror_app.CompanyMirror": {
        "endpoint": "companies",
        "natural_key": "iec",
        "mirror_model": "mirror_app.CompanyMirror",
        # change-feed label MDS emits for this model
        "mds_model_label": "mirror_app.CompanyMirror",
    },
    "mirror_app.PortMirror": {
        "endpoint": "ports",
        "natural_key": "code",
        "mirror_model": "mirror_app.PortMirror",
        "mds_model_label": "mirror_app.PortMirror",
    },
}

LOGGING_CONFIG = None
