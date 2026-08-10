"""
Independent skeptic re-verification of SEC-01.

Not part of the application test suite — lives under audit_evidence/, invoked
explicitly with pytest so it runs against pytest-django's throwaway test
database (created/destroyed for this run only; the real local "lmanagement"
DB is never touched).

Goal: empirically reproduce, by actually issuing HTTP requests through
Django's test client against the real view code (no mocking of
ProtectedMediaView or LicensePermission), that:

  1. A user with NO license/BOE/trade roles is correctly blocked (403) by
     LicensePermission on a normal license endpoint.
  2. The SAME user, hitting /api/media/<path> for a file placed at the
     predictable license-copy path, gets the file back with 200 — i.e. the
     RBAC check is bypassed for the document-download path.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
django.setup()

import pytest
from django.conf import settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def _make_user(username, roles=()):
    from apps.accounts.models import User
    from django.contrib.auth.models import Group

    user = User.objects.create_user(username=username, email=f"{username}@example.com", password="x")
    for role in roles:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    return user


def test_low_privilege_user_blocked_on_license_endpoint_but_not_on_media(tmp_path, settings):
    # Point MEDIA_ROOT at a throwaway tmp dir so we don't touch any real file.
    settings.MEDIA_ROOT = tmp_path
    settings.MEDIA_X_ACCEL_REDIRECT = ""  # force the direct-stream (dev) branch

    # A minimal real License row so the /api/licenses/<id>/ round trip is realistic
    # (only fields required by the model / serializer are set here for the check;
    # if the model requires more, this will raise and the skeptic result records that).
    from apps.license.models.core import LicenseDetailsModel

    license_number = "0510099999"
    license_dir = tmp_path / "licenses" / license_number
    license_dir.mkdir(parents=True)
    doc_path = license_dir / f"{license_number} Copy.pdf"
    doc_path.write_bytes(b"%PDF-1.4 fake licence copy contents\n")

    user = _make_user("incentive_only_user", roles=["INCENTIVE_LICENSE_VIEWER"])

    client = APIClient()
    client.force_authenticate(user=user)

    # 1. Confirm normal license list endpoint enforces LicensePermission for this user.
    #    (Use the list endpoint — it requires no existing object and is guaranteed to
    #    hit LicensePermission.has_permission for a GET.)
    license_list_resp = client.get("/api/licenses/")

    # 2. Same user, same session, hits the media endpoint for the predictable path.
    media_resp = client.get(f"/api/media/licenses/{license_number}/{license_number}%20Copy.pdf")

    result_lines = [
        f"MEDIA_ROOT (test) = {settings.MEDIA_ROOT}",
        f"file exists on disk = {doc_path.exists()}",
        f"user roles = {user.get_role_codes()}",
        f"GET /api/licenses/  -> status {license_list_resp.status_code}",
        f"GET /api/media/licenses/{license_number}/{license_number}%20Copy.pdf -> status {media_resp.status_code}",
    ]
    if media_resp.status_code == 200:
        result_lines.append(f"media response body (first 40 bytes) = {media_resp.getvalue()[:40]!r}")
    print("\n".join(result_lines))

    # Write results to a sibling file for evidence capture regardless of assertion outcome.
    out_path = os.path.join(os.path.dirname(__file__), "_skeptic_run_result.txt")
    with open(out_path, "w") as f:
        f.write("\n".join(result_lines) + "\n")

    assert license_list_resp.status_code == 403, (
        f"expected LicensePermission to block this low-privilege user on /api/licenses/, "
        f"got {license_list_resp.status_code}"
    )
    assert media_resp.status_code == 200, (
        f"expected ProtectedMediaView to (per the claim) NOT block this same user, "
        f"got {media_resp.status_code}"
    )
