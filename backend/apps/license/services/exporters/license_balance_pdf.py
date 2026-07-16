"""PDF renderer for the license balance report.

Extracted verbatim from ``LicenseDetailsViewSet.balance_pdf`` as part of the
clean-architecture refactor: the viewset (delivery layer) now only resolves the
license and delegates rendering here. Behaviour is unchanged.
"""
def build_balance_pdf_response(license_obj, request):
    """
    Generate PDF report for license balance details with all BOEs and Allotments.
    """
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io
    from datetime import date
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems


    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                          rightMargin=10*mm, leftMargin=10*mm,
                          topMargin=12*mm, bottomMargin=12*mm)

    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=3,
        fontName='Helvetica-Bold'
    )

    # Add title
    title = Paragraph(f"<b>License Balance Report</b>", title_style)
    elements.append(title)
    elements.append(Spacer(1, 3))

    # Add license header information split into 2 rows for clarity
    # Check if license has specific document types
    has_tl = license_obj.license_documents.filter(type='TRANSFER LETTER').exists()
    has_copy = license_obj.license_documents.filter(type='LICENSE COPY').exists()

    # Build license number with link if documents exist
    license_number_text = license_obj.license_number or '-'
    if has_tl or has_copy:
        # Get the base URL from request
        base_url = request.build_absolute_uri('/').rstrip('/')
        merge_url = f"{base_url}/api/licenses/{license_obj.id}/merged-documents/"
        license_number_text = f'{license_obj.license_number or "-"} (<link href="{merge_url}" color="blue"><u>Copy</u></link>)'

    header_data = [
        # Row 1: Headers
        ['License Number', 'License Date', 'License Expiry Date', 'Exporter Name', 'Port Name'],
        # Row 1: Values
        [
            Paragraph(license_number_text, styles['Normal']),
            license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-',
            license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-',
            Paragraph(license_obj.exporter.name if license_obj.exporter else '-', styles['Normal']),
            Paragraph(license_obj.port.name if license_obj.port else '-', styles['Normal'])
        ],
        # Row 2: Headers (spanning to match 5 columns)
        ['Purchase Status', 'Balance CIF', 'Get Norm Class', '', 'Latest Transfer'],
        # Row 2: Values
        [
            license_obj.purchase_status or '-',
            f"{float(license_obj.balance_cif or 0):.2f}",
            license_obj.get_norm_class or '-',
            '',
            Paragraph(str(license_obj.latest_transfer) if license_obj.latest_transfer else '-', styles['Normal'])
        ]
    ]

    # Landscape A4 is ~277mm wide, with margins = ~257mm usable width
    # Split into 5 columns: 50mm, 35mm, 40mm, 70mm, 62mm = 257mm
    header_table = Table(header_data, colWidths=[50*mm, 35*mm, 40*mm, 70*mm, 62*mm])
    header_table.setStyle(TableStyle([
        # Row 1 header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        # Row 2 header
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.whitesmoke),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        # Data rows
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ecf0f1')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ecf0f1')),
        # Common styles
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 2), (-1, 2), 8),
        ('FONTSIZE', (0, 1), (-1, 1), 7.5),
        ('FONTSIZE', (0, 3), (-1, 3), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 5))

    # Export Items Section
    if license_obj.export_license.exists():
        # Section header as table row
        export_section_header = Table([['Export Items']], colWidths=[275*mm])
        export_section_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(export_section_header)

        export_data = [['Item', 'Total CIF', 'Balance CIF']]
        for item in license_obj.export_license.all():
            item_desc = item.description or (str(item.norm_class) if item.norm_class else None) or 'None'
            export_data.append([
                Paragraph(item_desc, styles['Normal']),
                f"{float(item.cif_fc or item.fob_fc or 0):.2f}",
                f"{float(license_obj.balance_cif or 0):.2f}"
            ])

        export_table = Table(export_data, colWidths=[185*mm, 45*mm, 45*mm])
        export_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')])
        ]))
        elements.append(export_table)
        elements.append(Spacer(1, 8))

    # Import Items Section with Usage Details
    if license_obj.import_license.exists():
        # Section header as table row
        import_section_header = Table([['Import Items']], colWidths=[275*mm])
        import_section_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(import_section_header)

        for item in license_obj.import_license.all():
            # Main item data
            item_names = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else '-'

            # Get HS code label
            hs_code_display = str(item.hs_code.hs_code if item.hs_code else '-')

            item_data = [[
                'Sr', 'HS Code', 'Description', 'Item', 'Total Qty',
                'Allotted', 'Debited', 'Available', 'CIF FC', 'Bal CIF'
            ], [
                str(item.serial_number or '-'),
                hs_code_display,
                Paragraph(str(item.description or '-'), styles['Normal']),
                Paragraph(item_names, styles['Normal']),
                f"{float(item.quantity or 0):.2f}",
                f"{float(item.allotted_quantity or 0):.2f}",
                f"{float(item.debited_quantity or 0):.2f}",
                f"{float(item.available_quantity or 0):.2f}",
                f"{float(item.cif_fc or 0):.2f}",
                f"{float(item.balance_cif_fc or 0):.2f}"
            ]]

            item_table = Table(item_data, colWidths=[12*mm, 25*mm, 60*mm, 50*mm, 23*mm, 21*mm, 21*mm, 21*mm, 21*mm, 21*mm])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1'))
            ]))
            elements.append(item_table)
            elements.append(Spacer(1, 3))

            # BOEs
            boes = RowDetails.objects.filter(
                sr_number_id=item.id,
                transaction_type='D'
            ).select_related('bill_of_entry', 'bill_of_entry__company', 'bill_of_entry__port')

            if boes.exists():
                # BOEs header as section row
                boe_section_header = Table([['BOEs']], colWidths=[275*mm])
                boe_section_header.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333')),
                ]))
                elements.append(boe_section_header)

                boe_data = [['BOE Number', 'Date', 'Port', 'Company', 'Qty', 'CIF $', 'CIF INR']]

                # Calculate totals
                total_qty = 0
                total_cif_fc = 0
                total_cif_inr = 0

                for detail in boes:
                    total_qty += float(detail.qty or 0)
                    total_cif_fc += float(detail.cif_fc or 0)
                    total_cif_inr += float(detail.cif_inr or 0)

                    boe_data.append([
                        detail.bill_of_entry.bill_of_entry_number,
                        detail.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if detail.bill_of_entry.bill_of_entry_date else '-',
                        Paragraph(detail.bill_of_entry.port.name if detail.bill_of_entry.port else '-', styles['Normal']),
                        Paragraph(detail.bill_of_entry.company.name or '-' if detail.bill_of_entry.company else '-', styles['Normal']),
                        f"{float(detail.qty):.2f}",
                        f"{float(detail.cif_fc):.2f}",
                        f"{float(detail.cif_inr):.2f}"
                    ])

                # Add total footer row
                boe_data.append([
                    '', '', '', 'Total',
                    f"{total_qty:.2f}",
                    f"{total_cif_fc:.2f}",
                    f"{total_cif_inr:.2f}"
                ])

                boe_table = Table(boe_data, colWidths=[40*mm, 25*mm, 50*mm, 70*mm, 25*mm, 30*mm, 35*mm])
                boe_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#e8f5e9')]),
                    # Footer row styling
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, -1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                elements.append(boe_table)
                elements.append(Spacer(1, 5))

            # Allotments
            # Only show allotments where bill_of_entry is NULL (not yet converted to BOE)
            allotments = AllotmentItems.objects.filter(
                item_id=item.id,
                allotment__bill_of_entry__isnull=True
            ).select_related('allotment', 'allotment__company')

            if allotments.exists():
                # Allotments header as section row
                allot_section_header = Table([['Allotments']], colWidths=[275*mm])
                allot_section_header.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e67e22')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333')),
                ]))
                elements.append(allot_section_header)

                allot_data = [['Company', 'Qty', 'CIF $', 'CIF INR']]

                # Calculate totals
                total_allot_qty = 0
                total_allot_cif_fc = 0
                total_allot_cif_inr = 0

                for allot in allotments:
                    total_allot_qty += float(allot.qty or 0)
                    total_allot_cif_fc += float(allot.cif_fc or 0)
                    total_allot_cif_inr += float(allot.cif_inr or 0)

                    allot_data.append([
                        Paragraph(allot.allotment.company.name if allot.allotment.company else '-', styles['Normal']),
                        f"{float(allot.qty):.2f}",
                        f"{float(allot.cif_fc):.2f}",
                        f"{float(allot.cif_inr):.2f}"
                    ])

                # Add total footer row
                allot_data.append([
                    'Total',
                    f"{total_allot_qty:.2f}",
                    f"{total_allot_cif_fc:.2f}",
                    f"{total_allot_cif_inr:.2f}"
                ])

                allot_table = Table(allot_data, colWidths=[155*mm, 40*mm, 40*mm, 40*mm])
                allot_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fef5e7')]),
                    # Footer row styling
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fdebd0')),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, -1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                elements.append(allot_table)
                elements.append(Spacer(1, 5))

            # Balance calculation as table footer
            balance = float(item.quantity or 0) - float(item.debited_quantity or 0) - float(item.allotted_quantity or 0)
            balance_table = Table([[f'Balance Quantity: {balance:.2f}']], colWidths=[275*mm])
            balance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8e8e8')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#e74c3c')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(balance_table)
            elements.append(Spacer(1, 8))

    # Add Notes Section if notes exist
    if license_obj.balance_report_notes:
        notes_header = Table([['Notes']], colWidths=[275*mm])
        notes_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(notes_header)

        notes_content = Table([[Paragraph(license_obj.balance_report_notes, styles['Normal'])]], colWidths=[275*mm])
        notes_content.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffacd')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(notes_content)

    # ── End-of-PDF Summary Table ─────────────────────────────────────────
    # One flat row per BOE/Allotment per item — easy to copy-paste to Excel
    # Light green = BOE rows, Light red = Allotment rows
    COLOR_BOE   = colors.HexColor('#d9ead3')   # light green
    COLOR_ALLOT = colors.HexColor('#fce8e6')   # light red
    COLOR_HDR   = colors.HexColor('#1a1a1a')

    # Paragraph style for wrapping text in summary cells
    wrap_style = ParagraphStyle('wrap', parent=styles['Normal'], fontSize=7.5, leading=10)

    def P(text):
        return Paragraph(str(text), wrap_style)

    # Collect all rows — sort by item name before building table
    # Columns: License No | License Date | Item | Type | Company | Reference | Qty | Rate | CIF Value (FC)
    # BOE Reference  = "BOE number\nDate"
    # Allot Reference = "Invoice\nETA: date" (if available)
    summary_data = [['License No', 'License Date', 'Item', 'Type', 'Company', 'Reference', 'Qty', 'Rate', 'CIF Value (FC)']]
    summary_rows = []  # (sort_key, row_cells, color)
    total_cif    = 0.0

    license_date_str = license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-'
    lic_no = license_obj.license_number or '-'

    # Pre-aggregate by item name across all sr numbers.
    from collections import defaultdict
    from decimal import Decimal as _Dec
    from django.db.models import Sum as _Sum, DecimalField as _DF, Value as _Val
    from django.db.models.functions import Coalesce as _Coalesce

    # New restriction model: condition_type on LicenseImportItemsModel is
    # the source of truth. %-conditions share a pool from compute_condition_pools();
    # AU / blank use the full licence balance.
    from apps.license.services.condition_pool import compute_condition_pools as _ccp
    _cond_pools = _ccp(license_obj)

    _bal_agg = defaultdict(lambda: {'qty': 0.0, 'total_qty': 0.0, 'sr_ids': [], 'description': '', 'hs_code': '', 'condition_type': '', 'qty_by_cond': {}})
    for _item in license_obj.import_license.all():
        _key = ', '.join(sorted([i.name for i in _item.items.all()])) if _item.items.exists() else (_item.description or '-')
        _avail = float(_item.available_quantity or 0)
        _bal_agg[_key]['qty'] += _avail
        _bal_agg[_key]['total_qty'] += float(_item.quantity or 0)
        _bal_agg[_key]['sr_ids'].append(_item.serial_number)
        if not _bal_agg[_key]['description']:
            _bal_agg[_key]['description'] = _item.description or _key
        if not _bal_agg[_key]['hs_code']:
            _bal_agg[_key]['hs_code'] = str(_item.hs_code.hs_code if _item.hs_code else '-')
        if _item.condition_type and not _bal_agg[_key]['condition_type']:
            _bal_agg[_key]['condition_type'] = _item.condition_type
        # Per-condition qty breakdown for E1's Display/Util-qty split.
        _ct = (_item.condition_type or '').strip()
        _bal_agg[_key]['qty_by_cond'][_ct] = _bal_agg[_key]['qty_by_cond'].get(_ct, 0.0) + _avail

    for item in license_obj.import_license.all():
        item_name = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else (item.description or '-')

        boes = RowDetails.objects.filter(
            sr_number_id=item.id, transaction_type='D'
        ).select_related('bill_of_entry', 'bill_of_entry__port', 'bill_of_entry__company')

        for rd in boes:
            qty     = float(rd.qty or 0)
            cif     = float(rd.cif_fc or 0)
            rate    = cif / qty if qty else 0.0
            total_cif += cif
            boe_company = rd.bill_of_entry.company.name if rd.bill_of_entry.company else '-'
            ref_no  = rd.bill_of_entry.bill_of_entry_number or '-'
            ref_date = rd.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if rd.bill_of_entry.bill_of_entry_date else ''
            ref_str = f"{ref_no}\n{ref_date}" if ref_date else ref_no
            product = rd.bill_of_entry.product_name or item_name
            summary_rows.append((product.lower(), [
                P(lic_no), P(license_date_str), P(product),
                P('BOE'), P(boe_company), P(ref_str),
                P(f"{qty:,.2f}"), P(f"{rate:.2f}"), P(f"{cif:,.2f}"),
            ], COLOR_BOE))

        allotments = AllotmentItems.objects.filter(
            item_id=item.id, allotment__bill_of_entry__isnull=True
        ).select_related('allotment', 'allotment__company')

        for ai in allotments:
            qty     = float(ai.qty or 0)
            cif     = float(ai.cif_fc or 0)
            rate    = cif / qty if qty else 0.0
            total_cif += cif
            company = ai.allotment.company.name if ai.allotment.company else '-'
            invoice = ai.allotment.invoice or '-'
            eta     = ai.allotment.estimated_arrival_date.strftime('%d-%m-%Y') if ai.allotment.estimated_arrival_date else ''
            ref_str = f"{invoice}\nETA: {eta}" if eta else invoice
            product = ai.allotment.item_name or item_name
            summary_rows.append((product.lower(), [
                P(lic_no), P(license_date_str), P(product),
                P('Allotment'), P(company), P(ref_str),
                P(f"{qty:,.2f}"), P(f"{rate:.2f}"), P(f"{cif:,.2f}"),
            ], COLOR_ALLOT))

    # Sort by item name
    summary_rows.sort(key=lambda x: x[0])
    row_colors = []
    for _, row_cells, color in summary_rows:
        summary_data.append(row_cells)
        row_colors.append(color)

    if len(summary_data) > 1:
        # Total row
        summary_data.append([P(''), P(''), P(''), P(''), P('TOTAL'), P(''), P(''), P(''), P(f"{total_cif:,.2f}")])
        row_colors.append(colors.HexColor('#f2f2f2'))

        # ── License info mini-header (License No | License Date | Total CIF) ──
        total_license_cif = total_cif + float(license_obj.balance_cif or 0)
        info_style = ParagraphStyle('info', parent=styles['Normal'], fontSize=8, leading=11,
                                    textColor=colors.white, fontName='Helvetica-Bold')
        def IP(label, value):
            return Paragraph(f"<b>{label}:</b> {value}", info_style)

        info_row = Table([[
            IP('License No', lic_no),
            IP('License Date', license_date_str),
            IP('Total CIF', f"{total_license_cif:,.2f}"),
        ]], colWidths=[92*mm, 92*mm, 93*mm])
        info_row.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_HDR),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(Spacer(1, 10))
        elements.append(info_row)

        # Section header
        summ_hdr = Table([['Summary (BOE & Allotments)']], colWidths=[277*mm])
        summ_hdr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_HDR),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(summ_hdr)

        # col widths: lic_no, lic_date, item, type, company, reference, qty, rate, cif = 277mm
        col_w = [28*mm, 22*mm, 55*mm, 18*mm, 40*mm, 35*mm, 20*mm, 22*mm, 37*mm]
        summ_table = Table(summary_data, colWidths=col_w)

        style_cmds = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HDR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('ALIGN', (6, 0), (-1, -1), 'RIGHT'),   # qty, rate, cif right-aligned
            ('ALIGN', (0, 0), (5, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Total row bold
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f2f2f2')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]
        # Apply per-row background colours (skip header row at index 0)
        for i, bg in enumerate(row_colors, start=1):
            if i < len(summary_data):  # skip total row (handled above)
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

        summ_table.setStyle(TableStyle(style_cmds))
        elements.append(summ_table)

    # ── Balance Summary Table ─────────────────────────────────────────────
    if _bal_agg:
        total_bal_cif_fc = float(license_obj.balance_cif or 0)
        COLOR_YELLOW = colors.HexColor('#ffff00')

        # "Summary (Balance Quantity)" section header
        bal_hdr = Table([['Summary (Balance Quantity)']], colWidths=[277*mm])
        bal_hdr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_HDR),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(bal_hdr)

        # col widths: hsn, item_name, bal_qty, unit_price, cif_fc = 277mm
        # 30 + 87 + 45 + 45 + 70 = 277mm
        bal_col_w = [30*mm, 87*mm, 45*mm, 45*mm, 70*mm]

        Pb      = ParagraphStyle('balwrap',     parent=styles['Normal'], fontSize=8, leading=11)
        Pb_hdr  = ParagraphStyle('balwrap_hdr', parent=styles['Normal'], fontSize=8, leading=11,
                                 textColor=colors.white, fontName='Helvetica-Bold')
        Pb_yel  = ParagraphStyle('balwrap_yel', parent=styles['Normal'], fontSize=9, leading=12,
                                 fontName='Helvetica-Bold')

        def BP(text):
            return Paragraph(str(text), Pb)
        def BH(text):   # white bold header cell
            return Paragraph(str(text), Pb_hdr)
        def BY(text):   # yellow-cell (black bold)
            return Paragraph(str(text), Pb_yel)

        _license_balance = float(license_obj.get_balance_cif or 0)
        bal_table_data = [
            # Row 0: cols 0-3 merged "BALANCE CIF $" | col 4 = total (yellow)
            [BH('BALANCE CIF $'), '', '', '', BY(f"{total_bal_cif_fc:,.2f}")],
            # Row 1: column headers
            [BH('HSN Code'), BH('Item Name'), BH('Bal Qty'), BH('Unit Price'), BH('CIF FC')],
        ]
        for item_key in sorted(_bal_agg.keys()):
            b_qty = _bal_agg[item_key]['qty']
            cond = _bal_agg[item_key].get('condition_type') or ''
            if cond in _cond_pools:
                b_cif = float(min(_cond_pools[cond], _Dec(str(_license_balance))))
            else:
                b_cif = _license_balance
            unit_price = b_cif / b_qty if b_qty else 0.0
            desc       = _bal_agg[item_key]['description'] or item_key
            hs         = _bal_agg[item_key]['hs_code']
            bal_table_data.append([
                BP(hs),
                BP(desc),
                BP(f"{b_qty:,.2f}"),
                BP(f"{unit_price:,.2f}"),
                BP(f"{b_cif:,.2f}"),
            ])

        bal_table = Table(bal_table_data, colWidths=bal_col_w)
        bal_style = TableStyle([
            # Row 0: merge cols 0-3, dark header | col 4 yellow
            ('SPAN', (0, 0), (3, 0)),
            ('BACKGROUND', (0, 0), (3, 0), COLOR_HDR),
            ('BACKGROUND', (4, 0), (4, 0), COLOR_YELLOW),
            ('TEXTCOLOR', (4, 0), (4, 0), colors.black),
            ('ALIGN', (0, 0), (3, 0), 'CENTER'),
            ('ALIGN', (4, 0), (4, 0), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            # Row 1: column headers
            ('BACKGROUND', (0, 1), (-1, 1), COLOR_HDR),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            # Data rows: cols 2-4 right-aligned
            ('FONTSIZE', (0, 2), (-1, -1), 8),
            ('ALIGN', (2, 2), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 2), (1, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            # All cells
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ])
        bal_table.setStyle(bal_style)
        elements.append(Spacer(1, 8))
        elements.append(bal_table)

    # Build PDF
    doc.build(elements)

    # Get PDF from buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{license_obj.license_number}-balance.pdf"'
    response.write(pdf)

    return response
