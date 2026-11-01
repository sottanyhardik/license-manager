"""Anonymous and role-less access to critical API endpoints.

Scope: authentication and role gates only. These tests do not decide the
company/object access policy (decision D1); see test_item_pivot_authorization.py
for the cross-company characterization.

Each endpoint must reject an anonymous caller before validation or lookup, so
an unauthenticated request cannot learn whether a record exists or which
validation rules apply.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

LIST_PATHS = [
    "/api/licenses/",
    "/api/allotments/",
    "/api/bill-of-entries/",
    "/api/trades/",
    "/api/license-ledger/",
    "/api/masters/companies/",
    "/api/reports/item-pivot/",
]

WRITE_PATHS = [
    "/api/licenses/",
    "/api/allotments/",
    "/api/bill-of-entries/",
    "/api/trades/",
    "/api/masters/companies/",
]


def _anonymous():
    return APIClient()


def _authenticated_without_roles(db):
    user = User.objects.create_user(
        username="api-norole", email="api-norole@example.com", password="RoleP@ssw0rd123"
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.parametrize("path", LIST_PATHS)
def test_anonymous_list_is_rejected(db, path):
    response = _anonymous().get(path)
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_anonymous_write_is_rejected_before_validation(db, path):
    # An empty body would fail validation with 400. Authentication must come first.
    response = _anonymous().post(path, {}, format="json")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", LIST_PATHS)
def test_role_less_user_is_forbidden_on_list(db, path):
    response = _authenticated_without_roles(db).get(path)
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/api/licenses/999999999/", "/api/allotments/999999999/", "/api/trades/999999999/"])
def test_anonymous_detail_does_not_reveal_existence(db, path):
    """A nonexistent id and an existing id must look the same to an anonymous caller."""
    response = _anonymous().get(path)
    assert response.status_code in (401, 403)
