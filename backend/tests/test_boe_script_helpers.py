import requests

from apps.bill_of_entry.scripts import boe


class FakeResponse:
    def __init__(self, text="", content=b"", status_code=200, content_type="text/html"):
        self.text = text
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeCookies:
    def __init__(self):
        self.values = {}

    def update(self, values):
        self.values.update(values)

    def get_dict(self):
        return dict(self.values)


class FakeSession:
    def __init__(self, get_responses=None, post_responses=None, fail_get=False, fail_post=False):
        self.cookies = FakeCookies()
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.fail_get = fail_get
        self.fail_post = fail_post
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        if self.fail_get:
            raise requests.RequestException("network down")
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        if self.fail_post:
            raise requests.RequestException("network down")
        return self.post_responses.pop(0)


def test_fetch_cookies_uses_timeout_and_handles_network_error(monkeypatch):
    session = FakeSession(fail_get=True)
    monkeypatch.setattr(boe, "create_session", lambda: session)

    cookies, csrf = boe.fetch_cookies(timeout=3)

    assert cookies == {}
    assert csrf is None
    assert session.calls[0][2]["timeout"] == 3


def test_fetch_cookies_extracts_csrf_with_stdlib_parser(monkeypatch):
    session = FakeSession(
        get_responses=[
            FakeResponse(text='<html><input name="csrfPreventionSalt" value="csrf-123"></html>')
        ]
    )
    session.cookies.update({"sid": "abc"})
    monkeypatch.setattr(boe, "create_session", lambda: session)

    cookies, csrf = boe.fetch_cookies(timeout=6)

    assert cookies == {"sid": "abc"}
    assert csrf == "csrf-123"
    assert session.calls[0][2]["timeout"] == 6


def test_fetch_captcha_rejects_non_image_response(monkeypatch):
    session = FakeSession(get_responses=[FakeResponse(text="<html>blocked</html>", content_type="text/html")])
    monkeypatch.setattr(boe, "create_session", lambda: session)

    result = boe.fetch_captcha({"sid": 123}, timeout=4)

    assert result is None
    assert session.cookies.get_dict() == {"sid": "123"}
    assert session.calls[0][2]["timeout"] == 4


def test_request_bill_of_entry_trims_payload_and_requires_values(monkeypatch):
    html = "Bill 12345 found"
    session = FakeSession(post_responses=[FakeResponse(text=html)])
    monkeypatch.setattr(boe, "create_session", lambda: session)

    found, snippet = boe.request_bill_of_entry(
        {"sid": "abc"},
        " token ",
        " port ",
        " 12345 ",
        " 2026-07-16 ",
        " captcha ",
        timeout=5,
    )

    assert found is True
    assert snippet == html
    data = session.calls[0][2]["data"]
    assert data == {
        "csrfPreventionSalt": "token",
        "beTrack_location": "port",
        "BE_NO": "12345",
        "BE_DT": "2026-07-16",
        "captchaResp": "captcha",
    }
    assert session.calls[0][2]["timeout"] == 5


def test_request_bill_of_entry_rejects_missing_values_before_network(monkeypatch):
    session = FakeSession(post_responses=[FakeResponse(text="should not be used")])
    monkeypatch.setattr(boe, "create_session", lambda: session)

    found, message = boe.request_bill_of_entry({}, "", "port", "12345", "2026-07-16", "captcha")

    assert found is False
    assert message == "missing required form values"
    assert session.calls == []


def test_be_details_parses_details_and_current_status(monkeypatch):
    session = FakeSession(
        post_responses=[
            FakeResponse(text="<table><tr><th>IEC</th><td>IEC001</td></tr><tr><th>CHA Number</th><td>CHA9</td></tr></table>"),
            FakeResponse(text="<table><tr><th>APPRAISEMENT</th><td>Complete</td></tr><tr><th>OOC DATE</th><td>16/07/2026</td></tr></table>"),
        ]
    )
    monkeypatch.setattr(boe, "create_session", lambda: session)

    result = boe.be_details({}, {"BE_NO": "123"}, timeout=7)

    assert result == {
        "iec": "IEC001",
        "cha": "CHA9",
        "appraisement": "Complete",
        "ooc_date": "16/07/2026",
    }
    assert [call[2]["timeout"] for call in session.calls] == [7, 7]
