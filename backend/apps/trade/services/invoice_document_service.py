"""Canonical physical-document strategies for trade invoices.

This module never decides ledger eligibility and never computes accounting.
Callers pass the canonical sale bill amount already present on their ledger
transaction.  PURCHASE resolves the user's upload; SALE renders and persists
the existing Bill of Supply for that exact canonical version.
"""

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import hashlib
import json
from typing import Optional

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from apps.trade.bill_of_supply_pdf import generate_bill_of_supply_pdf
from apps.trade.models import (
    InvoiceDocumentAuditEvent,
    LicenseTrade,
    TradeInvoiceDocument,
    q2,
)


@dataclass(frozen=True)
class InvoiceDocumentResult:
    invoice_number: str
    document_exists: bool
    signed: bool
    status: str
    document_type: str
    document_id: Optional[int] = None
    generated_at: Optional[str] = None
    secure_url: Optional[str] = None
    storage_name: Optional[str] = None
    document_version: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class InvoiceDocumentService:
    PURCHASE_UPLOADED = "PURCHASE_UPLOADED"
    SALE_GENERATED = "SALE_GENERATED"

    @staticmethod
    def get_persisted_sale_document(trade: LicenseTrade):
        """Return the canonical latest immutable sale PDF without rendering it.

        Package workers use this same domain service as the authenticated
        invoice view, but must fail closed rather than silently creating a new
        invoice while assembling an audit package.
        """
        if trade.direction != LicenseTrade.DIR_SALE:
            raise ValueError("Sale document resolution requires a SALE trade")
        return TradeInvoiceDocument.objects.filter(trade=trade).order_by("-generated_on", "-id").first()

    @staticmethod
    def resolve_purchase_document(trade: LicenseTrade) -> InvoiceDocumentResult:
        if trade.direction != LicenseTrade.DIR_PURCHASE:
            raise ValueError("Purchase document resolution requires a PURCHASE trade")
        # The established schema has one optional supplier upload and no
        # separate signed-copy column or signature metadata for that upload.
        upload = trade.purchase_invoice_copy
        exists = bool(upload and upload.name)
        return InvoiceDocumentResult(
            invoice_number=trade.invoice_number or "",
            document_exists=exists,
            signed=False,
            status="UNSIGNED" if exists else "COPY_UNAVAILABLE",
            document_type=InvoiceDocumentService.PURCHASE_UPLOADED,
            storage_name=upload.name if exists else None,
        )

    @staticmethod
    def _sale_version_payload(trade: LicenseTrade, canonical_sale_bill_inr: Decimal, signed: bool):
        lines = [
            {
                "id": line.id,
                "description": line.description,
                "quantity": str(line.qty_kg),
                "amount_inr": str(q2(line.amount_inr)),
                "item_id": line.sr_number_id,
            }
            for line in trade.lines.all().order_by("id")
        ]
        incentive_lines = [
            {"id": line.id, "amount_inr": str(q2(line.amount_inr)), "license_id": line.incentive_license_id}
            for line in trade.incentive_lines.all().order_by("id")
        ]
        return {
            "trade_id": trade.pk,
            "invoice_number": trade.invoice_number or "",
            "invoice_date": trade.invoice_date.isoformat() if trade.invoice_date else None,
            "from_company_id": trade.from_company_id,
            "to_company_id": trade.to_company_id,
            "sale_bill_inr": str(q2(canonical_sale_bill_inr)),
            "signed": signed,
            "lines": lines,
            "incentive_lines": incentive_lines,
        }

    @classmethod
    def generate_sale_document(cls, trade: LicenseTrade, *, canonical_sale_bill_inr: Decimal):
        if trade.direction != LicenseTrade.DIR_SALE:
            raise ValueError("Sale invoice generation requires a SALE trade")
        canonical_amount = q2(canonical_sale_bill_inr)
        # Signature is factual: the existing renderer can sign only when the
        # issuing company has a stored signature.
        signed = bool(trade.from_company and getattr(trade.from_company, "signature", None))
        payload = cls._sale_version_payload(trade, canonical_amount, signed)
        version_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        existing = TradeInvoiceDocument.objects.filter(trade=trade, version_hash=version_hash).first()
        if existing:
            return cls._sale_result(existing)

        pdf = generate_bill_of_supply_pdf(
            trade, include_signature=signed, canonical_total_inr=canonical_amount,
        )
        content = pdf.getvalue() if hasattr(pdf, "getvalue") else bytes(pdf)
        filename = f"sale_invoice_{trade.pk}_{version_hash[:12]}.pdf"
        try:
            with transaction.atomic():
                document = TradeInvoiceDocument(
                    trade=trade, version_hash=version_hash, signed=signed,
                    sale_bill_inr=canonical_amount,
                )
                document.file.save(filename, ContentFile(content), save=False)
                document.save()
                InvoiceDocumentAuditEvent.objects.create(
                    event=InvoiceDocumentAuditEvent.EVENT_SALE_GENERATED,
                    trade=trade,
                    metadata={"version": version_hash[:12], "signed": signed},
                )
        except IntegrityError:
            document = TradeInvoiceDocument.objects.get(trade=trade, version_hash=version_hash)
        return cls._sale_result(document)

    @classmethod
    def resolve(cls, trade: LicenseTrade, *, canonical_sale_bill_inr=None):
        if trade.direction == LicenseTrade.DIR_PURCHASE:
            return cls.resolve_purchase_document(trade)
        if trade.direction == LicenseTrade.DIR_SALE:
            if canonical_sale_bill_inr is None:
                raise ValueError("canonical_sale_bill_inr is required for SALE")
            return cls.generate_sale_document(trade, canonical_sale_bill_inr=canonical_sale_bill_inr)
        raise ValueError("Invoice documents are supported only for PURCHASE and SALE")

    @staticmethod
    def issue_secure_link(result: InvoiceDocumentResult, *, trade, user, base_url=""):
        """Attach the shared opaque viewer URL without leaking storage data."""
        if not result.document_exists:
            return result
        from apps.trade.services.invoice_secure_links import issue_invoice_view_link

        link = issue_invoice_view_link(
            trade=trade,
            storage_name=result.storage_name,
            document_type=result.document_type,
            user=user,
            signed=result.signed,
            document_version=result.document_version or "",
            base_url=base_url,
        )
        return replace(result, secure_url=link["secure_url"])

    @classmethod
    def _sale_result(cls, document):
        return InvoiceDocumentResult(
            invoice_number=document.trade.invoice_number or "",
            document_exists=True,
            signed=document.signed,
            status="SIGNED" if document.signed else "UNSIGNED",
            document_type=cls.SALE_GENERATED,
            document_id=document.pk,
            generated_at=document.generated_on.isoformat(),
            storage_name=document.file.name,
            document_version=document.version_hash,
        )
