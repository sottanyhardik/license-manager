"""
Module 04 — Sync **API surface** tests (views.py + serializers.py + urls.py).

The pre-existing Module 04 suites call ``apps.core.sync.service`` directly, so
none of the six HTTP endpoints, none of the serializers and none of the URL
wiring was exercised.  These tests drive the real DRF stack end-to-end with
``APIClient``:

    POST /api/sync/push/            single event, batch, conflict logging, peer touch
    GET  /api/sync/pull/            change feed, ``since`` cursor, model filter
    POST /api/sync/delete-check/    safe delete vs 409 CONFLICT
    GET  /api/sync/status/          health counters
    GET  /api/sync/media/download/  file streaming + path-traversal defence
    GET  /api/sync/conflicts/       conflict log + ``since``/``limit``

Every endpoint is also asserted to be closed to anonymous callers.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, ItemGroupModel, ItemNameModel, MasterChange, PortModel
from apps.core.sync.models import MediaSyncTask, SyncConflictLog, SyncCursor, SyncPeer
from apps.core.tests.sync_factories import (  # noqa: F401  (fixtures imported by name)
    api,
    auth_client,
    company_event,
    locmem_cache,
    make_cursor,
    make_peer,
    make_user,
    media_root,
    port_event,
    push_payload,
    sha256_of,
    sync_event,
    write_media,
)

pytestmark = pytest.mark.django_db


PUSH = "sync:sync-push"
PULL = "sync:sync-pull"
DELETE_CHECK = "sync:sync-delete-check"
STATUS = "sync:sync-status"
MEDIA_DOWNLOAD = "sync:sync-media-download"
CONFLICTS = "sync:sync-conflicts"

ALL_ENDPOINTS = [PUSH, PULL, DELETE_CHECK, STATUS, MEDIA_DOWNLOAD, CONFLICTS]


# ── URL wiring ──────────────────────────────────────────────────────────

class TestUrlWiring:
    """urls.py — every view is reachable at its documented path."""

    @pytest.mark.parametrize("name,path", [
        (PUSH, "/api/sync/push/"),
        (PULL, "/api/sync/pull/"),
        (DELETE_CHECK, "/api/sync/delete-check/"),
        (STATUS, "/api/sync/status/"),
        (MEDIA_DOWNLOAD, "/api/sync/media/download/"),
        (CONFLICTS, "/api/sync/conflicts/"),
    ])
    def test_reverse_matches_documented_path(self, name, path):
        assert reverse(name) == path


# ── authentication ──────────────────────────────────────────────────────

class TestAuthenticationRequired:
    """Sync endpoints replicate master data — none may be anonymous."""

    @pytest.mark.parametrize("name", ALL_ENDPOINTS)
    def test_get_is_rejected_for_anonymous(self, name, locmem_cache):
        response = APIClient().get(reverse(name))
        assert response.status_code in (401, 403), (
            f"{name} answered anonymous GET with {response.status_code}"
        )

    @pytest.mark.parametrize("name", [PUSH, DELETE_CHECK])
    def test_post_is_rejected_for_anonymous(self, name, locmem_cache):
        response = APIClient().post(reverse(name), {}, format="json")
        assert response.status_code in (401, 403)

    def test_anonymous_push_writes_nothing(self, locmem_cache):
        """A rejected push must not reach the sync service."""
        payload = push_payload(port_event("ANON01", "Anon Port"))
        response = APIClient().post(reverse(PUSH), payload, format="json")

        assert response.status_code in (401, 403)
        assert not PortModel.objects.filter(code="ANON01").exists()
        assert MasterChange.objects.count() == 0

    def test_anonymous_media_download_cannot_read_files(self, locmem_cache, media_root):
        rel = write_media(media_root, "companies/1/logo.png", b"secret-bytes")
        response = APIClient().get(reverse(MEDIA_DOWNLOAD), {"path": rel})
        assert response.status_code in (401, 403)


# ── POST /api/sync/push/ ────────────────────────────────────────────────

class TestPushEndpoint:
    def test_single_event_is_applied(self, api):
        response = api.post(
            reverse(PUSH), push_payload(port_event("API001", "Api Port")), format="json",
        )

        assert response.status_code == 200
        body = response.data
        assert body["ok"] is True
        assert body["total"] == 1
        assert len(body["applied"]) == 1
        assert body["applied"][0]["op"] == "create"
        assert body["applied"][0]["natural_key"] == "API001"
        assert body["applied"][0]["model_label"] == "core.PortModel"
        assert body["skipped"] == []
        assert body["errors"] == []

        port = PortModel.objects.get(code="API001")
        assert port.name == "Api Port"
        assert port.origin_server == "server-A"
        assert port.sync_version == 1

    def test_batch_applies_every_event(self, api):
        events = [
            port_event("API002", "Port Two"),
            company_event("APICO00002", "Company Two"),
            port_event("API003", "Port Three"),
        ]
        response = api.post(reverse(PUSH), push_payload(events), format="json")

        assert response.status_code == 200
        assert response.data["ok"] is True
        assert response.data["total"] == 3
        assert len(response.data["applied"]) == 3
        assert PortModel.objects.filter(code__in=["API002", "API003"]).count() == 2
        assert CompanyModel.objects.filter(iec="APICO00002").exists()

    def test_batch_is_applied_in_registry_order(self, api):
        """Children may only be created after their parents exist."""
        events = [
            sync_event("core.ItemNameModel", "create", {"name": "OrderedItem"}),
            sync_event("core.ItemGroupModel", "create", {"name": "OrderedGroup"}),
        ]
        response = api.post(reverse(PUSH), push_payload(events), format="json")

        assert response.status_code == 200
        applied = [r["model_label"] for r in response.data["applied"]]
        assert applied.index("core.ItemGroupModel") < applied.index("core.ItemNameModel")

    def test_top_level_source_server_overrides_per_event_value(self, api):
        """views.py rewrites each event's source_server from the envelope."""
        event = port_event("API004", "Overridden", server="lying-server")
        response = api.post(
            reverse(PUSH), push_payload(event, source_server="truthful-server"), format="json",
        )

        assert response.status_code == 200
        assert PortModel.objects.get(code="API004").origin_server == "truthful-server"

    def test_push_emits_change_feed_rows(self, api):
        api.post(reverse(PUSH), push_payload(port_event("API005", "Feed")), format="json")

        change = MasterChange.objects.get(model_label="core.PortModel", natural_key="API005")
        assert change.op == MasterChange.OP_CREATE

    def test_push_touches_peer_last_seen(self, api):
        peer = make_peer("server-A", base_url="http://a.example.test")
        assert peer.last_seen is None

        before = timezone.now()
        api.post(
            reverse(PUSH),
            push_payload(port_event("API006", "Seen"), source_server="server-A"),
            format="json",
        )

        peer.refresh_from_db()
        assert peer.last_seen is not None
        assert peer.last_seen >= before

    def test_push_of_unknown_peer_does_not_create_a_peer(self, api):
        api.post(
            reverse(PUSH),
            push_payload(port_event("API007", "Ghost"), source_server="never-registered"),
            format="json",
        )
        assert not SyncPeer.objects.filter(server_id="never-registered").exists()

    def test_stale_event_is_skipped_and_logged_as_conflict(self, api):
        PortModel.objects.create(
            code="API008", name="Local Wins", sync_version=9, origin_server="server-Z",
        )

        response = api.post(
            reverse(PUSH),
            push_payload(port_event("API008", "Stale Loser", server="server-A", version=2)),
            format="json",
        )

        assert response.status_code == 200
        assert response.data["ok"] is True          # skipped, not an error
        assert len(response.data["skipped"]) == 1
        assert response.data["skipped"][0]["conflict"] is True
        assert PortModel.objects.get(code="API008").name == "Local Wins"

        log = SyncConflictLog.objects.get(model_label="core.PortModel", natural_key="API008")
        assert log.source_server == "server-A"
        assert log.op == "noop"
        assert "Local version 9" in log.detail

    def test_blocked_delete_is_reported_and_logged(self, api):
        group = ItemGroupModel.objects.create(name="ApiGroup", sync_version=1)
        ItemNameModel.objects.create(name="ApiItem", group=group, sync_version=1)

        response = api.post(
            reverse(PUSH),
            push_payload(sync_event(
                "core.ItemGroupModel", "delete", {"name": "ApiGroup"}, version=2,
            )),
            format="json",
        )

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert len(response.data["errors"]) == 1
        assert response.data["errors"][0]["conflict"] is True
        assert "409 CONFLICT" in response.data["errors"][0]["conflict_detail"]

        group.refresh_from_db()
        assert group.is_tombstone is False           # delete really was refused

        log = SyncConflictLog.objects.get(model_label="core.ItemGroupModel", natural_key="ApiGroup")
        assert "409 CONFLICT" in log.detail

    def test_response_matches_serializer_contract(self, api):
        response = api.post(
            reverse(PUSH), push_payload(port_event("API009", "Shape")), format="json",
        )
        assert set(response.data) == {"applied", "skipped", "errors", "total", "ok"}
        assert set(response.data["applied"][0]) == {
            "model_label", "natural_key", "op", "success", "conflict",
            "conflict_detail", "error",
        }

    def test_media_metadata_creates_a_media_task(self, api):
        response = api.post(
            reverse(PUSH),
            push_payload(company_event(
                "APIMED0001", "With Logo",
                media={"logo": {"path": "companies/9/logo.png", "sha256": "a" * 64},
                       "signature": None},
            )),
            format="json",
        )

        assert response.status_code == 200
        tasks = MediaSyncTask.objects.filter(model_label="core.CompanyModel")
        assert tasks.count() == 1                    # signature=None is skipped
        task = tasks.get()
        assert task.field_name == "logo"
        assert task.natural_key == "APIMED0001"
        assert task.source_path == "companies/9/logo.png"
        assert task.expected_sha256 == "a" * 64
        assert task.source_server == "server-A"
        assert task.status == MediaSyncTask.STATUS_PENDING

    def test_media_metadata_ignored_for_non_media_master(self, api):
        api.post(
            reverse(PUSH),
            push_payload(sync_event(
                "core.PortModel", "create", {"code": "API010", "name": "No Media"},
                media={"logo": {"path": "x.png", "sha256": "b" * 64}},
            )),
            format="json",
        )
        assert MediaSyncTask.objects.count() == 0

    def test_media_key_is_not_persisted_as_a_field(self, api):
        """``media`` is transport metadata — it must never reach the model."""
        response = api.post(
            reverse(PUSH),
            push_payload(company_event(
                "APIMED0002", "Meta Only",
                media={"logo": {"path": "companies/9/l.png", "sha256": "c" * 64}},
            )),
            format="json",
        )
        assert response.data["ok"] is True
        assert CompanyModel.objects.get(iec="APIMED0002").name == "Meta Only"


