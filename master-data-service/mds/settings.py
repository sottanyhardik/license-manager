"""
Settings for the Master-Data Service (MDS).

Standalone Django/DRF service — the sole write authority for the shared master
data (companies, ports, items, HS codes, SION norms, rates …). Consuming
projects keep a local read-mirror and talk to this service for writes + delta
pulls. See ../docs is in the main repo: docs/architecture/ADR-001-master-data-service.md
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default):
    """Parse a truthy env var; falls back to `default` (a bool) when unset."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# The test suite runs with DEBUG=False (its default) but over Django's HTTP
# test client and without a collectstatic manifest, so the prod-only transport
# security + whitenoise wiring would break it. pytest exports PYTEST_VERSION for
# the whole session, so we detect a test run and keep those pieces off there
# (real prod is unaffected). MDS_TESTING is an explicit manual override.
_TESTING = bool(os.getenv("PYTEST_VERSION")) or bool(os.getenv("MDS_TESTING"))

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
# In production ALLOWED_HOSTS MUST be real hosts (never "*"). The prod env file
# (.env.production.example) sets them explicitly; "*" is a dev-only default.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "masters",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise serves the Django admin's static files straight from the app
# process (no separate static server needed for the small admin bundle). It is
# only enabled when explicitly requested (USE_WHITENOISE) or in production, and
# only if the package is importable — so a dev checkout without whitenoise
# still boots. It must sit directly after SecurityMiddleware.
USE_WHITENOISE = _env_bool("USE_WHITENOISE", not DEBUG and not _TESTING)
if USE_WHITENOISE:
    try:
        import whitenoise  # noqa: F401
        MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
        STORAGES = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }
    except ImportError:
        # whitenoise not installed (dev) — fall back to Django's static serving.
        USE_WHITENOISE = False

ROOT_URLCONF = "mds.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mds.wsgi.application"

# Its OWN database — separate from any consuming project.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("MDS_DB_NAME", "master_data"),
        "USER": os.getenv("MDS_DB_USER", "master_data"),
        "PASSWORD": os.getenv("MDS_DB_PASS", "master_data"),
        "HOST": os.getenv("MDS_DB_HOST", "localhost"),
        "PORT": os.getenv("MDS_DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# collectstatic writes here (served by whitenoise, or by nginx via the
# /static/ alias in deploy/nginx-mds.conf). Gitignored (see .gitignore).
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Production security hardening -----------------------------------------
# All flags are env-gated and default to their prod-safe value only when
# DEBUG is False, so a dev run (DEBUG=True) stays plain-HTTP and boots without
# TLS. In production (DEBUG=False) these turn on automatically; each can still
# be overridden individually via env (e.g. disable HSTS until TLS is stable).
# _TESTING (defined above) keeps these off under pytest; real prod is unaffected.
if not DEBUG and not _TESTING:
    # Redirect any http:// request to https:// (nginx also does this; this is
    # defence in depth). Trust nginx's X-Forwarded-Proto so Django knows the
    # original request was already HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)

    # Secure, HttpOnly cookies over HTTPS only.
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", True)

    # HSTS — tell browsers to always use HTTPS. Default 1 year; only enable
    # preload once you intend to submit the domain.
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", False)

    # Stop browsers MIME-sniffing responses (X-Content-Type-Options: nosniff).
    SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("SECURE_CONTENT_TYPE_NOSNIFF", True)

# --- DRF -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "masters.auth.ServiceTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "masters.auth.HasServiceScope",
    ],
    "DEFAULT_PAGINATION_CLASS": "masters.pagination.MasterCursorPagination",
    "PAGE_SIZE": 200,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# --- Service-to-service tokens ---------------------------------------------
# Map: token -> scope ("read" or "write"). Set MDS_TOKENS as
# "token1:write,token2:read" in the environment. A "write" token also reads.
VALID_SERVICE_TOKEN_SCOPES = {"read", "write"}


def _parse_tokens(raw):
    out = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        token, _, scope = pair.partition(":")
        token = token.strip()
        if not token:
            continue
        scope = (scope.strip() or "read").lower()
        if scope not in VALID_SERVICE_TOKEN_SCOPES:
            raise ValueError(f"Invalid MDS token scope {scope!r}; expected 'read' or 'write'.")
        out[token] = scope
    return out


MDS_SERVICE_TOKENS = _parse_tokens(os.getenv("MDS_TOKENS", ""))

# --- Object storage (media) — configured in a later phase (Decision 5) -----
# django-storages[s3] + a private MinIO/S3 bucket. Left as local storage for
# the skeleton so the service boots without external infra.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
