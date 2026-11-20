"""Grouped BOE Excel exporter (moved verbatim from api/views_export.py)."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.http import HttpResponse

from apps.core.exporters.excel.cell_formats import (
    QUANTITY_FORMAT,
    finalize_workbook,
    sum_formula,
    sumif_label_formula,
    write_date,
    write_number,
    write_text,
)

from .common import OPENPYXL_AVAILABLE, _decimal_or_default, _text_response
from .grouping import group_boe

if OPENPYXL_AVAILABLE:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill


def _sum_of_rows(column, rows):
    """Grand total as a live formula summing only the given sub-total rows.

    Uses SUMIF on the sub-total label ("Total", column C) over this company's
    span (first..last sub-total row), so the formula length is constant (no Excel
    8,192-char / 255-argument limit) and other companies' rows are excluded.
    """
    if not rows:
        return 0
    return sumif_label_formula(3, "Total", column, min(rows), max(rows))


def export_grouped_xlsx(queryset):
    """Export grouped bill of entries to Excel"""
    if not OPENPYXL_AVAILABLE:
        return _text_response("Excel export not available", 503)

    # Group data
    grouped_data = group_boe(queryset)

    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bill of Entries"

    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1e3a8a", end_color="1e3a8a", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    row = 1

    # Title
    ws.merge_cells(f'A{row}:R{row}')
    cell = ws[f'A{row}']
    cell.value = "Bill of Entry Report"
    cell.font = Font(bold=True, size=16, color="1e3a8a")
    cell.alignment = Alignment(horizontal='center')
    row += 1

    # Total and date
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
    ws.merge_cells(f'A{row}:R{row}')
    cell = ws[f'A{row}']
    cell.value = f"Total INR: ₹{total_inr:,.2f}    Total FC: ${total_fc:,.2f}    {datetime.now().strftime('%d-%m-%Y')}"
    cell.alignment = Alignment(horizontal='center')
    row += 2

    # Process each company (sorted alphabetically, None values last)
    for company_name, license_dict in sorted(grouped_data.items(), key=lambda x: (x[0] is None, x[0] or '')):
        # Company header
        ws.merge_cells(f'A{row}:R{row}')
        cell = ws[f'A{row}']
        cell.value = company_name
        cell.font = Font(bold=True, size=14, color="FFFFFF")
        cell.fill = PatternFill(start_color="1e3a8a", end_color="1e3a8a", fill_type="solid")
        cell.alignment = Alignment(horizontal='center', vertical='center')
        row += 1

        # Rows holding each product total; the company grand total sums only these
        # (never the data rows again), so nothing is double counted.
        product_total_rows = []

        # Merge all products into a single table (group by product name only, ignore license serial)
        merged_products = defaultdict(lambda: defaultdict(list))
        for license_serial, products_dict in license_dict.items():
            for product_name, ports_dict in products_dict.items():
                for port_code, boe_list in ports_dict.items():
                    merged_products[product_name][port_code].extend(boe_list)

        # Process each product (Item) within company
        for product_name, ports_dict in merged_products.items():
            # Product subheader
            ws.merge_cells(f'A{row}:S{row}')
            cell = ws[f'A{row}']
            cell.value = f"Item: {product_name}"
            cell.font = Font(bold=True, size=14, color="3b82f6")
            row += 1

            # Table headers (18 columns - added Exporter and Exchange Rate)
            headers = ['Sr No', 'BOE Number', 'BOE Date', 'Port', 'Quantity (KGS)', 'Unit Price ($)', 'Value ($)',
                       'Exchange Rate', 'Total CIF INR', 'Item Name', 'Invoice', 'Exporter', 'License No.', 'License Date',
                       'License Port', 'Item Sr.', 'BOE Qty.', 'BOE $.', 'BOE CIF']

            # Write headers
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=row, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')
                cell.border = border
            row += 1

            sr_no = 1
            first_data_row = row

            # Process each port within product
            for port_code, boe_list in ports_dict.items():
                for boe in boe_list:
                    if boe['license_details']:
                        first_detail = boe['license_details'][0]
                        unit_price = boe['total_fc'] / boe['total_quantity'] if boe['total_quantity'] > 0 else 0

                        # Main BOE row (18 columns - added Exporter)
                        data = [
                            sr_no,
                            boe['boe_number'],
                            boe['boe_date'],
                            port_code,
                            boe['total_quantity'],  # raw Decimal so the SUM totals are exact
                            round(unit_price, 2),
                            round(boe['total_fc'], 2),
                            round(boe['exchange_rate'], 2),  # Exchange Rate
                            round(boe['total_inr'], 2),  # Total CIF INR
                            product_name,
                            boe['invoice_no'],
                            first_detail['exporter_name'],  # Exporter
                            first_detail['license_no'],     # License No.
                            first_detail['license_date'],
                            first_detail['license_port'],
                            first_detail['item_sr_no'],
                            int(first_detail['qty']),
                            round(first_detail['cif_fc'], 2),
                            round(first_detail['cif_inr'], 2)
                        ]

                        for col_idx, value in enumerate(data, 1):
                            cell = ws.cell(row=row, column=col_idx, value=value)
                            cell.border = border
                            cell.font = Font(size=12)
                            if col_idx in (3, 14):  # BOE Date / License Date: real dates
                                write_date(cell, value)
                            elif col_idx in (2, 11, 13):  # BOE no. / Invoice / License no.: identifiers
                                write_text(cell, value)
                            if col_idx in [5, 6, 7, 8, 9, 17, 18, 19]:  # Number columns
                                cell.alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
                                if col_idx in [6, 7, 18]:  # USD columns
                                    cell.number_format = '#,##0.00'
                                elif col_idx == 5:  # Total quantity: real number, 3dp
                                    write_number(cell, value, QUANTITY_FORMAT)
                                elif col_idx in [9, 19]:  # INR columns
                                    cell.number_format = '₹#,##0.00'
                                elif col_idx == 8:  # Exchange Rate column
                                    cell.number_format = '#,##0.00'
                            else:
                                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                        # Allow 2 lines by default; grow to 3 lines if the
                        # longest cell content suggests more wrapping is needed.
                        longest = max(
                            (len(str(v)) for v in data if v not in (None, '')),
                            default=0,
                        )
                        target_lines = 3 if longest > 30 else 2
                        ws.row_dimensions[row].height = max(28, target_lines * 16)

                        row += 1

                        # Additional license detail rows
                        for detail in boe['license_details'][1:]:
                            data = [
                                '', '', '', '', '', '', '', '', '',  # Empty main BOE columns
                                '', '',  # Item Name, Invoice
                                detail['exporter_name'],  # Exporter
                                detail['license_no'],     # License No.
                                detail['license_date'],
                                detail['license_port'],
                                detail['item_sr_no'],
                                int(detail['qty']),
                                round(detail['cif_fc'], 2),
                                round(detail['cif_inr'], 2)
                            ]

                            for col_idx, value in enumerate(data, 1):
                                cell = ws.cell(row=row, column=col_idx, value=value)
                                cell.border = border
                                cell.font = Font(size=12)
                                if col_idx == 14:  # License Date: real date
                                    write_date(cell, value)
                                elif col_idx == 13:  # License no.: identifier
                                    write_text(cell, value)
                                if col_idx in [17, 18, 19]:
                                    cell.alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
                                    if col_idx in [18, 19]:
                                        cell.number_format = '#,##0.00'
                                else:
                                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                            longest_detail = max(
                                (len(str(v)) for v in data if v not in (None, '')),
                                default=0,
                            )
                            target_lines_d = 3 if longest_detail > 30 else 2
                            ws.row_dimensions[row].height = max(28, target_lines_d * 16)

                            row += 1

                        if len(boe['license_details']) > 1:
                            total_dfia_qty = sum(
                                (_decimal_or_default(detail['qty']) for detail in boe['license_details']),
                                Decimal('0'),
                            )
                            total_dfia_value = sum(
                                (_decimal_or_default(detail['cif_fc']) for detail in boe['license_details']),
                                Decimal('0'),
                            )
                            # A merged label band keeps the subtotal
                            # readable and leaves Qty / DFIA $ aligned
                            # precisely beneath their table headers.
                            label_start_col = 12
                            label_end_col = 16
                            qty_col = 17
                            value_col = 18
                            total_fill = PatternFill(start_color='D9EAF7', end_color='D9EAF7', fill_type='solid')
                            value_fill = PatternFill(start_color='B8D8F0', end_color='B8D8F0', fill_type='solid')
                            ws.merge_cells(
                                start_row=row,
                                start_column=label_start_col,
                                end_row=row,
                                end_column=label_end_col,
                            )

                            label_cell = ws.cell(row=row, column=label_start_col, value='Total DFIA allocation')
                            label_cell.border = border
                            label_cell.fill = total_fill
                            label_cell.font = Font(bold=True, size=12, color='17365D')
                            label_cell.alignment = Alignment(horizontal='left', vertical='center')

                            for col_idx, value, number_format in [
                                (qty_col, total_dfia_qty, '#,##0'),
                                (value_col, total_dfia_value, '#,##0.00'),
                            ]:
                                cell = ws.cell(row=row, column=col_idx, value=value)
                                cell.border = border
                                cell.fill = value_fill
                                cell.font = Font(bold=True, size=12, color='17365D')
                                cell.alignment = Alignment(horizontal='right', vertical='center')
                                cell.number_format = number_format
                            # BOE CIF is intentionally left empty on the
                            # DFIA subtotal row, but retains the same band.
                            trailing_cell = ws.cell(row=row, column=19, value='')
                            trailing_cell.border = border
                            trailing_cell.fill = total_fill
                            ws.row_dimensions[row].height = 22
                            row += 1

                    sr_no += 1

            # Product totals: live SUM over this product's data rows only.
            last_data_row = row - 1
            ws.cell(row=row, column=3, value="Total").font = Font(bold=True)
            ws.cell(row=row, column=5, value=sum_formula(5, first_data_row, last_data_row)).font = Font(bold=True)
            ws.cell(row=row, column=5).number_format = QUANTITY_FORMAT
            ws.cell(row=row, column=7, value=sum_formula(7, first_data_row, last_data_row)).font = Font(bold=True)
            ws.cell(row=row, column=7).number_format = '#,##0.00'
            ws.cell(row=row, column=9, value=sum_formula(9, first_data_row, last_data_row)).font = Font(bold=True)
            ws.cell(row=row, column=9).number_format = '₹#,##0.00'
            product_total_rows.append(row)
            row += 2

        # Add grand total after all products
        ws.merge_cells(f'A{row}:B{row}')
        cell = ws.cell(row=row, column=1, value="Grand Total:")
        cell.font = Font(bold=True, size=14, color="1e3a8a")
        cell.fill = PatternFill(start_color='f1f5f9', end_color='f1f5f9', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')

        ws.cell(row=row, column=5, value=_sum_of_rows(5, product_total_rows)).font = Font(bold=True, size=14)
        ws.cell(row=row, column=5).fill = PatternFill(start_color='f1f5f9', end_color='f1f5f9', fill_type='solid')
        ws.cell(row=row, column=5).alignment = Alignment(horizontal='right', vertical='center')
        ws.cell(row=row, column=5).number_format = QUANTITY_FORMAT

        ws.cell(row=row, column=7, value=_sum_of_rows(7, product_total_rows)).font = Font(bold=True, size=14)
        ws.cell(row=row, column=7).fill = PatternFill(start_color='f1f5f9', end_color='f1f5f9', fill_type='solid')
        ws.cell(row=row, column=7).alignment = Alignment(horizontal='right', vertical='center')
        ws.cell(row=row, column=7).number_format = '#,##0.00'

        ws.merge_cells(f'H{row}:I{row}')
        cell = ws.cell(row=row, column=8, value=_sum_of_rows(9, product_total_rows))
        cell.number_format = '"CIF INR: ₹"#,##0.00'
        cell.font = Font(bold=True, size=14, color="1e3a8a")
        cell.fill = PatternFill(start_color='f1f5f9', end_color='f1f5f9', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        row += 3

    # Size columns with a friendly cap so wide cells wrap to 2–3 lines
    # instead of forcing the sheet to be enormously wide.
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
            except (TypeError, AttributeError):
                pass
        if column_letter:
            # Floor 10 (so short headers like "Sr No" stay readable),
            # cap 22 (so long text wraps onto 2–3 lines instead of stretching).
            adjusted_width = max(10, min(max_length + 2, 22))
            ws.column_dimensions[column_letter].width = adjusted_width

    # Save to response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    today = datetime.now().strftime('%d-%m-%Y')
    response['Content-Disposition'] = f'attachment; filename="BOE Report - {today}.xlsx"'
    finalize_workbook(wb)
    wb.save(response)

    return response
