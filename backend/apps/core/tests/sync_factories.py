"""
Shared helpers for the Module 04 sync **transport** tests.

The pre-existing suites (``test_master_sync.py``, ``test_three_server_runtime.py``)
exercise ``apps.core.sync.service`` in-process.  The transport layer — the DRF
API surface, the HTTP push/pull client, the media transfer worker and the Celery
entry points — is covered by:

    test_sync_api.py             — the six ``/api/sync/*`` endpoints
    test_sync_transport.py       — push.py HTTP client + tasks.py
    test_sync_media_transport.py — media.py end-to-end with real files
    test_sync_failures.py        — malformed / hostile / replayed input

Nothing here talks to a real network: ``urllib.request.urlopen`` is patched and
the peer's replies are constructed by hand.  Everything else (DB, files, DRF
routing, serializers, permissions) is real.

Contents
--------
* user / APIClient factories
* SyncPeer / SyncCursor factories
* sync-event and push-payload builders
* fake ``urlopen`` plumbing (``FakeHTTPResponse``, ``http_error``,
  ``patched_urlopen``, ``captured_requests``)
* pytest fixtures (``locmem_cache``, ``media_root``, ``api``) that test modules
  import by name
"""
from __future__ import annotations

import email.message
import io
import itertools
import json
import urllib.error
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

# ── identity ────────────────────────────────────────────────────────────

_counter = itertools.count(1)


def make_user(username: str | None = None, *, superuser: bool = True):
    """Create a user with a guaranteed-unique username/email."""
    from apps.accounts.models import User

    n = next(_counter)
    username = username or f"sync_user_{n}"
    return User.objects.create_user(
        username=username,
        email=f"{username}.{n}@example.test",
        password="sync-pass-123!",
        is_superuser=superuser,
    )


def auth_client(user=None) -> APIClient:
    """An APIClient authenticated as the registered ``server-A`` peer.

    Sync endpoints intentionally reject ordinary user credentials.  ``user`` is
    retained for call-site compatibility but is not used as a sync credential.
    """
    from django.conf import settings
    from apps.core.sync.models import SyncPeer

    token = "server-a-test-token"
    peer, _ = SyncPeer.objects.get_or_create(
        server_id="server-A", defaults={"base_url": "http://a.example.test"},
    )
    peer.set_auth_token(token)
    peer.save(update_fields=["auth_token"])
    settings.SYNC_PEER_TOKENS = {**getattr(settings, "SYNC_PEER_TOKENS", {}), "server-A": token}
    client = APIClient()
    client.credentials(
        HTTP_X_SYNC_SERVER_ID="server-A",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    return client


# ── peers ───────────────────────────────────────────────────────────────

def make_peer(
    server_id: str = "peer-B",
    *,
    base_url: str = "http://peer-b.example.test",
    auth_token: str | None = None,
    is_active: bool = True,
):
    from django.conf import settings
    from apps.core.sync.models import SyncPeer

    peer, _ = SyncPeer.objects.update_or_create(
        server_id=server_id,
        defaults={"base_url": base_url, "is_active": is_active},
    )
    if auth_token is None:
        auth_token = "server-a-test-token" if server_id == "server-A" else "peer-b-token"
    if auth_token:
        peer.set_auth_token(auth_token)
        peer.save(update_fields=["auth_token"])
        settings.SYNC_PEER_TOKENS = {
            **getattr(settings, "SYNC_PEER_TOKENS", {}), server_id: auth_token,
        }
    else:
        settings.SYNC_PEER_TOKENS = {
            key: value
            for key, value in getattr(settings, "SYNC_PEER_TOKENS", {}).items()
            if key != server_id
        }
    return peer


def make_cursor(peer, last_synced_at=None):
    from apps.core.sync.models import SyncCursor

    return SyncCursor.objects.create(peer=peer, last_synced_at=last_synced_at)


# ── event / payload builders ────────────────────────────────────────────

def sync_event(
    model_label: str,
    op: str,
    data: dict,
    *,
    server: str = "server-A",
    version: int = 1,
    media: dict | None = None,
) -> dict:
    """A single sync event in the shape the push API accepts."""
    event = {
        "model_label": model_label,
        "op": op,
        "data": data,
        "source_server": server,
        "source_version": version,
    }
    if media is not None:
        event["media"] = media
    return event


def company_event(iec, name, *, op="create", server="server-A", version=1, media=None):
    return sync_event(
        "core.CompanyModel", op, {"iec": iec, "name": name},
        server=server, version=version, media=media,
    )


def port_event(code, name, *, op="create", server="server-A", version=1):
    return sync_event(
        "core.PortModel", op, {"code": code, "name": name},
        server=server, version=version,
    )


def push_payload(events, *, source_server: str = "server-A") -> dict:
    """Wrap events in the top-level push envelope."""
    if isinstance(events, dict):
        events = [events]
    return {"source_server": source_server, "events": events}


# ── fake HTTP layer ─────────────────────────────────────────────────────

class FakeHTTPResponse:
    """Minimal stand-in for the object ``urlopen`` returns.

    ``push.py`` / ``media.py`` use it as a context manager and call ``read()``,
    so that is all this needs to support.
    """

    def __init__(self, body: bytes | str | dict = b"", status: int = 200):
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body = body
        self.status = status
        self.closed = False

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False


def json_response(payload: dict) -> FakeHTTPResponse:
    return FakeHTTPResponse(payload)


class ManagedHTTPError(urllib.error.HTTPError):
    """HTTPError fake that closes an unused in-memory response at GC time."""

    def __del__(self):  # pragma: no cover - only exercises interpreter cleanup
        self.close()


def http_error(code: int, body: bytes | str | dict = b"", url: str = "http://peer/") -> urllib.error.HTTPError:
    """A real ``HTTPError`` whose ``.read()`` returns ``body``."""
    if isinstance(body, dict):
        body = json.dumps(body)
    if isinstance(body, str):
        body = body.encode("utf-8")
    return ManagedHTTPError(
        url, code, f"HTTP {code}", email.message.Message(), io.BytesIO(body),
    )


def connection_refused() -> urllib.error.URLError:
    """What ``urlopen`` raises when the peer host refuses the connection."""
    return urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))


