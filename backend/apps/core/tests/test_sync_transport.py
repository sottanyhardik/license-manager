"""
Module 04 — Sync **transport client** tests (push.py) and Celery entry points
(tasks.py).

``push.py`` is the only code that talks to another server, and it had no test at
all: a peer that is down, slow, broken or hostile was completely unexercised.
Here ``urllib.request.urlopen`` is patched, so every branch — success, 4xx, 5xx,
connection refused, timeout, garbage body — is driven deterministically, and the
*request* the client builds (URL, method, headers, JSON body) is asserted too.

Two behaviours are load-bearing for data safety and get extra attention:

1. ``check_delete_on_peers`` must **fail safe** — a peer we cannot reach has to
   count as "might still reference this record", i.e. block the delete.
2. ``sync_from_peer`` must send a cursor the peer can actually parse, otherwise
   every "delta" pull silently degrades into a full resync.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import MasterChange, PortModel
from apps.core.sync.mixins import SERVER_ID
from apps.core.sync.models import SyncCursor
from apps.core.sync.push import (
    check_delete_on_peers,
    push_to_all_peers,
    push_to_peer,
    sync_from_all_peers,
    sync_from_peer,
)
from apps.core.tests.sync_factories import (  # noqa: F401  (fixtures imported by name)
    FakeHTTPResponse,
    api,
    auth_client,
    connection_refused,
    http_error,
    locmem_cache,
    make_cursor,
    make_peer,
    media_root,
    port_event,
    query_params_of,
    read_timeout,
    request_headers,
    sent_json,
    sent_requests,
    patched_urlopen,
)

pytestmark = pytest.mark.django_db


PUSH_OK = {"ok": True, "applied": [{}], "skipped": [], "errors": []}
PUSH_NOT_OK = {"ok": False, "applied": [], "skipped": [], "errors": [{}]}


def _events(n=1):
    return [port_event(f"TRN{i:03d}", f"Port {i}") for i in range(n)]


# ── push_to_peer: the happy path and the request it builds ─────────────

class TestPushToPeerRequest:
    def test_successful_push_returns_true(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_to_peer(peer, _events(2)) is True
        assert urlopen.call_count == 1

    def test_posts_to_the_peers_push_endpoint(self):
        peer = make_peer("peer-B", base_url="http://peer-b.example.test")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            push_to_peer(peer, _events())

        request = sent_requests(urlopen)[0]
        assert request.full_url == "http://peer-b.example.test/api/sync/push/"
        assert request.method == "POST"

    def test_trailing_slash_on_base_url_does_not_double_up(self):
        peer = make_peer("peer-B", base_url="http://peer-b.example.test/")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            push_to_peer(peer, _events())

        assert sent_requests(urlopen)[0].full_url == "http://peer-b.example.test/api/sync/push/"

    def test_sends_json_with_our_server_id_and_the_events(self):
        peer = make_peer("peer-B")
        events = _events(3)
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            push_to_peer(peer, events)

        request = sent_requests(urlopen)[0]
        headers = request_headers(request)
        assert headers["content-type"] == "application/json"

        body = sent_json(request)
        assert body["source_server"] == SERVER_ID
        assert len(body["events"]) == 3
        assert body["events"][0]["model_label"] == "core.PortModel"

    def test_sends_bearer_token_when_the_peer_has_one(self):
        peer = make_peer("peer-B", auth_token="s3cret")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            push_to_peer(peer, _events())

        assert request_headers(sent_requests(urlopen)[0])["authorization"] == "Bearer s3cret"

    def test_no_token_fails_closed_without_a_network_request(self):
        peer = make_peer("peer-B", auth_token="")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_to_peer(peer, _events()) is False

        urlopen.assert_not_called()

    def test_payload_survives_non_json_native_values(self):
        """``default=str`` must keep dates/Decimals from killing the push."""
        from decimal import Decimal

        peer = make_peer("peer-B")
        events = [{
            "model_label": "core.ExchangeRateModel",
            "op": "create",
            "data": {"date": date(2024, 5, 1), "usd": Decimal("83.25")},
            "source_server": SERVER_ID,
            "source_version": 1,
        }]
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_to_peer(peer, events) is True

        body = sent_json(sent_requests(urlopen)[0])
        assert body["events"][0]["data"]["date"] == "2024-05-01"
        assert body["events"][0]["data"]["usd"] == "83.25"

    def test_empty_event_list_short_circuits_without_a_request(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_to_peer(peer, []) is True
        urlopen.assert_not_called()


# ── push_to_peer: failure modes ────────────────────────────────────────

class TestPushToPeerFailures:
    def test_peer_reporting_not_ok_returns_false(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_NOT_OK)):
            assert push_to_peer(peer, _events()) is False

    def test_peer_response_without_ok_key_is_treated_as_failure(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse({"applied": []})):
            assert push_to_peer(peer, _events()) is False

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 500, 502, 503])
    def test_http_error_status_returns_false(self, code):
        peer = make_peer("peer-B")
        with patched_urlopen(side_effect=http_error(code, {"detail": "nope"})):
            assert push_to_peer(peer, _events()) is False

    def test_connection_refused_returns_false(self):
        peer = make_peer("peer-B")
        with patched_urlopen(side_effect=connection_refused()):
            assert push_to_peer(peer, _events()) is False

    def test_timeout_returns_false(self):
        peer = make_peer("peer-B")
        with patched_urlopen(side_effect=read_timeout()):
            assert push_to_peer(peer, _events()) is False

    def test_garbage_response_body_returns_false(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(b"<html>502 Bad Gateway</html>")):
            assert push_to_peer(peer, _events()) is False

    def test_failure_never_raises_out_of_the_client(self):
        """Callers (signals, Celery) must not blow up because a peer is down."""
        peer = make_peer("peer-B")
        for boom in [connection_refused(), read_timeout(), http_error(500), RuntimeError("x")]:
            with patched_urlopen(side_effect=boom):
                assert push_to_peer(peer, _events()) is False


# ── push_to_all_peers ──────────────────────────────────────────────────

class TestPushToAllPeers:
    def test_pushes_to_every_active_peer(self):
        make_peer("peer-B")
        make_peer("peer-C")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            results = push_to_all_peers(_events())

        assert results == {"peer-B": True, "peer-C": True}
        assert urlopen.call_count == 2

    def test_inactive_peers_are_skipped(self):
        make_peer("peer-B")
        make_peer("peer-dead", is_active=False)
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            results = push_to_all_peers(_events())

        assert results == {"peer-B": True}
        assert urlopen.call_count == 1

    def test_one_bad_peer_does_not_stop_the_others(self):
        make_peer("peer-B", base_url="http://b.example.test")
        make_peer("peer-C", base_url="http://c.example.test")
        with patched_urlopen(responses=[connection_refused(), FakeHTTPResponse(PUSH_OK)]):
            results = push_to_all_peers(_events())

        assert results == {"peer-B": False, "peer-C": True}

    def test_no_peers_is_a_no_op(self):
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_to_all_peers(_events()) == {}
        urlopen.assert_not_called()


# ── check_delete_on_peers ──────────────────────────────────────────────

class TestCheckDeleteOnPeers:
    NK = {"code": "DEL999"}

    def test_all_peers_clear_means_no_conflicts(self):
        make_peer("peer-B")
        make_peer("peer-C")
        with patched_urlopen(response=FakeHTTPResponse({"safe": True, "references": []})) as urlopen:
            assert check_delete_on_peers("core.PortModel", self.NK) == []
        assert urlopen.call_count == 2

    def test_request_shape(self):
        peer = make_peer("peer-B", base_url="http://b.example.test", auth_token="tok")
        with patched_urlopen(response=FakeHTTPResponse({"safe": True})) as urlopen:
            check_delete_on_peers("core.PortModel", self.NK)

        request = sent_requests(urlopen)[0]
        assert request.full_url == "http://b.example.test/api/sync/delete-check/"
        assert request.method == "POST"
        assert request_headers(request)["authorization"] == "Bearer tok"
        assert sent_json(request) == {"model_label": "core.PortModel", "natural_key": self.NK}

    def test_one_peer_reporting_references_blocks_the_delete(self):
        make_peer("peer-B")
        make_peer("peer-C")
        with patched_urlopen(responses=[
            FakeHTTPResponse({"safe": True, "references": []}),
            FakeHTTPResponse({"safe": False, "references": ["license.LicenseDetailsModel: 4 record(s)"]}),
        ]):
            conflicts = check_delete_on_peers("core.PortModel", self.NK)

        assert len(conflicts) == 1
        assert conflicts[0]["server"] == "peer-C"
        assert conflicts[0]["references"] == ["license.LicenseDetailsModel: 4 record(s)"]

    def test_409_response_is_read_as_a_conflict(self):
        """The peer's own API answers 409 for a blocked delete."""
        make_peer("peer-B")
        with patched_urlopen(side_effect=http_error(
            409, {"safe": False, "references": ["allotment.AllotmentModel: 2 record(s)"]},
        )):
            conflicts = check_delete_on_peers("core.PortModel", self.NK)

        assert len(conflicts) == 1
        assert conflicts[0]["references"] == ["allotment.AllotmentModel: 2 record(s)"]

    def test_unreachable_peer_blocks_the_delete_fail_safe(self):
        make_peer("peer-B")
        with patched_urlopen(side_effect=connection_refused()):
            conflicts = check_delete_on_peers("core.PortModel", self.NK)

        assert len(conflicts) == 1, "an unreachable peer must NOT be treated as clear"
        assert conflicts[0]["server"] == "peer-B"
        assert "unreachable" in conflicts[0]["references"][0].lower()

    def test_timeout_blocks_the_delete_fail_safe(self):
        make_peer("peer-B")
        with patched_urlopen(side_effect=read_timeout()):
            conflicts = check_delete_on_peers("core.PortModel", self.NK)
        assert len(conflicts) == 1

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 500, 502, 503])
    def test_error_status_other_than_409_blocks_the_delete_fail_safe(self, code):
        make_peer("peer-B")
        with patched_urlopen(side_effect=http_error(code, b"boom")):
            conflicts = check_delete_on_peers("core.PortModel", self.NK)

        assert len(conflicts) == 1, f"HTTP {code} must not be read as 'safe'"
        assert "unreachable" in conflicts[0]["references"][0].lower()

    def test_garbage_body_blocks_the_delete_fail_safe(self):
        make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(b"not json")):
            assert len(check_delete_on_peers("core.PortModel", self.NK)) == 1

    def test_every_unreachable_peer_is_listed(self):
        make_peer("peer-B")
        make_peer("peer-C")
        make_peer("peer-D")
        with patched_urlopen(responses=[
            connection_refused(),
            FakeHTTPResponse({"safe": True}),
            http_error(503),
        ]):
            conflicts = check_delete_on_peers("core.PortModel", self.NK)

        assert {c["server"] for c in conflicts} == {"peer-B", "peer-D"}

    def test_inactive_peers_are_not_consulted(self):
        make_peer("peer-B")
        make_peer("peer-dead", is_active=False)
        with patched_urlopen(response=FakeHTTPResponse({"safe": True})) as urlopen:
            check_delete_on_peers("core.PortModel", self.NK)
        assert urlopen.call_count == 1

    def test_no_peers_means_nothing_blocks(self):
        with patched_urlopen(response=FakeHTTPResponse({"safe": True})) as urlopen:
            assert check_delete_on_peers("core.PortModel", self.NK) == []
        urlopen.assert_not_called()

    def test_date_natural_key_is_serialisable(self):
        """Regression: ExchangeRateModel's natural key is a date and
        ``json.dumps`` raised TypeError straight out of the function."""
        make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse({"safe": True})) as urlopen:
            conflicts = check_delete_on_peers(
                "core.ExchangeRateModel", {"date": date(2024, 5, 1)},
            )

        assert conflicts == []
        assert sent_json(sent_requests(urlopen)[0])["natural_key"] == {"date": "2024-05-01"}


