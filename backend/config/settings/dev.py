from .base import *  # noqa: F401, F403
import os

DEBUG = True
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-not-for-production-use")  # noqa: S105

# Allow all hosts in dev
ALLOWED_HOSTS = ["*"]

# Use sqlite for quick local dev if DATABASE_URL not set
# (base.py already defaults to sqlite, so nothing extra needed)

# Disable SSL requirements
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
