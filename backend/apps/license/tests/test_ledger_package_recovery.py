"""Fail-closed recovery tests for licence-ledger package source corrections."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import CompanyModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseLedgerPackageItem,
    LicenseLedgerPackageJob,
    LicenseLedgerRecoveryAudit,
)
from apps.license.services.ledger_package_recovery import (
    link_unique_orphan,
    upload_purchase_document,
)
from apps.license.services.license_ledger_package import _note_pdf
from apps.trade.models import LicenseTrade, LicenseTradeLine


def _purchase(*, invoice_number="SUP/2026/1", supplier=None):
    return LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_PURCHASE,
        from_company=supplier,
        invoice_number=invoice_number,
        invoice_date="2026-04-01",
        total_amount="100.00",
    )


def _evidence(trade):
    return {
        "invoice_number": trade.invoice_number,
        "supplier_id": trade.from_company_id,
        "invoice_date": str(trade.invoice_date),
        "total_amount": str(trade.total_amount),
    }


@pytest.mark.django_db
def test_unique_exact_orphan_match_links_copy_and_writes_append_only_audit():
    supplier = CompanyModel.objects.create(name="Recovery Supplier", iec="9000000001")
    trade = _purchase(supplier=supplier)
    pdf = _note_pdf("Supplier invoice", [trade.invoice_number])

    with patch("apps.license.services.ledger_package_recovery.requeue_ready_package_items") as requeue:
        linked = link_unique_orphan(
            trade_id=trade.pk, source_key="orphan/supplier-invoice.pdf",
            source_bytes=pdf, evidence=_evidence(trade),
        )

    linked.refresh_from_db()
    assert linked.purchase_invoice_copy.name
    audit = LicenseLedgerRecoveryAudit.objects.get(trade=trade)
    assert audit.source_storage_key == "orphan/supplier-invoice.pdf"
    assert audit.matching_rule == "EXACT_INVOICE_SUPPLIER_DATE_TOTAL"
    assert audit.source_checksum
    requeue.assert_called_once_with(trade)


@pytest.mark.django_db
def test_ambiguous_exact_orphan_match_stays_unlinked():
    # SQL unique constraints treat NULL supplier values as distinct, allowing
    # this historical ambiguity to be represented and tested explicitly.
    trade = _purchase(invoice_number="DUP/2026/1")
    _purchase(invoice_number="DUP/2026/1")
    pdf = _note_pdf("Supplier invoice", [trade.invoice_number])

    with pytest.raises(ValueError, match="ambiguous"):
        link_unique_orphan(
            trade_id=trade.pk, source_key="orphan/ambiguous.pdf",
            source_bytes=pdf, evidence=_evidence(trade),
        )

    trade.refresh_from_db()
    assert not trade.purchase_invoice_copy
    assert not LicenseLedgerRecoveryAudit.objects.filter(trade=trade).exists()


@pytest.mark.django_db
def test_corrupt_orphan_and_upload_are_rejected_without_audit_or_link():
    trade = _purchase()
    for operation in (
        lambda: link_unique_orphan(trade_id=trade.pk, source_key="orphan/bad.bin", source_bytes=b"not a document", evidence=_evidence(trade)),
        lambda: upload_purchase_document(trade_id=trade.pk, content=b"not a document", filename="bad.bin"),
    ):
        with pytest.raises(Exception):
            operation()
    trade.refresh_from_db()
    assert not trade.purchase_invoice_copy
    assert not LicenseLedgerRecoveryAudit.objects.filter(trade=trade).exists()


@pytest.mark.django_db
def test_recovery_audit_is_immutable():
    trade = _purchase()
    audit = LicenseLedgerRecoveryAudit.objects.create(
        trade=trade, source_storage_key="orphan/a.pdf", source_checksum="a" * 64,
        matching_rule="EXACT_INVOICE_SUPPLIER_DATE_TOTAL",
    )
    audit.matching_rule = "tampered"
    with pytest.raises(ValidationError, match="immutable"):
        audit.save()
    with pytest.raises(ValidationError, match="immutable"):
        audit.delete()


@pytest.mark.django_db(transaction=True)
def test_upload_unblocks_affected_item_and_enqueues_its_existing_job_once():
    user = get_user_model().objects.create_superuser("recovery-owner", "recovery@example.test", "pw")
    licence = LicenseDetailsModel.objects.create(license_number="RECOVERY-READY")
    sr = LicenseImportItemsModel.objects.create(license=licence, serial_number=1, quantity="1.000", cif_fc="1.00")
    trade = _purchase()
    LicenseTradeLine.objects.create(trade=trade, sr_number=sr, qty_kg="1.000")
    job = LicenseLedgerPackageJob.objects.create(
        key="recovery-job", requested_by=user, requested_ids=[licence.pk], expires_at=timezone.now(),
    )
    item = LicenseLedgerPackageItem.objects.create(
        job=job, license=licence, licence_number=licence.license_number,
        status=LicenseLedgerPackageItem.STATUS_BLOCKED_MISSING_PURCHASE_DOCUMENT,
    )

    with patch("apps.license.tasks.enqueue_license_ledger_package_job.delay") as delay:
        upload_purchase_document(
            trade_id=trade.pk, content=_note_pdf("Supplier invoice", [trade.invoice_number]),
            filename="supplier.pdf", user=user,
        )

    item.refresh_from_db()
    assert item.status == LicenseLedgerPackageItem.STATUS_QUEUED
    delay.assert_called_once_with(job.pk, [item.pk])
