"""
License Ledger PDF generator adapted for the new backend model.

Uses the new LicenseDetailsModel's actual fields and relationships:
  - balance.balance_cif  (from LicenseBalance OneToOne)
  - import_item.cif_fc / available_value / available_quantity (denormalized)
  - allotment_details (AllotmentItems FK to LicenseImportItemsModel)
  - item_details (RowDetails FK to LicenseImportItemsModel)

Does NOT rely on legacy-only model methods:
  get_balance_cif, get_restriction_balances, _calculate_license_credit,
  available_value_calculated.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
COL_SERIAL = 1.0 * inch
COL_DESC = 3.5 * inch
COL_HS = 1.0 * inch
COL_QTY = 1.2 * inch
COL_AVAIL = 1.2 * inch
COL_COMPANY = 3.0 * inch
COL_CIF = 1.5 * inch

SP_SM = 0.1 * inch
SP_MD = 0.15 * inch
SP_LG = 0.3 * inch

PDF_MARGIN = 30
FS_TITLE = 16
FS_HDR = 9
FS_DATA = 8


class PDFGenerationError(Exception):
    """Raised when the ledger PDF cannot be built."""


def _dec(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def generate_license_ledger_pdf(license_obj) -> bytes:
    """
    Generate a landscape A4 PDF ledger for *license_obj* (LicenseDetailsModel).

    The caller must have prefetched:
        import_license__items
        import_license__hs_code
        import_license__allotment_details__allotment__company
        import_license__item_details__bill_of_entry__company
    and select_related:
        exporter, port, balance, notification_number

    Raises PDFGenerationError on failure.
    """
    buf = BytesIO()
    try:
        _build_pdf(buf, license_obj)
        return buf.getvalue()
    except Exception as exc:
        logger.exception(
            "Failed to generate ledger PDF for license %s: %s",
            getattr(license_obj, "license_number", "UNKNOWN"),
            exc,
        )
        raise PDFGenerationError(f"Failed to generate license ledger PDF: {exc}") from exc
    finally:
        buf.close()


def _build_pdf(buf: BytesIO, license_obj) -> None:  # noqa: C901
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=PDF_MARGIN,
        leftMargin=PDF_MARGIN,
        topMargin=PDF_MARGIN,
        bottomMargin=PDF_MARGIN,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CT", parent=styles["Heading1"], fontSize=FS_TITLE,
        textColor=colors.HexColor("#1a1a1a"), spaceAfter=12,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    wrap_style = ParagraphStyle(
        "WS", parent=styles["Normal"], fontSize=FS_DATA, leading=10,
    )
    bold_wrap = ParagraphStyle(
        "BW", parent=styles["Normal"], fontSize=FS_DATA,
        leading=10, fontName="Helvetica-Bold",
    )
    desc_style = ParagraphStyle(
        "DS", parent=styles["Normal"], fontSize=FS_HDR, leading=11, alignment=TA_LEFT,
    )

    elements = []
    elements.append(Paragraph("LICENSE LEDGER", title_style))
    elements.append(Spacer(1, SP_SM))

    # ── Balance CIF from the OneToOne satellite ──────────────────────────
    try:
        balance_cif = _dec(license_obj.balance.balance_cif)
    except Exception:
        balance_cif = Decimal("0")

    # ── License header table ─────────────────────────────────────────────
    lic_date_str = (
        license_obj.license_date.strftime("%d-%b-%Y")
        if license_obj.license_date else "N/A"
    )
    exp_date_str = (
        license_obj.license_expiry_date.strftime("%d-%b-%Y")
        if license_obj.license_expiry_date else "N/A"
    )
    notif_code = (
        license_obj.notification_number.code
        if license_obj.notification_number_id else ""
    )
    exporter_name = license_obj.exporter.name if license_obj.exporter_id else "N/A"

    license_info = [
        ["License Number:", license_obj.license_number, "License Date:", lic_date_str],
        ["Exporter:", exporter_name, "Expiry Date:", exp_date_str],
        ["Notification:", notif_code, "Purchase Status:", ""],
        ["Balance CIF FC:", f"{balance_cif:.2f}", "", ""],
    ]
    lic_table = Table(license_info, colWidths=[1.5 * inch, 3 * inch, 1.5 * inch, 3 * inch])
    lic_style = [
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecf0f1")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#ecf0f1")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), FS_HDR),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d4edda")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]
    lic_table.setStyle(TableStyle(lic_style))
    elements.append(lic_table)
    elements.append(Spacer(1, SP_LG))

    # ── Import items — group by first ItemNameModel (or description) ─────
    import_items = list(
        license_obj.import_license.all()
        .prefetch_related("items", "hs_code")
        .order_by("serial_number")
    )

    item_groups: dict = defaultdict(list)
    item_desc_map: dict = {}

    for imp in import_items:
        names = list(imp.items.all())
        if names:
            key = names[0].id
            item_desc_map.setdefault(key, imp.description or names[0].name)
            item_groups[key].append(imp)
        else:
            desc = imp.description or "No Item"
            key = f"desc_{desc}"
            item_desc_map.setdefault(key, desc)
            item_groups[key].append(imp)

    def _min_sn(items_list):
        return min(
            (i.serial_number for i in items_list if i.serial_number is not None),
            default=0,
        )

    sorted_groups = sorted(item_groups.items(), key=lambda kv: _min_sn(kv[1]))

    for _gk, g_items in sorted_groups:
        g_items_sorted = sorted(
            g_items,
            key=lambda x: x.serial_number if x.serial_number is not None else 0,
        )
        first_item = g_items_sorted[0]
        description = first_item.description or "No Description"
        serial_numbers_str = ", ".join(
            str(it.serial_number) for it in g_items_sorted if it.serial_number is not None
        ) or "N/A"
        hs_code = (first_item.hs_code.hs_code if first_item.hs_code else "-")

        total_import_qty = sum(_dec(i.quantity) for i in g_items)
        total_available_qty = sum(_dec(i.available_quantity) for i in g_items)

        item_info = [
            ["Sr No", "Product Description", "HS Code", "Total Import Qty", "Available Qty"],
            [
                serial_numbers_str,
                Paragraph(description, desc_style),
                hs_code,
                f"{total_import_qty:.2f}",
                f"{total_available_qty:.2f}",
            ],
        ]
        item_table = Table(
            item_info,
            colWidths=[COL_SERIAL, COL_DESC, COL_HS, COL_QTY, COL_AVAIL],
        )
        item_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (1, 1), (1, 1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), FS_HDR),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, SP_MD))

        # ── Allotments ───────────────────────────────────────────────────
        allot_by_co: dict = defaultdict(
            lambda: {"qty": Decimal("0"), "cif_fc": Decimal("0"), "cif_inr": Decimal("0"), "rows": []}
        )
        allot_qty = allot_cif_fc = allot_cif_inr = Decimal("0")

        for imp in g_items:
            for allot in imp.allotment_details.filter(
                is_boe=False,
                allotment__is_boe=False,
            ).select_related("allotment", "allotment__company"):
                co_name = allot.allotment.company.name if allot.allotment.company else "Unknown"
                d = (
                    allot.allotment.estimated_arrival_date
                    or allot.allotment.modified_on
                )
                q, cf, ci = _dec(allot.qty), _dec(allot.cif_fc), _dec(allot.cif_inr)
                allot_by_co[co_name]["qty"] += q
                allot_by_co[co_name]["cif_fc"] += cf
                allot_by_co[co_name]["cif_inr"] += ci
                allot_by_co[co_name]["rows"].append({
                    "date": d.strftime("%d-%b-%Y") if d else "-",
                    "qty": q,
                    "cif_fc": cf,
                    "cif_inr": ci,
                })
                allot_qty += q
                allot_cif_fc += cf
                allot_cif_inr += ci

        allot_data = [["Company / Date", "Quantity", "CIF FC", "CIF INR"]]
        co_total_rows: list[int] = []
        for co, d in sorted(allot_by_co.items()):
            for row in d["rows"]:
                allot_data.append([
                    Paragraph(f"  {row['date']}", wrap_style),
                    f"{row['qty']:.1f}",
                    f"{row['cif_fc']:.2f}",
                    f"{row['cif_inr']:.2f}",
                ])
            co_total_rows.append(len(allot_data))
            allot_data.append([
                Paragraph(co, bold_wrap),
                f"{d['qty']:.1f}",
                f"{d['cif_fc']:.2f}",
                f"{d['cif_inr']:.2f}",
            ])

        if len(allot_data) > 1:
            allot_data.append([
                "TOTAL",
                f"{allot_qty:.1f}",
                f"{allot_cif_fc:.2f}",
                f"{allot_cif_inr:.2f}",
            ])
            at_style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e67e22")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), FS_HDR),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fdebd0")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
            for ri in co_total_rows:
                at_style += [
                    ("FONTNAME", (0, ri), (-1, ri), "Helvetica-Bold"),
                    ("BACKGROUND", (0, ri), (-1, ri), colors.HexColor("#f8e5d3")),
                ]
            at = Table(allot_data, colWidths=[COL_COMPANY, COL_CIF, COL_CIF, COL_CIF])
            at.setStyle(TableStyle(at_style))
            elements.append(at)
            elements.append(Spacer(1, SP_MD))

        # ── BOE debits ───────────────────────────────────────────────────
        boe_by_co: dict = defaultdict(
            lambda: {"qty": Decimal("0"), "cif_fc": Decimal("0"), "cif_inr": Decimal("0"), "rows": []}
        )
        boe_qty = boe_cif_fc = boe_cif_inr = Decimal("0")

        for imp in g_items:
            for boe in imp.item_details.filter(
                bill_of_entry__isnull=False
            ).select_related("bill_of_entry", "bill_of_entry__company").order_by(
                "bill_of_entry__bill_of_entry_date"
            ):
                co_name = boe.bill_of_entry.company.name if boe.bill_of_entry.company else "Unknown"
                bd = boe.bill_of_entry.bill_of_entry_date
                bno = boe.bill_of_entry.bill_of_entry_number or "-"
                q, cf, ci = _dec(boe.qty), _dec(boe.cif_fc), _dec(boe.cif_inr)
                boe_by_co[co_name]["qty"] += q
                boe_by_co[co_name]["cif_fc"] += cf
                boe_by_co[co_name]["cif_inr"] += ci
                boe_by_co[co_name]["rows"].append({
                    "date": bd.strftime("%d-%b-%Y") if bd else "-",
                    "number": bno,
                    "qty": q,
                    "cif_fc": cf,
                    "cif_inr": ci,
                })
                boe_qty += q
                boe_cif_fc += cf
                boe_cif_inr += ci

        boe_data = [["Company / BOE No & Date", "Quantity", "CIF FC", "CIF INR"]]
        boe_co_total_rows: list[int] = []
        for co, d in sorted(boe_by_co.items()):
            for row in d["rows"]:
                boe_data.append([
                    Paragraph(f"  {row['number']} / {row['date']}", wrap_style),
                    f"{row['qty']:.1f}",
                    f"{row['cif_fc']:.2f}",
                    f"{row['cif_inr']:.2f}",
                ])
            boe_co_total_rows.append(len(boe_data))
            boe_data.append([
                Paragraph(co, bold_wrap),
                f"{d['qty']:.1f}",
                f"{d['cif_fc']:.2f}",
                f"{d['cif_inr']:.2f}",
            ])

        if len(boe_data) > 1:
            boe_data.append([
                "TOTAL",
                f"{boe_qty:.1f}",
                f"{boe_cif_fc:.2f}",
                f"{boe_cif_inr:.2f}",
            ])
            bt_style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), FS_HDR),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d5f4e6")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
            for ri in boe_co_total_rows:
                bt_style += [
                    ("FONTNAME", (0, ri), (-1, ri), "Helvetica-Bold"),
                    ("BACKGROUND", (0, ri), (-1, ri), colors.HexColor("#c8e6c9")),
                ]
            bt = Table(boe_data, colWidths=[COL_COMPANY, COL_CIF, COL_CIF, COL_CIF])
            bt.setStyle(TableStyle(bt_style))
            elements.append(bt)
            elements.append(Spacer(1, SP_MD))

        if len(allot_data) == 1 and len(boe_data) == 1:
            elements.append(Paragraph("<i>No transactions found</i>", styles["Normal"]))

        elements.append(Spacer(1, SP_LG))

    # ── Summary table ────────────────────────────────────────────────────
    elements.append(Spacer(1, SP_LG))
    elements.append(Paragraph(
        f"<b>License Date:</b> {lic_date_str} &nbsp;&nbsp;&nbsp; <b>Expiry Date:</b> {exp_date_str}",
        ParagraphStyle("SI", parent=styles["Normal"], fontSize=FS_HDR, leading=13),
    ))
    elements.append(Spacer(1, SP_SM))
    elements.append(Paragraph("SUMMARY", title_style))
    elements.append(Spacer(1, SP_SM))

    sum_data = [[
        "Item Description", "Import Qty", "Total CIF $",
        "Purchase Qty", "CIF $ Purchase",
        "Sold Qty", "CIF $ Sold",
        "Avail Qty", "Balance $",
    ]]

    for _gk, g_items in sorted_groups:
        g_items_sorted = sorted(
            g_items,
            key=lambda x: x.serial_number if x.serial_number is not None else 0,
        )
        description = g_items_sorted[0].description or "No Description"
        total_import_qty = sum(_dec(i.quantity) for i in g_items)
        total_cif_fc = sum(_dec(i.cif_fc) for i in g_items)
        total_available_qty = sum(_dec(i.available_quantity) for i in g_items)
        balance_fc = sum(_dec(i.available_value) for i in g_items)

        allotted_qty = Decimal("0")
        allotted_cif = Decimal("0")
        boe_qty2 = Decimal("0")
        boe_cif2 = Decimal("0")

        for imp in g_items:
            for a in imp.allotment_details.filter(is_boe=False, allotment__is_boe=False):
                allotted_qty += _dec(a.qty)
                allotted_cif += _dec(a.cif_fc)
            for b in imp.item_details.filter(bill_of_entry__isnull=False):
                boe_qty2 += _dec(b.qty)
                boe_cif2 += _dec(b.cif_fc)

        sum_data.append([
            Paragraph(description, ParagraphStyle(
                "DD", parent=styles["Normal"], fontSize=FS_DATA, leading=10,
            )),
            f"{total_import_qty:.2f}",
            f"{total_cif_fc:.2f}",
            f"{allotted_qty:.2f}" if allotted_qty > 0 else "-",
            f"{allotted_cif:.2f}" if allotted_cif > 0 else "-",
            f"{boe_qty2:.2f}" if boe_qty2 > 0 else "-",
            f"{boe_cif2:.2f}" if boe_cif2 > 0 else "-",
            f"{total_available_qty:.2f}",
            f"{balance_fc:.2f}",
        ])

    sum_table = Table(
        sum_data,
        colWidths=[
            2.5 * inch, 0.7 * inch, 0.8 * inch,
            0.7 * inch, 0.9 * inch,
            0.7 * inch, 0.9 * inch,
            0.7 * inch, 0.9 * inch,
        ],
    )
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), FS_HDR),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (4, 1), (4, -1), colors.HexColor("#fdebd0")),
        ("BACKGROUND", (6, 1), (6, -1), colors.HexColor("#d5f4e6")),
        ("BACKGROUND", (8, 1), (8, -1), colors.HexColor("#e8f5e9")),
        ("FONTNAME", (8, 1), (8, -1), "Helvetica-Bold"),
    ]))
    elements.append(sum_table)
    elements.append(Spacer(1, SP_LG))

    elements.append(Paragraph(
        f"<i>Generated on: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}</i>",
        ParagraphStyle(
            "FT", parent=styles["Normal"], fontSize=FS_DATA,
            textColor=colors.grey, alignment=TA_CENTER,
        ),
    ))

    doc.build(elements)