# ── sync_from_peer ─────────────────────────────────────────────────────

class TestSyncFromPeer:
    def test_applies_pulled_events_and_returns_the_count(self):
        peer = make_peer("peer-B")
        payload = {"server_id": "peer-B", "events": [
            port_event("PLL001", "Pulled One", server="peer-B"),
            port_event("PLL002", "Pulled Two", server="peer-B"),
        ], "count": 2}

        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 2

        assert PortModel.objects.filter(code__in=["PLL001", "PLL002"]).count() == 2
        assert PortModel.objects.get(code="PLL001").origin_server == "peer-B"

    def test_first_durable_pull_starts_at_immutable_cursor_zero(self):
        peer = make_peer("peer-B", base_url="http://b.example.test")
        assert not SyncCursor.objects.filter(peer=peer).exists()

        with patched_urlopen(response=FakeHTTPResponse({"events": []})) as urlopen:
            sync_from_peer(peer)

        request = sent_requests(urlopen)[0]
        assert query_params_of(request.full_url) == {"cursor": "0"}
        assert SyncCursor.objects.filter(peer=peer).exists()

    def test_cursor_advances_after_a_successful_pull(self):
        peer = make_peer("peer-B")
        before = timezone.now()
        payload = {"events": [port_event("PLL003", "Cursor", server="peer-B")]}

        with patched_urlopen(response=FakeHTTPResponse(payload)):
            sync_from_peer(peer)

        cursor = SyncCursor.objects.get(peer=peer)
        assert cursor.last_synced_at is not None and cursor.last_synced_at >= before
        assert cursor.last_pull_at is not None and cursor.last_pull_at >= before

        peer.refresh_from_db()
        assert peer.last_seen is not None and peer.last_seen >= before

    def test_cursor_acknowledges_the_source_watermark_not_receiver_clock(self):
        """A source change written during transport must remain eligible later."""
        peer = make_peer("peer-B")
        source_watermark = timezone.now() - timedelta(minutes=5)
        payload = {
            "events": [{
                **port_event("PLL003W", "Watermark", server="peer-B"),
                "at": source_watermark.isoformat(),
            }],
            "cursor": source_watermark.isoformat(),
        }

        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 1

        cursor = SyncCursor.objects.get(peer=peer)
        assert cursor.last_synced_at == source_watermark

    def test_partial_batch_does_not_acknowledge_the_source_cursor(self):
        """Rejected events are retried; they must never be skipped by a cursor."""
        peer = make_peer("peer-B")
        previous_cursor = timezone.now() - timedelta(hours=1)
        make_cursor(peer, last_synced_at=previous_cursor)
        source_watermark = timezone.now() - timedelta(minutes=5)
        payload = {
            "events": [
                {**port_event("PLL003P", "Good", server="peer-B"), "at": source_watermark.isoformat()},
                {
                    "model_label": "core.NotAModel", "op": "create", "data": {},
                    "source_server": "peer-B", "source_version": 1,
                    "at": source_watermark.isoformat(),
                },
            ],
            "cursor": source_watermark.isoformat(),
        }

        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 1

        cursor = SyncCursor.objects.get(peer=peer)
        assert cursor.last_synced_at == previous_cursor
        assert cursor.last_pull_at is None

    def test_existing_cursor_is_sent_as_since(self):
        peer = make_peer("peer-B")
        cursor_time = timezone.now() - timedelta(hours=2)
        make_cursor(peer, last_synced_at=cursor_time)

        with patched_urlopen(response=FakeHTTPResponse({"events": []})) as urlopen:
            sync_from_peer(peer)

        params = query_params_of(sent_requests(urlopen)[0].full_url)
        assert params["since"] == cursor_time.isoformat()

    def test_since_is_url_encoded_so_the_peer_can_parse_it(self, api):
        """Regression: the cursor was interpolated raw, so the "+" of the UTC
        offset arrived as a space, ``parse_datetime`` returned None and the peer
        silently replied with its **entire** change feed."""
        peer = make_peer("peer-B")
        cursor_time = timezone.now() - timedelta(hours=1)
        make_cursor(peer, last_synced_at=cursor_time)
        assert "+" in cursor_time.isoformat(), "precondition: aware ISO offset"

        with patched_urlopen(response=FakeHTTPResponse({"events": []})) as urlopen:
            sync_from_peer(peer)
        query = sent_requests(urlopen)[0].full_url.split("?", 1)[1]
        assert "+" not in query, f"un-encoded cursor in {query!r}"

        # Replay that exact query string against the real pull endpoint: the
        # change from before the cursor must NOT come back.
        PortModel.objects.create(code="OLD001", name="Before cursor", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="OLD001",
            op=MasterChange.OP_CREATE, at=cursor_time - timedelta(hours=1),
        )
        PortModel.objects.create(code="NEW001", name="After cursor", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="NEW001",
            op=MasterChange.OP_CREATE, at=timezone.now(),
        )

        response = api.get(f"{reverse('sync:sync-pull')}?{query}")
        codes = [e["data"].get("code") for e in response.data["events"]]
        assert "NEW001" in codes
        assert "OLD001" not in codes, "cursor was dropped — delta pull is a full resync"

    def test_empty_response_applies_nothing(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse({"events": []})):
            assert sync_from_peer(peer) == 0

        cursor = SyncCursor.objects.get(peer=peer)
        # Documents current behaviour: an empty delta does not move the cursor.
        assert cursor.last_synced_at is None
        assert cursor.last_pull_at is None

    def test_response_without_events_key_is_tolerated(self):
        peer = make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse({"server_id": "peer-B"})):
            assert sync_from_peer(peer) == 0

    @pytest.mark.parametrize("boom", ["refused", "timeout", "http500", "garbage"])
    def test_unreachable_or_broken_peer_leaves_the_cursor_untouched(self, boom):
        peer = make_peer("peer-B")
        cursor_time = timezone.now() - timedelta(hours=3)
        make_cursor(peer, last_synced_at=cursor_time)

        cases = {
            "refused": dict(side_effect=connection_refused()),
            "timeout": dict(side_effect=read_timeout()),
            "http500": dict(side_effect=http_error(500)),
            "garbage": dict(response=FakeHTTPResponse(b"<html>")),
        }
        with patched_urlopen(**cases[boom]):
            assert sync_from_peer(peer) == 0

        cursor = SyncCursor.objects.get(peer=peer)
        assert cursor.last_synced_at == cursor_time
        assert cursor.last_pull_at is None
        peer.refresh_from_db()
        assert peer.last_seen is None

    def test_bad_events_are_reported_not_raised(self):
        peer = make_peer("peer-B")
        payload = {"events": [
            {"model_label": "core.NotAModel", "op": "create", "data": {},
             "source_server": "peer-B", "source_version": 1},
        ]}
        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 0

    def test_partially_bad_batch_still_applies_the_good_events(self):
        peer = make_peer("peer-B")
        payload = {"events": [
            port_event("PLL004", "Good", server="peer-B"),
            {"model_label": "core.NotAModel", "op": "create", "data": {},
             "source_server": "peer-B", "source_version": 1},
        ]}
        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 1

        assert PortModel.objects.filter(code="PLL004").exists()

    def test_replaying_the_same_pull_is_idempotent(self):
        peer = make_peer("peer-B")
        payload = {"events": [port_event("PLL005", "Idem", server="peer-B")]}

        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 1
        with patched_urlopen(response=FakeHTTPResponse(payload)):
            assert sync_from_peer(peer) == 0          # same version → skipped

        assert PortModel.objects.filter(code="PLL005").count() == 1
        assert PortModel.objects.get(code="PLL005").sync_version == 1


