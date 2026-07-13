"""Shared test helpers: build fake ``requests.Response`` objects and a fake
Session so tests never touch the network (stdlib ``unittest.mock`` only)."""

from __future__ import annotations

import json

import requests


def make_response(
    status_code: int = 200,
    json_body=None,
    headers: dict | None = None,
    url: str = "https://masters.test.local/api/v1/",
) -> requests.Response:
    """Construct a real requests.Response with the given status/body/headers."""
    resp = requests.Response()
    resp.status_code = status_code
    resp.url = url
    if headers:
        resp.headers.update(headers)
    if json_body is not None:
        resp._content = json.dumps(json_body).encode("utf-8")
        resp.headers.setdefault("Content-Type", "application/json")
    else:
        resp._content = b""
    return resp


class FakeSession:
    """Stands in for requests.Session.

    ``handler`` is a callable ``(method, url, **kwargs) -> requests.Response`` OR
    a raised exception. Every call is recorded in ``self.calls`` for assertions.
    """

    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.headers = {}
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        result = self.handler(method, url, **kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    def mount(self, *a, **k):
        pass

    def close(self):
        self.closed = True
