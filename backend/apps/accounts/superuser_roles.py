"""Superusers hold every role.

Roles are Django ``Group`` rows (``User.has_role`` / ``has_any_role`` / ``get_role_codes``).
Superusers already bypass most role checks, but several code paths read group membership
directly (``has_any_role``, ``/me`` ``roles``, user lists filtered by role), so a superuser
must also *belong* to every group:

* every existing superuser gets every existing role (``post_migrate`` + ``sync_superuser_roles``),
* a newly created role is granted to every superuser,
* a newly created (or promoted) superuser gets every role,
* removing a role from a superuser (Admin, user-management API, imports) is re-granted.

Only ``is_superuser=True`` users are touched; ordinary users, ``is_staff`` admins and
their assignments are never changed. Grants insert directly into the auto-created
``user_groups`` through table with ``bulk_create(ignore_conflicts=True)``: idempotent,
safe under concurrent inserts (unique user/group pair), and it sends no ``m2m_changed``,
so the signal receivers cannot recurse. Demoting a superuser leaves their roles as they are.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


def _through():
    return get_user_model().groups.through


def _insert_missing(user_ids: list[int], group_ids: list[int], using: str) -> int:
    if not user_ids or not group_ids:
        return 0
    through = _through()
    existing = set(
        through.objects.using(using)
        .filter(user_id__in=user_ids, group_id__in=group_ids)
        .values_list("user_id", "group_id")
    )
    rows = [
        through(user_id=user_id, group_id=group_id)
        for user_id in user_ids
        for group_id in group_ids
        if (user_id, group_id) not in existing
    ]
    through.objects.using(using).bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def _superuser_ids(using: str, user_ids: list[int] | None = None) -> list[int]:
    qs = get_user_model().objects.using(using).filter(is_superuser=True)
    if user_ids is not None:
        qs = qs.filter(pk__in=user_ids)
    return list(qs.values_list("pk", flat=True))


def grant_all_roles_to_user(user_id: int, using: str = "default") -> int:
    """Give one user every role if (still) a superuser. Returns the number of grants added."""
    group_ids = list(Group.objects.using(using).values_list("pk", flat=True))
    return _insert_missing(_superuser_ids(using, [user_id]), group_ids, using)


def grant_role_to_superusers(group_id: int, using: str = "default") -> int:
    """Give one role to every superuser. Returns the number of grants added."""
    return _insert_missing(_superuser_ids(using), [group_id], using)


def sync_all_superusers(using: str = "default") -> int:
    """Give every superuser every role. Idempotent; returns the number of grants added."""
    group_ids = list(Group.objects.using(using).values_list("pk", flat=True))
    return _insert_missing(_superuser_ids(using), group_ids, using)
