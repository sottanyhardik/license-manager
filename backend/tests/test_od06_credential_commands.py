"""OD-06: force_password_reset and invalidate_all_sessions (test DB only)."""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import ActivityLog

User = get_user_model()
CUTOFF = "2025-12-17"
BEFORE = datetime(2025, 12, 1, 9, 0, tzinfo=dt_timezone.utc)
ON_CUTOFF = datetime(2025, 12, 17, 23, 0, tzinfo=dt_timezone.utc)
AFTER = datetime(2026, 1, 10, 9, 0, tzinfo=dt_timezone.utc)
PASSWORD = "Original-Pass-123!"


def _user(username, joined, *, superuser=False, email=True):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com" if email else None,
        password=PASSWORD,
        is_superuser=superuser,
        is_staff=superuser,
    )
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    user.refresh_from_db()
    return user


@pytest.fixture
def population(db):
    users = {
        "old": _user("od06_old", BEFORE),
        "edge": _user("od06_edge", ON_CUTOFF),
        "noemail": _user("od06_noemail", BEFORE, email=False),
        "admin": _user("od06_admin", BEFORE, superuser=True),
        "new": _user("od06_new", AFTER),
    }
    refresh = {key: RefreshToken.for_user(user) for key, user in users.items()}
    return users, refresh


def _run(*args):
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def _count(output, label):
    line = next(line for line in output.splitlines() if line.strip().startswith(label))
    return int(line.split(":", 1)[1].split()[0])


def _usable(user):
    user.refresh_from_db()
    return user.has_usable_password()


# ── force_password_reset ─────────────────────────────────────────────────────

def test_dry_run_is_default_and_changes_nothing(population):
    users, _ = population
    output = _run("force_password_reset", "--joined-on-or-before", CUTOFF)
    assert "DRY RUN" in output
    assert _count(output, "matched accounts") == 4
    assert _count(output, "superusers skipped") == 1
    assert _count(output, "selected accounts") == 3
    assert _count(output, "refresh tokens to blacklist") == 3
    assert _count(output, "selected without email") == 1
    assert all(_usable(u) for u in users.values())
    assert BlacklistedToken.objects.count() == 0
    assert ActivityLog.objects.filter(module="security").count() == 0
    # Counts only: no usernames are printed.
    assert not any(u.username in output for u in users.values())


def test_execute_requires_reason(population):
    with pytest.raises(CommandError, match="--reason"):
        _run("force_password_reset", "--joined-on-or-before", CUTOFF, "--execute")


@pytest.mark.parametrize("args,match", [
    ((), "Provide"),
    (("--joined-on-or-before", "17-12-2025"), "YYYY-MM-DD"),
    (("--usernames-file", "/nonexistent/od06.txt"), "does not exist"),
])
def test_invalid_arguments_are_rejected(db, args, match):
    with pytest.raises(CommandError, match=match):
        _run("force_password_reset", *args)


def test_execute_invalidates_selected_accounts_and_audits(population):
    users, refresh = population
    output = _run("force_password_reset", "--joined-on-or-before", CUTOFF, "--execute", "--reason", "OD-06 test")
    assert "EXECUTED" in output
    for key in ("old", "edge", "noemail"):
        assert not _usable(users[key])
    assert _usable(users["admin"]), "superusers are skipped without --include-superusers"
    assert _usable(users["new"]), "accounts created after the cut-off are untouched"

    blacklisted_users = set(BlacklistedToken.objects.values_list("token__user__username", flat=True))
    assert blacklisted_users == {users[k].username for k in ("old", "edge", "noemail")}
    with pytest.raises(TokenError):
        RefreshToken(str(refresh["old"])).check_blacklist()
    RefreshToken(str(refresh["new"])).check_blacklist()  # not blacklisted

    logs = ActivityLog.objects.filter(module="security")
    assert logs.count() == 4  # 3 per-user rows + 1 summary
    summary = logs.get(username="system:force_password_reset")
    assert summary.extra["selected"] == 3
    assert summary.extra["superusers_skipped"] == 1
    assert summary.extra["reason"] == "OD-06 test"
    assert summary.extra["criteria"]["joined_on_or_before"] == CUTOFF
    assert set(logs.exclude(pk=summary.pk).values_list("user__username", flat=True)) == {
        users[k].username for k in ("old", "edge", "noemail")
    }