class TestSyncFromAllPeers:
    def test_aggregates_per_peer_counts(self):
        make_peer("peer-B")
        make_peer("peer-C")
        with patched_urlopen(responses=[
            FakeHTTPResponse({"events": [port_event("ALL001", "B", server="peer-B")]}),
            FakeHTTPResponse({"events": [
                port_event("ALL002", "C1", server="peer-C"),
                port_event("ALL003", "C2", server="peer-C"),
            ]}),
        ]):
            results = sync_from_all_peers()

        assert results == {"peer-B": 1, "peer-C": 2}

    def test_inactive_peers_are_skipped(self):
        make_peer("peer-B")
        make_peer("peer-dead", is_active=False)
        with patched_urlopen(response=FakeHTTPResponse({"events": []})):
            assert set(sync_from_all_peers()) == {"peer-B"}

    def test_a_dead_peer_does_not_block_a_live_one(self):
        make_peer("peer-B")
        make_peer("peer-C")
        with patched_urlopen(responses=[
            connection_refused(),
            FakeHTTPResponse({"events": [port_event("ALL004", "C", server="peer-C")]}),
        ]):
            assert sync_from_all_peers() == {"peer-B": 0, "peer-C": 1}


# ── Celery tasks ───────────────────────────────────────────────────────

class TestCeleryTasksDisabled:
    """With SYNC_ENABLED off, no task may touch the network."""

    @pytest.fixture(autouse=True)
    def _disabled(self, settings):
        settings.SYNC_ENABLED = False

    def test_pull_from_peers_is_a_no_op(self):
        from apps.core.sync.tasks import pull_from_peers

        with patch("apps.core.sync.push.sync_from_all_peers") as pull:
            assert pull_from_peers() == "Sync disabled"
        pull.assert_not_called()

    def test_process_media_tasks_is_a_no_op(self):
        from apps.core.sync.tasks import process_media_tasks

        with patch("apps.core.sync.media.run_media_sync_worker") as worker:
            assert process_media_tasks() == "Sync disabled"
        worker.assert_not_called()

    def test_push_changes_is_a_no_op(self):
        from apps.core.sync.tasks import push_changes

        with patch("apps.core.sync.service.get_changes_since") as changes, \
                patch("apps.core.sync.push.push_to_all_peers") as push:
            assert push_changes() == "Sync disabled"
        changes.assert_not_called()
        push.assert_not_called()

    def test_missing_setting_is_treated_as_disabled(self, settings):
        from apps.core.sync.tasks import pull_from_peers

        del settings.SYNC_ENABLED
        with patch("apps.core.sync.push.sync_from_all_peers") as pull:
            assert pull_from_peers() == "Sync disabled"
        pull.assert_not_called()


