"""
Regression tests for ``update_license_ownership.authenticate()``.

Bug: the IP fallback (``http://<ip>``) and the plain-HTTP menu choice now answer
with a ``301`` redirect to HTTPS. ``requests`` rewrites a redirected POST to GET
and drops the JSON body, so the credentials never reached the server and auth
failed with a ``400 {"detail":"username & password required"}``.

``authenticate()`` now follows the redirect manually, re-issuing the POST (body
preserved), and returns the resolved HTTPS base so the later sync POSTs skip the
redirect too.
"""
from unittest import mock

import pytest

from apps.license.management.commands import update_license_ownership as cmd


class _FakeResponse:
    def __init__(self, status_code, *, headers=None, json_data=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


@pytest.mark.unit
class TestAuthenticateFollowsHttpsRedirect:
    def test_post_body_survives_301_and_resolves_https_base(self, monkeypatch):
        # Avoid the interactive getpass prompt.
        monkeypatch.setattr(cmd, "SERVER_PASSWORD", "secret")
        monkeypatch.setattr(cmd, "SERVER_USERNAME", "hardik")
        monkeypatch.setattr(cmd, "auth_token", None)

        ip_login = "http://165.232.185.220/api/auth/login/"
        https_login = "https://license-tractor.duckdns.org/api/auth/login/"
        calls = []

        def fake_post(url, **kwargs):
            calls.append((url, kwargs))
            if url == ip_login:
                return _FakeResponse(301, headers={"Location": https_login})
            if url == https_login:
                return _FakeResponse(200, json_data={"access": "jwt-token"})
            return _FakeResponse(404, text="unexpected url")

        with mock.patch.object(cmd.requests, "post", side_effect=fake_post):
            ok, resolved = cmd.authenticate("http://165.232.185.220")

        assert ok is True
        # Resolved to the HTTPS base so subsequent sync POSTs skip the redirect too.
        assert resolved == "https://license-tractor.duckdns.org"
        assert cmd.auth_token == "jwt-token"

        # Both hops were POSTs carrying the credentials — the body was NOT dropped,
        # and redirects were handled manually (allow_redirects=False on every call).
        assert len(calls) == 2
        for url, kwargs in calls:
            assert kwargs.get("json") == {"username": "hardik", "password": "secret"}
            assert kwargs.get("allow_redirects") is False

    def test_non_redirect_400_is_reported_as_failure(self, monkeypatch):
        monkeypatch.setattr(cmd, "SERVER_PASSWORD", "secret")
        monkeypatch.setattr(cmd, "auth_token", None)

        def fake_post(url, **kwargs):
            return _FakeResponse(400, text='{"detail":"username & password required"}')

        with mock.patch.object(cmd.requests, "post", side_effect=fake_post):
            ok, _resolved = cmd.authenticate("https://license-tractor.duckdns.org")

        assert ok is False
        assert cmd.auth_token is None
