from datetime import date
from decimal import Decimal
from io import BytesIO
import uuid

import pytest
from django.core.files.base import ContentFile

from apps.core.models import CompanyModel
from apps.trade.models import InvoiceDocumentAuditEvent, LicenseTrade, TradeInvoiceDocument
from apps.trade.services.invoice_document_service import InvoiceDocumentResult, InvoiceDocumentService
from apps.license.services.license_ledger_export import enrich_invoice_documents


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def company(iec, name):
    return CompanyModel.objects.create(iec=iec, name=name)


def trade(direction):
    seller = company(uuid.uuid4().hex[:10], "Supplier Ltd")
    buyer = company(uuid.uuid4().hex[:10], "Buyer Ltd")
    return LicenseTrade.objects.create(
        direction=direction,
        from_company=seller,
        to_company=buyer,
        invoice_number=f"INV-{direction}-1",
        invoice_date=date(2026, 7, 1),
    )


def test_purchase_uses_existing_uploaded_copy_without_inventing_signature_state():
    purchase = trade(LicenseTrade.DIR_PURCHASE)
    purchase.purchase_invoice_copy.save("ordinary.pdf", ContentFile(b"ordinary"))

    result = InvoiceDocumentService.resolve_purchase_document(purchase)

    assert result.document_exists is True
    assert result.signed is False
    assert result.status == "UNSIGNED"
    assert result.storage_name.endswith("ordinary.pdf")


def test_purchase_unsigned_fallback_and_missing_copy_are_not_errors():
    purchase = trade(LicenseTrade.DIR_PURCHASE)
    missing = InvoiceDocumentService.resolve_purchase_document(purchase)
    assert missing.invoice_number == purchase.invoice_number
    assert missing.document_exists is False
    assert missing.status == "COPY_UNAVAILABLE"

    purchase.purchase_invoice_copy.save("ordinary.pdf", ContentFile(b"ordinary"))
    unsigned = InvoiceDocumentService.resolve_purchase_document(purchase)
    assert unsigned.document_exists is True
    assert unsigned.signed is False
    assert unsigned.status == "UNSIGNED"


def test_sale_generation_is_idempotent_and_uses_canonical_amount(monkeypatch):
    sale = trade(LicenseTrade.DIR_SALE)
    rendered = []

    def fake_renderer(trade_obj, include_signature, **_kwargs):
        rendered.append((trade_obj.pk, include_signature))
        return BytesIO(b"%PDF canonical sale")

    monkeypatch.setattr(
        "apps.trade.services.invoice_document_service.generate_bill_of_supply_pdf", fake_renderer
    )
    first = InvoiceDocumentService.generate_sale_document(
        sale, canonical_sale_bill_inr=Decimal("1519243.00")
    )
    second = InvoiceDocumentService.generate_sale_document(
        sale, canonical_sale_bill_inr=Decimal("1519243.00")
    )

    assert first.document_id == second.document_id
    assert rendered == [(sale.pk, False)]
    document = TradeInvoiceDocument.objects.get(pk=first.document_id)
    assert document.sale_bill_inr == Decimal("1519243.00")
    assert document.file.read() == b"%PDF canonical sale"
    assert InvoiceDocumentAuditEvent.objects.filter(
        trade=sale, event=InvoiceDocumentAuditEvent.EVENT_SALE_GENERATED
    ).count() == 1


def test_changed_canonical_sale_amount_creates_auditable_new_version(monkeypatch):
    sale = trade(LicenseTrade.DIR_SALE)
    monkeypatch.setattr(
        "apps.trade.services.invoice_document_service.generate_bill_of_supply_pdf",
        lambda *_args, **_kwargs: BytesIO(b"%PDF invoice"),
    )
    old = InvoiceDocumentService.generate_sale_document(sale, canonical_sale_bill_inr=Decimal("10"))
    new = InvoiceDocumentService.generate_sale_document(sale, canonical_sale_bill_inr=Decimal("11"))

    assert old.document_id != new.document_id
    assert TradeInvoiceDocument.objects.filter(trade=sale).count() == 2


def test_direction_contract_is_enforced():
    sale = trade(LicenseTrade.DIR_SALE)
    with pytest.raises(ValueError):
        InvoiceDocumentService.resolve_purchase_document(sale)


def test_request_orchestration_enriches_canonical_rows_once(monkeypatch):
    sale = trade(LicenseTrade.DIR_SALE)
    row = {
        "id": sale.pk,
        "type": "SALE",
        "sale_bill_amount": Decimal("1519243.00"),
    }
    result = InvoiceDocumentResult(
        invoice_number=sale.invoice_number,
        document_exists=True,
        signed=False,
        status="UNSIGNED",
        document_type="SALE_GENERATED",
        storage_name="generated.pdf",
    )
    calls = []

    def resolve(*_args, **kwargs):
        calls.append(kwargs["canonical_sale_bill_inr"])
        return result

    monkeypatch.setattr(InvoiceDocumentService, "resolve", resolve)
    monkeypatch.setattr(
        InvoiceDocumentService,
        "issue_secure_link",
        lambda resolved, **_kwargs: InvoiceDocumentResult(
            **{**resolved.to_dict(), "secure_url": "/api/invoice-documents/view/opaque/"}
        ),
    )
    data = {"licenses": [{"transactions": [row], "display_transactions": [row]}]}

    enrich_invoice_documents(data, user=object())

    assert calls == [Decimal("1519243.00")]
    assert row["invoice_document"] == {
        "invoice_number": sale.invoice_number,
        "document_exists": True,
        "signed": False,
        "status": "UNSIGNED",
        "secure_url": "/api/invoice-documents/view/opaque/",
    }


def test_request_orchestration_ignores_non_invoice_transactions(monkeypatch):
    row = {"id": 99, "type": "COMMISSION_SALE", "sale_bill_amount": Decimal("10.00")}
    monkeypatch.setattr(
        InvoiceDocumentService,
        "resolve",
        lambda *_args, **_kwargs: pytest.fail("commission must not resolve an invoice document"),
    )

    enrich_invoice_documents(
        {"licenses": [{"transactions": [row], "display_transactions": []}]},
        user=object(),
    )

    assert "invoice_document" not in row
