"""Contract tests for the MDS master API — the behaviors consumers rely on."""

import pytest
from rest_framework.test import APIClient

from masters.models import Company, MasterChange

WRITE = "t-write"
READ = "t-read"


@pytest.fixture(autouse=True)
def _tokens(settings):
    settings.MDS_SERVICE_TOKENS = {WRITE: "write", READ: "read"}


@pytest.fixture
def api():
    return APIClient()


def _auth(client, token=WRITE):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
class TestAuth:
    def test_no_token_is_denied(self, api):
        assert api.get("/api/v1/companies/").status_code in (401, 403)

    def test_invalid_token_is_denied(self, api):
        _auth(api, "nope")
        assert api.get("/api/v1/companies/").status_code in (401, 403)

    def test_read_token_cannot_write(self, api):
        _auth(api, READ)
        r = api.post("/api/v1/companies/bulk_upsert/", [{"iec": "IEC1", "name": "A"}], format="json")
        assert r.status_code == 403

    def test_read_token_can_read(self, api):
        _auth(api, READ)
        assert api.get("/api/v1/companies/").status_code == 200


@pytest.mark.django_db
class TestBulkUpsert:
    def test_creates_then_updates_by_natural_key(self, api):
        _auth(api)
        r = api.post(
            "/api/v1/companies/bulk_upsert/",
            [{"iec": "IEC1", "name": "Acme"}, {"iec": "IEC2", "name": "Beta"}],
            format="json",
        )
        assert r.status_code == 200
        assert r.data == {"created": 2, "updated": 0}
        assert Company.objects.count() == 2

        # same natural key -> update, not duplicate
        r = api.post(
            "/api/v1/companies/bulk_upsert/",
            [{"iec": "IEC1", "name": "Acme Renamed"}],
            format="json",
        )
        assert r.data == {"created": 0, "updated": 1}
        assert Company.objects.count() == 2
        assert Company.objects.get(iec="IEC1").name == "Acme Renamed"

    def test_missing_natural_key_is_rejected(self, api):
        _auth(api)
        r = api.post("/api/v1/companies/bulk_upsert/", [{"name": "NoIEC"}], format="json")
        assert r.status_code == 400


@pytest.mark.django_db
class TestDeleteByKey:
    def test_deletes_row_and_records_delete_change(self, api):
        _auth(api)
        Company.objects.create(iec="IEC1", name="Acme")
        r = api.post("/api/v1/companies/delete_by_key/", {"iec": "IEC1"}, format="json")
        assert r.status_code == 200
        assert r.data == {"deleted": 1}
        assert not Company.objects.filter(iec="IEC1").exists()
        # the change feed carries the delete so it propagates to mirrors.
        assert MasterChange.objects.filter(
            natural_key="IEC1", op=MasterChange.OP_DELETE
        ).exists()

    def test_accepts_generic_key_field(self, api):
        _auth(api)
        Company.objects.create(iec="IEC9", name="Zed")
        r = api.post("/api/v1/companies/delete_by_key/", {"key": "IEC9"}, format="json")
        assert r.status_code == 200
        assert r.data == {"deleted": 1}

    def test_absent_key_is_idempotent_success(self, api):
        _auth(api)
        r = api.post("/api/v1/companies/delete_by_key/", {"iec": "GHOST"}, format="json")
        assert r.status_code == 200
        assert r.data == {"deleted": 0}

    def test_missing_key_is_rejected(self, api):
        _auth(api)
        r = api.post("/api/v1/companies/delete_by_key/", {}, format="json")
        assert r.status_code == 400

    def test_read_token_cannot_delete(self, api):
        _auth(api, READ)
        Company.objects.create(iec="IEC1", name="Acme")
        r = api.post("/api/v1/companies/delete_by_key/", {"iec": "IEC1"}, format="json")
        assert r.status_code == 403
        assert Company.objects.filter(iec="IEC1").exists()


@pytest.mark.django_db
class TestDeltaAndEtag:
    def test_updated_since_filters(self, api):
        _auth(api)
        Company.objects.create(iec="OLD", name="Old")
        api.post("/api/v1/companies/bulk_upsert/", [{"iec": "NEW", "name": "New"}], format="json")
        # a cursor in the far past returns everything
        r = api.get("/api/v1/companies/?updated_since=2000-01-01T00:00:00Z")
        assert r.status_code == 200
        iecs = {row["iec"] for row in r.data["results"]}
        assert {"OLD", "NEW"} <= iecs
        # a cursor in the far future returns nothing
        r = api.get("/api/v1/companies/?updated_since=2999-01-01T00:00:00Z")
        assert r.data["results"] == []

    def test_etag_returns_304(self, api):
        _auth(api)
        Company.objects.create(iec="IEC1", name="Acme")
        first = api.get("/api/v1/companies/")
        etag = first["ETag"]
        assert etag
        second = api.get("/api/v1/companies/", HTTP_IF_NONE_MATCH=etag)
        assert second.status_code == 304

    def test_meta_reports_count(self, api):
        _auth(api)
        Company.objects.create(iec="IEC1", name="Acme")
        r = api.get("/api/v1/companies/_meta/")
        assert r.status_code == 200
        assert r.data["count"] == 1
        assert r.data["etag"]


@pytest.mark.django_db
class TestChangeFeed:
    def test_records_create_update_delete(self, api):
        _auth(api)
        c = Company.objects.create(iec="IEC1", name="Acme")  # create
        c.name = "Acme 2"
        c.save()  # update
        c.delete()  # delete

        ops = list(MasterChange.objects.filter(natural_key="IEC1").values_list("op", flat=True))
        assert ops == ["create", "update", "delete"]

    def test_feed_since_filter(self, api):
        _auth(api)
        Company.objects.create(iec="IEC1", name="Acme")
        r = api.get("/api/v1/changes/?since=2000-01-01T00:00:00Z")
        assert r.status_code == 200
        assert any(row["natural_key"] == "IEC1" for row in r.data["results"])
