"""Grouped (Company > Item > Port) BOE PDF exporter (moved verbatim from api/views_export.py)."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse

from apps.core.models import ExchangeRateModel
from apps.core.utils.pdf_utils import create_pdf_exporter

from .common import REPORTLAB_AVAILABLE, _decimal_or_default, _text_response
from .grouping import group_boe

if REPORTLAB_AVAILABLE:
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table as RLTable, TableStyle


def export_grouped_pdf(queryset):
    """Export grouped bill of entries to PDF grouped by Company → Item → Port"""
    if not REPORTLAB_AVAILABLE:
        return _text_response("PDF export not available", 503)

    pdf_exporter = create_pdf_exporter(
        title="Bill of Entry Report",
        filename_prefix="Bill_of_Entries",
        orientation='landscape'
    )

    if not pdf_exporter:
        return _text_response("PDF export not available", 503)

    # Group data
    grouped_data = group_boe(queryset)

    # Active exchange rate for the mini-table in the header
    active_rate = ExchangeRateModel.get_active_rate()

    # Calculate grand totals
    total_inr = sum(boe['total_inr']
                    for company in grouped_data.values()
                    for license_dict in company.values()
                    for product in license_dict.values()
                    for port in product.values()
                    for boe in port)
    total_fc = sum(boe['total_fc']
                   for company in grouped_data.values()
                   for license_dict in company.values()
                   for product in license_dict.values()
                   for port in product.values()
                   for boe in port)

    def shorten_exporter(name, max_words=2):
        """Return first N words of an exporter name followed by '…'."""
        if not name or name == '--':
            return name or '--'
        words = name.split()
        if len(words) <= max_words:
            return name
        return ' '.join(words[:max_words]) + '…'  # …

    # Create PDF response - inline display for new tab
    response = HttpResponse(content_type='application/pdf')
    today = datetime.now().strftime('%d-%m-%Y')
    filename = f'BOE Report - {today}.pdf'
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    buffer = BytesIO()
    doc = pdf_exporter.create_document(buffer)

    elements = []

    # Item sub-header style
    item_style = ParagraphStyle(
        'ItemHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=HexColor('#1e40af'),
        spaceAfter=2,
        spaceBefore=3,
        leftIndent=0,
    )

    # Header: title + totals on left, exchange rate mini-table on right
    subtitle_text = (f"Total CIF (FC): ${pdf_exporter.format_number(total_fc)} | "
                     f"Total CIF (INR): {pdf_exporter.format_number(total_inr)}")

    if active_rate:
        exch_data = [
            ['Exch. Rate', active_rate.date.strftime('%d-%m-%Y')],
            ['USD', str(active_rate.usd)],
            ['EUR', str(active_rate.euro)],
            ['GBP', str(active_rate.pound_sterling)],
            ['CNY', str(active_rate.chinese_yuan)],
        ]
        exch_table = RLTable(exch_data, colWidths=[0.7 * inch, 0.8 * inch])
        exch_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), pdf_exporter.HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        title_para = Paragraph("Bill of Entry Report", pdf_exporter.title_style)
        subtitle_para = Paragraph(subtitle_text, pdf_exporter.subtitle_style)
        ts_style = ParagraphStyle(
            'TS',
            parent=pdf_exporter.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
        ts_para = Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", ts_style)

        header_layout = RLTable([[title_para, exch_table]], colWidths=[8.85 * inch, 1.5 * inch])
        header_layout.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        elements.append(header_layout)
        elements.append(subtitle_para)
        elements.append(ts_para)
    else:
        pdf_exporter.add_title(elements, subtitle=subtitle_text)

    # 18 columns — full landscape A4 (~11.35" usable after 0.15" margins).
    # Qty(KGS) and Value($) restored.  Column widths are set so that
    # Port, Lic.Date, Lic.Port, BOE $., BOE CIF never split across 2 lines.
    col_widths = [
        0.25 * inch,  # Sr No
        0.78 * inch,  # BOE Number   (+0.20)
        0.75 * inch,  # BOE Date     (+0.10)
        0.54 * inch,  # Port
        0.50 * inch,  # Qty (KGS)
        0.45 * inch,  # Unit Price ($)
        0.73 * inch,  # Value ($)    (+0.08)
        0.45 * inch,  # Exchange Rate
        0.80 * inch,  # Item Name
        0.50 * inch,  # Invoice
        0.83 * inch,  # Exporter
        0.98 * inch,  # License No.  (+0.20)
        0.65 * inch,  # Lic. Date
        0.54 * inch,  # Lic. Port
        0.28 * inch,  # Item Sr.
        0.50 * inch,  # BOE Qty.
        0.90 * inch,  # BOE $.
        0.92 * inch,  # BOE CIF      (+0.10)
    ]  # total = 11.35"

    table_header = [
        'Sr\nNo', 'BOE\nNumber', 'BOE\nDate', 'Port',
        'Qty\n(KGS)', 'Unit\nPrice ($)', 'Value\n($)', 'Exch.\nRate',
        'Item\nName', 'Invoice',
        'Exporter', 'License\nNo.', 'Lic. Date', 'Lic. Port', 'Item\nSr.',
        'BOE\nQty.', 'BOE $.', 'BOE CIF'
    ]

    # Process each company (sorted alphabetically, None values last)
    for company_name, license_dict in sorted(grouped_data.items(), key=lambda x: (x[0] is None, x[0] or '')):
        pdf_exporter.add_company_header(elements, company_name)

        company_total_qty = 0
        company_total_inr = 0
        company_total_fc = 0

        # Merge license_serial level → group by product → port (same as xlsx)
        merged_products = defaultdict(lambda: defaultdict(list))
        for license_serial, products_dict in license_dict.items():
            for product_name, ports_dict in products_dict.items():
                for port_code, boe_list in ports_dict.items():
                    merged_products[product_name][port_code].extend(boe_list)

        # Process each item (product) within this company
        for product_name in sorted(merged_products.keys()):
            ports_dict = merged_products[product_name]

            elements.append(Paragraph(f"Item: {product_name}", item_style))

            table_data = [table_header]
            sr_no = 1
            dfia_subtotal_rows = []

            for port_code in sorted(ports_dict.keys()):
                port_total_qty = 0
                port_total_value = 0
                port_total_inr = 0

                for boe in ports_dict[port_code]:
                    if boe['license_details']:
                        first_detail = boe['license_details'][0]
                        unit_price = (
                            boe['total_fc'] / boe['total_quantity']
                            if boe['total_quantity'] > 0 else 0
                        )

                        # Main BOE row (first licence detail) — 18 columns
                        table_data.append([
                            str(sr_no),
                            boe['boe_number'],
                            boe['boe_date'],
                            port_code,
                            pdf_exporter.format_number(boe['total_quantity'], decimals=0),
                            pdf_exporter.format_number(unit_price),
                            pdf_exporter.format_number(boe['total_fc']),
                            pdf_exporter.format_number(boe['exchange_rate']),
                            boe['product_name'],
                            boe['invoice_no'],
                            shorten_exporter(first_detail['exporter_name']),
                            first_detail['license_no'],
                            first_detail['license_date'],
                            first_detail['license_port'],
                            first_detail['item_sr_no'],
                            pdf_exporter.format_number(first_detail['qty'], decimals=0),
                            pdf_exporter.format_number(first_detail['cif_fc']),
                            pdf_exporter.format_number(first_detail['cif_inr'])
                        ])

                        # Additional licence detail rows — 18 columns (10 empty leading)
                        for detail in boe['license_details'][1:]:
                            table_data.append([
                                '', '', '', '', '', '', '', '', '', '',
                                shorten_exporter(detail['exporter_name']),
                                detail['license_no'],
                                detail['license_date'],
                                detail['license_port'],
                                detail['item_sr_no'],
                                pdf_exporter.format_number(detail['qty'], decimals=0),
                                pdf_exporter.format_number(detail['cif_fc']),
                                pdf_exporter.format_number(detail['cif_inr'])
                            ])

                        # Preserve every BOE item line and add a clear
                        # DFIA subtotal only for a multi-line allocation.
                        if len(boe['license_details']) > 1:
                            total_dfia_qty = sum(
                                (_decimal_or_default(detail['qty']) for detail in boe['license_details']),
                                Decimal('0'),
                            )
                            total_dfia_value = sum(
                                (_decimal_or_default(detail['cif_fc']) for detail in boe['license_details']),
                                Decimal('0'),
                            )
                            dfia_subtotal_rows.append(len(table_data))
                            table_data.append([
                                '', '', '', '', '', '', '', '', '', '',
                                'Total DFIA allocation', '', '', '', '',
                                pdf_exporter.format_number(total_dfia_qty, decimals=0),
                                pdf_exporter.format_number(total_dfia_value),
                                '',
                            ])

                    sr_no += 1
                    port_total_qty += boe['total_quantity']
                    port_total_value += boe['total_fc']
                    port_total_inr += boe['total_inr']

                # Port total row — 18 cols; totals in Qty, Value$, and BOE CIF cols
                table_data.append([
                    '',
                    f'Port Total ({port_code})',
                    '', '',
                    pdf_exporter.format_number(port_total_qty, decimals=0),   # Qty
                    '',
                    pdf_exporter.format_number(port_total_value),              # Value $
                    '', '', '', '', '', '', '', '', '', '',
                    pdf_exporter.format_number(port_total_inr)                 # BOE CIF
                ])

                company_total_qty += port_total_qty
                company_total_inr += port_total_inr
                company_total_fc += port_total_value

            # col 10 = Exporter — left-align for readable name wrapping
            table = pdf_exporter.create_table(table_data, col_widths=col_widths, repeating_rows=1, left_align_cols={10})

            # Right-align numeric cols (0-indexed) for 18-col layout:
            # Qty(4), UnitPrice(5), Value$(6), ExchRate(7), BOEQty(15), BOE$(16), BOECIF(17)
            additional_styles = []
            for col_idx in [4, 5, 6, 7, 15, 16, 17]:
                additional_styles.append(
                    ('ALIGN', (col_idx, 1), (col_idx, len(table_data) - 1), 'RIGHT')
                )

            for subtotal_row in dfia_subtotal_rows:
                additional_styles.extend([
                    ('SPAN', (10, subtotal_row), (14, subtotal_row)),
                    ('BACKGROUND', (10, subtotal_row), (17, subtotal_row), colors.HexColor('#dbeafe')),
                    ('TEXTCOLOR', (10, subtotal_row), (17, subtotal_row), colors.HexColor('#1e3a8a')),
                    ('FONTNAME', (10, subtotal_row), (17, subtotal_row), 'Helvetica-Bold'),
                    ('ALIGN', (10, subtotal_row), (14, subtotal_row), 'LEFT'),
                    ('TOPPADDING', (10, subtotal_row), (17, subtotal_row), 4),
                    ('BOTTOMPADDING', (10, subtotal_row), (17, subtotal_row), 4),
                ])

            # Port Total rows — bold + subtle header background
            for row_idx, row in enumerate(table_data):
                if row[1] and 'Port Total' in str(row[1]):
                    additional_styles.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
                    additional_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), pdf_exporter.HEADER_BG))

            table.setStyle(TableStyle(additional_styles))
            elements.append(table)
            pdf_exporter.add_spacer(elements, 0.15)

        # Company grand total
        summary_data = [[
            'Grand Total:',
            f"Qty: {pdf_exporter.format_number(company_total_qty, decimals=0)} KGS",
            f"CIF (FC): ${pdf_exporter.format_number(company_total_fc)}",
            f"CIF (INR): {pdf_exporter.format_number(company_total_inr)}"
        ]]
        summary_table = pdf_exporter.create_summary_table(summary_data)
        elements.append(summary_table)
        pdf_exporter.add_spacer(elements, 0.3)

    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response
