"""Superusers automatically hold every role; nobody else is touched."""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.superuser_roles import sync_all_superusers

PASSWORD = "x-Strong-pass-91"
pytestmark = pytest.mark.django_db


def _all_role_names() -> set[str]:
    return set(Group.objects.values_list("name", flat=True))


@pytest.fixture
def roles():
    return [Group.objects.get_or_create(name=name)[0] for name in ("ROLE_A_TEST", "ROLE_B_TEST")]


def test_new_superuser_receives_every_existing_role(roles, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        admin = User.objects.create_superuser(username="su-new", password=PASSWORD)

    assert set(admin.get_role_codes()) == _all_role_names()


def test_new_role_is_granted_to_every_superuser_only(roles, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        admin = User.objects.create_superuser(username="su-1", password=PASSWORD)
        staff = User.objects.create_user(username="staff-1", password=PASSWORD, is_staff=True)
        normal = User.objects.create_user(username="normal-1", password=PASSWORD)
        normal.groups.add(roles[0])
        new_role = Group.objects.create(name="ROLE_NEW_TEST")

    assert new_role in admin.groups.all()
    assert list(staff.groups.all()) == []
    assert list(normal.groups.all()) == [roles[0]]


def test_promoting_a_user_grants_every_role(roles, django_capture_on_commit_callbacks):
    user = User.objects.create_user(username="promote-me", password=PASSWORD)
    assert list(user.groups.all()) == []

    with django_capture_on_commit_callbacks(execute=True):
        user.is_superuser = True
        user.save()

    assert set(user.get_role_codes()) == _all_role_names()


def test_removing_roles_from_a_superuser_is_regranted(roles, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        admin = User.objects.create_superuser(username="su-remove", password=PASSWORD)
    with django_capture_on_commit_callbacks(execute=True):
        admin.groups.set([roles[0]])  # what Admin's form / the user API do
    with django_capture_on_commit_callbacks(execute=True):
        roles[1].accounts_user_set.remove(admin)  # reverse direction
    with django_capture_on_commit_callbacks(execute=True):
        admin.groups.clear()

    assert set(admin.get_role_codes()) == _all_role_names()


def test_user_management_api_cannot_strip_superuser_roles(roles, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        admin = User.objects.create_superuser(username="su-api", password=PASSWORD)
        target = User.objects.create_superuser(username="su-target", password=PASSWORD)
    client = APIClient()
    client.force_authenticate(admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(f"/api/auth/users/{target.pk}/", {"roles": ["ROLE_A_TEST"]}, format="json")

    assert response.status_code == 200, response.content
    assert set(target.get_role_codes()) == _all_role_names()


def test_normal_user_role_assignment_is_exact(roles, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        admin = User.objects.create_superuser(username="su-assign", password=PASSWORD)
        target = User.objects.create_user(username="acct-only", password=PASSWORD)
    client = APIClient()
    client.force_authenticate(admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(f"/api/auth/users/{target.pk}/", {"roles": ["ROLE_B_TEST"]}, format="json")

    assert response.status_code == 200, response.content
    assert target.get_role_codes() == ["ROLE_B_TEST"]


def test_sync_backfills_superusers_that_bypassed_signals(roles):
    user = User.objects.create_user(username="bulk-promoted", password=PASSWORD)
    normal = User.objects.create_user(username="untouched", password=PASSWORD)
    User.objects.filter(pk=user.pk).update(is_superuser=True)  # no signals

    assert sync_all_superusers() == len(_all_role_names())
    assert sync_all_superusers() == 0  # idempotent: no duplicates
    assert set(user.get_role_codes()) == _all_role_names()
    assert list(normal.groups.all()) == []


def test_management_command_and_raw_saves(roles, capsys):
    user = User.objects.create_user(username="cmd-promoted", password=PASSWORD)
    User.objects.filter(pk=user.pk).update(is_superuser=True)

    call_command("sync_superuser_roles")

    assert "assignment(s) added" in capsys.readouterr().out
    assert set(user.get_role_codes()) == _all_role_names()

    # loaddata-style raw saves never trigger grants.
    raw_user = User(username="raw-su", is_superuser=True)
    raw_user.set_password(PASSWORD)
    raw_user.save_base(raw=True)  # sends post_save(raw=True), as loaddata does
    assert list(raw_user.groups.all()) == []
