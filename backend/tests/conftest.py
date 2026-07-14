pytest_plugins = ["conftest_managed"]

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


# ---------------------------------------------------------------------------
# Base client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


# ---------------------------------------------------------------------------
# Legacy auth_token / authenticated_client (kept for backward compat)
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_token(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="testuser",
        password="testpassword123",
        email="test@example.com",
    )
    refresh = RefreshToken.for_user(user)
    return {
        "user": user,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@pytest.fixture
def authenticated_client(api_client, auth_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token['access']}")
    return api_client


# ---------------------------------------------------------------------------
# Shared role-user fixtures — available to all test modules
# ---------------------------------------------------------------------------

def _ensure_group(name: str) -> Group:
    """Get-or-create a Django Group by role-code name."""
    g, _ = Group.objects.get_or_create(name=name)
    return g


@pytest.fixture
def viewer_user(db, django_user_model):
    """
    User with LICENSE_VIEWER role only.
    Per BR-14: read access is allowed; write operations must be blocked (403).
    """
    user = django_user_model.objects.create_user(
        username="cf_viewer",
        password="viewer_pass123",
        email="cf_viewer@example.com",
    )
    user.groups.add(_ensure_group("LICENSE_VIEWER"))
    return user


@pytest.fixture
def manager_user(db, django_user_model):
    """
    User with LICENSE_MANAGER role.
    Per BR-14: manager roles grant full read + write access.
    """
    user = django_user_model.objects.create_user(
        username="cf_manager",
        password="mgr_pass123",
        email="cf_manager@example.com",
    )
    user.groups.add(_ensure_group("LICENSE_MANAGER"))
    return user


@pytest.fixture
def superuser(db, django_user_model):
    """
    Django superuser — bypasses ALL RBAC checks (BR-14).
    """
    return django_user_model.objects.create_superuser(
        username="cf_superuser",
        password="su_pass123",
        email="cf_superuser@example.com",
    )


# ---------------------------------------------------------------------------
# auth_client helper — returns an API client pre-loaded with Bearer token
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_client(api_client):
    """
    Factory fixture.  Usage::

        def test_something(auth_client, manager_user):
            client = auth_client(manager_user)
            client.get("/api/v1/licenses/")

    Returns a function that accepts a user and returns an APIClient with the
    Bearer token already set.
    """
    def _make(user):
        refresh = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        return client

    return _make
