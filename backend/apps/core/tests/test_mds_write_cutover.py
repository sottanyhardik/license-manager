"""
Tests for the MASTER WRITE CUTOVER (ADR-001 Phase 6).

Two things are proven here:

1. MDS OFF (default): the viewset create/update/delete paths behave exactly as
   before — a plain local write, no MDS import, no 503.
2. MDS ON: create/update route through ``write_master`` with an id-free payload
   built by the shared helper, then reconcile the local mirror; delete routes
   through ``delete_master`` (MDS first, then local); MDS unreachable surfaces a
   DRF 503 and leaves NO partial local write.

The MDS network hop is faked at ``apps.core.mds_write._client_mods`` so no live
service is needed — the goal is to prove the cutover branching, payload shape,
transaction/rollback, and error translation, which are the risky parts.
"""
from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from django.contrib.auth import get_user_model

from apps.core.models import CompanyModel
from apps.core.views.views import CompanyViewSet

User = get_user_model()
FACTORY = APIRequestFactory()


# --- fakes -----------------------------------------------------------------
class FakeMDSUnavailable(Exception):
    pass


class FakeMDSHTTPError(Exception):
    """Stands in for mds_client.client.MDSHTTPError (reachable but non-2xx)."""

    def __init__(self, status_code, body, url="https://mds.test/x"):
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(f"MDS returned HTTP {status_code}: {body!r}")


class WriteRecorder:
    """Stands in for mds_client.sync.{write_master,delete_master,refresh_local}.

    ``down`` -> raise MDSUnavailable (service unreachable).
    ``reject`` -> a (status_code, body) tuple; raise MDSHTTPError (MDS reachable
    but rejected the write/delete, e.g. a 400 validation error)."""

    def __init__(self, *, down=False, reject=None):
        self.down = down
        self.reject = reject
        self.writes = []
        self.deletes = []
        self.refreshed = []

    def _maybe_fail(self):
        if self.down:
            raise FakeMDSUnavailable("down")
        if self.reject is not None:
            raise FakeMDSHTTPError(*self.reject)

    def write_master(self, label, row):
        self._maybe_fail()
        self.writes.append((label, row))
        return {"created": 1, "updated": 0}

    def delete_master(self, label, key):
        self._maybe_fail()
        self.deletes.append((label, key))
        return {"deleted": 1, "local_deleted": 1}

    def refresh_local(self, label):
        self.refreshed.append(label)


@pytest.fixture
def enable_mds(settings):
    """Turn the cutover on for this test, wiring the 17-master map."""
    from mds_client.model_map import DEFAULT_MDS_MODELS

    settings.MDS_ENABLED = True
    settings.MDS_MODELS = DEFAULT_MDS_MODELS
    settings.MDS_BASE_URL = "https://masters.test.local/api/v1/"
    settings.MDS_TOKEN = "test-token"
    return settings


@pytest.fixture
def patch_client(monkeypatch):
    """Install a WriteRecorder in place of the real mds_client helpers + map the
    fake MDSUnavailable into what mds_write catches."""

    def _install(recorder):
        monkeypatch.setattr(
            "apps.core.mds_write._client_mods",
            lambda: (
                FakeMDSUnavailable,
                FakeMDSHTTPError,
                recorder.write_master,
                recorder.delete_master,
                recorder.refresh_local,
            ),
        )
        return recorder

    return _install


@pytest.fixture
def user(db):
    return User.objects.create_user(username="u1", password="x")


# --- MDS OFF (default) ------------------------------------------------------
@pytest.mark.django_db
class TestMdsOffUnchanged:
    def test_create_is_plain_local_write(self, user, monkeypatch):
        # If the cutover were entered it would call _client_mods; make that blow
        # up so the test fails loudly if MDS-off ever routes through MDS.
        monkeypatch.setattr(
            "apps.core.mds_write._client_mods",
            lambda: (_ for _ in ()).throw(AssertionError("MDS path hit while disabled")),
        )
        request = FACTORY.post("/companies/", {"iec": "IEC0000001", "name": "Acme"})
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"post": "create"})
        resp = view(request)
        assert resp.status_code == 201
        c = CompanyModel.objects.get(iec="IEC0000001")
        assert c.name == "Acme"
        assert c.created_by_id == user.id  # audit behavior preserved

    def test_delete_is_plain_local_delete(self, user):
        c = CompanyModel.objects.create(iec="IEC0000002", name="Beta")
        request = FACTORY.delete("/companies/")
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"delete": "destroy"})
        resp = view(request, pk=c.pk)
        assert resp.status_code == 204
        assert not CompanyModel.objects.filter(pk=c.pk).exists()


# --- MDS ON -----------------------------------------------------------------
@pytest.mark.django_db
class TestMdsOnCreate:
    def test_create_writes_idfree_payload_and_refreshes(self, user, enable_mds, patch_client):
        rec = patch_client(WriteRecorder())
        request = FACTORY.post("/companies/", {"iec": "IEC1000001", "name": "Acme", "bill_colour": "#333"})
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"post": "create"})
        resp = view(request)

        assert resp.status_code == 201
        # reached MDS exactly once with the right label + an id-free row.
        assert len(rec.writes) == 1
        label, row = rec.writes[0]
        assert label == "core.CompanyModel"
        assert row["iec"] == "IEC1000001"
        assert row["name"] == "Acme"
        assert "id" not in row and "created_by" not in row and "created_on" not in row
        # local mirror reconciled from MDS.
        assert rec.refreshed == ["core.CompanyModel"]
        # local row exists (authoritative copy will be reconciled by refresh).
        assert CompanyModel.objects.filter(iec="IEC1000001").exists()

    def test_create_503_and_no_partial_write_when_mds_down(self, user, enable_mds, patch_client):
        rec = patch_client(WriteRecorder(down=True))
        request = FACTORY.post("/companies/", {"iec": "IEC2000002", "name": "GhostCo"})
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"post": "create"})
        resp = view(request)

        assert resp.status_code == 503
        assert "unreachable" in str(resp.data).lower()
        # local write MUST have been rolled back (no partial write).
        assert not CompanyModel.objects.filter(iec="IEC2000002").exists()


