"""Presentation-only PDF renderer for the canonical Financial License Ledger.

This module deliberately imports no model, selector, or accounting service.
It formats the already-filtered, already-calculated canonical DTO only.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from shared.pdf.builders import format_indian_number


NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#1F4E78")
PALE_BLUE = colors.HexColor("#D9EAF7")
PALE_RED = colors.HexColor("#FCE8E6")
PALE_GREEN = colors.HexColor("#EDF7F0")
PALE_SALE = colors.HexColor("#EEF4FB")
GREY = colors.HexColor("#666666")
# A4 portrait width less consistent ten-millimetre print margins.
PRINTABLE_WIDTH = 190 * mm
# Amounts must be kept on one line.  On portrait A4, six fully formatted
# Indian-number columns cannot coexist with the five descriptive columns at a
# readable size.  Render the two logical halves as companion tables instead
# of letting ReportLab paint numbers through the final cell border.
DETAIL_DESCRIPTION_WIDTHS = (24 * mm, 52 * mm, 38 * mm, 20 * mm, 56 * mm)
DETAIL_AMOUNT_WIDTHS = (22 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm)


# Ledger exports are archival documents.  Embed a TrueType font when the
# runtime provides it so text remains selectable and portable rather than
# relying solely on a viewer's base-14 Helvetica substitution.
try:
    pdfmetrics.registerFont(TTFont("FinancialLedger", "/System/Library/Fonts/Supplemental/Verdana.ttf"))
    pdfmetrics.registerFont(TTFont("FinancialLedgerBold", "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"))
    FONT_REGULAR, FONT_BOLD = "FinancialLedger", "FinancialLedgerBold"
except Exception:  # Linux deployment image may not have macOS supplemental fonts.
    FONT_REGULAR, FONT_BOLD = "Helvetica", "Helvetica-Bold"


def _date(value) -> str:
    return value.strftime("%d-%b-%Y") if isinstance(value, (date, datetime)) else "—"


def _number(value) -> str:
    return "—" if value is None else format_indian_number(Decimal(str(value)), 2)


def _text(value) -> str:
    return escape(str(value)) if value not in (None, "") else "—"


def _cell_text(value, *, bold=False, align="LEFT"):
    """Wrap long names/items safely so PDF rows never overlap each other."""
    tag_open = "<b>" if bold else ""
    tag_close = "</b>" if bold else ""
    return Paragraph(
        f"{tag_open}{_text(value)}{tag_close}",
        ParagraphStyle(
            "LedgerCell", fontName=FONT_REGULAR, fontSize=6.2, leading=7.4,
            alignment={"LEFT": 0, "RIGHT": 2, "CENTER": 1}[align], splitLongWords=1,
        ),
    )

def _invoice_cell(row):
    """Render only canonical document metadata; never resolve a document here."""
    document = row.get("invoice_document") or {}
    # The canonical ledger selector already carries the system invoice number
    # on the transaction.  Secure document enrichment is optional, so it must
    # never erase that value when no uploaded-copy metadata exists.
    canonical_number = row.get("invoice_number")
    number = _text(document.get("invoice_number") or canonical_number)
    url = document.get("secure_url") if document.get("document_exists") else None
    if url:
        status = "SIGNED" if document.get("signed") else "UNSIGNED"
        return Paragraph(
            f'<link href="{escape(str(url), {"\"": "&quot;"})}" color="#1F4E78"><u>{number}</u></link><br/>'
            f'<font size="5.5" color="#666666">{status}</font>',
            ParagraphStyle("InvoiceLink", fontName=FONT_REGULAR, fontSize=6.2, leading=7.4, splitLongWords=1),
        )
    if document.get("status") == "COPY_UNAVAILABLE":
        return Paragraph(
            f'{number}<br/><font size="5.5" color="#666666">Copy unavailable</font>',
            ParagraphStyle("InvoiceUnavailable", fontName=FONT_REGULAR, fontSize=6.2, leading=7.4, splitLongWords=1),
        )
    return _cell_text(document.get("invoice_number") or canonical_number)


def _header_cell(value):
    return Paragraph(_text(value), ParagraphStyle(
        "LedgerHeader", fontName=FONT_BOLD, fontSize=6.2, leading=7.1,
        textColor=colors.white, alignment=TA_CENTER, splitLongWords=1,
    ))


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#B4C7E7"))
    canvas.line(doc.leftMargin, 10 * mm, A4[0] - doc.rightMargin, 10 * mm)
    canvas.setFillColor(GREY)
    canvas.setFont(FONT_REGULAR, 7)
    canvas.drawString(doc.leftMargin, 6.5 * mm, "License Manager · Financial Trade Ledger")
    label = f"Page {doc.page}"
    canvas.drawString(A4[0] - doc.rightMargin - stringWidth(label, FONT_REGULAR, 7), 6.5 * mm, label)
    canvas.restoreState()


def _table(rows, widths, *, numeric_from=None, total_row=None, font_size=7, transaction_rows=None, total_label_through=None):
    # LongTable calculates and splits the transaction body incrementally.  A
    # regular Table can leave a sparse page when a wrapped row is taller than
    # its remaining frame, particularly on portrait A4.
    table = LongTable(rows, repeatRows=1, colWidths=widths, hAlign="LEFT", splitByRow=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if len(rows) > 1:
        if numeric_from is not None:
            commands.append(("ALIGN", (numeric_from, 1), (-1, -1), "RIGHT"))
        commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]))
    if total_row is not None:
        commands.extend([
            ("FONTNAME", (0, total_row), (-1, total_row), FONT_BOLD),
            ("BACKGROUND", (0, total_row), (-1, total_row), PALE_BLUE),
        ])
        if total_label_through is not None:
            commands.extend([
                ("SPAN", (0, total_row), (total_label_through, total_row)),
                ("ALIGN", (0, total_row), (total_label_through, total_row), "LEFT"),
                ("LEFTPADDING", (0, total_row), (total_label_through, total_row), 5),
            ])
    for row_index, transaction_type in transaction_rows or []:
        # Make linked purchase/sale entries immediately scannable without
        # changing the canonical debit/credit values shown in their columns.
        background = PALE_GREEN if transaction_type == "PURCHASE" else PALE_SALE
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), background))
    table.setStyle(TableStyle(commands))
    return table


def _render_list(elements, canonical_data, styles) -> None:
    elements.append(Paragraph("FINANCIAL TRADE LEDGER", styles["LedgerTitle"]))
    elements.append(Paragraph("License Summary · Purchase and Sale Bills in INR", styles["LedgerSubtitle"]))
    elements.append(Spacer(1, 5 * mm))

    # Built-in PDF fonts do not contain the Unicode rupee glyph; using the
    # unambiguous ISO currency code avoids a missing-glyph box in statements.
    headers = ["License Number", "Type", "Date", "1st Purchase Date", "SION Norms",
               "Balance ($)", "Purchase (INR)", "Sale (INR)", "P/L (INR)"]
    company_groups = canonical_data.get("company_groups") or []
    if not company_groups:
        elements.append(Paragraph("No ledger records", styles["LedgerSubtitle"]))
    for group in company_groups:
        company_name = group.get("company_name") or "-"
        elements.append(Paragraph(_text(company_name), styles["CompanyHeading"]))
        # Company/SION membership and every total are supplied by the
        # canonical reporting service.  This renderer deliberately performs
        # no grouping, summation, or interpretation of SION display text.
        for sion_group in group.get("sion_groups") or []:
            sion_label = sion_group.get("sion_label") or "N/A / EMPTY"
            count = sion_group.get("license_count", 0)
            elements.append(Paragraph(
                f"SION: {_text(sion_label)}  ·  License Count: {count}",
                styles["SionHeading"],
            ))
            rows = [[_header_cell(header) for header in headers]]
            for data in sion_group.get("licenses") or []:
                rows.append([
                    _cell_text(data.get("license_number")), _cell_text(data.get("license_type")),
                    _date(data.get("license_date")), _date(data.get("first_purchase_date")),
                    _cell_text(data.get("sion_norms")), _number(data.get("current_balance")),
                    _number(data.get("purchase_bill_inr")), _number(data.get("sale_bill_inr")),
                    _number(data.get("profit_loss_inr")),
                ])
            rows.append([
                f"Total — SION {sion_label}", "", "", "", "",
                _number(sion_group.get("total_balance")),
                _number(sion_group.get("total_purchase_bill_inr")),
                _number(sion_group.get("total_sale_bill_inr")),
                _number(sion_group.get("total_profit_loss_inr")),
            ])
            elements.append(_table(
                rows, [19*mm, 12*mm, 15*mm, 18*mm, 21*mm, 18*mm, 21*mm, 21*mm, 20*mm],
                numeric_from=5, total_row=len(rows)-1,
            ))
            elements.append(Spacer(1, 3 * mm))

        company_total = [["", "Balance ($)", "Purchase (INR)", "Sale (INR)", "P/L (INR)"], [
            f"COMPANY TOTAL — {company_name}", _number(group.get("total_balance")),
            _number(group.get("total_purchase_bill_inr")), _number(group.get("total_sale_bill_inr")),
            _number(group.get("total_profit_loss_inr")),
        ]]
        elements.append(_table(
            company_total, [70*mm, 24*mm, 32*mm, 32*mm, 32*mm], numeric_from=1, total_row=1,
        ))
        elements.append(Spacer(1, 6 * mm))

    grand_total = canonical_data.get("grand_total")
    if grand_total:
        rows = [["", "Licenses", "Balance ($)", "Purchase (INR)", "Sale (INR)", "P/L (INR)"], [
            "GRAND TOTAL", str(grand_total.get("license_count", 0)),
            _number(grand_total.get("total_balance")),
            _number(grand_total.get("total_purchase_bill_inr")),
            _number(grand_total.get("total_sale_bill_inr")),
            _number(grand_total.get("total_profit_loss_inr")),
        ]]
        elements.append(_table(
            rows, [55*mm, 16*mm, 28*mm, 30*mm, 30*mm, 31*mm], numeric_from=1, total_row=1,
            font_size=8,
        ))


def _metadata_table(data):
    summary = data["summary"]
    rows = [
        ["License Number", data.get("license_number") or "—", "License Date", _date(data.get("license_date")),
         "Expiry Date", _date(data.get("expiry_date"))],
        ["Exporter", data.get("exporter_name") or "—", "Total Value", _number(summary.get("total_purchase")),
         "Balance ($)", _number(summary.get("current_balance"))],
        ["1st Purchase Date", _date(data.get("first_purchase_date")), "SION Norms", data.get("sion_norms") or "—",
         "Purchase Bill", "YES" if data.get("has_purchase_bill") else "NO PURCHASE BILL"],
        ["Purchase (INR)", _number(summary.get("total_purchase_bill_inr")),
         "Sale (INR)", _number(summary.get("total_sale_bill_inr")),
         "P/L (INR)", _number(summary.get("total_profit_loss"))],
    ]
    # Plain strings do not wrap in ReportLab tables, which caused long labels
    # such as “1st Purchase Date” and long exporter names to collide.  Use
    # paragraph cells and give label columns enough room for clear scanning.
    label_style = ParagraphStyle("LedgerMetadataLabel", fontName=FONT_BOLD, fontSize=8, leading=10, splitLongWords=1)
    value_style = ParagraphStyle("LedgerMetadataValue", fontName=FONT_REGULAR, fontSize=8, leading=10, splitLongWords=1)
    wrapped_rows = [
        [Paragraph(_text(value), label_style if index % 2 == 0 else value_style)
         for index, value in enumerate(row)]
        for row in rows
    ]
    table = Table(wrapped_rows, colWidths=[22*mm, 42*mm, 21*mm, 35*mm, 21*mm, 49*mm])
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
        ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE), ("BACKGROUND", (2, 0), (2, -1), PALE_BLUE),
        ("BACKGROUND", (4, 0), (4, -1), PALE_BLUE),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD), ("FONTNAME", (2, 0), (2, -1), FONT_BOLD),
        ("FONTNAME", (4, 0), (4, -1), FONT_BOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if not data.get("has_purchase_bill"):
        commands.extend([("BACKGROUND", (5, 2), (5, 2), PALE_RED), ("TEXTCOLOR", (5, 2), (5, 2), colors.HexColor("#C00000"))])
    table.setStyle(TableStyle(commands))
    return table


def _render_detail(elements, data, styles) -> None:
    elements.append(Paragraph("LICENSE LEDGER STATEMENT", styles["LedgerTitle"]))
    elements.append(Paragraph(f"[ {_text(data.get('license_type'))} ]", styles["LedgerSubtitle"]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_metadata_table(data))
    elements.append(Spacer(1, 5 * mm))

    groups = data.get("company_groups") or data.get("license_wise_companies") or []
    if not groups:
        groups = [{"company_id": None, "company_name": "LICENSE LEDGER",
                   "purchase_total": None, "sale_total": None, "current_balance": None, "profit_loss": None}]
    all_rows = ([data["opening_display"]] if data.get("opening_display") else []) + list(data.get("display_transactions") or [])
    description_headers = ["Date", "Particulars", "Invoice Number", "Type", "Items"]
    amount_headers = ["Date", "Credit ($)", "Debit ($)", "Purchase (INR)", "Sale (INR)", "Balance ($)", "P/L (INR)"]
    for group in groups:
        company_name = group.get("company_name") or "—"
        # These are canonical FC totals already calculated per company.  For
        # a legacy/single-group detail payload, use the licence summary rather
        # than recomputing from displayed rows.
        credit_total = group.get("purchase_value")
        debit_total = group.get("sale_value")
        if credit_total is None and len(groups) == 1:
            credit_total = data["summary"].get("total_purchase")
        if debit_total is None and len(groups) == 1:
            debit_total = data["summary"].get("total_sale")
        elements.append(Paragraph(_text(company_name), styles["CompanyHeading"]))
        description_rows = [[_header_cell(header) for header in description_headers]]
        amount_rows = [[_header_cell(header) for header in amount_headers]]
        transaction_row_styles = []
        for row in all_rows:
            if group.get("company_id") is not None and row.get("company_id") != group.get("company_id"):
                continue
            transaction_type = row.get("type") or "—"
            description_rows.append([
                _date(row.get("date")), _cell_text(row.get("party_name") or ("Opening Balance" if transaction_type == "OPENING" else None)),
                _invoice_cell(row), _cell_text(transaction_type, bold=True, align="CENTER"), _cell_text(", ".join(row.get("item_names") or [])),
            ])
            amount_rows.append([
                _date(row.get("date")),
                _number(row.get("purchase_amount")), _number(row.get("sale_amount")), _number(row.get("purchase_bill_amount")),
                _number(row.get("sale_bill_amount")), "",
                _number(row.get("profit_loss_inr")),
            ])
            if transaction_type in {"PURCHASE", "SALE"}:
                transaction_row_styles.append((len(description_rows) - 1, transaction_type))
        elements.append(_table(
            description_rows, DETAIL_DESCRIPTION_WIDTHS,
            font_size=6.2, transaction_rows=transaction_row_styles,
        ))
        elements.append(Spacer(1, 2 * mm))
        elements.append(_table(
            amount_rows, DETAIL_AMOUNT_WIDTHS,
            numeric_from=1, font_size=6.2, transaction_rows=transaction_row_styles,
        ))
        # A portrait page cannot accommodate seven numeric totals alongside a
        # long licence label.  Two short rows keep every value inside the
        # printable frame instead of clipping the final P/L column.
        total_rows = [
            [_header_cell("Licence total"), _header_cell("Credit ($)"), _header_cell("Debit ($)"), _header_cell("Balance ($)")],
            [_cell_text(f"LICENSE TOTAL — {data.get('license_number') or '—'} · {company_name}", bold=True),
             _number(credit_total), _number(debit_total), _number(group.get("current_balance"))],
            [_header_cell("Financial total"), _header_cell("Purchase (INR)"), _header_cell("Sale (INR)"), _header_cell("P/L (INR)")],
            [_cell_text("INR TOTAL", bold=True), _number(group.get("purchase_total")),
             _number(group.get("sale_total")), _number(group.get("profit_loss"))],
        ]
        total_table = LongTable(total_rows, colWidths=[58*mm, 44*mm, 44*mm, 44*mm], hAlign="LEFT")
        total_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (0, 2), (-1, 2), NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), PALE_BLUE), ("BACKGROUND", (0, 3), (-1, 3), PALE_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 6 * mm))


def render_financial_ledger_pdf(canonical_data: dict) -> BytesIO:
    """Render canonical values without querying, aggregating, or classifying."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=10*mm, rightMargin=10*mm,
        topMargin=12*mm, bottomMargin=14*mm, title="License Ledger Statement",
        author="License Manager",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="LedgerTitle", parent=styles["Title"], fontName=FONT_BOLD,
                              fontSize=17, leading=20, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2*mm))
    styles.add(ParagraphStyle(name="LedgerSubtitle", parent=styles["Normal"], fontSize=8, leading=10,
                              textColor=GREY, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CompanyHeading", parent=styles["Heading2"], fontName=FONT_BOLD,
                              fontSize=10, leading=13, textColor=colors.white, backColor=BLUE,
                              leftIndent=3*mm, borderPadding=(4, 4, 4, 4), spaceBefore=2*mm, spaceAfter=2*mm))
    styles.add(ParagraphStyle(name="SionHeading", parent=styles["Heading3"], fontName=FONT_BOLD,
                              fontSize=9, leading=11, textColor=NAVY, backColor=PALE_BLUE,
                              leftIndent=3*mm, borderPadding=(3, 3, 3, 3), spaceBefore=2*mm,
                              spaceAfter=1.5*mm))
    elements = []
    licenses = canonical_data.get("licenses") or []
    # The export orchestration always supplies scope.  The single-row fallback
    # keeps direct renderer callers from older integrations usable without
    # affecting endpoint behaviour.
    is_detail = canonical_data.get("scope") == "detail" or (
        canonical_data.get("scope") is None and len(licenses) == 1
    )
    if is_detail:
        if licenses:
            _render_detail(elements, licenses[0], styles)
        else:
            elements.append(Paragraph("LICENSE LEDGER STATEMENT", styles["LedgerTitle"]))
            elements.append(Paragraph("No ledger records", styles["LedgerSubtitle"]))
    else:
        _render_list(elements, canonical_data, styles)
        # The SION report is an index/summary layer, never a replacement for
        # the canonical individual ledgers.  Append every unique license DTO
        # once, including all of its canonical transaction rows.
        for data in licenses:
            elements.append(PageBreak())
            _render_detail(elements, data, styles)
    doc.build(elements, onFirstPage=_page_footer, onLaterPages=_page_footer)
    buffer.seek(0)
    return buffer