# ── GET /api/sync/pull/ ─────────────────────────────────────────────────

class TestPullEndpoint:
    def _seed(self, code, *, minutes_ago):
        PortModel.objects.create(code=code, name=f"Port {code}", sync_version=1)
        return MasterChange.objects.create(
            model_label="core.PortModel", natural_key=code, op=MasterChange.OP_CREATE,
            at=timezone.now() - timedelta(minutes=minutes_ago),
        )

    def test_returns_change_feed(self, api):
        self._seed("PUL001", minutes_ago=10)
        response = api.get(reverse(PULL))

        assert response.status_code == 200
        assert response.data["count"] == len(response.data["events"])
        codes = [e["data"].get("code") for e in response.data["events"]]
        assert "PUL001" in codes

    def test_event_shape_is_consumable_by_push(self, api):
        self._seed("PUL002", minutes_ago=10)
        event = [e for e in api.get(reverse(PULL)).data["events"]
                 if e["data"].get("code") == "PUL002"][0]

        assert {"model_label", "op", "data", "source_server", "source_version", "at"} <= set(event)
        assert event["model_label"] == "core.PortModel"
        assert event["op"] == "create"

    def test_server_id_is_reported(self, api, settings):
        from apps.core.sync.mixins import SERVER_ID
        assert api.get(reverse(PULL)).data["server_id"] == SERVER_ID

    def test_since_cursor_excludes_older_changes(self, api):
        self._seed("PUL003", minutes_ago=120)
        self._seed("PUL004", minutes_ago=1)

        cutoff = (timezone.now() - timedelta(minutes=60)).isoformat()
        response = api.get(reverse(PULL), {"since": cutoff})

        codes = [e["data"].get("code") for e in response.data["events"]]
        assert "PUL004" in codes
        assert "PUL003" not in codes

    def test_future_since_returns_nothing(self, api):
        self._seed("PUL005", minutes_ago=5)
        future = (timezone.now() + timedelta(hours=1)).isoformat()

        response = api.get(reverse(PULL), {"since": future})
        assert response.data["count"] == 0
        assert response.data["events"] == []

    def test_unparseable_since_is_ignored_not_fatal(self, api):
        """A bad cursor degrades to a full feed rather than a 500."""
        self._seed("PUL006", minutes_ago=5)
        response = api.get(reverse(PULL), {"since": "not-a-timestamp"})

        assert response.status_code == 200
        codes = [e["data"].get("code") for e in response.data["events"]]
        assert "PUL006" in codes

    def test_model_label_filter(self, api):
        self._seed("PUL007", minutes_ago=5)
        CompanyModel.objects.create(iec="PULCO00001", name="Pull Co")
        MasterChange.objects.create(
            model_label="core.CompanyModel", natural_key="PULCO00001",
            op=MasterChange.OP_CREATE,
        )

        response = api.get(reverse(PULL), {"model_label": "core.CompanyModel"})
        labels = {e["model_label"] for e in response.data["events"]}
        assert labels == {"core.CompanyModel"}

    def test_multiple_model_label_filters(self, api):
        self._seed("PUL008", minutes_ago=5)
        CompanyModel.objects.create(iec="PULCO00002", name="Pull Co 2")
        MasterChange.objects.create(
            model_label="core.CompanyModel", natural_key="PULCO00002",
            op=MasterChange.OP_CREATE,
        )
        ItemGroupModel.objects.create(name="PullGroup", sync_version=1)
        MasterChange.objects.create(
            model_label="core.ItemGroupModel", natural_key="PullGroup",
            op=MasterChange.OP_CREATE,
        )

        response = api.get(
            reverse(PULL) + "?model_label=core.PortModel&model_label=core.CompanyModel",
        )
        labels = {e["model_label"] for e in response.data["events"]}
        assert labels == {"core.PortModel", "core.CompanyModel"}

    def test_delete_events_carry_only_the_natural_key(self, api):
        PortModel.objects.create(code="PUL009", name="Gone", sync_version=1, is_tombstone=True)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="PUL009", op=MasterChange.OP_DELETE,
        )

        event = [e for e in api.get(reverse(PULL)).data["events"]
                 if e["op"] == "delete" and e["data"].get("code") == "PUL009"][0]
        assert event["data"] == {"code": "PUL009"}

    def test_pull_response_is_unpaginated(self, api):
        """Documents current behaviour: the whole delta ships in one response."""
        for i in range(12):
            self._seed(f"PGN{i:03d}", minutes_ago=5)

        response = api.get(reverse(PULL))
        assert set(response.data) == {"server_id", "events", "count"}
        assert response.data["count"] >= 12
        assert len(response.data["events"]) == response.data["count"]


