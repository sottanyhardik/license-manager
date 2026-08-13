"""
Module 04 — Sync **failure handling**: malformed, hostile, duplicated and
out-of-order input arriving over the wire.

A sync endpoint is exposed to whatever a peer (or a confused operator, or an
attacker with a token) sends.  The rules pinned here are:

* Garbage in → 4xx and **no partial write**; never a 500.
* One poison event must not abort the rest of the batch, and must not make the
  endpoint permanently un-pushable (the sender retries forever).
* Replaying an event is a no-op: one row, no version inflation.
* Event order must not change the converged result.
* Every registered master must be routable through the transport.
"""
from __future__ import annotations

import json

import pytest
from django.urls import reverse

from apps.core.models import (
    CompanyModel,
    HeadSIONNormsModel,
    HSCodeModel,
    ItemGroupModel,
    ItemNameModel,
    MasterChange,
    PortModel,
    ProductDescriptionModel,
    SionNormClassModel,
)
from apps.core.sync.models import SyncConflictLog
from apps.core.tests.sync_factories import (  # noqa: F401  (fixtures imported by name)
    api,
    auth_client,
    company_event,
    locmem_cache,
    make_peer,
    media_root,
    port_event,
    push_payload,
    sync_event,
)

pytestmark = pytest.mark.django_db

PUSH = "sync:sync-push"
PULL = "sync:sync-pull"
DELETE_CHECK = "sync:sync-delete-check"


def _push(api, events, source_server="server-A"):
    return api.post(reverse(PUSH), push_payload(events, source_server=source_server), format="json")


# ── malformed envelopes ────────────────────────────────────────────────

class TestMalformedPayloads:
    @pytest.mark.parametrize("payload,label", [
        ({}, "empty body"),
        ({"events": []}, "no source_server"),
        ({"source_server": "server-A"}, "no events"),
        ({"source_server": "server-A", "events": {}}, "events not a list"),
        ({"source_server": "server-A", "events": "nope"}, "events is a string"),
        ({"source_server": "", "events": [{}]}, "blank source_server"),
        ({"source_server": "server-A", "events": [None]}, "null event"),
    ])
    def test_envelope_problems_are_400(self, api, payload, label):
        response = api.post(reverse(PUSH), payload, format="json")
        assert response.status_code == 400, f"{label} → {response.status_code}"

    @pytest.mark.parametrize("event,label", [
        ({"op": "create", "data": {"code": "MAL001"}, "source_server": "server-A"},
         "missing model_label"),
        ({"model_label": "core.PortModel", "data": {"code": "MAL001"},
          "source_server": "server-A"}, "missing op"),
        ({"model_label": "core.PortModel", "op": "create", "source_server": "server-A"},
         "missing data"),
        ({"model_label": "core.PortModel", "op": "create", "data": {"code": "MAL001"}},
         "missing source_server"),
        ({"model_label": "core.PortModel", "op": "explode",
          "data": {"code": "MAL001"}, "source_server": "server-A"}, "unknown op"),
        ({"model_label": "core.PortModel", "op": "CREATE",
          "data": {"code": "MAL001"}, "source_server": "server-A"}, "wrong case op"),
        ({"model_label": "core.PortModel", "op": "create",
          "data": "not-a-dict", "source_server": "server-A"}, "data is a string"),
        ({"model_label": "core.PortModel", "op": "create",
          "data": ["code"], "source_server": "server-A"}, "data is a list"),
        ({"model_label": "core.PortModel", "op": "create", "data": {"code": "MAL001"},
          "source_server": "server-A", "source_version": 0}, "version below 1"),
        ({"model_label": "core.PortModel", "op": "create", "data": {"code": "MAL001"},
          "source_server": "server-A", "source_version": -3}, "negative version"),
        ({"model_label": "core.PortModel", "op": "create", "data": {"code": "MAL001"},
          "source_server": "server-A", "source_version": "many"}, "version not an int"),
        ({"model_label": "core.PortModel", "op": "create", "data": {"code": "MAL001"},
          "source_server": "server-A", "at": "yesterday"}, "unparseable timestamp"),
        ({"model_label": "core.PortModel", "op": "create", "data": {"code": "MAL001"},
          "source_server": "server-A", "media": "not-a-dict"}, "media is a string"),
        ({"model_label": "x" * 200, "op": "create", "data": {"code": "MAL001"},
          "source_server": "server-A"}, "model_label too long"),
    ])
    def test_event_problems_are_400_and_write_nothing(self, api, event, label):
        response = _push(api, [event])

        assert response.status_code == 400, f"{label} → {response.status_code}"
        assert not PortModel.objects.filter(code="MAL001").exists(), f"{label} wrote a row"
        assert MasterChange.objects.count() == 0, f"{label} wrote a change-feed row"

    def test_one_bad_event_rejects_the_whole_envelope(self, api):
        """Serializer-level validation is all-or-nothing, so a valid sibling in
        the same batch is not applied either."""
        response = _push(api, [
            port_event("MAL010", "Good"),
            {"model_label": "core.PortModel", "op": "nope", "data": {"code": "MAL011"},
             "source_server": "server-A"},
        ])

        assert response.status_code == 400
        assert not PortModel.objects.filter(code__in=["MAL010", "MAL011"]).exists()

    def test_error_body_names_the_offending_field(self, api):
        response = _push(api, [{"op": "create", "data": {}, "source_server": "server-A"}])
        assert response.status_code == 400
        assert "model_label" in json.dumps(response.data)

    @pytest.mark.parametrize("body", ["{not json", "", "[]", "null", "<xml/>"])
    def test_corrupt_request_body_is_400(self, api, body):
        response = api.post(reverse(PUSH), data=body, content_type="application/json")
        assert response.status_code == 400

    def test_wrong_content_type_is_rejected(self, api):
        response = api.post(reverse(PUSH), data="source_server=server-A",
                            content_type="text/plain")
        assert response.status_code in (400, 415)

    @pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
    def test_push_only_accepts_post(self, api, method):
        response = getattr(api, method)(reverse(PUSH))
        assert response.status_code == 405

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_pull_only_accepts_get(self, api, method):
        response = getattr(api, method)(reverse(PULL))
        assert response.status_code == 405


