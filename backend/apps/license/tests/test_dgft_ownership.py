from unittest.mock import Mock

import requests

from apps.license.services.dgft_ownership import (
    DGFT_URL,
    fetch_scrip_ownership,
)


def _successful_response(status_code=200):
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.raise_for_status.return_value = None
    return response


def _fetch(**overrides):
    payload = {
        "scrip_number": "SCRIP-1",
        "scrip_issue_date": "01/01/2026",
        "iec_number": "IEC123",
        "app_id": "204000000",
        "session_id": "SESSION",
        "csrf_token": "CSRF",
    }
    payload.update(overrides)
    return fetch_scrip_ownership(**payload)


def test_fetch_scrip_ownership_posts_sanitized_payload(monkeypatch):
    response = _successful_response()
    post = Mock(return_value=response)
    monkeypatch.setattr("apps.license.services.dgft_ownership.requests.post", post)

    result = _fetch(
        scrip_number=" SCRIP-1 ",
        proxy=" http://proxy.example:8080 ",
        aws_alb=" AWSCOOKIE ",
    )

    assert result is response
    post.assert_called_once()
    _, kwargs = post.call_args
    assert post.call_args.args == (DGFT_URL,)
    assert kwargs["data"]["scripNumber"] == "SCRIP-1"
    assert kwargs["cookies"]["JSESSIONID"] == "SESSION"
    assert kwargs["cookies"]["AWSALB"] == "AWSCOOKIE"
    assert kwargs["params"]["_csrf"] == "CSRF"
    assert kwargs["proxies"] == {
        "http": "http://proxy.example:8080",
        "https": "http://proxy.example:8080",
    }


def test_fetch_scrip_ownership_uses_proxy_environment(monkeypatch):
    response = _successful_response()
    post = Mock(return_value=response)
    monkeypatch.setattr("apps.license.services.dgft_ownership.requests.post", post)
    monkeypatch.setenv("DGFT_PROXY", " socks5://127.0.0.1:1080 ")

    result = _fetch(proxy=None)

    assert result is response
    assert post.call_args.kwargs["proxies"] == {
        "http": "socks5://127.0.0.1:1080",
        "https": "socks5://127.0.0.1:1080",
    }


def test_fetch_scrip_ownership_missing_required_value_skips_network(monkeypatch):
    post = Mock()
    monkeypatch.setattr("apps.license.services.dgft_ownership.requests.post", post)

    result = _fetch(session_id="   ")

    assert result is None
    post.assert_not_called()


def test_fetch_scrip_ownership_retries_rate_limit(monkeypatch):
    rate_limited = _successful_response(status_code=429)
    success = _successful_response(status_code=200)
    post = Mock(side_effect=[rate_limited, success])
    sleep = Mock()
    monkeypatch.setattr("apps.license.services.dgft_ownership.requests.post", post)
    monkeypatch.setattr("apps.license.services.dgft_ownership.time.sleep", sleep)

    result = _fetch()

    assert result is success
    assert post.call_count == 2
    sleep.assert_called_once_with(5)


def test_fetch_scrip_ownership_returns_none_after_request_errors(monkeypatch):
    post = Mock(side_effect=requests.Timeout("timed out"))
    sleep = Mock()
    monkeypatch.setattr("apps.license.services.dgft_ownership.requests.post", post)
    monkeypatch.setattr("apps.license.services.dgft_ownership.time.sleep", sleep)

    result = _fetch()

    assert result is None
    assert post.call_count == 4
    assert sleep.call_count == 3
