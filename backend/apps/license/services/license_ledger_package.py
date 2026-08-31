"""Read-only assembly of the native licence-ledger download package.

This module selects only direct ``LicenseTrade`` relationships and delegates
all invoice presentation to the established server-side renderers. It never
updates a model, generates an invoice number, or exposes storage names.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape


class PackageDocumentError(RuntimeError):
    """A required, selected package document could not be rendered/read.

    Callers must mark the licence work item failed; it is intentionally not
    converted into a blank page or an apparent `not_applicable` section.
    """


def _safe_part(value: object) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip(".-") or "licence"


def _pdf_bytes(value) -> bytes:
    return value.getvalue() if hasattr(value, "getvalue") else bytes(value)


def _page_count(pdf: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(BytesIO(pdf)).pages)


def _note_pdf(title: str, lines: list[str]) -> bytes:
    """A native, selectable explanatory/separator page."""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 10 * mm)]
    story.extend(Paragraph(escape(str(line)), styles["BodyText"]) for line in lines)
    doc.build(story)
    return output.getvalue()


def _append_pdf(writer, pdf: bytes) -> None:
    from pypdf import PdfReader
    for page in PdfReader(BytesIO(pdf)).pages:
        writer.add_page(page)


def _append_normalized_pdf(writer, pdf: bytes) -> None:
    """Add every source page to a portrait A4 canvas without distortion.

    Final licence packages are an A4-portrait document.  Invoice uploads may
    use arbitrary media boxes (including landscape); those pages are scaled
    down where needed and centred on a white portrait A4 page.  This avoids
    both clipping and a landscape page leaking into the final merge.
    """
    from pypdf import PdfReader, PageObject, Transformation

    for source in PdfReader(BytesIO(pdf)).pages:
        source_width, source_height = float(source.mediabox.width), float(source.mediabox.height)
        target_width, target_height = A4
        margin = 10 * mm
        # Never enlarge a smaller source page: preserve its native appearance
        # and centre it; only oversized pages are reduced to the print area.
        scale = min(1.0, (target_width - 2 * margin) / source_width, (target_height - 2 * margin) / source_height)
        page = PageObject.create_blank_page(width=target_width, height=target_height)
        page.merge_transformed_page(source, Transformation().scale(scale).translate(
            (target_width - source_width * scale) / 2,
            (target_height - source_height * scale) / 2,
        ))
        writer.add_page(page)


def _read_upload(upload) -> bytes:
    """Read one authorised upload sequentially; never pass a storage path to ZIP."""
    with upload.open("rb") as source:
        return b"".join(chunk for chunk in source.chunks())


def _image_pdf(image_bytes: bytes) -> bytes:
    """Fit an uploaded image onto A4 without cropping it."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    canvas = Canvas(output, pagesize=A4)
    image = ImageReader(BytesIO(image_bytes))
    width, height = image.getSize()
    page_width, page_height = A4
    max_width, max_height = page_width - 30 * mm, page_height - 30 * mm
    scale = min(max_width / width, max_height / height)
    draw_width, draw_height = width * scale, height * scale
    canvas.drawImage(image, (page_width - draw_width) / 2, (page_height - draw_height) / 2,
                     draw_width, draw_height, preserveAspectRatio=True, mask="auto")
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def _purchase_candidates(license_id: int) -> list[dict]:
    """Use the shared canonical direct/main-purchase relationship selector."""
    from apps.license.models import LicenseDetailsModel
    from apps.license.services.license_invoice_relations import get_main_purchase_invoices
    return get_main_purchase_invoices(LicenseDetailsModel.objects.get(pk=license_id))


