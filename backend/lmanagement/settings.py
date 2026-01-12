"""
Django settings for lmanagement project (cleaned + modernized).
For Django 5.x with DRF + JWT + Celery + Redis + Vite/React frontend.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.urls import reverse_lazy

# ---------------------------------------------------------------------
# Base Paths
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-this-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS",
                          "127.0.0.1,localhost,139.59.92.226,labdhi.duckdns.org,143.110.252.201,license-manager.duckdns.org,178.128.58.219,165.232.185.220,license-tractor.duckdns.org").split(
    ",")

# HTTPS Settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "False").lower() == "true"

# ---------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # Third-party
    "django_extensions",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "whitenoise.runserver_nostatic",

    # Local apps
    "accounts",
    "core",
    "license",
    "bill_of_entry",
    "allotment",
    "trade",
]

# ---------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # corsheaders middleware must be high so preflight responses are handled early
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Disable CSRF for API endpoints (JWT authenticated)
    "core.middleware.DisableCSRFForAPIMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "lmanagement.urls"

# ---------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR.parent / "frontend" / "dist",  # React build folder (first priority)
            BASE_DIR / "templates",
        ],
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

WSGI_APPLICATION = "lmanagement.wsgi.application"

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "lmanagement"),
        "USER": os.getenv("DB_USER", "lmanagement"),
        "PASSWORD": os.getenv("DB_PASS", "lmanagement"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# ---------------------------------------------------------------------
# Password Validation
# ---------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR.parent / "frontend" / "dist" / "assets",  # React build assets
]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# Disable login redirects for API-only project (no HTML views)
# LOGIN_URL = reverse_lazy("login")
# LOGIN_REDIRECT_URL = reverse_lazy("dashboard")
# LOGOUT_REDIRECT_URL = reverse_lazy("login")

# ---------------------------------------------------------------------
# REST Framework & JWT Auth
# ---------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.authentication.JWTAuthenticationFromQueryParam",
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DATETIME_FORMAT": "%d-%m-%Y %H:%M",
    "DATE_FORMAT": "%d-%m-%Y",
    # Disable CSRF for API endpoints when using JWT authentication
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    # Enable refresh rotation
    "ROTATE_REFRESH_TOKENS": True,  # ✔ new refresh each time
    "BLACKLIST_AFTER_ROTATION": True,  # ✔ prevents reuse

    "AUTH_HEADER_TYPES": ("Bearer",),
}
# ---------------------------------------------------------------------
# Celery & Redis
# ---------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ---------------------------------------------------------------------
# Caching (Redis)
# ---------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# ---------------------------------------------------------------------
# CORS (for Vite / React frontend)
# ---------------------------------------------------------------------
# Note: For development we explicitly whitelist origins (do not use allow-all in production).
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # default Vite port
    "http://127.0.0.1:5173",
    "http://localhost:3000",  # sometimes Vite is proxied to 3000 in dev
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Django serving React frontend
    "http://127.0.0.1:8000",
    "http://139.59.92.226",  # Production server (Labdhi)
    "http://139.59.92.226:8000",
    "https://labdhi.duckdns.org",  # Production domain (Labdhi)
    "http://143.110.252.201:8000",  # Server IP
    "https://license-manager.duckdns.org",  # Production domain with SSL
    "http://165.232.185.220",  # Tractor server IP (HTTP)
    "https://165.232.185.220",  # Tractor server IP (HTTPS)
    "https://license-tractor.duckdns.org",  # Production domain (Tractor)
]

# Allow cookies (credentials) across origins when frontend sends withCredentials
CORS_ALLOW_CREDENTIALS = True

# Extend allowed headers to include CSRF and Authorization (case-insensitive)
try:
    # import default headers from corsheaders if available
    from corsheaders.defaults import default_headers

    CORS_ALLOW_HEADERS = list(default_headers) + [
        "X-CSRFToken",
        "x-csrftoken",
        "Authorization",
        "authorization",
    ]
except Exception:
    # fallback - minimal safe set
    CORS_ALLOW_HEADERS = [
        "accept",
        "accept-encoding",
        "authorization",
        "content-type",
        "origin",
        "user-agent",
        "x-csrftoken",
        "x-requested-with",
    ]

# Optional: expose headers to browser
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken", "Authorization"]

# CSRF trusted origins for Django's CSRF checks (if you use session auth)
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://139.59.92.226",
    "http://139.59.92.226:8000",
    "https://labdhi.duckdns.org",
    "http://143.110.252.201:8000",
    "https://license-manager.duckdns.org",
    "http://165.232.185.220",
    "https://165.232.185.220",
    "https://license-tractor.duckdns.org",
]

# ---------------------------------------------------------------------
# Email (file backend for dev)
# ---------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Optional: also set a from email for clarity
DEFAULT_FROM_EMAIL = "info@labdhimercantile.com"
FRONTEND_URL = "http://localhost:5173"  # update for production

# ---------------------------------------------------------------------
# App-specific Config
# ---------------------------------------------------------------------
EXPIRY_DAY = 60
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000