def read_timeout() -> TimeoutError:
    """What ``urlopen`` raises when the peer stops responding (socket.timeout)."""
    return TimeoutError("timed out")


@contextmanager
def patched_urlopen(*, response=None, responses=None, side_effect=None):
    """Patch ``urllib.request.urlopen`` and yield the mock.

    Exactly one of ``response`` / ``responses`` / ``side_effect`` is used;
    entries in ``responses``/``side_effect`` that are exceptions are raised.
    """
    kwargs = {}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    elif responses is not None:
        kwargs["side_effect"] = list(responses)
    else:
        kwargs["return_value"] = response if response is not None else FakeHTTPResponse(b"{}")

    with patch("urllib.request.urlopen", **kwargs) as mock_urlopen:
        yield mock_urlopen


def sent_requests(mock_urlopen) -> list:
    """The ``urllib.request.Request`` objects handed to the patched urlopen."""
    return [call.args[0] for call in mock_urlopen.call_args_list]


def request_headers(request) -> dict:
    """Case-insensitive view of a Request's headers."""
    return {k.lower(): v for k, v in request.headers.items()}


def sent_json(request) -> dict:
    """Decode the JSON body of a captured Request."""
    return json.loads(request.data.decode("utf-8"))


def query_of(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).query


def query_params_of(url: str) -> dict:
    """Decode a captured URL's query string the way a Django server would."""
    from urllib.parse import parse_qs, urlsplit

    return {k: v[0] for k, v in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}


# ── fixtures (imported by name into the test modules) ───────────────────

@pytest.fixture
def locmem_cache(settings):
    """Isolate DRF throttle counters from the shared Redis cache."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "sync-transport-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield cache
    cache.clear()


@pytest.fixture
def media_root(settings, tmp_path):
    """Point MEDIA_ROOT at a throwaway directory (never the real one)."""
    root = tmp_path / "media"
    root.mkdir()
    settings.MEDIA_ROOT = root
    return root


@pytest.fixture
def api(locmem_cache, db):
    """An authenticated APIClient with throttling isolated."""
    return auth_client()


def write_media(root, rel_path: str, content: bytes) -> str:
    """Write ``content`` under MEDIA_ROOT and return the relative path."""
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)
    return rel_path


def sha256_of(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()
