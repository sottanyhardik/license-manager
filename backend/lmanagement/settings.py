# FILE: lmanagement/settings.py
import os
import json
import warnings
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

# docxtpl imports docxcompose, whose current release still imports the
# deprecated pkg_resources compatibility API.  Ignore only that known upstream
# warning; all other deprecation warnings remain visible to operators.
warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module=r"docxcompose\.properties",
)

# ---------------------------------------------------------------------
# Base Paths
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment files if present.  ``.env_dgft`` is deliberately
# separate because DGFT session cookies and CSRF values are short-lived
# browser credentials, not general application configuration.
try:
    from dotenv import load_dotenv
    for _env_path in (BASE_DIR / ".env", BASE_DIR / ".env_dgft"):
        if _env_path.exists():
            # Values supplied by the process (for example, production secret
            # storage) always take precedence over local files.
            load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on process environment

# ---------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------
_DEFAULT_DEV_SECRET_KEY = "local-dev-only-secret-key-change-for-production-7f8e6d5c4b3a2910"
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    _DEFAULT_DEV_SECRET_KEY,
)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"   # PRODUCTION DEFAULT: False
DEPLOYMENT_ENV = os.getenv("DJANGO_ENVIRONMENT", "development").lower()
IS_PRODUCTION = DEPLOYMENT_ENV in {"production", "prod"}

# DGFT scrip-ownership lookup.  Values are loaded from ``.env_dgft`` locally
# (or normal process environment in deployed environments).  The session and
# CSRF token expire; operators must refresh them from an authenticated DGFT
# browser session when a lookup is rejected.
DGFT_OWNERSHIP_URL = os.getenv("DGFT_OWNERSHIP_URL", "https://www.dgft.gov.in/CP/webHP")
DGFT_SCRIP_NUMBER = os.getenv("DGFT_SCRIP_NUMBER", "")
DGFT_SCRIP_ISSUE_DATE = os.getenv("DGFT_SCRIP_ISSUE_DATE", "")
DGFT_IEC_NUMBER = os.getenv("DGFT_IEC_NUMBER", "")
DGFT_APP_ID = os.getenv("DGFT_APP_ID", "")
DGFT_SESSION_ID = os.getenv("DGFT_SESSION_ID", "")
DGFT_CSRF_TOKEN = os.getenv("DGFT_CSRF_TOKEN", "")
DGFT_AWSALB = os.getenv("DGFT_AWSALB", "")
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost"  # production: set ALLOWED_HOSTS env var with real domains
)
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS.split(",") if host.strip()]

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


def _validate_production_security() -> None:
    """Fail closed for explicitly configured production processes.

    Local test and development environments remain usable without production
    secrets.  A process declared as production must not silently boot with the
    repository fallback secret, permissive hosts, or insecure cookies.
    """
    if not IS_PRODUCTION:
        return
    errors = []
    if DEBUG:
        errors.append("DEBUG must be False")
    if SECRET_KEY == _DEFAULT_DEV_SECRET_KEY or len(SECRET_KEY) < 32:
        errors.append("DJANGO_SECRET_KEY must be a non-default secret of at least 32 characters")
    if not ALLOWED_HOSTS or any(host in {"localhost", "127.0.0.1", "*"} for host in ALLOWED_HOSTS):
        errors.append("ALLOWED_HOSTS must contain only explicit production hosts")
    if not (SECURE_SSL_REDIRECT and SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE):
        errors.append("SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, and CSRF_COOKIE_SECURE must be true")
    if SECURE_HSTS_SECONDS < 31536000:
        errors.append("SECURE_HSTS_SECONDS must be at least 31536000")
    if not SECURE_HSTS_INCLUDE_SUBDOMAINS:
        errors.append("SECURE_HSTS_INCLUDE_SUBDOMAINS must be true")
    if not SECURE_HSTS_PRELOAD:
        errors.append("SECURE_HSTS_PRELOAD must be true")
    if any(
        os.getenv(name, default) == default
        for name, default in (
            ("DB_NAME", "lmanagement"),
            ("DB_USER", "lmanagement"),
            ("DB_PASS", "lmanagement"),
            ("DB_HOST", "localhost"),
            ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        )
    ):
        errors.append("database and Redis connection settings must be explicitly configured")
    if errors:
        raise RuntimeError("Invalid production security configuration: " + "; ".join(errors))


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
    "drf_spectacular",

    # Local apps (modules under backend/apps/; app_label preserved via AppConfig)
    "apps.accounts",
    "apps.core",
    "apps.license",
    "apps.bill_of_entry",
    "apps.allotment",
    "apps.trade",
    "apps.reconciliation",
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
# Parallel local/CI verification must not share Django's default
# ``test_lmanagement`` database: one runner can otherwise drop it while another
# is migrating or tearing down.  Test commands may set TEST_DB_NAME to a
# unique, explicit identifier (for example test_lmanagement_sync_ledger).
_test_db_name = os.getenv("TEST_DB_NAME", "").strip()
if _test_db_name:
    DATABASES["default"]["TEST"] = {"NAME": _test_db_name}

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

