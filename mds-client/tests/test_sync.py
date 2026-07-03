"""Sync-level tests: mirror upsert by natural key, cursor advance, ETag 304
short-circuit, change-feed delete application, and write_master degradation."""

from __future__ import annotations

import requests
from django.test import TestCase

from mds_client.client import MDSClient, MDSUnavailable
from mds_client.models import MDSSyncState
from mds_client.sync import sync_all, sync_model, write_master
from tests.mirror_app.models import CompanyMirror, PortMirror
from tests.support import FakeSession, make_response

BASE = "https://masters.test.local/api/v1/"
COMPANY = "mirror_app.CompanyMirror"


def client_with(handler) -> MDSClient:
    return MDSClient(base_url=BASE, token="tok", session=FakeSession(handler))


class ScriptedHandler:
    """Route requests by URL substring to canned responses. ``changes`` returns
    an empty page unless overridden, so delta tests don't need to model it."""

    def __init__(self, delta_pages=None, changes=None):
        self.delta_pages = iter(delta_pages or [])
        self.changes = changes if changes is not None else []

    def __call__(self, method, url, **kwargs):
        if "/changes/" in url:
            return make_response(json_body={"results": self.changes, "next": None})
        if "/_meta/" in url:
            return make_response(json_body={"max_modified": None, "count": 0, "etag": '"m"'})
        # a delta list request
        try:
            return next(self.delta_pages)
        except StopIteration:  # pragma: no cover - safety
            return make_response(json_body={"results": [], "next": None})


