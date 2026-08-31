"""Contract tests for the one-merged-PDF-per-licence ZIP package."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from pypdf import PdfReader
import pytest
from django.core.files.base import ContentFile

from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.license_ledger_package import (
    LicenseLedgerPackageService,
    _append_normalized_pdf,
    _final_party_sales_invoice_bundle,
    _note_pdf,
)
from apps.trade.models import LicenseTrade, LicenseTradeLine, TradeInvoiceDocument


def _dataset():
    return {
        "license_id": 91,
        "license_number": "PKG/091",
        "summary": {
            "total_cif": "100.00",
            "actual_debited_cif": "40.00",
            "actual_balance_cif": "60.00",
            "quantity_by_unit": {},
            "cif_reconciliation": "PASS — 100.00 = 40.00 + 60.00",
            "quantity_reconciliation": "PASS",
            "financial_reconciliation": "PASS",
        },
    }


def _text(pdf):
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)


def test_package_has_only_user_facing_documents_and_never_calls_manifest_renderer():
    """The archive contains no internal audit/manifest document."""
    purchase_records = [
        {"purchase_transaction_id": 11, "purchase_invoice_id": 11,
         "invoice_number": "PUR-011", "document_id": "11:main.pdf",
         "selection_result": "included: 1 source page(s)"},
        {"purchase_transaction_id": 12, "purchase_invoice_id": 12,
         "invoice_number": "PUR-012", "document_id": None,
         "selection_result": "EXCLUDED: explicit paired/copy relation"},
    ]
    sales_records = [
        {"sales_invoice_id": 351, "trade_id": 351, "invoice_number": "SAL-351",
         "classification_status": "FINAL_PARTY",
         "classification_provenance": "CANONICAL_TRANSACTION_GRAPH",
         "selection_result": "included: direct final-party SALE invoice"},
        {"sales_invoice_id": 373, "trade_id": 373, "invoice_number": "SAL-373",
         "classification_status": "INTERLINKED",
         "classification_provenance": "CANONICAL_TRANSACTION_GRAPH",
         "selection_result": "EXCLUDED: explicit paired/copy relation"},
    ]
    pdf = _note_pdf("Native document", ["Selectable native document text"])
    with (
        patch.object(LicenseLedgerPackageService, "_custom_ledger_pdf", return_value=pdf),
        patch("apps.license.services.license_ledger_package._main_purchase_invoice_bundle",
              return_value=(pdf, purchase_records, [])),
        patch("apps.license.services.license_ledger_package._final_party_sales_invoice_bundle",
              return_value=(pdf, sales_records, [])),
        patch("apps.license.services.license_ledger_export.enrich_invoice_documents"),
        patch("apps.license.services.license_ledger_export.render_license_ledger", return_value=BytesIO(pdf)),
    ):
        package = LicenseLedgerPackageService.build(
            datasets=[_dataset()], requested_by=SimpleNamespace(get_username=lambda: "auditor"),
        )

    with ZipFile(package) as archive:
        assert archive.namelist() == ["PKG-091.pdf"]
        assert all(archive.read(name).startswith(b"%PDF-") for name in archive.namelist())
        package_text = "\n".join(_text(archive.read(name)) for name in archive.namelist())
    for forbidden in ("Package Manifest", "Package ID", "Ledger and Reconciliation", "Purchase Document Decisions", "Final-Party Sales Invoice Decisions"):
        assert forbidden not in package_text


@pytest.mark.django_db
def test_manual_final_party_invoice_is_included_once_and_interlinked_sale_is_audited_excluded():
    """Packaging relies on the persisted manual decision, never a view token.

    The representative invoice number intentionally exercises the complete
    financial-year/slash/leading-zero format required in each package output.
    Database-created primary keys make this a relationship regression test,
    rather than embedding production sale or licence identifiers.
    """
    seller = CompanyModel.objects.create(name="Ledger Seller", iec="9111111111")
    final_buyer = CompanyModel.objects.create(name="Confirmed Final Buyer", iec="9222222222")
    intermediary = CompanyModel.objects.create(name="Interlinked Buyer", iec="9333333333")
    licence = LicenseDetailsModel.objects.create(license_number="MANUAL-FINAL-PACKAGE")
    item = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, quantity="2.000", cif_fc="20.00",
    )

    final_sale = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE, from_company=seller, to_company=final_buyer,
        invoice_number="LGL/2026-27/0003", invoice_date="2026-04-01",
        final_party_status=LicenseTrade.FINAL_PARTY_FINAL, final_party=final_buyer,
        final_party_classification_provenance="EXPLICIT_MANUAL_BUSINESS_CONFIRMATION",
        final_party_resolution_note="Business confirmation recorded by authorised reviewer.",
    )
    excluded_sale = LicenseTrade.objects.create(
        direction=LicenseTrade.DIR_SALE, from_company=seller, to_company=intermediary,
        invoice_number="LGL/2026-27/0004", invoice_date="2026-04-02",
        final_party_status=LicenseTrade.FINAL_PARTY_INTERMEDIATE,
        final_party_classification_provenance="CANONICAL_TRANSACTION_GRAPH_INTERLINK",
    )
    for trade in (final_sale, excluded_sale):
        LicenseTradeLine.objects.create(trade=trade, sr_number=item, qty_kg="1.000")

    document = TradeInvoiceDocument(
        trade=final_sale, version_hash="a" * 64, signed=False, sale_bill_inr="1.00",
    )
    document.file.save("final-sale.pdf", ContentFile(_note_pdf("System Invoice", [final_sale.invoice_number, final_sale.to_company.name])), save=False)
    document.save()
    bundle, records, warnings = _final_party_sales_invoice_bundle(licence.pk)

    assert warnings == []
    assert _text(bundle).count("LGL/2026-27/0003") == 1
    assert "LGL/2026-27/0004" not in _text(bundle)
    by_trade = {record["trade_id"]: record for record in records}
    assert by_trade[final_sale.pk]["classification_status"] == "FINAL_PARTY"
    assert by_trade[final_sale.pk]["classification_provenance"] == "EXPLICIT_MANUAL_BUSINESS_CONFIRMATION"
    assert by_trade[final_sale.pk]["selection_result"] == "included: direct final-party SALE invoice"
    assert by_trade[excluded_sale.pk]["classification_status"] == "INTERLINKED"
    assert by_trade[excluded_sale.pk]["selection_result"] == "EXCLUDED"
    # Capability tokens are access credentials: no raw token may reach the
    # package decision records or a manifest constructed from them.
    assert "TVc32VwiSKQPblcjySQLk1WAlz4B4Xsa_Qpy2FxdQEQ" not in str(records)


def test_removed_manifest_renderer_is_not_part_of_the_package_api():
    """The audit PDF exposes canonical IDs and evidence, never credentials."""
    context = {
        "license_number": "MANUAL-FINAL-MANIFEST", "license_id": 77,
        "generated_at": "2026-08-28", "requested_by": "auditor", "package_id": "test-package",
        "environment": "test", "status": "completed", "ledger_totals": _dataset()["summary"],
        "purchase_records": [], "warnings": [], "errors": [], "files": [],
        "sales_records": [
            {
                "sales_invoice_id": 9001, "trade_id": 9001, "document_id": 7001,
                "invoice_number": "LGL/2026-27/0003", "classification_status": "FINAL_PARTY",
                "classification_provenance": "EXPLICIT_MANUAL_BUSINESS_CONFIRMATION",
                "selection_result": "included: direct final-party SALE invoice",
            },
            {
                "sales_invoice_id": 9002, "trade_id": 9002, "document_id": 7002,
                "invoice_number": "LGL/2026-27/0004", "classification_status": "INTERLINKED",
                "classification_provenance": "CANONICAL_TRANSACTION_GRAPH_INTERLINK",
                "selection_result": "EXCLUDED: explicit paired/copy relation",
            },
        ],
    }
    # This old manifest context is deliberately not rendered.  Package output
    # must never disclose its classifications, provenance, IDs, or decisions.
    assert "Package Manifest" not in str(context)


def test_normalized_package_page_is_a4_portrait_even_for_a_landscape_source():
    """A landscape invoice may not turn a final licence package landscape."""
    from pypdf import PdfWriter
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas

    source = BytesIO()
    canvas = Canvas(source, pagesize=landscape(A4))
    canvas.drawString(100, 100, "Landscape source invoice")
    canvas.save()
    writer = PdfWriter()
    _append_normalized_pdf(writer, source.getvalue())
    output = BytesIO(); writer.write(output)
    page = PdfReader(output).pages[0]
    assert abs(float(page.mediabox.width) - A4[0]) < 0.1
    assert abs(float(page.mediabox.height) - A4[1]) < 0.1


def test_build_sections_uses_the_immutable_four_section_order():
    pdf = _note_pdf("Native document", ["section"])
    with (
        patch.object(LicenseLedgerPackageService, "_custom_ledger_pdf", return_value=pdf),
        patch("apps.license.services.license_ledger_package._main_purchase_invoice_bundle", return_value=(pdf, [], [])),
        patch("apps.license.services.license_ledger_package._final_party_sales_invoice_bundle", return_value=(pdf, [], [])),
        patch("apps.license.services.license_ledger_export.enrich_invoice_documents"),
        patch("apps.license.services.license_ledger_export.render_license_ledger", return_value=BytesIO(pdf)),
    ):
        sections = LicenseLedgerPackageService.build_sections(
            dataset=_dataset(), requested_by=SimpleNamespace(get_username=lambda: "auditor"),
        )
    assert [name for name, _content in sections] == [
        "01-custom-ledger.pdf", "02-financial-ledger.pdf",
        "03-main-purchase-invoices.pdf", "04-final-party-sales-invoices.pdf",
    ]
