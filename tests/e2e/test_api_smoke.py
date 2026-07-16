"""
API smoke tests.

Hit every endpoint that has historically broken when fields were moved between
LicenseDetailsModel and its OneToOne sub-tables (LicenseBalance / LicenseFlags /
LicenseNotes / LicenseOwnership), and every filter that touches a moved field.

A failure here means real users see a 500. Keep this list in sync as new
endpoints are added.
"""
from __future__ import annotations

import pytest


# ---------- auth ----------
def test_login_returns_token(backend_url, e2e_credentials):
    import requests
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json=e2e_credentials,
        timeout=10,
        # Plain HTTP only — fails closed if SECURE_SSL_REDIRECT is left on
        # against DEBUG=False with no HTTPS proxy in front.
        allow_redirects=False,
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "access" in body and "refresh" in body and "user" in body


def test_login_no_redirect_in_dev(backend_url, e2e_credentials):
    """If DEBUG=True locally, the login endpoint must NOT 301 to HTTPS."""
    import requests
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json=e2e_credentials,
        timeout=10,
        allow_redirects=False,
    )
    assert r.status_code != 301, "SECURE_SSL_REDIRECT is leaking — check DEBUG env var"


# ---------- dashboard / masters ----------
def test_dashboard(api_get):
    r = api_get("dashboard/")
    assert r.status_code == 200, r.text[:200]


def test_masters_companies(api_get):
    r = api_get("masters/companies/?page_size=3")
    assert r.status_code == 200, r.text[:200]


def test_masters_sion_classes_active(api_get):
    r = api_get("masters/sion-classes/?is_active=true&page_size=3")
    assert r.status_code == 200, r.text[:200]


# ---------- license CRUD + the filters that broke on the sub-table split ----------
@pytest.mark.parametrize(
    "qs",
    [
        "page_size=3",
        "is_active=true&page_size=3",       # LicenseFlags.is_active
        "is_expired=false&page_size=3",     # LicenseFlags.is_expired
        "status=active&page_size=3",        # filter_by_status
        "status=expiring_soon&page_size=3", # filter_by_status (was bare is_active=True)
        "status=expired&page_size=3",
        "balance_cif_min=100&page_size=3",  # LicenseBalance.balance_cif
        "balance_cif_max=999999999&page_size=3",
        "has_balance=true&page_size=3",     # filter_has_balance
    ],
)
def test_licenses_list_filters(api_get, qs):
    r = api_get(f"licenses/?{qs}")
    assert r.status_code == 200, f"licenses/?{qs} -> {r.status_code}: {r.text[:200]}"


def test_license_detail_serializes_moved_fields(api_get):
    """Detail GET must round-trip the @property-shimmed fields."""
    r = api_get("licenses/?page_size=1")
    assert r.status_code == 200
    lic_id = r.json()["results"][0]["id"]
    detail = api_get(f"licenses/{lic_id}/")
    assert detail.status_code == 200, detail.text[:200]
    body = detail.json()
    # These all live on sub-tables now; if the serializer can't read them via
    # the @property shims we'll get nulls or a 500.
    for key in (
        "balance_cif", "is_active", "is_expired", "is_au", "is_audit",
        "current_owner", "condition_sheet", "balance_report_notes",
    ):
        assert key in body, f"missing {key!r} in license detail response"


# ---------- list viewsets ----------
@pytest.mark.parametrize(
    "path",
    [
        "active-licenses/?page_size=3",
        "expiring-licenses/?page_size=3",
        "inventory-balance/?page_size=3",
        "incentive-licenses/?page_size=3",
        "license-ledger/?page_size=3",
        "license-ledger/?active_only=true&min_balance=100&page_size=3",
        "license-items/?page_size=3",
    ],
)
def test_license_viewsets(api_get, path):
    r = api_get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


# ---------- reports ----------
@pytest.fixture(scope="module")
def sample_norm(api_get) -> str:
    r = api_get("item-pivot/available-norms/")
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert isinstance(data, list) and data, "no norms returned"
    return data[0]["norm_class"]


def test_item_pivot_available_norms(api_get):
    r = api_get("item-pivot/available-norms/")
    assert r.status_code == 200, r.text[:200]
    assert isinstance(r.json(), list)


def test_item_pivot_report(api_get, sample_norm):
    r = api_get(
        f"reports/item-pivot/?format=json&days=30&sion_norm={sample_norm}"
        f"&min_balance=200&license_status=active"
    )
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert "items" in body and "licenses_by_norm_notification" in body


def test_item_report_available_items(api_get):
    r = api_get("item-report/available-items/")
    assert r.status_code == 200, r.text[:200]


def test_item_report(api_get):
    r = api_get("reports/item-report/?format=json&hsn_code=72&min_balance=0")
    assert r.status_code == 200, r.text[:200]


def test_active_licenses_report(api_get):
    r = api_get("reports/active-licenses/?format=json&days=30")
    assert r.status_code == 200, r.text[:200]


def test_expiring_licenses_report(api_get):
    r = api_get("reports/expiring-licenses/?format=json&days=30")
    assert r.status_code == 200, r.text[:200]


def test_inventory_balance_report(api_get, sample_norm):
    r = api_get(f"reports/inventory-balance/?format=json&sion_norm={sample_norm}")
    assert r.status_code == 200, r.text[:200]
