"""Credential-invalidation actions for the OD-06 incident response.

Used by the ``force_password_reset`` and ``invalidate_all_sessions``
management commands. Both commands default to a dry run that only counts.
Changes happen only with ``execute=True``, inside one transaction, and are
audited in ``core.ActivityLog`` (module ``security``).

Notes on scope:

* ``set_unusable_password()`` changes the password hash, so Django session
  auth (session hash check) and every outstanding password-reset link
  (``default_token_generator`` hashes the password) become invalid for that
  user. The custom reset flow (``accounts/views/password.py``) does not filter
  on ``has_usable_password()``, so affected users with an email can still
  self-serve a reset.
* Refresh JWTs are blacklisted through simplejwt ``token_blacklist``. Access
  JWTs are stateless and expire within ``ACCESS_TOKEN_LIFETIME`` (30 min by
  default). Rotating ``SECRET_KEY`` invalidates all of them at once.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.core.models import ActivityLog

AUDIT_MODULE = "security"
INCIDENT_REF = "OD-06"
_BATCH_SIZE = 500


@dataclass
class ResetSelection:
    users: QuerySet
    matched_total: int
    superusers_skipped: int
    usernames_requested: int = 0
    usernames_not_found: int = 0


@dataclass
class ResetResult:
    selected: int
    passwords_invalidated: int
    already_unusable: int
    tokens_blacklisted: int
    without_email: int
    executed: bool
    criteria: dict = field(default_factory=dict)


@dataclass
class InvalidateAllResult:
    sessions: int
    tokens_blacklisted: int
    expired_tokens_flushed: int
    executed: bool


def read_usernames_file(lines: Iterable[str]) -> set[str]:
    """One username per line; blank lines and ``#`` comments are ignored."""
    names = set()
    for raw in lines:
        name = raw.split("#", 1)[0].strip()
        if name:
            names.add(name)
    return names


def select_affected_users(
    *,
    joined_on_or_before: date | None,
    usernames: set[str] | None,
    include_superusers: bool,
) -> ResetSelection:
    """Users matching either criterion (union). Superusers are skipped unless asked."""
    if joined_on_or_before is None and not usernames:
        raise ValueError("At least one selection criterion is required.")
    User = get_user_model()
    criteria = Q(pk__in=[])
    if joined_on_or_before is not None:
        criteria |= Q(date_joined__date__lte=joined_on_or_before)
    not_found = 0
    if usernames:
        criteria |= Q(username__in=usernames)
        found = set(User.objects.filter(username__in=usernames).values_list("username", flat=True))
        not_found = len(usernames - found)
    matched = User.objects.filter(criteria)
    matched_total = matched.count()
    superusers = matched.filter(is_superuser=True).count()
    users = matched if include_superusers else matched.filter(is_superuser=False)
    return ResetSelection(
        users=users.order_by("pk"),
        matched_total=matched_total,
        superusers_skipped=0 if include_superusers else superusers,
        usernames_requested=len(usernames or ()),
        usernames_not_found=not_found,
    )


def _unblacklisted_tokens(user_ids=None) -> QuerySet:
    tokens = OutstandingToken.objects.filter(blacklistedtoken__isnull=True)
    if user_ids is not None:
        tokens = tokens.filter(user_id__in=user_ids)
    return tokens


def _blacklist(tokens: QuerySet) -> int:
    ids = list(tokens.values_list("pk", flat=True))
    for start in range(0, len(ids), _BATCH_SIZE):
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token_id=pk) for pk in ids[start:start + _BATCH_SIZE]],
            ignore_conflicts=True,
        )
    return len(ids)


def force_password_reset(
    selection: ResetSelection,
    *,
    execute: bool,
    reason: str = "",
    criteria: dict | None = None,
) -> ResetResult:
    users = selection.users
    user_ids = list(users.values_list("pk", flat=True))
    usable_users = [u for u in users.only("pk", "username", "password", "email") if u.has_usable_password()]
    without_email = users.filter(Q(email__isnull=True) | Q(email="")).count()
    tokens = _unblacklisted_tokens(user_ids)
    result = ResetResult(
        selected=len(user_ids),
        passwords_invalidated=len(usable_users),
        already_unusable=len(user_ids) - len(usable_users),
        tokens_blacklisted=tokens.count(),
        without_email=without_email,
        executed=execute,
        criteria=dict(criteria or {}),
    )
    if not execute:
        return result

    with transaction.atomic():
        for user in usable_users:
            user.set_unusable_password()
        User = get_user_model()
        for start in range(0, len(usable_users), _BATCH_SIZE):
            User.objects.bulk_update(usable_users[start:start + _BATCH_SIZE], ["password"])
        result.tokens_blacklisted = _blacklist(tokens)
        invalidated_ids = {u.pk for u in usable_users}
        ActivityLog.objects.bulk_create(
            [
                ActivityLog(
                    user_id=user.pk,
                    username=user.username,
                    action=ActivityLog.ACTION_UPDATE,
                    module=AUDIT_MODULE,
                    resource_id=str(user.pk),
                    description=f"{INCIDENT_REF}: password invalidated (forced reset); refresh tokens blacklisted",
                    extra={"incident": INCIDENT_REF, "command": "force_password_reset",
                           "password_invalidated": user.pk in invalidated_ids},
                )
                for user in users.only("pk", "username")
            ],
            batch_size=_BATCH_SIZE,
        )
        ActivityLog.objects.create(
            username="system:force_password_reset",
            action=ActivityLog.ACTION_UPDATE,
            module=AUDIT_MODULE,
            description=f"{INCIDENT_REF}: forced password reset ({result.selected} accounts)"[:500],
            extra={
                "incident": INCIDENT_REF,
                "command": "force_password_reset",
                "reason": reason[:300],
                "criteria": result.criteria,
                "selected": result.selected,
                "passwords_invalidated": result.passwords_invalidated,
                "already_unusable": result.already_unusable,
                "tokens_blacklisted": result.tokens_blacklisted,
                "superusers_skipped": selection.superusers_skipped,
                "without_email": result.without_email,
                "executed_at": timezone.now().isoformat(),
            },
        )
    return result


def invalidate_all_sessions(*, execute: bool, flush_expired: bool, reason: str = "") -> InvalidateAllResult:
    sessions = Session.objects.all()
    tokens = _unblacklisted_tokens()
    expired = OutstandingToken.objects.filter(expires_at__lt=timezone.now())
    result = InvalidateAllResult(
        sessions=sessions.count(),
        tokens_blacklisted=tokens.count(),
        expired_tokens_flushed=expired.count() if flush_expired else 0,
        executed=execute,
    )
    if not execute:
        return result

    with transaction.atomic():
        result.sessions = sessions.delete()[0]
        result.tokens_blacklisted = _blacklist(tokens)
        if flush_expired:
            # Same semantics as simplejwt's ``flushexpiredtokens``: expired
            # outstanding tokens (and their blacklist rows, by cascade) go away.
            result.expired_tokens_flushed = expired.count()
            expired.delete()
        ActivityLog.objects.create(
            username="system:invalidate_all_sessions",
            action=ActivityLog.ACTION_DELETE,
            module=AUDIT_MODULE,
            description=f"{INCIDENT_REF}: all sessions deleted and all refresh tokens blacklisted"[:500],
            extra={
                "incident": INCIDENT_REF,
                "command": "invalidate_all_sessions",
                "reason": reason[:300],
                "sessions_deleted": result.sessions,
                "tokens_blacklisted": result.tokens_blacklisted,
                "expired_tokens_flushed": result.expired_tokens_flushed,
                "executed_at": timezone.now().isoformat(),
            },
        )
    return result
