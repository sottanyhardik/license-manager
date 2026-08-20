"""Process-level tests for the fail-closed production settings contract."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
SETTINGS_IMPORT = "import lmanagement.settings"
_SETTINGS_ENV = {
    "DJANGO_ENVIRONMENT",
    "DJANGO_SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "SECURE_SSL_REDIRECT",
    "SESSION_COOKIE_SECURE",
    "CSRF_COOKIE_SECURE",
    "SECURE_HSTS_SECONDS",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "DB_NAME",
    "DB_USER",
    "DB_PASS",
    "DB_HOST",
    "DB_PORT",
    "REDIS_URL",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "FRONTEND_URL",
    "EMAIL_BACKEND",
    "DEFAULT_FROM_EMAIL",
}


def _settings_process(**overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in _SETTINGS_ENV:
        env.pop(name, None)
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", SETTINGS_IMPORT],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _valid_production_environment(**overrides: str) -> dict[str, str]:
    environment = {
        "DJANGO_ENVIRONMENT": "production",
        "DJANGO_SECRET_KEY": "non-secret-test-key-that-is-longer-than-thirty-two-characters",
        "DEBUG": "False",
        "ALLOWED_HOSTS": "staging.example.invalid",
        "SECURE_SSL_REDIRECT": "True",
        "SESSION_COOKIE_SECURE": "True",
        "CSRF_COOKIE_SECURE": "True",
        "SECURE_HSTS_SECONDS": "31536000",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
        "SECURE_HSTS_PRELOAD": "True",
        "DB_NAME": "license_manager_staging",
        "DB_USER": "license_manager",
        "DB_PASS": "non-secret-placeholder",
        "DB_HOST": "postgres.staging.invalid",
        "DB_PORT": "5432",
        "REDIS_URL": "redis://redis.staging.invalid:6379/14",
        "CORS_ALLOWED_ORIGINS": "https://staging.example.invalid",
        "CSRF_TRUSTED_ORIGINS": "https://staging.example.invalid",
        "FRONTEND_URL": "https://staging.example.invalid",
        "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "DEFAULT_FROM_EMAIL": "noreply@staging.example.invalid",
    }
    environment.update(overrides)
    return environment


def test_production_settings_accept_explicit_https_staging_values():
    result = _settings_process(**_valid_production_environment())

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("DJANGO_SECRET_KEY", "", "DJANGO_SECRET_KEY must be a non-default secret"),
        ("CORS_ALLOWED_ORIGINS", "http://localhost:5173", "CORS_ALLOWED_ORIGINS entries must use HTTPS"),
        ("CSRF_TRUSTED_ORIGINS", "https://localhost:5173", "CSRF_TRUSTED_ORIGINS must not contain wildcard or loopback origins"),
        ("CORS_ALLOWED_ORIGINS", "https://*.example.invalid", "CORS_ALLOWED_ORIGINS must not contain wildcard or loopback origins"),
        ("FRONTEND_URL", "http://staging.example.invalid", "FRONTEND_URL must use HTTPS in production"),
        ("EMAIL_BACKEND", "", "EMAIL_BACKEND must be explicitly configured"),
    ],
)
def test_production_settings_reject_insecure_or_missing_configuration(name, value, message):
    result = _settings_process(**_valid_production_environment(**{name: value}))

    assert result.returncode != 0
    assert message in result.stderr


def test_development_settings_keep_localhost_for_local_frontend_work():
    result = _settings_process(DJANGO_ENVIRONMENT="development")

    assert result.returncode == 0, result.stderr
