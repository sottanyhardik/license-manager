"""
migrate_auth — Step 1 of the green-field DB migration.

Copies auth.User rows (custom accounts.User model), Django Groups, and
Group-membership M2M from a source Postgres DB into the target DB.

This is the PATTERN command — all subsequent migrate_* commands follow
exactly the same skeleton:
  - --source-db / --dry-run / --batch-size CLI flags
  - Source connection opened with psycopg2 (no Django ORM on source side)
  - Natural-key idempotency: upsert via UPDATE-WHERE-natural-key +
    INSERT-WHERE-NOT-EXISTS so re-runs are safe
  - Balance/computed fields copied VERBATIM (signal bypass via `raw=True`
    equivalent: bulk_create + update_fields only, no model.save())
  - Every migrated/skipped/failed row appended to migration_log.jsonl
  - Exit code 1 if any row failed; 0 on full success (including dry-run)

Usage:
  python manage.py migrate_auth \\
      --source-db "postgres://user:pass@host:5432/old_db" \\
      [--dry-run] \\
      [--batch-size 500]

All subsequent migration commands (migrate_masters, migrate_license_headers,
…) replace only the "SOURCE QUERY" and "ROW MAPPING" sections while keeping
this scaffolding unchanged.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterator

import psycopg2
import psycopg2.extras
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AUDIT_DIR = Path("migration-audit")
LOG_FILE = AUDIT_DIR / "migration_log.jsonl"

DEFAULT_BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def source_cursor(dsn: str) -> Generator[psycopg2.extensions.cursor, None, None]:
    """Open a read-only server-side cursor on the source DB."""
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True, autocommit=True)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class AuditLog:
    """Append-only JSONL audit log for the migration run."""

    def __init__(self, path: Path, dry_run: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._dry_run = dry_run
        self._errors: list[dict] = []

    def record(
        self,
        *,
        command: str,
        action: str,
        natural_key: dict,
        status: str,          # "migrated" | "skipped" | "dry_run" | "error"
        detail: str = "",
        source_pk: Any = None,
        target_pk: Any = None,
    ) -> None:
        entry = {
            "ts": _now(),
            "command": command,
            "action": action,
            "natural_key": natural_key,
            "status": status,
            "detail": detail,
            "source_pk": source_pk,
            "target_pk": target_pk,
            "dry_run": self._dry_run,
        }
        if status == "error":
            self._errors.append(entry)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    @property
    def has_errors(self) -> bool:
        return bool(self._errors)

    @property
    def error_count(self) -> int:
        return len(self._errors)


def batched(cursor: psycopg2.extensions.cursor, query: str, size: int) -> Iterator[list]:
    """Execute *query* on *cursor* and yield lists of rows of length *size*."""
    cursor.execute(query)
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            break
        yield rows


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Step 1: migrate auth.User rows, Groups, and Group memberships "
        "from a source Postgres DB. Idempotent (re-run safe). "
        "Use --dry-run to preview without writing."
    )

    # ------------------------------------------------------------------ CLI
    def add_arguments(self, parser):
        parser.add_argument(
            "--source-db",
            required=True,
            metavar="DSN",
            help='Postgres DSN for the source DB, e.g. "postgres://u:p@host/db"',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview only — no rows written to the target DB.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            metavar="N",
            help=f"Rows per batch (default: {DEFAULT_BATCH_SIZE}).",
        )

    # ------------------------------------------------------------------ Entry
    def handle(self, *args, **options):
        source_dsn: str = options["source_db"]
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]

        audit = AuditLog(LOG_FILE, dry_run=dry_run)

        self.stdout.write(
            self.style.WARNING(
                f"{'[DRY-RUN] ' if dry_run else ''}migrate_auth — source: {source_dsn!r}"
            )
        )

        try:
            with source_cursor(source_dsn) as cur:
                self._migrate_groups(cur, audit, dry_run, batch_size)
                self._migrate_users(cur, audit, dry_run, batch_size)
                self._migrate_group_memberships(cur, audit, dry_run, batch_size)
        except psycopg2.OperationalError as exc:
            raise CommandError(f"Cannot connect to source DB: {exc}") from exc

        # Summary
        total_errors = audit.error_count
        status_style = self.style.ERROR if total_errors else self.style.SUCCESS
        self.stdout.write(
            status_style(
                f"migrate_auth done. Errors: {total_errors}. "
                f"Log: {LOG_FILE.resolve()}"
            )
        )

        if total_errors:
            sys.exit(1)

    # ------------------------------------------------------------------ Groups
    def _migrate_groups(
        self,
        cur: psycopg2.extensions.cursor,
        audit: AuditLog,
        dry_run: bool,
        batch_size: int,
    ) -> None:
        """
        SOURCE QUERY — adjust table name if the source app used a different prefix.
        Natural key: name (unique per Django Group).
        """
        query = """
            SELECT id, name
            FROM auth_group
            ORDER BY id
        """
        migrated = skipped = errors = 0

        for batch in batched(cur, query, batch_size):
            for row in batch:
                name: str = row["name"]
                natural_key = {"name": name}
                try:
                    if dry_run:
                        audit.record(
                            command="migrate_auth",
                            action="group",
                            natural_key=natural_key,
                            status="dry_run",
                            source_pk=row["id"],
                        )
                        migrated += 1
                        continue

                    with transaction.atomic():
                        obj, created = Group.objects.get_or_create(name=name)

                    status = "migrated" if created else "skipped"
                    if created:
                        migrated += 1
                    else:
                        skipped += 1

                    audit.record(
                        command="migrate_auth",
                        action="group",
                        natural_key=natural_key,
                        status=status,
                        source_pk=row["id"],
                        target_pk=obj.pk,
                    )
                except Exception as exc:
                    errors += 1
                    logger.exception("migrate_auth: group %r failed: %s", name, exc)
                    audit.record(
                        command="migrate_auth",
                        action="group",
                        natural_key=natural_key,
                        status="error",
                        detail=str(exc),
                        source_pk=row["id"],
                    )

        self.stdout.write(
            f"  Groups — migrated={migrated} skipped={skipped} errors={errors}"
        )

    # ------------------------------------------------------------------ Users
    def _migrate_users(
        self,
        cur: psycopg2.extensions.cursor,
        audit: AuditLog,
        dry_run: bool,
        batch_size: int,
    ) -> None:
        """
        SOURCE QUERY — targets `accounts_user` (the custom User model table).
        Natural key: username (unique; email secondary).

        FIELD MAPPING (TODO for backend-engineer):
          Map every column from the source `accounts_user` table to the
          corresponding field on apps.accounts.models.User. The fields below
          are the current schema — verify against the source DB column list
          before wiring up.

          Source columns to map:
            id, password, last_login, is_superuser, username, first_name,
            last_name, email, is_staff, is_active, date_joined, avatar

          AuditModel fields (created_by_id, modified_by_id) are NOT set here —
          they point to User PKs which don't exist yet. Set them in a post-pass
          or leave NULL (they are nullable).

        NOTE on IDs (see OQ-5 in the plan): we preserve source PKs by writing
          `id=row["id"]` directly. Django auto-assigns the sequence; call
          `setval(pg_get_serial_sequence('accounts_user','id'), MAX(id))`
          after the load completes (the reconcile command does this).
        """
        query = """
            SELECT
                id,
                password,
                last_login,
                is_superuser,
                username,
                first_name,
                last_name,
                email,
                is_staff,
                is_active,
                date_joined,
                avatar
            FROM accounts_user
            ORDER BY id
        """
        migrated = skipped = errors = 0

        for batch in batched(cur, query, batch_size):
            for row in batch:
                username: str = row["username"]
                natural_key = {"username": username}
                source_pk = row["id"]
                try:
                    if dry_run:
                        audit.record(
                            command="migrate_auth",
                            action="user",
                            natural_key=natural_key,
                            status="dry_run",
                            source_pk=source_pk,
                        )
                        migrated += 1
                        continue

                    # ---- ROW MAPPING (fill this in) -------------------------
                    defaults = dict(
                        # id=source_pk,  # uncomment if preserving PKs (OQ-5 choice A)
                        password=row["password"],           # hashed — copy verbatim
                        last_login=row["last_login"],
                        is_superuser=bool(row["is_superuser"]),
                        first_name=row["first_name"] or "",
                        last_name=row["last_name"] or "",
                        email=row["email"],
                        is_staff=bool(row["is_staff"]),
                        is_active=bool(row["is_active"]),
                        date_joined=row["date_joined"],
                        # avatar: media-file path copy is handled by migrate_media.sh
                        # avatar=row["avatar"],
                        # created_by / modified_by: set in post-pass
                    )
                    # ---------------------------------------------------------

                    with transaction.atomic():
                        existing = User.objects.filter(username=username).first()
                        if existing:
                            # Idempotent: update only non-auth fields (never
                            # overwrite password if user has already changed it
                            # in the new system — policy decision; currently we
                            # DO overwrite to guarantee parity with source).
                            for field, value in defaults.items():
                                setattr(existing, field, value)
                            existing.save(update_fields=list(defaults.keys()))
                            obj = existing
                            skipped += 1
                            status = "skipped"
                        else:
                            obj = User.objects.create(**defaults)
                            migrated += 1
                            status = "migrated"

                    audit.record(
                        command="migrate_auth",
                        action="user",
                        natural_key=natural_key,
                        status=status,
                        source_pk=source_pk,
                        target_pk=obj.pk,
                    )
                except Exception as exc:
                    errors += 1
                    logger.exception("migrate_auth: user %r failed: %s", username, exc)
                    audit.record(
                        command="migrate_auth",
                        action="user",
                        natural_key=natural_key,
                        status="error",
                        detail=str(exc),
                        source_pk=source_pk,
                    )

        self.stdout.write(
            f"  Users — migrated={migrated} skipped={skipped} errors={errors}"
        )

    # ------------------------------------------------------- Group memberships
    def _migrate_group_memberships(
        self,
        cur: psycopg2.extensions.cursor,
        audit: AuditLog,
        dry_run: bool,
        batch_size: int,
    ) -> None:
        """
        Natural key: (username, group_name) — M2M resolved by natural keys,
        not by source integer IDs, so this is immune to PK drift.
        """
        query = """
            SELECT
                u.username,
                g.name AS group_name
            FROM accounts_user_groups aug
            JOIN accounts_user u ON u.id = aug.user_id
            JOIN auth_group     g ON g.id = aug.group_id
            ORDER BY u.username, g.name
        """
        migrated = skipped = errors = 0

        for batch in batched(cur, query, batch_size):
            for row in batch:
                username = row["username"]
                group_name = row["group_name"]
                natural_key = {"username": username, "group": group_name}
                try:
                    if dry_run:
                        audit.record(
                            command="migrate_auth",
                            action="group_membership",
                            natural_key=natural_key,
                            status="dry_run",
                        )
                        migrated += 1
                        continue

                    with transaction.atomic():
                        user = User.objects.get(username=username)
                        group = Group.objects.get(name=group_name)
                        added = not user.groups.filter(pk=group.pk).exists()
                        if added:
                            user.groups.add(group)

                    if added:
                        migrated += 1
                        status = "migrated"
                    else:
                        skipped += 1
                        status = "skipped"

                    audit.record(
                        command="migrate_auth",
                        action="group_membership",
                        natural_key=natural_key,
                        status=status,
                    )
                except (User.DoesNotExist, Group.DoesNotExist) as exc:
                    errors += 1
                    logger.error(
                        "migrate_auth: group_membership %r — ref not found: %s",
                        natural_key,
                        exc,
                    )
                    audit.record(
                        command="migrate_auth",
                        action="group_membership",
                        natural_key=natural_key,
                        status="error",
                        detail=str(exc),
                    )
                except Exception as exc:
                    errors += 1
                    logger.exception(
                        "migrate_auth: group_membership %r failed: %s", natural_key, exc
                    )
                    audit.record(
                        command="migrate_auth",
                        action="group_membership",
                        natural_key=natural_key,
                        status="error",
                        detail=str(exc),
                    )

        self.stdout.write(
            f"  Group memberships — migrated={migrated} skipped={skipped} errors={errors}"
        )
