# trade/bill_of_supply_pdf.py
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image


def num_to_words_indian(amount):
    """Convert number to Indian rupees words"""
    try:
        # Remove decimals for word conversion
        whole_amount = int(amount)

        # Conversion logic for Indian numbering system
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
        teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
                 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

        if whole_amount == 0:
            return 'Zero'

        def convert_below_thousand(n):
            if n == 0:
                return ''
            elif n < 10:
                return ones[n]
            elif n < 20:
                return teens[n - 10]
            elif n < 100:
                return tens[n // 10] + (' ' + ones[n % 10] if n % 10 != 0 else '')
            else:
                return ones[n // 100] + ' Hundred' + (' ' + convert_below_thousand(n % 100) if n % 100 != 0 else '')

        def convert_indian(n):
            if n < 1000:
                return convert_below_thousand(n)

            crore = n // 10000000
            n %= 10000000
            lakh = n // 100000
            n %= 100000
            thousand = n // 1000
            n %= 1000

            result = []
            if crore > 0:
                result.append(convert_below_thousand(crore) + ' Crore')
            if lakh > 0:
                result.append(convert_below_thousand(lakh) + ' Lakh')
            if thousand > 0:
                result.append(convert_below_thousand(thousand) + ' Thousand')
            if n > 0:
                result.append(convert_below_thousand(n))

            return ' '.join(result)

        return convert_indian(whole_amount)
    except Exception as e:
        return str(int(amount))


def generate_bill_of_supply_pdf(trade, include_signature=True):
    """
    Generate Bill of Supply PDF for SALE transactions.

    Args:
        trade: LicenseTrade instance with direction='SALE'
        include_signature: Boolean - whether to include signature and stamp (default: True)

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()

    # Get company color (default to black)
    from_company = trade.from_company
    company_color = colors.black

    if from_company and from_company.bill_colour:
        color_value = from_company.bill_colour.strip()
        if color_value:
            if not color_value.startswith('#'):
                color_value = '#' + color_value
            try:
                company_color = colors.HexColor(color_value)
            except:
                company_color = colors.black

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=15  # Reduced margins to fit content on one page
    )

    elements = []
    styles = getSampleStyleSheet()

    # Page width
    page_width = A4[0] - 60  # minus margins

    # Logo and Title section
    import os
    from PIL import Image as PILImage

    # Title style
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Normal'],
        fontSize=16,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=10
    )

    logo_img = None
    # Try to add company logo
    import logging
    logger = logging.getLogger(__name__)

    if from_company:
        logger.info(f"Company: {from_company.name}, Has logo attr: {hasattr(from_company, 'logo')}, Logo value: {from_company.logo if hasattr(from_company, 'logo') else 'N/A'}")

        if hasattr(from_company, 'logo') and from_company.logo:
            try:
                logo_path = from_company.logo.path
                logger.info(f"Logo path: {logo_path}, Exists: {os.path.exists(logo_path)}")

                if os.path.exists(logo_path):
                    # Get image dimensions to maintain aspect ratio
                    pil_img = PILImage.open(logo_path)
                    img_width, img_height = pil_img.size
                    aspect = img_height / float(img_width)

                    # Set max dimensions
                    max_width = 1.5 * inch
                    max_height = 0.75 * inch

                    # Calculate size maintaining aspect ratio
                    if aspect > (max_height / max_width):
                        # Height is limiting factor
                        display_height = max_height
                        display_width = max_height / aspect
                    else:
                        # Width is limiting factor
                        display_width = max_width
                        display_height = max_width * aspect

                    logo_img = Image(logo_path, width=display_width, height=display_height)
                    logger.info(f"Logo loaded successfully: {display_width}x{display_height}")
                else:
                    logger.warning(f"Logo file does not exist at path: {logo_path}")
            except Exception as e:
                # Log error but continue
                logger.error(f"Failed to load logo: {e}", exc_info=True)
                logo_img = None
        else:
            logger.info("Company has no logo or logo field is empty")
    else:
        logger.warning("No from_company found")

    if logo_img:
        # Create table with logo on left, title in center
        logo_title_table = Table([
            [logo_img, Paragraph('<b>Bill of Supply</b>', title_style), '']
        ], colWidths=[page_width*0.25, page_width*0.5, page_width*0.25])
        logo_title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(logo_title_table)
    else:
        # Just title without logo
        elements.append(Paragraph('<b>Bill of Supply</b>', title_style))

    # Header table (Seller info + Invoice details)
    from_addr = []
    if from_company:
        from_addr.append(f'<b>{from_company.name}</b>')
        if trade.from_addr_line_1:
            from_addr.append(trade.from_addr_line_1)
        if trade.from_addr_line_2:
            from_addr.append(trade.from_addr_line_2)
        if trade.from_gst:
            from_addr.append(f'GSTIN/UIN: {trade.from_gst}')
        # Extract state from address
        if 'Maharashtra' in (trade.from_addr_line_2 or ''):
            from_addr.append('State Name : Maharashtra, Code : 27')
        # Add contact if available
        if hasattr(from_company, 'phone') and from_company.phone:
            from_addr.append(f'Contact : {from_company.phone}')

    to_addr = []
    to_company = trade.to_company
    if to_company:
        to_addr.append(f'<b>{to_company.name}</b>')
        if trade.to_addr_line_1:
            to_addr.append(trade.to_addr_line_1)
        if trade.to_addr_line_2:
            to_addr.append(trade.to_addr_line_2)
        if trade.to_gst:
            to_addr.append(f'GSTIN/UIN       : {trade.to_gst}')
        if trade.to_pan:
            to_addr.append(f'PAN/IT No        : {trade.to_pan}')

    # Format invoice date
    invoice_date_str = trade.invoice_date.strftime('%d-%b-%y') if trade.invoice_date else ''

    header_data = [
        [
            Paragraph('<br/>'.join(from_addr), styles['Normal']),
            Paragraph(f'<b>Invoice No.</b><br/>{trade.invoice_number or ""}', styles['Normal']),
            Paragraph(f'<b>Dated</b><br/>{invoice_date_str}', styles['Normal'])
        ],
        [
            Paragraph('<b>Buyer (Bill to)</b><br/>' + '<br/>'.join(to_addr), styles['Normal']),
            '', ''
        ]
    ]

    header_table = Table(header_data, colWidths=[page_width*0.7, page_width*0.15, page_width*0.15])
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (0, 1), (-1, 1)),  # Span buyer row
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(header_table)

    # Determine billing mode from first line (assuming all lines use same mode)
    billing_mode = trade.lines.first().mode if trade.lines.exists() else 'QTY'

    # Items table - dynamic headers based on billing mode
    if billing_mode == 'QTY':
        # QTY mode: Sl No | Description | HSN | Quantity | Rate per KG | Amount
        header_row = [
            Paragraph('<b>Sl<br/>No.</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Description of Goods</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>HSN/SAC</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Quantity</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Rate per KG</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Amount</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))
        ]
        col_count = 6
    elif billing_mode == 'CIF_INR':
        # CIF mode: Sl No | Description | HSN | CIF FC | EXC RT | CIF INR | Rate % | Amount
        header_row = [
            Paragraph('<b>Sl<br/>No.</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Description of Goods</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>HSN/SAC</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>CIF FC</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>EXC RT</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>CIF INR</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Rate %</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Amount</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))
        ]
        col_count = 8
    else:  # FOB_INR
        # FOB mode: Sl No | Description | HSN | FOB INR | Rate % | Amount
        header_row = [
            Paragraph('<b>Sl<br/>No.</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Description of Goods</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>HSN/SAC</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>FOB INR</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Rate %</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
            Paragraph('<b>Amount</b>', ParagraphStyle('center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))
        ]
        col_count = 6

    items_data = [header_row]

    # Add items
    subtotal = 0
    total_qty = 0
    total_cif_fc = 0
    total_cif_inr = 0
    total_fob_inr = 0

    for idx, line in enumerate(trade.lines.all(), start=1):
        # Calculate amount
        amount = line.amount_inr or 0
        subtotal += amount

        # Get description: license_number - license_date - port_code (wrapped to 2 lines)
        description = ''
        if line.sr_number and line.sr_number.license:
            lic = line.sr_number.license
            license_num = lic.license_number or 'Unknown'
            license_date = lic.license_date.strftime('%d-%m-%Y') if lic.license_date else ''
            port_code = lic.port.code if lic.port and hasattr(lic.port, 'code') else (lic.port.name if lic.port else '')

            # Format as: license_num - license_date (line 1)
            #            port_code (line 2)
            line1 = f"{license_num}"
            if license_date:
                line1 += f" - {license_date}"

            if port_code:
                description = f"{line1}<br/>{port_code}"
            else:
                description = line1
        elif line.description:
            description = line.description

        # Wrap description in Paragraph for proper formatting
        description_para = Paragraph(description, styles['Normal'])

        # Build row based on billing mode
        # Create right-aligned style for numbers
        right_align_style = ParagraphStyle('right', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)

        if billing_mode == 'QTY':
            qty_str = f"{line.qty_kg:,.3f} Kg" if line.qty_kg else "0.000 Kg"
            total_qty += (line.qty_kg or 0)
            row = [
                str(idx),
                description_para,
                '47060000',  # Always use fixed HSN code for paper/pulp products
                Paragraph(qty_str, right_align_style),
                Paragraph(f"{line.rate_inr_per_kg:,.2f}" if line.rate_inr_per_kg else "0.00", right_align_style),
                Paragraph(f"{amount:,.2f}", right_align_style)
            ]
        elif billing_mode == 'CIF_INR':
            total_cif_fc += (line.cif_fc or 0)
            total_cif_inr += (line.cif_inr or 0)
            row = [
                str(idx),
                description_para,
                '47060000',  # Always use fixed HSN code for paper/pulp products
                Paragraph(f"{line.cif_fc:,.2f}" if line.cif_fc else "0.00", right_align_style),
                Paragraph(f"{line.exc_rate:,.2f}" if line.exc_rate else "0.00", right_align_style),
                Paragraph(f"{line.cif_inr:,.2f}" if line.cif_inr else "0.00", right_align_style),
                Paragraph(f"{line.pct:.2f}" if line.pct else "0.00", right_align_style),
                Paragraph(f"{amount:,.2f}", right_align_style)
            ]
        else:  # FOB_INR
            total_fob_inr += (line.fob_inr or 0)
            row = [
                str(idx),
                description_para,
                '47060000',  # Always use fixed HSN code for paper/pulp products
                Paragraph(f"{line.fob_inr:,.2f}" if line.fob_inr else "0.00", right_align_style),
                Paragraph(f"{line.pct:.2f}" if line.pct else "0.00", right_align_style),
                Paragraph(f"{amount:,.2f}", right_align_style)
            ]

        items_data.append(row)

    # Calculate roundoff
    rounded_total = round(subtotal)
    roundoff = rounded_total - subtotal

    # Add rounding off row (dynamic based on column count)
    roundoff_sign = '(-)' if roundoff < 0 else ''
    roundoff_row = [''] * col_count
    roundoff_row[1] = Paragraph('<i>Less :</i>', ParagraphStyle('italic', parent=styles['Normal'], fontSize=9))
    roundoff_row[2] = Paragraph('<b><i>Rounding Off</i></b>', ParagraphStyle('italic', parent=styles['Normal'], fontSize=9, fontName='Helvetica-BoldOblique'))
    roundoff_row[-1] = Paragraph(f"{roundoff_sign}{abs(roundoff):.2f}", ParagraphStyle('right', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT))
    items_data.append(roundoff_row)

    # Add empty rows for spacing (min 5 rows total to keep content compact)
    while len(items_data) < 7:  # Header + 5 rows minimum (reduced from 12 to fit on one page)
        items_data.append([''] * col_count)

    # Add total row (dynamic based on mode)
    total_row = [''] * col_count
    total_row[2] = Paragraph('<b>Total</b>', ParagraphStyle('bold', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=TA_RIGHT))

    # Create right-aligned bold style for total numbers with no word wrap
    bold_right_style = ParagraphStyle('bold_right', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=TA_RIGHT, wordWrap='LTR', splitLongWords=False)

    if billing_mode == 'QTY':
        total_row[3] = Paragraph(f"<b>{total_qty:,.3f} Kg</b>", bold_right_style)
    elif billing_mode == 'CIF_INR':
        total_row[3] = Paragraph(f"<b>{total_cif_fc:,.2f}</b>", bold_right_style)
        total_row[5] = Paragraph(f"<b>{total_cif_inr:,.2f}</b>", bold_right_style)
    else:  # FOB_INR
        total_row[3] = Paragraph(f"<b>{total_fob_inr:,.2f}</b>", bold_right_style)

    total_row[-1] = Paragraph(f'<b>Rs. {rounded_total:,.2f}</b>', bold_right_style)
    items_data.append(total_row)

    # Use full page width for items table - dynamic column widths based on mode
    if billing_mode == 'QTY':
        col_widths = [
            page_width*0.05,   # Sl No
            page_width*0.40,   # Description (wider for license info)
            page_width*0.10,   # HSN
            page_width*0.15,   # Quantity
            page_width*0.15,   # Rate per KG
            page_width*0.15    # Amount
        ]
    elif billing_mode == 'CIF_INR':
        col_widths = [
            page_width*0.05,   # Sl No
            page_width*0.24,   # Description
            page_width*0.08,   # HSN
            page_width*0.12,   # CIF FC
            page_width*0.10,   # EXC RT
            page_width*0.13,   # CIF INR (increased from 0.12)
            page_width*0.10,   # Rate %
            page_width*0.18    # Amount
        ]
    else:  # FOB_INR
        col_widths = [
            page_width*0.05,   # Sl No
            page_width*0.38,   # Description
            page_width*0.10,   # HSN
            page_width*0.20,   # FOB INR
            page_width*0.10,   # Rate %
            page_width*0.17    # Amount
        ]

    items_table = Table(items_data, colWidths=col_widths)

    items_table.setStyle(TableStyle([
        # Header row
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Sl No center
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),  # HSN center
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),   # Quantity right
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),   # Rate right
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),  # per center
        ('ALIGN', (6, 0), (6, -1), 'RIGHT'),   # Amount right
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        # Total row
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 10),
    ]))

    elements.append(items_table)

    # Amount in words and footer
    amount_words = num_to_words_indian(rounded_total)

    footer_data = [
        [
            Paragraph(f'<b>Amount Chargeable (in words)</b><br/>INR {amount_words} Only', styles['Normal']),
            Paragraph('<b>E. & O.E</b>', ParagraphStyle('right', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT))
        ]
    ]

    footer_table = Table(footer_data, colWidths=[page_width*0.8, page_width*0.2])
    footer_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(footer_table)

    # Prepare Bank Details text
    bank_details_text = ''
    has_bank_details = False
    if from_company and (from_company.bank_account_number or from_company.bank_name or from_company.ifsc_code):
        has_bank_details = True
        bank_details_text = '<b>Bank Details</b><br/>'
        if from_company.bank_name:
            bank_details_text += f'Bank Name: {from_company.bank_name}<br/>'
        if from_company.bank_account_number:
            bank_details_text += f'Account Number: {from_company.bank_account_number}<br/>'
        if from_company.ifsc_code:
            bank_details_text += f'IFSC Code: {from_company.ifsc_code}'

    # Combined table with Bank Details and Declaration merged
    # Row 1: Bank Details (left) | for Company (right)
    # Row 2: Declaration (left) | Signature (right)

    declaration_data = []

    # First row: Bank Details
    if has_bank_details:
        declaration_data.append([
            Paragraph(bank_details_text, styles['Normal']),
            Paragraph(f'<b>for {from_company.name if from_company else ""}</b>',
                     ParagraphStyle('right', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT))
        ])

    # Second row: Declaration
    left_content = Paragraph(
        f"<b>Company's PAN        : {trade.from_pan or 'N/A'}</b><br/><br/>"
        "<b>Declaration</b><br/>"
        "We declare that this invoice shows the actual price of the goods described "
        "and that all particulars are true and correct.",
        styles['Normal']
    )

    declaration_data.append([left_content, ''])  # Declaration (left) + Signature (right)

    if include_signature and from_company:
        # Add signature/stamp if requested
        sig_rows = []

        # First row: Signature and Stamp side by side (removed "for Company Name" as it's now in Bank Details)
        sig_stamp_row = []

        # Try to add signature image - bigger size using full space
        sig_img = None
        if hasattr(from_company, 'signature') and from_company.signature:
            try:
                import os
                sig_path = from_company.signature.path
                if os.path.exists(sig_path):
                    sig_img = Image(sig_path, width=1.3*inch, height=0.7*inch)  # Bigger size
            except Exception as e:
                logger.error(f"Failed to load signature: {e}")
                sig_img = None

        # Try to add stamp image - bigger size using full space
        stamp_img = None
        if hasattr(from_company, 'stamp') and from_company.stamp:
            try:
                import os
                from PIL import Image as PILImage
                stamp_path = from_company.stamp.path
                if os.path.exists(stamp_path):
                    # Get original stamp dimensions
                    pil_stamp = PILImage.open(stamp_path)
                    stamp_width, stamp_height = pil_stamp.size

                    # Use original aspect ratio, max size 1.0 inch (bigger for full space)
                    max_size = 1.0 * inch
                    aspect = stamp_height / float(stamp_width)

                    if aspect > 1:
                        # Taller than wide
                        display_height = min(max_size, stamp_height)
                        display_width = display_height / aspect
                    else:
                        # Wider than tall or square
                        display_width = min(max_size, stamp_width)
                        display_height = display_width * aspect

                    stamp_img = Image(stamp_path, width=display_width, height=display_height)
            except Exception as e:
                logger.error(f"Failed to load stamp: {e}")
                stamp_img = None

        # Place signature and stamp side by side with bigger sizes
        if sig_img and stamp_img:
            # Both inside, side by side - using full width of right column
            sig_stamp_table = Table([[sig_img, stamp_img]], colWidths=[1.4*inch, 1.1*inch])
            sig_stamp_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            sig_rows.append([sig_stamp_table])
        elif sig_img:
            sig_rows.append([sig_img])
        elif stamp_img:
            sig_rows.append([stamp_img])
        else:
            # No images, add spacing
            sig_rows.append([Paragraph('<br/><br/>', styles['Normal'])])

        # Last row: "Authorised Signatory"
        sig_rows.append([Paragraph('<b>Authorised Signatory</b>',
                                   ParagraphStyle('right', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))])

        # Create signature table - use full width of right column (35% of page)
        # Remove all internal grid lines to merge vertically
        sig_table = Table(sig_rows, colWidths=[page_width*0.35])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (0, 0), 'TOP'),  # First row (for PURPLEHUB) at TOP
            ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),  # Middle rows (signature/stamp) in MIDDLE
            ('LEFTPADDING', (0, 0), (-1, -1), 3),  # Add some padding to keep it inside
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0, colors.white),  # Remove all internal lines
        ]))
        # Set signature in the last row's right column
        declaration_data[-1][1] = sig_table
    else:
        declaration_data[-1][1] = Paragraph(
            f'<b>for {from_company.name if from_company else ""}</b><br/><br/><br/><br/><br/><br/>'
            '<b>Authorised Signatory</b>',
            ParagraphStyle('right', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)
        )

    # Create merged table with dynamic row heights
    if has_bank_details:
        row_heights = [0.7*inch, 1.3*inch]  # Row 1: Bank Details (increased to fit all text), Row 2: Declaration (bigger for signature)
    else:
        row_heights = [1.3*inch]  # Only Declaration row

    declaration_table = Table(declaration_data, colWidths=[page_width*0.65, page_width*0.35], rowHeights=row_heights)

    # Build style based on number of rows
    style_list = [
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Outer box
        ('LINEAFTER', (0, 0), (0, -1), 0.5, colors.black),  # Vertical line between columns
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # All left cells TOP
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]

    if has_bank_details:
        # Only add horizontal line below Bank Details in the LEFT column (not the right column with signature)
        style_list.append(('LINEBELOW', (0, 0), (0, 0), 0.5, colors.black))  # Only left cell
        # Right column of second row (signature) should be BOTTOM aligned
        style_list.append(('VALIGN', (1, 1), (1, 1), 'BOTTOM'))
    else:
        # Right column (signature) should be BOTTOM aligned
        style_list.append(('VALIGN', (1, 0), (1, 0), 'BOTTOM'))

    declaration_table.setStyle(TableStyle(style_list))
    elements.append(declaration_table)

    # Footer text (removed spacer to save space)
    elements.append(Paragraph(
        '<b>This is a Computer Generated Invoice</b>',
        ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    ))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
