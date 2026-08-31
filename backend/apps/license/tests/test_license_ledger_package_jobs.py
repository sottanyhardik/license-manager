"""HTTP contracts for durable licence-ledger package jobs."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from django.utils import timezone

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.license.models import LicenseDetailsModel, LicenseLedgerPackageItem
from apps.license.services.license_ledger_package import _note_pdf
from apps.license.tasks import _build_item_sections


def _client():
    user = get_user_model().objects.create_superuser("ledger-package-owner", "owner@example.test", "test-password")
    client = APIClient(); client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db(transaction=True)
def test_package_post_is_accepted_and_duplicate_ids_make_one_item():
    client, _user = _client()
    licence = LicenseDetailsModel.objects.create(license_number="0311051359")
    with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay") as enqueue:
        response = client.post("/api/license-ledger/download-package/", {"license_ids": [str(licence.pk), str(licence.pk)]}, format="json")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued" and body["total"] == body["queued"] == 1
    assert LicenseLedgerPackageItem.objects.filter(job__key=body["job_id"]).count() == 1
    enqueue.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_job_status_and_downloads_are_owner_scoped():
    client, owner = _client()
    licence = LicenseDetailsModel.objects.create(license_number="0311051360")
    with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay"):
        created = client.post("/api/license-ledger/download-package/", {"license_ids": [str(licence.pk)]}, format="json").json()
    assert client.get(created["status_url"]).status_code == 200
    other = get_user_model().objects.create_superuser("ledger-package-other", "other@example.test", "test-password")
    client.force_authenticate(user=other)
    assert client.get(created["status_url"]).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_idempotency_key_reuses_the_same_owner_job():
    client, _user = _client()
    licence = LicenseDetailsModel.objects.create(license_number="0311051361")
    with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay") as enqueue:
        first = client.post("/api/license-ledger/download-package/", {"license_ids": [str(licence.pk)]}, format="json", HTTP_IDEMPOTENCY_KEY="same-click")
        second = client.post("/api/license-ledger/download-package/", {"license_ids": [str(licence.pk)]}, format="json", HTTP_IDEMPOTENCY_KEY="same-click")
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    enqueue.assert_called_once()


@pytest.mark.django_db
def test_server_ready_item_status_exposes_safe_artifact_metadata():
    client, _user = _client()
    licence = LicenseDetailsModel.objects.create(license_number="0311051362")
    with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay"):
        created = client.post("/api/license-ledger/download-package/", {"license_ids": [str(licence.pk)]}, format="json").json()
    item = LicenseLedgerPackageItem.objects.get(job__key=created["job_id"])
    item.status = "server_ready"
    item.completed_at = timezone.now()
    item.output_key = "private-storage-path-never-exposed.pdf"
    item.output_size = 12345
    item.output_checksum = "a" * 64
    item.save()
    result = client.get(created["status_url"]).json()["licences"][0]
    assert result["license_id"] == licence.pk
    assert result["licence_number"] == "0311051362"
    assert result["filename"] == "0311051362.pdf"
    assert result["size"] == 12345 and result["sha256"] == "a" * 64
    assert result["download_url"].endswith(f"/licences/{item.pk}/download/")
    assert "output_key" not in result and "private-storage-path" not in str(result)


def test_worker_manifest_keeps_canonical_section_order_and_marks_empty_optional_sections():
    """Storage gets only actual PDFs; audit metadata retains all four sections."""
    pdf = _note_pdf("Canonical section", ["one source page"])
    item = SimpleNamespace(
        license=SimpleNamespace(pk=91), license_id=91, licence_number="0311051359",
        job=SimpleNamespace(requested_by=object()),
    )
    dataset = {"license_id": 91, "license_number": "0311051359"}
    with (
        patch("apps.license.services.canonical_ledger_service.CanonicalLedgerService.build_canonical_ledger_dataset", return_value=dataset),
        patch("apps.license.services.license_ledger_package._purchase_candidates", return_value=[]),
        patch("apps.license.services.license_ledger_package._final_party_sales_candidates", return_value=[]),
        patch("apps.license.services.license_ledger_package.LicenseLedgerPackageService.build_sections", return_value=[
            ("01-custom-ledger.pdf", pdf), ("02-financial-ledger.pdf", pdf),
        ]),
    ):
        merged, manifest, persisted = _build_item_sections(item)

    assert merged.startswith(b"%PDF-")
    from pypdf import PdfReader
    from reportlab.lib.pagesizes import A4
    for page in PdfReader(BytesIO(merged)).pages:
        assert abs(float(page.mediabox.width) - A4[0]) < 0.1
        assert abs(float(page.mediabox.height) - A4[1]) < 0.1
    assert [entry["filename"] for entry in manifest["sections"]] == [
        "01-custom-ledger.pdf", "02-financial-ledger.pdf",
        "03-main-purchase-invoices.pdf", "04-final-party-sales-invoices.pdf",
    ]
    assert [entry["status"] for entry in manifest["sections"]] == [
        "included", "included", "not_applicable", "not_applicable",
    ]
    assert [name for name, _content in persisted] == [
        "01-custom-ledger.pdf", "02-financial-ledger.pdf",
    ]