# Authenticated media downloads (see apps.core.views.media.ProtectedMediaView).
# In production set this to nginx's internal location prefix (e.g. "/protected-media/")
# so nginx serves the bytes via X-Accel-Redirect. Leave empty in dev to stream via Django.
MEDIA_X_ACCEL_REDIRECT = os.getenv("MEDIA_X_ACCEL_REDIRECT", "")

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
        "apps.core.authentication.JWTAuthenticationFromQueryParam",  # JWT auth for API
        # JWT must be evaluated before a browser's session cookie. Otherwise
        # SessionAuthentication can reject a valid bearer-token mutation for a
        # missing CSRF token before JWT authentication is reached.
        "rest_framework.authentication.SessionAuthentication",  # Browser/admin fallback
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    # OpenAPI schema generation (drf-spectacular).
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
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
        "password_reset": "5/hour",   # password reset request/confirm (anti-abuse + anti-enumeration)
    },
    # Return throttle information in response headers
    "NUM_PROXIES": 1,  # Number of proxies (for accurate IP detection)
}

SIMPLE_JWT = {
    # Access tokens are stateless and CANNOT be revoked (only refresh tokens can be
    # blacklisted), so a long-lived access token is a long-lived bearer credential if
    # it ever leaks. Keep it short (default 30 min). The frontend refreshes it
    # through one queued refresh request on the next authenticated API call, so
    # active sessions last as long as the refresh token. Tunable via env.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))),
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
# Replanning uses the standard worker queue so a normal Celery worker processes
# accepted Auto Plan requests without requiring a separate subscription.
CELERY_TASK_ROUTES = {
    "planning.dispatch_replan_requests": {"queue": "celery"},
    "planning.replan_license": {"queue": "celery"},
    "planning.recover_pending_replan_requests": {"queue": "celery"},
    "license.enqueue_license_ledger_package": {"queue": "celery"},
    "license.build_license_ledger_package_item": {"queue": "celery"},
    "license.finalize_license_ledger_package": {"queue": "celery"},
    "license.recover_license_ledger_package_jobs": {"queue": "celery"},
    "license.cleanup_expired_ledger_packages": {"queue": "celery"},
}
CELERY_TASK_ANNOTATIONS = {
    "planning.replan_license": {
        "acks_late": True,
        "reject_on_worker_lost": True,
        "soft_time_limit": int(os.getenv("LICENSE_REPLAN_SOFT_TIME_LIMIT", "240")),
        "time_limit": int(os.getenv("LICENSE_REPLAN_TIME_LIMIT", "300")),
    },
    "license.build_license_ledger_package_item": {
        "acks_late": True,
        "reject_on_worker_lost": True,
        "soft_time_limit": int(os.getenv("LICENSE_PACKAGE_ITEM_SOFT_TIME_LIMIT", "240")),
        "time_limit": int(os.getenv("LICENSE_PACKAGE_ITEM_TIME_LIMIT", "300")),
    },
    "license.finalize_license_ledger_package": {
        "acks_late": True,
        "reject_on_worker_lost": True,
        "soft_time_limit": int(os.getenv("LICENSE_PACKAGE_ARCHIVE_SOFT_TIME_LIMIT", "300")),
        "time_limit": int(os.getenv("LICENSE_PACKAGE_ARCHIVE_TIME_LIMIT", "360")),
    },
}
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))

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
# OpenAPI / API documentation (drf-spectacular)
# ---------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "License Manager API",
    "DESCRIPTION": "DGFT import/export licence, allotment, BOE and trade management API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # ``allocation_basis`` and ``search_mode`` deliberately share the same
    # ACTUAL/PLAN choices while retaining distinct runtime fields.  A stable
    # schema component name documents that shared wire enum without a noisy
    # duplicate-choice warning.
    "ENUM_NAME_OVERRIDES": {
        "AllocationBasisEnum": [("ACTUAL", "Actual"), ("PLAN", "Plan")],
    },
}

# ---------------------------------------------------------------------
# CORS (for Vite / React frontend)
# ---------------------------------------------------------------------
# Note: For development we explicitly whitelist origins (do not use allow-all in production).
CORS_ALLOW_ALL_ORIGINS = False

_cors_extra = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
_development_origins = [
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
]
CORS_ALLOWED_ORIGINS = _cors_extra if IS_PRODUCTION else _development_origins + _cors_extra

# Allow cookies (credentials) across origins when frontend sends withCredentials
CORS_ALLOW_CREDENTIALS = True

# Allow ANY localhost port (covers Vite's dynamic port assignment 5173–5180+)
CORS_ALLOWED_ORIGIN_REGEXES = [] if IS_PRODUCTION else [
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
        # Package creation uses this non-secret key to turn a double click
        # into one durable Celery job. It must be allowed by CORS preflight
        # before the browser can issue the POST.
        "Idempotency-Key",
        "idempotency-key",
        # Correlates one explicit ledger-upload attempt across the browser,
        # API and worker logs. It is intentionally a non-sensitive UUID.
        "x-upload-operation-id",
    ]
