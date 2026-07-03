# FILE: lmanagement/settings.py
import os
from datetime import timedelta
from pathlib import Path

from django.urls import reverse_lazy

# ---------------------------------------------------------------------
# Base Paths
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present (production servers place it at BASE_DIR/.env)
try:
    from dotenv import load_dotenv
    _env_path = BASE_DIR / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)  # env vars already set take precedence
except ImportError:
    pass  # python-dotenv not installed — rely on process environment

# ---------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "local-dev-only-secret-key-change-for-production-7f8e6d5c4b3a2910",
)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"   # PRODUCTION DEFAULT: False
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost"  # production: set ALLOWED_HOSTS env var with real domains
).split(",")

# HTTPS Settings — all default to OFF; production servers must set them
# explicitly via environment variables (see server-envs/*.env).
# Tying these to DEBUG caused SECURE_SSL_REDIRECT to activate locally
# when DEBUG was defaulted to False, which 301-redirected CORS preflights.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT         = os.getenv("SECURE_SSL_REDIRECT",         "False").lower() == "true"
SESSION_COOKIE_SECURE       = os.getenv("SESSION_COOKIE_SECURE",       "False").lower() == "true"
CSRF_COOKIE_SECURE          = os.getenv("CSRF_COOKIE_SECURE",          "False").lower() == "true"
SECURE_HSTS_SECONDS         = int(os.getenv("SECURE_HSTS_SECONDS",     "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "False").lower() == "true"
SECURE_HSTS_PRELOAD             = os.getenv("SECURE_HSTS_PRELOAD",             "False").lower() == "true"

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

_cors_extra = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CORS_ALLOWED_ORIGINS = [
    # ── Development (HTTP allowed locally — all common Vite/React ports) ─────
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",   # Vite uses 5174 when 5173 is taken
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # ── Production: add via CORS_ALLOWED_ORIGINS env var (comma-separated) ───
    # e.g. CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app2.com
] + _cors_extra

# Allow cookies (credentials) across origins when frontend sends withCredentials
CORS_ALLOW_CREDENTIALS = True

# Allow ANY localhost port (covers Vite's dynamic port assignment 5173–5180+)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
]

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
_csrf_extra = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # Production: set CSRF_TRUSTED_ORIGINS env var (comma-separated HTTPS origins)
] + _csrf_extra

# ---------------------------------------------------------------------
# Email (file backend for dev)
# ---------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",  # dev default — set to SMTP in prod
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "info@labdhimercantile.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ---------------------------------------------------------------------
# App-specific Config
# ---------------------------------------------------------------------
EXPIRY_DAY = 60
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

# Company that owns biscuits-side glass-formers heuristic
# (used in LicenseDetailsModel.get_glass_formers to scope BOE+allotment debits).
# Override per environment via env var if the owning company differs.
BISCUIT_COMPANY_ID = int(os.getenv("BISCUIT_COMPANY_ID", "567"))

# ---------------------------------------------------------------------
# Master-Data Service integration (ADR-001) — OFF by default
# ---------------------------------------------------------------------
# When MDS_ENABLED=true and the `mds_client` package is importable, register it
# and adopt the full 17-master mapping. This does NOT change read behavior (reads
# still hit the local tables); it enables the sync worker + write client. The
# write cutover (routing master writes to MDS) is a later, explicit step.
MDS_ENABLED = os.getenv("MDS_ENABLED", "False").lower() == "true"
MDS_BASE_URL = os.getenv("MDS_BASE_URL", "")
MDS_TOKEN = os.getenv("MDS_TOKEN", "")
if MDS_ENABLED:
    try:
        import mds_client  # noqa: F401

        INSTALLED_APPS += ["mds_client"]
        from mds_client import DEFAULT_MDS_MODELS

        MDS_MODELS = DEFAULT_MDS_MODELS
    except ImportError:
        # package not installed in this environment — stay disabled, don't crash
        MDS_ENABLED = False
