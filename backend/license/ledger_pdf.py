# license/ledger_pdf.py
from collections import defaultdict
from decimal import Decimal
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak


def generate_license_ledger_pdf(license_obj):
    """
    Generate a detailed ledger PDF for a license grouped by item description.

    Structure:
    - License Header
    - For each unique item description:
        - Sr No, Product Description, HS Code
        - Combined table with both Allotments and BOE entries
        - Totals at bottom
    """
    buffer = BytesIO()

    # Create PDF with landscape orientation
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    # Title
    title = Paragraph(f"LICENSE LEDGER", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.1 * inch))

    # Calculate license-level balance (use centralized method)
    license_balance_cif = Decimal(str(license_obj.get_balance_cif or 0))

    # Check if license has 10% restriction and calculate remaining restriction balance
    is_restricted = False
    restriction_balance = Decimal('0')

    # Check if any import items have restricted heads
    for item in license_obj.import_license.all():
        if item.items.filter(head__is_restricted=True, head__restriction_percentage__gt=0).exists():
            is_restricted = True
            # Get the restriction percentage from the first restricted head
            first_restricted = item.items.filter(head__is_restricted=True, head__restriction_percentage__gt=0).first()
            if first_restricted and first_restricted.head:
                restriction_pct = Decimal(str(first_restricted.head.restriction_percentage or 0))
                # Calculate total restricted CIF (total export CIF × restriction percentage)
                total_export_cif = license_obj._calculate_license_credit()
                total_restricted_cif = (total_export_cif * restriction_pct / Decimal('100'))

                # Calculate debits and allotments for restricted items
                restricted_debits = Decimal('0')
                restricted_allotments = Decimal('0')
                for imp_item in license_obj.import_license.all():
                    if imp_item.items.filter(head__is_restricted=True, head__restriction_percentage__gt=0).exists():
                        restricted_debits += imp_item._calculate_item_debit()
                        restricted_allotments += imp_item._calculate_item_allotment()

                # Remaining restriction balance after debits and allotments
                restriction_balance = total_restricted_cif - restricted_debits - restricted_allotments
                restriction_balance = restriction_balance if restriction_balance >= Decimal('0') else Decimal('0')
                break

    # License Information Header
    license_info = [
        ['License Number:', license_obj.license_number, 'License Date:',
         license_obj.license_date.strftime('%d-%b-%Y') if license_obj.license_date else 'N/A'],
        ['Exporter:', license_obj.exporter.name if license_obj.exporter else 'N/A', 'Expiry Date:',
         license_obj.license_expiry_date.strftime('%d-%b-%Y') if license_obj.license_expiry_date else 'N/A'],
        ['Notification:', license_obj.notification_number, 'Purchase Status:', license_obj.purchase_status],
    ]

    if is_restricted:
        license_info.append(['Balance CIF FC:', f"{license_balance_cif:.2f}", '10% Restriction Balance:', f"{restriction_balance:.2f}"])
    else:
        license_info.append(['Balance CIF FC:', f"{license_balance_cif:.2f}", '', ''])

    license_table = Table(license_info, colWidths=[1.5*inch, 3*inch, 1.5*inch, 3*inch])

    table_style = [
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]

    # Highlight the balance row
    if len(license_info) > 3:
        table_style.extend([
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ])

    license_table.setStyle(TableStyle(table_style))

    elements.append(license_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Get all import items and group by description
    import_items = license_obj.import_license.all().prefetch_related(
        'items',
        'hs_code',
        'allotment_details__allotment__company'
    ).order_by('serial_number')

    # Group items by description
    description_groups = defaultdict(list)
    for item in import_items:
        desc = item.description if item.description else "No Description"
        description_groups[desc].append(item)

    # Process each description group, sorted by the first item's serial number
    for description, items in sorted(description_groups.items(), key=lambda x: min(item.serial_number for item in x[1])):
        # Collect all serial numbers for this description
        serial_numbers = [str(item.serial_number) for item in items]
        serial_numbers_str = ", ".join(serial_numbers)

        # Get HS code from first item
        hs_code = items[0].hs_code.hs_code if items[0].hs_code else '-'

        # Calculate quantities for this description group
        total_import_qty = Decimal('0')
        total_available_qty = Decimal('0')
        for item in items:
            total_import_qty += Decimal(str(item.quantity or 0))
            total_available_qty += Decimal(str(item.available_quantity or 0))

        # Item header with quantities
        item_info = [
            ['Sr No', 'Product Description', 'HS Code', 'Total Import Qty', 'Available Qty'],
            [
                serial_numbers_str,
                description[:60] if description else '-',
                hs_code,
                f"{total_import_qty:.2f}",
                f"{total_available_qty:.2f}"
            ]
        ]

        item_table = Table(item_info, colWidths=[1*inch, 3.5*inch, 1*inch, 1.2*inch, 1.2*inch])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, 1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        elements.append(item_table)
        elements.append(Spacer(1, 0.15 * inch))

        # Allotment table - grouped by company with row details
        allotment_by_company = defaultdict(lambda: {'qty': Decimal('0'), 'cif_fc': Decimal('0'), 'cif_inr': Decimal('0'), 'rows': []})

        allot_qty = Decimal('0')
        allot_cif_fc = Decimal('0')
        allot_cif_inr = Decimal('0')

        # Get all allotments for items in this group (exclude those converted to BOE)
        for item in items:
            allotments = item.allotment_details.filter(
                is_boe=False,
                allotment__is_boe=False  # Exclude allotments that have been converted to BOE
            ).select_related('allotment', 'allotment__company').order_by('allotment__estimated_arrival_date')

            for allot in allotments:
                company_name = allot.allotment.company.name if allot.allotment.company else 'Unknown'
                display_date = allot.allotment.estimated_arrival_date if allot.allotment.estimated_arrival_date else allot.allotment.modified_on

                allotment_by_company[company_name]['qty'] += Decimal(str(allot.qty or 0))
                allotment_by_company[company_name]['cif_fc'] += Decimal(str(allot.cif_fc or 0))
                allotment_by_company[company_name]['cif_inr'] += Decimal(str(allot.cif_inr or 0))
                allotment_by_company[company_name]['rows'].append({
                    'date': display_date.strftime('%d-%b-%Y') if display_date else '-',
                    'qty': Decimal(str(allot.qty or 0)),
                    'cif_fc': Decimal(str(allot.cif_fc or 0)),
                    'cif_inr': Decimal(str(allot.cif_inr or 0))
                })

                allot_qty += Decimal(str(allot.qty or 0))
                allot_cif_fc += Decimal(str(allot.cif_fc or 0))
                allot_cif_inr += Decimal(str(allot.cif_inr or 0))

        allotment_data = [['Company / Date', 'Quantity', 'CIF FC', 'CIF INR']]
        company_total_rows = []  # Track which rows are company totals
        for company, data in sorted(allotment_by_company.items()):
            # Add individual row details
            for row in data['rows']:
                allotment_data.append([
                    f"  {row['date']}",
                    f"{row['qty']:.1f}",
                    f"{row['cif_fc']:.2f}",
                    f"{row['cif_inr']:.2f}"
                ])
            # Add company total
            company_total_rows.append(len(allotment_data))  # Mark this row as company total
            allotment_data.append([
                company[:40],
                f"{data['qty']:.1f}",
                f"{data['cif_fc']:.2f}",
                f"{data['cif_inr']:.2f}"
            ])

        # Add allotment table if there are allotments
        if len(allotment_data) > 1:
            allotment_data.append([
                'TOTAL',
                f"{allot_qty:.1f}",
                f"{allot_cif_fc:.2f}",
                f"{allot_cif_inr:.2f}"
            ])

            allotment_table = Table(allotment_data, colWidths=[3*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fdebd0')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]
            # Make company total rows bold with light background
            for row_idx in company_total_rows:
                table_style.extend([
                    ('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8e5d3')),
                ])
            allotment_table.setStyle(TableStyle(table_style))

            elements.append(allotment_table)
            elements.append(Spacer(1, 0.15 * inch))

        # BOE table - grouped by company with row details
        boe_by_company = defaultdict(lambda: {'qty': Decimal('0'), 'cif_fc': Decimal('0'), 'cif_inr': Decimal('0'), 'rows': []})

        boe_qty = Decimal('0')
        boe_cif_fc = Decimal('0')
        boe_cif_inr = Decimal('0')

        # Get all BOE entries for items in this group
        for item in items:
            boes = item.item_details.order_by().filter(
                bill_of_entry__isnull=False
            ).order_by('bill_of_entry__bill_of_entry_date').select_related(
                'bill_of_entry', 'bill_of_entry__company'
            )

            for boe in boes:
                company_name = boe.bill_of_entry.company.name if boe.bill_of_entry.company else 'Unknown'
                boe_date = boe.bill_of_entry.bill_of_entry_date
                boe_number = boe.bill_of_entry.bill_of_entry_number

                boe_by_company[company_name]['qty'] += Decimal(str(boe.qty or 0))
                boe_by_company[company_name]['cif_fc'] += Decimal(str(boe.cif_fc or 0))
                boe_by_company[company_name]['cif_inr'] += Decimal(str(boe.cif_inr or 0))
                boe_by_company[company_name]['rows'].append({
                    'date': boe_date.strftime('%d-%b-%Y') if boe_date else '-',
                    'number': boe_number or '-',
                    'qty': Decimal(str(boe.qty or 0)),
                    'cif_fc': Decimal(str(boe.cif_fc or 0)),
                    'cif_inr': Decimal(str(boe.cif_inr or 0))
                })

                boe_qty += Decimal(str(boe.qty or 0))
                boe_cif_fc += Decimal(str(boe.cif_fc or 0))
                boe_cif_inr += Decimal(str(boe.cif_inr or 0))

        boe_data = [['Company / BOE No & Date', 'Quantity', 'CIF FC', 'CIF INR']]
        boe_company_total_rows = []  # Track which rows are company totals
        for company, data in sorted(boe_by_company.items()):
            # Add individual row details
            for row in data['rows']:
                boe_data.append([
                    f"  {row['number']} / {row['date']}",
                    f"{row['qty']:.1f}",
                    f"{row['cif_fc']:.2f}",
                    f"{row['cif_inr']:.2f}"
                ])
            # Add company total
            boe_company_total_rows.append(len(boe_data))  # Mark this row as company total
            boe_data.append([
                company[:40],
                f"{data['qty']:.1f}",
                f"{data['cif_fc']:.2f}",
                f"{data['cif_inr']:.2f}"
            ])

        # Add BOE table if there are BOEs
        if len(boe_data) > 1:
            boe_data.append([
                'TOTAL',
                f"{boe_qty:.1f}",
                f"{boe_cif_fc:.2f}",
                f"{boe_cif_inr:.2f}"
            ])

            boe_table = Table(boe_data, colWidths=[3*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            boe_table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f4e6')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]
            # Make company total rows bold with light background
            for row_idx in boe_company_total_rows:
                boe_table_style.extend([
                    ('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#c8e6c9')),
                ])
            boe_table.setStyle(TableStyle(boe_table_style))

            elements.append(boe_table)
            elements.append(Spacer(1, 0.15 * inch))

        # Show message if no transactions
        if len(allotment_data) == 1 and len(boe_data) == 1:
            no_trans = Paragraph("<i>No transactions found</i>", styles['Normal'])
        elements.append(Spacer(1, 0.3 * inch))

    # Summary table at the end
    elements.append(Spacer(1, 0.3 * inch))
    summary_title = Paragraph("SUMMARY", title_style)
    elements.append(summary_title)
    elements.append(Spacer(1, 0.1 * inch))

    summary_data = [['Item Description', 'Total Import Qty', 'CIF FC', 'Allotted Qty', 'BOE Qty', 'Available Qty', 'Balance CIF FC', 'Status']]

    # Calculate summary for each description group
    for description, items in sorted(description_groups.items(), key=lambda x: min(item.serial_number for item in x[1])):
        total_import_qty = Decimal('0')
        total_cif_fc = Decimal('0')
        total_available_qty = Decimal('0')
        allotted_qty = Decimal('0')
        boe_qty = Decimal('0')
        is_restricted_item = False

        for item in items:
            total_import_qty += Decimal(str(item.quantity or 0))
            total_cif_fc += Decimal(str(item.cif_fc or 0))
            total_available_qty += Decimal(str(item.available_quantity or 0))

            # Check if this item has restricted head
            if item.items.filter(head__is_restricted=True, head__restriction_percentage__gt=0).exists():
                is_restricted_item = True

            # Calculate allotted quantity (exclude converted allotments)
            allotments = item.allotment_details.filter(
                is_boe=False,
                allotment__is_boe=False
            )
            for allot in allotments:
                allotted_qty += Decimal(str(allot.qty or 0))

            # Calculate BOE quantity
            boes = item.item_details.filter(bill_of_entry__isnull=False)
            for boe in boes:
                boe_qty += Decimal(str(boe.qty or 0))

        # Balance CIF FC: Show license balance for all items, except use item-level balance for restricted items
        if is_restricted_item:
            # For restricted items, use item-level balance calculation
            balance_cif_fc = sum(Decimal(str(item.balance_cif_fc or 0)) for item in items)
        else:
            # For non-restricted items, show license balance
            balance_cif_fc = license_balance_cif

        # Determine status
        if total_available_qty <= 0:
            status = 'DEBITED'
        elif allotted_qty > 0:
            status = 'ALLOTED'
        else:
            status = 'BALANCE'

        # Use Paragraph for description to allow text wrapping
        desc_paragraph = Paragraph(description if description else '-', ParagraphStyle('DescStyle', parent=styles['Normal'], fontSize=8, leading=10))

        summary_data.append([
            desc_paragraph,
            f"{total_import_qty:.2f}",
            f"{total_cif_fc:.2f}",
            f"{allotted_qty:.2f}" if allotted_qty > 0 else '-',
            f"{boe_qty:.2f}" if boe_qty > 0 else '-',
            f"{total_available_qty:.2f}",
            f"{balance_cif_fc:.2f}",
            status
        ])

    summary_table = Table(summary_data, colWidths=[3*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.8*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Footer
    footer_text = Paragraph(
        f"<i>Generated on: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}</i>",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    )
    elements.append(footer_text)

    # Build PDF
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
