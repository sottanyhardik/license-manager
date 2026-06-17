"""
End-to-end smoke-test fixtures.

Both the Django backend (default http://localhost:8000) and the Vite frontend
(default http://localhost:5173) must be running. These tests hit live servers —
they do NOT spin up a Django test DB, so they catch the kind of bugs that
unit tests can miss: real ORM queries against real data, real React renders.

Override the URLs / credentials with environment variables:

    LM_BACKEND_URL=http://localhost:8000
    LM_FRONTEND_URL=http://localhost:5173
    LM_USERNAME=hardik
    LM_PASSWORD=admin@123
"""
from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import pytest
import requests


BACKEND_URL = os.environ.get("LM_BACKEND_URL", "http://localhost:8000").rstrip("/")
FRONTEND_URL = os.environ.get("LM_FRONTEND_URL", "http://localhost:5173").rstrip("/")
USERNAME = os.environ.get("LM_USERNAME", "hardik")
PASSWORD = os.environ.get("LM_PASSWORD", "admin@123")


def _is_listening(url: str) -> bool:
    p = urlparse(url)
    host = p.hostname or "localhost"
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def backend_url() -> str:
    if not _is_listening(BACKEND_URL):
        pytest.skip(f"Backend not reachable at {BACKEND_URL} — start `python manage.py runserver`.")
    return BACKEND_URL


@pytest.fixture(scope="session")
def frontend_url() -> str:
    if not _is_listening(FRONTEND_URL):
        pytest.skip(f"Frontend not reachable at {FRONTEND_URL} — start `npm run dev`.")
    return FRONTEND_URL


@pytest.fixture(scope="session")
def jwt_token(backend_url: str) -> str:
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    return r.json()["access"]


@pytest.fixture(scope="session")
def auth_headers(jwt_token: str) -> dict:
    return {"Authorization": f"Bearer {jwt_token}"}


@pytest.fixture(scope="session")
def api_get(backend_url: str, auth_headers: dict):
    def _get(path: str, **kwargs):
        url = path if path.startswith("http") else f"{backend_url}/api/{path.lstrip('/')}"
        return requests.get(url, headers=auth_headers, timeout=30, **kwargs)
    return _get


# ---------------------------------------------------------------------------
# Selenium driver — session-scoped, headless Chrome.
# Selenium 4 ships with selenium-manager, which auto-downloads the right driver.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def selenium_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        pytest.skip("selenium not installed — `pip install -r tests/e2e/requirements.txt`")

    opts = Options()
    if os.environ.get("LM_HEADLESS", "1") != "0":
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    # Silence Chrome's "DevTools listening" noise.
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture(scope="session")
def _spa_auth_payload(backend_url: str) -> dict:
    """One login per pytest session. The login endpoint is throttled at
    10/minute; doing it once and reusing the tokens keeps every test under
    the limit even when the full suite runs back-to-back."""
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()


@pytest.fixture
def logged_in_driver(selenium_driver, frontend_url: str, _spa_auth_payload: dict):
    """Inject the JWT tokens into localStorage so the SPA treats us as authenticated.

    Function-scoped on purpose: if any test triggers a 401 the axios interceptor
    calls `localStorage.clear()` and redirects to /login, which would silently
    break every subsequent test sharing a session-scoped driver. Re-injecting
    per test keeps each test independent without hitting the login throttle —
    we re-use the same cached tokens from `_spa_auth_payload`.

    The login-form path is exercised separately by test_login_page().
    """
    # Hit the frontend once to establish origin for localStorage.
    selenium_driver.get(frontend_url + "/login")
    selenium_driver.execute_script(
        "localStorage.clear();"
        "localStorage.setItem('access', arguments[0]);"
        "localStorage.setItem('refresh', arguments[1]);"
        "localStorage.setItem('user', arguments[2]);",
        _spa_auth_payload["access"],
        _spa_auth_payload["refresh"],
        __import__("json").dumps(_spa_auth_payload.get("user", {})),
    )
    return selenium_driver
