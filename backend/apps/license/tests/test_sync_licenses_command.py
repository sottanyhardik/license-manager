from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.license.models import LicenseDetailsModel


def test_sync_licenses_rejects_blank_license_number():
    with pytest.raises(CommandError, match="--license must not be blank"):
        call_command("sync_licenses", "--license", "   ", "--dry-run")


def test_sync_licenses_rejects_invalid_batch_size():
    with pytest.raises(CommandError, match="--batch-size must be greater than zero"):
        call_command("sync_licenses", "--batch-size", "0", "--dry-run")


@pytest.fixture
def stale_license_state():
    license_obj = LicenseDetailsModel.objects.create(
        license_number="SYNC-LIC-001",
        license_expiry_date=date(2020, 1, 1),
    )
    balance = license_obj.balance
    balance.balance_cif = Decimal("1000.00")
    balance.save(update_fields=["balance_cif"])
    flags = license_obj.flags
    flags.is_null = False
    flags.is_expired = False
    flags.save(update_fields=["is_null", "is_expired"])
    return license_obj


@pytest.mark.django_db
def test_sync_licenses_updates_split_balance_and_flags(stale_license_state):
    call_command(
        "sync_licenses",
        "--license",
        "SYNC-LIC-001",
        "--no-items",
        "--batch-size",
        "1",
        stdout=StringIO(),
    )

    stale_license_state.balance.refresh_from_db()
    stale_license_state.flags.refresh_from_db()
    assert stale_license_state.balance.balance_cif == Decimal("0.00")
    assert stale_license_state.flags.is_null is True
    assert stale_license_state.flags.is_expired is True


@pytest.mark.django_db
def test_sync_licenses_dry_run_preserves_split_balance_and_flags(stale_license_state):
    call_command(
        "sync_licenses",
        "--license",
        "SYNC-LIC-001",
        "--no-items",
        "--dry-run",
        stdout=StringIO(),
    )

    stale_license_state.balance.refresh_from_db()
    stale_license_state.flags.refresh_from_db()
    assert stale_license_state.balance.balance_cif == Decimal("1000.00")
    assert stale_license_state.flags.is_null is False
    assert stale_license_state.flags.is_expired is False