# ── schema-valid but semantically broken events ────────────────────────

class TestUnprocessableEvents:
    def test_unknown_model_label_is_reported_not_fatal(self, api):
        response = _push(api, [sync_event("core.NotAModel", "create", {"code": "X"})])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert len(response.data["errors"]) == 1
        assert "Unknown model_label" in response.data["errors"][0]["error"]
        assert MasterChange.objects.count() == 0

    def test_unregistered_but_real_model_is_refused(self, api):
        """A model that exists in Django but is not in the sync registry must not
        be writable through the sync API."""
        response = _push(api, [sync_event(
            "license.LicenseDetailsModel", "create", {"license_number": "0510000000"},
        )])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "Unknown model_label" in response.data["errors"][0]["error"]

        from apps.license.models import LicenseDetailsModel
        assert not LicenseDetailsModel.objects.filter(license_number="0510000000").exists()

    def test_missing_natural_key_is_a_per_event_error_not_a_500(self, api):
        """Regression: the natural-key check ran outside the error handler, so a
        payload without its business key returned 500 — and the sender, having
        no success to record, replayed the same poisoned batch forever."""
        response = _push(api, [sync_event("core.PortModel", "create", {"name": "no code"})])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "Missing natural key field 'code'" in response.data["errors"][0]["error"]
        assert PortModel.objects.count() == 0

    def test_missing_natural_key_on_delete_is_a_per_event_error(self, api):
        response = _push(api, [sync_event("core.PortModel", "delete", {"name": "x"})])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "Missing natural key" in response.data["errors"][0]["error"]

    def test_a_poison_event_does_not_abort_its_batch(self, api):
        response = _push(api, [
            port_event("POI001", "Good one"),
            sync_event("core.PortModel", "create", {"name": "no code"}),
            port_event("POI002", "Good two"),
        ])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert len(response.data["applied"]) == 2
        assert len(response.data["errors"]) == 1
        assert PortModel.objects.filter(code__in=["POI001", "POI002"]).count() == 2

    def test_unknown_field_in_data_is_a_per_event_error(self, api):
        response = _push(api, [sync_event(
            "core.PortModel", "create", {"code": "UNK001", "name": "x", "nonsense": 1},
        )])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "nonsense" in response.data["errors"][0]["error"]
        assert not PortModel.objects.filter(code="UNK001").exists()

    def test_wrong_type_for_a_model_field_is_a_per_event_error(self, api):
        response = _push(api, [sync_event(
            "core.ItemNameModel", "create",
            {"name": "BadTypes", "restriction_percentage": "not-a-number"},
        )])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert not ItemNameModel.objects.filter(name="BadTypes").exists()

    def test_oversized_value_is_a_per_event_error(self, api):
        response = _push(api, [sync_event(
            "core.PortModel", "create", {"code": "X" * 200, "name": "Too long"},
        )])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert PortModel.objects.filter(name="Too long").count() == 0

    def test_unresolvable_parent_is_a_per_event_error(self, api):
        """FK parents travel as natural keys; if the parent has not arrived yet
        the child must fail cleanly (and be retried), not link to a random row."""
        response = _push(api, [sync_event(
            "core.ItemNameModel", "create", {"name": "Orphan", "group": "MissingGroup"},
        )])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "Unresolved FK" in response.data["errors"][0]["error"]
        assert not ItemNameModel.objects.filter(name="Orphan").exists()

    def test_corrupt_fk_natural_key_in_a_push_event_is_a_per_event_error(self, api):
        response = _push(api, [sync_event(
            "core.ItemNameModel", "create", {"name": "BadFk", "group": "A|B|C"},
        )])

        assert response.status_code == 200
        assert response.data["ok"] is False
        assert "does not match" in response.data["errors"][0]["error"]
        assert not ItemNameModel.objects.filter(name="BadFk").exists()

    def test_parent_then_child_in_one_batch_succeeds(self, api):
        response = _push(api, [
            sync_event("core.ItemNameModel", "create", {"name": "Child", "group": "Parent"}),
            sync_event("core.ItemGroupModel", "create", {"name": "Parent"}),
        ])

        assert response.status_code == 200, response.data
        assert response.data["ok"] is True, response.data["errors"]
        child = ItemNameModel.objects.get(name="Child")
        assert child.group == ItemGroupModel.objects.get(name="Parent")

    def test_local_user_ids_are_never_replicated(self, api):
        """A surrogate user id from another server would point at the wrong
        person locally — or break a deferred FK constraint at commit."""
        response = _push(api, [sync_event(
            "core.PortModel", "create",
            {"code": "AUD001", "name": "Audit", "created_by_id": 999999,
             "modified_by_id": 999999},
        )])

        assert response.status_code == 200, response.data
        assert response.data["ok"] is True, response.data["errors"]
        port = PortModel.objects.get(code="AUD001")
        assert port.created_by_id != 999999
        assert port.modified_by_id != 999999

    def test_outbound_events_do_not_leak_local_user_ids(self, api):
        from apps.accounts.models import User

        author = User.objects.create_user(
            username="audit_author", email="audit_author@example.test", password="x",
        )
        PortModel.objects.create(
            code="AUD002", name="Audit Out", sync_version=1,
            created_by=author, modified_by=author,
        )
        MasterChange.objects.create(
            model_label="core.PortModel", natural_key="AUD002", op=MasterChange.OP_CREATE,
        )

        event = [e for e in api.get(reverse(PULL)).data["events"]
                 if e["data"].get("code") == "AUD002"][0]

        assert "created_by_id" not in event["data"]
        assert "modified_by_id" not in event["data"]
        assert "created_by" not in event["data"]


