from __future__ import annotations

from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.license.management.commands.update_license_expiry import Command
from apps.license.models import LicenseDetailsModel


def write_csv(tmp_path, content: str):
    csv_path = tmp_path / "expiry.csv"
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


def test_update_license_expiry_rejects_blank_csv_path():
    with pytest.raises(CommandError, match="CSV file path must not be blank"):
        call_command("update_license_expiry", "   ")


def test_update_license_expiry_rejects_missing_csv_file(tmp_path):
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(CommandError, match="CSV file not found"):
        call_command("update_license_expiry", str(missing_path))


def test_update_license_expiry_rejects_directory_path(tmp_path):
    with pytest.raises(CommandError, match="CSV path is not a file"):
        call_command("update_license_expiry", str(tmp_path))


def test_update_license_expiry_rejects_empty_csv_file(tmp_path):
    csv_path = write_csv(tmp_path, "\n\n")

    with pytest.raises(CommandError, match="does not contain any license expiry rows"):
        call_command("update_license_expiry", str(csv_path))


def test_update_license_expiry_parses_legacy_two_digit_years_as_2000s():
    command = Command()

    assert command.parse_date("17/03/69") == date(2069, 3, 17)
    assert command.parse_date("17-03-99") == date(2099, 3, 17)


@pytest.mark.django_db
def test_update_license_expiry_updates_license_and_flags(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-001",
        license_expiry_date=date(2099, 1, 1),
    )
    license_obj.flags.is_expired = False
    license_obj.flags.save(update_fields=["is_expired"])
    csv_path = write_csv(
        tmp_path,
        "license_number,license_expiry_date\nEXP-LIC-001,2020-01-10\n",
    )

    call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    license_obj.refresh_from_db()
    license_obj.flags.refresh_from_db()
    assert license_obj.license_expiry_date == date(2020, 1, 10)
    assert license_obj.flags.is_expired is True


@pytest.mark.django_db
def test_update_license_expiry_accepts_no_header_csv_and_trims_values(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(license_number="EXP-LIC-002")
    csv_path = write_csv(tmp_path, "  EXP-LIC-002  , 17/03/26 \n")

    call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    license_obj.refresh_from_db()
    assert license_obj.license_expiry_date == date(2026, 3, 17)


@pytest.mark.django_db
def test_update_license_expiry_dry_run_does_not_write(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-003",
        license_expiry_date=date(2026, 1, 1),
    )
    csv_path = write_csv(tmp_path, "license_number,license_expiry_date\nEXP-LIC-003,2027-02-01\n")

    call_command("update_license_expiry", str(csv_path), "--dry-run", stdout=StringIO())

    license_obj.refresh_from_db()
    assert license_obj.license_expiry_date == date(2026, 1, 1)


@pytest.mark.django_db
def test_update_license_expiry_rejects_malformed_rows_without_writes(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-004",
        license_expiry_date=date(2026, 1, 1),
    )
    csv_path = write_csv(
        tmp_path,
        "license_number,license_expiry_date\nEXP-LIC-004,2027-02-01,unexpected\n",
    )

    with pytest.raises(CommandError, match="CSV validation failed"):
        call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    license_obj.refresh_from_db()
    assert license_obj.license_expiry_date == date(2026, 1, 1)


@pytest.mark.django_db
def test_update_license_expiry_rejects_duplicate_license_rows(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-005",
        license_expiry_date=date(2026, 1, 1),
    )
    csv_path = write_csv(
        tmp_path,
        "license_number,license_expiry_date\n"
        "EXP-LIC-005,2027-02-01\n"
        "EXP-LIC-005,2028-03-01\n",
    )

    with pytest.raises(CommandError, match="CSV validation failed"):
        call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    license_obj.refresh_from_db()
    assert license_obj.license_expiry_date == date(2026, 1, 1)


@pytest.mark.django_db
def test_update_license_expiry_missing_license_blocks_all_writes(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-006",
        license_expiry_date=date(2026, 1, 1),
    )
    csv_path = write_csv(
        tmp_path,
        "license_number,license_expiry_date\n"
        "EXP-LIC-006,2027-02-01\n"
        "EXP-LIC-MISSING,2027-03-01\n",
    )

    with pytest.raises(CommandError, match="CSV validation failed"):
        call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    license_obj.refresh_from_db()
    assert license_obj.license_expiry_date == date(2026, 1, 1)


@pytest.mark.django_db
def test_update_license_expiry_rejects_invalid_date_without_writes(tmp_path):
    license_obj = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-007",
        license_expiry_date=date(2026, 1, 1),
    )
    csv_path = write_csv(tmp_path, "license_number,license_expiry_date\nEXP-LIC-007,not-a-date\n")

    with pytest.raises(CommandError, match="CSV validation failed"):
        call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    license_obj.refresh_from_db()
    assert license_obj.license_expiry_date == date(2026, 1, 1)


@pytest.mark.django_db
def test_update_license_expiry_rolls_back_transaction_on_save_failure(tmp_path, monkeypatch):
    first_license = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-ROLLBACK-1",
        license_expiry_date=date(2026, 1, 1),
    )
    second_license = LicenseDetailsModel.objects.create(
        license_number="EXP-LIC-ROLLBACK-2",
        license_expiry_date=date(2026, 1, 1),
    )
    csv_path = write_csv(
        tmp_path,
        "license_number,license_expiry_date\n"
        "EXP-LIC-ROLLBACK-1,2027-02-01\n"
        "EXP-LIC-ROLLBACK-2,2027-03-01\n",
    )
    original_save = LicenseDetailsModel.save

    def fail_second_save(self, *args, **kwargs):
        if self.license_number == "EXP-LIC-ROLLBACK-2":
            raise RuntimeError("simulated save failure")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(LicenseDetailsModel, "save", fail_second_save)

    with pytest.raises(CommandError, match="Error updating licenses"):
        call_command("update_license_expiry", str(csv_path), stdout=StringIO())

    first_license.refresh_from_db()
    second_license.refresh_from_db()
    assert first_license.license_expiry_date == date(2026, 1, 1)
    assert second_license.license_expiry_date == date(2026, 1, 1)
