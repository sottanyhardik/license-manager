"""Force a password reset for accounts exposed in the OD-06 database dumps.

Dry run by default: prints counts only and changes nothing. With
``--execute``, in one transaction:

* sets an unusable password on every selected account. That forces the
  password-reset flow and also voids old reset links and sessions;
* blacklists every outstanding refresh JWT of those accounts;
* writes ``core.ActivityLog`` audit rows (module ``security``).

Cut-off (from git metadata only; see docs/security/OD-06-remediation-manifest.md):
the latest dump commit is 58fa4691 (2025-12-17), so use
``--joined-on-or-before 2025-12-17``. Dates compare in the project TIME_ZONE.

Examples::

    python manage.py force_password_reset --joined-on-or-before 2025-12-17
    python manage.py force_password_reset --joined-on-or-before 2025-12-17 \\
        --include-superusers --execute --reason "OD-06 rotation 2026-11-xx"
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.security_actions import (
    force_password_reset,
    read_usernames_file,
    select_affected_users,
)


class Command(BaseCommand):
    help = "OD-06: force password resets for exposed accounts (dry run unless --execute)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--joined-on-or-before",
            metavar="YYYY-MM-DD",
            help="Select accounts whose date_joined is on or before this date.",
        )
        parser.add_argument(
            "--usernames-file",
            metavar="PATH",
            help="Select accounts listed in this file (one username per line, '#' comments).",
        )
        parser.add_argument(
            "--include-superusers",
            action="store_true",
            help="Also reset superusers. By default they are skipped and counted.",
        )
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True,
                          help="Count only; change nothing (default).")
        mode.add_argument("--execute", action="store_true",
                          help="Apply the changes. Requires --reason.")
        parser.add_argument("--reason", default="", help="Audit reason / ticket (required with --execute).")

    def handle(self, *args, **options):
        cutoff = self._parse_date(options.get("joined_on_or_before"))
        usernames = self._read_usernames(options.get("usernames_file"))
        if cutoff is None and not usernames:
            raise CommandError("Provide --joined-on-or-before and/or --usernames-file.")
        execute = bool(options["execute"])
        reason = (options.get("reason") or "").strip()
        if execute and not reason:
            raise CommandError("--execute requires --reason (recorded in the audit log).")

        selection = select_affected_users(
            joined_on_or_before=cutoff,
            usernames=usernames,
            include_superusers=options["include_superusers"],
        )
        criteria = {
            "joined_on_or_before": cutoff.isoformat() if cutoff else None,
            "usernames_file": bool(usernames),
            "include_superusers": bool(options["include_superusers"]),
        }
        result = force_password_reset(selection, execute=execute, reason=reason, criteria=criteria)

        label = "EXECUTED" if execute else "DRY RUN (no changes)"
        self.stdout.write(f"force_password_reset: {label}")
        self.stdout.write(f"  matched accounts:            {selection.matched_total}")
        self.stdout.write(f"  superusers skipped:          {selection.superusers_skipped}")
        if usernames:
            self.stdout.write(f"  usernames in file:           {selection.usernames_requested}")
            self.stdout.write(f"  usernames not found:         {selection.usernames_not_found}")
        self.stdout.write(f"  selected accounts:           {result.selected}")
        self.stdout.write(f"  passwords to invalidate:     {result.passwords_invalidated}")
        self.stdout.write(f"  already unusable:            {result.already_unusable}")
        self.stdout.write(f"  refresh tokens to blacklist: {result.tokens_blacklisted}")
        self.stdout.write(f"  selected without email:      {result.without_email} "
                          "(cannot self-serve a reset; an admin must set a password)")
        if not execute:
            self.stdout.write("Re-run with --execute --reason '...' to apply.")

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError("--joined-on-or-before must be YYYY-MM-DD.") from exc

    @staticmethod
    def _read_usernames(path_value):
        if not path_value:
            return None
        path = Path(path_value)
        if not path.is_file():
            raise CommandError("--usernames-file does not exist or is not a file.")
        with path.open(encoding="utf-8") as handle:
            names = read_usernames_file(handle)
        if not names:
            raise CommandError("--usernames-file contains no usernames.")
        return names
