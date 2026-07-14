"""
tests/reports/test_reports.py

Tests for the async reports app.

CeleryTaskTracker is managed=False in production; the patch_managed fixture
sets managed=True so SQLite creates the table in-memory (same pattern as
tests/tasks/test_tasks.py).

Celery tasks are mocked — we test the HTTP layer only, not the task body.
"""
import uuid
from unittest.mock import patch

import pytest
from apps.core.models import CeleryTaskTracker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# ---------------------------------------------------------------------------
# Patch managed=True so the test DB creates the table
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_managed(db):
    CeleryTaskTracker._meta.managed = True
    yield
    CeleryTaskTracker._meta.managed = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_token(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="reportuser",
        password="testpassword123",
        email="report@example.com",
        is_superuser=True,  # superuser passes ReportDispatchPermission trivially
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
# Test 1: POST balance/generate/ dispatches task and returns 202 + task_id
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_generate_balance_report_dispatches_task(authenticated_client):
    fake_task_id = str(uuid.uuid4())

    with patch(
        "apps.reports.views.uuid.uuid4",
        return_value=uuid.UUID(fake_task_id),
    ), patch(
        "apps.reports.tasks.generate_balance_report_task.apply_async",
    ) as mock_delay:
        url = reverse("reports:balance-generate")
        resp = authenticated_client.post(
            url,
            {"license_ids": [1, 2, 3], "format": "json"},
            format="json",
        )

    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()
    assert "task_id" in data
    assert data["task_id"] == fake_task_id
    mock_delay.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: GET task status returns "pending" for PENDING tracker
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_status_pending(authenticated_client):
    task_id = str(uuid.uuid4())
    CeleryTaskTracker.objects.create(
        task_id=task_id,
        task_name="generate_balance_report_task",
        status="PENDING",
    )

    url = reverse("reports:task-status", kwargs={"task_id": task_id})
    resp = authenticated_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "pending"
    assert data["task_id"] == task_id
    assert data["file_url"] is None


# ---------------------------------------------------------------------------
# Test 3: GET task status returns "done" + file_url for SUCCESS tracker
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_status_done_returns_file_url(authenticated_client, settings):
    settings.MEDIA_URL = "/media/"
    task_id = str(uuid.uuid4())
    rel_path = f"reports/balance_{task_id}.json"

    CeleryTaskTracker.objects.create(
        task_id=task_id,
        task_name="generate_balance_report_task",
        status="SUCCESS",
        result={"file_path": rel_path},
    )

    url = reverse("reports:task-status", kwargs={"task_id": task_id})
    resp = authenticated_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "done"
    assert data["file_url"] is not None
    assert rel_path in data["file_url"]


# ---------------------------------------------------------------------------
# Test 4: Unauthenticated POST returns 401
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_unauthenticated_blocked(api_client):
    url = reverse("reports:balance-generate")
    resp = api_client.post(
        url,
        {"license_ids": [1], "format": "json"},
        format="json",
    )
    # DRF returns 401 for unauthenticated requests when IsAuthenticated is in play
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_task_status_failed_returns_error(authenticated_client):
    task_id = str(uuid.uuid4())
    CeleryTaskTracker.objects.create(
        task_id=task_id,
        task_name="generate_balance_report_task",
        status="FAILURE",
        result={"error": "Something went wrong"},
    )
    url = reverse("reports:task-status", kwargs={"task_id": task_id})
    resp = authenticated_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] in ("failed", "error", "FAILURE")