class MirrorUpsertTests(TestCase):
    def test_delta_pull_upserts_by_natural_key(self):
        pages = [
            make_response(
                json_body={
                    "results": [
                        {"iec": "AAA", "name": "Acme", "modified_on": "2026-07-01T10:00:00Z"},
                        {"iec": "BBB", "name": "Beta", "modified_on": "2026-07-02T10:00:00Z"},
                    ],
                    "next": None,
                },
                headers={"ETag": '"etag-v1"'},
            )
        ]
        client = client_with(ScriptedHandler(delta_pages=pages))
        result = sync_model(COMPANY, client=client)

        self.assertEqual(result.created, 2)
        self.assertEqual(CompanyMirror.objects.count(), 2)
        self.assertEqual(CompanyMirror.objects.get(iec="AAA").name, "Acme")

        # cursor advanced to the max modified_on; etag stored.
        state = MDSSyncState.objects.get(model_label=COMPANY)
        self.assertEqual(state.cursor, "2026-07-02T10:00:00Z")
        self.assertEqual(state.etag, '"etag-v1"')

    def test_second_pull_updates_existing_row(self):
        CompanyMirror.objects.create(iec="AAA", name="Old")
        pages = [
            make_response(
                json_body={
                    "results": [{"iec": "AAA", "name": "New", "modified_on": "2026-07-03T10:00:00Z"}],
                    "next": None,
                }
            )
        ]
        client = client_with(ScriptedHandler(delta_pages=pages))
        result = sync_model(COMPANY, client=client)

        self.assertEqual(result.updated, 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(CompanyMirror.objects.get(iec="AAA").name, "New")
        self.assertEqual(CompanyMirror.objects.count(), 1)

    def test_unknown_fields_are_ignored(self):
        # MDS may serialize fields the mirror doesn't have (e.g. logo/signature).
        pages = [
            make_response(
                json_body={
                    "results": [{"iec": "AAA", "name": "Acme", "logo": "s3://x", "id": 999, "modified_on": "2026-07-01T10:00:00Z"}],
                    "next": None,
                }
            )
        ]
        client = client_with(ScriptedHandler(delta_pages=pages))
        sync_model(COMPANY, client=client)
        row = CompanyMirror.objects.get(iec="AAA")
        self.assertEqual(row.name, "Acme")
        # MDS's id must NOT have been written onto the local PK.
        self.assertNotEqual(row.pk, 999)


class KeylessFKResolutionTests(TestCase):
    """The keyless-master case: MDS serialises the FK as the parent's NATURAL
    KEY, and the mirror must resolve it to the LOCAL parent id (ids diverge)."""

    LABEL = "mirror_app.SionExportMirror"

    def test_fk_resolved_by_parent_natural_key_not_id(self):
        from tests.mirror_app.models import NormClassMirror, SionExportMirror

        # Local parent has a DIFFERENT id than MDS would (simulate divergence by
        # giving it a specific pk); the row references it only by natural key.
        parent = NormClassMirror.objects.create(norm_class="E1")
        uid = "e3c8c2a2-59da-5414-9faf-07eca387ae81"
        pages = [
            make_response(json_body={
                "results": [{
                    "uid": uid, "norm_class": "E1", "description": "cloth",
                    "id": 9999,  # MDS's id — must be ignored
                    "modified_on": "2026-07-03T10:00:00Z",
                }],
                "next": None,
            })
        ]
        client = client_with(ScriptedHandler(delta_pages=pages))
        result = sync_model(self.LABEL, client=client)

        self.assertEqual(result.created, 1)
        row = SionExportMirror.objects.get(uid=uid)
        # FK points at the LOCAL parent, resolved by natural key — not MDS's id.
        self.assertEqual(row.norm_class_id, parent.pk)
        self.assertEqual(row.description, "cloth")
        self.assertNotEqual(row.pk, 9999)

    def test_missing_parent_is_skipped_not_wrongly_linked(self):
        from tests.mirror_app.models import SionExportMirror

        # No parent with norm_class="ZZ" exists -> required FK unresolved ->
        # the row is skipped (IntegrityError rolled back), never linked wrongly.
        pages = [
            make_response(json_body={
                "results": [{
                    "uid": "11111111-1111-5111-8111-111111111111",
                    "norm_class": "ZZ", "description": "orphan",
                    "modified_on": "2026-07-03T10:00:00Z",
                }],
                "next": None,
            })
        ]
        client = client_with(ScriptedHandler(delta_pages=pages))
        with self.assertRaises(Exception):
            sync_model(self.LABEL, client=client)
        self.assertEqual(SionExportMirror.objects.count(), 0)


class ETagShortCircuitSyncTests(TestCase):
    def test_304_skips_upsert_but_still_applies_deletes(self):
        # Seed one row + prior state so we send If-None-Match.
        CompanyMirror.objects.create(iec="GONE", name="ToDelete")
        MDSSyncState.objects.create(model_label=COMPANY, cursor="2026-07-01T00:00:00Z", etag='"cur"')

        def handler(method, url, **kwargs):
            if "/changes/" in url:
                return make_response(
                    json_body={
                        "results": [
                            {"model_label": COMPANY, "natural_key": "GONE", "op": "delete", "at": "2026-07-05T00:00:00Z"}
                        ],
                        "next": None,
                    }
                )
            return make_response(status_code=304)  # collection unchanged

        client = client_with(handler)
        result = sync_model(COMPANY, client=client)

        self.assertTrue(result.skipped_unchanged)
        self.assertEqual(result.deleted, 1)
        self.assertFalse(CompanyMirror.objects.filter(iec="GONE").exists())
        state = MDSSyncState.objects.get(model_label=COMPANY)
        self.assertEqual(state.changes_cursor, "2026-07-05T00:00:00Z")


class ChangeFeedDeleteTests(TestCase):
    def test_delete_from_change_feed_removes_mirror_row(self):
        CompanyMirror.objects.create(iec="AAA", name="Acme")
        pages = [make_response(json_body={"results": [], "next": None})]
        changes = [
            {"model_label": COMPANY, "natural_key": "AAA", "op": "delete", "at": "2026-07-04T00:00:00Z"},
            # a change for another model must be ignored here.
            {"model_label": "mirror_app.PortMirror", "natural_key": "P1", "op": "delete", "at": "2026-07-04T01:00:00Z"},
        ]
        client = client_with(ScriptedHandler(delta_pages=pages, changes=changes))
        result = sync_model(COMPANY, client=client)

        self.assertEqual(result.deleted, 1)
        self.assertFalse(CompanyMirror.objects.filter(iec="AAA").exists())


class SyncAllTests(TestCase):
    def test_sync_all_covers_every_configured_model(self):
        def handler(method, url, **kwargs):
            if "/changes/" in url:
                return make_response(json_body={"results": [], "next": None})
            if "companies" in url:
                return make_response(json_body={"results": [{"iec": "AAA", "name": "Acme", "modified_on": "2026-07-01T00:00:00Z"}], "next": None})
            if "ports" in url:
                return make_response(json_body={"results": [{"code": "INBOM", "name": "Mumbai", "modified_on": "2026-07-01T00:00:00Z"}], "next": None})
            return make_response(json_body={"results": [], "next": None})

        client = client_with(handler)
        results = sync_all(client=client)
        labels = {r.model_label for r in results}
        self.assertIn(COMPANY, labels)
        self.assertIn("mirror_app.PortMirror", labels)
        self.assertEqual(CompanyMirror.objects.count(), 1)
        self.assertEqual(PortMirror.objects.count(), 1)


class WriteMasterTests(TestCase):
    def test_write_master_calls_bulk_upsert(self):
        captured = {}

        def handler(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return make_response(json_body={"created": 1, "updated": 0})

        client = client_with(handler)
        result = write_master(COMPANY, {"iec": "AAA", "name": "Acme"}, client=client)
        self.assertEqual(result, {"created": 1, "updated": 0})
        self.assertEqual(captured["method"], "POST")
        self.assertTrue(captured["url"].endswith("/companies/bulk_upsert/"))
        self.assertEqual(captured["json"], [{"iec": "AAA", "name": "Acme"}])

    def test_write_master_raises_clear_error_when_mds_down(self):
        def handler(method, url, **kwargs):
            return requests.ConnectionError("refused")

        client = client_with(handler)
        with self.assertRaises(MDSUnavailable) as ctx:
            write_master(COMPANY, {"iec": "AAA"}, client=client)
        self.assertIn("read-only", str(ctx.exception).lower())