@pytest.mark.django_db
class TestMdsOnUpdate:
    def test_update_routes_to_mds(self, user, enable_mds, patch_client):
        rec = patch_client(WriteRecorder())
        c = CompanyModel.objects.create(iec="IEC3000003", name="Old")
        request = FACTORY.patch("/companies/", {"name": "New"})
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"patch": "partial_update"})
        resp = view(request, pk=c.pk)

        assert resp.status_code == 200
        assert len(rec.writes) == 1
        label, row = rec.writes[0]
        assert label == "core.CompanyModel"
        assert row["name"] == "New"
        assert rec.refreshed == ["core.CompanyModel"]


@pytest.mark.django_db
class TestMdsOnDelete:
    def test_delete_routes_to_mds_then_local(self, user, enable_mds, patch_client):
        rec = patch_client(WriteRecorder())
        c = CompanyModel.objects.create(iec="IEC4000004", name="ToGo")
        request = FACTORY.delete("/companies/")
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"delete": "destroy"})
        resp = view(request, pk=c.pk)

        assert resp.status_code == 204
        assert rec.deletes == [("core.CompanyModel", "IEC4000004")]

    def test_delete_503_leaves_local_row_intact_when_mds_down(self, user, enable_mds, patch_client):
        rec = patch_client(WriteRecorder(down=True))
        c = CompanyModel.objects.create(iec="IEC5000005", name="Stay")
        request = FACTORY.delete("/companies/")
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"delete": "destroy"})
        resp = view(request, pk=c.pk)

        assert resp.status_code == 503
        # MDS never confirmed -> local row must survive (no half-delete).
        assert CompanyModel.objects.filter(pk=c.pk).exists()


@pytest.mark.django_db
class TestMdsRejectsWrite:
    """MDS reachable but returns a non-2xx (validation / conflict). This must NOT
    crash as a 500: a 4xx surfaces MDS's real message as a 400 (local change
    rolled back), a 5xx degrades to the 503 service-unavailable contract."""

    def test_create_4xx_surfaces_message_as_validation_error(self, user, enable_mds, patch_client):
        patch_client(WriteRecorder(reject=(400, {"display_order": ["must be unique per norm class"]})))
        request = FACTORY.post("/companies/", {"iec": "IEC6000006", "name": "Rejected"})
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"post": "create"})
        resp = view(request)

        assert resp.status_code == 400
        assert "unique per norm class" in str(resp.data)
        # local write rolled back — no partial write.
        assert not CompanyModel.objects.filter(iec="IEC6000006").exists()

    def test_create_5xx_degrades_to_503(self, user, enable_mds, patch_client):
        patch_client(WriteRecorder(reject=(500, "boom")))
        request = FACTORY.post("/companies/", {"iec": "IEC7000007", "name": "Boom"})
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"post": "create"})
        resp = view(request)

        assert resp.status_code == 503
        assert not CompanyModel.objects.filter(iec="IEC7000007").exists()

    def test_delete_4xx_surfaces_message_and_keeps_local_row(self, user, enable_mds, patch_client):
        patch_client(WriteRecorder(reject=(409, {"detail": "row is referenced"})))
        c = CompanyModel.objects.create(iec="IEC8000008", name="Ref")
        request = FACTORY.delete("/companies/")
        force_authenticate(request, user=user)
        view = CompanyViewSet.as_view({"delete": "destroy"})
        resp = view(request, pk=c.pk)

        assert resp.status_code == 400
        assert "referenced" in str(resp.data)
        # MDS never confirmed the delete -> local row must survive.
        assert CompanyModel.objects.filter(pk=c.pk).exists()


@pytest.mark.django_db
class TestKeylessRoundTripPayload:
    """A keyless master (UnitPrice) must write its deterministic uid as the
    natural key so MDS keys on it and the row converges across servers."""

    def test_unit_price_payload_carries_uid(self, user, enable_mds, patch_client):
        from apps.core.models import UnitPriceModel
        from apps.core.views.views import UnitPriceViewSet

        rec = patch_client(WriteRecorder())
        request = FACTORY.post("/unit-prices/", {"name": "SKU1", "unit_price": "9.99", "label": "per kg"})
        force_authenticate(request, user=user)
        view = UnitPriceViewSet.as_view({"post": "create"})
        resp = view(request)

        assert resp.status_code == 201
        assert len(rec.writes) == 1
        label, row = rec.writes[0]
        assert label == "core.UnitPriceModel"
        # uid present, a valid uuid, and equal to the row's computed uid.
        assert "uid" in row and row["uid"]
        uuid.UUID(str(row["uid"]))
        obj = UnitPriceModel.objects.get(name="SKU1")
        assert str(row["uid"]) == str(obj.uid)
