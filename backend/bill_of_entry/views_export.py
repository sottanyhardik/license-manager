# bill_of_entry/views_export.py
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
    Decorator to add grouped export functionality to BillOfEntryViewSet
    """

    @action(detail=False, methods=['get'], url_path='export')
    def export_bill_of_entries(self, request):
        """
        Export bill of entries grouped by company.
        URL: /api/bill-of-entries/export/?_export=pdf

        Query params:
            - _export: 'pdf' or 'xlsx' (default: pdf)
            - company: filter by company ID
            - bill_of_entry_date_after: filter by date
            - bill_of_entry_date_before: filter by date
        """
        export_format = request.query_params.get('_export', 'pdf').lower()

        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Filter only BOEs with item details and order by company, product, port, date
        queryset = queryset.filter(
            item_details__isnull=False
        ).distinct().order_by(
            'company__name', 'product_name', 'port__code', 'bill_of_entry_date'
        ).prefetch_related(
            'item_details__sr_number__license',
            'item_details__sr_number__hs_code',
            'company',
            'port'
        )

        if export_format == 'pdf':
            return self._export_grouped_pdf(queryset)
        elif export_format == 'xlsx':
            return self._export_grouped_xlsx(queryset)
        else:
            return HttpResponse("Invalid export format. Use 'pdf' or 'xlsx'.", status=400)

    def _export_grouped_pdf(self, queryset):
        """Export grouped bill of entries to PDF"""
        if not REPORTLAB_AVAILABLE:
            return HttpResponse("PDF export not available", status=500)

        # Group data
        grouped_data = self._group_boe(queryset)

        # Create PDF
        response = HttpResponse(content_type='application/pdf')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'Bill_of_Entries_{timestamp}.pdf'
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
        total_inr = sum(boe['total_inr']
                        for company in grouped_data.values()
                        for product in company.values()
                        for port in product.values()
                        for boe in port)
        total_fc = sum(boe['total_fc']
                       for company in grouped_data.values()
                       for product in company.values()
                       for port in product.values()
                       for boe in port)

        elements.append(Paragraph("Bill of Entry Report", title_style))
        elements.append(Paragraph(
            f"Total INR: ₹{total_inr:,.2f} &nbsp;&nbsp;&nbsp; Total FC: ${total_fc:,.2f} &nbsp;&nbsp;&nbsp; {datetime.now().strftime('%d-%m-%Y')}",
            ParagraphStyle('subtitle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)))
        elements.append(Spacer(1, 12))

        # Process each company
        for company_name, products_dict in grouped_data.items():
            # Company header
            elements.append(Paragraph(f"<b>{company_name}</b>",
                                      ParagraphStyle('company', parent=styles['Heading2'], fontSize=12)))
            elements.append(Spacer(1, 6))

            # Track company totals
            company_total_qty = 0
            company_total_inr = 0
            company_total_fc = 0

            # Process each product (Item) within company
            for product_name, ports_dict in products_dict.items():
                # Product/Item subheader
                elements.append(Paragraph(f"Item: <b>{product_name}</b>",
                                          ParagraphStyle('product', parent=styles['Normal'], fontSize=10,
                                                         textColor=colors.blue)))
                elements.append(Spacer(1, 3))

                # Table header - 15 columns (removed BOE column)
                table_data = [[
                    'Sr No', 'BOE Date', 'Port', 'Quantity\n(KGS)', 'Unit Price ($)', 'Value ($)',
                    'Item Name', 'Invoice', 'License No.', 'BOE Date', 'BOE Port',
                    'Item Sr.', 'BOE Qty.', 'BOE $.', 'BOE CIF'
                ]]

                sr_no = 1
                product_total_qty = 0
                product_total_value = 0

                # Process each port within product
                for port_code, boe_list in ports_dict.items():
                    for boe in boe_list:
                        # Main BOE row (first license detail or summary)
                        if boe['license_details']:
                            first_detail = boe['license_details'][0]

                            table_data.append([
                                sr_no,
                                boe['boe_date'],
                                port_code,
                                f"{int(boe['total_quantity']):,}",
                                f"{(boe['total_fc'] / boe['total_quantity'] if boe['total_quantity'] > 0 else 0):.2f}",
                                f"{boe['total_fc']:,.2f}",
                                product_name,
                                boe['invoice_no'],
                                first_detail['license_no'],
                                boe['boe_date'],
                                port_code,
                                first_detail['item_sr_no'],
                                f"{int(first_detail['qty']):,}",
                                f"{first_detail['cif_fc']:,.2f}",
                                f"{first_detail['cif_inr']:,.2f}"
                            ])

                            # Additional license detail rows (if multiple licenses)
                            for detail in boe['license_details'][1:]:
                                table_data.append([
                                    '', '', '', '', '', '',  # Empty columns for main BOE info
                                    '', '',  # Item Name, Invoice (removed BOE column)
                                    detail['license_no'],
                                    boe['boe_date'],
                                    port_code,
                                    detail['item_sr_no'],
                                    f"{int(detail['qty']):,}",
                                    f"{detail['cif_fc']:,.2f}",
                                    f"{detail['cif_inr']:,.2f}"
                                ])

                        sr_no += 1
                        product_total_qty += boe['total_quantity']
                        product_total_value += boe['total_fc']
                        company_total_qty += boe['total_quantity']
                        company_total_inr += boe['total_inr']
                        company_total_fc += boe['total_fc']

                # Add product totals row
                table_data.append([
                    '', '', 'Total\nQuantity', f"{int(product_total_qty):,}",
                    'Total USD $', f"{product_total_value:,.2f}",
                    '', '', '', '', '', '', '', '', ''
                ])

                # Create table with column widths (15 columns - removed BOE column)
                col_widths = [0.3 * inch, 0.6 * inch, 0.5 * inch, 0.6 * inch, 0.6 * inch, 0.6 * inch,
                              0.8 * inch, 0.7 * inch, 0.7 * inch, 0.6 * inch, 0.5 * inch,
                              0.4 * inch, 0.6 * inch, 0.6 * inch, 0.6 * inch]

                # Enable table splitting across pages with repeatRows for header
                table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=True)

                # Build table styles
                table_styles = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('FONTSIZE', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('TOPPADDING', (0, 1), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ]

                table.setStyle(TableStyle(table_styles))
                elements.append(table)
                elements.append(Spacer(1, 12))

            # Add company total after all products
            company_total_table = Table([[
                'Company Total:', f"Quantity: {int(company_total_qty):,}",
                f"FC (USD): ${company_total_fc:,.2f}", f"INR: ₹{company_total_inr:,.2f}"
            ]], colWidths=[2 * inch, 2 * inch, 2 * inch, 2 * inch])
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

    def _export_grouped_xlsx(self, queryset):
        """Export grouped bill of entries to Excel"""
        if not OPENPYXL_AVAILABLE:
            return HttpResponse("Excel export not available", status=500)

        # Group data
        grouped_data = self._group_boe(queryset)

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Bill of Entries"

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
        cell.value = "Bill of Entry Report"
        cell.font = Font(bold=True, size=16)
        cell.alignment = Alignment(horizontal='center')
        row += 1

        # Total and date
        total_inr = sum(boe['total_inr']
                        for company in grouped_data.values()
                        for product in company.values()
                        for port in product.values()
                        for boe in port)
        total_fc = sum(boe['total_fc']
                       for company in grouped_data.values()
                       for product in company.values()
                       for port in product.values()
                       for boe in port)
        ws.merge_cells(f'A{row}:O{row}')
        cell = ws[f'A{row}']
        cell.value = f"Total INR: ₹{total_inr:,.2f}    Total FC: ${total_fc:,.2f}    {datetime.now().strftime('%d-%m-%Y')}"
        cell.alignment = Alignment(horizontal='center')
        row += 2

        # Process each company
        for company_name, products_dict in grouped_data.items():
            # Company header
            ws.merge_cells(f'A{row}:O{row}')
            cell = ws[f'A{row}']
            cell.value = company_name
            cell.font = Font(bold=True, size=14)
            row += 1

            # Track company totals
            company_total_qty = 0
            company_total_value = 0

            # Process each product (Item) within company
            for product_name, ports_dict in products_dict.items():
                # Product subheader
                ws.merge_cells(f'A{row}:O{row}')
                cell = ws[f'A{row}']
                cell.value = f"Item: {product_name}"
                cell.font = Font(bold=True, size=11, color="0000FF")
                row += 1

                # Table headers - 16 columns matching allotment structure
                headers = ['Sr No', 'BOE Date', 'Port', 'Quantity (KGS)', 'Unit Price ($)', 'Value ($)',
                           'Item Name', 'Invoice', 'License No.', 'BOE Date', 'BOE Port',
                           'Item Sr.', 'BOE Qty.', 'BOE $.', 'BOE CIF']

                # Write headers
                for col_idx, header in enumerate(headers, 1):
                    cell = ws.cell(row=row, column=col_idx, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='center', wrap_text=True)
                    cell.border = border
                row += 1

                sr_no = 1
                product_total_qty = 0
                product_total_value = 0

                # Process each port within product
                for port_code, boe_list in ports_dict.items():
                    for boe in boe_list:
                        if boe['license_details']:
                            first_detail = boe['license_details'][0]
                            unit_price = boe['total_fc'] / boe['total_quantity'] if boe['total_quantity'] > 0 else 0

                            # Main BOE row
                            data = [
                                sr_no,
                                boe['boe_date'],
                                port_code,
                                int(boe['total_quantity']),
                                unit_price,
                                boe['total_fc'],
                                product_name,
                                boe['invoice_no'],
                                first_detail['license_no'],
                                boe['boe_date'],
                                port_code,
                                first_detail['item_sr_no'],
                                int(first_detail['qty']),
                                first_detail['cif_fc'],
                                first_detail['cif_inr']
                            ]

                            for col_idx, value in enumerate(data, 1):
                                cell = ws.cell(row=row, column=col_idx, value=value)
                                cell.border = border
                                cell.alignment = Alignment(horizontal='center', vertical='center')
                                if col_idx in [4, 5, 6, 13, 14, 15]:  # Number columns
                                    cell.alignment = Alignment(horizontal='right', vertical='center')
                            row += 1

                            # Additional license detail rows
                            for detail in boe['license_details'][1:]:
                                data = [
                                    '', '', '', '', '', '',  # Empty main BOE columns
                                    '', '',  # Item Name, Invoice, BOE
                                    detail['license_no'],
                                    boe['boe_date'],
                                    port_code,
                                    detail['item_sr_no'],
                                    int(detail['qty']),
                                    detail['cif_fc'],
                                    detail['cif_inr']
                                ]

                                for col_idx, value in enumerate(data, 1):
                                    cell = ws.cell(row=row, column=col_idx, value=value)
                                    cell.border = border
                                    cell.alignment = Alignment(horizontal='center', vertical='center')
                                    if col_idx in [13, 14, 15]:
                                        cell.alignment = Alignment(horizontal='right', vertical='center')
                                row += 1

                        sr_no += 1
                        product_total_qty += boe['total_quantity']
                        product_total_value += boe['total_fc']
                        company_total_qty += boe['total_quantity']
                        company_total_value += boe['total_fc']

                # Product totals
                ws.cell(row=row, column=3, value="Total Quantity").font = Font(bold=True)
                ws.cell(row=row, column=4, value=int(product_total_qty)).font = Font(bold=True)
                ws.cell(row=row, column=5, value="Total USD $").font = Font(bold=True)
                ws.cell(row=row, column=6, value=product_total_value).font = Font(bold=True)
                row += 2

            # Add company total after all products
            ws.merge_cells(f'A{row}:B{row}')
            cell = ws.cell(row=row, column=1, value="Company Total:")
            cell.font = Font(bold=True, size=12)
            cell.fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')

            ws.cell(row=row, column=4, value=int(company_total_qty)).font = Font(bold=True, size=12)
            ws.cell(row=row, column=4).fill = PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')
            ws.cell(row=row, column=4).alignment = Alignment(horizontal='center', vertical='center')

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
        response['Content-Disposition'] = f'attachment; filename="Bill_of_Entries_{timestamp}.xlsx"'
        wb.save(response)

        return response

    def _group_boe(self, queryset):
        """Group bill of entries by company → product_name → port"""
        # Structure: {company: {product_name: {port: [boe_list]}}}
        grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for boe in queryset:
            company_name = boe.company.name if boe.company else "Unknown"
            port_code = boe.port.code if boe.port else "Unknown Port"
            product_name = boe.product_name or "Unknown Product"

            # Collect license details for this BOE
            license_details = []
            for detail in boe.item_details.all():
                license_obj = detail.sr_number.license if detail.sr_number else None
                license_details.append({
                    'license_no': license_obj.license_number if license_obj else '--',
                    'item_sr_no': str(detail.sr_number.serial_number) if detail.sr_number else '--',
                    'qty': float(detail.qty or 0),
                    'cif_fc': float(detail.cif_fc or 0),
                    'cif_inr': float(detail.cif_inr or 0)
                })

            boe_data = {
                'boe_number': boe.bill_of_entry_number or '--',
                'boe_date': boe.bill_of_entry_date.strftime('%d-%m-%Y') if boe.bill_of_entry_date else '--',
                'port': port_code,
                'product_name': product_name,
                'invoice_no': boe.invoice_no or '--',
                'total_quantity': float(boe.get_total_quantity or 0),
                'total_fc': float(boe.get_total_fc or 0),
                'total_inr': float(boe.get_total_inr or 0),
                'license_details': license_details,  # List of license entries
            }

            grouped_data[company_name][product_name][port_code].append(boe_data)

        return grouped_data

    # Add methods to the viewset class
    viewset_class.export_bill_of_entries = export_bill_of_entries
    viewset_class._export_grouped_pdf = _export_grouped_pdf
    viewset_class._export_grouped_xlsx = _export_grouped_xlsx
    viewset_class._group_boe = _group_boe

    return viewset_class