# ── replay / duplicates ────────────────────────────────────────────────

class TestReplayAndDuplicates:
    def test_replaying_a_create_produces_exactly_one_record(self, api):
        event = port_event("RPL001", "Once", version=1)

        first = _push(api, [event])
        second = _push(api, [event])

        assert first.data["applied"][0]["op"] == "create"
        assert second.data["skipped"][0]["op"] == "noop"
        assert PortModel.objects.filter(code="RPL001").count() == 1

    def test_replay_does_not_inflate_the_version(self, api):
        event = port_event("RPL002", "Version", version=3)
        for _ in range(4):
            _push(api, [event])

        port = PortModel.objects.get(code="RPL002")
        assert port.sync_version == 3
        assert port.name == "Version"

    def test_replay_does_not_duplicate_change_feed_rows(self, api):
        event = port_event("RPL003", "Feed", version=1)
        _push(api, [event])
        _push(api, [event])

        assert MasterChange.objects.filter(
            model_label="core.PortModel", natural_key="RPL003",
        ).count() == 1

    def test_the_same_event_twice_in_one_batch_is_applied_once(self, api):
        event = port_event("RPL004", "Twice", version=1)
        response = _push(api, [event, event])

        assert response.data["total"] == 2
        assert len(response.data["applied"]) == 1
        assert len(response.data["skipped"]) == 1
        assert PortModel.objects.filter(code="RPL004").count() == 1

    def test_two_servers_creating_the_same_key_reconcile_to_one_row(self, api):
        _push(api, [company_event("RPL000005", "From A", server="server-A", version=1)],
              source_server="server-A")
        _push(api, [company_event("RPL000005", "From B", server="server-B", version=2)],
              source_server="server-B")

        assert CompanyModel.objects.filter(iec="RPL000005").count() == 1
        company = CompanyModel.objects.get(iec="RPL000005")
        assert company.name == "From B"
        assert company.origin_server == "server-B"

    def test_replayed_delete_is_idempotent(self, api):
        PortModel.objects.create(code="RPL006", name="Doomed", sync_version=1)
        event = sync_event("core.PortModel", "delete", {"code": "RPL006"}, version=2)

        first = _push(api, [event])
        second = _push(api, [event])

        assert first.data["applied"][0]["op"] == "delete"
        assert second.data["skipped"][0]["op"] == "noop"
        assert PortModel.objects.get(code="RPL006").is_tombstone is True
        assert MasterChange.objects.filter(
            model_label="core.PortModel", natural_key="RPL006", op="delete",
        ).count() == 1


