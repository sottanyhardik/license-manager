"""Accounting roles must be assignable through the user-admin UI.

The admin user form and the Settings page build their role checkboxes from
``GET /api/auth/users/available-roles/`` (``ROLE_CODES``). Without the ACCOUNTS_* codes
no non-superuser could be granted the Accounting workspace, so the main navigation
and the ``/accounting/*`` route guard hid it from everyone except superusers.
"""

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.permissions import ACCOUNTS_READ_ROLES
from apps.accounts.views.user_management import ROLE_CODES

ACCOUNTING_ROLE_CODES = ("ACCOUNTS_VIEWER", "ACCOUNTS_MANAGER", "ACCOUNTS_APPROVER")
PASSWORD = "x-Strong-pass-91"


def _admin_client(username: str) -> APIClient:
    admin = User.objects.create_superuser(username=username, password=PASSWORD)
    client = APIClient()
    client.force_authenticate(admin)
    return client


def test_role_codes_include_every_accounting_read_role() -> None:
    assert set(ACCOUNTS_READ_ROLES) <= set(ROLE_CODES)
    assert len(ROLE_CODES) == len(set(ROLE_CODES))


@pytest.mark.django_db
def test_available_roles_endpoint_lists_accounting_roles() -> None:
    response = _admin_client("roles-admin").get("/api/auth/users/available-roles/")

    assert response.status_code == 200
    for code in ACCOUNTING_ROLE_CODES:
        assert code in response.json()


@pytest.mark.django_db
def test_accounting_role_can_be_assigned_through_user_management() -> None:
    for code in ACCOUNTING_ROLE_CODES:  # created by accounting/0003 on real databases
        Group.objects.get_or_create(name=code)
    target = User.objects.create_user(username="acct-clerk", password=PASSWORD)

    response = _admin_client("roles-admin2").patch(
        f"/api/auth/users/{target.pk}/", {"roles": ["ACCOUNTS_VIEWER"]}, format="json",
    )

    assert response.status_code == 200, response.content
    assert "ACCOUNTS_VIEWER" in response.json()["roles"]
    assert target.has_any_role(ACCOUNTS_READ_ROLES)