# ── POST /api/sync/delete-check/ ────────────────────────────────────────

class TestDeleteCheckEndpoint:
    def test_unreferenced_record_is_safe(self, api):
        PortModel.objects.create(code="DCK001", name="Free", sync_version=1)

        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.PortModel", "natural_key": {"code": "DCK001"}},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["safe"] is True
        assert response.data["references"] == []
        assert response.data["natural_key"] == "DCK001"
        assert response.data["model_label"] == "core.PortModel"

    def test_missing_record_is_safe(self, api):
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.PortModel", "natural_key": {"code": "NOPE01"}},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["safe"] is True

    def test_referenced_record_returns_409_with_references(self, api):
        group = ItemGroupModel.objects.create(name="DckGroup", sync_version=1)
        ItemNameModel.objects.create(name="DckItem", group=group, sync_version=1)

        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.ItemGroupModel", "natural_key": {"name": "DckGroup"}},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["safe"] is False
        assert len(response.data["references"]) >= 1
        assert any("ItemNameModel" in ref for ref in response.data["references"])
        assert any("1 record(s)" in ref for ref in response.data["references"])

    def test_delete_check_never_mutates(self, api):
        group = ItemGroupModel.objects.create(name="DckReadOnly", sync_version=1)
        ItemNameModel.objects.create(name="DckChild", group=group, sync_version=1)

        api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.ItemGroupModel", "natural_key": {"name": "DckReadOnly"}},
            format="json",
        )

        group.refresh_from_db()
        assert group.is_tombstone is False
        assert ItemNameModel.objects.filter(name="DckChild").exists()
        assert MasterChange.objects.count() == 0

    def test_becomes_safe_once_children_are_gone(self, api):
        group = ItemGroupModel.objects.create(name="DckFreed", sync_version=1)
        child = ItemNameModel.objects.create(name="DckFreedChild", group=group, sync_version=1)

        body = {"model_label": "core.ItemGroupModel", "natural_key": {"name": "DckFreed"}}
        assert api.post(reverse(DELETE_CHECK), body, format="json").status_code == 409

        child.delete()
        again = api.post(reverse(DELETE_CHECK), body, format="json")
        assert again.status_code == 200
        assert again.data["safe"] is True

    def test_unknown_model_label_is_400(self, api):
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.NotAModel", "natural_key": {"code": "X"}},
            format="json",
        )
        assert response.status_code == 400
        assert "Unknown model_label" in response.data["error"]

    @pytest.mark.parametrize("body", [
        {},
        {"model_label": "core.PortModel"},
        {"natural_key": {"code": "X"}},
        {"model_label": "core.PortModel", "natural_key": "not-a-dict"},
    ])
    def test_malformed_body_is_400(self, api, body):
        response = api.post(reverse(DELETE_CHECK), body, format="json")
        assert response.status_code == 400

    def test_composite_natural_key(self, api):
        from apps.core.models import HSCodeModel, ProductDescriptionModel

        hs = HSCodeModel.objects.create(hs_code="98765432", sync_version=1)
        ProductDescriptionModel.objects.create(
            hs_code=hs, product_description="Widget", sync_version=1,
        )

        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.ProductDescriptionModel",
             "natural_key": {"hs_code": "98765432", "product_description": "Widget"}},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["natural_key"] == "98765432|Widget"

    def test_foreign_key_natural_key_is_resolved_not_treated_as_a_pk(self, api):
        """Regression: an FK natural key was filtered as a surrogate pk, so the
        record was never found and delete-check answered ``safe`` (fail-open)
        for every FK-keyed master."""
        from apps.core.models import (
            HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel,
        )

        head = HeadSIONNormsModel.objects.create(name="FkHead")
        norm = SionNormClassModel.objects.create(norm_class="E9", head_norm=head)
        SIONExportModel.objects.create(norm_class=norm, description="FkExport")
        SIONImportModel.objects.create(norm_class=norm, serial_number="1")

        # The child itself is unreferenced → genuinely safe.
        child = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.SIONExportModel",
             "natural_key": {"norm_class": "E9", "description": "FkExport"}},
            format="json",
        )
        assert child.status_code == 200
        assert child.data["natural_key"] == "E9|FkExport"

        # The parent is referenced by both children → must be blocked.
        parent = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.SionNormClassModel", "natural_key": {"norm_class": "E9"}},
            format="json",
        )
        assert parent.status_code == 409
        assert parent.data["safe"] is False
        assert any("SIONExportModel" in ref for ref in parent.data["references"])
        assert any("SIONImportModel" in ref for ref in parent.data["references"])

    def test_non_numeric_foreign_key_natural_key_is_not_a_server_error(self, api):
        """``filter(norm_class="E9")`` used to coerce to an integer pk."""
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.SIONExportModel",
             "natural_key": {"norm_class": "NOPE", "description": "x"}},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["safe"] is True


