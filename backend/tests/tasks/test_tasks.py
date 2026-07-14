"""
tests/tasks/test_tasks.py

Integration tests for the tasks API.
All models are managed=False in production; this file patches managed=True
so that SQLite creates the tables in-memory for the test run (same pattern
as tests/core/test_masters.py).
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import factory
from factory.django import DjangoModelFactory

from apps.tasks.models import Task, TaskRemark


# ── Patch managed=True ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_managed(db):
    Task._meta.managed = True
    TaskRemark._meta.managed = True
    yield
    Task._meta.managed = False
    TaskRemark._meta.managed = False


# ── Factories ─────────────────────────────────────────────────────────────────

class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Task {n}")
    status = Task.STATUS_PENDING
    priority = Task.PRIORITY_NORMAL


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username="tester", password="pass123")


@pytest.fixture
def other_user(db, django_user_model):
    return django_user_model.objects.create_user(username="other", password="pass456")


@pytest.fixture
def auth_client(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_task(auth_client, user):
    url = reverse("tasks:task-list")
    resp = auth_client.post(url, {"title": "Buy milk", "priority": "normal"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["title"] == "Buy milk"
    assert data["status"] == Task.STATUS_PENDING


@pytest.mark.django_db
def test_complete_task_changes_status(auth_client, user):
    task = TaskFactory(created_by=user)
    url = reverse("tasks:task-complete", kwargs={"pk": task.pk})
    resp = auth_client.post(url)
    assert resp.status_code == status.HTTP_200_OK
    task.refresh_from_db()
    assert task.status == Task.STATUS_COMPLETED


@pytest.mark.django_db
def test_reject_task_requires_reason(auth_client, user):
    task = TaskFactory(created_by=user)
    url = reverse("tasks:task-reject", kwargs={"pk": task.pk})
    # Reject with reason — should succeed
    resp = auth_client.post(url, {"reason": "Not needed"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    task.refresh_from_db()
    assert task.status == Task.STATUS_REJECTED
    assert task.rejection_reason == "Not needed"


@pytest.mark.django_db
def test_reopen_task(auth_client, user):
    task = TaskFactory(created_by=user, status=Task.STATUS_COMPLETED)
    url = reverse("tasks:task-reopen", kwargs={"pk": task.pk})
    resp = auth_client.post(url)
    assert resp.status_code == status.HTTP_200_OK
    task.refresh_from_db()
    assert task.status == Task.STATUS_PENDING


@pytest.mark.django_db
def test_add_remark(auth_client, user):
    task = TaskFactory(created_by=user)
    url = reverse("tasks:task-remarks", kwargs={"pk": task.pk})
    resp = auth_client.post(url, {"text": "Checked and confirmed"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["text"] == "Checked and confirmed"


@pytest.mark.django_db
def test_list_shows_only_relevant_tasks(auth_client, user, other_user):
    # Task by other user not involving me — should NOT appear
    TaskFactory(created_by=other_user, assigned_to=other_user)
    # Task assigned to me — should appear
    mine = TaskFactory(created_by=other_user, assigned_to=user)
    url = reverse("tasks:task-list")
    resp = auth_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    ids = [t["id"] for t in resp.json()]
    assert mine.id in ids
