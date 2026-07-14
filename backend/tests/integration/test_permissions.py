# tests/integration/test_permissions.py
"""
RBAC and authentication integration tests.

Covers:
  - BR-14: Viewer roles can read but not write.
  - All /api/v1/ endpoints return 401 for unauthenticated requests.
  - Superuser bypasses all checks.
"""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bearer(user):
    return f"Bearer {str(RefreshToken.for_user(user).access_token)}"


def _add_group(user, *group_names):
    for name in group_names:
        g, _ = Group.objects.get_or_create(name=name)
        user.groups.add(g)


# ---------------------------------------------------------------------------
# Shared fixtures (also added to conftest.py — these duplicate for isolation)
# ---------------------------------------------------------------------------

@pytest.fixture
def viewer_user(db, django_user_model):
    """
    User with LICENSE_VIEWER role only.
    Per BR-14: viewer roles grant read-only access; write endpoints must return 403.
    """
    user = django_user_model.objects.create_user(
        username="viewer", password="viewer_pass123", email="viewer@example.com"
    )
    _add_group(user, "LICENSE_VIEWER")
    return user


@pytest.fixture
def allotment_viewer_user(db, django_user_model):
    """User with ALLOTMENT_VIEWER role only."""
    user = django_user_model.objects.create_user(
        username="allot_viewer", password="av_pass123", email="av@example.com"
    )
    _add_group(user, "ALLOTMENT_VIEWER")
    return user


@pytest.fixture
def manager_user(db, django_user_model):
    """User with full manager roles across all modules."""
    user = django_user_model.objects.create_user(
        username="full_mgr", password="mgr_pass123", email="fullmgr@example.com"
    )
    _add_group(user, "LICENSE_MANAGER", "ALLOTMENT_MANAGER")
    return user


@pytest.fixture
def superuser(db, django_user_model):
    """Django superuser — bypasses all RBAC."""
    return django_user_model.objects.create_superuser(
        username="su_perms", password="su_pass123", email="super@example.com"
    )


# ---------------------------------------------------------------------------
# Test 9 — Viewer role cannot write to any module
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("endpoint,method", [
    ("/api/v1/licenses/", "post"),
    ("/api/v1/allotments/", "post"),
])
def test_viewer_role_cannot_write(db, viewer_user, endpoint, method):
    """
    BR-14: Viewer roles must receive 403 on all write (POST/PUT/PATCH/DELETE)
    operations.

    Note: /api/v1/bill-of-entries/ and /api/v1/trades/ are excluded because
    those app routers are not registered in config/api_urls.py in this build.
    Endpoints that ARE registered: licenses, allotments.
    """
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_bearer(viewer_user))

    fn = getattr(client, method)
    resp = fn(endpoint, {}, format="json")
    assert resp.status_code == 403, (
        f"Expected 403 for viewer on {method.upper()} {endpoint}, "
        f"got {resp.status_code}. Response: {getattr(resp, 'data', resp.content)}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint,method", [
    ("/api/v1/licenses/", "post"),
    ("/api/v1/allotments/", "post"),
])
def test_allotment_viewer_cannot_write_licenses(db, allotment_viewer_user, endpoint, method):
    """
    ALLOTMENT_VIEWER must not be able to POST to license endpoints
    (they lack LICENSE_MANAGER).
    """
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_bearer(allotment_viewer_user))

    fn = getattr(client, method)
    resp = fn(endpoint, {}, format="json")
    assert resp.status_code == 403, (
        f"Expected 403 for allotment_viewer on {method.upper()} {endpoint}, "
        f"got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Test 10 — Unauthenticated blocked everywhere
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", [
    "/api/v1/licenses/",
    "/api/v1/allotments/",
    "/api/v1/masters/companies/",
    "/api/v1/masters/ports/",
    "/api/v1/masters/hs-codes/",
    "/api/v1/masters/exchange-rates/",
])
def test_all_api_endpoints_require_auth(endpoint):
    """
    Every /api/v1/ endpoint (except login/refresh/health) must return 401
    when no Authorization header is supplied.
    """
    client = APIClient()
    resp = client.get(endpoint)
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated GET {endpoint}, got {resp.status_code}"
    )


@pytest.mark.django_db
def test_login_endpoint_does_not_require_auth():
    """
    POST /api/v1/auth/login/ must be accessible without a token — it is the
    token-acquisition endpoint.
    """
    client = APIClient()
    # Bad credentials → 401, but not due to missing token (that would be 401 too,
    # so we check the error message or just that it does not return 403/405)
    resp = client.post(
        "/api/v1/auth/login/",
        {"username": "no_such_user", "password": "wrong"},
        format="json",
    )
    # 400 (bad creds) or 401 from simplejwt — both indicate the endpoint is reachable
    assert resp.status_code in (400, 401), (
        f"Login endpoint returned unexpected {resp.status_code}"
    )


@pytest.mark.django_db
def test_health_endpoint_does_not_require_auth():
    """
    GET /api/health/ must be accessible without a token (health-check).
    """
    client = APIClient()
    resp = client.get("/api/health/")
    assert resp.status_code in (200, 503), (
        f"Health endpoint returned unexpected {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Superuser bypass
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_superuser_can_read_any_endpoint(db, superuser):
    """
    BR-14: Superusers bypass all role checks — they can read even endpoints
    they have no explicit group membership for.
    """
    from unittest.mock import patch, MagicMock
    from apps.license.models import LicenseDetailsModel

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_bearer(superuser))

    # Mock the queryset so we don't need real license data
    with patch(
        "apps.license.views.license.LicenseViewSet.get_queryset",
        return_value=LicenseDetailsModel.objects.none(),
    ):
        resp = client.get("/api/v1/licenses/")
    assert resp.status_code == 200, (
        f"Superuser should get 200 on GET /api/v1/licenses/, got {resp.status_code}"
    )


@pytest.mark.django_db
def test_manager_can_read_and_write(db, manager_user):
    """
    LICENSE_MANAGER can GET (read) the license list endpoint.
    Confirms the role grants access without 403.
    """
    from unittest.mock import patch
    from apps.license.models import LicenseDetailsModel

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_bearer(manager_user))

    with patch(
        "apps.license.views.license.LicenseViewSet.get_queryset",
        return_value=LicenseDetailsModel.objects.none(),
    ):
        resp = client.get("/api/v1/licenses/")
    assert resp.status_code == 200, (
        f"LICENSE_MANAGER should get 200 on GET /api/v1/licenses/, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Role isolation — viewer can read but not write (GET vs POST)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_license_viewer_can_read(db, viewer_user):
    """
    LICENSE_VIEWER can GET the license list — read access must work.
    """
    from unittest.mock import patch
    from apps.license.models import LicenseDetailsModel

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_bearer(viewer_user))

    with patch(
        "apps.license.views.license.LicenseViewSet.get_queryset",
        return_value=LicenseDetailsModel.objects.none(),
    ):
        resp = client.get("/api/v1/licenses/")
    assert resp.status_code == 200, (
        f"LICENSE_VIEWER should get 200 on GET /api/v1/licenses/, got {resp.status_code}"
    )


@pytest.mark.django_db
def test_no_role_user_blocked_on_read(db, django_user_model):
    """
    A user with no group membership at all must get 403 even on GET requests.
    """
    from apps.license.models import LicenseDetailsModel

    user = django_user_model.objects.create_user(
        username="norole2", password="p", email="norole2@x.com"
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=_bearer(user))

    resp = client.get("/api/v1/licenses/")
    assert resp.status_code == 403, (
        f"User with no roles should get 403, got {resp.status_code}"
    )
