"""Negative authorization tests for the Item Pivot report (JSON and Excel).

The report is protected by ``ReportPermission``, which is a role check
(apps/accounts/permissions.py). It does not scope data by company. The
cross-company test below therefore pins CURRENT behaviour pending owner
decision D1 (company/object access policy). It is not an approval of that
behaviour: when D1 is decided, update this test together with the policy.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.constants import GE
from apps.core.models import CompanyModel, PurchaseStatus
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel

User = get_user_model()
PIVOT_URL = "/api/reports/item-pivot/"


def _client_for(user):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def report_viewer(db):
    user = User.objects.create_user(
        username="pivot-viewer", email="pivot-viewer@example.com", password="RoleP@ssw0rd123"
    )
    user.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
    return user


@pytest.fixture
def role_less_user(db):
    return User.objects.create_user(
        username="pivot-norole", email="pivot-norole@example.com", password="RoleP@ssw0rd123"
    )


@pytest.fixture
def foreign_company_licence(db):
    """A visible, active GE-status licence belonging to a company the viewer was never assigned."""
    company = CompanyModel.objects.create(iec=f"88{uuid.uuid4().int % 10**8:08d}", name="Other Tenant Exporter")
    status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
    today = date.today()
    licence = LicenseDetailsModel.objects.create(
        license_number=f"AUTH{uuid.uuid4().int % 10**8:08d}",
        license_date=today - timedelta(days=30),
        license_expiry_date=today + timedelta(days=365),
        exporter=company,
        purchase_status=status,
    )
    LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("1000.00"))
    return licence


@pytest.mark.parametrize("fmt", [None, "excel"])
def test_anonymous_request_is_rejected(db, fmt):
    params = {"format": fmt} if fmt else {}
    response = _client_for(None).get(PIVOT_URL, params)
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("fmt", [None, "excel"])
def test_authenticated_user_without_report_role_is_forbidden(role_less_user, fmt):
    params = {"format": fmt} if fmt else {}
    response = _client_for(role_less_user).get(PIVOT_URL, params)
    assert response.status_code == 403


def test_report_viewer_can_read_json(report_viewer):
    response = _client_for(report_viewer).get(PIVOT_URL)
    assert response.status_code == 200
    assert "grand_total" in response.json()


def test_d1_current_behaviour_report_viewer_sees_licence_from_unassigned_company(
    report_viewer, foreign_company_licence
):
    """CHARACTERIZATION (D1, not an approval): ReportPermission has no company
    scope, so a REPORT_VIEWER receives a licence belonging to a company they
    were never assigned. Update this test with the D1 policy decision."""
    response = _client_for(report_viewer).get(
        PIVOT_URL, {"min_balance": "0", "license_status": "all", "purchase_status": GE}
    )
    assert response.status_code == 200
    assert response.json()["grand_total"]["license_count"] >= 1