def _main_purchase_invoice_bundle(license_id: int) -> tuple[bytes, list[dict], list[str]]:
    """Merge every applicable direct supplier PDF/image, or fail closed."""
    from pypdf import PdfWriter

    writer, records, warnings = PdfWriter(), [], []
    candidates = _purchase_candidates(license_id)
    included = [candidate for candidate in candidates if candidate["selection_result"] == "INCLUDED"]
    records.extend(dict(candidate) for candidate in candidates if candidate not in included)
    if not included:
        return b"", candidates, warnings
    from apps.trade.models import LicenseTrade
    trades = LicenseTrade.objects.in_bulk([candidate["source_id"] for candidate in included])

    seen_documents: set[str] = set()
    for candidate in included:
        trade = trades[candidate["source_id"]]
        upload = trade.purchase_invoice_copy
        record = dict(candidate)
        record["invoice_number"] = trade.invoice_number or "Invoice number missing in system record"
        record["document_id"] = None
        if not upload or not upload.name:
            record["selection_result"] = "MISSING_MAIN_PURCHASE_INVOICE"
            records.append(record)
            raise PackageDocumentError(f"MISSING_MAIN_PURCHASE_INVOICE transaction {trade.pk}")
        # A storage name is used only to deduplicate already-authorised direct
        # records; it is never emitted or trusted as a ZIP filename.
        identity = f"{trade.pk}:{upload.name}"
        if identity in seen_documents:
            record["selection_result"] = "excluded: duplicate canonical document identity"
            records.append(record)
            continue
        seen_documents.add(identity)
        record["document_id"] = identity
        try:
            source = _read_upload(upload)
            if source.startswith(b"%PDF-"):
                if not source:
                    raise ValueError("zero-byte PDF")
                source_pages, rendered = _page_count(source), source
            else:
                from PIL import Image
                with Image.open(BytesIO(source)) as probe:
                    probe.verify()
                rendered, source_pages = _image_pdf(source), 1
            _append_normalized_pdf(writer, rendered)
            record["selection_result"] = f"included: {source_pages} source page(s)"
            record["source_page_count"] = source_pages
            record["sha256"] = hashlib.sha256(source).hexdigest()
        except PackageDocumentError:
            raise
        except Exception as exc:
            record["selection_result"] = "excluded: document is unreadable or unsupported"
            records.append(record)
            raise PackageDocumentError(f"Purchase invoice document is unreadable for transaction {trade.pk}") from exc
        records.append(record)
    output = BytesIO()
    writer.write(output)
    return (output.getvalue() if len(writer.pages) else b""), records, warnings


def _final_party_sales_candidates(license_id: int) -> list[dict]:
    """Use the shared selector; it refuses to infer a final party."""
    from apps.license.models import LicenseDetailsModel
    from apps.license.services.license_invoice_relations import get_final_party_sales_invoices
    return get_final_party_sales_invoices(LicenseDetailsModel.objects.get(pk=license_id))