# ── ordering / convergence ─────────────────────────────────────────────

class TestOutOfOrderConvergence:
    VERSIONS = [
        ("server-A", 1, "v1 from A"),
        ("server-B", 2, "v2 from B"),
        ("server-C", 3, "v3 from C"),
    ]

    def _apply(self, api, order, iec):
        for server, version, name in order:
            _push(api, [company_event(iec, name, server=server, version=version)],
                  source_server=server)
        return CompanyModel.objects.get(iec=iec)

    def test_in_order_delivery(self, api):
        company = self._apply(api, self.VERSIONS, "ORD000001")
        assert (company.name, company.sync_version, company.origin_server) == (
            "v3 from C", 3, "server-C",
        )

    def test_reverse_order_delivery_converges_identically(self, api):
        company = self._apply(api, list(reversed(self.VERSIONS)), "ORD000002")
        assert (company.name, company.sync_version, company.origin_server) == (
            "v3 from C", 3, "server-C",
        )

    def test_interleaved_order_delivery_converges_identically(self, api):
        order = [self.VERSIONS[1], self.VERSIONS[2], self.VERSIONS[0]]
        company = self._apply(api, order, "ORD000003")
        assert (company.name, company.sync_version, company.origin_server) == (
            "v3 from C", 3, "server-C",
        )

    def test_all_orders_agree(self, api):
        import itertools

        results = set()
        for i, order in enumerate(itertools.permutations(self.VERSIONS)):
            company = self._apply(api, list(order), f"PERM{i:06d}")
            results.add((company.name, company.sync_version, company.origin_server))

        assert results == {("v3 from C", 3, "server-C")}

    def test_a_single_batch_converges_like_sequential_delivery(self, api):
        batch = [company_event("ORD000004", name, server=server, version=version)
                 for server, version, name in reversed(self.VERSIONS)]
        response = _push(api, batch)

        assert response.status_code == 200
        company = CompanyModel.objects.get(iec="ORD000004")
        assert (company.name, company.sync_version) == ("v3 from C", 3)

    def test_late_stale_update_cannot_resurrect_old_data(self, api):
        _push(api, [company_event("ORD000005", "Current", server="server-C", version=5)])
        _push(api, [company_event("ORD000005", "Ancient", server="server-A", version=1)])

        assert CompanyModel.objects.get(iec="ORD000005").name == "Current"
        assert SyncConflictLog.objects.filter(natural_key="ORD000005").exists()

    def test_delete_then_recreate_at_a_higher_version(self, api):
        _push(api, [port_event("ORD006", "Alive", version=1)])
        _push(api, [sync_event("core.PortModel", "delete", {"code": "ORD006"}, version=2)])
        assert PortModel.objects.get(code="ORD006").is_tombstone is True

        _push(api, [port_event("ORD006", "Back", version=3)])
        port = PortModel.objects.get(code="ORD006")
        assert port.name == "Back"
        assert PortModel.objects.filter(code="ORD006").count() == 1

    def test_stale_delete_cannot_remove_newer_data(self, api):
        PortModel.objects.create(code="ORD007", name="Fresh", sync_version=9)
        response = _push(api, [
            sync_event("core.PortModel", "delete", {"code": "ORD007"}, version=2),
        ])

        assert response.status_code == 200
        assert PortModel.objects.get(code="ORD007").is_tombstone is False
        assert response.data["skipped"][0]["conflict"] is True


