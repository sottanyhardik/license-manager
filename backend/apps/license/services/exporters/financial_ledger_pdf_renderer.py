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
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from shared.pdf.builders import format_indian_number


NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#1F4E78")
PALE_BLUE = colors.HexColor("#D9EAF7")
PALE_RED = colors.HexColor("#FCE8E6")
GREY = colors.HexColor("#666666")


def _date(value) -> str:
    return value.strftime("%d-%b-%Y") if isinstance(value, (date, datetime)) else "-"


def _number(value) -> str:
    return "-" if value is None else format_indian_number(Decimal(str(value)), 2)


def _text(value) -> str:
    return escape(str(value)) if value not in (None, "") else "-"


def _invoice_cell(row):
    """Render only canonical document metadata; never resolve a document here."""
    document = row.get("invoice_document") or {}
    number = _text(document.get("invoice_number"))
    url = document.get("secure_url") if document.get("document_exists") else None
    if url:
        status = "SIGNED" if document.get("signed") else "UNSIGNED"
        return Paragraph(
            f'<link href="{escape(str(url), {"\"": "&quot;"})}" color="#1F4E78"><u>{number}</u></link><br/>'
            f'<font size="5.5" color="#666666">{status}</font>',
            ParagraphStyle("InvoiceLink", fontName="Helvetica", fontSize=6.5, leading=8),
        )
    if document.get("status") == "COPY_UNAVAILABLE":
        return Paragraph(
            f'{number}<br/><font size="5.5" color="#666666">Copy unavailable</font>',
            ParagraphStyle("InvoiceUnavailable", fontName="Helvetica", fontSize=6.5, leading=8),
        )
    return number


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#B4C7E7"))
    canvas.line(doc.leftMargin, 10 * mm, landscape(A4)[0] - doc.rightMargin, 10 * mm)
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(doc.leftMargin, 6.5 * mm, "License Manager · Financial Trade Ledger")
    label = f"Page {doc.page}"
    canvas.drawString(landscape(A4)[0] - doc.rightMargin - stringWidth(label, "Helvetica", 7), 6.5 * mm, label)
    canvas.restoreState()


def _table(rows, widths, *, numeric_from=0, total_row=None, font_size=7):
    table = Table(rows, repeatRows=1, colWidths=widths, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if len(rows) > 1:
        commands.append(("ALIGN", (numeric_from, 1), (-1, -1), "RIGHT"))
        commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]))
    if total_row is not None:
        commands.extend([
            ("FONTNAME", (0, total_row), (-1, total_row), "Helvetica-Bold"),
            ("BACKGROUND", (0, total_row), (-1, total_row), PALE_BLUE),
        ])
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
            rows = [headers]
            for data in sion_group.get("licenses") or []:
                rows.append([
                    data.get("license_number") or "-", data.get("license_type") or "-",
                    _date(data.get("license_date")), _date(data.get("first_purchase_date")),
                    data.get("sion_norms") or "-", _number(data.get("current_balance")),
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
                rows, [29*mm, 18*mm, 23*mm, 27*mm, 32*mm, 27*mm, 30*mm, 30*mm, 29*mm],
                numeric_from=5, total_row=len(rows)-1,
            ))
            elements.append(Spacer(1, 3 * mm))

        company_total = [["", "Balance ($)", "Purchase (INR)", "Sale (INR)", "P/L (INR)"], [
            f"COMPANY TOTAL — {company_name}", _number(group.get("total_balance")),
            _number(group.get("total_purchase_bill_inr")), _number(group.get("total_sale_bill_inr")),
            _number(group.get("total_profit_loss_inr")),
        ]]
        elements.append(_table(
            company_total, [105*mm, 32*mm, 36*mm, 36*mm, 36*mm], numeric_from=1, total_row=1,
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
            rows, [80*mm, 25*mm, 34*mm, 39*mm, 39*mm, 38*mm], numeric_from=1, total_row=1,
            font_size=8,
        ))