def _final_party_sales_invoice_bundle(license_id: int) -> tuple[bytes, list[dict], list[str]]:
    """Merge the canonical persisted invoice document for every final sale."""
    from pypdf import PdfWriter

    writer, records, warnings = PdfWriter(), [], []
    candidates = _final_party_sales_candidates(license_id)
    # The persisted FINAL classification names the actual buyer on whose
    # system invoice we are relying. Keep this defensive invariant here as
    # well: a FINAL classification for another party cannot make this invoice
    # a final-party invoice copy.
    included = [candidate for candidate in candidates if candidate["selection_result"] == "INCLUDED"]
    records.extend(dict(candidate) for candidate in candidates if candidate not in included)
    if not included:
        # ``not_applicable`` is valid only when every discovered sale was
        # positively excluded as intermediate/interlinked.  An unclassified
        # direct sale is a schema/audit failure, not evidence that there was
        # no final-party sale.
        unresolved = [candidate for candidate in candidates
                      if candidate.get("classification_status") not in ("INTERLINKED", "NOT_APPLICABLE")
                      and not candidate.get("is_interlinked")]
        if unresolved:
            sale_ids = ", ".join(str(candidate["source_id"]) for candidate in unresolved)
            raise PackageDocumentError(f"FINAL_PARTY_CLASSIFICATION_REQUIRED sale(s) {sale_ids}")
        return b"", candidates, warnings
    from apps.trade.models import LicenseTrade
    trades = LicenseTrade.objects.in_bulk([candidate["source_id"] for candidate in included])
    seen: set[int] = set()
    for candidate in included:
        trade = trades[candidate["source_id"]]
        record = dict(candidate)
        record["invoice_number"] = trade.invoice_number or "Invoice number missing in system record"
        if trade.pk in seen:
            record["selection_result"] = "excluded: duplicate canonical sales invoice"
            records.append(record)
            continue
        seen.add(trade.pk)
        try:
            # Never call a request-authenticated endpoint from Celery and never
            # regenerate an invoice copy here.  The shared canonical service
            # resolves the immutable persisted document used by the invoice view.
            from apps.trade.services.invoice_document_service import InvoiceDocumentService
            document = InvoiceDocumentService.get_persisted_sale_document(trade)
            if document is None or not document.file or not document.file.name:
                record["selection_result"] = "MISSING_FINAL_PARTY_SALES_INVOICE"
                records.append(record)
                raise PackageDocumentError(f"MISSING_FINAL_PARTY_SALES_INVOICE sale {trade.pk}")
            pdf = _read_upload(document.file)
            if not pdf:
                raise PackageDocumentError(f"MISSING_FINAL_PARTY_SALES_INVOICE zero-byte document sale {trade.pk}")
            if not pdf.startswith(b"%PDF-"):
                raise PackageDocumentError(f"MISSING_FINAL_PARTY_SALES_INVOICE unreadable document sale {trade.pk}")
            pages = _page_count(pdf)
            _append_normalized_pdf(writer, pdf)
            record["selection_result"] = "included: direct final-party SALE invoice"
            record["document_id"] = document.pk
            record["source_page_count"] = pages
            record["sha256"] = hashlib.sha256(pdf).hexdigest()
        except PackageDocumentError:
            raise
        except Exception as exc:
            record["selection_result"] = "excluded: system invoice renderer failed"
            records.append(record)
            raise PackageDocumentError(f"Sales invoice renderer failed for transaction {trade.pk}") from exc
        records.append(record)
    output = BytesIO()
    writer.write(output)
    return (output.getvalue() if len(writer.pages) else b""), records, warnings


def _ledger_totals(dataset: dict) -> dict:
    summary = dataset.get("summary") or {}
    total_cif = summary.get("total_cif") or summary.get("total_license_cif") or summary.get("opening_balance")
    balance_cif = summary.get("actual_balance_cif") or summary.get("current_balance")
    debited_cif = summary.get("actual_debited_cif") or summary.get("used_cif")
    if debited_cif is None and total_cif is not None and balance_cif is not None:
        debited_cif = total_cif - balance_cif
    return {
        "total_cif": total_cif,
        "actual_debited_cif": debited_cif,
        "actual_balance_cif": balance_cif,
        "quantity_by_unit": summary.get("quantity_by_unit") or {},
        "cif_reconciliation": summary.get("cif_reconciliation") or "Canonical ledger values included",
        "quantity_reconciliation": summary.get("quantity_reconciliation") or "Canonical ledger values included",
        "financial_reconciliation": summary.get("financial_reconciliation") or "Canonical financial ledger included",
    }


