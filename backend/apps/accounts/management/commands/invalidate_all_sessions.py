"""Invalidate every Django session and every outstanding refresh JWT (OD-06).

Dry run by default: prints counts only. With ``--execute``, in one
transaction: deletes all ``django_session`` rows, blacklists every
outstanding simplejwt refresh token, optionally deletes expired outstanding
tokens (``--flush-expired``), and writes a ``core.ActivityLog`` audit row.

Run this right after the coordinated SECRET_KEY restart. Rotating the key
already invalidates every signature, so this removes the residual rows. See
docs/security/OD-06-rotation-runbook.md.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.security_actions import invalidate_all_sessions


class Command(BaseCommand):
    help = "OD-06: delete all sessions and blacklist all refresh JWTs (dry run unless --execute)."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True,
                          help="Count only; change nothing (default).")
        mode.add_argument("--execute", action="store_true",
                          help="Apply the changes. Requires --reason.")
        parser.add_argument("--flush-expired", action="store_true",
                            help="Also delete expired outstanding tokens (like simplejwt flushexpiredtokens).")
        parser.add_argument("--reason", default="", help="Audit reason / ticket (required with --execute).")

    def handle(self, *args, **options):
        execute = bool(options["execute"])
        reason = (options.get("reason") or "").strip()
        if execute and not reason:
            raise CommandError("--execute requires --reason (recorded in the audit log).")
        result = invalidate_all_sessions(
            execute=execute, flush_expired=bool(options["flush_expired"]), reason=reason,
        )
        label = "EXECUTED" if execute else "DRY RUN (no changes)"
        self.stdout.write(f"invalidate_all_sessions: {label}")
        self.stdout.write(f"  sessions to delete:          {result.sessions}")
        self.stdout.write(f"  refresh tokens to blacklist: {result.tokens_blacklisted}")
        if options["flush_expired"]:
            self.stdout.write(f"  expired tokens to flush:     {result.expired_tokens_flushed}")
        if not execute:
            self.stdout.write("Re-run with --execute --reason '...' to apply.")
