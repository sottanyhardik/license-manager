"""
REST client for the Master-Data Service.

``MDSClient`` wraps a ``requests.Session`` (connection pooling + urllib3 retry on
idempotent verbs) and exposes exactly the endpoints the sync worker and write
path need:

    get_meta(model)                         -> {"max_modified", "count", "etag"}
    fetch_delta(model, since=None, etag=None) -> DeltaPage(results, next_url, etag, not_modified)
    bulk_upsert(model, rows)                -> {"created", "updated"}
    get_changes(since=None)                 -> list[change dicts]  (create/update/delete)

Failure model (explicit — see ADR-001 Decision 3 degradation contract):
- Connection errors / timeouts  -> ``MDSUnavailable`` (writes should fail loudly;
  reads keep serving from the local mirror, which never touches this client).
- HTTP 4xx/5xx after retries     -> ``MDSError`` carrying status + body.
- HTTP 304 on a conditional GET  -> not an error; surfaced as ``not_modified``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 is a hard dep of requests; import path differs across versions.
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - defensive
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

from . import settings as mds_settings


# --- exceptions -------------------------------------------------------------
class MDSError(Exception):
    """Base error for all MDS client problems."""


class MDSUnavailable(MDSError):
    """MDS could not be reached (connection refused, DNS, timeout, retries exhausted).

    Callers on the WRITE path should treat this as 'central service is down':
    fail loudly with a user-facing message (or enqueue to an outbox). Callers on
    the READ path never see this because reads come from the local mirror.
    """


class MDSHTTPError(MDSError):
    """MDS returned a non-2xx status. Carries the status code and response body."""

    def __init__(self, status_code: int, body: Any, url: str):
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(f"MDS returned HTTP {status_code} for {url}: {body!r}")


# --- delta page -------------------------------------------------------------
@dataclass
class DeltaPage:
    """One page of a delta pull.

    ``results``      : the list of master rows (raw dicts as MDS serialized them).
    ``next_url``     : absolute URL of the next cursor page, or None if last page.
    ``etag``         : the collection ETag from this response (for If-None-Match next time).
    ``not_modified`` : True when MDS answered 304 (nothing changed since ``etag``).
    """

    results: list = field(default_factory=list)
    next_url: str | None = None
    etag: str | None = None
    not_modified: bool = False


class MDSClient:
    """Thin, reusable REST client. Instantiate once per process / per task run.

    Reads config from Django settings by default; explicit args override (handy
    for tests). All network calls funnel through ``_request`` so timeout, auth,
    retry, and error mapping are defined in exactly one place.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        timeout=None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or mds_settings.get_base_url()).rstrip("/") + "/"
        self.token = token or mds_settings.get_token()
        self.timeout = timeout if timeout is not None else mds_settings.get_timeout()
        max_retries = max_retries if max_retries is not None else mds_settings.get_max_retries()
        backoff_factor = (
            backoff_factor if backoff_factor is not None else mds_settings.get_backoff_factor()
        )
        self.session = session or self._build_session(max_retries, backoff_factor)

    # -- session / transport ------------------------------------------------
    def _build_session(self, max_retries: int, backoff_factor: float) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )
        # Retry only idempotent verbs on transient network/5xx; POST is NOT
        # retried automatically to avoid duplicate bulk_upsert side effects
        # (bulk_upsert is natural-key idempotent on MDS, but we stay explicit).
        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _url(self, path: str) -> str:
        """Resolve a relative path against the API base (base already has a slash)."""
        return urljoin(self.base_url, path.lstrip("/"))

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Single choke point: applies timeout, maps connection failures to
        MDSUnavailable, and raises MDSHTTPError on non-2xx (except 304)."""
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self.session.request(method, url, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise MDSUnavailable(f"Could not reach MDS at {url}: {exc}") from exc
        except requests.RequestException as exc:  # pragma: no cover - defensive
            raise MDSError(f"Unexpected error calling MDS at {url}: {exc}") from exc

        if resp.status_code == 304:
            return resp
        if not (200 <= resp.status_code < 300):
            body = self._safe_body(resp)
            raise MDSHTTPError(resp.status_code, body, url)
        return resp

    @staticmethod
    def _safe_body(resp: requests.Response):
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # -- endpoints ----------------------------------------------------------
    def _endpoint_for(self, model: str) -> str:
        """Map a model_label (or a raw endpoint segment) to its URL segment."""
        models = mds_settings.get_models()
        cfg = models.get(model)
        if cfg is not None:
            return cfg["endpoint"]
        # Allow passing a raw endpoint segment (e.g. "companies") directly.
        return model

    def get_meta(self, model: str) -> dict:
        """GET /<endpoint>/_meta/ -> {max_modified, count, etag}. One tiny request
        to decide whether a full delta pull is even needed."""
        endpoint = self._endpoint_for(model)
        resp = self._request("GET", self._url(f"{endpoint}/_meta/"))
        return resp.json()

    def fetch_delta(self, model: str, since: str | None = None, etag: str | None = None) -> DeltaPage:
        """GET /<endpoint>/?updated_since=<since> with optional If-None-Match.

        Returns a single page. When ``etag`` is supplied and the collection is
        unchanged, MDS answers 304 and we short-circuit with
        ``DeltaPage(not_modified=True)`` — no rows transferred.
        """
        endpoint = self._endpoint_for(model)
        params = {}
        if since:
            params["updated_since"] = since
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        resp = self._request("GET", self._url(f"{endpoint}/"), params=params, headers=headers)
        if resp.status_code == 304:
            return DeltaPage(not_modified=True, etag=etag)
        return self._page_from_response(resp)

    def fetch_delta_url(self, url: str) -> DeltaPage:
        """Follow an absolute cursor ``next`` URL from a previous page. Auth and
        timeout still apply via the shared session."""
        resp = self._request("GET", url)
        return self._page_from_response(resp)

    def iter_delta(self, model: str, since: str | None = None, etag: str | None = None):
        """Generator yielding every row across all cursor pages of a delta pull.

        Handles the 304 short-circuit (yields nothing) and follows ``next``
        cursor links until exhausted.
        """
        page = self.fetch_delta(model, since=since, etag=etag)
        if page.not_modified:
            return
        for row in page.results:
            yield row
        while page.next_url:
            page = self.fetch_delta_url(page.next_url)
            for row in page.results:
                yield row

    def bulk_upsert(self, model: str, rows: list) -> dict:
        """POST /<endpoint>/bulk_upsert/ with a list of natural-key-keyed rows.
        Returns {created, updated}. Not auto-retried (see _build_session)."""
        endpoint = self._endpoint_for(model)
        resp = self._request("POST", self._url(f"{endpoint}/bulk_upsert/"), json=rows)
        return resp.json()

    def get_changes(self, since: str | None = None) -> list:
        """GET /changes/?since=<since> -> the change feed (create/update/delete).

        Cursor-paginated like the masters; this walks all pages and returns the
        flat list of change dicts in ``at`` order.
        """
        params = {}
        if since:
            params["since"] = since
        resp = self._request("GET", self._url("changes/"), params=params)
        page = self._page_from_response(resp)
        changes = list(page.results)
        while page.next_url:
            page = self.fetch_delta_url(page.next_url)
            changes.extend(page.results)
        return changes

    # -- response parsing ---------------------------------------------------
    @staticmethod
    def _page_from_response(resp: requests.Response) -> DeltaPage:
        etag = resp.headers.get("ETag")
        payload = resp.json()
        if isinstance(payload, dict):
            results = payload.get("results", [])
            next_url = payload.get("next")
        else:  # a bare list (non-paginated) — tolerate it
            results = payload
            next_url = None
        return DeltaPage(results=results, next_url=next_url, etag=etag)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
