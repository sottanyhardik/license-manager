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

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
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
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
def _parse_tokens(raw):
    out = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        token, _, scope = pair.partition(":")
        out[token.strip()] = (scope.strip() or "read").lower()
    return out


MDS_SERVICE_TOKENS = _parse_tokens(os.getenv("MDS_TOKENS", ""))

# --- Object storage (media) — configured in a later phase (Decision 5) -----
# django-storages[s3] + a private MinIO/S3 bucket. Left as local storage for
# the skeleton so the service boots without external infra.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
