"""Shared bootstrap for the read-only DB integrity scripts.

Every script here:
  * boots Django from ``backend/`` (settings ``lmanagement.settings`` unless overridden),
  * refuses to run unless the default DB host is local,
  * runs all queries inside a READ ONLY transaction that is rolled back.
Nothing in this directory writes to the database.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / "backend"
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def setup() -> None:
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
    import django

    django.setup()
    from django.conf import settings

    host = str(settings.DATABASES["default"].get("HOST") or "")
    if host not in LOCAL_HOSTS:
        sys.exit(f"refusing to run: default DB host is not local ({host!r})")


@contextlib.contextmanager
def read_only():
    from django.db import connection, transaction

    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        try:
            yield connection
        finally:
            transaction.set_rollback(True)