# ── GET /api/sync/status/ ───────────────────────────────────────────────

class TestStatusEndpoint:
    def test_reports_registry_size_and_server_id(self, api):
        from apps.core.sync.mixins import SERVER_ID
        from apps.core.sync.registry import get_model_labels

        response = api.get(reverse(STATUS))
        assert response.status_code == 200
        assert response.data["server_id"] == SERVER_ID
        assert response.data["registered_masters"] == len(get_model_labels())

    def test_counts_active_peers_only(self, api):
        make_peer("peer-1")
        make_peer("peer-2")
        make_peer("peer-3", is_active=False)

        assert api.get(reverse(STATUS)).data["peers"] == 2

    def test_counts_media_tasks_by_status(self, api):
        MediaSyncTask.objects.create(
            model_label="core.CompanyModel", natural_key="A", field_name="logo",
            source_server="s", source_path="a.png", status=MediaSyncTask.STATUS_PENDING,
        )
        MediaSyncTask.objects.create(
            model_label="core.CompanyModel", natural_key="B", field_name="logo",
            source_server="s", source_path="b.png", status=MediaSyncTask.STATUS_FAILED,
        )
        MediaSyncTask.objects.create(
            model_label="core.CompanyModel", natural_key="C", field_name="logo",
            source_server="s", source_path="c.png", status=MediaSyncTask.STATUS_COMPLETE,
        )

        data = api.get(reverse(STATUS)).data
        assert data["pending_media_tasks"] == 1
        assert data["failed_media_tasks"] == 1

    def test_recent_conflicts_window_is_24h(self, api):
        SyncConflictLog.objects.create(
            model_label="core.PortModel", natural_key="R1", op="update", source_server="s",
        )
        SyncConflictLog.objects.create(
            model_label="core.PortModel", natural_key="R2", op="update", source_server="s",
            created_at=timezone.now() - timedelta(days=3),
        )

        assert api.get(reverse(STATUS)).data["recent_conflicts"] == 1

    def test_last_sync_at_comes_from_the_newest_cursor(self, api):
        older = timezone.now() - timedelta(hours=5)
        newer = timezone.now() - timedelta(minutes=5)
        make_cursor(make_peer("peer-old"), last_synced_at=older)
        make_cursor(make_peer("peer-new"), last_synced_at=newer)

        reported = api.get(reverse(STATUS)).data["last_sync_at"]
        assert reported is not None
        # DRF renders with settings.DATETIME_FORMAT, so compare on the minute.
        assert newer.strftime("%d-%m-%Y %H:%M") == reported

    def test_last_sync_at_null_when_never_synced(self, api):
        assert api.get(reverse(STATUS)).data["last_sync_at"] is None
        assert SyncCursor.objects.count() == 0


