"""OD-06: production secret validation (security_config + system checks + settings guard).

No real or exposed secret values appear here. Strong values are generated
per test run; weak values are the repository's own public placeholders.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.core import checks
from django.test import override_settings

from lmanagement import checks as security_checks
from lmanagement.security_config import (
    DEFAULT_DEV_DB_PASSWORD,
    DEFAULT_DEV_SECRET_KEY,
    evaluate_db_password,
    evaluate_production_secrets,
    evaluate_secret_key,
    load_denylist,
    sha256_hex,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
CI_SECRET_KEY = "ci-not-a-secret-key-for-tests-only"


def _ids(findings):
    return sorted(f.id for f in findings)


def _strong_key() -> str:
    return secrets.token_urlsafe(64)


def _template_value(relative_path: str, key: str) -> str:
    for line in (REPO_ROOT / relative_path).read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"{key} not found in {relative_path}")


# ── SECRET_KEY ───────────────────────────────────────────────────────────────

def test_strong_secret_key_passes():
    assert evaluate_secret_key(_strong_key()) == []


@pytest.mark.parametrize("value", ["", None])
def test_missing_secret_key_is_rejected(value):
    assert _ids(evaluate_secret_key(value)) == ["lmanagement.E001"]


def test_backend_dev_default_secret_key_is_rejected():
    assert "lmanagement.E002" in _ids(evaluate_secret_key(DEFAULT_DEV_SECRET_KEY))


def test_ci_secret_key_is_rejected_as_placeholder_and_weak():
    assert _ids(evaluate_secret_key(CI_SECRET_KEY)) == ["lmanagement.E002", "lmanagement.E003"]


@pytest.mark.parametrize("value", [
    "x" * 49 + "Y",                       # 50 chars but only 2 unique characters
    secrets.token_urlsafe(30)[:40],       # random but shorter than 50
    "django-insecure-" + secrets.token_urlsafe(48),
])
def test_weak_secret_keys_fail_django_w009_criteria(value):
    assert "lmanagement.E003" in _ids(evaluate_secret_key(value))


@pytest.mark.parametrize("path,key", [
    ("backend/.env.example", "DJANGO_SECRET_KEY"),
    ("master-data-service/.env.example", "SECRET_KEY"),
    ("master-data-service/.env.production.example", "SECRET_KEY"),
])
def test_repository_template_secret_keys_are_rejected(path, key):
    assert evaluate_secret_key(_template_value(path, key)) != []


# ── DB password ──────────────────────────────────────────────────────────────

def test_strong_db_password_passes():
    assert evaluate_db_password(secrets.token_urlsafe(24), db_user="app", db_name="appdb") == []


@pytest.mark.parametrize("value", ["", None])
def test_missing_db_password_is_rejected(value):
    assert _ids(evaluate_db_password(value)) == ["lmanagement.E010"]


@pytest.mark.parametrize("value,user,name", [
    (DEFAULT_DEV_DB_PASSWORD, "someone", "somedb"),   # settings dev fallback
    ("postgres", "app", "db"),                        # common weak value
    ("AppRole", "approle", "db"),                     # equals DB user (case-insensitive)
    ("appdb", "app", "AppDB"),                        # equals DB name
    ("CHANGE_ME_STRONG_DB_PASSWORD", "app", "db"),    # template placeholder
    ("<db password>", "app", "db"),
])
def test_well_known_or_placeholder_db_passwords_are_rejected(value, user, name):
    assert "lmanagement.E011" in _ids(evaluate_db_password(value, db_user=user, db_name=name))


@pytest.mark.parametrize("path,key", [
    ("backend/.env.example", "DB_PASS"),
    ("master-data-service/.env.example", "MDS_DB_PASS"),
    ("master-data-service/.env.production.example", "MDS_DB_PASS"),
])
def test_repository_template_db_passwords_are_rejected(path, key):
    assert evaluate_db_password(_template_value(path, key), db_user="u", db_name="n") != []


# ── Denylist (ops-supplied, outside the repo) ────────────────────────────────

def test_denylisted_secret_key_and_db_password_are_rejected(tmp_path):
    key, password = _strong_key(), secrets.token_urlsafe(24)
    deny = tmp_path / "ops" / "denylist.txt"
    deny.parent.mkdir()
    deny.write_text(f"# exposed secrets (digests only)\n{sha256_hex(key)}\n\n{sha256_hex(password).upper()}  # db\n")
    findings = evaluate_production_secrets(
        secret_key=key, db_password=password, db_user="app", db_name="appdb",
        debug=False, denylist_path=str(deny), repo_root=tmp_path / "repo",
    )
    assert _ids(findings) == ["lmanagement.E004", "lmanagement.E012"]
    rendered = " ".join(f.message + f.hint for f in findings)
    assert key not in rendered and password not in rendered


def test_denylist_inside_repository_is_refused(tmp_path):
    deny = tmp_path / "denylist.txt"
    deny.write_text(sha256_hex("anything") + "\n")
    digests, findings = load_denylist(str(deny), repo_root=tmp_path)
    assert digests == frozenset()
    assert _ids(findings) == ["lmanagement.E031"]


def test_missing_denylist_fails_closed(tmp_path):
    _, findings = load_denylist(str(tmp_path / "absent.txt"), repo_root=tmp_path / "repo")
    assert _ids(findings) == ["lmanagement.E030"]


def test_malformed_denylist_lines_are_reported(tmp_path):
    deny = tmp_path / "deny.txt"
    deny.write_text("not-a-digest\n" + sha256_hex("x") + "\n")
    digests, findings = load_denylist(str(deny), repo_root=tmp_path / "repo")
    assert len(digests) == 1
    assert _ids(findings) == ["lmanagement.E032"]


def test_repository_ships_no_denylist_digests():
    """The mechanism is in the repo, but no sha256 digests of secrets are."""
    source = (BACKEND_DIR / "lmanagement" / "security_config.py").read_text()
    assert not re.search(r"\b[0-9a-f]{64}\b", source)


def test_debug_in_production_is_rejected():
    findings = evaluate_production_secrets(
        secret_key=_strong_key(), db_password=secrets.token_urlsafe(24), db_user="a", db_name="b",
        debug=True, denylist_path="", repo_root=REPO_ROOT,
    )
    assert _ids(findings) == ["lmanagement.E020"]


# ── Django system checks ─────────────────────────────────────────────────────

def test_checks_are_registered_with_security_and_deploy_tags():
    registry = checks.registry.registry
    assert security_checks.check_production_secrets_deploy in registry.registered_checks | registry.deployment_checks
    assert set(security_checks.check_production_secrets_deploy.tags) == {"security", "deploy"}
    assert "security" in security_checks.check_production_secrets_startup.tags


@override_settings(SECRET_KEY=CI_SECRET_KEY, DEBUG=False)
def test_deploy_check_reports_errors_for_dev_secrets():
    messages = security_checks.check_production_secrets_deploy()
    assert all(isinstance(m, checks.Error) for m in messages)
    assert {"lmanagement.E002", "lmanagement.E003"} <= {m.id for m in messages}


def test_deploy_check_passes_for_strong_configuration(settings, monkeypatch):
    settings.SECRET_KEY = _strong_key()
    settings.DEBUG = False
    settings.SECURITY_SECRET_DENYLIST_FILE = ""
    monkeypatch.setitem(settings.DATABASES["default"], "PASSWORD", secrets.token_urlsafe(24))
    assert security_checks.check_production_secrets_deploy() == []


@override_settings(SECRET_KEY=CI_SECRET_KEY, DEBUG=False)
def test_startup_check_is_silent_under_tests():
    assert security_checks.check_production_secrets_startup() == []


@override_settings(SECRET_KEY=CI_SECRET_KEY, DEBUG=False, IS_PRODUCTION=False)
def test_startup_check_warns_when_debug_off_outside_tests(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver"])
    messages = security_checks.check_production_secrets_startup()
    assert messages and all(isinstance(m, checks.Warning) for m in messages)
    assert "lmanagement.W002" in {m.id for m in messages}


@override_settings(SECRET_KEY=CI_SECRET_KEY, DEBUG=True)
def test_startup_check_is_silent_in_debug(monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["manage.py", "runserver"])
    assert security_checks.check_production_secrets_startup() == []


# ── settings import-time guard (subprocess, no DB connection) ────────────────

def _production_env(**overrides) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DB_", "SECURITY_"))}
    env.update({
        "DJANGO_ENVIRONMENT": "production",
        "DEBUG": "False",
        "DJANGO_SECRET_KEY": _strong_key(),
        "ALLOWED_HOSTS": "lm.example.com",
        "SECURE_SSL_REDIRECT": "true", "SESSION_COOKIE_SECURE": "true", "CSRF_COOKIE_SECURE": "true",
        "SECURE_HSTS_SECONDS": "31536000", "SECURE_HSTS_INCLUDE_SUBDOMAINS": "true", "SECURE_HSTS_PRELOAD": "true",
        "DB_NAME": "lm_prod_test", "DB_USER": "lm_app", "DB_PASS": secrets.token_urlsafe(24),
        "DB_HOST": "db.internal.example", "REDIS_URL": "redis://cache.internal.example:6379/0",
        "CORS_ALLOWED_ORIGINS": "https://lm.example.com", "CSRF_TRUSTED_ORIGINS": "https://lm.example.com",
        "FRONTEND_URL": "https://lm.example.com",
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "DEFAULT_FROM_EMAIL": "noreply@example.com",
    })
    env.update(overrides)
    return env


def _import_settings(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", "import lmanagement.settings"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
    )


def test_production_settings_import_succeeds_with_strong_secrets():
    result = _import_settings(_production_env())
    assert result.returncode == 0, result.stderr[-2000:]


def test_production_settings_refuse_dev_default_secret_key():
    env = _production_env()
    env.pop("DJANGO_SECRET_KEY")
    result = _import_settings(env)
    assert result.returncode != 0
    assert "lmanagement.E002" in result.stderr


def test_production_settings_refuse_ci_key_and_dev_db_password_without_leaking_them():
    weak_password = DEFAULT_DEV_DB_PASSWORD
    result = _import_settings(_production_env(DJANGO_SECRET_KEY=CI_SECRET_KEY, DB_PASS=weak_password))
    assert result.returncode != 0
    for finding_id in ("lmanagement.E002", "lmanagement.E003", "lmanagement.E011"):
        assert finding_id in result.stderr
    assert CI_SECRET_KEY not in result.stderr


def test_production_settings_refuse_denylisted_key(tmp_path):
    key = _strong_key()
    deny = tmp_path / "denylist.txt"
    deny.write_text(sha256_hex(key) + "\n")
    result = _import_settings(_production_env(DJANGO_SECRET_KEY=key, SECURITY_SECRET_DENYLIST_FILE=str(deny)))
    assert result.returncode != 0
    assert "lmanagement.E004" in result.stderr
    assert key not in result.stderr


def test_ci_and_dev_settings_still_import():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "SECURITY_"))}
    env.update({"TESTING": "true", "SECRET_KEY": CI_SECRET_KEY})
    result = _import_settings(env)
    assert result.returncode == 0, result.stderr[-2000:]


# ── M1 (security review): environment detection fails closed ────────────────

@pytest.mark.parametrize("environment", ["production ", " Production", "prod\n", "producton", "staging"])
def test_malformed_or_unknown_environment_is_treated_as_production(environment):
    env = _production_env(DJANGO_ENVIRONMENT=environment)
    env.pop("DJANGO_SECRET_KEY")  # dev default key -> must be refused in production
    result = _import_settings(env)
    assert result.returncode != 0, f"guard skipped for DJANGO_ENVIRONMENT={environment!r}"
    assert "lmanagement.E002" in result.stderr


@pytest.mark.parametrize("environment", ["development", "dev", "local", "test", "testing", "ci", " development "])
def test_explicit_non_production_environment_keeps_dev_defaults(environment):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DB_", "SECURITY_"))}
    env.update({"DJANGO_ENVIRONMENT": environment, "DEBUG": "True"})
    result = _import_settings(env)
    assert result.returncode == 0, result.stderr[-2000:]
