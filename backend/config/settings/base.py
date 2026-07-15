"""
Base Django settings for License Manager.

Loaded by dev / prod / test sub-modules via `from .base import *`.
Never use this module directly as DJANGO_SETTINGS_MODULE.
"""
import os
import re as _re
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# BASE_DIR = backend/  (2 parents up from config/settings/base.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env if present (dev/CI convenience; prod uses real env vars)
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = False

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "simple_history",
    # django-health-check ≥ 4.x dropped the sub-package structure;
    # checks are registered as plugins via HEALTH_CHECK setting instead.
    "health_check",
    # Local
    "shared",
    "apps.accounts",
    "apps.core",
    "apps.license",
    "apps.allotment",
    "apps.bill_of_entry",
    "apps.tasks",
    "apps.dashboard",
    "apps.reports",
    "apps.trade",
    "apps.notifications",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must be before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Resolution order (first match wins):
#   1. DATABASE_URL env var (full DSN, e.g. from Docker / Heroku / Railway)
#   2. Individual DB_NAME / DB_USER / DB_PASS / DB_HOST / DB_PORT env vars
#      (same naming convention as the legacy backend's lmanagement/settings.py)
#   3. SQLite fallback for local development without any env vars set
#
# Production ALWAYS sets DATABASE_URL or DB_* vars — the SQLite fallback is
# intentionally kept so `manage.py check` works in CI without a live database.
_db_url = os.environ.get("DATABASE_URL")

if not _db_url:
    # Build a PostgreSQL DSN from the legacy env var naming convention
    _db_name = os.environ.get("DB_NAME")
    _db_user = os.environ.get("DB_USER")
    _db_pass = os.environ.get("DB_PASS", "")
    _db_host = os.environ.get("DB_HOST", "localhost")
    _db_port = os.environ.get("DB_PORT", "5432")

    if _db_name and _db_user:
        # All required fields present — construct a PostgreSQL DSN
        _db_url = f"postgresql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
    else:
        # No database config at all — use SQLite for local dev / CI
        _db_url = "sqlite:///db.sqlite3"

_conn_max_age = 0 if _db_url.startswith("sqlite") else 60

# dj_database_url infers the correct Django backend from the URL scheme:
#   sqlite:///  → django.db.backends.sqlite3
#   postgresql:// / postgres:// → django.db.backends.postgresql
# Do NOT pass engine= here — it would override the scheme-based detection and
# force PostgreSQL even for SQLite URLs (causing the "database does not exist"
# error when the sqlite filename is used as a Postgres DB name).
DATABASES = {
    "default": dj_database_url.config(
        default=_db_url,
        conn_max_age=_conn_max_age,
    )
}

# ---------------------------------------------------------------------------
# Caches — django-redis
# ---------------------------------------------------------------------------
# REDIS_URL is the base URL without a DB suffix (e.g. redis://localhost:6379).
# DB isolation prevents a cache flush from wiping in-flight Celery messages:
#   /1  — Django cache
#   /2  — Celery broker
#   /3  — Celery result backend
_redis_base = os.environ.get("REDIS_URL", "redis://localhost:6379")
# Strip any trailing /N from the base URL so we can append our own DB number.
_redis_base = _re.sub(r"/\d+$", "", _redis_base.rstrip("/"))

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{_redis_base}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth model
# ---------------------------------------------------------------------------
# managed=False proxy over the shared accounts_user table.
# The legacy backend owns the table; we only read/authenticate against it.
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
    },
    "DEFAULT_PAGINATION_CLASS": "shared.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "shared.exceptions.custom_exception_handler",
}

# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------------------------------------------------------------------------
# DRF Spectacular (OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "License Manager API v1",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o
]

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = f"{_redis_base}/2"
CELERY_RESULT_BACKEND = f"{_redis_base}/3"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
