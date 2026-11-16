"""Django system checks for production secrets (OD-06).

The rules live in ``lmanagement.security_config``. The import-time guard in
``settings._validate_production_security()`` uses the same rules.

* ``manage.py check --deploy`` reports every finding as an Error, so the
  command exits non-zero. Run it on staging/production hosts before go-live.
* At startup (any command that runs system checks, for example runserver
  or migrate) with ``DEBUG=False`` outside production and outside tests, the
  same findings are reported as advisory Warnings. A server that forgot
  ``DJANGO_ENVIRONMENT=production`` is then still told its secrets are weak.
  Production itself already fails closed at import time.

Registered from ``apps.core.apps.CoreConfig.ready()``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from django.conf import settings
from django.core import checks

from lmanagement.security_config import Finding, evaluate_production_secrets

DEPLOY_TAG = "deploy"


def _findings() -> list[Finding]:
    database = settings.DATABASES.get("default", {})
    return evaluate_production_secrets(
        secret_key=getattr(settings, "SECRET_KEY", ""),
        db_password=database.get("PASSWORD", ""),
        db_user=database.get("USER", "") or "",
        db_name=database.get("NAME", "") or "",
        debug=bool(settings.DEBUG),
        denylist_path=getattr(settings, "SECURITY_SECRET_DENYLIST_FILE", ""),
        repo_root=Path(settings.BASE_DIR).parent,
    )


def _is_test_run() -> bool:
    return (
        os.getenv("TESTING", "").lower() == "true"
        or bool(os.getenv("PYTEST_VERSION"))
        or "test" in sys.argv[1:2]
    )


def _deploy_run_requested() -> bool:
    return "--deploy" in sys.argv


@checks.register(checks.Tags.security, DEPLOY_TAG, deploy=True)
def check_production_secrets_deploy(app_configs=None, **kwargs) -> list[checks.CheckMessage]:
    """``check --deploy``: weak/placeholder/denylisted secrets are errors."""
    return [checks.Error(f.message, hint=f.hint or None, id=f.id) for f in _findings()]


@checks.register(checks.Tags.security)
def check_production_secrets_startup(app_configs=None, **kwargs) -> list[checks.CheckMessage]:
    """Startup: advisory warnings when DEBUG is off outside production and tests."""
    if getattr(settings, "IS_PRODUCTION", False):
        return []  # Production already failed closed at import time.
    if settings.DEBUG or _is_test_run() or _deploy_run_requested():
        return []
    return [
        checks.Warning(f.message, hint=f.hint or None, id=f.id.replace(".E", ".W", 1))
        for f in _findings()
    ]
