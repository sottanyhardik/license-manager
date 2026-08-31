"""Fail-closed source recovery and per-item readiness for ledger packages.

Discovery is read-only.  A source can be attached only by the explicit
``link_unique_orphan`` operation after all authoritative header fields match.
"""
from __future__ import annotations

import hashlib
import re
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.license.models import LicenseLedgerPackageItem, LicenseLedgerRecoveryAudit
from apps.license.services.license_invoice_relations import get_final_party_sales_invoices, get_main_purchase_invoices
from apps.trade.models import LicenseTrade


def normalize_invoice(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def validate_source_bytes(content: bytes) -> str:
    """Return source type only for readable PDF/image; reject executable junk."""
    if not content:
        raise ValueError("Document is zero bytes")
    if content.startswith(b"%PDF-"):
        from pypdf import PdfReader
        if not PdfReader(BytesIO(content)).pages:
            raise ValueError("PDF has no pages")
        return "PDF"
    from PIL import Image
    with Image.open(BytesIO(content)) as image:
        image.verify()
    return "IMAGE"


def missing_purchase_trades(licence):
    """Canonical direct purchases whose required physical document is absent."""
    ids = [row["source_id"] for row in get_main_purchase_invoices(licence) if row["selection_result"] == "INCLUDED"]
    return list(LicenseTrade.objects.filter(pk__in=ids).filter(purchase_invoice_copy="").order_by("pk"))


def licence_readiness(licence) -> dict:
    missing = missing_purchase_trades(licence)
    sales = get_final_party_sales_invoices(licence)
    unknown = [row["source_id"] for row in sales if row["classification_status"] == LicenseTrade.FINAL_PARTY_UNKNOWN]
    # An explicitly FINAL sale with no persisted canonical invoice is a source
    # blocker, not a non-applicable result.
    final_missing = []
    for row in sales:
        if row["selection_result"] == "INCLUDED" and not row.get("document_id"):
            final_missing.append(row["source_id"])
    if missing and (unknown or final_missing): status = "BLOCKED_MULTIPLE_REASONS"
    elif missing: status = "BLOCKED_MISSING_PURCHASE_DOCUMENT"
    elif unknown: status = "BLOCKED_UNKNOWN_SALES_CLASSIFICATION"
    elif final_missing: status = "BLOCKED_MISSING_FINAL_PARTY_SALES_INVOICE"
    else: status = "READY"
    return {"status": status, "missing_purchase_trade_ids": [t.pk for t in missing],
            "unknown_sale_ids": unknown, "missing_final_sale_ids": final_missing}


def readiness_tabs(job) -> dict:
    """Presentation-safe, explicit review rows for one durable package job."""
    missing, unknown, resolved = [], [], []
    licence_ids = list(job.items.values_list("license_id", flat=True))
    # The same purchase trade can affect several requested licences; retain a
    # row per licence because uploads/resume are evaluated per work item.
    for item in job.items.select_related("license").order_by("pk"):
        for trade in missing_purchase_trades(item.license):
            audits = list(trade.ledger_recovery_audits.order_by("-created_at").values("id", "recovery_method", "source_checksum", "created_at"))
            missing.append({"item_id": item.pk, "licence_id": item.license_id, "licence_number": item.licence_number,
                "trade_id": trade.pk, "supplier": getattr(trade.from_company, "name", "") if trade.from_company_id else "",
                "supplier_id": trade.from_company_id, "purchase_invoice_number": trade.invoice_number or "",
                "invoice_date": trade.invoice_date, "invoice_amount": str(trade.total_amount),
                "expected_document": "supplier purchase invoice", "candidate_orphans": [], "current_status": "MISSING", "audits": audits})
        for candidate in get_final_party_sales_invoices(item.license):
            if candidate["classification_status"] != LicenseTrade.FINAL_PARTY_UNKNOWN:
                continue
            trade = LicenseTrade.objects.select_related("from_company", "to_company", "linked_trade", "counterpart", "copied_from").get(pk=candidate["source_id"])
            unknown.append({"item_id": item.pk, "licence_id": item.license_id, "licence_number": item.licence_number,
                "sale_id": trade.pk, "invoice_number": trade.invoice_number or "", "seller": getattr(trade.from_company, "name", "") if trade.from_company_id else "",
                "buyer": getattr(trade.to_company, "name", "") if trade.to_company_id else "", "buyer_id": trade.to_company_id,
                "parent_sale_id": trade.linked_trade_id or trade.copied_from_id, "counterpart_sale_id": trade.counterpart_id,
                "branch_path": "linked=%s counterpart=%s copied_from=%s" % (trade.linked_trade_id or "", trade.counterpart_id or "", trade.copied_from_id or ""),
                "finalized_status": candidate["classification_status"], "invoice_date": trade.invoice_date,
                "invoice_value": str(trade.total_amount), "existing_classification_evidence": trade.final_party_resolution_note or "",
                "decision": "", "reason": ""})
    for audit in LicenseLedgerRecoveryAudit.objects.filter(trade__lines__sr_number__license_id__in=licence_ids).select_related("trade").distinct().order_by("-created_at"):
        resolved.append({"audit_id": audit.pk, "trade_id": audit.trade_id, "recovery_method": audit.recovery_method,
                         "source_checksum": audit.source_checksum, "matched_document": bool(audit.linked_document_key),
                         "created_at": audit.created_at})
    return {"missing_purchase_documents": missing, "orphan_recovery_candidates": [],
            "unknown_sales_classifications": unknown, "resolved": resolved}


def candidate_matches_for_orphan(*, invoice_number: str, supplier_id: int | None, invoice_date, total_amount):
    """Only exact invoice/supplier/date/amount matches qualify for automatic link."""
    query = LicenseTrade.objects.filter(direction=LicenseTrade.DIR_PURCHASE, purchase_invoice_copy="")
    query = query.filter(invoice_number__iexact=invoice_number, from_company_id=supplier_id,
                         invoice_date=invoice_date, total_amount=total_amount)
    return list(query.order_by("pk"))


def link_unique_orphan(*, trade_id: int, source_key: str, source_bytes: bytes, evidence: dict, user=None):
    """Copy a uniquely proven orphan through Django storage and audit it.

    ``evidence`` must include the four exact header fields; it is intentionally
    rechecked here rather than trusting a browser candidate token.
    """
    validate_source_bytes(source_bytes)
    with transaction.atomic():
        trade = LicenseTrade.objects.select_for_update().get(pk=trade_id, direction=LicenseTrade.DIR_PURCHASE)
        if trade.purchase_invoice_copy:
            raise ValueError("Purchase trade already has a document")
        required = {"invoice_number", "supplier_id", "invoice_date", "total_amount"}
        if not required.issubset(evidence):
            raise ValueError("Exact authoritative matching evidence is required")
        if (normalize_invoice(evidence["invoice_number"]) != normalize_invoice(trade.invoice_number)
                or str(evidence["supplier_id"]) != str(trade.from_company_id)
                or str(evidence["invoice_date"]) != str(trade.invoice_date)
                or str(evidence["total_amount"]) != str(trade.total_amount)):
            raise ValueError("Evidence does not match the purchase trade")
        matches = candidate_matches_for_orphan(invoice_number=trade.invoice_number, supplier_id=trade.from_company_id,
                                                invoice_date=trade.invoice_date, total_amount=trade.total_amount)
        if len(matches) != 1 or matches[0].pk != trade.pk:
            raise ValueError("Orphan match is ambiguous or not uniquely deterministic")
        checksum = hashlib.sha256(source_bytes).hexdigest()
        filename = "recovered-%s-%s" % (trade.pk, checksum[:12])
        trade.purchase_invoice_copy.save(filename, ContentFile(source_bytes), save=False)
        trade.save(update_fields=["purchase_invoice_copy", "modified_on"])
        LicenseLedgerRecoveryAudit.objects.create(trade=trade, source_storage_key=source_key,
            source_checksum=checksum, linked_document_key=trade.purchase_invoice_copy.name,
            evidence=dict(evidence), matching_rule="EXACT_INVOICE_SUPPLIER_DATE_TOTAL", recovery_method="ORPHAN_LINK", created_by=user)
    requeue_ready_package_items(trade)
    return trade


def upload_purchase_document(*, trade_id: int, content: bytes, filename: str, user=None):
    """Attach an authorised, validated supplier upload and audit its provenance."""
    validate_source_bytes(content)
    with transaction.atomic():
        trade = LicenseTrade.objects.select_for_update().get(pk=trade_id, direction=LicenseTrade.DIR_PURCHASE)
        checksum = hashlib.sha256(content).hexdigest()
        trade.purchase_invoice_copy.save("uploaded-%s-%s-%s" % (trade.pk, checksum[:12], filename), ContentFile(content), save=False)
        trade.save(update_fields=["purchase_invoice_copy", "modified_on"])
        LicenseLedgerRecoveryAudit.objects.create(trade=trade, source_storage_key="USER_UPLOAD",
            source_checksum=checksum, linked_document_key=trade.purchase_invoice_copy.name,
            evidence={"filename": filename}, matching_rule="AUTHORISED_UPLOAD", recovery_method="UPLOAD", created_by=user)
    requeue_ready_package_items(trade)
    return trade


def requeue_ready_package_items(trade):
    """Re-evaluate all durable requests affected by a changed purchase/sale."""
    licence_ids = set(trade.lines.values_list("sr_number__license_id", flat=True))
    ready_ids = []
    with transaction.atomic():
        blocked_statuses = [
            LicenseLedgerPackageItem.STATUS_BLOCKED_MISSING_PURCHASE_DOCUMENT,
            LicenseLedgerPackageItem.STATUS_BLOCKED_UNKNOWN_SALES_CLASSIFICATION,
            LicenseLedgerPackageItem.STATUS_BLOCKED_MULTIPLE_REASONS,
            LicenseLedgerPackageItem.STATUS_BLOCKED_MISSING_FINAL_PARTY_SALES_INVOICE,
        ]
        for item in LicenseLedgerPackageItem.objects.select_for_update().filter(license_id__in=licence_ids, status__in=blocked_statuses):
            readiness = licence_readiness(item.license)
            if readiness["status"] == "READY":
                item.status, item.error, item.completed_at = "queued", "", None
                item.save(update_fields=["status", "error", "completed_at"])
                ready_ids.append(item.pk)
            else:
                # A separate blocker may remain after this change. Persist the
                # freshly evaluated reason so the request page never reports
                # stale unknown-sale IDs alongside a current missing purchase.
                import json
                item.status = readiness["status"].lower()
                item.error = json.dumps(readiness, sort_keys=True)
                item.save(update_fields=["status", "error"])
    if ready_ids:
        from apps.license.tasks import enqueue_license_ledger_package_job
        for job_id in LicenseLedgerPackageItem.objects.filter(pk__in=ready_ids).values_list("job_id", flat=True).distinct():
            enqueue_license_ledger_package_job.delay(job_id, ready_ids)
    return ready_ids
