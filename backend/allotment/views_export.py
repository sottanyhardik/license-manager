# allotment/views_export.py
from collections import defaultdict
from datetime import datetime
from io import BytesIO

from django.http import HttpResponse
from rest_framework.decorators import action

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def add_grouped_export_action(viewset_class):
    """
    Decorator to add grouped export functionality to AllotmentViewSet
    """

    @action(detail=False, methods=['get'], url_path='download')
    def download_grouped_export(self, request):
        """
        Export allotments grouped by company and item name.
        Query params:
            - type: 'AT' for allotment (default), 'TL' for transfer letter
            - export: 'pdf' or 'xlsx' (from query params, e.g., _export=pdf)
            - company: filter by company ID
            - item_name: filter by item name
            - is_boe: filter by is_boe status
        """
        export_type = request.query_params.get('type', 'AT')
        export_format = request.query_params.get('_export', 'pdf').lower()

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Filter only allotments with details and order by company, item, port
        # Use distinct() without parameters to avoid duplication from prefetch_related
        queryset = queryset.filter(
            allotment_details__isnull=False
        ).distinct().order_by(
            'company__name', 'item_name', 'port__code'
        ).prefetch_related(
            'allotment_details__item__license__exporter',
            'allotment_details__item__hs_code',
            'company',
            'port'
        )

        if export_format == 'pdf':
            return self._export_grouped_pdf(queryset, export_type)
        elif export_format == 'xlsx':
            return self._export_grouped_xlsx(queryset, export_type)
        else:
            return HttpResponse("Invalid export format. Use 'pdf' or 'xlsx'.", status=400)

    def _export_grouped_pdf(self, queryset, export_type):
        """Export grouped allotments to PDF"""
        if not REPORTLAB_AVAILABLE:
            return HttpResponse("PDF export not available", status=500)

        # Group data
        grouped_data = self._group_allotments(queryset)

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'Pending_Allotments_{timestamp}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                                leftMargin=0.3 * inch, rightMargin=0.3 * inch)

        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=6,
            alignment=TA_CENTER
        )

        # Calculate totals
        total_usd = sum(item['value'] for company in grouped_data.values()
                        for ports in company.values()
                        for items in ports.values()
                        for item in items)

        elements.append(Paragraph("Allotment Report", title_style))
        elements.append(
            Paragraph(f"Total USD $: {total_usd:,.2f} &nbsp;&nbsp;&nbsp; {datetime.now().strftime('%d-%m-%Y')}",
                      ParagraphStyle('subtitle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)))
        elements.append(Spacer(1, 12))

        # Process each company
        for company_name, items_dict in grouped_data.items():
            # Company header
            elements.append(Paragraph(f"<b>{company_name}</b>",
                                      ParagraphStyle('company', parent=styles['Heading2'], fontSize=12)))
            elements.append(Spacer(1, 6))

            # Track company totals
            company_total_qty = 0
            company_total_value = 0

            # Process each item within company
            for item_name_key, ports_dict in items_dict.items():
                # Get the actual item name from first allotment for display
                first_allot = next(iter(next(iter(ports_dict.values())))) if ports_dict else None
                display_item_name = first_allot[
                    'item_name'] if first_allot and 'item_name' in first_allot else item_name_key

                # Item subheader (optional, can be styled differently)
                if len(items_dict) > 1:  # Only show if multiple items
                    elements.append(Paragraph(f"Item: {display_item_name}",
                                              ParagraphStyle('item', parent=styles['Normal'], fontSize=12,
                                                             textColor=colors.black)))
                    elements.append(Spacer(1, 3))

                # Process each port within item
                for port_code, allotments in ports_dict.items():
                    # Table header with DFIA columns
                    table_data = [[
                        'Sr No', 'Allotment\nDate', 'Port', 'Quantity\n(KGS)',
                        'Unit Price ($)', 'Value ($)', 'Item Name', 'Invoice', 'ETA', 'BOE',
                        'DFIA No.', 'DFIA Date', 'DFIA Port', 'Item Sr.', 'DFIA Qty.', 'DFIA $.', 'DFIA CIF'
                    ]]

                    sr_no = 1
                    for allot in allotments:
                        # Add rows for each license detail
                        for idx, detail in enumerate(allot['details']):
                            # Create Paragraph objects for long text fields to enable wrapping
                            item_name_text = allot.get('item_name', display_item_name)
                            invoice_text = allot['invoice']

                            # Wrap long text in Paragraph for word wrapping
                            item_name_para = Paragraph(item_name_text,
                                                       ParagraphStyle('cell', parent=styles['Normal'], fontSize=7,
                                                                      leading=8))
                            invoice_para = Paragraph(invoice_text,
                                                     ParagraphStyle('cell', parent=styles['Normal'], fontSize=7,
                                                                    leading=8))

                            if idx == 0:
                                # First license row: show allotment data + license data
                                table_data.append([
                                    sr_no,
                                    allot['date'],
                                    allot['port'],
                                    f"{int(allot['quantity']):,}",
                                    f"{allot['unit_price']:.2f}",
                                    f"{allot['value']:,.2f}",
                                    item_name_para,
                                    invoice_para,
                                    allot['eta'],
                                    'Yes' if allot.get('is_boe') else 'No',
                                    detail['dfia_no'],
                                    detail['dfia_date'],
                                    detail['dfia_port'],
                                    detail['item_sr_no'],
                                    f"{int(detail['dfia_qty']):,}",
                                    f"{detail['dfia_value']:,.2f}",
                                    f"{detail['dfia_cif']:,.2f}"
                                ])
                            else:
                                # Subsequent license rows: empty allotment columns + license data
                                table_data.append([
                                    '', '', '', '', '', '', '', '', '', '',
                                    detail['dfia_no'],
                                    detail['dfia_date'],
                                    detail['dfia_port'],
                                    detail['item_sr_no'],
                                    f"{int(detail['dfia_qty']):,}",
                                    f"{detail['dfia_value']:,.2f}",
                                    f"{detail['dfia_cif']:,.2f}"
                                ])
                        sr_no += 1

                    # Calculate item totals
                    item_total_qty = sum(a['quantity'] for a in allotments)
                    item_total_value = sum(a['value'] for a in allotments)

                    # Add to company totals
                    company_total_qty += item_total_qty
                    company_total_value += item_total_value

                    table_data.append([
                        '', '', 'Total\nQuantity',
                        f"{int(item_total_qty):,}", 'Total USD $', f"{item_total_value:,.2f}",
                        '', '', '', '', '', '', '', '', '', '', ''
                    ])

                    # Create table with column widths for 17 columns
                    col_widths = [0.35 * inch, 0.6 * inch, 0.5 * inch, 0.6 * inch, 0.65 * inch, 0.6 * inch,
                                  0.8 * inch, 0.8 * inch, 0.6 * inch, 0.4 * inch,
                                  0.8 * inch, 0.6 * inch, 0.6 * inch, 0.5 * inch, 0.6 * inch, 0.65 * inch, 0.65 * inch]

                    # Enable table splitting across pages with repeatRows for header
                    table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=True)

                    # Build table styles with cell merging for multiple licenses
                    table_styles = [
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),  # Dark black text for data rows
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),  # Increased header font size
                        ('FONTSIZE', (0, 1), (-1, -1), 7),  # Increased data font size
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
                        ('TOPPADDING', (0, 1), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ]

                    # Note: We cannot use SPAN with splitByRow=True as it causes layout errors
                    # Vertical merging will be visual only (empty cells for subsequent licenses)
                    # row_idx = 1  # Start after header
                    # for allot in allotments:
                    #     if len(allot['details']) > 1:
                    #         # Merge allotment columns (0-9) vertically across license rows
                    #         for col_idx in range(10):
                    #             table_styles.append(('SPAN', (col_idx, row_idx), (col_idx, row_idx + len(allot['details']) - 1)))
                    #     row_idx += len(allot['details'])

                    table.setStyle(TableStyle(table_styles))

                    elements.append(table)
                    elements.append(Spacer(1, 12))

            # Add company total after all items
            company_total_table = Table([[
                'Company Total:', f"Quantity: {int(company_total_qty):,}", f"Value (USD): ${company_total_value:,.2f}"
            ]], colWidths=[2.5 * inch, 2.5 * inch, 2.5 * inch])
            company_total_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(company_total_table)
            elements.append(Spacer(1, 20))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)

        return response

    def _export_grouped_xlsx(self, queryset, export_type):
        """Export grouped allotments to Excel"""
        if not OPENPYXL_AVAILABLE:
            return HttpResponse("Excel export not available", status=500)

        # Group data
        grouped_data = self._group_allotments(queryset)

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Allotment Report"

        # Styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        row = 1

        # Title
        ws.merge_cells(f'A{row}:O{row}')
        cell = ws[f'A{row}']
        cell.value = "Allotment Report"
        cell.font = Font(bold=True, size=16)
        cell.alignment = Alignment(horizontal='center')
        row += 1

        # Total and date
        total_usd = sum(item['value'] for company in grouped_data.values()
                        for ports in company.values()
                        for items in ports.values()
                        for item in items)
        ws.merge_cells(f'A{row}:O{row}')
        cell = ws[f'A{row}']
        cell.value = f"Total USD $: {total_usd:,.2f}    {datetime.now().strftime('%d-%m-%Y')}"
        cell.alignment = Alignment(horizontal='center')
        row += 2

        # Process each company
        for company_name, items_dict in grouped_data.items():
            # Company header
            ws.merge_cells(f'A{row}:O{row}')
            cell = ws[f'A{row}']
            cell.value = company_name
            cell.font = Font(bold=True, size=14)
            row += 1

            # Track company totals
            company_total_qty = 0
            company_total_value = 0

            # Process each item within company
            for item_name_key, ports_dict in items_dict.items():
                # Get the actual item name from first allotment for display
                first_allot = next(iter(next(iter(ports_dict.values())))) if ports_dict else None
                display_item_name = first_allot[
                    'item_name'] if first_allot and 'item_name' in first_allot else item_name_key

                # Item subheader (optional)
                if len(items_dict) > 1:  # Only show if multiple items
                    ws.merge_cells(f'A{row}:O{row}')
                    cell = ws[f'A{row}']
                    cell.value = f"Item: {display_item_name}"
                    cell.font = Font(bold=True, size=12, italic=True)
                    row += 1

                # Process each port within item
                for port_code, allotments in ports_dict.items():
                    # Table headers - allotment info + license subheader
                    main_headers = ['Sr No', 'Allotment Date', 'Port', 'Quantity (KGS)',
                                    'Unit Price ($)', 'Value ($)', 'Item Name', 'Invoice', 'ETA', 'BOE']
                    license_headers = ['DFIA No.', 'DFIA Date', 'DFIA Port', 'Item Sr. NO.', 'DFIA Qty.', 'DFIA $.',
                                       'DFIA CIF']

                    # Write main headers
                    for col_idx, header in enumerate(main_headers, 1):
                        cell = ws.cell(row=row, column=col_idx, value=header)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal='center')
                        cell.border = border

                    # Merge cells for "DFIA Licenses" header
                    start_col = len(main_headers) + 1
                    end_col = start_col + len(license_headers) - 1
                    ws.merge_cells(start_row=row, start_column=start_col, end_row=row, end_column=end_col)
                    cell = ws.cell(row=row, column=start_col, value='DFIA Licenses')
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='center')
                    cell.border = border
                    row += 1

                    # Write license sub-headers
                    for col_idx, header in enumerate(license_headers, start_col):
                        cell = ws.cell(row=row, column=col_idx, value=header)
                        cell.font = Font(bold=True, size=9)
                        cell.fill = PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid')
                        cell.alignment = Alignment(horizontal='center')
                        cell.border = border
                    row += 1

                    sr_no = 1
                    for allot in allotments:
                        start_row_for_allot = row

                        # Write allotment data (will be merged vertically if multiple licenses)
                        allot_data = [
                            sr_no,
                            allot['date'],
                            allot['port'],
                            int(allot['quantity']),
                            allot['unit_price'],
                            allot['value'],
                            allot.get('item_name', display_item_name),
                            allot['invoice'],
                            allot['eta'],
                            'Yes' if allot.get('is_boe') else 'No'
                        ]

                        # Write license details (one row per license)
                        for detail_idx, detail in enumerate(allot['details']):
                            # Write allotment data only in first row
                            if detail_idx == 0:
                                for col_idx, value in enumerate(allot_data, 1):
                                    cell = ws.cell(row=row, column=col_idx, value=value)
                                    cell.border = border
                                    cell.alignment = Alignment(horizontal='center', vertical='center')
                                    if col_idx in [4, 5, 6]:  # Number columns
                                        cell.alignment = Alignment(horizontal='right', vertical='center')

                            # Write license details
                            license_data = [
                                detail['dfia_no'],
                                detail['dfia_date'],
                                detail['dfia_port'],
                                detail['item_sr_no'],
                                int(detail['dfia_qty']),
                                detail['dfia_value'],
                                detail['dfia_cif']
                            ]

                            for col_idx, value in enumerate(license_data, len(main_headers) + 1):
                                cell = ws.cell(row=row, column=col_idx, value=value)
                                cell.border = border
                                cell.alignment = Alignment(horizontal='center', vertical='center')
                                if col_idx in [len(main_headers) + 5, len(main_headers) + 6,
                                               len(main_headers) + 7]:  # Qty, Value, and CIF columns
                                    cell.alignment = Alignment(horizontal='right', vertical='center')
                            row += 1

                        # Merge allotment cells vertically if multiple licenses
                        if len(allot['details']) > 1:
                            for col_idx in range(1, len(main_headers) + 1):
                                ws.merge_cells(start_row=start_row_for_allot, start_column=col_idx,
                                               end_row=row - 1, end_column=col_idx)

                        sr_no += 1

                    # Grand total for item
                    item_total_qty = sum(a['quantity'] for a in allotments)
                    item_total_value = sum(a['value'] for a in allotments)

                    # Add to company totals
                    company_total_qty += item_total_qty
                    company_total_value += item_total_value

                    ws.cell(row=row, column=3, value="Total Quantity").font = Font(bold=True)
                    ws.cell(row=row, column=4, value=int(item_total_qty)).font = Font(bold=True)
                    ws.cell(row=row, column=5, value="Total USD $").font = Font(bold=True)
                    ws.cell(row=row, column=6, value=item_total_value).font = Font(bold=True)
                    row += 2

            # Add company total after all items
            ws.merge_cells(f'A{row}:C{row}')
            cell = ws.cell(row=row, column=1, value="Company Total:")
            cell.font = Font(bold=True, size=12)
            cell.fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')

            ws.cell(row=row, column=4, value=int(company_total_qty)).font = Font(bold=True, size=12)
            ws.cell(row=row, column=4).fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
            ws.cell(row=row, column=4).alignment = Alignment(horizontal='center', vertical='center')

            ws.merge_cells(f'E{row}:E{row}')
            ws.cell(row=row, column=5, value="Total USD $:").font = Font(bold=True, size=12)
            ws.cell(row=row, column=5).fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
            ws.cell(row=row, column=5).alignment = Alignment(horizontal='center', vertical='center')

            ws.cell(row=row, column=6, value=company_total_value).font = Font(bold=True, size=12)
            ws.cell(row=row, column=6).fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
            ws.cell(row=row, column=6).alignment = Alignment(horizontal='center', vertical='center')
            row += 3

        # Auto-size columns
        for column in ws.columns:
            max_length = 0
            column_letter = None
            for cell in column:
                try:
                    # Skip merged cells
                    if hasattr(cell, 'column_letter'):
                        if column_letter is None:
                            column_letter = cell.column_letter
                        if cell.value and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                except:
                    pass
            if column_letter:
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width

        # Save to response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="Pending_Allotments_{timestamp}.xlsx"'
        wb.save(response)

        return response

    def _group_allotments(self, queryset):
        """Group allotments by company → item name → port code (case-insensitive for item name)"""
        grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for allotment in queryset:
            company_name = allotment.company.name if allotment.company else "Unknown"
            port_code = allotment.port.code if allotment.port else "Unknown Port"
            # Use uppercase for grouping key to make it case-insensitive, but keep original for display
            item_name = allotment.item_name or "Unknown"
            item_name_key = item_name.upper()  # Case-insensitive grouping key

            allot_data = {
                'date': allotment.estimated_arrival_date.strftime(
                    '%d-%m-%Y') if allotment.estimated_arrival_date else '--',
                'port': port_code,
                'quantity': float(allotment.required_quantity or 0),
                'unit_price': float(allotment.unit_value_per_unit or 0),
                'value': float(allotment.required_value or 0),
                'invoice': allotment.invoice or '--',
                'eta': allotment.estimated_arrival_date.strftime(
                    '%d-%m-%Y') if allotment.estimated_arrival_date else '--',
                'is_boe': allotment.is_boe,
                'details': []
            }

            # Add allotment details
            for detail in allotment.allotment_details.all():
                license_obj = detail.item.license if detail.item else None
                allot_data['details'].append({
                    'dfia_no': license_obj.license_number if license_obj else '--',
                    'dfia_date': license_obj.license_date.strftime(
                        '%d-%m-%Y') if license_obj and license_obj.license_date else '--',
                    'dfia_port': license_obj.port.code if license_obj and license_obj.port else '--',
                    'item_sr_no': str(detail.item.serial_number) if detail.item else '--',
                    'dfia_qty': float(detail.qty or 0),
                    'dfia_value': float(detail.cif_fc or 0),
                    'dfia_cif': float(detail.cif_inr or 0)
                })

            # Store original item_name for display
            allot_data['item_name'] = item_name
            grouped_data[company_name][item_name_key][port_code].append(allot_data)

        return grouped_data

    # Add methods to the viewset class
    viewset_class.download_grouped_export = download_grouped_export
    viewset_class._export_grouped_pdf = _export_grouped_pdf
    viewset_class._export_grouped_xlsx = _export_grouped_xlsx
    viewset_class._group_allotments = _group_allotments

    return viewset_class