class TestCeleryTasksEnabled:
    @pytest.fixture(autouse=True)
    def _enabled(self, settings):
        settings.SYNC_ENABLED = True

    def test_pull_from_peers_delegates_and_reports(self):
        from apps.core.sync.tasks import pull_from_peers

        with patch("apps.core.sync.push.sync_from_all_peers",
                   return_value={"peer-B": 3}) as pull:
            assert pull_from_peers() == {"peer-B": 3}
        pull.assert_called_once_with()

    def test_pull_from_peers_end_to_end_over_the_fake_wire(self):
        from apps.core.sync.tasks import pull_from_peers

        make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(
            {"events": [port_event("CEL001", "Celery", server="peer-B")]},
        )):
            assert pull_from_peers() == {"peer-B": 1}

        assert PortModel.objects.filter(code="CEL001").exists()

    def test_process_media_tasks_runs_the_worker(self):
        from apps.core.sync.tasks import process_media_tasks

        with patch("apps.core.sync.media.run_media_sync_worker") as worker:
            assert process_media_tasks() == "OK"
        worker.assert_called_once_with()

    def test_push_changes_pushes_the_delta(self):
        from apps.core.sync.tasks import push_changes

        events = _events(2)
        with patch("apps.core.sync.service.get_changes_since", return_value=events) as changes, \
                patch("apps.core.sync.push.push_to_all_peers",
                      return_value={"peer-B": True}) as push:
            assert push_changes() == {"peer-B": True}

        changes.assert_called_once_with(None)
        push.assert_called_once_with(events)

    def test_push_changes_forwards_the_since_cursor(self):
        from apps.core.sync.tasks import push_changes

        since = timezone.now().isoformat()
        with patch("apps.core.sync.service.get_changes_since", return_value=[]) as changes:
            assert push_changes(since) == "No changes"
        changes.assert_called_once_with(since)

    def test_push_changes_with_nothing_to_send_makes_no_request(self):
        from apps.core.sync.tasks import push_changes

        make_peer("peer-B")
        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_changes(timezone.now().isoformat()) == "No changes"
        urlopen.assert_not_called()

    def test_push_changes_end_to_end_over_the_fake_wire(self):
        from apps.core.sync.tasks import push_changes

        make_peer("peer-B")
        PortModel.objects.create(code="CEL002", name="Pushed", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="CEL002", op=MasterChange.OP_CREATE,
        )

        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            assert push_changes() == {"peer-B": True}

        body = sent_json(sent_requests(urlopen)[0])
        assert any(e["data"].get("code") == "CEL002" for e in body["events"])

    def test_task_names_are_registered(self):
        from apps.core.sync import tasks

        assert tasks.pull_from_peers.name == "sync.pull_from_peers"
        assert tasks.process_media_tasks.name == "sync.process_media_tasks"
        assert tasks.push_changes.name == "sync.push_changes"


