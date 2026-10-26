"""Import-line item suggestion uses the C969 product-name rules, as the save path does."""
import pytest
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from django.contrib.auth import get_user_model

URL = "/api/import-item-suggestion/"


@pytest.fixture
def client():
    user = get_user_model().objects.create_user(username="suggest-user", password="x")
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def norms():
    head = HeadSIONNormsModel.objects.create(name="Suggest")
    return {c: SionNormClassModel.objects.create(head_norm=head, norm_class=c) for c in ("C969", "E5")}


@pytest.fixture
def items(norms):
    return {
        "FRONT WHEELRIM": ItemNameModel.objects.create(name="FRONT WHEELRIM", sion_norm_class=norms["C969"]),
        "'O' Ring": ItemNameModel.objects.create(name="'O' Ring", sion_norm_class=norms["C969"]),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("description, name", [("Front Wheel Rim", "FRONT WHEELRIM"), ("'O' Ring", "'O' Ring")])
def test_c969_description_suggests_its_item(client, norms, items, description, name):
    response = client.post(URL, {"description": description, "norm_class_ids": [norms["C969"].pk]}, format="json")
    assert response.status_code == 200
    assert response.json() == {"items": [{"id": items[name].pk, "name": name}]}


@pytest.mark.django_db
@pytest.mark.parametrize("description", ["(DELETED)", "", "20", "Gear housing part"])
def test_blank_deleted_or_unknown_gets_no_item(client, norms, items, description):
    response = client.post(URL, {"description": description, "norm_class_ids": [norms["C969"].pk]}, format="json")
    assert response.json() == {"items": []}


@pytest.mark.django_db
def test_other_norms_get_no_suggestion(client, norms, items):
    response = client.post(URL, {"description": "Front Wheel Rim", "norm_class_ids": [norms["E5"].pk]}, format="json")
    assert response.json() == {"items": []}


@pytest.mark.django_db
def test_requires_login(norms):
    response = APIClient().post(URL, {"description": "Front Wheel Rim", "norm_class_ids": [norms["C969"].pk]}, format="json")
    assert response.status_code in (401, 403)
