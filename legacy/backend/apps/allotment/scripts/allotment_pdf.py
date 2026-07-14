"""
Allotment PDF generation helper.
Used by both the generate-pdf API action and the transfer-letter zip builder.
"""
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


def generate_allotment_pdf_bytes(allotment):
    """
    Build the allotment letter PDF and return it as bytes.
    Raises on error so callers can handle appropriately.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.black,
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=6,
        alignment=TA_LEFT,
    )

    elements = []

    # Header
    elements.append(Paragraph(f"Allotment Time: {datetime.now().strftime('%d %B %Y %H:%M')}", header_style))
    elements.append(Spacer(1, 12))

    # Company details
    company_name = allotment.company.name if allotment.company else "N/A"
    company_address = getattr(allotment.company, 'address', '') or ''
    elements.append(Paragraph("<b>To,</b>", header_style))
    elements.append(Paragraph(f"<b>{company_name}</b>", header_style))
    if company_address:
        elements.append(Paragraph(company_address, header_style))
    elements.append(Spacer(1, 12))

    # Subject
    total_qty = int(allotment.required_quantity or 0)
    invoice = allotment.invoice or "N/A"
    item_name = allotment.item_name or "N/A"
    first_detail = allotment.allotment_details.select_related('item').first()
    raw_unit = (first_detail.item.unit if first_detail and first_detail.item else None) or 'kg'
    unit_map = {'kg': 'Kgs', 'kgs': 'Kgs', 'pcs': 'Pcs', 'nos': 'Nos', 'mts': 'Mts', 'mt': 'Mts', 'ltr': 'Ltr'}
    unit_display = unit_map.get(raw_unit.lower(), raw_unit.upper())
    subject = f"<b>Subject:</b> License Allotment for {item_name} Invoice No. {invoice} for {total_qty:,} {unit_display}"
    elements.append(Paragraph(subject, header_style))
    elements.append(Spacer(1, 12))

    # Summary table
    summary_data = [
        ['Date', 'Item', 'Port Of Discharge'],
        [
            allotment.estimated_arrival_date.strftime('%d/%m/%Y') if allotment.estimated_arrival_date else 'N/A',
            item_name,
            allotment.port.code if allotment.port else 'N/A',
        ],
    ]
    summary_table = Table(summary_data, colWidths=[1.2 * inch, 1.5 * inch, 1.2 * inch, 1.5 * inch, 1.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 18))

    # Detail table
    detail_data = [
        ['DFIA No', 'Reg No', 'Port Code', 'Duty Type', 'Item Sr.No', 'Qty', 'CIF $', 'NTF No']
    ]
    for detail in allotment.allotment_details.all():
        license_obj = detail.item.license if detail.item else None
        license_num_date = (
            f"{license_obj.license_number}\n{license_obj.license_date.strftime('%d-%m-%Y')}"
            if license_obj and license_obj.license_date
            else (license_obj.license_number if license_obj else 'N/A')
        )
        reg_num_date = (
            f"{license_obj.registration_number}\n{license_obj.registration_date.strftime('%d-%m-%Y')}"
            if license_obj and license_obj.registration_date
            else (license_obj.registration_number if license_obj else 'N/A')
        )
        item_unit = (detail.item.unit if detail.item else None) or 'kg'
        item_unit_display = unit_map.get(item_unit.lower(), item_unit.upper())
        detail_data.append([
            license_num_date,
            reg_num_date,
            license_obj.port if license_obj else 'N/A',
            'DFIA',
            str(detail.item.serial_number) if detail.item else 'N/A',
            f"{int(detail.qty):,} {item_unit_display}",
            f"{float(detail.cif_fc):,.2f}",
            (license_obj.notification_number.code if license_obj and license_obj.notification_number_id else 'N/A'),
        ])

    total_qty_allotted = sum(int(d.qty) for d in allotment.allotment_details.all())
    total_cif = sum(float(d.cif_fc) for d in allotment.allotment_details.all())
    detail_data.append(['Total', '', '', '', '', f"{total_qty_allotted:,} {unit_display}", f"{total_cif:,.2f}", ''])

    detail_table = Table(
        detail_data,
        colWidths=[1.2 * inch, 1.2 * inch, 0.8 * inch, 0.7 * inch, 0.8 * inch, 0.8 * inch, 0.9 * inch, 1.1 * inch],
    )
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
    ]))
    elements.append(detail_table)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def allotment_pdf_filename(allotment):
    """Return the canonical filename for an allotment PDF."""
    if allotment.invoice:
        return f'Allotment - {allotment.invoice}.pdf'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'Allotment_{allotment.company.name}_{timestamp}.pdf'