def test_include_superusers_flag(population):
    users, _ = population
    _run("force_password_reset", "--joined-on-or-before", CUTOFF, "--include-superusers",
         "--execute", "--reason", "OD-06 test")
    assert not _usable(users["admin"])
    assert _usable(users["new"])


def test_usernames_file_is_unioned_with_cutoff(population, tmp_path):
    users, _ = population
    names = tmp_path / "exposed.txt"
    names.write_text("# exported from the dump inventory\nod06_new\nod06_ghost\n\n")
    output = _run("force_password_reset", "--usernames-file", str(names))
    assert _count(output, "usernames in file") == 2
    assert _count(output, "usernames not found") == 1
    assert _count(output, "selected accounts") == 1

    output = _run("force_password_reset", "--usernames-file", str(names),
                  "--joined-on-or-before", CUTOFF, "--execute", "--reason", "OD-06 test")
    assert _count(output, "selected accounts") == 4
    assert not _usable(users["new"])


def test_rerun_is_idempotent(population):
    _run("force_password_reset", "--joined-on-or-before", CUTOFF, "--execute", "--reason", "first")
    output = _run("force_password_reset", "--joined-on-or-before", CUTOFF)
    assert _count(output, "passwords to invalidate") == 0
    assert _count(output, "already unusable") == 3
    assert _count(output, "refresh tokens to blacklist") == 0


def test_reset_flow_still_works_and_old_links_die(population):
    users, _ = population
    user = users["old"]
    stale_token = default_token_generator.make_token(user)
    _run("force_password_reset", "--joined-on-or-before", CUTOFF, "--execute", "--reason", "OD-06 test")
    user.refresh_from_db()
    client = APIClient()
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    stale = client.post("/api/auth/password-reset-confirm/",
                        {"uid": uid, "token": stale_token, "new_password": "Fresh-Pass-456!xyz"}, format="json")
    assert stale.status_code == 400

    fresh_token = default_token_generator.make_token(user)
    fresh = client.post("/api/auth/password-reset-confirm/",
                        {"uid": uid, "token": fresh_token, "new_password": "Fresh-Pass-456!xyz"}, format="json")
    assert fresh.status_code == 200, fresh.content
    user.refresh_from_db()
    assert user.check_password("Fresh-Pass-456!xyz")


# ── invalidate_all_sessions ──────────────────────────────────────────────────

def _make_session(user):
    store = SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store.create()
    return store.session_key


def _expire_one_token(user):
    token = OutstandingToken.objects.filter(user=user).first()
    OutstandingToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(days=1))


def test_invalidate_all_dry_run_counts_only(population):
    users, _ = population
    _make_session(users["old"])
    _make_session(users["new"])
    output = _run("invalidate_all_sessions")
    assert "DRY RUN" in output
    assert _count(output, "sessions to delete") == 2
    assert _count(output, "refresh tokens to blacklist") == 5
    assert Session.objects.count() == 2
    assert BlacklistedToken.objects.count() == 0
    assert not ActivityLog.objects.filter(module="security").exists()


def test_invalidate_all_execute_requires_reason(db):
    with pytest.raises(CommandError, match="--reason"):
        _run("invalidate_all_sessions", "--execute")


def test_invalidate_all_execute_deletes_sessions_blacklists_and_audits(population):
    users, refresh = population
    _make_session(users["old"])
    _make_session(users["admin"])
    output = _run("invalidate_all_sessions", "--execute", "--reason", "OD-06 test")
    assert "EXECUTED" in output
    assert Session.objects.count() == 0
    assert BlacklistedToken.objects.count() == OutstandingToken.objects.count() == 5
    for token in refresh.values():
        with pytest.raises(TokenError):
            RefreshToken(str(token)).check_blacklist()
    log = ActivityLog.objects.get(module="security", username="system:invalidate_all_sessions")
    assert log.action == ActivityLog.ACTION_DELETE
    assert log.extra["sessions_deleted"] == 2
    assert log.extra["tokens_blacklisted"] == 5


def test_invalidate_all_flush_expired(population):
    users, _ = population
    _expire_one_token(users["new"])
    output = _run("invalidate_all_sessions", "--flush-expired")
    assert _count(output, "expired tokens to flush") == 1
    assert OutstandingToken.objects.count() == 5
    _run("invalidate_all_sessions", "--flush-expired", "--execute", "--reason", "OD-06 test")
    assert OutstandingToken.objects.count() == 4
    assert BlacklistedToken.objects.count() == 4
