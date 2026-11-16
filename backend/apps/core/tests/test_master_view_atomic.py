"""MasterViewSet writes are atomic: a failure after the first write rolls back."""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import PortModel
from apps.core.views.master_view import MasterViewSet

User = get_user_model()


class _WriteThenFail:
    """Fake serializer: performs one real write, then raises."""

    def __init__(self, fail=True):
        self.fail = fail
        self.Meta = SimpleNamespace(model=PortModel)
        self.instance = None

    def save(self, **kwargs):
        self.instance = PortModel.objects.create(name="Atomic Port", code="ATM001")
        if self.fail:
            raise RuntimeError("boom after first write")
        return self.instance


def _viewset():
    vs = MasterViewSet()
    vs.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    return vs


@pytest.mark.django_db
def test_perform_create_rolls_back_on_later_failure():
    with pytest.raises(RuntimeError):
        _viewset().perform_create(_WriteThenFail())
    assert not PortModel.objects.filter(code="ATM001").exists()


@pytest.mark.django_db
def test_perform_update_rolls_back_on_later_failure():
    with pytest.raises(RuntimeError):
        _viewset().perform_update(_WriteThenFail())
    assert not PortModel.objects.filter(code="ATM001").exists()


@pytest.mark.django_db
def test_perform_destroy_rolls_back_on_later_failure():
    port = PortModel.objects.create(name="Victim", code="ATM002")
    other = PortModel.objects.create(name="Sibling", code="ATM003")
    real_delete = port.delete

    def delete_then_fail(*a, **k):
        other.delete()
        raise RuntimeError("boom after first delete")

    port.delete = delete_then_fail
    with pytest.raises(RuntimeError):
        _viewset().perform_destroy(port)
    port.delete = real_delete
    assert PortModel.objects.filter(code="ATM003").exists()
    assert PortModel.objects.filter(code="ATM002").exists()


@pytest.mark.django_db
def test_success_path_create_update_delete_via_api_unchanged():
    user = User.objects.create_user(username="atomic-su", email="a@example.com", password="pw-Atomic-123")
    user.is_superuser = user.is_staff = True
    user.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")

    r = client.post("/api/masters/ports/", {"name": "Okay Port", "code": "ATM010"}, format="json")
    assert r.status_code == 201, r.data
    assert r.data["code"] == "ATM010"
    pk = r.data["id"]
    r = client.patch(f"/api/masters/ports/{pk}/", {"name": "Okay Port 2"}, format="json")
    assert r.status_code == 200 and r.data["name"] == "Okay Port 2"
    assert client.delete(f"/api/masters/ports/{pk}/").status_code == 204
    assert not PortModel.objects.filter(pk=pk).exists()