class LicenseLedgerPackageService:
    """Build one merged canonical PDF per selected licence; read-only."""

    @classmethod
    def build(cls, *, datasets: list[dict], requested_by, base_url: str = "") -> BytesIO:
        package = BytesIO()
        with ZipFile(package, "w", ZIP_DEFLATED, allowZip64=True) as archive:
            for dataset in datasets:
                licence = _safe_part(dataset["license_number"])
                archive.writestr(f"{licence}.pdf", cls._build_license_pdf(
                    dataset=dataset, requested_by=requested_by, base_url=base_url,
                ))
        package.seek(0)
        return package

    @classmethod
    def build_merged_pdf(cls, *, datasets: list[dict], requested_by, base_url: str = "") -> BytesIO:
        """Merge per-licence canonical PDFs for the legacy single-PDF route."""
        from pypdf import PdfWriter
        writer = PdfWriter()
        for dataset in datasets:
            _append_pdf(writer, cls._build_license_pdf(
                dataset=dataset, requested_by=requested_by, base_url=base_url,
            ))
        output = BytesIO(); writer.write(output); output.seek(0)
        return output

    @classmethod
    def _build_license_pdf(cls, *, dataset: dict, requested_by, base_url: str) -> bytes:
        """Merge this licence's selected canonical documents in display order."""
        from pypdf import PdfWriter
        sections = cls.build_sections(dataset=dataset, requested_by=requested_by, base_url=base_url)
        writer = PdfWriter()
        for _name, content in sections:
            if content:
                _append_normalized_pdf(writer, content)
        output = BytesIO(); writer.write(output)
        return output.getvalue()

    @classmethod
    def build_sections(cls, *, dataset: dict, requested_by, base_url: str = "") -> list[tuple[str, bytes]]:
        """Build canonical package sections in their immutable business order.

        The asynchronous storage workflow persists these exact bytes under the
        returned names before making the merged per-licence PDF.  Empty
        optional invoice sections are deliberately omitted rather than padded
        with a synthetic blank page.
        """
        from apps.license.services.license_ledger_export import generate_license_ledger_statement_pdf

        financial = _pdf_bytes(generate_license_ledger_statement_pdf(
            canonical_data={"licenses": [dataset], "company_groups": [], "grand_total": {}},
            user=requested_by, base_url=base_url,
        ))
        purchase, _purchase_records, _purchase_warnings = _main_purchase_invoice_bundle(dataset["license_id"])
        sales, _sales_records, _sales_warnings = _final_party_sales_invoice_bundle(dataset["license_id"])
        sections = [
            ("01-custom-ledger.pdf", cls._custom_ledger_pdf(dataset)),
            ("02-financial-ledger.pdf", financial),
        ]
        if purchase:
            sections.append(("03-main-purchase-invoices.pdf", purchase))
        if sales:
            sections.append(("04-final-party-sales-invoices.pdf", sales))
        return sections

    @classmethod
    def build_ledger_only_draft(cls, *, dataset: dict, requested_by, base_url: str = "") -> bytes:
        """Create a clearly separate draft without purchase-invoice pages.

        This is deliberately not used by verified request items or ZIPs. It
        is an operator-requested ledger preview while a purchase document is
        being recovered.
        """
        from pypdf import PdfWriter
        from apps.license.services.license_ledger_export import generate_license_ledger_statement_pdf
        financial = _pdf_bytes(generate_license_ledger_statement_pdf(
            canonical_data={"licenses": [dataset], "company_groups": [], "grand_total": {}}, user=requested_by, base_url=base_url,
        ))
        writer = PdfWriter()
        _append_normalized_pdf(writer, cls._custom_ledger_pdf(dataset))
        _append_normalized_pdf(writer, financial)
        # A draft is allowed to omit only unavailable purchase documents.  It
        # still includes every verified final-party sales invoice so it is a
        # useful review file rather than an unnecessarily incomplete one.
        sales, _records, _warnings = _final_party_sales_invoice_bundle(dataset["license_id"])
        if sales:
            _append_normalized_pdf(writer, sales)
        output = BytesIO(); writer.write(output)
        return output.getvalue()

    @staticmethod
    def _custom_ledger_pdf(dataset: dict) -> bytes:
        """Package hook for the one canonical native Customs Ledger renderer."""
        from apps.license.models import LicenseDetailsModel
        from apps.license.services.custom_ledger_pdf import get_custom_ledger_data, render_custom_ledger_pdf
        licence = LicenseDetailsModel.objects.get(pk=dataset["license_id"])
        return render_custom_ledger_pdf(get_custom_ledger_data(licence, canonical_dataset=dataset))
