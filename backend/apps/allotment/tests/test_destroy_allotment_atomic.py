"""destroy_allotment is atomic: partial delete failure leaves everything intact."""
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentModel
from apps.core.models import CompanyModel

User = get_user_model()


@pytest.fixture
def client(db):
    user = User.objects.create_user(username="allot-atomic", email="al@example.com", password="pw-Atomic-123")
    user.is_superuser = user.is_staff = True
    user.save()
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


@pytest.fixture
def company(db):
    return CompanyModel.objects.create(name="Atomic Co", iec="IEC777777")


def test_destroy_success_returns_204(client, company):
    a = AllotmentModel.objects.create(company=company)
    r = client.delete(f"/api/allotments/{a.pk}/")
    assert r.status_code == 204
    assert not AllotmentModel.objects.filter(pk=a.pk).exists()


def test_destroy_missing_returns_404(client):
    assert client.delete("/api/allotments/99999999/").status_code == 404


def test_destroy_rolls_back_when_delete_fails_midway(client, company):
    victim = AllotmentModel.objects.create(company=company)
    sibling = AllotmentModel.objects.create(company=company)

    def delete_other_then_fail(self, *a, **k):
        AllotmentModel.objects.filter(pk=sibling.pk).delete()
        raise RuntimeError("boom after first write")

    with mock.patch.object(AllotmentModel, "delete", delete_other_then_fail):
        r = client.delete(f"/api/allotments/{victim.pk}/")
    assert r.status_code == 500
    assert AllotmentModel.objects.filter(pk=victim.pk).exists()
    assert AllotmentModel.objects.filter(pk=sibling.pk).exists()
