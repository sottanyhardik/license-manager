"""The master serializers must express inter-master FKs as the parent's NATURAL
KEY (not the raw integer id), because ids diverge across servers (ADR-001
Decision 2). This is what lets a consumer mirror resolve FKs locally without a
duplicate. These tests lock that contract in on read AND write."""

import pytest
from rest_framework.test import APIClient

from masters.models import HeadSIONNorm, SIONExport, SIONNormClass

WRITE = "t-write"


@pytest.fixture(autouse=True)
def _tokens(settings):
    settings.MDS_SERVICE_TOKENS = {WRITE: "write"}


@pytest.fixture
def api():
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {WRITE}")
    return c


@pytest.fixture
def norm(db):
    head = HeadSIONNorm.objects.create(name="Textiles")
    return SIONNormClass.objects.create(head_norm=head, norm_class="E1", is_active=True)


@pytest.mark.django_db
def test_fk_serialized_as_parent_natural_key(api, norm):
    exp = SIONExport.objects.create(norm_class=norm, description="cloth")
    r = api.get(f"/api/v1/sion-exports/?updated_since=1970-01-01T00:00:00Z")
    assert r.status_code == 200
    row = next(x for x in r.data["results"] if x["uid"] == str(exp.uid))
    # norm_class rendered as the natural key "E1", not the integer id.
    assert row["norm_class"] == "E1"


@pytest.mark.django_db
def test_bulk_upsert_resolves_fk_by_natural_key(api, norm):
    r = api.post(
        "/api/v1/sion-exports/bulk_upsert/",
        [{"uid": "11111111-1111-5111-8111-111111111111", "norm_class": "E1", "description": "yarn"}],
        format="json",
    )
    assert r.status_code == 200, r.data
    assert r.data == {"created": 1, "updated": 0}
    exp = SIONExport.objects.get(uid="11111111-1111-5111-8111-111111111111")
    assert exp.norm_class_id == norm.id  # linked to the right local parent
