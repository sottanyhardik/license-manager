# tests/accounts/test_auth.py
"""
Phase 1 Authentication test suite.

Covers:
- Login: success, invalid credentials, inactive user
- Logout: blacklists refresh token
- /me: authenticated and unauthenticated
- Token refresh: rotation makes old token invalid
- RBAC: permission class blocks wrong role
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.accounts.factories import UserFactory, GroupFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_tokens(user):
    """Return a (access_str, refresh_str) tuple for *user*."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def _client_with_token(access_token: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLogin:
    url = "/api/v1/auth/login/"

    def test_login_success(self):
        user = UserFactory(username="alice", password=None)
        user.set_password("secret123")
        user.save()

        client = APIClient()
        response = client.post(self.url, {"username": "alice", "password": "secret123"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access" in data["data"]
        assert "refresh" in data["data"]
        assert data["data"]["user"]["username"] == "alice"

    def test_login_invalid_credentials(self):
        UserFactory(username="bob")
        client = APIClient()
        response = client.post(self.url, {"username": "bob", "password": "wrongpass"}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["success"] is False

    def test_login_inactive_user(self):
        user = UserFactory(username="charlie", is_active=False, password=None)
        user.set_password("secret123")
        user.save()

        client = APIClient()
        response = client.post(self.url, {"username": "charlie", "password": "secret123"}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["success"] is False

    def test_login_missing_fields(self):
        client = APIClient()
        response = client.post(self.url, {"username": "dave"}, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["success"] is False


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLogout:
    login_url = "/api/v1/auth/login/"
    logout_url = "/api/v1/auth/logout/"
    refresh_url = "/api/v1/auth/token/refresh/"

    def test_logout_blacklists_token(self):
        user = UserFactory(username="eve", password=None)
        user.set_password("secret123")
        user.save()
        access, refresh = _get_tokens(user)

        client = _client_with_token(access)
        resp = client.post(self.logout_url, {"refresh": refresh}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["success"] is True

        # Attempt to reuse the blacklisted refresh token
        anon = APIClient()
        resp2 = anon.post(self.refresh_url, {"refresh": refresh}, format="json")
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_requires_authentication(self):
        client = APIClient()
        resp = client.post(self.logout_url, {"refresh": "dummy"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_missing_refresh_token(self):
        user = UserFactory()
        access, _ = _get_tokens(user)
        client = _client_with_token(access)
        resp = client.post(self.logout_url, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["success"] is False


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMeEndpoint:
    url = "/api/v1/auth/me/"

    def test_me_returns_user(self):
        user = UserFactory(username="frank", email="frank@example.com")
        access, _ = _get_tokens(user)
        client = _client_with_token(access)

        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["username"] == "frank"
        assert data["data"]["email"] == "frank@example.com"
        assert "roles" in data["data"]

    def test_me_unauthenticated(self):
        client = APIClient()
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_includes_roles(self):
        user = UserFactory(username="grace")
        group = GroupFactory(name="LICENSE_MANAGER")
        user.groups.add(group)
        access, _ = _get_tokens(user)

        client = _client_with_token(access)
        resp = client.get(self.url)
        assert resp.status_code == status.HTTP_200_OK
        assert "LICENSE_MANAGER" in resp.json()["data"]["roles"]


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTokenRefresh:
    url = "/api/v1/auth/token/refresh/"

    def test_refresh_returns_new_tokens(self):
        user = UserFactory()
        _, refresh = _get_tokens(user)

        client = APIClient()
        resp = client.post(self.url, {"refresh": refresh}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "access" in data["data"]
        assert "refresh" in data["data"]

    def test_refresh_rotates_token(self):
        """After rotation the old refresh token must be rejected."""
        user = UserFactory()
        _, old_refresh = _get_tokens(user)

        client = APIClient()
        resp = client.post(self.url, {"refresh": old_refresh}, format="json")
        assert resp.status_code == status.HTTP_200_OK

        # Reuse the old refresh — must fail because BLACKLIST_AFTER_ROTATION=True
        resp2 = client.post(self.url, {"refresh": old_refresh}, format="json")
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_token(self):
        client = APIClient()
        resp = client.post(self.url, {"refresh": "not.a.valid.token"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# RBAC permission gating
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRBACPermissions:
    """
    Verify that BaseRolePermission subclasses correctly gate access.
    We use LicensePermission as a concrete representative.
    """

    def _make_request(self, method="GET"):
        """Return a mock-like object that satisfies BaseRolePermission interface."""
        from unittest.mock import MagicMock
        from rest_framework import permissions as drf_permissions

        req = MagicMock()
        req.method = method
        return req

    def test_superuser_always_passes(self):
        from apps.accounts.permissions import LicensePermission

        user = UserFactory(is_superuser=True)
        perm = LicensePermission()
        req = self._make_request("POST")
        req.user = user
        assert perm.has_permission(req, None) is True

    def test_unauthenticated_blocked(self):
        from apps.accounts.permissions import LicensePermission
        from unittest.mock import MagicMock

        perm = LicensePermission()
        req = self._make_request("GET")
        user = MagicMock()
        user.is_superuser = False
        user.is_authenticated = False
        req.user = user
        assert perm.has_permission(req, None) is False

    def test_wrong_role_blocked_on_write(self):
        """A user with ALLOTMENT_VIEWER cannot write via LicensePermission."""
        user = UserFactory()
        group = GroupFactory(name="ALLOTMENT_VIEWER")
        user.groups.add(group)

        from apps.accounts.permissions import LicensePermission
        from unittest.mock import MagicMock
        from rest_framework import permissions as drf_permissions

        perm = LicensePermission()
        req = MagicMock()
        req.method = "POST"
        req.user = user
        # SAFE_METHODS is a tuple; POST is not in it
        assert perm.has_permission(req, None) is False

    def test_correct_role_allows_read(self):
        """LICENSE_VIEWER can read via LicensePermission."""
        user = UserFactory()
        group = GroupFactory(name="LICENSE_VIEWER")
        user.groups.add(group)

        from apps.accounts.permissions import LicensePermission
        from unittest.mock import MagicMock
        from rest_framework import permissions as drf_permissions

        perm = LicensePermission()
        req = MagicMock()
        req.method = "GET"
        req.user = user
        # is_authenticated must be truthy
        user.is_superuser = False
        user.is_authenticated = True
        assert perm.has_permission(req, None) is True

    def test_permission_class_blocks_wrong_role(self):
        """
        Explicit acceptance criterion: call a real DRF view permission check
        using UserManagementPermission and verify a non-USER_MANAGER is blocked.
        """
        user = UserFactory()
        group = GroupFactory(name="TRADE_VIEWER")
        user.groups.add(group)

        from apps.accounts.permissions import UserManagementPermission
        from unittest.mock import MagicMock

        perm = UserManagementPermission()
        req = MagicMock()
        req.method = "GET"
        req.user = user
        user.is_superuser = False
        user.is_authenticated = True

        # TRADE_VIEWER is NOT in UserManagementPermission.required_roles_for_read
        assert perm.has_permission(req, None) is False