def _metadata_table(data):
    summary = data["summary"]
    rows = [
        ["License Number", data.get("license_number") or "-", "License Date", _date(data.get("license_date")),
         "Expiry Date", _date(data.get("expiry_date"))],
        ["Exporter", data.get("exporter_name") or "-", "Total Value", _number(summary.get("total_purchase")),
         "Balance ($)", _number(summary.get("current_balance"))],
        ["1st Purchase Date", _date(data.get("first_purchase_date")), "SION Norms", data.get("sion_norms") or "-",
         "Purchase Bill", "YES" if data.get("has_purchase_bill") else "NO PURCHASE BILL"],
        ["Purchase (INR)", _number(summary.get("total_purchase_bill_inr")),
         "Sale (INR)", _number(summary.get("total_sale_bill_inr")),
         "P/L (INR)", _number(summary.get("total_profit_loss"))],
    ]
    table = Table(rows, colWidths=[25*mm, 57*mm, 25*mm, 42*mm, 27*mm, 48*mm])
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A6A6A6")),
        ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE), ("BACKGROUND", (2, 0), (2, -1), PALE_BLUE),
        ("BACKGROUND", (4, 0), (4, -1), PALE_BLUE),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (4, 0), (4, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
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
    headers = ["Date", "Particulars", "Invoice Number", "Type", "Items", "Credit ($)", "Debit ($)",
               "Purchase (INR)", "Sale (INR)", "Balance ($)", "P/L (INR)"]
    for group in groups:
        company_name = group.get("company_name") or "-"
        elements.append(Paragraph(_text(company_name), styles["CompanyHeading"]))
        rows = [headers]
        for row in all_rows:
            if group.get("company_id") is not None and row.get("company_id") != group.get("company_id"):
                continue
            rows.append([
                _date(row.get("date")), row.get("party_name") or ("Opening Balance" if row.get("type") == "OPENING" else "-"),
                _invoice_cell(row), row.get("type") or "-", ", ".join(row.get("item_names") or []) or "-",
                _number(row.get("purchase_amount")), _number(row.get("sale_amount")), _number(row.get("purchase_bill_amount")),
                _number(row.get("sale_bill_amount")), _number(row.get("license_running_balance")),
                _number(row.get("profit_loss_inr")),
            ])
        rows.append([
            f"Total — {company_name}", "", "", "", "", "", "",
            _number(group.get("purchase_total")), _number(group.get("sale_total")),
            _number(group.get("current_balance")), _number(group.get("profit_loss")),
        ])
        elements.append(_table(
            rows, [17*mm, 27*mm, 25*mm, 19*mm, 28*mm, 21*mm, 21*mm, 25*mm, 25*mm, 22*mm, 25*mm],
            numeric_from=5, total_row=len(rows)-1, font_size=6,
        ))
        elements.append(Spacer(1, 6 * mm))


def render_financial_ledger_pdf(canonical_data: dict) -> BytesIO:
    """Render canonical values without querying, aggregating, or classifying."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=9*mm, rightMargin=9*mm,
        topMargin=11*mm, bottomMargin=14*mm, title="License Ledger Statement",
        author="License Manager",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="LedgerTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              fontSize=17, leading=20, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2*mm))
    styles.add(ParagraphStyle(name="LedgerSubtitle", parent=styles["Normal"], fontSize=8, leading=10,
                              textColor=GREY, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CompanyHeading", parent=styles["Heading2"], fontName="Helvetica-Bold",
                              fontSize=10, leading=13, textColor=colors.white, backColor=BLUE,
                              leftIndent=3*mm, borderPadding=(4, 4, 4, 4), spaceBefore=2*mm, spaceAfter=2*mm))
    styles.add(ParagraphStyle(name="SionHeading", parent=styles["Heading3"], fontName="Helvetica-Bold",
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