# ── GET /api/sync/media/download/ ───────────────────────────────────────

class TestMediaDownloadEndpoint:
    def test_serves_the_file(self, api, media_root):
        content = b"\x89PNG\r\n\x1a\nfake-logo"
        rel = write_media(media_root, "companies/7/logo.png", content)

        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": rel})

        assert response.status_code == 200
        assert b"".join(response.streaming_content) == content
        assert response["Content-Type"] == "image/png"

    def test_content_type_falls_back_to_octet_stream(self, api, media_root):
        rel = write_media(media_root, "tl/letter.unknownext", b"blob")
        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": rel})

        assert response.status_code == 200
        assert response["Content-Type"] == "application/octet-stream"

    def test_bytes_are_identical_so_sha256_survives_transfer(self, api, media_root):
        content = bytes(range(256)) * 40
        rel = write_media(media_root, "tl/binary.bin", content)

        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": rel})
        served = b"".join(response.streaming_content)

        assert sha256_of(served) == sha256_of(content)

    def test_missing_path_param_is_400(self, api, media_root):
        response = api.get(reverse(MEDIA_DOWNLOAD))
        assert response.status_code == 400
        assert "path" in response.data["error"]

    def test_blank_path_param_is_400(self, api, media_root):
        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": ""})
        assert response.status_code == 400

    def test_unknown_file_is_404(self, api, media_root):
        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": "companies/7/absent.png"})
        assert response.status_code == 404

    @pytest.mark.parametrize("hostile", [
        "../outside.txt",
        "companies/../../outside.txt",
        "..",
        "../",
        "a/../../../etc/passwd",
        "/etc/passwd",
        "/outside.txt",
    ])
    def test_path_traversal_is_rejected(self, api, media_root, hostile):
        outside = media_root.parent / "outside.txt"
        outside.write_bytes(b"TOP SECRET")

        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": hostile})

        assert response.status_code == 400, f"{hostile!r} was not rejected"
        assert b"TOP SECRET" not in response.content

    @pytest.mark.parametrize("encoded", [
        "..%2Foutside.txt",
        "companies%2F..%2F..%2Foutside.txt",
        "%2Fetc%2Fpasswd",
    ])
    def test_percent_encoded_traversal_is_rejected(self, api, media_root, encoded):
        outside = media_root.parent / "outside.txt"
        outside.write_bytes(b"TOP SECRET")

        response = api.get(f"{reverse(MEDIA_DOWNLOAD)}?path={encoded}")

        assert response.status_code == 400, f"{encoded!r} was not rejected"

    def test_directory_path_is_not_a_server_error(self, api, media_root):
        """Regression: ``exists()`` matched directories → IsADirectoryError → 500."""
        (media_root / "companies").mkdir()
        for candidate in [".", "companies", "companies/"]:
            response = api.get(reverse(MEDIA_DOWNLOAD), {"path": candidate})
            assert response.status_code == 404, f"{candidate!r} → {response.status_code}"

    def test_null_byte_path_is_not_a_server_error(self, api, media_root):
        response = api.get(f"{reverse(MEDIA_DOWNLOAD)}?path=companies%2F%00.png")
        assert response.status_code in (400, 404)

    def test_nested_path_inside_media_root_is_allowed(self, api, media_root):
        rel = write_media(media_root, "a/b/c/d/deep.txt", b"deep")
        response = api.get(reverse(MEDIA_DOWNLOAD), {"path": rel})
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == b"deep"


