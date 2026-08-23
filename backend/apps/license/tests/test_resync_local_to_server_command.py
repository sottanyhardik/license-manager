from __future__ import annotations

from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.core.models import CompanyModel
from apps.license.management.commands import resync_local_to_server
from apps.license.management.commands.resync_local_to_server import (
    _build_payload_from_local,
    _normalize_server_url,
    _parse_license_numbers,
)
from apps.license.models import LicenseDetailsModel, LicenseTransferModel


def test_resync_rejects_blank_license_list():
    with pytest.raises(CommandError, match="at least one non-blank"):
        call_command("resync_local_to_server", "--licenses", " , ", "--dry-run")


def test_resync_rejects_invalid_since_date():
    with pytest.raises(CommandError, match="YYYY-MM-DD"):
        call_command("resync_local_to_server", "--since", "2026-99-99", "--dry-run")


def test_resync_rejects_non_positive_batch_size():
    with pytest.raises(CommandError, match="--batch-size must be greater than zero"):
        call_command("resync_local_to_server", "--batch-size", "0", "--dry-run")


def test_resync_rejects_invalid_server_url():
    with pytest.raises(CommandError, match="absolute http\\(s\\) URL"):
        _normalize_server_url("license-manager.example.com")


def test_parse_license_numbers_deduplicates_and_trims():
    assert _parse_license_numbers(" LIC-1,LIC-2, LIC-1 ,,") == ["LIC-1", "LIC-2"]


@pytest.fixture
def local_license():
    exporter = CompanyModel.objects.create(iec="EXP1234567", name="Exporter Co")
    current_owner = CompanyModel.objects.create(iec="OWN1234567", name="Owner Co")
    previous_owner = CompanyModel.objects.create(iec="OLD1234567", name="Old Owner")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="RESYNC-001",
        license_date=date(2026, 1, 10),
        license_expiry_date=date(2027, 1, 10),
        exporter=exporter,
    )
    ownership = license_obj.ownership
    ownership.current_owner = current_owner
    ownership.file_transfer_status = "Transfer - Pending"
    ownership.last_ownership_fetch = timezone.now()
    ownership.save(
        update_fields=[
            "current_owner",
            "file_transfer_status",
            "last_ownership_fetch",
        ]
    )
    LicenseTransferModel.objects.create(
        license=license_obj,
        from_company=previous_owner,
        to_company=current_owner,
        transfer_status="Pending",
        transfer_initiation_date=timezone.now(),
        transfer_date=date(2026, 2, 1),
        cbic_status="OPEN",
        user_id_transfer_initiation="init-user",
    )
    return license_obj


@pytest.mark.django_db
def test_build_payload_from_local_serializes_ownership_and_transfers(local_license):
    payload = _build_payload_from_local(local_license)

    assert payload["license_number"] == "RESYNC-001"
    assert payload["license_date"] == "2026-01-10"
    assert payload["validity"] == "10/01/2027"
    assert payload["exporter_iec"] == "EXP1234567"
    assert payload["current_owner"] == {"iec": "OWN1234567", "name": "Owner Co"}
    assert payload["file_transfer_status"] == "Transfer - Pending"
    assert payload["transfers"][0]["from_iec"] == "OLD1234567"
    assert payload["transfers"][0]["to_iec"] == "OWN1234567"


@pytest.mark.django_db
def test_resync_dry_run_does_not_authenticate_or_post(local_license, monkeypatch):
    def fail_authenticate(*args, **kwargs):
        raise AssertionError("dry-run must not authenticate")

    def fail_bulk_sync(*args, **kwargs):
        raise AssertionError("dry-run must not post")

    monkeypatch.setattr(resync_local_to_server, "authenticate", fail_authenticate)
    monkeypatch.setattr(resync_local_to_server, "bulk_sync_to_server", fail_bulk_sync)

    stdout = StringIO()
    call_command(
        "resync_local_to_server",
        "--licenses",
        "RESYNC-001",
        "--dry-run",
        stdout=stdout,
    )

    assert "would push" in stdout.getvalue()


@pytest.mark.django_db
def test_resync_posts_in_batches(local_license, monkeypatch):
    for index in range(2, 5):
        LicenseDetailsModel.objects.create(license_number=f"RESYNC-00{index}")
    batch_sizes = []

    monkeypatch.setattr(
        resync_local_to_server,
        "authenticate",
        lambda server_url: (True, server_url),
    )

    def fake_bulk_sync(payloads, server_url):
        batch_sizes.append(len(payloads))
        return {"success": len(payloads), "failed": 0, "errors": []}

    monkeypatch.setattr(resync_local_to_server, "bulk_sync_to_server", fake_bulk_sync)

    call_command(
        "resync_local_to_server",
        "--server",
        "https://example.test/",
        "--licenses",
        "RESYNC-001,RESYNC-002,RESYNC-003,RESYNC-004",
        "--batch-size",
        "2",
        stdout=StringIO(),
    )

    assert batch_sizes == [2, 2]


@pytest.mark.django_db
def test_resync_raises_when_remote_reports_failures(local_license, monkeypatch):
    monkeypatch.setattr(
        resync_local_to_server,
        "authenticate",
        lambda server_url: (True, server_url),
    )
    monkeypatch.setattr(
        resync_local_to_server,
        "bulk_sync_to_server",
        lambda payloads, server_url: {"success": 0, "failed": 1, "errors": []},
    )

    with pytest.raises(CommandError, match="Remote sync failed"):
        call_command(
            "resync_local_to_server",
            "--licenses",
            "RESYNC-001",
            stdout=StringIO(),
        )
