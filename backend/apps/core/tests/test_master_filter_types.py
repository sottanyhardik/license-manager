"""
Regression coverage for the global Purchase Status / Norm filter
standardization: every consumer across the portal now fetches these two
option lists from `usePurchaseStatusOptions`/`useSionNormOptions`, which
both pass `is_active=true` straight through to the masters API — so that
param must actually filter, not silently no-op.

`MasterViewSet.apply_advanced_filters` (apps/core/views/master_view.py)
only recognises "exact", "icontains", "date_range", "range",
"related_exact", "in", "fk", "exclude_fk" as filter types — "boolean" was
never implemented. `SionNormClassViewSet` declared its `is_active` filter
as `{"type": "boolean"}`, so `?is_active=true` (and `=false`) were both
silent no-ops and every list request returned all ~2,000+ norm classes
(all but a handful inactive) regardless of the filter. Fixed by switching
to `{"type": "exact"}` — the same type `PurchaseStatusViewSet` already
used correctly.
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

from apps.core.models import HeadSIONNormsModel, PurchaseStatus, SionNormClassModel

User = get_user_model()

SION_CLASSES_URL = "/api/masters/sion-classes/"
PURCHASE_STATUSES_URL = "/api/masters/purchase-statuses/"


@pytest.fixture
def authed_client(db):
    user = User.objects.create_user(
        username="master-filter-viewer",
        email="master-filter-viewer@example.com",
        password="RoleP@ssw0rd123",
    )
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.mark.django_db
def test_sion_norm_class_is_active_filter_actually_filters(authed_client):
    head = HeadSIONNormsModel.objects.create(name="TEST-HEAD")
    active = SionNormClassModel.objects.create(
        head_norm=head, norm_class="ZT-ACTIVE", description="Active test norm", is_active=True,
    )
    inactive = SionNormClassModel.objects.create(
        head_norm=head, norm_class="ZT-INACT", description="Inactive test norm", is_active=False,
    )

    active_only = authed_client.get(SION_CLASSES_URL, {"is_active": "true"})
    assert active_only.status_code == 200
    codes = {row["norm_class"] for row in active_only.json().get("results", active_only.json())}
    assert active.norm_class in codes
    assert inactive.norm_class not in codes

    inactive_only = authed_client.get(SION_CLASSES_URL, {"is_active": "false"})
    codes = {row["norm_class"] for row in inactive_only.json().get("results", inactive_only.json())}
    assert inactive.norm_class in codes
    assert active.norm_class not in codes


@pytest.mark.django_db
def test_purchase_status_is_active_filter_actually_filters(authed_client):
    """Baseline for the type that already worked correctly ("exact") —
    guards against a future regression back to the broken "boolean" type."""
    active = PurchaseStatus.objects.create(code="ZA", label="Z Active Test", is_active=True)
    inactive = PurchaseStatus.objects.create(code="ZI", label="Z Inactive Test", is_active=False)

    response = authed_client.get(PURCHASE_STATUSES_URL, {"is_active": "true"})
    assert response.status_code == 200
    codes = {row["code"] for row in response.json().get("results", response.json())}
    assert active.code in codes
    assert inactive.code not in codes
