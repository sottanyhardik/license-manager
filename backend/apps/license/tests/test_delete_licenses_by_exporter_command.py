from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_delete_licenses_by_exporter_rejects_blank_exporter():
    with pytest.raises(CommandError, match="Exporter filter must not be blank"):
        call_command(
            "delete_licenses_by_exporter",
            "--filter",
            "contains",
            "--exporter",
            "   ",
            "--dry-run",
        )


def test_delete_licenses_by_exporter_rejects_invalid_batch_size():
    with pytest.raises(CommandError, match="Batch size must be greater than zero"):
        call_command(
            "delete_licenses_by_exporter",
            "--filter",
            "contains",
            "--exporter",
            "PARLE",
            "--dry-run",
            "--batch-size",
            "0",
        )


def test_delete_licenses_by_exporter_requires_dry_run_or_confirm():
    stdout = StringIO()

    call_command(
        "delete_licenses_by_exporter",
        "--filter",
        "contains",
        "--exporter",
        "PARLE",
        stdout=stdout,
    )

    assert "You must specify either --dry-run or --confirm to proceed" in stdout.getvalue()


@pytest.mark.django_db
def test_delete_licenses_by_exporter_dry_run_with_no_matches_does_not_delete():
    stdout = StringIO()

    call_command(
        "delete_licenses_by_exporter",
        "--filter",
        "contains",
        "--exporter",
        "NO-SUCH-EXPORTER",
        "--dry-run",
        stdout=stdout,
    )

    assert 'No licenses found where exporter contains "NO-SUCH-EXPORTER"' in stdout.getvalue()