# ── GET /api/sync/conflicts/ ────────────────────────────────────────────

class TestConflictLogEndpoint:
    def _log(self, nk, *, minutes_ago=0, detail="boom"):
        return SyncConflictLog.objects.create(
            model_label="core.PortModel", natural_key=nk, op="update",
            source_server="server-A", detail=detail,
            created_at=timezone.now() - timedelta(minutes=minutes_ago),
        )

    def test_empty_log(self, api):
        response = api.get(reverse(CONFLICTS))
        assert response.status_code == 200
        assert response.data == {"conflicts": [], "count": 0}

    def test_returns_conflicts_newest_first(self, api):
        self._log("OLD", minutes_ago=60)
        self._log("NEW", minutes_ago=1)

        response = api.get(reverse(CONFLICTS))
        assert response.data["count"] == 2
        assert [c["natural_key"] for c in response.data["conflicts"]] == ["NEW", "OLD"]

    def test_conflict_fields_are_exposed(self, api):
        self._log("FIELDS", detail="version tie")
        conflict = api.get(reverse(CONFLICTS)).data["conflicts"][0]
        assert conflict["model_label"] == "core.PortModel"
        assert conflict["source_server"] == "server-A"
        assert conflict["detail"] == "version tie"
        assert "created_at" in conflict

    def test_since_filter(self, api):
        self._log("BEFORE", minutes_ago=120)
        self._log("AFTER", minutes_ago=1)

        cutoff = (timezone.now() - timedelta(minutes=60)).isoformat()
        response = api.get(reverse(CONFLICTS), {"since": cutoff})

        assert [c["natural_key"] for c in response.data["conflicts"]] == ["AFTER"]

    def test_limit_caps_the_result(self, api):
        for i in range(5):
            self._log(f"L{i}", minutes_ago=i)

        response = api.get(reverse(CONFLICTS), {"limit": "2"})
        assert response.data["count"] == 2

    @pytest.mark.parametrize("bad_limit", ["abc", "", "1.5", "10;DROP"])
    def test_non_integer_limit_is_not_a_server_error(self, api, bad_limit):
        """Regression: ``int(...)`` on user input raised ValueError → 500."""
        self._log("BADLIMIT")
        response = api.get(reverse(CONFLICTS), {"limit": bad_limit})
        assert response.status_code == 400, f"limit={bad_limit!r} → {response.status_code}"

    @pytest.mark.parametrize("bad_limit", ["-1", "0"])
    def test_non_positive_limit_is_not_a_server_error(self, api, bad_limit):
        """Regression: a negative slice bound raised AssertionError → 500."""
        self._log("NEGLIMIT")
        response = api.get(reverse(CONFLICTS), {"limit": bad_limit})
        assert response.status_code == 200
        assert response.data["count"] >= 1

    def test_push_conflict_shows_up_in_the_log_endpoint(self, api):
        """End-to-end: a losing push is visible to operators."""
        PortModel.objects.create(
            code="E2E001", name="Local", sync_version=7, origin_server="server-Z",
        )
        api.post(
            reverse(PUSH),
            push_payload(port_event("E2E001", "Remote", server="server-A", version=3)),
            format="json",
        )

        conflicts = api.get(reverse(CONFLICTS)).data["conflicts"]
        assert [c["natural_key"] for c in conflicts] == ["E2E001"]
        assert conflicts[0]["source_server"] == "server-A"
