"""Dashboard C969 link review: row data, error isolation, cache versioning, and invalidation on link changes."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel

CACHE_KEY = "view:dashboard:v2:superuser"


@pytest.fixture(autouse=True)
def clean_dashboard_cache():
    cache.delete(CACHE_KEY)
    yield
    cache.delete(CACHE_KEY)


@pytest.fixture
def client(db):
    user = get_user_model().objects.create_user(
        username="dash-review", email="dash-review@example.com", password="testpass123!", is_superuser=True,
    )
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def wrong_link(db):
    head = HeadSIONNormsModel.objects.create(name="Dashboard review")
    c969 = SionNormClassModel.objects.create(head_norm=head, norm_class="C969")
    battery = ItemNameModel.objects.create(name="AUTOMOTIVE BATTERY", sion_norm_class=c969)
    seat = ItemNameModel.objects.create(name="SEAT ASSEMBLY", sion_norm_class=c969)
    licence = LicenseDetailsModel.objects.create(license_number="DASH-REV-001")
    LicenseExportItemModel.objects.create(license=licence, norm_class=c969, cif_fc=Decimal("100"))
    line = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, description="Automotive Battery-8507", quantity=Decimal("1"),
    )
    line.items.set([seat])
    return {"line": line, "licence": licence, "battery": battery}


def test_dashboard_lists_the_wrong_link_with_its_licence_id(client, wrong_link):
    response = client.get(reverse("license:dashboard"))

    assert response.status_code == 200
    review = response.json()["c969_link_review"]
    assert review["count"] == 1
    assert review["rows"] == [{
        "import_item_id": wrong_link["line"].pk,
        "licence_id": wrong_link["licence"].pk,
        "licence_number": "DASH-REV-001",
        "description": "Automotive Battery-8507",
        "saved_items": ["SEAT ASSEMBLY"],
        "expected_item": "AUTOMOTIVE BATTERY",
    }]


def test_a_review_failure_does_not_break_the_rest_of_the_dashboard(client, wrong_link):
    with patch("apps.license.views.dashboard.c969_link_mismatches", side_effect=RuntimeError("boom")):
        response = client.get(reverse("license:dashboard"))

    assert response.status_code == 200
    body = response.json()
    assert "license_stats" in body
    assert body["c969_link_review"] == {"count": 0, "rows": [], "error": "C969 link review could not run"}


def test_payload_cached_before_the_review_existed_is_not_served(client, wrong_link):
    cache.set("view:dashboard:superuser", {"stale": True}, 60)

    body = client.get(reverse("license:dashboard")).json()

    assert "stale" not in body
    assert body["c969_link_review"]["count"] == 1


def test_changing_a_saved_item_link_clears_the_dashboard_cache(client, wrong_link):
    client.get(reverse("license:dashboard"))
    assert cache.get(CACHE_KEY) is not None

    wrong_link["line"].items.set([wrong_link["battery"]])

    assert cache.get(CACHE_KEY) is None
    body = client.get(reverse("license:dashboard")).json()
    assert body["c969_link_review"]["count"] == 0