# ── every registered master is routable ────────────────────────────────

class TestEveryRegisteredMasterIsTransportable:
    """A master in the registry that cannot round-trip is a silent sync hole."""

    def test_all_masters_survive_a_pull(self, api):
        from apps.core.sync.registry import get_all_entries

        assert api.get(reverse(PULL)).status_code == 200
        assert len(get_all_entries()) == 20

    @pytest.mark.parametrize("label,data", [
        ("core.CompanyModel", {"iec": "TRA000001", "name": "Co"}),
        ("core.PortModel", {"code": "TRA001", "name": "Port"}),
        ("core.HSCodeModel", {"hs_code": "12345678"}),
        ("core.ItemGroupModel", {"name": "TraGroup"}),
        ("core.SchemeCode", {"code": "TRASCH"}),
        ("core.NotificationNumber", {"code": "TRANOT"}),
        ("core.ExchangeRateModel", {
            "date": "2024-05-01", "usd": "83.2500", "euro": "90.1000",
            "pound_sterling": "104.5000", "chinese_yuan": "11.4000",
        }),
        ("core.TransferLetterModel", {"name": "TraTL"}),
        ("core.UnitPriceModel", {"name": "TraUnit", "label": "kg"}),
        ("core.ItemNameModel", {"name": "TraItem"}),
    ])
    def test_master_can_be_created_over_the_wire(self, api, label, data):
        response = _push(api, [sync_event(label, "create", data)])

        assert response.status_code == 200, response.data
        assert response.data["ok"] is True, response.data["errors"]
        assert len(response.data["applied"]) == 1

    def test_fk_keyed_master_round_trips(self, api):
        """Regression: FK natural keys were filtered as surrogate pks, so these
        masters could never be created, matched or deleted through sync."""
        HSCodeModel.objects.create(hs_code="55555555", sync_version=1)

        create = _push(api, [sync_event(
            "core.ProductDescriptionModel", "create",
            {"hs_code": "55555555", "product_description": "Cotton Yarn"},
        )])
        assert create.data["ok"] is True, create.data["errors"]

        product = ProductDescriptionModel.objects.get(product_description="Cotton Yarn")
        assert product.hs_code.hs_code == "55555555"

        # A second identical event must reconcile onto the same row, not add one.
        again = _push(api, [sync_event(
            "core.ProductDescriptionModel", "update",
            {"hs_code": "55555555", "product_description": "Cotton Yarn"}, version=2,
        )])
        assert again.data["ok"] is True
        assert ProductDescriptionModel.objects.filter(
            product_description="Cotton Yarn",
        ).count() == 1

        delete = _push(api, [sync_event(
            "core.ProductDescriptionModel", "delete",
            {"hs_code": "55555555", "product_description": "Cotton Yarn"}, version=3,
        )])
        assert delete.data["ok"] is True, delete.data["errors"]
        product.refresh_from_db()
        assert product.is_tombstone is True

    def test_nullable_relational_ordering_master_round_trips(self, api):
        """Regression: ItemNameModel's ``Meta.ordering`` crosses a nullable FK,
        and Postgres refuses SELECT ... FOR UPDATE on the nullable side of the
        resulting outer join — every event for this master errored."""
        ItemGroupModel.objects.create(name="OrdGroup", sync_version=1)

        create = _push(api, [sync_event(
            "core.ItemNameModel", "create", {"name": "OrdItem", "group": "OrdGroup"},
        )])
        assert create.data["ok"] is True, create.data["errors"]

        update = _push(api, [sync_event(
            "core.ItemNameModel", "update",
            {"name": "OrdItem", "group": "OrdGroup", "display_order": 7}, version=2,
        )])
        assert update.data["ok"] is True, update.data["errors"]
        assert ItemNameModel.objects.get(name="OrdItem").display_order == 7

        delete = _push(api, [sync_event(
            "core.ItemNameModel", "delete", {"name": "OrdItem"}, version=3,
        )])
        assert delete.data["ok"] is True, delete.data["errors"]
        assert ItemNameModel.objects.get(name="OrdItem").is_tombstone is True

    def test_null_foreign_key_round_trips_as_null(self, api):
        """A parent-less child must transport as "no parent", not as a stale id."""
        ItemNameModel.objects.create(name="NoParent", group=None, sync_version=1)
        MasterChange.objects.create(
            model_label="core.ItemNameModel", natural_key="NoParent",
            op=MasterChange.OP_CREATE,
        )

        event = [e for e in api.get(reverse(PULL)).data["events"]
                 if e["model_label"] == "core.ItemNameModel"][0]
        assert event["data"]["group"] is None
        assert event["data"]["sion_norm_class"] is None

        ItemNameModel.objects.filter(name="NoParent").delete()
        response = _push(api, [{**event, "source_server": "peer-B"}], source_server="peer-B")

        assert response.data["ok"] is True, response.data["errors"]
        restored = ItemNameModel.objects.get(name="NoParent")
        assert restored.group is None
        assert restored.sion_norm_class is None

    def test_pull_then_push_round_trip_for_an_fk_master(self, api):
        """The exact bytes a peer would receive must apply on the other side."""
        head = HeadSIONNormsModel.objects.create(name="RtHead")
        SionNormClassModel.objects.create(norm_class="R1", head_norm=head, description="d")
        MasterChange.objects.create(
            model_label="core.SionNormClassModel", natural_key="R1",
            op=MasterChange.OP_CREATE,
        )

        event = [e for e in api.get(reverse(PULL)).data["events"]
                 if e["model_label"] == "core.SionNormClassModel"][0]
        assert event["data"]["head_norm"] == "RtHead"

        SionNormClassModel.objects.filter(norm_class="R1").delete()

        response = _push(api, [{**event, "source_server": "peer-B"}], source_server="peer-B")
        assert response.data["ok"] is True, response.data["errors"]

        restored = SionNormClassModel.objects.get(norm_class="R1")
        assert restored.head_norm == head
        assert restored.description == "d"


