"""
Independent skeptic re-verification of SEC-02.

Not part of the application test suite -- lives under audit_evidence/,
invoked explicitly with pytest so it runs against pytest-django's throwaway
test database (created/destroyed for this run only; the real local
"lmanagement" DB is never touched).

Goal: empirically reproduce, by actually issuing an HTTP request through
Django's test client against the REAL URLconf/view/serializer/permission
code (no mocking of CompanyViewSet, CompanySerializer, or
MasterDataPermission), that an authenticated user with ZERO roles (a
stronger case than the claim's example of INCENTIVE_LICENSE_VIEWER-only,
since it removes any doubt about role-specific carve-outs) can read a
company's banking/PAN/GST fields via GET /api/masters/companies/.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.core.models import CompanyModel

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_zero_role_authenticated_user_can_read_company_banking_fields():
    # User with a valid account but ZERO group memberships (zero roles) --
    # the most restrictive real-world case. Deliberately stronger than the
    # claim's cited example role (INCENTIVE_LICENSE_VIEWER-only) to remove
    # any doubt about a role-specific carve-out somewhere in the stack.
    user = User.objects.create_user(
        username="skeptic-zero-role-user",
        email="skeptic-zero-role-user@example.com",
        password="Sk3pticP@ss123",
    )
    assert user.get_role_codes() == []  # sanity: confirms zero roles

    company = CompanyModel.objects.create(
        iec="SKEP123456",
        name="Skeptic Verify Pvt Ltd",
        pan="ABCDE1234F",
        gst_number="27ABCDE1234F1Z5",
        bank_account_number="000123456789",
        bank_name="HDFC Bank",
        ifsc_code="HDFC0000123",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/masters/companies/")

    print("user roles =", user.get_role_codes())
    print("GET /api/masters/companies/ -> status", resp.status_code)
    if resp.data.get("results"):
        print("BODY KEYS (results[0]) =", sorted(resp.data["results"][0].keys()))
        print("bank_account_number =", resp.data["results"][0].get("bank_account_number"))
        print("bank_name =", resp.data["results"][0].get("bank_name"))
        print("ifsc_code =", resp.data["results"][0].get("ifsc_code"))
        print("pan =", resp.data["results"][0].get("pan"))
        print("gst_number =", resp.data["results"][0].get("gst_number"))

    assert resp.status_code == 200, (
        f"Expected 200 (claim: MasterDataPermission allows any authenticated "
        f"user on SAFE_METHODS, no has_any_role check), got {resp.status_code}: {resp.data}"
    )

    result = resp.data["results"][0]
    for sensitive_field in ("bank_account_number", "bank_name", "ifsc_code", "pan", "gst_number"):
        assert sensitive_field in result, (
            f"Expected {sensitive_field} in response body (CompanySerializer fields='__all__' claim), "
            f"got keys: {sorted(result.keys())}"
        )

    assert result["bank_account_number"] == "000123456789"
    assert result["bank_name"] == "HDFC Bank"
    assert result["ifsc_code"] == "HDFC0000123"
    assert result["pan"] == "ABCDE1234F"
    assert result["gst_number"] == "27ABCDE1234F1Z5"

    print(
        "CONFIRMED: zero-role authenticated user received full banking/PAN/GST "
        "fields via GET /api/masters/companies/"
    )