class TestChangeFeedRobustness:
    """``get_changes_since`` feeds every outbound push and pull."""

    def test_changes_for_unregistered_models_are_skipped(self):
        from apps.core.sync.service import get_changes_since

        MasterChange.objects.create(
            model_label="license.LicenseDetailsModel", natural_key="0510000001",
            op=MasterChange.OP_CREATE,
        )
        PortModel.objects.create(code="FEED01", name="Real", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="FEED01", op=MasterChange.OP_CREATE,
        )

        events = get_changes_since()
        assert {e["model_label"] for e in events} == {"core.PortModel"}

    def test_changes_for_hard_deleted_rows_are_skipped(self):
        """A row removed outside the sync path must not break the whole feed."""
        from apps.core.sync.service import get_changes_since

        port = PortModel.objects.create(code="FEED02", name="Vanishing", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="FEED02", op=MasterChange.OP_CREATE,
        )
        port.delete()
        PortModel.objects.create(code="FEED03", name="Survivor", sync_version=1)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="FEED03", op=MasterChange.OP_CREATE,
        )

        codes = [e["data"].get("code") for e in get_changes_since()]
        assert codes == ["FEED03"]

    def test_delete_changes_survive_a_hard_deleted_row(self):
        from apps.core.sync.service import get_changes_since

        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="FEED04", op=MasterChange.OP_DELETE,
        )
        events = get_changes_since()
        assert events[0]["op"] == "delete"
        assert events[0]["data"] == {"code": "FEED04"}

    def test_excluded_fields_are_not_transported(self):
        """``MasterSyncEntry.exclude_fields`` is a registry feature no entry uses
        yet; it must work before someone relies on it."""
        from apps.core.sync.registry import MasterSyncEntry
        from apps.core.sync.service import _serialize_instance, apply_create_or_update

        entry = MasterSyncEntry(
            model_label="core.PortModel", natural_key=("code",), uid_field=None,
            exclude_fields=("name",),
        )
        port = PortModel.objects.create(code="EXC001", name="Secret", sync_version=1)

        data = _serialize_instance(port, entry)
        assert "name" not in data
        assert data["code"] == "EXC001"

        result = apply_create_or_update(
            entry, {"code": "EXC001", "name": "Overwrite me"}, "server-A", 2,
        )
        assert result.op == "update"
        port.refresh_from_db()
        assert port.name == "Secret", "an excluded field must not be written"

    def test_conflict_log_helper(self):
        from apps.core.sync.service import get_conflict_log

        SyncConflictLog = __import__(
            "apps.core.sync.models", fromlist=["SyncConflictLog"],
        ).SyncConflictLog
        old = SyncConflictLog.objects.create(
            model_label="core.PortModel", natural_key="CL-OLD", op="update",
            source_server="server-A", created_at=timezone.now() - timedelta(days=2),
        )
        SyncConflictLog.objects.create(
            model_label="core.PortModel", natural_key="CL-NEW", op="update",
            source_server="server-A",
        )

        assert [c["natural_key"] for c in get_conflict_log()] == ["CL-NEW", "CL-OLD"]
        assert len(get_conflict_log(limit=1)) == 1

        cutoff = (timezone.now() - timedelta(days=1)).isoformat()
        assert [c["natural_key"] for c in get_conflict_log(since=cutoff)] == ["CL-NEW"]
        assert len(get_conflict_log(since="not-a-date")) == 2
        assert old.pk


