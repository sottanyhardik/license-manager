# trade/bill_of_supply_pdf.py
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image


def num_to_words_indian(amount):
    """Convert number to Indian rupees words"""
    try:
        from num2words import num2words
        return num2words(int(amount), lang='en_IN').upper()
    except ImportError:
        # Fallback if num2words is not available
        return str(int(amount))


def generate_bill_of_supply_pdf(trade, include_signature=True):
    """
    Generate Bill of Supply PDF for SALE transactions matching the purple invoice format.

    Args:
        trade: LicenseTrade instance with direction='SALE'
        include_signature: Boolean - whether to include signature and stamp (default: True)

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()

    # Get company color (default to #800080 purple)
    from_company = trade.from_company
    company_color = '#800080'  # Default purple

    if from_company and from_company.bill_colour:
        # Ensure color has # prefix
        color_value = from_company.bill_colour.strip()
        if color_value:
            if not color_value.startswith('#'):
                color_value = '#' + color_value
            company_color = color_value

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    # Container for the 'Flowable' objects
    elements = []

    # Styles
    styles = getSampleStyleSheet()

    # Header company name style
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor(company_color),
        fontName='Helvetica-Bold',
        alignment=TA_RIGHT,
        spaceAfter=2
    )

    company_address_style = ParagraphStyle(
        'CompanyAddressStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.black,
        alignment=TA_RIGHT,
        leading=10
    )

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor(company_color),
        spaceAfter=15,
        spaceBefore=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor(company_color),
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12
    )

    small_style = ParagraphStyle(
        'SmallStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )

    # Header with Logo and Company Details
    header_data = []

    # Logo section (left) and Company details (right)
    logo_cell = ""
    if from_company.logo:
        try:
            # Load image and maintain aspect ratio
            from PIL import Image as PILImage
            img = PILImage.open(from_company.logo.path)
            img_width, img_height = img.size

            # Set max dimensions while maintaining aspect ratio
            max_width = 1.5 * inch
            max_height = 1.5 * inch

            # Calculate aspect ratio
            aspect = img_width / img_height

            if aspect > 1:  # Landscape
                width = max_width
                height = max_width / aspect
            else:  # Portrait or square
                height = max_height
                width = max_height * aspect

            logo_cell = Image(from_company.logo.path, width=width, height=height)
        except:
            logo_cell = Paragraph("", normal_style)
    else:
        logo_cell = Paragraph("", normal_style)

    company_details = f"""
        <b><font size="14" color="{company_color}">{from_company.name.upper()}</font></b><br/>
        <font size="8">
        {trade.from_addr_line_1 or ''}<br/>
        {trade.from_addr_line_2 or ''}<br/>
        PAN: {trade.from_pan or 'N/A'} | GST: {trade.from_gst or 'N/A'}
        </font>
    """

    header_data.append([logo_cell, Paragraph(company_details, company_address_style)])

    header_table = Table(header_data, colWidths=[2 * inch, 5.3 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(company_color)),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 0.2 * inch))

    # Invoice Title
    title = Paragraph("<u>Invoice</u>", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.15 * inch))

    # Invoice Number and Date
    invoice_date = trade.invoice_date.strftime('%d-%m-%Y') if trade.invoice_date else 'N/A'

    invoice_info_data = [[
        Paragraph(f"<b>Invoice No.</b> {trade.invoice_number}", normal_style),
        Paragraph(f"<b>Date:</b> {invoice_date}", normal_style)
    ]]

    invoice_info_table = Table(invoice_info_data, colWidths=[4.65 * inch, 2.65 * inch])
    invoice_info_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(invoice_info_table)
    elements.append(Spacer(1, 0.1 * inch))

    # Bill To Section
    to_company = trade.to_company
    bill_to_text = f"""
        <font color="{company_color}"><b>Bill To:</b></font><br/>
        <br/>
        <b>{to_company.name.upper()}</b><br/>
        {trade.to_addr_line_1 or ''}<br/>
        {trade.to_addr_line_2 or ''}<br/>
        PAN: {trade.to_pan or 'N/A'}<br/>
        GST: {trade.to_gst or 'N/A'}
    """

    bill_to_para = Paragraph(bill_to_text, normal_style)
    bill_to_table = Table([[bill_to_para]], colWidths=[7.3 * inch])
    bill_to_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(bill_to_table)
    elements.append(Spacer(1, 0.15 * inch))

    # Line Items Table
    # Header row with purple background
    header_style_center = ParagraphStyle('HeaderStyle', parent=small_style, textColor=colors.white, alignment=TA_CENTER,
                                         fontName='Helvetica-Bold')
    right_align_style = ParagraphStyle('RightAlign', parent=small_style, alignment=TA_RIGHT, wordWrap='LTR')

    # Determine the mode from first line (assuming all lines have same mode)
    trade_lines = trade.lines.all()
    if not trade_lines:
        return None

    billing_mode = trade_lines[0].mode if trade_lines else 'CIF_INR'

    # Build headers and data based on mode
    if billing_mode == 'CIF_INR':
        # CIF_INR Mode: DFIA Number | Mode | CIF (FC) | Exchange Rate | CIF (INR) | Percentage (%) | Amount (INR)
        line_items_header = [[
            Paragraph('<b>DFIA Number</b>', header_style_center),
            Paragraph('<b>Mode</b>', header_style_center),
            Paragraph('<b>CIF (FC)</b>', header_style_center),
            Paragraph('<b>Exchange Rate</b>', header_style_center),
            Paragraph('<b>CIF (INR)</b>', header_style_center),
            Paragraph('<b>Percentage (%)</b>', header_style_center),
            Paragraph('<b>Amount (INR)</b>', header_style_center)
        ]]

        line_items_data = []
        total_cif_fc = 0
        total_cif_inr = 0

        for line in trade_lines:
            sr_label = ''
            if line.sr_number:
                license_no = line.sr_number.license.license_number if line.sr_number.license else ''
                license_date = line.sr_number.license.license_date if line.sr_number.license else ''
                port = ' - ' + line.sr_number.license.port.code if line.sr_number.license and line.sr_number.license.port else ''
                sr_label = f"{license_no} - {license_date} {port}"

            cif_fc = float(line.cif_fc or 0)
            exc_rate = float(line.exc_rate or 0)
            cif_inr = float(line.cif_inr or 0)
            pct = float(line.pct or 0)
            amount = float(line.amount_inr or 0)

            total_cif_fc += cif_fc
            total_cif_inr += cif_inr

            line_items_data.append([
                Paragraph(sr_label, small_style),
                Paragraph('CIF INR', small_style),
                Paragraph(f"<nobr>{cif_fc:,.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{exc_rate:,.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{cif_inr:,.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{pct:.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{amount:,.2f}</nobr>", right_align_style)
            ])

        total_amount = float(trade.total_amount) if trade.total_amount else 0
        total_style_left = ParagraphStyle('TotalStyle', parent=small_style, textColor=colors.HexColor(company_color),
                                          fontName='Helvetica-Bold')
        total_style_right = ParagraphStyle('TotalRightStyle', parent=small_style,
                                           textColor=colors.HexColor(company_color),
                                           alignment=TA_RIGHT, fontName='Helvetica-Bold')

        line_items_data.append([
            Paragraph('<b>Total</b>', total_style_left),
            '',
            Paragraph(f'<b><nobr>{total_cif_fc:,.2f}</nobr></b>', total_style_right),
            Paragraph('<b>-</b>', total_style_right),
            Paragraph(f'<b><nobr>{total_cif_inr:,.2f}</nobr></b>', total_style_right),
            Paragraph('<b>-</b>', total_style_right),
            Paragraph(f'<b><nobr>{total_amount:,.2f}</nobr></b>', total_style_right)
        ])

        all_line_data = line_items_header + line_items_data
        # Total width should be 7.3 inches (same as other tables)
        line_items_table = Table(all_line_data,
                                 colWidths=[2.1 * inch, 0.7 * inch, 1 * inch, 1 * inch, 1 * inch, 0.8 * inch, 0.7 * inch])

    elif billing_mode == 'FOB_INR':
        # FOB_INR Mode: DFIA Number | Mode | FOB (INR) | Percentage (%) | Amount (INR)
        line_items_header = [[
            Paragraph('<b>DFIA Number</b>', header_style_center),
            Paragraph('<b>Mode</b>', header_style_center),
            Paragraph('<b>FOB (INR)</b>', header_style_center),
            Paragraph('<b>Percentage (%)</b>', header_style_center),
            Paragraph('<b>Amount (INR)</b>', header_style_center)
        ]]

        line_items_data = []
        total_fob_inr = 0

        for line in trade_lines:
            sr_label = ''
            if line.sr_number:
                license_no = line.sr_number.license.license_number if line.sr_number.license else ''
                license_date = line.sr_number.license.license_date if line.sr_number.license else ''
                port = ' - ' + line.sr_number.license.port.code if line.sr_number.license and line.sr_number.license.port else ''
                sr_label = f"{license_no} - {license_date} {port}"

            fob_inr = float(line.fob_inr or 0)
            pct = float(line.pct or 0)
            amount = float(line.amount_inr or 0)

            total_fob_inr += fob_inr

            line_items_data.append([
                Paragraph(sr_label, small_style),
                Paragraph('FOB INR', small_style),
                Paragraph(f"<nobr>{fob_inr:,.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{pct:.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{amount:,.2f}</nobr>", right_align_style)
            ])

        total_amount = float(trade.total_amount) if trade.total_amount else 0
        total_style_left = ParagraphStyle('TotalStyle', parent=small_style, textColor=colors.HexColor(company_color),
                                          fontName='Helvetica-Bold')
        total_style_right = ParagraphStyle('TotalRightStyle', parent=small_style,
                                           textColor=colors.HexColor(company_color),
                                           alignment=TA_RIGHT, fontName='Helvetica-Bold')

        line_items_data.append([
            Paragraph('<b>Total</b>', total_style_left),
            '',
            Paragraph(f'<b><nobr>{total_fob_inr:,.2f}</nobr></b>', total_style_right),
            Paragraph('<b>-</b>', total_style_right),
            Paragraph(f'<b><nobr>{total_amount:,.2f}</nobr></b>', total_style_right)
        ])

        all_line_data = line_items_header + line_items_data
        # Total width should be 7.3 inches (same as other tables)
        line_items_table = Table(all_line_data, colWidths=[2.5 * inch, 1 * inch, 1.5 * inch, 1 * inch, 1.3 * inch])

    else:  # QTY mode
        # QTY Mode: DFIA Number | Mode | Quantity (KG) | Rate (INR/KG) | Amount (INR)
        line_items_header = [[
            Paragraph('<b>DFIA Number</b>', header_style_center),
            Paragraph('<b>Mode</b>', header_style_center),
            Paragraph('<b>Quantity (KG)</b>', header_style_center),
            Paragraph('<b>Rate (INR/KG)</b>', header_style_center),
            Paragraph('<b>Amount (INR)</b>', header_style_center)
        ]]

        line_items_data = []
        total_qty = 0

        for line in trade_lines:
            sr_label = ''
            if line.sr_number:
                license_no = line.sr_number.license.license_number if line.sr_number.license else ''
                license_date = line.sr_number.license.license_date if line.sr_number.license else ''
                port = ' - ' + line.sr_number.license.port.code if line.sr_number.license and line.sr_number.license.port else ''
                sr_label = f"{license_no} - {license_date} {port}"

            qty = float(line.qty_kg or 0)
            rate = float(line.rate_inr_per_kg or 0)
            amount = float(line.amount_inr or 0)

            total_qty += qty

            line_items_data.append([
                Paragraph(sr_label, small_style),
                Paragraph('QTY', small_style),
                Paragraph(f"<nobr>{qty:,.4f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{rate:,.2f}</nobr>", right_align_style),
                Paragraph(f"<nobr>{amount:,.2f}</nobr>", right_align_style)
            ])

        total_amount = float(trade.total_amount) if trade.total_amount else 0
        total_style_left = ParagraphStyle('TotalStyle', parent=small_style, textColor=colors.HexColor(company_color),
                                          fontName='Helvetica-Bold')
        total_style_right = ParagraphStyle('TotalRightStyle', parent=small_style,
                                           textColor=colors.HexColor(company_color),
                                           alignment=TA_RIGHT, fontName='Helvetica-Bold')

        line_items_data.append([
            Paragraph('<b>Total</b>', total_style_left),
            '',
            Paragraph(f'<b><nobr>{total_qty:,.4f}</nobr></b>', total_style_right),
            Paragraph('<b>-</b>', total_style_right),
            Paragraph(f'<b><nobr>{total_amount:,.2f}</nobr></b>', total_style_right)
        ])

        all_line_data = line_items_header + line_items_data
        # Total width should be 7.3 inches (same as other tables)
        line_items_table = Table(all_line_data, colWidths=[2.5 * inch, 1 * inch, 1.5 * inch, 1 * inch, 1.3 * inch])

    line_items_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(company_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data rows
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        # DFIA Number column - left align
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        # Mode column - center align
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        # All numeric columns - right align
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        # Total row
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor(company_color)),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(line_items_table)
    elements.append(Spacer(1, 0.1 * inch))

    # Total Amount in Words
    amount_words = num_to_words_indian(total_amount)
    words_text = f'<font color="{company_color}"><b>Total Amount in Words:</b></font> RUPEES {amount_words} ONLY'

    words_para = Paragraph(words_text, normal_style)
    elements.append(words_para)
    elements.append(Spacer(1, 0.15 * inch))

    # Remarks Section
    remarks_text = f"""
        <font color="{company_color}"><b>Remark:</b></font><br/>
        {trade.remarks or 'N/A'}
    """
    if trade.boe:
        boe_text = f"Bill OF Entry No. {trade.boe.bill_of_entry_number if hasattr(trade.boe, 'bill_of_entry_number') else trade.boe}"
        boe_date = f"Dated. {trade.boe.bill_of_entry_date if hasattr(trade.boe, 'bill_of_entry_date') else 'N/A'}"
        remarks_text = f"""
            <font color="{company_color}"><b>Remark:</b></font><br/>
            {boe_text}<br/>
            {boe_date}<br/>
            {trade.remarks or ''}
        """

    remarks_para = Paragraph(remarks_text, normal_style)
    remarks_table = Table([[remarks_para]], colWidths=[7.3 * inch])
    remarks_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(remarks_table)
    elements.append(Spacer(1, 0.15 * inch))

    # Bank Details and Authorized Signatory
    bank_details_text = f"""
        <font color="{company_color}"><b>Bank Details:</b></font><br/>
        <br/>
        <b>Account No:</b> {from_company.bank_account_number or 'N/A'}<br/>
        <b>Bank Name:</b> {from_company.bank_name or 'N/A'}<br/>
        <b>IFSC:</b> {from_company.ifsc_code or 'N/A'}<br/>
        <b>Account Type:</b> {from_company.get_account_type_display() if from_company.account_type else 'N/A'}
    """

    # Signature section
    sig_center_style = ParagraphStyle('SigStyle', parent=normal_style, alignment=TA_CENTER)
    signature_content = [
        Paragraph(f'<font color="{company_color}"><b>Authorised Signatory</b></font>', sig_center_style)]

    # Only add signature and stamp if include_signature is True
    if include_signature:
        # Add signature image if available
        if from_company.signature:
            try:
                from PIL import Image as PILImage
                sig_img = PILImage.open(from_company.signature.path)
                sig_width, sig_height = sig_img.size

                # Max dimensions for signature
                max_sig_width = 1.5 * inch
                max_sig_height = 0.7 * inch

                # Calculate aspect ratio
                sig_aspect = sig_width / sig_height

                if sig_aspect > (max_sig_width / max_sig_height):
                    width = max_sig_width
                    height = max_sig_width / sig_aspect
                else:
                    height = max_sig_height
                    width = max_sig_height * sig_aspect

                sig_image = Image(from_company.signature.path, width=width, height=height)
                signature_content.append(sig_image)
            except:
                signature_content.append(Spacer(1, 0.5 * inch))
        else:
            signature_content.append(Spacer(1, 0.5 * inch))

        # Add stamp image if available
        if from_company.stamp:
            try:
                from PIL import Image as PILImage
                stamp_img = PILImage.open(from_company.stamp.path)
                stamp_width, stamp_height = stamp_img.size

                # Max dimensions for stamp (square)
                max_stamp_size = 1.2 * inch

                # Calculate aspect ratio
                stamp_aspect = stamp_width / stamp_height

                if stamp_aspect > 1:
                    width = max_stamp_size
                    height = max_stamp_size / stamp_aspect
                else:
                    height = max_stamp_size
                    width = max_stamp_size * stamp_aspect

                stamp_image = Image(from_company.stamp.path, width=width, height=height)
                signature_content.append(stamp_image)
            except:
                pass
    else:
        # Add empty space when signature is not included
        signature_content.append(Spacer(1, 0.8 * inch))

    # Name below signature
    name_center_style = ParagraphStyle('NameStyle', parent=small_style, alignment=TA_CENTER, fontName='Helvetica-Bold')
    signature_content.append(Paragraph(from_company.name, name_center_style))

    # Create nested table for signature
    sig_table = Table([[item] for item in signature_content])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    footer_data = [[
        Paragraph(bank_details_text, normal_style),
        sig_table
    ]]

    footer_table = Table(footer_data, colWidths=[3.65 * inch, 3.65 * inch])
    footer_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    elements.append(footer_table)
    elements.append(Spacer(1, 0.1 * inch))

    # Footer note
    footer_note = Paragraph(
        f'<para alignment="center"><font size="8" color="{company_color}"><b>Note:</b> This is a system-generated invoice.</font></para>',
        styles['Normal']
    )
    elements.append(footer_note)

    # Build PDF
    doc.build(elements)

    # Get the value of the BytesIO buffer and return it
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
