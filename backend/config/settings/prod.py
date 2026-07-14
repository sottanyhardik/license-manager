"""
Production settings for license-manager-v1 (backend/).

Extends base.py.  All secrets and host-specific values MUST come from
environment variables or the server's .env file — never hardcoded here.

Required env vars (no defaults — app refuses to start if missing):
  SECRET_KEY          Django secret key
  ALLOWED_HOSTS       Comma-separated list, e.g. "license-manager.duckdns.org"
  DATABASE_URL        Postgres DSN

Optional env vars (sensible defaults shown):
  MEDIA_ROOT          Path for user-uploaded files (default: backend/media)
  REDIS_URL           Celery/cache broker (default: redis://localhost:6379/2)
  CORS_ALLOWED_ORIGINS  Comma-separated origins (default: empty)
"""

import os

from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core (enforce — base sets defaults, prod must tighten)
# ---------------------------------------------------------------------------
DEBUG = False

# base.py already reads SECRET_KEY from os.environ["SECRET_KEY"] (hard fail if
# missing).  ALLOWED_HOSTS is read from os.environ.get(...) in base; prod
# re-asserts it so an empty list in prod raises immediately on startup.
_allowed = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if not _allowed:
    raise RuntimeError("ALLOWED_HOSTS env var is required in production — set it before starting gunicorn.")
ALLOWED_HOSTS = _allowed

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True  # belt-and-suspenders; header deprecated in modern browsers

# Tell Django that the nginx reverse-proxy sets X-Forwarded-Proto when the
# original request was HTTPS.  Required for SECURE_SSL_REDIRECT to work
# correctly when gunicorn sits behind nginx.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
# BASE_DIR is declared in base.py (Path(__file__).parent.parent.parent = backend/)
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405  — BASE_DIR imported via *
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))  # noqa: F405

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/license-manager-v1/django.log",
            "maxBytes": 10 * 1024 * 1024,   # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            # supervisor captures stdout/stderr; keep console for supervisor-out.log
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.security": {
            # Log security events (SuspiciousOperation etc.) at INFO so they
            # are always visible without enabling root DEBUG.
            "handlers": ["file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Celery — production broker / backend must come from env (no hardcoded DB)
# ---------------------------------------------------------------------------
# base.py computes CELERY_BROKER_URL / CELERY_RESULT_BACKEND from REDIS_URL
# with fixed DB suffixes /2 and /3.  In production the operator may want to
# point at a dedicated Redis instance or a different DB number, so we allow
# full DSN overrides via explicit env vars.
_celery_broker = os.environ.get("CELERY_BROKER_URL")
if _celery_broker:
    CELERY_BROKER_URL = _celery_broker

_celery_backend = os.environ.get("CELERY_RESULT_BACKEND")
if _celery_backend:
    CELERY_RESULT_BACKEND = _celery_backend
