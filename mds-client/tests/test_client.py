"""Client-level tests: pagination, ETag/304 short-circuit, bulk_upsert, meta,
change feed, and MDSUnavailable on connection error. Stdlib mocking only."""

from __future__ import annotations

import requests
from django.test import SimpleTestCase

from mds_client.client import MDSClient, MDSHTTPError, MDSUnavailable
from tests.support import FakeSession, make_response

BASE = "https://masters.test.local/api/v1/"


def client_with(handler) -> MDSClient:
    return MDSClient(base_url=BASE, token="tok", session=FakeSession(handler))


class GetMetaTests(SimpleTestCase):
    def test_get_meta_returns_high_water_mark(self):
        def handler(method, url, **kwargs):
            assert url.endswith("/companies/_meta/"), url
            return make_response(json_body={"max_modified": "2026-07-01T00:00:00Z", "count": 5, "etag": '"abc"'})

        client = client_with(handler)
        meta = client.get_meta("mirror_app.CompanyMirror")
        self.assertEqual(meta["count"], 5)
        self.assertEqual(meta["etag"], '"abc"')


class DeltaPaginationTests(SimpleTestCase):
    def test_iter_delta_follows_cursor_pages(self):
        page1 = make_response(
            json_body={
                "results": [{"iec": "A", "modified_on": "2026-07-01T00:00:00Z"}],
                "next": BASE + "companies/?cursor=p2",
            },
            headers={"ETag": '"etag1"'},
        )
        page2 = make_response(
            json_body={
                "results": [{"iec": "B", "modified_on": "2026-07-02T00:00:00Z"}],
                "next": None,
            }
        )
        seq = iter([page1, page2])

        def handler(method, url, **kwargs):
            return next(seq)

        client = client_with(handler)
        rows = list(client.iter_delta("mirror_app.CompanyMirror", since="2026-06-01T00:00:00Z"))
        self.assertEqual([r["iec"] for r in rows], ["A", "B"])

    def test_fetch_delta_sends_updated_since_param(self):
        captured = {}

        def handler(method, url, **kwargs):
            captured.update(kwargs.get("params") or {})
            return make_response(json_body={"results": [], "next": None})

        client = client_with(handler)
        client.fetch_delta("mirror_app.CompanyMirror", since="2026-06-01T00:00:00Z")
        self.assertEqual(captured.get("updated_since"), "2026-06-01T00:00:00Z")


class ETagShortCircuitTests(SimpleTestCase):
    def test_304_returns_not_modified_and_sends_if_none_match(self):
        captured = {}

        def handler(method, url, **kwargs):
            captured.update(kwargs.get("headers") or {})
            return make_response(status_code=304)

        client = client_with(handler)
        page = client.fetch_delta("mirror_app.CompanyMirror", since="x", etag='"etag1"')
        self.assertTrue(page.not_modified)
        self.assertEqual(page.results, [])
        self.assertEqual(captured.get("If-None-Match"), '"etag1"')

    def test_iter_delta_yields_nothing_on_304(self):
        def handler(method, url, **kwargs):
            return make_response(status_code=304)

        client = client_with(handler)
        rows = list(client.iter_delta("mirror_app.CompanyMirror", etag='"e"'))
        self.assertEqual(rows, [])


class BulkUpsertTests(SimpleTestCase):
    def test_bulk_upsert_posts_list_and_returns_counts(self):
        captured = {}

        def handler(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return make_response(json_body={"created": 1, "updated": 2})

        client = client_with(handler)
        result = client.bulk_upsert("mirror_app.CompanyMirror", [{"iec": "A"}, {"iec": "B"}])
        self.assertEqual(result, {"created": 1, "updated": 2})
        self.assertEqual(captured["method"], "POST")
        self.assertTrue(captured["url"].endswith("/companies/bulk_upsert/"))
        self.assertEqual(len(captured["json"]), 2)


class ChangeFeedTests(SimpleTestCase):
    def test_get_changes_walks_pages(self):
        page1 = make_response(
            json_body={
                "results": [{"model_label": "mirror_app.CompanyMirror", "natural_key": "A", "op": "delete", "at": "2026-07-01T00:00:00Z"}],
                "next": BASE + "changes/?cursor=p2",
            }
        )
        page2 = make_response(
            json_body={
                "results": [{"model_label": "mirror_app.PortMirror", "natural_key": "P1", "op": "update", "at": "2026-07-02T00:00:00Z"}],
                "next": None,
            }
        )
        seq = iter([page1, page2])

        def handler(method, url, **kwargs):
            return next(seq)

        client = client_with(handler)
        changes = client.get_changes(since="2026-06-01T00:00:00Z")
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]["op"], "delete")


class FailureModeTests(SimpleTestCase):
    def test_connection_error_raises_mds_unavailable(self):
        def handler(method, url, **kwargs):
            return requests.ConnectionError("connection refused")

        client = client_with(handler)
        with self.assertRaises(MDSUnavailable):
            client.get_meta("mirror_app.CompanyMirror")

    def test_timeout_raises_mds_unavailable(self):
        def handler(method, url, **kwargs):
            return requests.Timeout("read timed out")

        client = client_with(handler)
        with self.assertRaises(MDSUnavailable):
            client.fetch_delta("mirror_app.CompanyMirror")

    def test_http_500_raises_mds_http_error(self):
        def handler(method, url, **kwargs):
            return make_response(status_code=500, json_body={"detail": "boom"})

        client = client_with(handler)
        with self.assertRaises(MDSHTTPError) as ctx:
            client.get_meta("mirror_app.CompanyMirror")
        self.assertEqual(ctx.exception.status_code, 500)

    def test_auth_header_is_set_on_session(self):
        # Real session build path (no injected session) sets the bearer token.
        client = MDSClient(base_url=BASE, token="secret-token")
        self.assertEqual(client.session.headers["Authorization"], "Bearer secret-token")
        client.close()
