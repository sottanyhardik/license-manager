"""Native, read-only Customs Ledger PDF selection and rendering.

This module deliberately keeps database selection separate from ReportLab
presentation.  It is used by both the individual download endpoint and the
package exporter, so neither route can drift into a screen-capture export.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.db.models import Prefetch

from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
from apps.core.constants import DEBIT, DEC_0
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return DEC_0


def _number(value) -> str:
    return f"{_decimal(value):,.2f}"


def _date(value) -> str:
    return value.strftime("%d-%b-%Y") if value else "—"


def get_custom_ledger_data(licence, user=None, *, canonical_dataset=None) -> dict:
    """Return the authoritative item/BOE input for a DFIA Customs Ledger.

    BOE rows use the same genuine-hidden exclusion used by the existing item
    export.  Only debit rows are included; plans and non-BOE allotments never
    enter this history section.  Stored item balances retain the application's
    established balance-engine calculations.
    """
    licence = LicenseDetailsModel.objects.select_related(
        "exporter", "notification_number", "purchase_status"
    ).prefetch_related(
        Prefetch("import_license", queryset=LicenseImportItemsModel.objects.select_related("hs_code").prefetch_related("items__sion_norm_class").order_by("serial_number"))
    ).get(pk=licence.pk)
    item_ids = [item.id for item in licence.import_license.all()]
    boes = annotate_and_exclude_hidden(
        RowDetails.objects.filter(sr_number_id__in=item_ids, transaction_type=DEBIT),
        boe_field="bill_of_entry",
    ).select_related("sr_number", "bill_of_entry__port", "bill_of_entry__company").order_by(
        "sr_number__serial_number", "bill_of_entry__bill_of_entry_date", "pk"
    )
    rows_by_item = defaultdict(list)
    for row in boes:
        boe = row.bill_of_entry
        rows_by_item[row.sr_number_id].append({
            "id": row.pk, "number": getattr(boe, "bill_of_entry_number", "—"),
            "date": _date(getattr(boe, "bill_of_entry_date", None)),
            "port": getattr(getattr(boe, "port", None), "name", "—") or "—",
            "company": getattr(getattr(boe, "company", None), "name", "—") or "—",
            "description": getattr(boe, "product_name", "—") or "—",
            "qty": _decimal(row.qty), "cif": _decimal(row.cif_fc),
        })
    items, unit_totals = [], defaultdict(lambda: {"original": DEC_0, "debited": DEC_0, "available": DEC_0})
    for item in licence.import_license.all():
        debit_rows = rows_by_item[item.id]
        boe_qty, boe_cif = sum((r["qty"] for r in debit_rows), DEC_0), sum((r["cif"] for r in debit_rows), DEC_0)
        # Difference from the posted BOE trail is retained as an explicit
        # adjustment rather than mislabelling allotments/direct sales as BOEs.
        # Use the same live item balance helpers as the ledger rather than a
        # potentially stale denormalized field after an import transaction.
        from apps.core.scripts.calculate_balance import calculate_debited_quantity, calculate_debited_value
        canonical_debited_qty = _decimal(calculate_debited_quantity(item))
        canonical_debited_cif = _decimal(calculate_debited_value(item))
        adjustment_qty = canonical_debited_qty - boe_qty
        adjustment_cif = canonical_debited_cif - boe_cif
        original, debited, available = _decimal(item.quantity), canonical_debited_qty, _decimal(item.balance_quantity)
        unit = item.unit or "—"
        unit_totals[unit]["original"] += original
        unit_totals[unit]["debited"] += debited
        unit_totals[unit]["available"] += available
        names = ", ".join(x.name for x in item.items.all() if x.name) or "—"
        items.append({"id": item.id, "serial": item.serial_number, "product": names,
                      "description": item.description or "—", "hsn": getattr(item.hs_code, "hs_code", "—") or "—",
                      "unit": unit, "original": original, "debited": debited, "available": available,
                      "cif": _decimal(item.cif_fc), "debited_cif": canonical_debited_cif,
                      "balance_cif": _decimal(item.balance_cif_fc), "boes": debit_rows,
                      "adjustment_qty": adjustment_qty, "adjustment_cif": adjustment_cif})
    summary = (canonical_dataset or {}).get("summary", {})
    total_cif = _decimal(getattr(licence, "opening_balance", DEC_0))
    balance_cif = _decimal(getattr(licence, "get_balance_cif", DEC_0))
    actual_debited_cif = total_cif - balance_cif
    return {"licence": licence, "license_number": licence.license_number, "summary": summary, "items": items,
            "unit_totals": dict(unit_totals), "total_cif": total_cif,
            "actual_debited_cif": actual_debited_cif, "actual_balance_cif": balance_cif,
            "reconciled": abs(total_cif - actual_debited_cif - balance_cif) <= Decimal("0.01")}


def render_custom_ledger_pdf(data: dict) -> bytes:
    """Render native selectable text/tables; no raster or browser dependency."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    # Verdana is present on the supported local/runtime image and embedding a
    # TrueType font keeps generated text selectable/searchable in all viewers.
    font_path = "/System/Library/Fonts/Supplemental/Verdana.ttf"
    try:
        pdfmetrics.registerFont(TTFont("LedgerVerdana", font_path))
        pdfmetrics.registerFont(TTFont("LedgerVerdanaBold", "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"))
        regular, bold = "LedgerVerdana", "LedgerVerdanaBold"
    except Exception:
        regular, bold = "Helvetica", "Helvetica-Bold"
    output = BytesIO()
    page = A4
    left = right = 10 * mm
    top, bottom = 18 * mm, 14 * mm
    styles = getSampleStyleSheet()
    title = ParagraphStyle("custom-title", parent=styles["Title"], fontName=bold, fontSize=14, leading=17, textColor=colors.HexColor("#17365D"))
    body = ParagraphStyle("custom-body", parent=styles["BodyText"], fontName=regular, fontSize=7, leading=9, wordWrap="CJK")
    small = ParagraphStyle("custom-small", parent=body, fontSize=6.3, leading=7.7)
    header = ParagraphStyle("custom-header", parent=small, fontName=bold, textColor=colors.white, alignment=1)
    section = ParagraphStyle("custom-section", parent=body, fontName=bold, fontSize=9, leading=11, textColor=colors.HexColor("#17365D"))
    p = lambda value, style=body: Paragraph(escape(str(value if value not in (None, "") else "—")), style)
    licence = data["licence"]
    def page_decor(canvas, doc):
        canvas.saveState(); canvas.setFont(regular, 6.5); canvas.setFillColor(colors.HexColor("#4B5563"))
        canvas.drawString(left, page[1] - 8*mm, f"Customs Ledger • Licence {data['license_number']}")
        canvas.drawRightString(page[0] - right, 8*mm, f"Page {doc.page}"); canvas.restoreState()
    doc = SimpleDocTemplate(output, pagesize=page, leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom)
    story = [Paragraph(f"Customs Ledger — Item Detail: {data['license_number']}", title), Spacer(1, 4)]
    details = [[p("Licence date", small), p(_date(licence.license_date), small), p("Expiry date", small), p(_date(licence.license_expiry_date), small), p("Status", small), p(getattr(getattr(licence, 'purchase_status', None), 'label', '—'), small)],
               [p("Notification", small), p(licence.get_notification_number_display(), small), p("Licence holder", small), p(getattr(getattr(licence, 'exporter', None), 'name', None) or licence.archived_exporter_name, small), p("Total CIF", small), p(_number(data['total_cif']), small)],
               [p("Actual debited CIF", small), p(_number(data['actual_debited_cif']), small), p("Actual balance CIF", small), p(_number(data['actual_balance_cif']), small), p("CIF reconciliation", small), p("PASS" if data['reconciled'] else "CHECK", small)]]
    summary_table = Table(details, colWidths=[24*mm, 35*mm, 24*mm, 42*mm, 28*mm, 35*mm])
    summary_table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.25,colors.HexColor("#CBD5E1")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F1F5F9")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#F1F5F9")),("BACKGROUND",(4,0),(4,-1),colors.HexColor("#F1F5F9")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story += [summary_table, Spacer(1, 8), Paragraph("Item-wise Import Summary", section), Spacer(1, 3)]
    item_headers = ["SR", "Product / item", "HSN", "Unit", "Original qty", "BOE debited qty", "Available qty", "Original CIF", "Debited CIF", "Balance CIF"]
    # Portrait A4 is deliberately compact but remains readable; paragraph
    # cells wrap instead of allowing a ledger column to overflow the page.
    widths = [8*mm, 34*mm, 16*mm, 11*mm, 17*mm, 19*mm, 18*mm, 20*mm, 20*mm, 20*mm]
    item_rows = [[p(x, header) for x in item_headers]]
    for item in data['items']:
        item_rows.append([p(x, small) for x in [item['serial'], item['product'], item['hsn'], item['unit'], _number(item['original']), _number(item['debited']), _number(item['available']), _number(item['cif']), _number(item['debited_cif']), _number(item['balance_cif'])]])
    item_table = Table(item_rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    item_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#94A3B8")),("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(4,1),(-1,-1),"RIGHT"),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story += [item_table, Spacer(1, 8)]
    debit_groups = []
    for item in data['items']:
        group = [Paragraph(f"SR {item['serial']} — {escape(item['product'])} ({escape(item['description'])})", ParagraphStyle("item-label", parent=body, fontName=bold))]
        boe_rows = [[p(x, header) for x in ["BOE no.", "BOE date", "Port", "Importer / company", "BOE item", "Qty", "CIF"]]]
        for row in item['boes']:
            boe_rows.append([p(x, small) for x in [row['number'], row['date'], row['port'], row['company'], row['description'], _number(row['qty']), _number(row['cif'])]])
        if item['adjustment_qty'] or item['adjustment_cif']:
            boe_rows.append([p(x, small) for x in ["Adjustment", "—", "—", "Non-BOE adjustment", "Not a BOE debit", _number(item['adjustment_qty']), _number(item['adjustment_cif'])]])
        # Do not manufacture an empty debit-history row for an import item.
        # It is neither a posted BOE debit nor useful PDF content, and many
        # empty placeholders create artificial page breaks in large licences.
        if len(boe_rows) == 1:
            continue
        boe_table = Table(boe_rows, colWidths=[19*mm, 16*mm, 18*mm, 29*mm, 58*mm, 19*mm, 22*mm], repeatRows=1, hAlign="LEFT")
        boe_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2563EB")),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#94A3B8")),("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(5,1),(6,-1),"RIGHT"),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
        group += [boe_table, Spacer(1, 6)]
        # A one-row BOE section must never be split from its import-item
        # identity; larger BOE tables still paginate themselves with headers.
        debit_groups.append(KeepTogether(group))
    if debit_groups:
        story += [Paragraph("Posted BOE Debit History", section), Spacer(1, 3), *debit_groups]
    totals_rows = [[p("Unit", header), p("Original quantity", header), p("Debited quantity", header), p("Available quantity", header)]]
    for unit, values in data["unit_totals"].items():
        totals_rows.append([p(unit, small), p(_number(values.get("original")), small), p(_number(values.get("debited")), small), p(_number(values.get("available")), small)])
    totals = Table(totals_rows, colWidths=[35*mm, 48*mm, 48*mm, 48*mm], repeatRows=1)
    totals.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#94A3B8")), ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story.append(KeepTogether([Paragraph("Final Quantity and CIF Totals", section), Spacer(1, 3), totals, Spacer(1, 3), Paragraph(f"CIF totals — Total: {_number(data['total_cif'])}; Net actual debited: {_number(data['actual_debited_cif'])}; Actual balance: {_number(data['actual_balance_cif'])}.", small)]))
    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return output.getvalue()