except ImportError:
    # fallback - minimal safe set
    CORS_ALLOW_HEADERS = [
        "accept",
        "accept-encoding",
        "authorization",
        "content-type",
        "origin",
        "user-agent",
        "x-csrftoken",
        "idempotency-key",
        "x-upload-operation-id",
        "x-requested-with",
    ]

# Optional: expose headers to browser
CORS_EXPOSE_HEADERS = ["Content-Type", "Content-Disposition", "X-CSRFToken", "Authorization"]

# CSRF trusted origins for Django's CSRF checks (if you use session auth)
_csrf_extra = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]
_development_csrf_origins = [
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
]
CSRF_TRUSTED_ORIGINS = _csrf_extra if IS_PRODUCTION else _development_csrf_origins + _csrf_extra


def _validate_production_origin_policy() -> None:
    """Reject development, wildcard, and insecure browser origins in production."""
    if not IS_PRODUCTION:
        return

    errors = []
    for setting_name, origins in (
        ("CORS_ALLOWED_ORIGINS", CORS_ALLOWED_ORIGINS),
        ("CSRF_TRUSTED_ORIGINS", CSRF_TRUSTED_ORIGINS),
    ):
        for origin in origins:
            if not origin.startswith("https://"):
                errors.append(f"{setting_name} entries must use HTTPS")
                continue
            host = origin.removeprefix("https://").split("/", 1)[0].split(":", 1)[0].lower()
            if host in {"localhost", "127.0.0.1", "::1"} or "*" in origin:
                errors.append(f"{setting_name} must not contain wildcard or loopback origins")
    if CORS_ALLOW_CREDENTIALS and ("*" in CORS_ALLOWED_ORIGINS or CORS_ALLOWED_ORIGIN_REGEXES):
        errors.append("credentialed CORS must use explicit origins only")
    if errors:
        raise RuntimeError("Invalid production origin policy: " + "; ".join(sorted(set(errors))))


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


def _validate_production_delivery_configuration() -> None:
    """Ensure deploy-only browser and mail configuration is explicit and safe."""
    if not IS_PRODUCTION:
        return

    errors = []
    if not FRONTEND_URL.startswith("https://"):
        errors.append("FRONTEND_URL must use HTTPS in production")
    frontend_host = FRONTEND_URL.removeprefix("https://").split("/", 1)[0].split(":", 1)[0].lower()
    if frontend_host in {"localhost", "127.0.0.1", "::1"} or "*" in FRONTEND_URL:
        errors.append("FRONTEND_URL must not contain wildcard or loopback host")
    if not os.getenv("EMAIL_BACKEND", "").strip():
        errors.append("EMAIL_BACKEND must be explicitly configured")
    if not DEFAULT_FROM_EMAIL or not os.getenv("DEFAULT_FROM_EMAIL", "").strip():
        errors.append("DEFAULT_FROM_EMAIL must be explicitly configured")
    if errors:
        raise RuntimeError("Invalid production delivery configuration: " + "; ".join(errors))


_validate_production_security()
_validate_production_origin_policy()
_validate_production_delivery_configuration()

# ---------------------------------------------------------------------
# App-specific Config
# ---------------------------------------------------------------------
EXPIRY_DAY = 60
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

# Company that owns biscuits-side glass-formers heuristic
# (used in LicenseDetailsModel.get_glass_formers to scope BOE+allotment debits).
# Override per environment via env var if the owning company differs.
BISCUIT_COMPANY_ID = int(os.getenv("BISCUIT_COMPANY_ID", "567"))

# BOE / Invoice Reconciliation panel (apps.reconciliation) — tolerance
# thresholds below which a CIF/quantity mismatch between an invoice (trade
# lines) and its linked BOE(s) is NOT flagged as a discrepancy. Also reused
# as the near-duplicate-BOE CIF tolerance in `duplicate_boes()`.
RECONCILIATION_CIF_TOLERANCE = Decimal(os.getenv("RECONCILIATION_CIF_TOLERANCE", "1.00"))
RECONCILIATION_QTY_TOLERANCE = Decimal(os.getenv("RECONCILIATION_QTY_TOLERANCE", "1.000"))

# ---------------------------------------------------------------------
# Master Sync (Module 04) — multi-server peer-to-peer synchronization
# ---------------------------------------------------------------------
SYNC_SERVER_ID = os.getenv("SYNC_SERVER_ID", "default")
SYNC_ENABLED = os.getenv("SYNC_ENABLED", "False").lower() == "true"
SYNC_PUSH_ON_SAVE = os.getenv("SYNC_PUSH_ON_SAVE", "False").lower() == "true"
try:
    SYNC_PEER_TOKENS = json.loads(os.getenv("SYNC_PEER_TOKENS", "{}"))
except json.JSONDecodeError as exc:
    raise RuntimeError("SYNC_PEER_TOKENS must be a JSON object keyed by server id") from exc
if not isinstance(SYNC_PEER_TOKENS, dict) or any(
    not isinstance(key, str) or not isinstance(value, str) or not value.strip()
    for key, value in SYNC_PEER_TOKENS.items()
):
    raise RuntimeError("SYNC_PEER_TOKENS must be a JSON object of non-empty string credentials")

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
