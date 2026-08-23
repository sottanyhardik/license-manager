from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from apps.core.models import PurchaseStatus
from apps.license.models import LicenseDetailsModel


@pytest.mark.django_db
def test_migrate_purchase_status_renames_np_when_mi_is_missing():
    np_status = PurchaseStatus.objects.create(code="NP", label="NP")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="NP-ONLY-001",
        purchase_status=np_status,
    )
    stdout = StringIO()

    call_command("migrate_purchase_status_np_to_mi", "--confirm", stdout=stdout)

    np_status.refresh_from_db()
    license_obj.refresh_from_db()
    assert np_status.code == "MI"
    assert np_status.label == "MITC"
    assert license_obj.purchase_status_id == np_status.id
    assert "Post-migration state" in stdout.getvalue()


@pytest.mark.django_db
def test_migrate_purchase_status_merges_np_into_existing_mi():
    np_status = PurchaseStatus.objects.create(code="NP", label="Legacy NP")
    mi_status = PurchaseStatus.objects.create(code="MI", label="MITC")
    license_obj = LicenseDetailsModel.objects.create(
        license_number="NP-MERGE-001",
        purchase_status=np_status,
    )
    stdout = StringIO()

    call_command("migrate_purchase_status_np_to_mi", "--confirm", stdout=stdout)

    license_obj.refresh_from_db()
    assert license_obj.purchase_status_id == mi_status.id
    assert not PurchaseStatus.objects.filter(id=np_status.id).exists()
    assert PurchaseStatus.objects.filter(code="MI").count() == 1
    assert "Reassigned 1 licenses" in stdout.getvalue()


@pytest.mark.django_db
def test_migrate_purchase_status_dry_run_does_not_write():
    np_status = PurchaseStatus.objects.create(code="NP", label="Legacy NP")
    stdout = StringIO()

    call_command("migrate_purchase_status_np_to_mi", "--dry-run", stdout=stdout)

    np_status.refresh_from_db()
    assert np_status.code == "NP"
    assert "--dry-run" in stdout.getvalue()


@pytest.mark.django_db
def test_migrate_purchase_status_refuses_write_without_confirm():
    np_status = PurchaseStatus.objects.create(code="NP", label="Legacy NP")
    stdout = StringIO()

    call_command("migrate_purchase_status_np_to_mi", stdout=stdout)

    np_status.refresh_from_db()
    assert np_status.code == "NP"
    assert "Refusing to write without --confirm" in stdout.getvalue()
