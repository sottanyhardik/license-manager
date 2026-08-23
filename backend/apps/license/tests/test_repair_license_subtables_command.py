from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.license.management.commands.repair_license_subtables import Command
from apps.license.models import LicenseDetailsModel, LicenseNotes


def test_repair_license_subtables_requires_dry_run_or_confirm(monkeypatch):
    def fail_if_called(self):
        raise AssertionError("validation should not run without an explicit mode")

    monkeypatch.setattr(Command, "_validate_required_tables", fail_if_called)

    with pytest.raises(CommandError, match="Pass --dry-run to preview or --confirm"):
        call_command("repair_license_subtables", stdout=StringIO())


def test_repair_license_subtables_dry_run_dispatches_no_write_methods(monkeypatch):
    calls = []

    def fake_validate(self):
        calls.append(("validate", None))

    def fake_repair_model_columns(self, model, *, dry_run):
        calls.append(("model_columns", model.__name__, dry_run))

    def fake_repair_lookup_fks(self, *, dry_run):
        calls.append(("lookup_fks", dry_run))

    def fake_repair_split_tables(self, *, dry_run):
        calls.append(("split_tables", dry_run))

    def fail_report_counts(self):
        raise AssertionError("dry-run must not run final write verification")

    monkeypatch.setattr(Command, "_validate_required_tables", fake_validate)
    monkeypatch.setattr(Command, "_repair_model_columns", fake_repair_model_columns)
    monkeypatch.setattr(Command, "_repair_lookup_fks", fake_repair_lookup_fks)
    monkeypatch.setattr(Command, "_repair_split_tables", fake_repair_split_tables)
    monkeypatch.setattr(Command, "_report_counts", fail_report_counts)

    stdout = StringIO()
    call_command("repair_license_subtables", "--dry-run", stdout=stdout)

    assert calls == [
        ("validate", None),
        ("model_columns", "LicenseDetailsModel", True),
        ("lookup_fks", True),
        ("split_tables", True),
    ]
    assert "DRY-RUN complete" in stdout.getvalue()


def test_repair_license_subtables_quotes_schema_qualified_identifiers():
    quoted = Command()._quote_identifier_path("public.license_licensedetailsmodel")

    assert quoted == '"public"."license_licensedetailsmodel"'


@pytest.mark.django_db
def test_repair_license_subtables_report_counts_detects_missing_subrows():
    license_obj = LicenseDetailsModel.objects.create(license_number="SUBTABLE-REPAIR-001")
    LicenseNotes.objects.filter(license=license_obj).delete()

    with pytest.raises(CommandError, match="License sub-table repair incomplete"):
        Command()._report_counts()


@pytest.mark.django_db
def test_repair_license_subtables_report_counts_accepts_complete_subrows():
    LicenseDetailsModel.objects.create(license_number="SUBTABLE-REPAIR-002")
    command = Command()
    command.stdout = StringIO()

    command._report_counts()

    assert "License sub-tables OK" in command.stdout.getvalue()
