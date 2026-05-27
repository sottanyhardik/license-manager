# FILE: lmanagement/settings.py
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
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "local-dev-only-secret-key-change-for-production-7f8e6d5c4b3a2910",
)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS",
                          "127.0.0.1,localhost,139.59.92.226,labdhi.duckdns.org,143.110.252.201,license-manager.duckdns.org,178.128.58.219,165.232.185.220,license-tractor.duckdns.org").split(
    ",")

# HTTPS Settings
# When DEBUG=True (dev server, HTTP only) these are automatically off.
# When DEBUG=False (production) these default to on — can be overridden via env vars.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
_https_default = "False" if DEBUG else "True"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", _https_default).lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", _https_default).lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", _https_default).lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", _https_default).lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", _https_default).lower() == "true"

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

    # Local apps (modules under backend/apps/; app_label preserved via AppConfig)
    "apps.accounts",
    "apps.core",
    "apps.license",
    "apps.bill_of_entry",
    "apps.allotment",
    "apps.trade",
    "apps.tasks",
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
    "apps.core.middleware.DisableCSRFForAPIMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Activity audit log — must be AFTER AuthenticationMiddleware so request.user is set
    "apps.core.middleware.ActivityLogMiddleware",
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
        "rest_framework.authentication.SessionAuthentication",  # Session auth for browser
        "apps.core.authentication.JWTAuthenticationFromQueryParam",  # JWT auth for API
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DATETIME_FORMAT": "%d-%m-%Y %H:%M",
    "DATE_FORMAT": "%d-%m-%Y",
    # Disable CSRF for API endpoints when using JWT authentication
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    # Throttling configuration
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.core.throttling.BurstRateThrottle",  # Short-term burst protection
        "apps.core.throttling.UserRateThrottle",   # General user throttling
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Anonymous users (unauthenticated)
        "anon": "300/hour",           # 300 requests per hour for anonymous users

        # Authenticated users (general)
        "user": "3000/hour",          # 3000 requests per hour for authenticated users

        # Staff users (admins)
        "staff": "10000/hour",        # 10000 requests per hour for staff users

        # Burst protection (short-term)
        "burst": "180/minute",        # 180 requests per minute (3 per second - prevents rapid-fire)

        # Sustained usage (long-term)
        "sustained": "20000/day",     # 20000 requests per day

        # Resource-intensive operations
        "upload": "2000/hour",        # 2000 file uploads per hour
        "export": "100/hour",         # 100 exports (Excel/PDF) per hour

        # Security-sensitive operations
        "login": "10/minute",         # 10 login attempts per minute
        "strict": "30/hour",          # 30 sensitive operations per hour (delete, bulk ops)
    },
    # Return throttle information in response headers
    "NUM_PROXIES": 1,  # Number of proxies (for accurate IP detection)
}

SIMPLE_JWT = {
    # Access token lasts 4 hours — long enough for a full working session.
    # The frontend proactively refreshes 5 min before expiry, so users never
    # hit a 401 mid-request during normal use.
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=4),
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
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# ---------------------------------------------------------------------
# CORS (for Vite / React frontend)
# ---------------------------------------------------------------------
# Note: For development we explicitly whitelist origins (do not use allow-all in production).
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    # ── Development (HTTP allowed locally) ───────────────────────────────────
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # ── Production (HTTPS only — HTTP origins removed to prevent MITM) ───────
    "https://labdhi.duckdns.org",
    "https://license-manager.duckdns.org",
    "https://165.232.185.220",
    "https://license-tractor.duckdns.org",
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
    "https://labdhi.duckdns.org",
    "https://license-manager.duckdns.org",
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

# Company that owns biscuits-side glass-formers heuristic
# (used in LicenseDetailsModel.get_glass_formers to scope BOE+allotment debits).
# Override per environment via env var if the owning company differs.
BISCUIT_COMPANY_ID = int(os.getenv("BISCUIT_COMPANY_ID", "567"))
