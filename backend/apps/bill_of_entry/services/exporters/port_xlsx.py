"""Flat port-wise BOE Excel exporter (moved verbatim from api/views_export.py)."""
from datetime import datetime

from django.http import HttpResponse

from apps.bill_of_entry.api.serializers import BillOfEntrySerializer

from .common import OPENPYXL_AVAILABLE, _decimal_or_default, _text_response

if OPENPYXL_AVAILABLE:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill


def export_port_xlsx(queryset):
    """Export simplified flat BOE list: single sheet, one header, no grouping."""
    if not OPENPYXL_AVAILABLE:
        return _text_response("Excel export not available", 503)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Port BOE List"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1e3a8a", end_color="1e3a8a", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Title row
    ws.merge_cells('A1:G1')
    title_cell = ws['A1']
    title_cell.value = f"Port BOE Report — {datetime.now().strftime('%d-%m-%Y')}"
    title_cell.font = Font(bold=True, size=14, color="1e3a8a")
    title_cell.alignment = Alignment(horizontal='center')

    # Single header row
    headers = ['BOE Number', 'BOE Date', 'Port', 'Company', 'Quantity (KGS)', 'Total CIF INR', 'Item Name']
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border

    row = 3
    for boe in queryset:
        # Totals from the prefetched rows (identical Decimals, no per-BOE SUM queries).
        BillOfEntrySerializer._seed_totals_from_prefetch(boe)
        boe_number = boe.bill_of_entry_number or '--'
        boe_date = boe.bill_of_entry_date.strftime('%d-%m-%Y') if boe.bill_of_entry_date else '--'
        port_code = boe.port.code if boe.port else '--'
        company_name = boe.company.name if boe.company else '--'
        total_quantity = _decimal_or_default(boe.get_total_quantity)
        total_inr = _decimal_or_default(boe.get_total_inr)
        product_name = (boe.product_name or '').strip().upper() or '--'

        data = [boe_number, boe_date, port_code, company_name, int(total_quantity), round(total_inr, 2), product_name]
        for col_idx, value in enumerate(data, 1):
            cell = ws.cell(row=row, column=col_idx, value=value)
            cell.border = border
            if col_idx == 5:
                cell.alignment = Alignment(horizontal='right', vertical='center')
                cell.number_format = '#,##0'
            elif col_idx == 6:
                cell.alignment = Alignment(horizontal='right', vertical='center')
                cell.number_format = '₹#,##0.00'
            else:
                cell.alignment = Alignment(horizontal='center', vertical='center')
        row += 1

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
            except (TypeError, AttributeError):
                pass
        if column_letter:
            ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    today = datetime.now().strftime('%d-%m-%Y')
    response['Content-Disposition'] = f'attachment; filename="Port BOE Report - {today}.xlsx"'
    wb.save(response)
    return response