class TestSyncBookkeepingModels:
    """The operator-facing string forms used in logs and the admin."""

    def test_peer_str(self):
        peer = make_peer("peer-B", base_url="http://b.example.test")
        assert str(peer) == "Peer peer-B (http://b.example.test)"

    def test_cursor_str(self):
        cursor = make_cursor(make_peer("peer-B"))
        assert "peer-B" in str(cursor)

    def test_conflict_log_str(self):
        from apps.core.sync.models import SyncConflictLog

        conflict = SyncConflictLog.objects.create(
            model_label="core.PortModel", natural_key="STR001", op="update",
            source_server="server-A", source_version=3,
        )
        text = str(conflict)
        assert "core.PortModel[STR001]" in text
        assert "v3" in text
        assert "server-A" in text

    def test_media_task_str(self):
        from apps.core.sync.models import MediaSyncTask

        task = MediaSyncTask.objects.create(
            model_label="core.CompanyModel", natural_key="C1", field_name="logo",
            source_server="peer-B", source_path="companies/1/logo.png",
        )
        assert str(task) == "Media pending: core.CompanyModel[C1].logo from peer-B"


class TestPushedPayloadIsAcceptedByThePeerApi:
    """Contract test: what push.py sends must be what views.py accepts.

    The client and the server were written independently and never met in a
    test; this feeds the client's exact JSON body into the real push endpoint.
    """

    def test_client_payload_round_trips_through_the_push_endpoint(self, api):
        peer = make_peer("peer-B")
        PortModel.objects.create(code="RTP001", name="Round Trip", sync_version=4)
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="RTP001", op=MasterChange.OP_CREATE,
        )

        from apps.core.sync.service import get_changes_since
        from apps.core.sync.mixins import SERVER_ID
        receiving_peer = make_peer(SERVER_ID, auth_token="round-trip-token")
        api.credentials(
            HTTP_X_SYNC_SERVER_ID=receiving_peer.server_id,
            HTTP_AUTHORIZATION="Bearer round-trip-token",
        )
        events = get_changes_since()

        with patched_urlopen(response=FakeHTTPResponse(PUSH_OK)) as urlopen:
            push_to_peer(peer, events)
        wire_body = sent_requests(urlopen)[0].data.decode()

        PortModel.objects.filter(code="RTP001").delete()

        response = api.post(reverse("sync:sync-push"), data=wire_body,
                            content_type="application/json")

        assert response.status_code == 200, response.data
        assert response.data["ok"] is True, response.data["errors"]
        assert PortModel.objects.filter(code="RTP001").exists()
        assert json.loads(wire_body)["source_server"] == SERVER_ID
