from __future__ import annotations

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.license.models import LicenseBalance, LicenseDetailsModel


def test_update_balance_cif_rejects_invalid_batch_size():
    with pytest.raises(CommandError, match="--batch-size must be greater than zero"):
        call_command("update_balance_cif", "--batch-size", "0")


def test_update_balance_cif_rejects_blank_license_number():
    with pytest.raises(CommandError, match="--license-number must not be blank"):
        call_command("update_balance_cif", "--license-number", "   ")


@pytest.mark.django_db
def test_update_balance_cif_missing_license_raises_command_error():
    with pytest.raises(CommandError, match="License MISSING-LIC not found"):
        call_command("update_balance_cif", "--license-number", "MISSING-LIC")


@pytest.mark.django_db
def test_update_balance_cif_updates_split_balance_row(monkeypatch):
    license_obj = LicenseDetailsModel.objects.create(license_number="BAL-LIC-001")
    license_obj.balance.balance_cif = Decimal("1.00")
    license_obj.balance.save(update_fields=["balance_cif"])
    monkeypatch.setattr(
        "apps.license.management.commands.update_balance_cif."
        "LicenseBalanceCalculator.calculate_balance",
        lambda license_obj: Decimal("25.50"),
    )

    call_command(
        "update_balance_cif",
        "--license-number",
        "BAL-LIC-001",
        stdout=StringIO(),
    )

    license_obj.balance.refresh_from_db()
    assert license_obj.balance.balance_cif == Decimal("25.50")


@pytest.mark.django_db
def test_update_balance_cif_dry_run_does_not_write(monkeypatch):
    license_obj = LicenseDetailsModel.objects.create(license_number="BAL-LIC-002")
    license_obj.balance.balance_cif = Decimal("1.00")
    license_obj.balance.save(update_fields=["balance_cif"])
    monkeypatch.setattr(
        "apps.license.management.commands.update_balance_cif."
        "LicenseBalanceCalculator.calculate_balance",
        lambda license_obj: Decimal("25.50"),
    )

    call_command(
        "update_balance_cif",
        "--license-number",
        "BAL-LIC-002",
        "--dry-run",
        stdout=StringIO(),
    )

    license_obj.balance.refresh_from_db()
    assert license_obj.balance.balance_cif == Decimal("1.00")


@pytest.mark.django_db
def test_update_balance_cif_recreates_missing_balance_row(monkeypatch):
    license_obj = LicenseDetailsModel.objects.create(license_number="BAL-LIC-003")
    LicenseBalance.objects.filter(license=license_obj).delete()
    monkeypatch.setattr(
        "apps.license.management.commands.update_balance_cif."
        "LicenseBalanceCalculator.calculate_balance",
        lambda license_obj: Decimal("42.00"),
    )

    call_command(
        "update_balance_cif",
        "--license-number",
        "BAL-LIC-003",
        stdout=StringIO(),
    )

    assert LicenseBalance.objects.get(license=license_obj).balance_cif == Decimal("42.00")
