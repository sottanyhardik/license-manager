"""Focused invariants for the immutable master-sync transport ledger."""
from __future__ import annotations

import uuid

import pytest

from apps.core.sync.models import SyncEvent, SyncInboxEvent, SyncPeerDelivery
from apps.core.sync.push import pending_events_for_peer
from apps.core.sync.service import apply_sync_batch, get_changes_since
from apps.core.tests.sync_factories import make_peer, port_event


pytestmark = pytest.mark.django_db


def _event(code: str, *, event_id=None, version=1):
    payload = port_event(code, code, server="server-A", version=version)
    payload["event_id"] = str(event_id or uuid.uuid4())
    return payload


def test_replay_is_idempotent_and_keeps_original_payload():
    event = _event("LEDGER001")
    assert len(apply_sync_batch([event]).applied) == 1
    assert len(apply_sync_batch([event]).skipped) == 1
    assert SyncInboxEvent.objects.filter(source_server="server-A").count() == 1
    stored = SyncEvent.objects.get()
    assert stored.payload["data"]["name"] == "LEDGER001"
    assert stored.source_version == 1


def test_integer_cursor_orders_events_with_equal_wall_clock_times():
    first, second = _event("LEDGER002"), _event("LEDGER003")
    apply_sync_batch([first, second])
    feed = get_changes_since(cursor=0)
    assert [row["data"]["code"] for row in feed] == ["LEDGER002", "LEDGER003"]
    assert get_changes_since(cursor=feed[0]["cursor"])[0]["data"]["code"] == "LEDGER003"


def test_offline_peer_delivery_remains_pending_until_acknowledged():
    event = _event("LEDGER004")
    apply_sync_batch([event])
    peer = make_peer("peer-ledger")
    pending = pending_events_for_peer(peer)
    assert [row["event_id"] for row in pending] == [event["event_id"]]
    stored = SyncEvent.objects.get()
    SyncPeerDelivery.objects.create(
        peer=peer, event=stored, status=SyncPeerDelivery.STATUS_ACKNOWLEDGED,
    )
    assert pending_events_for_peer(peer) == []


def test_failed_inbox_event_is_not_acknowledged_as_a_safe_replay():
    event = {
        "event_id": str(uuid.uuid4()), "model_label": "core.NotRegistered",
        "op": "create", "data": {}, "source_server": "server-A", "source_version": 1,
    }
    assert len(apply_sync_batch([event]).errors) == 1
    assert len(apply_sync_batch([event]).errors) == 1
    assert SyncInboxEvent.objects.get().result == "failed"


def test_local_registered_master_write_emits_transactional_outbox_snapshot():
    from apps.core.models import PortModel

    port = PortModel.objects.create(code="LEDGER005", name="Initial")
    port.name = "Changed"
    port.save(update_fields=["name"])

    events = list(SyncEvent.objects.order_by("id"))
    assert [event.op for event in events] == ["create", "update"]
    assert events[-1].payload["data"]["name"] == "Changed"
    assert events[-1].source_version == 2


def test_inbound_write_is_not_reemitted_as_a_local_event():
    event = _event("LEDGER006")
    apply_sync_batch([event])
    stored = SyncEvent.objects.get()
    assert stored.event_id == uuid.UUID(event["event_id"])
    assert stored.source_server == "server-A"


def test_event_rows_are_append_only():
    apply_sync_batch([_event("LEDGER007")])
    event = SyncEvent.objects.get()
    event.op = "delete"
    with pytest.raises(RuntimeError, match="immutable"):
        event.save()
