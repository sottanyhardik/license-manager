"""
End-to-end fixtures.

Both the Django backend (default http://localhost:8000) and the Vite frontend
(default http://localhost:5173) must be running. These tests hit live servers —
they do NOT spin up a Django test DB, so they catch the kind of bugs that
unit tests can miss: real ORM queries against real data, real React renders.

Override the URLs / credentials with environment variables:

    LM_BACKEND_URL=http://localhost:8000
    LM_FRONTEND_URL=http://localhost:5173
    LM_USERNAME=hardik
    LM_PASSWORD=admin@123
Managed production gate
-----------------------
Set ``LM_E2E_MANAGED=1`` to own the Django, Celery, and production-frontend
processes. Managed mode fails closed if the isolated database, Redis namespace,
or repository seed hook is absent; it never falls back to shared credentials
or a development database.
"""
from __future__ import annotations

import os
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIRECTORY = REPOSITORY_ROOT / "backend"
FRONTEND_DIRECTORY = REPOSITORY_ROOT / "frontend"
MANAGED_MODE = os.environ.get("LM_E2E_MANAGED") == "1"
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


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen, label: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{label} exited early with status {process.returncode}")
        if _is_listening(url):
            return
        time.sleep(0.2)
    raise RuntimeError(f"{label} did not listen at {url} within 45 seconds")


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture(scope="session")
def e2e_runtime():
    """Start the isolated real-process stack when LM_E2E_MANAGED=1.

    Required managed inputs deliberately prove that writes target disposable
    test resources: LM_E2E_DB_NAME starts with ``test_``, Redis uses a
    non-zero namespace, and LM_E2E_SEED_COMMAND creates the canonical data.
    """
    if not MANAGED_MODE:
        yield {"backend_url": BACKEND_URL, "frontend_url": FRONTEND_URL}
        return

    db_name = os.environ.get("LM_E2E_DB_NAME", "")
    redis_url = os.environ.get("LM_E2E_REDIS_URL", "")
    seed_command = os.environ.get("LM_E2E_SEED_COMMAND", "")
    if not db_name.startswith("test_") or len(db_name) <= len("test_"):
        pytest.fail("Managed E2E requires disposable LM_E2E_DB_NAME beginning with 'test_'.")
    if not redis_url or redis_url.rstrip("/").endswith("/0"):
        pytest.fail("Managed E2E requires LM_E2E_REDIS_URL on an isolated non-zero Redis DB.")
    if not seed_command:
        pytest.fail("Managed E2E requires LM_E2E_SEED_COMMAND for the canonical scenario.")
    if not (BACKEND_DIRECTORY / "manage.py").is_file() or not (FRONTEND_DIRECTORY / "package.json").is_file():
        pytest.fail("Managed E2E repository layout is incomplete.")

    backend_port = _free_local_port()
    frontend_port = _free_local_port()
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    backend_env = os.environ.copy()
    backend_env.update({
        "DB_NAME": db_name,
        "REDIS_URL": redis_url,
        "DEBUG": "true",
        "CORS_ALLOWED_ORIGINS": frontend_url,
        "CSRF_TRUSTED_ORIGINS": frontend_url,
        "PYTHONUNBUFFERED": "1",
    })
    python = os.environ.get("LM_E2E_PYTHON", sys.executable)
    processes: list[subprocess.Popen] = []
    try:
        subprocess.run([python, "manage.py", "migrate", "--noinput"], cwd=BACKEND_DIRECTORY, env=backend_env, check=True)
        backend = subprocess.Popen(
            [python, "manage.py", "runserver", f"127.0.0.1:{backend_port}", "--noreload"],
            cwd=BACKEND_DIRECTORY, env=backend_env,
        )
        processes.append(backend)
        _wait_for_server(backend_url, backend, "Django E2E server")

        # The seed command belongs to the repository and must create the
        # canonical licence/user graph before the real worker starts.
        import shlex
        subprocess.run(shlex.split(seed_command), cwd=REPOSITORY_ROOT, env=backend_env, check=True)

        worker = subprocess.Popen(
            [python, "-m", "celery", "-A", "lmanagement", "worker", "--pool=solo", "--loglevel=WARNING"],
            cwd=BACKEND_DIRECTORY, env=backend_env,
        )
        processes.append(worker)

        frontend_env = os.environ.copy()
        frontend_env["VITE_API_URL"] = backend_url
        subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIRECTORY, env=frontend_env, check=True)
        frontend = subprocess.Popen(
            ["npm", "run", "preview", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            cwd=FRONTEND_DIRECTORY, env=frontend_env,
        )
        processes.append(frontend)
        _wait_for_server(frontend_url, frontend, "production frontend preview")
        yield {"backend_url": backend_url, "frontend_url": frontend_url}
    finally:
        for process in reversed(processes):
            _stop_process(process)


@pytest.fixture(scope="session")
def backend_url(e2e_runtime) -> str:
    url = e2e_runtime["backend_url"]
    if not _is_listening(url):
        if MANAGED_MODE:
            pytest.fail(f"Managed Django E2E server is not reachable at {url}.")
        pytest.skip(f"Backend not reachable at {BACKEND_URL} — start `python manage.py runserver`.")
    return url


@pytest.fixture(scope="session")
def frontend_url(e2e_runtime) -> str:
    url = e2e_runtime["frontend_url"]
    if not _is_listening(url):
        if MANAGED_MODE:
            pytest.fail(f"Managed production frontend is not reachable at {url}.")
        pytest.skip(f"Frontend not reachable at {FRONTEND_URL} — start `npm run dev`.")
    return url


@pytest.fixture(scope="session")
def e2e_credentials() -> dict:
    return {"username": USERNAME, "password": PASSWORD}


@pytest.fixture(scope="session")
def jwt_token(backend_url: str, e2e_credentials: dict) -> str:
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json=e2e_credentials,
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
        if MANAGED_MODE:
            pytest.fail("Managed E2E requires Selenium; install tests/e2e/requirements.txt.")
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
def _spa_auth_payload(backend_url: str, e2e_credentials: dict) -> dict:
    """One login per pytest session. The login endpoint is throttled at
    10/minute; doing it once and reusing the tokens keeps every test under
    the limit even when the full suite runs back-to-back."""
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json=e2e_credentials,
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
        json.dumps(_spa_auth_payload.get("user", {})),
    )
    return selenium_driver
