from types import SimpleNamespace

from django.test import override_settings

from apps.license.management.commands.update_license_ownership import (
    fetch_and_update_ownership,
    get_dgft_ownership_credentials,
)


@override_settings(
    DGFT_APP_ID="", DGFT_SESSION_ID="", DGFT_CSRF_TOKEN="", DGFT_AWSALB=""
)
def test_dgft_ownership_credentials_have_no_committed_fallbacks(monkeypatch):
    """Ownership fetches must fail safely instead of using committed sessions."""
    for name in (
        "DGFT_APP_ID",
        "DGFT_SESSION_ID",
        "DGFT_CSRF_TOKEN",
        "DGFT_AWSALB",
    ):
        monkeypatch.delenv(name, raising=False)

    assert get_dgft_ownership_credentials() == (None, None, None, None)


def test_dgft_ownership_credentials_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("DGFT_APP_ID", "  application-id  ")
    monkeypatch.setenv("DGFT_SESSION_ID", " session-id ")
    monkeypatch.setenv("DGFT_CSRF_TOKEN", " csrf-token ")
    monkeypatch.setenv("DGFT_AWSALB", " alb-cookie ")

    assert get_dgft_ownership_credentials() == (
        "application-id",
        "session-id",
        "csrf-token",
        "alb-cookie",
    )


@override_settings(
    DGFT_APP_ID="settings-app-id",
    DGFT_SESSION_ID="settings-session-id",
    DGFT_CSRF_TOKEN="settings-csrf-token",
    DGFT_AWSALB="settings-alb-cookie",
)
def test_dgft_ownership_credentials_fall_back_to_loaded_settings(monkeypatch):
    for name in (
        "DGFT_APP_ID",
        "DGFT_SESSION_ID",
        "DGFT_CSRF_TOKEN",
        "DGFT_AWSALB",
    ):
        monkeypatch.delenv(name, raising=False)

    assert get_dgft_ownership_credentials() == (
        "settings-app-id",
        "settings-session-id",
        "settings-csrf-token",
        "settings-alb-cookie",
    )


@override_settings(DGFT_APP_ID="", DGFT_SESSION_ID="", DGFT_CSRF_TOKEN="")
def test_missing_dgft_ownership_credentials_fail_before_network_access(monkeypatch):
    for name in ("DGFT_APP_ID", "DGFT_SESSION_ID", "DGFT_CSRF_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    result = fetch_and_update_ownership(
        SimpleNamespace(exporter=None),
        default_iec="IEC123",
    )

    assert result == (
        False,
        None,
        "DGFT ownership credentials are not configured. Set DGFT_APP_ID, "
        "DGFT_SESSION_ID, and DGFT_CSRF_TOKEN.",
    )