# ── delete-check hostile input ─────────────────────────────────────────

class TestDeleteCheckFailures:
    def test_incomplete_natural_key_is_400_not_500(self, api):
        """Regression: the natural-key builder raised ValueError straight out of
        the view."""
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.PortModel", "natural_key": {}},
            format="json",
        )
        assert response.status_code == 400
        assert "code" in response.data["error"]

    def test_partial_composite_natural_key_is_400(self, api):
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.ProductDescriptionModel",
             "natural_key": {"hs_code": "12345678"}},
            format="json",
        )
        assert response.status_code == 400

    def test_null_natural_key_value_is_400(self, api):
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.PortModel", "natural_key": {"code": None}},
            format="json",
        )
        assert response.status_code == 400

    def test_unexpected_natural_key_field_is_400(self, api):
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.PortModel", "natural_key": {"nonsense": "x"}},
            format="json",
        )
        assert response.status_code == 400

    def test_ambiguous_natural_key_blocks_the_delete(self, api):
        """``TransferLetterModel.name`` is the registry natural key but is not
        unique in the DB.  ``master_uid`` normally blocks duplicates, yet it is
        nullable, so legacy rows written before Module 04 (or via bulk_create,
        which skips ``save()``) can collide — an ambiguous key must never be
        answered with ``safe``."""
        from apps.core.models import TransferLetterModel

        TransferLetterModel.objects.create(name="AMBIGUOUS")
        TransferLetterModel.objects.bulk_create([TransferLetterModel(name="AMBIGUOUS")])
        assert TransferLetterModel.objects.filter(name="AMBIGUOUS").count() == 2

        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.TransferLetterModel", "natural_key": {"name": "AMBIGUOUS"}},
            format="json",
        )

        assert response.status_code == 409
        assert response.data["safe"] is False
        assert "Ambiguous" in response.data["references"][0]

    def test_corrupt_foreign_key_natural_key_is_400(self, api):
        response = api.post(
            reverse(DELETE_CHECK),
            {"model_label": "core.SIONExportModel",
             "natural_key": {"norm_class": "E1|EXTRA|PARTS", "description": "x"}},
            format="json",
        )
        assert response.status_code == 400
        assert "does not match" in response.data["error"]
