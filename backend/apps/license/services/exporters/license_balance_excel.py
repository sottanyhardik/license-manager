"""Excel renderers for license balance reports.

Extracted verbatim from ``LicenseDetailsViewSet.balance_excel``,
``balance_excel_unused`` and ``bulk_balance_excel`` as part of the
clean-architecture refactor. The viewset now only resolves inputs and delegates
here; behaviour is unchanged.
"""
def build_balance_excel_unused(license_obj):
    """Original full balance Excel — kept for reference, no longer exposed."""
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from io import BytesIO
    from datetime import date


    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "License Balance"

    # Header styling
    header_fill = PatternFill(start_color="2c3e50", end_color="2c3e50", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    data_fill = PatternFill(start_color="ecf0f1", end_color="ecf0f1", fill_type="solid")
    section_fill = PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
    section_font = Font(bold=True, color="FFFFFF", size=12)

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Title
    current_row = 1
    ws.merge_cells(f'A{current_row}:J{current_row}')
    title_cell = ws[f'A{current_row}']
    title_cell.value = "License Balance Report"
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    current_row += 2

    # License Header Information
    # Row 1 Headers
    headers_row1 = ['License Number', 'License Date', 'License Expiry Date', 'Exporter Name', 'Port Name']
    for col_num, header in enumerate(headers_row1, 1):
        cell = ws.cell(row=current_row, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='left', vertical='center')
    current_row += 1

    # Row 1 Values
    values_row1 = [
        license_obj.license_number or '-',
        license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-',
        license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-',
        license_obj.exporter.name if license_obj.exporter else '-',
        license_obj.port.name if license_obj.port else '-'
    ]
    for col_num, value in enumerate(values_row1, 1):
        cell = ws.cell(row=current_row, column=col_num, value=value)
        cell.fill = data_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='left', vertical='center')
    current_row += 2

    # Row 2 Headers
    headers_row2 = ['Purchase Status', 'Balance CIF', 'Get Norm Class', 'Latest Transfer']
    for col_num, header in enumerate(headers_row2, 1):
        cell = ws.cell(row=current_row, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='left', vertical='center')
    current_row += 1

    # Row 2 Values
    values_row2 = [
        str(license_obj.purchase_status) if license_obj.purchase_status else '-',
        f"{float(license_obj.balance_cif or 0):.2f}",
        license_obj.get_norm_class or '-',
        str(license_obj.latest_transfer) if license_obj.latest_transfer else '-'
    ]
    for col_num, value in enumerate(values_row2, 1):
        cell = ws.cell(row=current_row, column=col_num, value=value)
        cell.fill = data_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='left', vertical='center')
    current_row += 2

    # Export Items Section
    if license_obj.export_license.exists():
        # Section header
        ws.merge_cells(f'A{current_row}:C{current_row}')
        section_cell = ws[f'A{current_row}']
        section_cell.value = "Export Items"
        section_cell.fill = section_fill
        section_cell.font = section_font
        section_cell.alignment = Alignment(horizontal='center', vertical='center')
        current_row += 1

        # Export items headers
        export_headers = ['Item', 'Total CIF', 'Balance CIF']
        for col_num, header in enumerate(export_headers, 1):
            cell = ws.cell(row=current_row, column=col_num, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
        current_row += 1

        # Export items data
        for item in license_obj.export_license.all():
            item_desc = item.description or (str(item.norm_class) if item.norm_class else None) or 'None'
            values = [
                item_desc,
                f"{float(item.cif_fc or item.fob_fc or 0):.2f}",
                f"{float(license_obj.balance_cif or 0):.2f}"
            ]
            for col_num, value in enumerate(values, 1):
                cell = ws.cell(row=current_row, column=col_num, value=value)
                cell.border = thin_border
            current_row += 1

        current_row += 1

    # Import Items Section
    if license_obj.import_license.exists():
        from apps.bill_of_entry.models import RowDetails
        from apps.allotment.models import AllotmentItems

        # Section header
        ws.merge_cells(f'A{current_row}:J{current_row}')
        section_cell = ws[f'A{current_row}']
        section_cell.value = "Import Items"
        section_cell.fill = section_fill
        section_cell.font = section_font
        section_cell.alignment = Alignment(horizontal='center', vertical='center')
        current_row += 1

        for item in license_obj.import_license.all():
            # Item headers
            item_headers = ['Sr', 'HS Code', 'Description', 'Item', 'Total Qty',
                           'Allotted', 'Debited', 'Available', 'CIF FC', 'Bal CIF']
            for col_num, header in enumerate(item_headers, 1):
                cell = ws.cell(row=current_row, column=col_num, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.border = thin_border
            current_row += 1

            # Item data
            item_names = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else '-'
            hs_code_display = str(item.hs_code.hs_code if item.hs_code else '-')

            item_values = [
                str(item.serial_number or '-'),
                hs_code_display,
                str(item.description or '-'),
                item_names,
                f"{float(item.quantity or 0):.2f}",
                f"{float(item.allotted_quantity or 0):.2f}",
                f"{float(item.debited_quantity or 0):.2f}",
                f"{float(item.available_quantity or 0):.2f}",
                f"{float(item.cif_fc or 0):.2f}",
                f"{float(item.balance_cif_fc or 0):.2f}"
            ]
            from apps.license.utils.condition_excel import annotate_cell as _annotate_cond_unused
            for col_num, value in enumerate(item_values, 1):
                cell = ws.cell(row=current_row, column=col_num, value=value)
                cell.fill = data_fill
                cell.border = thin_border
                # Tint the Serial Number cell when this item carries a
                # licence condition (AU / 2% / 3% / 5% / 10%).
                if col_num == 1 and item.condition_type:
                    _annotate_cond_unused(cell, item.condition_type)
            current_row += 1

            # BOE Details
            boes = RowDetails.objects.filter(
                sr_number_id=item.id,
                transaction_type='D'
            ).select_related('bill_of_entry', 'bill_of_entry__port', 'bill_of_entry__company')
            if boes.exists():
                current_row += 1
                ws.merge_cells(f'A{current_row}:G{current_row}')
                boe_header_cell = ws[f'A{current_row}']
                boe_header_cell.value = "BOEs"
                boe_header_cell.fill = PatternFill(start_color="3498db", end_color="3498db", fill_type="solid")
                boe_header_cell.font = Font(bold=True, color="FFFFFF")
                current_row += 1

                boe_headers = ['BOE Number', 'Date', 'Port', 'Company', 'Qty', 'CIF $', 'CIF INR']
                for col_num, header in enumerate(boe_headers, 1):
                    cell = ws.cell(row=current_row, column=col_num, value=header)
                    cell.fill = PatternFill(start_color="3498db", end_color="3498db", fill_type="solid")
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.border = thin_border
                current_row += 1

                for boe in boes:
                    boe_values = [
                        boe.bill_of_entry.bill_of_entry_number if boe.bill_of_entry else '-',
                        boe.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if boe.bill_of_entry and boe.bill_of_entry.bill_of_entry_date else '-',
                        boe.bill_of_entry.port.name if boe.bill_of_entry and boe.bill_of_entry.port else '-',
                        boe.bill_of_entry.company.name if boe.bill_of_entry and boe.bill_of_entry.company else '-',
                        f"{float(boe.qty or 0):.2f}",
                        f"{float(boe.cif_fc or 0):.2f}",
                        f"{float(boe.cif_inr or 0):.2f}"
                    ]
                    for col_num, value in enumerate(boe_values, 1):
                        cell = ws.cell(row=current_row, column=col_num, value=value)
                        cell.border = thin_border
                    current_row += 1

            # Allotment Details
            # Only show allotments where bill_of_entry is NULL (not yet converted to BOE)
            allotments = AllotmentItems.objects.filter(
                item=item,
                allotment__bill_of_entry__isnull=True
            ).select_related('allotment', 'allotment__company')
            if allotments.exists():
                current_row += 1
                ws.merge_cells(f'A{current_row}:D{current_row}')
                allot_header_cell = ws[f'A{current_row}']
                allot_header_cell.value = "Allotments"
                allot_header_cell.fill = PatternFill(start_color="e67e22", end_color="e67e22", fill_type="solid")
                allot_header_cell.font = Font(bold=True, color="FFFFFF")
                current_row += 1

                allot_headers = ['Company', 'Qty', 'CIF $', 'CIF INR']
                for col_num, header in enumerate(allot_headers, 1):
                    cell = ws.cell(row=current_row, column=col_num, value=header)
                    cell.fill = PatternFill(start_color="e67e22", end_color="e67e22", fill_type="solid")
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.border = thin_border
                current_row += 1

                for allot in allotments:
                    allot_values = [
                        allot.allotment.company.name if allot.allotment and allot.allotment.company else '-',
                        f"{float(allot.qty or 0):.2f}",
                        f"{float(allot.cif_fc or 0):.2f}",
                        f"{float(allot.cif_inr or 0):.2f}"
                    ]
                    for col_num, value in enumerate(allot_values, 1):
                        cell = ws.cell(row=current_row, column=col_num, value=value)
                        cell.border = thin_border
                    current_row += 1

            # Balance calculation
            current_row += 1
            balance = float(item.quantity or 0) - float(item.debited_quantity or 0) - float(item.allotted_quantity or 0)
            ws.merge_cells(f'A{current_row}:J{current_row}')
            balance_cell = ws[f'A{current_row}']
            balance_cell.value = f"Balance Quantity: {balance:.2f}"
            balance_cell.fill = PatternFill(start_color="e8e8e8", end_color="e8e8e8", fill_type="solid")
            balance_cell.font = Font(bold=True, color="e74c3c")
            balance_cell.border = thin_border
            current_row += 2

    # Notes Section
    if license_obj.balance_report_notes:
        current_row += 1
        ws.merge_cells(f'A{current_row}:J{current_row}')
        notes_header_cell = ws[f'A{current_row}']
        notes_header_cell.value = "Notes"
        notes_header_cell.fill = section_fill
        notes_header_cell.font = section_font
        notes_header_cell.alignment = Alignment(horizontal='center', vertical='center')
        current_row += 1

        ws.merge_cells(f'A{current_row}:J{current_row}')
        notes_cell = ws[f'A{current_row}']
        notes_cell.value = license_obj.balance_report_notes
        notes_cell.fill = PatternFill(start_color="fffacd", end_color="fffacd", fill_type="solid")
        notes_cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        notes_cell.border = thin_border
        ws.row_dimensions[current_row].height = 60

    # Set column widths
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    ws.column_dimensions['I'].width = 15
    ws.column_dimensions['J'].width = 15

    # Save to bytes
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    # Create response
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{license_obj.license_number}-balance.xlsx"'
    return response


def build_balance_excel(license_obj):
    """
    Generate Excel summary report matching the two bottom tables in balance_pdf:
    1. Summary (BOE & Allotments)
    2. Summary (Balance Quantity)
    """
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from decimal import Decimal as _Dec
    from collections import defaultdict
    from django.db.models import Sum as _Sum, DecimalField as _DF, Value as _Val
    from django.db.models.functions import Coalesce as _Coalesce
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems


    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"

    # ── Styles ────────────────────────────────────────────────────────────
    HDR_FILL   = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    HDR_FONT   = Font(bold=True, color="FFFFFF", size=9)
    BOE_FILL   = PatternFill(start_color="DEEAF1", end_color="DEEAF1", fill_type="solid")
    ALLOT_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    YEL_FILL   = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    ALT_FILL   = PatternFill(start_color="F9F9F9", end_color="F9F9F9", fill_type="solid")
    BOLD       = Font(bold=True, size=9)
    NORM       = Font(size=9)
    THIN_BORDER = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    def _hdr(ws, row, col, value):
        c = ws.cell(row=row, column=col, value=value)
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        return c

    def _cell(ws, row, col, value, fill=None, bold=False, align='left', num_fmt=None):
        c = ws.cell(row=row, column=col, value=value)
        if fill: c.fill = fill
        c.font = BOLD if bold else NORM
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        if num_fmt: c.number_format = num_fmt
        return c

    license_date_str = license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-'
    license_expiry_str = license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-'
    ledger_date_str = license_obj.ledger_date.strftime('%d-%m-%Y') if license_obj.ledger_date else '-'
    lic_no = license_obj.license_number or '-'

    # ── Collect summary rows ──────────────────────────────────────────────
    from datetime import date as _date_cls
    summary_rows = []   # (group, sort_date, row_data_dict, is_boe)
    total_cif = 0.0

    for item in license_obj.import_license.all():
        item_name = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else (item.description or '-')

        boes = RowDetails.objects.filter(
            sr_number_id=item.id, transaction_type='D'
        ).select_related('bill_of_entry', 'bill_of_entry__port', 'bill_of_entry__company')

        for rd in boes:
            qty  = float(rd.qty or 0)
            cif  = float(rd.cif_fc or 0)
            rate = cif / qty if qty else 0.0
            total_cif += cif
            boe_company = rd.bill_of_entry.company.name if rd.bill_of_entry.company else '-'
            ref_no   = rd.bill_of_entry.bill_of_entry_number or '-'
            ref_date = rd.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if rd.bill_of_entry.bill_of_entry_date else ''
            ref_str  = f"{ref_no} / {ref_date}" if ref_date else ref_no
            product  = rd.bill_of_entry.product_name or item_name
            _sort_dt = rd.bill_of_entry.bill_of_entry_date or _date_cls.min
            summary_rows.append((0, _sort_dt, {
                'item': product, 'type': 'BOE', 'company': boe_company,
                'reference': ref_str, 'qty': qty, 'rate': rate, 'cif': cif
            }, True))

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
            ref_str = f"{invoice} / ETA: {eta}" if eta else invoice
            product = ai.allotment.item_name or item_name
            _sort_dt = ai.allotment.estimated_arrival_date or _date_cls.min
            summary_rows.append((1, _sort_dt, {
                'item': product, 'type': 'Allotment', 'company': company,
                'reference': ref_str, 'qty': qty, 'rate': rate, 'cif': cif
            }, False))

    # BOEs first (sorted by BOE date), then allotments (sorted by allotment date)
    summary_rows.sort(key=lambda x: (x[0], x[1]))

    # ── Pre-aggregate balance data ─────────────────────────────────────────
    # New restriction model: condition_type on LicenseImportItemsModel is
    # the source of truth. Percentage conditions share a pool computed by
    # compute_condition_pools(); AU / blank use the full licence balance.
    from apps.license.services.condition_pool import compute_condition_pools as _ccp
    _cond_pools = _ccp(license_obj)

    _bal_agg = defaultdict(lambda: {
        'qty': 0.0, 'total_qty': 0.0, 'sr_ids': [],
        'description': '', 'hs_code': '', 'condition_type': ''
    })
    for _item in license_obj.import_license.all():
        _key = ', '.join(sorted([i.name for i in _item.items.all()])) if _item.items.exists() else (_item.description or '-')
        _bal_agg[_key]['qty'] += float(_item.available_quantity or 0)
        _bal_agg[_key]['total_qty'] += float(_item.quantity or 0)
        _bal_agg[_key]['sr_ids'].append(_item.serial_number)
        if not _bal_agg[_key]['description']:
            _bal_agg[_key]['description'] = _item.description or _key
        if not _bal_agg[_key]['hs_code']:
            _bal_agg[_key]['hs_code'] = str(_item.hs_code.hs_code if _item.hs_code else '-')
        if _item.condition_type and not _bal_agg[_key]['condition_type']:
            _bal_agg[_key]['condition_type'] = _item.condition_type

    _license_balance = float(license_obj.get_balance_cif or 0)
    total_license_cif = total_cif + _license_balance

    # ══════════════════════════════════════════════════════════════════════
    # Section 1: License info row
    # ══════════════════════════════════════════════════════════════════════
    r = 1
    _today = _date_cls.today()
    INFO_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    INFO_FONT = Font(bold=True, color="FFFFFF", size=9)
    if license_obj.license_expiry_date:
        _days = (license_obj.license_expiry_date - _today).days
        if _days < 0:
            EXPIRY_FILL = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
        elif _days <= 90:
            EXPIRY_FILL = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")
        else:
            EXPIRY_FILL = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
    else:
        EXPIRY_FILL = INFO_FILL
    for col, (label, val) in enumerate([
        ('License No', lic_no),
        ('License Date', license_date_str),
        ('Expiry Date', license_expiry_str),
        ('Total CIF', f"{total_license_cif:,.2f}"),
        ('Ledger Date', ledger_date_str),
    ], 1):
        c = ws.cell(row=r, column=col, value=f"{label}: {val}")
        c.fill = EXPIRY_FILL if col == 3 else INFO_FILL
        c.font = INFO_FONT
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal='right' if col == 4 else 'left', vertical='center')
    r += 1

    # ══════════════════════════════════════════════════════════════════════
    # Section 2: Summary (BOE & Allotments)
    # ══════════════════════════════════════════════════════════════════════
    # Section header (merged A:G)
    ws.merge_cells(f'A{r}:G{r}')
    sh = ws[f'A{r}']
    sh.value = 'Summary (BOE & Allotments)'
    sh.fill = HDR_FILL; sh.font = Font(bold=True, color="FFFFFF", size=10)
    sh.alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    # Column headers
    SUMM_COLS = ['Item', 'Type', 'Company', 'Reference', 'Qty', 'Rate', 'CIF Value (FC)']
    for col, h in enumerate(SUMM_COLS, 1):
        _hdr(ws, r, col, h)
    r += 1

    # Data rows
    for _s, _sd, row_data, is_boe in summary_rows:
        fill = BOE_FILL if is_boe else ALLOT_FILL
        _cell(ws, r, 1, row_data['item'],      fill=fill)
        _cell(ws, r, 2, row_data['type'],      fill=fill)
        _cell(ws, r, 3, row_data['company'],   fill=fill)
        _cell(ws, r, 4, row_data['reference'], fill=fill)
        _cell(ws, r, 5, row_data['qty'],       fill=fill, align='right', num_fmt='#,##0.00')
        _cell(ws, r, 6, row_data['rate'],      fill=fill, align='right', num_fmt='#,##0.00')
        _cell(ws, r, 7, row_data['cif'],       fill=fill, align='right', num_fmt='#,##0.00')
        r += 1

    # Total row
    if summary_rows:
        _cell(ws, r, 1, '', fill=TOTAL_FILL)
        _cell(ws, r, 2, '', fill=TOTAL_FILL)
        _cell(ws, r, 3, '', fill=TOTAL_FILL)
        _cell(ws, r, 4, 'TOTAL', fill=TOTAL_FILL, bold=True, align='right')
        _cell(ws, r, 5, '', fill=TOTAL_FILL)
        _cell(ws, r, 6, '', fill=TOTAL_FILL)
        _cell(ws, r, 7, total_cif, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        r += 1

    r += 1  # blank row

    # ══════════════════════════════════════════════════════════════════════
    # Section 3: Utilization Planning (E1) / Summary (Balance Quantity)
    # ══════════════════════════════════════════════════════════════════════
    _norm_vals = list(license_obj.export_license.values_list('norm_class__norm_class', flat=True))
    _is_e1 = any(n and 'E1' in str(n) and 'E126' not in str(n) and 'E132' not in str(n) for n in _norm_vals)
    _is_e5 = any(n and str(n).strip() == 'E5' for n in _norm_vals)
    _is_e132 = any(n and str(n).strip() == 'E132' for n in _norm_vals)
    if _is_e1:
        from apps.license.services.e1_plan import (
            E1_CATS as _E1_CATS_BE,
            E1_EXCLUDED_CONDITIONS as _E1_EXCL_BE,
            E1_MAX_PRICES as _E1_MAX_PRICES_BE,
            classify_e1_item as _classify_e1_be,
            compute_e1_plan as _compute_e1_plan_be,
        )
        _e1_display = {c: 0.0 for c in _E1_CATS_BE}
        _e1_util    = {c: 0.0 for c in _E1_CATS_BE}
        _cat_first_desc = {c: '' for c in _E1_CATS_BE}
        _unclassified = []
        for _ik in _bal_agg:
            _agg = _bal_agg[_ik]
            _bq = _agg['qty']
            _de = _agg['description'] or _ik
            _hs = _agg['hs_code']
            _lbl = _classify_e1_be(_ik, _hs, _de)
            if _lbl:
                _e1_display[_lbl] += _bq
                _excl = _E1_EXCL_BE.get(_lbl, frozenset())
                for _ct, _q in _agg.get('qty_by_cond', {}).items():
                    if _ct not in _excl:
                        _e1_util[_lbl] += _q
                if not _cat_first_desc[_lbl]:
                    _cat_first_desc[_lbl] = _de
            else:
                _sr_str = ', '.join(str(s) for s in sorted(set(_agg['sr_ids'])))
                _unclassified.append((_ik, _sr_str, _hs, _de, _bq))

    # E1's utilisation table is 8 cols wide; E5 and "other" stay 7 cols.
    _util_span = 'H' if _is_e1 else ('I' if _is_e132 else 'G')
    _balcif_label_span = 'E' if _is_e1 else ('H' if _is_e132 else 'D')
    _balcif_value_col = 6 if _is_e1 else (9 if _is_e132 else 5)
    ws.merge_cells(f'A{r}:{_util_span}{r}')
    bh = ws[f'A{r}']
    bh.value = 'Utilization Planning' if (_is_e1 or _is_e5 or _is_e132) else 'Summary (Balance Quantity)'
    bh.fill = HDR_FILL; bh.font = Font(bold=True, color="FFFFFF", size=10)
    bh.alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    # BALANCE CIF $ row.
    ws.merge_cells(f'A{r}:{_balcif_label_span}{r}')
    bc = ws[f'A{r}']
    bc.value = 'BALANCE CIF $'
    bc.fill = HDR_FILL; bc.font = Font(bold=True, color="FFFFFF", size=9)
    bc.alignment = Alignment(horizontal='center', vertical='center')
    bc.border = THIN_BORDER
    yc = ws.cell(row=r, column=_balcif_value_col, value=_license_balance)
    yc.fill = YEL_FILL; yc.font = Font(bold=True, size=9)
    yc.border = THIN_BORDER
    yc.alignment = Alignment(horizontal='right', vertical='center')
    yc.number_format = '#,##0.00'
    r += 1

    if _is_e1:
        for col, h in enumerate(['Item Category', 'Rate ($/unit)', 'Bal Qty', 'Util Qty', 'Unit Price', 'Planned CIF ($)', 'Product Description', 'Remaining Bal $'], 1):
            _hdr(ws, r, col, h)
        r += 1

        _e1_planned_per_cat, _e1_rate_per_cat = _compute_e1_plan_be(
            _e1_display, _e1_util, _license_balance,
        )
        _total_planned = 0.0
        _e1_remaining = _license_balance
        for _idx, _lbl in enumerate(_E1_CATS_BE):
            _bq = _e1_display[_lbl]
            _uq = _e1_util[_lbl]
            _pc = _e1_planned_per_cat.get(_lbl, 0.0)
            _rt = float(_E1_MAX_PRICES_BE[_lbl])
            _up_formula = f'=IF(D{r}=0,0,ROUNDDOWN(F{r}/D{r},2))'
            _e1_remaining -= _pc
            _total_planned += _pc
            _rf = None if _idx % 2 == 0 else ALT_FILL
            _cell(ws, r, 1, _lbl, fill=_rf)
            _cell(ws, r, 2, _rt, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 3, _bq, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 4, _uq, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 5, _up_formula, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 6, _pc, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 7, _cat_first_desc.get(_lbl, ''), fill=_rf)
            _cell(ws, r, 8, _e1_remaining, fill=_rf, align='right', num_fmt='#,##0.00')
            r += 1

        if _bal_agg:
            from apps.license.utils.condition_excel import annotate_cell as _annotate_e1_item_be
            r += 1
            ws.merge_cells(f'A{r}:H{r}')
            _uh = ws[f'A{r}']
            _uh.value = 'LICENSE ITEM LIST'
            _uh.fill = HDR_FILL; _uh.font = Font(bold=True, color="FFFFFF", size=9)
            _uh.alignment = Alignment(horizontal='center', vertical='center')
            _uh.border = THIN_BORDER
            r += 1
            for col, h in enumerate(['Item Name', 'Sr No(s)', 'HS Code', 'Product Description', 'Total Qty', 'Balance Qty'], 1):
                _hdr(ws, r, col, h)
            r += 1
            for _i2, _ik2 in enumerate(sorted(_bal_agg.keys())):
                _agg2 = _bal_agg[_ik2]
                _sr2 = ', '.join(str(s) for s in sorted(set(_agg2['sr_ids'])))
                _hs2 = _agg2['hs_code']
                _de2 = _agg2['description'] or _ik2
                _bq2 = _agg2['qty']
                _tq2 = _agg2['total_qty']
                _cond2 = _agg2.get('condition_type') or ''
                _rf2 = None if _i2 % 2 == 0 else ALT_FILL
                _name_cell = _cell(ws, r, 1, _ik2, fill=_rf2)
                _cell(ws, r, 2, _sr2, fill=_rf2, align='center')
                _cell(ws, r, 3, _hs2, fill=_rf2)
                _cell(ws, r, 4, _de2, fill=_rf2)
                _cell(ws, r, 5, _tq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 6, _bq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                _annotate_e1_item_be(_name_cell, _cond2)
                r += 1

        r += 1
        _cell(ws, r, 1, '', fill=TOTAL_FILL)
        _cell(ws, r, 2, '', fill=TOTAL_FILL)
        _cell(ws, r, 3, '', fill=TOTAL_FILL)
        _cell(ws, r, 4, '', fill=TOTAL_FILL)
        _cell(ws, r, 5, 'TOTAL PLANNED CIF $', fill=TOTAL_FILL, bold=True, align='right')
        _cell(ws, r, 6, _total_planned, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        r += 1
        _rem = _license_balance - _total_planned
        _RF = PatternFill(start_color="C00000" if _rem < 0 else "1F4E79",
                          end_color="C00000" if _rem < 0 else "1F4E79", fill_type="solid")
        for _ci in range(1, 6):
            _cx = ws.cell(row=r, column=_ci)
            _cx.fill = _RF; _cx.border = THIN_BORDER
        _rc = ws.cell(row=r, column=5, value='REMAINING BALANCE CIF $')
        _rc.fill = _RF; _rc.font = Font(bold=True, color="FFFFFF", size=9)
        _rc.border = THIN_BORDER; _rc.alignment = Alignment(horizontal='right', vertical='center')
        _rc2 = ws.cell(row=r, column=6, value=_rem)
        _rc2.fill = _RF; _rc2.font = Font(bold=True, color="FFFFFF", size=9)
        _rc2.border = THIN_BORDER
        _rc2.alignment = Alignment(horizontal='right', vertical='center')
        _rc2.number_format = '#,##0.00'
        r += 1
    elif _is_e5:
        from apps.license.services.e5_plan import (
            E5_CATS as _E5_CATS_ORDERED_BE,
            E5_PLAN_CATS as _E5_PLAN_CATS_BE,
            classify_e5_item as _classify_e5_be,
            compute_e5_plan as _compute_e5_plan_be,
        )
        _e5_totals = {c: 0.0 for c in _E5_PLAN_CATS_BE}
        _e5_first_desc = {}
        _e5_unclassified = []
        _wf_qty = 0.0
        for _ik in _bal_agg:
            _bq = _bal_agg[_ik]['qty']
            _hs = _bal_agg[_ik]['hs_code'] or ''
            _de = _bal_agg[_ik]['description'] or _ik
            _cat = _classify_e5_be(_ik, _hs, _de)
            if _cat:
                _e5_totals[_cat] += _bq
                if not _e5_first_desc.get(_cat):
                    _e5_first_desc[_cat] = _de
            else:
                _sr_str = ', '.join(str(s) for s in sorted(set(_bal_agg[_ik]['sr_ids'])))
                _e5_unclassified.append((_ik, _sr_str, _bal_agg[_ik]['hs_code'], _de, _bq))

        _pool_10_be = _cond_pools.get('10%', _Dec('0'))
        # `_wf_qty` is None — wheat-flour qty is already aggregated
        # into `_e5_totals['WHEAT FLOUR']` by the classifier.
        _e5_planned_per_cat_be, _e5_rate_per_cat_be = _compute_e5_plan_be(
            _e5_totals, None, _license_balance, _pool_10_be,
        )

        for col, h in enumerate(['Item Category', 'Rate ($/unit)', 'Bal Qty', 'Unit Price', 'Planned CIF ($)', 'Product Description', 'Remaining Bal $'], 1):
            _hdr(ws, r, col, h)
        r += 1

        _e5_planned = 0.0
        for _idx, _lbl in enumerate(_E5_CATS_ORDERED_BE):
            _bq = _e5_totals.get(_lbl, 0.0)
            _pc = _e5_planned_per_cat_be.get(_lbl, 0.0)
            _rt = _e5_rate_per_cat_be.get(_lbl, 0.0)
            # Live unit-price formula off Bal Qty (C) and Planned CIF (E).
            _up_formula = f'=IF(C{r}=0,0,ROUNDDOWN(E{r}/C{r},2))'
            _e5_planned += _pc
            _rf = None if _idx % 2 == 0 else ALT_FILL
            _cell(ws, r, 1, _lbl, fill=_rf)
            if _bq or _pc:
                _cell(ws, r, 2, _rt, fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 3, _bq, fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 4, _up_formula, fill=_rf, align='right', num_fmt='#,##0.00')
            else:
                _cell(ws, r, 2, '-', fill=_rf, align='center')
                _cell(ws, r, 3, '-', fill=_rf, align='center')
                _cell(ws, r, 4, '-', fill=_rf, align='center')
            _cell(ws, r, 5, _pc, fill=_rf, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 6, _e5_first_desc.get(_lbl, ''), fill=_rf)
            _cell(ws, r, 7, _license_balance - _e5_planned, fill=_rf, align='right', num_fmt='#,##0.00')
            r += 1

        if _bal_agg:
            from apps.license.utils.condition_excel import annotate_cell as _annotate_e5_item_be
            r += 1
            ws.merge_cells(f'A{r}:G{r}')
            _uh = ws[f'A{r}']
            _uh.value = 'LICENSE ITEM LIST'
            _uh.fill = HDR_FILL; _uh.font = Font(bold=True, color="FFFFFF", size=9)
            _uh.alignment = Alignment(horizontal='center', vertical='center')
            _uh.border = THIN_BORDER
            r += 1
            for col, h in enumerate(['Item Name', 'Sr No(s)', 'HS Code', 'Product Description', 'Total Qty', 'Balance Qty'], 1):
                _hdr(ws, r, col, h)
            r += 1
            for _i2, _ik2 in enumerate(sorted(_bal_agg.keys())):
                _agg2 = _bal_agg[_ik2]
                _sr2 = ', '.join(str(s) for s in sorted(set(_agg2['sr_ids'])))
                _hs2 = _agg2['hs_code']
                _de2 = _agg2['description'] or _ik2
                _bq2 = _agg2['qty']
                _tq2 = _agg2['total_qty']
                _cond2 = _agg2.get('condition_type') or ''
                _rf2 = None if _i2 % 2 == 0 else ALT_FILL
                _name_cell = _cell(ws, r, 1, _ik2, fill=_rf2)
                _cell(ws, r, 2, _sr2, fill=_rf2, align='center')
                _cell(ws, r, 3, _hs2, fill=_rf2)
                _cell(ws, r, 4, _de2, fill=_rf2)
                _cell(ws, r, 5, _tq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 6, _bq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                # Colour the Item Name cell by License Marking so the
                # Excel matches the ConditionBadge palette in the UI.
                _annotate_e5_item_be(_name_cell, _cond2)
                r += 1

        r += 1
        _cell(ws, r, 1, '', fill=TOTAL_FILL)
        _cell(ws, r, 2, '', fill=TOTAL_FILL)
        _cell(ws, r, 3, '', fill=TOTAL_FILL)
        _cell(ws, r, 4, 'TOTAL ALLOCATED CIF $', fill=TOTAL_FILL, bold=True, align='right')
        _cell(ws, r, 5, _e5_planned, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        r += 1
    elif _is_e132:
        # E132 planning classification (services/e132_plan.py): each balance item
        # is classified into exactly one planning item; quantity is summed per item
        # and priced at the item's fixed unit price (Milk price is To-Be-Defined).
        from apps.license.services.e132_plan import plan_e132 as _plan_e132_be
        _e132_records = [
            {'record_id': _ik, 'quantity': _bal_agg[_ik]['qty'],
             'hs_code': _bal_agg[_ik]['hs_code'] or '',
             'description': _bal_agg[_ik]['description'] or _ik}
            for _ik in sorted(_bal_agg.keys(),
                              key=lambda k: min(_bal_agg[k]['sr_ids'] or [0]))
        ]
        _e132_plan = _plan_e132_be(_e132_records, _license_balance)

        if not _e132_plan['items']:
            ws.merge_cells(f'A{r}:I{r}')
            _nm = ws[f'A{r}']
            _nm.value = 'No applicable E132 planning item matched the balance items.'
            _nm.font = Font(bold=True, size=9)
            _nm.alignment = Alignment(horizontal='center', vertical='center')
            r += 1
        else:
            for col, h in enumerate(['Planning Item', 'Total Qty', 'Unit Price ($)', 'Planning Value ($)', 'Source Records'], 1):
                _hdr(ws, r, col, h)
            r += 1
            _e132_ds = r
            for _idx, _pi in enumerate(_e132_plan['items']):
                _rf = None if _idx % 2 == 0 else ALT_FILL
                _price = _pi['unit_price']
                _val = _pi['planning_value']
                _cell(ws, r, 1, _pi['planning_item_name'], fill=_rf, bold=True)
                _cell(ws, r, 2, float(_pi['total_quantity']), fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 3, (float(_price) if _price is not None else 'TBD'), fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 4, (float(_val) if _val is not None else 'TBD'), fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 5, _pi['num_source_records'], fill=_rf, align='center')
                r += 1
            _e132_de = r - 1
            # TOTAL = live SUM of the column (not a pre-computed value), so it
            # always matches the (capped) cells above and updates if they change.
            _cell(ws, r, 1, 'TOTAL', fill=TOTAL_FILL, bold=True)
            _cell(ws, r, 2, f'=SUM(B{_e132_ds}:B{_e132_de})', fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 3, '', fill=TOTAL_FILL)
            _cell(ws, r, 4, f'=SUM(D{_e132_ds}:D{_e132_de})', fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 5, '', fill=TOTAL_FILL)
            r += 1
            if _e132_plan['exceptions']:
                ws.merge_cells(f'A{r}:E{r}')
                _ex = ws[f'A{r}']
                _ex.value = (f"{len(_e132_plan['exceptions'])} balance item(s) matched no E132 "
                             f"planning rule and are excluded (see exception report).")
                _ex.font = Font(italic=True, size=8, color="C00000")
                _ex.alignment = Alignment(horizontal='left', vertical='center')
                r += 1
    else:
        from apps.license.utils.condition_excel import annotate_cell as _annotate_cond_be
        # Column headers
        BAL_COLS = ['HSN Code', 'Item Name', 'Bal Qty', 'Unit Price', 'CIF FC', 'Cond']
        for col, h in enumerate(BAL_COLS, 1):
            _hdr(ws, r, col, h)
        r += 1

        # Data rows
        for idx, item_key in enumerate(sorted(_bal_agg.keys())):
            b_qty = _bal_agg[item_key]['qty']
            cond = _bal_agg[item_key].get('condition_type') or ''
            if cond in _cond_pools:
                b_cif = float(min(_cond_pools[cond], _Dec(str(_license_balance))))
            else:
                b_cif = _license_balance

            unit_price = b_cif / b_qty if b_qty else 0.0
            desc = _bal_agg[item_key]['description'] or item_key
            hs   = _bal_agg[item_key]['hs_code']
            row_fill = None if idx % 2 == 0 else ALT_FILL

            hs_cell = _cell(ws, r, 1, hs,         fill=row_fill)
            _cell(ws, r, 2, desc,       fill=row_fill)
            _cell(ws, r, 3, b_qty,      fill=row_fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 4, unit_price, fill=row_fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 5, b_cif,      fill=row_fill, align='right', num_fmt='#,##0.00')
            cond_cell = _cell(ws, r, 6, cond, fill=row_fill, align='center', bold=True)
            _annotate_cond_be(hs_cell, cond)
            _annotate_cond_be(cond_cell, cond)
            r += 1

    # ── Column widths ─────────────────────────────────────────────────────
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 40
    ws.column_dimensions['D'].width = 22
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 28
    ws.column_dimensions['G'].width = 14
    ws.column_dimensions['H'].width = 14
    ws.column_dimensions['I'].width = 16

    ws.freeze_panes = 'A2'

    # ── Save ──────────────────────────────────────────────────────────────
    # Recalculate formulas (e.g. the E132 TOTAL =SUM) on open so viewers show
    # computed values, not blank cached results.
    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True

    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{license_obj.license_number}-summary.xlsx"'
    return response


def build_bulk_balance_excel(request):
    """
    Generate a multi-sheet Excel with one sheet per license.
    Sheet name = license number. Same layout as balance_excel.
    POST body: {"license_numbers": ["3011007415", "3011007018", ...]}
    """
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter as _gcl
    from io import BytesIO
    from decimal import Decimal as _Dec
    from collections import defaultdict
    from django.db.models import Sum as _Sum, DecimalField as _DF, Value as _Val
    from django.db.models.functions import Coalesce as _Coalesce
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems
    from rest_framework.response import Response
    from apps.license.models import LicenseDetailsModel

    license_numbers = request.data.get('license_numbers', [])
    if not license_numbers:
        return Response({'error': 'No license numbers provided.'}, status=400)

    licenses = LicenseDetailsModel.objects.filter(
        license_number__in=license_numbers
    ).prefetch_related('import_license', 'import_license__items')

    if not licenses.exists():
        return Response({'error': 'No matching licenses found.'}, status=404)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    # ── Shared styles ──────────────────────────────────────────────────────
    HDR_FILL   = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    HDR_FONT   = Font(bold=True, color="FFFFFF", size=9)
    BOE_FILL   = PatternFill(start_color="DEEAF1", end_color="DEEAF1", fill_type="solid")
    ALLOT_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    YEL_FILL   = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    ALT_FILL   = PatternFill(start_color="F9F9F9", end_color="F9F9F9", fill_type="solid")
    BOLD       = Font(bold=True, size=9)
    NORM       = Font(size=9)
    THIN_BORDER = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    def _hdr(ws, row, col, value):
        c = ws.cell(row=row, column=col, value=value)
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        return c

    def _cell(ws, row, col, value, fill=None, bold=False, align='left', num_fmt=None):
        c = ws.cell(row=row, column=col, value=value)
        if fill: c.fill = fill
        c.font = BOLD if bold else NORM
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        if num_fmt: c.number_format = num_fmt
        return c

    def _write_license_sheet(wb, license_obj):
        from datetime import date as _date_cls
        sheet_name = str(license_obj.license_number)[:31]
        ws = wb.create_sheet(title=sheet_name)

        license_date_str = license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-'
        license_expiry_str = license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-'
        ledger_date_str = license_obj.ledger_date.strftime('%d-%m-%Y') if license_obj.ledger_date else '-'
        lic_no = license_obj.license_number or '-'

        summary_rows = []
        total_cif = 0.0
        total_cif_inr = 0.0

        for item in license_obj.import_license.all():
            item_name = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else (item.description or '-')

            boes = RowDetails.objects.filter(
                sr_number_id=item.id, transaction_type='D'
            ).select_related('bill_of_entry', 'bill_of_entry__port', 'bill_of_entry__company')

            for rd in boes:
                qty  = float(rd.qty or 0)
                cif  = float(rd.cif_fc or 0)
                cif_inr = float(rd.cif_inr or 0)
                rate = cif / qty if qty else 0.0
                total_cif += cif
                total_cif_inr += cif_inr
                boe_company = rd.bill_of_entry.company.name if rd.bill_of_entry.company else '-'
                ref_no   = rd.bill_of_entry.bill_of_entry_number or '-'
                ref_date = rd.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if rd.bill_of_entry.bill_of_entry_date else ''
                ref_str  = f"{ref_no} / {ref_date}" if ref_date else ref_no
                product  = rd.bill_of_entry.product_name or item_name
                _sort_dt = rd.bill_of_entry.bill_of_entry_date or _date_cls.min
                summary_rows.append((0, _sort_dt, {
                    'item': product, 'type': 'BOE', 'company': boe_company,
                    'reference': ref_str, 'qty': qty, 'rate': rate, 'cif': cif,
                    'cif_inr': cif_inr,
                }, True))

            allotments = AllotmentItems.objects.filter(
                item_id=item.id, allotment__bill_of_entry__isnull=True
            ).select_related('allotment', 'allotment__company')

            for ai in allotments:
                qty     = float(ai.qty or 0)
                cif     = float(ai.cif_fc or 0)
                cif_inr = float(ai.cif_inr or 0)
                rate    = cif / qty if qty else 0.0
                total_cif += cif
                total_cif_inr += cif_inr
                company = ai.allotment.company.name if ai.allotment.company else '-'
                invoice = ai.allotment.invoice or '-'
                eta     = ai.allotment.estimated_arrival_date.strftime('%d-%m-%Y') if ai.allotment.estimated_arrival_date else ''
                ref_str = f"{invoice} / ETA: {eta}" if eta else invoice
                product = ai.allotment.item_name or item_name
                _sort_dt = ai.allotment.estimated_arrival_date or _date_cls.min
                summary_rows.append((1, _sort_dt, {
                    'item': product, 'type': 'Allotment', 'company': company,
                    'reference': ref_str, 'qty': qty, 'rate': rate, 'cif': cif,
                    'cif_inr': cif_inr,
                }, False))

        # BOEs first (sorted by BOE date), then allotments (sorted by allotment date)
        summary_rows.sort(key=lambda x: (x[0], x[1]))

        # New restriction model: condition_type on LicenseImportItemsModel is
        # the source of truth. Percentage conditions share a pool computed
        # by compute_condition_pools(); AU / blank conditions use the full
        # licence balance.
        from apps.license.services.condition_pool import compute_condition_pools as _ccp
        _cond_pools = _ccp(license_obj)

        _bal_agg = defaultdict(lambda: {
            'qty': 0.0, 'total_qty': 0.0, 'sr_ids': [],
            'description': '', 'hs_code': '', 'condition_type': '',
            'qty_by_cond': {},
            'plan_qty': 0.0, 'plan_cif': 0.0,
        })
        # Effective plan per license: manual if manually planned, else norm.
        from apps.license.services.norm_plan import effective_plan_for_license
        _plan_source, _plan_map = effective_plan_for_license(license_obj)
        for _item in license_obj.import_license.all():
            _key = ', '.join(sorted([i.name for i in _item.items.all()])) if _item.items.exists() else (_item.description or '-')
            _avail = float(_item.available_quantity or 0)
            _bal_agg[_key]['qty'] += _avail
            _bal_agg[_key]['total_qty'] += float(_item.quantity or 0)
            _pl = _plan_map.get(_item.id)
            if _pl:
                _bal_agg[_key]['plan_qty'] += _pl['planned_quantity']
                _bal_agg[_key]['plan_cif'] += _pl['planned_cif']
            _bal_agg[_key]['sr_ids'].append(_item.serial_number)
            if not _bal_agg[_key]['description']:
                _bal_agg[_key]['description'] = _item.description or _key
            if not _bal_agg[_key]['hs_code']:
                _bal_agg[_key]['hs_code'] = str(_item.hs_code.hs_code if _item.hs_code else '-')
            # Carry per-item licence-condition (AU / 2% / 3% / 5% / 10%)
            # through to the bulk-balance Excel cell.
            if _item.condition_type and not _bal_agg[_key]['condition_type']:
                _bal_agg[_key]['condition_type'] = _item.condition_type
            # Per-condition qty breakdown for E1's Display/Util-qty split.
            _ct = (_item.condition_type or '').strip()
            _bal_agg[_key]['qty_by_cond'][_ct] = _bal_agg[_key]['qty_by_cond'].get(_ct, 0.0) + _avail

        _license_balance = float(license_obj.get_balance_cif or 0)
        total_license_cif = total_cif + _license_balance

        r = 1
        _today = _date_cls.today()
        INFO_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        INFO_FONT = Font(bold=True, color="FFFFFF", size=9)
        if license_obj.license_expiry_date:
            _days = (license_obj.license_expiry_date - _today).days
            if _days < 0:
                EXPIRY_FILL = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
            elif _days <= 90:
                EXPIRY_FILL = PatternFill(start_color="ED7D31", end_color="ED7D31", fill_type="solid")
            else:
                EXPIRY_FILL = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        else:
            EXPIRY_FILL = INFO_FILL
        iec_val = license_obj.exporter.iec if license_obj.exporter else '-'
        for col, (label, val) in enumerate([
            ('License No', lic_no),
            ('IEC', iec_val),
            ('License Date', license_date_str),
            ('Expiry Date', license_expiry_str),
            ('Total CIF', f"{total_license_cif:,.2f}"),
            ('Ledger Date', ledger_date_str),
        ], 1):
            c = ws.cell(row=r, column=col, value=f"{label}: {val}")
            c.fill = EXPIRY_FILL if col == 4 else INFO_FILL
            c.font = INFO_FONT
            c.border = THIN_BORDER
            c.alignment = Alignment(horizontal='right' if col == 5 else 'left', vertical='center')
        r += 1

        ws.merge_cells(f'A{r}:H{r}')
        sh = ws[f'A{r}']
        sh.value = 'Summary (BOE & Allotments)'
        sh.fill = HDR_FILL; sh.font = Font(bold=True, color="FFFFFF", size=10)
        sh.alignment = Alignment(horizontal='center', vertical='center')
        r += 1

        SUMM_COLS = ['Item', 'Type', 'Company', 'Reference', 'Qty', 'Rate', 'CIF Value (FC)', 'CIF Value (INR)']
        for col, h in enumerate(SUMM_COLS, 1):
            _hdr(ws, r, col, h)
        r += 1

        for _s, _sd, row_data, is_boe in summary_rows:
            fill = BOE_FILL if is_boe else ALLOT_FILL
            _cell(ws, r, 1, row_data['item'],          fill=fill)
            _cell(ws, r, 2, row_data['type'],          fill=fill)
            _cell(ws, r, 3, row_data['company'],       fill=fill)
            _cell(ws, r, 4, row_data['reference'],     fill=fill)
            _cell(ws, r, 5, row_data['qty'],           fill=fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 6, row_data['rate'],          fill=fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 7, row_data['cif'],           fill=fill, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 8, row_data.get('cif_inr', 0), fill=fill, align='right', num_fmt='#,##0.00')
            r += 1

        if summary_rows:
            _cell(ws, r, 1, '', fill=TOTAL_FILL); _cell(ws, r, 2, '', fill=TOTAL_FILL)
            _cell(ws, r, 3, '', fill=TOTAL_FILL)
            _cell(ws, r, 4, 'TOTAL', fill=TOTAL_FILL, bold=True, align='right')
            _cell(ws, r, 5, '', fill=TOTAL_FILL); _cell(ws, r, 6, '', fill=TOTAL_FILL)
            _cell(ws, r, 7, total_cif, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _cell(ws, r, 8, total_cif_inr, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            r += 1

        r += 1

        # ── Norm check for utilization planning ──────────────────────────
        _norm_vals = list(license_obj.export_license.values_list('norm_class__norm_class', flat=True))
        _is_e1 = any(n and 'E1' in str(n) and 'E126' not in str(n) and 'E132' not in str(n) for n in _norm_vals)
        _is_e5 = any(n and str(n).strip() == 'E5' for n in _norm_vals)
        _is_e132 = any(n and str(n).strip() == 'E132' for n in _norm_vals)
        _exporter_name = license_obj.exporter.name if license_obj.exporter else ''
        _exporter_iec  = license_obj.exporter.iec  if license_obj.exporter else ''
        _port_code     = license_obj.port.code     if license_obj.port     else ''
        _util_return = {
            'lic_no': lic_no, 'norm_type': 'other',
            'balance_cif': _license_balance,
            'total_license_cif': total_license_cif,
            'license_date': license_obj.license_date,
            'license_expiry_date': license_obj.license_expiry_date,
            'port_code': _port_code,
            'exporter_name': _exporter_name, 'iec': _exporter_iec,
            'planned': {}, 'qty_per_cat': {}, 'total_planned': _license_balance, 'categories': [],
            # 10% condition-pool — surfaced for the bulk-summary "10% Balance"
            # column next to DIETARY FIBRE. Default 0; the E5 branch fills it
            # with the real value from compute_condition_pools().
            'pool_10': 0.0,
            'sheet_name': sheet_name,
            'cell_refs': {
                'balance_cif': None,
                'qty_per_cat': {},
                'planned': {},
                'total_planned': None,
                'wastage': None,
            },
        }
        if _is_e1:
            from apps.license.services.e1_plan import (
                E1_CATS as _E1_CATS_ORDERED,
                E1_EXCLUDED_CONDITIONS as _E1_EXCL,
                classify_e1_item as _classify_e1,
            )
            _e1_display = {c: 0.0 for c in _E1_CATS_ORDERED}
            _e1_util    = {c: 0.0 for c in _E1_CATS_ORDERED}
            _cat_first_desc = {c: '' for c in _E1_CATS_ORDERED}
            _unclassified = []
            # Per-category License Marking (priority: stricter % wins).
            _cond_priority_e1 = {"2%": 5, "3%": 4, "5%": 3, "10%": 2, "AU": 1}
            _e1_cond_per_cat: dict[str, str] = {}
            for _ik in _bal_agg:
                _agg = _bal_agg[_ik]
                _bq = _agg['qty']
                _de = _agg['description'] or _ik
                _hs = _agg['hs_code']
                _cond = _agg.get('condition_type') or ''
                _lbl = _classify_e1(_ik, _hs, _de)
                if _lbl:
                    _e1_display[_lbl] += _bq
                    # Util qty = sum across non-excluded conditions for this step.
                    _excl = _E1_EXCL.get(_lbl, frozenset())
                    for _ct, _q in _agg.get('qty_by_cond', {}).items():
                        if _ct not in _excl:
                            _e1_util[_lbl] += _q
                    if not _cat_first_desc[_lbl]:
                        _cat_first_desc[_lbl] = _de
                    if _cond and (
                        _lbl not in _e1_cond_per_cat
                        or _cond_priority_e1.get(_cond, 0) > _cond_priority_e1.get(_e1_cond_per_cat[_lbl], 0)
                    ):
                        _e1_cond_per_cat[_lbl] = _cond
                else:
                    _sr_str = ', '.join(str(s) for s in sorted(set(_agg['sr_ids'])))
                    _unclassified.append((_ik, _sr_str, _hs, _de, _bq))
        elif _is_e5:
            from apps.license.services.e5_plan import (
                E5_PLAN_CATS as _E5_PLAN_CATS,
                classify_e5_item as _classify_e5,
            )
            _e5_totals = {c: 0.0 for c in _E5_PLAN_CATS}
            _e5_first_desc = {}
            _e5_unclassified = []
            _wf_qty = 0.0
            # Per-category License Marking — surfaced to the bulk summary
            # so each category's cells inherit the ConditionBadge colour.
            # Priority: stricter % wins; "AU" only if no % is present.
            _cond_priority = {"2%": 5, "3%": 4, "5%": 3, "10%": 2, "AU": 1}
            _e5_cond_per_cat: dict[str, str] = {}
            for _ik in _bal_agg:
                _bq = _bal_agg[_ik]['qty']
                _hs = _bal_agg[_ik]['hs_code'] or ''
                _de = _bal_agg[_ik]['description'] or _ik
                _cond = _bal_agg[_ik].get('condition_type') or ''
                _cat = _classify_e5(_ik, _hs, _de)
                if _cat:
                    _e5_totals[_cat] += _bq
                    if not _e5_first_desc.get(_cat):
                        _e5_first_desc[_cat] = _de
                    if _cond and (
                        _cat not in _e5_cond_per_cat
                        or _cond_priority.get(_cond, 0) > _cond_priority.get(_e5_cond_per_cat[_cat], 0)
                    ):
                        _e5_cond_per_cat[_cat] = _cond
                else:
                    _sr_str = ', '.join(str(s) for s in sorted(set(_bal_agg[_ik]['sr_ids'])))
                    _e5_unclassified.append((_ik, _sr_str, _bal_agg[_ik]['hs_code'], _de, _bq))
        elif _is_e132:
            # E132 planning classification (rendered below): classify each balance
            # item into one planning item, sum quantity, price at the fixed rate.
            from apps.license.services.e132_plan import plan_e132 as _plan_e132_bulk
            _e132_records = [
                {'record_id': _ik, 'quantity': _bal_agg[_ik]['qty'],
                 'hs_code': _bal_agg[_ik]['hs_code'] or '',
                 'description': _bal_agg[_ik]['description'] or _ik}
                for _ik in sorted(_bal_agg.keys(),
                                  key=lambda k: min(_bal_agg[k]['sr_ids'] or [0]))
            ]
            _e132_plan = _plan_e132_bulk(_e132_records, _license_balance)

        # E1's utilisation table is 8 cols wide (extra Util Qty column);
        # E5/"other" stay 7 cols; E132's planning table is 5 cols.
        _util_span = 'H' if _is_e1 else ('E' if _is_e132 else 'G')
        _balcif_label_span = 'E' if _is_e1 else ('D' if _is_e132 else 'D')
        _balcif_value_col = 6 if _is_e1 else (5 if _is_e132 else 5)
        ws.merge_cells(f'A{r}:{_util_span}{r}')
        bh = ws[f'A{r}']
        bh.value = 'Utilization Planning' if (_is_e1 or _is_e5 or _is_e132) else 'Summary (Balance Quantity)'
        bh.fill = HDR_FILL; bh.font = Font(bold=True, color="FFFFFF", size=10)
        bh.alignment = Alignment(horizontal='center', vertical='center')
        r += 1

        ws.merge_cells(f'A{r}:{_balcif_label_span}{r}')
        bc = ws[f'A{r}']
        bc.value = 'BALANCE CIF $'
        bc.fill = HDR_FILL; bc.font = Font(bold=True, color="FFFFFF", size=9)
        bc.alignment = Alignment(horizontal='center', vertical='center')
        bc.border = THIN_BORDER
        yc = ws.cell(row=r, column=_balcif_value_col, value=_license_balance)
        yc.fill = YEL_FILL; yc.font = Font(bold=True, size=9)
        yc.border = THIN_BORDER
        yc.alignment = Alignment(horizontal='right', vertical='center')
        yc.number_format = '#,##0.00'
        _util_return['cell_refs']['balance_cif'] = yc.coordinate
        r += 1

        if _is_e1:
            from apps.license.services.e1_plan import (
                compute_e1_plan as _compute_e1_plan,
                E1_MAX_PRICES as _E1_MAX_PRICES,
            )
            # 8-column layout adds a Util Qty column (col 4) so the spec's
            # "Display vs Utilization quantity" split is visible.
            # Cols: A=Cat B=Rate C=Bal(Display) D=Util E=UnitPrice F=Planned G=Desc H=Remaining
            for col, h in enumerate(['Item Category', 'Rate ($/unit)', 'Bal Qty', 'Util Qty', 'Unit Price', 'Planned CIF ($)', 'Product Description', 'Remaining Bal $'], 1):
                _hdr(ws, r, col, h)
            r += 1

            _e1_planned_per_cat, _e1_rate_per_cat = _compute_e1_plan(
                _e1_display, _e1_util, _license_balance,
            )
            _total_planned = 0.0
            _e1_remaining = _license_balance
            _planned_per_cat = {}
            for _idx, _lbl in enumerate(_E1_CATS_ORDERED):
                _bq = _e1_display[_lbl]
                _uq = _e1_util[_lbl]
                _pc = _e1_planned_per_cat.get(_lbl, 0.0)
                _rt = float(_E1_MAX_PRICES[_lbl])
                _planned_per_cat[_lbl] = _pc
                # Unit Price = Planned / Util Qty (D), with guard against /0.
                _up_formula = f'=IF(D{r}=0,0,ROUNDDOWN(F{r}/D{r},2))'
                _e1_remaining -= _pc
                _total_planned += _pc
                _rf = None if _idx % 2 == 0 else ALT_FILL
                _cell(ws, r, 1, _lbl, fill=_rf)
                _cell(ws, r, 2, _rt, fill=_rf, align='right', num_fmt='#,##0.00')
                _qty_cell = _cell(ws, r, 3, _bq, fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 4, _uq, fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 5, _up_formula, fill=_rf, align='right', num_fmt='#,##0.00')
                _planned_cell = _cell(ws, r, 6, _pc, fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 7, _cat_first_desc.get(_lbl, ''), fill=_rf)
                _cell(ws, r, 8, _e1_remaining, fill=_rf, align='right', num_fmt='#,##0.00')
                _util_return['cell_refs']['qty_per_cat'][_lbl] = _qty_cell.coordinate
                _util_return['cell_refs']['planned'][_lbl] = _planned_cell.coordinate
                r += 1

            if _bal_agg:
                from apps.license.utils.condition_excel import annotate_cell as _annotate_e1_item
                r += 1
                ws.merge_cells(f'A{r}:H{r}')
                _uh = ws[f'A{r}']
                _uh.value = 'LICENSE ITEM LIST'
                _uh.fill = HDR_FILL; _uh.font = Font(bold=True, color="FFFFFF", size=9)
                _uh.alignment = Alignment(horizontal='center', vertical='center')
                _uh.border = THIN_BORDER
                r += 1
                for col, h in enumerate(['Item Name', 'Sr No(s)', 'HS Code', 'Product Description', 'Total Qty', 'Balance Qty', 'Plan Qty', 'Plan CIF'], 1):
                    _hdr(ws, r, col, h)
                r += 1
                for _i2, _ik2 in enumerate(sorted(_bal_agg.keys())):
                    _agg2 = _bal_agg[_ik2]
                    _sr2 = ', '.join(str(s) for s in sorted(set(_agg2['sr_ids'])))
                    _hs2 = _agg2['hs_code']
                    _de2 = _agg2['description'] or _ik2
                    _bq2 = _agg2['qty']
                    _tq2 = _agg2['total_qty']
                    _cond2 = _agg2.get('condition_type') or ''
                    _rf2 = None if _i2 % 2 == 0 else ALT_FILL
                    _name_cell = _cell(ws, r, 1, _ik2, fill=_rf2)
                    _cell(ws, r, 2, _sr2, fill=_rf2, align='center')
                    _cell(ws, r, 3, _hs2, fill=_rf2)
                    _cell(ws, r, 4, _de2, fill=_rf2)
                    _cell(ws, r, 5, _tq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 6, _bq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 7, _agg2.get('plan_qty', 0.0), fill=_rf2, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 8, _agg2.get('plan_cif', 0.0), fill=_rf2, align='right', num_fmt='#,##0.00')
                    # Colour the Item Name cell by License Marking so the
                    # Excel matches the ConditionBadge palette in the UI.
                    _annotate_e1_item(_name_cell, _cond2)
                    r += 1

            r += 1
            _cell(ws, r, 1, '', fill=TOTAL_FILL)
            _cell(ws, r, 2, '', fill=TOTAL_FILL)
            _cell(ws, r, 3, '', fill=TOTAL_FILL)
            _cell(ws, r, 4, '', fill=TOTAL_FILL)
            _cell(ws, r, 5, 'TOTAL PLANNED CIF $', fill=TOTAL_FILL, bold=True, align='right')
            _total_planned_cell = _cell(ws, r, 6, _total_planned, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _util_return['cell_refs']['total_planned'] = _total_planned_cell.coordinate
            r += 1
            _rem = _license_balance - _total_planned
            _RF = PatternFill(start_color="C00000" if _rem < 0 else "1F4E79",
                              end_color="C00000" if _rem < 0 else "1F4E79", fill_type="solid")
            for _ci in range(1, 6):
                _cx = ws.cell(row=r, column=_ci)
                _cx.fill = _RF; _cx.border = THIN_BORDER
            _rc = ws.cell(row=r, column=5, value='REMAINING BALANCE CIF $')
            _rc.fill = _RF; _rc.font = Font(bold=True, color="FFFFFF", size=9)
            _rc.border = THIN_BORDER; _rc.alignment = Alignment(horizontal='right', vertical='center')
            _rc2 = ws.cell(row=r, column=6, value=_rem)
            _rc2.fill = _RF; _rc2.font = Font(bold=True, color="FFFFFF", size=9)
            _rc2.border = THIN_BORDER
            _rc2.alignment = Alignment(horizontal='right', vertical='center')
            _rc2.number_format = '#,##0.00'
            _util_return['cell_refs']['wastage'] = _rc2.coordinate
            r += 1
            _util_return.update({
                'norm_type': 'E1', 'planned': _planned_per_cat,
                'qty_per_cat': dict(_e1_display),
                'total_planned': _total_planned,
                'categories': list(_E1_CATS_ORDERED),
                'condition_per_cat': dict(_e1_cond_per_cat),
            })
        elif _is_e5:
            from apps.license.services.e5_plan import (
                E5_CATS as _E5_CATS_ORDERED,
                compute_e5_plan as _compute_e5_plan,
            )
            _pool_10 = _cond_pools.get('10%', _Dec('0'))
            # `_wf_qty` is None — wheat-flour qty is already aggregated
            # into `_e5_totals['WHEAT FLOUR']` by the classifier.
            _e5_planned_per_cat, _e5_rate_per_cat = _compute_e5_plan(
                _e5_totals, None, _license_balance, _pool_10,
            )

            for col, h in enumerate(['Item Category', 'Rate ($/unit)', 'Bal Qty', 'Unit Price', 'Planned CIF ($)', 'Product Description', 'Remaining Bal $'], 1):
                _hdr(ws, r, col, h)
            r += 1

            _e5_planned = 0.0
            _e5_qty = {}
            for _idx, _lbl in enumerate(_E5_CATS_ORDERED):
                _bq = _e5_totals.get(_lbl, 0.0)
                _e5_qty[_lbl] = _bq
                _pc = _e5_planned_per_cat.get(_lbl, 0.0)
                _rt = _e5_rate_per_cat.get(_lbl, 0.0)
                # Live formula referencing this row's Bal Qty (col C) and
                # Planned CIF (col E). Zero-qty rows render '-' below.
                _up_formula = f'=IF(C{r}=0,0,ROUNDDOWN(E{r}/C{r},2))'
                _e5_planned += _pc
                _rf = None if _idx % 2 == 0 else ALT_FILL
                _cell(ws, r, 1, _lbl, fill=_rf)
                if _bq or _pc:
                    _cell(ws, r, 2, _rt, fill=_rf, align='right', num_fmt='#,##0.00')
                    _qty_cell = _cell(ws, r, 3, _bq, fill=_rf, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 4, _up_formula, fill=_rf, align='right', num_fmt='#,##0.00')
                else:
                    _cell(ws, r, 2, '-', fill=_rf, align='center')
                    _qty_cell = _cell(ws, r, 3, '-', fill=_rf, align='center')
                    _cell(ws, r, 4, '-', fill=_rf, align='center')
                _planned_cell = _cell(ws, r, 5, _pc, fill=_rf, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 6, _e5_first_desc.get(_lbl, ''), fill=_rf)
                _remaining_cell = _cell(ws, r, 7, _license_balance - _e5_planned, fill=_rf, align='right', num_fmt='#,##0.00')
                _util_return['cell_refs']['qty_per_cat'][_lbl] = _qty_cell.coordinate
                _util_return['cell_refs']['planned'][_lbl] = _planned_cell.coordinate
                _util_return['cell_refs']['wastage'] = _remaining_cell.coordinate
                r += 1

            if _bal_agg:
                from apps.license.utils.condition_excel import annotate_cell as _annotate_e5_item
                r += 1
                ws.merge_cells(f'A{r}:G{r}')
                _uh = ws[f'A{r}']
                _uh.value = 'LICENSE ITEM LIST'
                _uh.fill = HDR_FILL; _uh.font = Font(bold=True, color="FFFFFF", size=9)
                _uh.alignment = Alignment(horizontal='center', vertical='center')
                _uh.border = THIN_BORDER
                r += 1
                for col, h in enumerate(['Item Name', 'Sr No(s)', 'HS Code', 'Product Description', 'Total Qty', 'Balance Qty', 'Plan Qty', 'Plan CIF'], 1):
                    _hdr(ws, r, col, h)
                r += 1
                for _i2, _ik2 in enumerate(sorted(_bal_agg.keys())):
                    _agg2 = _bal_agg[_ik2]
                    _sr2 = ', '.join(str(s) for s in sorted(set(_agg2['sr_ids'])))
                    _hs2 = _agg2['hs_code']
                    _de2 = _agg2['description'] or _ik2
                    _bq2 = _agg2['qty']
                    _tq2 = _agg2['total_qty']
                    _cond2 = _agg2.get('condition_type') or ''
                    _rf2 = None if _i2 % 2 == 0 else ALT_FILL
                    _name_cell = _cell(ws, r, 1, _ik2, fill=_rf2)
                    _cell(ws, r, 2, _sr2, fill=_rf2, align='center')
                    _cell(ws, r, 3, _hs2, fill=_rf2)
                    _cell(ws, r, 4, _de2, fill=_rf2)
                    _cell(ws, r, 5, _tq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 6, _bq2, fill=_rf2, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 7, _agg2.get('plan_qty', 0.0), fill=_rf2, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 8, _agg2.get('plan_cif', 0.0), fill=_rf2, align='right', num_fmt='#,##0.00')
                    # Colour the Item Name cell by License Marking so the
                    # Excel matches the ConditionBadge palette in the UI.
                    _annotate_e5_item(_name_cell, _cond2)
                    r += 1

            r += 1
            _cell(ws, r, 1, '', fill=TOTAL_FILL)
            _cell(ws, r, 2, '', fill=TOTAL_FILL)
            _cell(ws, r, 3, '', fill=TOTAL_FILL)
            _cell(ws, r, 4, 'TOTAL ALLOCATED CIF $', fill=TOTAL_FILL, bold=True, align='right')
            _e5_total_cell = _cell(ws, r, 5, _e5_planned, fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _util_return['cell_refs']['total_planned'] = _e5_total_cell.coordinate
            r += 1
            # "10% Balance" displayed in the bulk summary uses the
            # licence's canonical E5 10% restriction figure
            # (`get_per_cif().tenRestriction`) — falls back to the local
            # condition_pool value, then to 10% of the licence credit.
            try:
                _per_cif = license_obj.get_per_cif() or {}
            except Exception:
                _per_cif = {}
            _ten_balance = _per_cif.get('tenRestriction')
            if _ten_balance is None or _ten_balance == 0:
                _ten_balance = _pool_10
            _util_return.update({
                'norm_type': 'E5', 'planned': _e5_planned_per_cat,
                'qty_per_cat': _e5_qty,
                'total_planned': _e5_planned,
                'categories': list(_E5_CATS_ORDERED),
                'pool_10': float(_ten_balance or 0),
                'condition_per_cat': dict(_e5_cond_per_cat),
            })
        elif _is_e132:
            # E132 planning classification (services/e132_plan.py). Renders the
            # per-licence planning table (computed above as `_e132_plan`) and tags
            # `_util_return` with the per-planning-item aggregates so the
            # cross-licence "Utilization Planning Summary" sheet gets its E132
            # section alongside E1 and E5.
            _e132_tot_qty = 0.0
            _e132_tot_val = 0.0
            _e132_cell_refs = {}   # planning item -> {qty, unit_price, value} coords
            _e132_total_ref = None  # coord of the per-licence TOTAL planning-value cell
            if not _e132_plan['items']:
                ws.merge_cells(f'A{r}:E{r}')
                _nm = ws[f'A{r}']
                _nm.value = 'No applicable E132 planning item matched the balance items.'
                _nm.font = Font(bold=True, size=9)
                _nm.alignment = Alignment(horizontal='center', vertical='center')
                r += 1
            else:
                for col, h in enumerate(['Planning Item', 'Total Qty', 'Unit Price ($)', 'Planning Value ($)', 'Source Records'], 1):
                    _hdr(ws, r, col, h)
                r += 1
                _e132_ds = r
                for _idx, _pi in enumerate(_e132_plan['items']):
                    _rf = None if _idx % 2 == 0 else ALT_FILL
                    _price = _pi['unit_price']
                    _val = _pi['planning_value']
                    _cell(ws, r, 1, _pi['planning_item_name'], fill=_rf, bold=True)
                    _qc = _cell(ws, r, 2, float(_pi['total_quantity']), fill=_rf, align='right', num_fmt='#,##0.00')
                    _uc = _cell(ws, r, 3, (float(_price) if _price is not None else 'TBD'), fill=_rf, align='right', num_fmt='#,##0.00')
                    _vc = _cell(ws, r, 4, (float(_val) if _val is not None else 'TBD'), fill=_rf, align='right', num_fmt='#,##0.00')
                    _cell(ws, r, 5, _pi['num_source_records'], fill=_rf, align='center')
                    # Capture coords so the cross-licence summary references these
                    # cells (edit the per-licence sheet → summary updates live).
                    _e132_cell_refs[_pi['planning_item_name']] = {
                        'qty': _qc.coordinate, 'unit_price': _uc.coordinate, 'value': _vc.coordinate,
                    }
                    _e132_tot_qty += float(_pi['total_quantity'])
                    _e132_tot_val += float(_val) if _val is not None else 0.0
                    r += 1
                _e132_de = r - 1
                # TOTAL = live SUM of the column so it always matches the (capped)
                # cells above and recalculates if any are edited.
                _cell(ws, r, 1, 'TOTAL', fill=TOTAL_FILL, bold=True)
                _cell(ws, r, 2, f'=SUM(B{_e132_ds}:B{_e132_de})', fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 3, '', fill=TOTAL_FILL)
                _tvc = _cell(ws, r, 4, f'=SUM(D{_e132_ds}:D{_e132_de})', fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
                _e132_total_ref = _tvc.coordinate
                _cell(ws, r, 5, '', fill=TOTAL_FILL)
                r += 1
                if _e132_plan['exceptions']:
                    ws.merge_cells(f'A{r}:E{r}')
                    _ex = ws[f'A{r}']
                    _ex.value = (f"{len(_e132_plan['exceptions'])} balance item(s) matched no E132 "
                                 f"planning rule and are excluded (see exception report).")
                    _ex.font = Font(italic=True, size=8, color="C00000")
                    _ex.alignment = Alignment(horizontal='left', vertical='center')
                    r += 1

            _util_return.update({
                'norm_type': 'E132',
                'e132_per_item': {
                    _pi['planning_item_name']: {
                        'qty': float(_pi['total_quantity']),
                        'value': (float(_pi['planning_value']) if _pi['planning_value'] is not None else None),
                        'unit_price': (float(_pi['unit_price']) if _pi['unit_price'] is not None else None),
                    }
                    for _pi in _e132_plan['items']
                },
                'e132_total_value': _e132_tot_val,
                'e132_cell_refs': _e132_cell_refs,
                'e132_total_value_ref': _e132_total_ref,
            })
        else:
            from apps.license.utils.condition_excel import annotate_cell as _annotate_cond
            BAL_COLS = ['HSN Code', 'Item Name', 'Bal Qty', 'Unit Price', 'CIF FC', 'Cond', 'Plan Qty', 'Plan CIF']
            for col, h in enumerate(BAL_COLS, 1):
                _hdr(ws, r, col, h)
            r += 1

            for idx, item_key in enumerate(sorted(_bal_agg.keys())):
                b_qty = _bal_agg[item_key]['qty']
                cond = _bal_agg[item_key].get('condition_type') or ''
                if cond in _cond_pools:
                    # Shared pool for this %-condition, capped at licence balance.
                    b_cif = float(min(_cond_pools[cond], _Dec(str(_license_balance))))
                else:
                    # AU or blank: full licence balance is available.
                    b_cif = _license_balance

                unit_price = b_cif / b_qty if b_qty else 0.0
                desc = _bal_agg[item_key]['description'] or item_key
                hs   = _bal_agg[item_key]['hs_code']
                row_fill = None if idx % 2 == 0 else ALT_FILL

                hs_cell = _cell(ws, r, 1, hs, fill=row_fill)
                _cell(ws, r, 2, desc,       fill=row_fill)
                _cell(ws, r, 3, b_qty,      fill=row_fill, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 4, unit_price, fill=row_fill, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 5, b_cif,      fill=row_fill, align='right', num_fmt='#,##0.00')
                cond_cell = _cell(ws, r, 6, cond, fill=row_fill, align='center', bold=True)
                _cell(ws, r, 7, _bal_agg[item_key].get('plan_qty', 0.0), fill=row_fill, align='right', num_fmt='#,##0.00')
                _cell(ws, r, 8, _bal_agg[item_key].get('plan_cif', 0.0), fill=row_fill, align='right', num_fmt='#,##0.00')
                # When a licence condition is set on this item, paint the
                # HSN and Cond cells with the same colour used in the UI
                # badges so the restriction is visible at a glance.
                _annotate_cond(hs_cell, cond)
                _annotate_cond(cond_cell, cond)
                r += 1

        # Per-item licence conditions (AU / 2% / 3% / 5% / 10%) — always
        # rendered when at least one item carries a condition, regardless
        # of norm type. Sits below the Utilization / Summary block.
        _items_with_cond = [
            _it for _it in license_obj.import_license.all()
            if _it.condition_type
        ]
        if _items_with_cond:
            from apps.license.utils.condition_excel import annotate_cell as _annotate_per_item
            r += 1
            ws.merge_cells(f'A{r}:E{r}')
            _ich = ws[f'A{r}']
            _ich.value = 'Item-level Licence Conditions'
            _ich.fill = HDR_FILL; _ich.font = Font(bold=True, color="FFFFFF", size=10)
            _ich.alignment = Alignment(horizontal='center', vertical='center')
            r += 1
            for col, h in enumerate(['Sr No', 'HSN Code', 'Item Name', 'Description', 'Condition'], 1):
                _hdr(ws, r, col, h)
            r += 1
            for _it in sorted(_items_with_cond, key=lambda x: x.serial_number or 0):
                _names = ', '.join([i.name for i in _it.items.all()]) if _it.items.exists() else '-'
                _hs = str(_it.hs_code.hs_code if _it.hs_code else '-')
                sr_cell = _cell(ws, r, 1, _it.serial_number or '-', align='center', bold=True)
                _cell(ws, r, 2, _hs)
                _cell(ws, r, 3, _names)
                _cell(ws, r, 4, _it.description or '-')
                cond_cell = _cell(ws, r, 5, _it.condition_type, align='center', bold=True)
                _annotate_per_item(sr_cell, _it.condition_type)
                _annotate_per_item(cond_cell, _it.condition_type)
                r += 1

        ws.column_dimensions['A'].width = 14
        ws.column_dimensions['B'].width = 14
        ws.column_dimensions['C'].width = 40
        ws.column_dimensions['D'].width = 22
        ws.column_dimensions['E'].width = 25
        ws.column_dimensions['F'].width = 28
        ws.column_dimensions['G'].width = 14
        ws.column_dimensions['H'].width = 14
        ws.column_dimensions['I'].width = 16
        ws.freeze_panes = 'A2'
        return _util_return

    def _norm_sort_key(lic):
        norms = list(lic.export_license.values_list('norm_class__norm_class', flat=True))
        norm_str = ', '.join(sorted(str(n) for n in norms if n)) or 'ZZZ'
        # Group order: E1 first, E5 second, rest alphabetically
        if any('E1' in str(n) and 'E126' not in str(n) and 'E132' not in str(n) for n in norms if n):
            return ('0_E1', norm_str)
        if any(str(n).strip() == 'E5' for n in norms if n):
            return ('1_E5', norm_str)
        return ('2_' + norm_str, norm_str)

    sorted_licenses = sorted(licenses, key=_norm_sort_key)

    _util_summaries = []
    for license_obj in sorted_licenses:
        _util_summaries.append(_write_license_sheet(wb, license_obj))

    # ── Create Utilization Planning Summary as first sheet ─────────────────
    from apps.license.services.e1_plan import E1_CATS as _E1_CATS_ORDERED_SUMM
    from apps.license.services.e5_plan import E5_CATS as _E5_CATS_ORDERED_SUMM
    from apps.license.utils.condition_excel import annotate_cell as _annotate_summary
    _E1_CATS_LABELS = list(_E1_CATS_ORDERED_SUMM)
    _E5_CATS_LABELS = list(_E5_CATS_ORDERED_SUMM)
    _e1_rows = [s for s in _util_summaries if s['norm_type'] == 'E1']
    _e5_rows = [s for s in _util_summaries if s['norm_type'] == 'E5']
    _e132_rows = [s for s in _util_summaries if s['norm_type'] == 'E132']
    _other_rows = [s for s in _util_summaries if s['norm_type'] == 'other']

    _sw = wb.create_sheet(title="Utilization Planning Summary")
    wb.move_sheet(_sw, offset=-(len(wb.worksheets) - 1))

    _sr = 1

    def _shdr(ws, row, col, value, span=1):
        c = ws.cell(row=row, column=col, value=value)
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        return c

    def _scell(ws, row, col, value, fill=None, bold=False, align='left', num_fmt=None):
        c = ws.cell(row=row, column=col, value=value)
        if fill: c.fill = fill
        c.font = BOLD if bold else NORM
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        if num_fmt: c.number_format = num_fmt
        return c

    # Fixed summary columns:
    #   1=Sr No (global counter), 2=License No, 3=License Date, 4=Expiry,
    #   5=Exporter, 6=Balance CIF, 7=Total CIF. Then category quantity/CIF pairs.
    _FIXED_SUMMARY_COLS = 7
    # Each category occupies 3 sub-columns: Bal Qty, Unit Price, Planned CIF ($).
    # E5 inserts an extra single "10% Balance" column right after the first
    # category (DIETARY FIBRE), so the E5 total/waste columns shift by +1.
    _CAT_START_COL = _FIXED_SUMMARY_COLS + 1
    _E1_TOTAL_COL  = _FIXED_SUMMARY_COLS + len(_E1_CATS_LABELS) * 3 + 1
    _E1_WASTE_COL  = _E1_TOTAL_COL + 1
    _E5_POOL10_COL = _CAT_START_COL + 3   # one extra column between cat 0 (DF) and cat 1
    _E5_TOTAL_COL  = _FIXED_SUMMARY_COLS + len(_E5_CATS_LABELS) * 3 + 1 + 1
    _E5_WASTE_COL  = _E5_TOTAL_COL + 1

    def _e5_cat_col(ci):
        """Start column for E5 category index `ci`. Categories after DIETARY
        FIBRE (ci > 0) are pushed right by 1 to make room for the inserted
        '10% Balance' column."""
        return _CAT_START_COL + ci * 3 + (1 if ci > 0 else 0)
    # Other-licenses section has IEC at col 8 and Port at col 9; the E132 section
    # spans 26 columns (7 fixed + 6 planning items × 3 + Total Planning Value).
    _MAX_COL = max(_E1_WASTE_COL, _E5_WASTE_COL, 26)

    # Global Sr No counter, shared across E1 / E5 / Other sections
    _global_sr = [0]

    WASTE_FILL = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")

    def _merge_hdr(ws, r, c1, c2, value, fill_color="1F4E79"):
        ws.merge_cells(f'{_gcl(c1)}{r}:{_gcl(c2)}{r}')
        c = ws[f'{_gcl(c1)}{r}']
        c.value = value
        c.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.border = THIN_BORDER
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def _sheet_formula(row, cell_ref):
        if not cell_ref:
            return None
        sheet = (row.get('sheet_name') or row.get('lic_no') or '').replace("'", "''")
        return f"='{sheet}'!{cell_ref}"

    def _sum_formula(col, row1, row2):
        return f"=SUM({_gcl(col)}{row1}:{_gcl(col)}{row2})"

    # Title row
    _sw.merge_cells(f'A{_sr}:{_gcl(_MAX_COL)}{_sr}')
    _tc = _sw[f'A{_sr}']
    _tc.value = 'UTILIZATION PLANNING SUMMARY'
    _tc.fill = HDR_FILL; _tc.font = Font(bold=True, color="FFFFFF", size=12)
    _tc.alignment = Alignment(horizontal='center', vertical='center')
    _sr += 1

    # ── E1 section ────────────────────────────────────────────────────────
    if _e1_rows:
        _merge_hdr(_sw, _sr, 1, _E1_WASTE_COL, 'E1 NORM LICENSES', "2E75B6")
        _sr += 1

        _sw.merge_cells(f'A{_sr}:A{_sr+1}'); _shdr(_sw, _sr, 1, 'Sr No')
        _sw.merge_cells(f'B{_sr}:B{_sr+1}'); _shdr(_sw, _sr, 2, 'License No')
        _sw.merge_cells(f'C{_sr}:C{_sr+1}'); _shdr(_sw, _sr, 3, 'License Date')
        _sw.merge_cells(f'D{_sr}:D{_sr+1}'); _shdr(_sw, _sr, 4, 'License Expiry Date')
        _sw.merge_cells(f'E{_sr}:E{_sr+1}'); _shdr(_sw, _sr, 5, 'Total CIF $')
        _sw.merge_cells(f'F{_sr}:F{_sr+1}'); _shdr(_sw, _sr, 6, 'Balance CIF $')
        _sw.merge_cells(f'G{_sr}:G{_sr+1}'); _shdr(_sw, _sr, 7, 'Exporter Name')
        for _ci, _cat in enumerate(_E1_CATS_LABELS):
            _cc = _CAT_START_COL + _ci * 3
            _sw.merge_cells(f'{_gcl(_cc)}{_sr}:{_gcl(_cc+2)}{_sr}')
            _shdr(_sw, _sr, _cc, _cat)
        _sw.merge_cells(f'{_gcl(_E1_TOTAL_COL)}{_sr}:{_gcl(_E1_TOTAL_COL)}{_sr+1}')
        _shdr(_sw, _sr, _E1_TOTAL_COL, 'TOTAL PLANNED CIF $')
        _sw.merge_cells(f'{_gcl(_E1_WASTE_COL)}{_sr}:{_gcl(_E1_WASTE_COL)}{_sr+1}')
        _c = _sw.cell(row=_sr, column=_E1_WASTE_COL, value='Wastage $')
        _c.fill = WASTE_FILL; _c.font = Font(bold=True, size=9)
        _c.border = THIN_BORDER
        _c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        _sr += 1
        for _ci in range(len(_E1_CATS_LABELS)):
            _cc = _CAT_START_COL + _ci * 3
            _shdr(_sw, _sr, _cc,     'Bal Qty')
            _shdr(_sw, _sr, _cc + 1, 'Unit Price')
            _shdr(_sw, _sr, _cc + 2, 'Planned CIF ($)')
        _sr += 1

        _e1_tot = {'bal': 0.0, 'planned': 0.0, 'waste': 0.0,
                   'qty': {c: 0.0 for c in _E1_CATS_LABELS},
                   'cif': {c: 0.0 for c in _E1_CATS_LABELS}}
        _e1_data_start = _sr
        for _i, _row in enumerate(_e1_rows):
            _rf = None if _i % 2 == 0 else ALT_FILL
            _waste = _row['balance_cif'] - _row['total_planned']
            _refs = _row.get('cell_refs') or {}
            _ld = _row.get('license_date')
            _ed = _row.get('license_expiry_date')
            _ld_str = _ld.strftime('%d-%m-%Y') if _ld else '-'
            _ed_str = _ed.strftime('%d-%m-%Y') if _ed else '-'
            _global_sr[0] += 1
            _scell(_sw, _sr, 1, _global_sr[0], fill=_rf, bold=True, align='center')
            _scell(_sw, _sr, 2, _row['lic_no'], fill=_rf, bold=True)
            _scell(_sw, _sr, 3, _ld_str, fill=_rf, align='center')
            _scell(_sw, _sr, 4, _ed_str, fill=_rf, align='center')
            _scell(_sw, _sr, 5, _row.get('total_license_cif') or 0.0, fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 6, _sheet_formula(_row, _refs.get('balance_cif')) or _row['balance_cif'], fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 7, _row.get('exporter_name') or '-', fill=_rf)
            _e1_cond_map = _row.get('condition_per_cat') or {}
            for _ci, _cat in enumerate(_E1_CATS_LABELS):
                _cc = _CAT_START_COL + _ci * 3
                _q = _row['qty_per_cat'].get(_cat, 0.0)
                _p = _row['planned'].get(_cat, 0.0)
                _q_ref = (_refs.get('qty_per_cat') or {}).get(_cat)
                _p_ref = (_refs.get('planned') or {}).get(_cat)
                # Live unit-price formula off this row's Bal Qty (_cc) and
                # Planned CIF (_cc+2). Auto-updates if either changes.
                _q_col = _gcl(_cc)
                _p_col = _gcl(_cc + 2)
                _up_formula = f'=IF({_q_col}{_sr}=0,0,ROUNDDOWN({_p_col}{_sr}/{_q_col}{_sr},2))'
                _cq = _scell(_sw, _sr, _cc,     _sheet_formula(_row, _q_ref) or _q, fill=_rf, align='right', num_fmt='#,##0.00')
                _cu = _scell(_sw, _sr, _cc + 1, _up_formula,                         fill=_rf, align='right', num_fmt='#,##0.00')
                _cp = _scell(_sw, _sr, _cc + 2, _sheet_formula(_row, _p_ref) or _p, fill=_rf, align='right', num_fmt='#,##0.00')
                # Colour the triplet by the category's License Marking.
                _cat_cond = _e1_cond_map.get(_cat) or ''
                if _cat_cond:
                    _annotate_summary(_cq, _cat_cond)
                    _annotate_summary(_cu, _cat_cond)
                    _annotate_summary(_cp, _cat_cond)
                _e1_tot['qty'][_cat] += _q
                _e1_tot['cif'][_cat] += _p
            _scell(_sw, _sr, _E1_TOTAL_COL, _sheet_formula(_row, _refs.get('total_planned')) or _row['total_planned'], fill=_rf, bold=True, align='right', num_fmt='#,##0.00')
            _wc = _sw.cell(row=_sr, column=_E1_WASTE_COL, value=_sheet_formula(_row, _refs.get('wastage')) or _waste)
            _wc.fill = WASTE_FILL; _wc.font = Font(bold=True, size=9)
            _wc.border = THIN_BORDER; _wc.alignment = Alignment(horizontal='right', vertical='center')
            _wc.number_format = '#,##0.00'
            _e1_tot['bal']     += _row['balance_cif']
            _e1_tot['planned'] += _row['total_planned']
            _e1_tot['waste']   += _waste
            _sr += 1
        _e1_data_end = _sr - 1

        # E1 total row
        _scell(_sw, _sr, 1, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 2, 'TOTAL', fill=TOTAL_FILL, bold=True, align='center')
        _scell(_sw, _sr, 3, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 4, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 5, _sum_formula(5, _e1_data_start, _e1_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, 6, _sum_formula(6, _e1_data_start, _e1_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, 7, '', fill=TOTAL_FILL)
        for _ci, _cat in enumerate(_E1_CATS_LABELS):
            _cc = _CAT_START_COL + _ci * 3
            # Total-row unit price = SUM(Planned CIF) / SUM(Bal Qty),
            # referencing the live total cells on this same row.
            _q_col = _gcl(_cc)
            _p_col = _gcl(_cc + 2)
            _tot_up_formula = f'=IF({_q_col}{_sr}=0,0,ROUNDDOWN({_p_col}{_sr}/{_q_col}{_sr},2))'
            _scell(_sw, _sr, _cc,     _sum_formula(_cc, _e1_data_start, _e1_data_end),     fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, _cc + 1, _tot_up_formula,                                      fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, _cc + 2, _sum_formula(_cc + 2, _e1_data_start, _e1_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, _E1_TOTAL_COL, _sum_formula(_E1_TOTAL_COL, _e1_data_start, _e1_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _wt = _sw.cell(row=_sr, column=_E1_WASTE_COL, value=_sum_formula(_E1_WASTE_COL, _e1_data_start, _e1_data_end))
        _wt.fill = WASTE_FILL; _wt.font = Font(bold=True, size=9)
        _wt.border = THIN_BORDER; _wt.alignment = Alignment(horizontal='right', vertical='center')
        _wt.number_format = '#,##0.00'
        _sr += 2

    # ── E5 section ────────────────────────────────────────────────────────
    if _e5_rows:
        _merge_hdr(_sw, _sr, 1, _E5_WASTE_COL, 'E5 NORM LICENSES', "375623")
        _sr += 1

        _sw.merge_cells(f'A{_sr}:A{_sr+1}'); _shdr(_sw, _sr, 1, 'Sr No')
        _sw.merge_cells(f'B{_sr}:B{_sr+1}'); _shdr(_sw, _sr, 2, 'License No')
        _sw.merge_cells(f'C{_sr}:C{_sr+1}'); _shdr(_sw, _sr, 3, 'License Date')
        _sw.merge_cells(f'D{_sr}:D{_sr+1}'); _shdr(_sw, _sr, 4, 'License Expiry Date')
        _sw.merge_cells(f'E{_sr}:E{_sr+1}'); _shdr(_sw, _sr, 5, 'Total CIF $')
        _sw.merge_cells(f'F{_sr}:F{_sr+1}'); _shdr(_sw, _sr, 6, 'Balance CIF $')
        _sw.merge_cells(f'G{_sr}:G{_sr+1}'); _shdr(_sw, _sr, 7, 'Exporter Name')
        for _ci, _cat in enumerate(_E5_CATS_LABELS):
            _cc = _e5_cat_col(_ci)
            _sw.merge_cells(f'{_gcl(_cc)}{_sr}:{_gcl(_cc+2)}{_sr}')
            _shdr(_sw, _sr, _cc, _cat)
        # 10% Balance — single column wedged between DIETARY FIBRE and SWP.
        _sw.merge_cells(f'{_gcl(_E5_POOL10_COL)}{_sr}:{_gcl(_E5_POOL10_COL)}{_sr+1}')
        _shdr(_sw, _sr, _E5_POOL10_COL, '10% Balance')
        _sw.merge_cells(f'{_gcl(_E5_TOTAL_COL)}{_sr}:{_gcl(_E5_TOTAL_COL)}{_sr+1}')
        _shdr(_sw, _sr, _E5_TOTAL_COL, 'TOTAL ALLOCATED CIF $')
        _sw.merge_cells(f'{_gcl(_E5_WASTE_COL)}{_sr}:{_gcl(_E5_WASTE_COL)}{_sr+1}')
        _c = _sw.cell(row=_sr, column=_E5_WASTE_COL, value='Wastage $')
        _c.fill = WASTE_FILL; _c.font = Font(bold=True, size=9)
        _c.border = THIN_BORDER
        _c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        _sr += 1
        for _ci in range(len(_E5_CATS_LABELS)):
            _cc = _e5_cat_col(_ci)
            _shdr(_sw, _sr, _cc,     'Bal Qty')
            _shdr(_sw, _sr, _cc + 1, 'Unit Price')
            _shdr(_sw, _sr, _cc + 2, 'Planned CIF ($)')
        _sr += 1

        _e5_tot = {'bal': 0.0, 'planned': 0.0, 'waste': 0.0,
                   'qty': {c: 0.0 for c in _E5_CATS_LABELS},
                   'cif': {c: 0.0 for c in _E5_CATS_LABELS}}
        _e5_data_start = _sr
        for _i, _row in enumerate(_e5_rows):
            _rf = None if _i % 2 == 0 else ALT_FILL
            _waste = _row['balance_cif'] - _row['total_planned']
            _refs = _row.get('cell_refs') or {}
            _ld = _row.get('license_date')
            _ed = _row.get('license_expiry_date')
            _ld_str = _ld.strftime('%d-%m-%Y') if _ld else '-'
            _ed_str = _ed.strftime('%d-%m-%Y') if _ed else '-'
            _global_sr[0] += 1
            _scell(_sw, _sr, 1, _global_sr[0], fill=_rf, bold=True, align='center')
            _scell(_sw, _sr, 2, _row['lic_no'], fill=_rf, bold=True)
            _scell(_sw, _sr, 3, _ld_str, fill=_rf, align='center')
            _scell(_sw, _sr, 4, _ed_str, fill=_rf, align='center')
            _scell(_sw, _sr, 5, _row.get('total_license_cif') or 0.0, fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 6, _sheet_formula(_row, _refs.get('balance_cif')) or _row['balance_cif'], fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 7, _row.get('exporter_name') or '-', fill=_rf)
            _e5_cond_map = _row.get('condition_per_cat') or {}
            for _ci, _cat in enumerate(_E5_CATS_LABELS):
                _cc = _e5_cat_col(_ci)
                _q = _row['qty_per_cat'].get(_cat, 0.0)
                _p = _row['planned'].get(_cat, 0.0)
                _q_ref = (_refs.get('qty_per_cat') or {}).get(_cat)
                _p_ref = (_refs.get('planned') or {}).get(_cat)
                # Live unit price = ROUNDDOWN(Planned / Bal Qty, 2), guarded
                # against /0. Both source cells are pulled live from the
                # per-licence sheet via _sheet_formula, so the unit price
                # updates if the user edits either side.
                _q_col = _gcl(_cc)
                _p_col = _gcl(_cc + 2)
                _up_formula = f'=IF({_q_col}{_sr}=0,0,ROUNDDOWN({_p_col}{_sr}/{_q_col}{_sr},2))'
                _cq = _scell(_sw, _sr, _cc,     _sheet_formula(_row, _q_ref) or _q, fill=_rf, align='right', num_fmt='#,##0.00')
                _cu = _scell(_sw, _sr, _cc + 1, _up_formula,                         fill=_rf, align='right', num_fmt='#,##0.00')
                _cp = _scell(_sw, _sr, _cc + 2, _sheet_formula(_row, _p_ref) or _p, fill=_rf, align='right', num_fmt='#,##0.00')
                # Colour the triplet by the category's License Marking.
                _cat_cond = _e5_cond_map.get(_cat) or ''
                if _cat_cond:
                    _annotate_summary(_cq, _cat_cond)
                    _annotate_summary(_cu, _cat_cond)
                    _annotate_summary(_cp, _cat_cond)
                _e5_tot['qty'][_cat] += _q
                _e5_tot['cif'][_cat] += _p
            # 10% Balance — display-only; always painted with the 10% colour
            # since it literally represents the 10% restriction budget.
            _row_pool10 = _row.get('pool_10', 0.0)
            _pool10_cell = _scell(_sw, _sr, _E5_POOL10_COL, _row_pool10, fill=_rf, align='right', num_fmt='#,##0.00')
            _annotate_summary(_pool10_cell, '10%')
            _e5_tot.setdefault('pool_10', 0.0)
            _e5_tot['pool_10'] += _row_pool10
            _scell(_sw, _sr, _E5_TOTAL_COL, _sheet_formula(_row, _refs.get('total_planned')) or _row['total_planned'], fill=_rf, bold=True, align='right', num_fmt='#,##0.00')
            _wc = _sw.cell(row=_sr, column=_E5_WASTE_COL, value=_sheet_formula(_row, _refs.get('wastage')) or _waste)
            _wc.fill = WASTE_FILL; _wc.font = Font(bold=True, size=9)
            _wc.border = THIN_BORDER; _wc.alignment = Alignment(horizontal='right', vertical='center')
            _wc.number_format = '#,##0.00'
            _e5_tot['bal']     += _row['balance_cif']
            _e5_tot['planned'] += _row['total_planned']
            _e5_tot['waste']   += _waste
            _sr += 1
        _e5_data_end = _sr - 1

        # E5 total row
        _scell(_sw, _sr, 1, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 2, 'TOTAL', fill=TOTAL_FILL, bold=True, align='center')
        _scell(_sw, _sr, 3, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 4, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 5, _sum_formula(5, _e5_data_start, _e5_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, 6, _sum_formula(6, _e5_data_start, _e5_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, 7, '', fill=TOTAL_FILL)
        for _ci, _cat in enumerate(_E5_CATS_LABELS):
            _cc = _e5_cat_col(_ci)
            # Total-row unit price = SUM(Planned CIF) / SUM(Bal Qty),
            # referencing the live total cells on this same row.
            _q_col = _gcl(_cc)
            _p_col = _gcl(_cc + 2)
            _tot_up_formula = f'=IF({_q_col}{_sr}=0,0,ROUNDDOWN({_p_col}{_sr}/{_q_col}{_sr},2))'
            _scell(_sw, _sr, _cc,     _sum_formula(_cc, _e5_data_start, _e5_data_end),     fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, _cc + 1, _tot_up_formula,                                      fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, _cc + 2, _sum_formula(_cc + 2, _e5_data_start, _e5_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        # 10% Balance total — sum of per-license pool values; painted with
        # the 10% colour to stay consistent with the data rows above.
        _pool10_tot_cell = _scell(_sw, _sr, _E5_POOL10_COL,
               _sum_formula(_E5_POOL10_COL, _e5_data_start, _e5_data_end),
               fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _annotate_summary(_pool10_tot_cell, '10%')
        _scell(_sw, _sr, _E5_TOTAL_COL, _sum_formula(_E5_TOTAL_COL, _e5_data_start, _e5_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _wt = _sw.cell(row=_sr, column=_E5_WASTE_COL, value=_sum_formula(_E5_WASTE_COL, _e5_data_start, _e5_data_end))
        _wt.fill = WASTE_FILL; _wt.font = Font(bold=True, size=9)
        _wt.border = THIN_BORDER; _wt.alignment = Alignment(horizontal='right', vertical='center')
        _wt.number_format = '#,##0.00'
        _sr += 2

    # ── E132 section ───────────────────────────────────────────────────────
    # E132 planning classifies each item into one of six planning items (Yeast /
    # Cheese Cream Butter & Fats / PKO / RBD / Aluminium Foil / Milk). Like E1/E5
    # the summary shows a per-item Qty / Unit Price / Planning Value column group,
    # plus TOTAL PLANNING VALUE, one row per licence with a TOTAL row. Milk's price
    # is To-Be-Defined → shown as 'TBD' and excluded from value sums.
    if _e132_rows:
        from apps.license.services.e132_plan import PLANNING_ORDER as _E132_ITEMS
        _E132_LABELS = list(_E132_ITEMS)   # 6 planning items in priority order
        _E132_CAT_START = _FIXED_SUMMARY_COLS + 1                            # 8
        _E132_TOTAL_COL = _FIXED_SUMMARY_COLS + len(_E132_LABELS) * 3 + 1    # 26

        _merge_hdr(_sw, _sr, 1, _E132_TOTAL_COL, 'E132 NORM LICENSES', "7030A0")
        _sr += 1
        _sw.merge_cells(f'A{_sr}:A{_sr+1}'); _shdr(_sw, _sr, 1, 'Sr No')
        _sw.merge_cells(f'B{_sr}:B{_sr+1}'); _shdr(_sw, _sr, 2, 'License No')
        _sw.merge_cells(f'C{_sr}:C{_sr+1}'); _shdr(_sw, _sr, 3, 'License Date')
        _sw.merge_cells(f'D{_sr}:D{_sr+1}'); _shdr(_sw, _sr, 4, 'License Expiry Date')
        _sw.merge_cells(f'E{_sr}:E{_sr+1}'); _shdr(_sw, _sr, 5, 'Total CIF $')
        _sw.merge_cells(f'F{_sr}:F{_sr+1}'); _shdr(_sw, _sr, 6, 'Balance CIF $')
        _sw.merge_cells(f'G{_sr}:G{_sr+1}'); _shdr(_sw, _sr, 7, 'Exporter Name')
        for _ci, _cat in enumerate(_E132_LABELS):
            _cc = _E132_CAT_START + _ci * 3
            _sw.merge_cells(f'{_gcl(_cc)}{_sr}:{_gcl(_cc+2)}{_sr}')
            _shdr(_sw, _sr, _cc, _cat)
        _sw.merge_cells(f'{_gcl(_E132_TOTAL_COL)}{_sr}:{_gcl(_E132_TOTAL_COL)}{_sr+1}')
        _shdr(_sw, _sr, _E132_TOTAL_COL, 'TOTAL PLANNING VALUE $')
        _sr += 1
        for _ci in range(len(_E132_LABELS)):
            _cc = _E132_CAT_START + _ci * 3
            _shdr(_sw, _sr, _cc,     'Qty')
            _shdr(_sw, _sr, _cc + 1, 'Unit Price')
            _shdr(_sw, _sr, _cc + 2, 'Planning Value ($)')
        _sr += 1

        _e132_data_start = _sr
        for _i, _row in enumerate(_e132_rows):
            _rf = None if _i % 2 == 0 else ALT_FILL
            _refs = _row.get('cell_refs') or {}
            _ld = _row.get('license_date'); _ed = _row.get('license_expiry_date')
            _ld_str = _ld.strftime('%d-%m-%Y') if _ld else '-'
            _ed_str = _ed.strftime('%d-%m-%Y') if _ed else '-'
            _per_item = _row.get('e132_per_item') or {}
            _refs132 = _row.get('e132_cell_refs') or {}
            _global_sr[0] += 1
            _scell(_sw, _sr, 1, _global_sr[0], fill=_rf, bold=True, align='center')
            _scell(_sw, _sr, 2, _row['lic_no'], fill=_rf, bold=True)
            _scell(_sw, _sr, 3, _ld_str, fill=_rf, align='center')
            _scell(_sw, _sr, 4, _ed_str, fill=_rf, align='center')
            _scell(_sw, _sr, 5, _row.get('total_license_cif') or 0.0, fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 6, _sheet_formula(_row, _refs.get('balance_cif')) or _row['balance_cif'], fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 7, _row.get('exporter_name') or '-', fill=_rf)
            for _ci, _cat in enumerate(_E132_LABELS):
                _cc = _E132_CAT_START + _ci * 3
                _pi = _per_item.get(_cat) or {}
                _present = _cat in _per_item
                _q = _pi.get('qty', 0.0)
                _up = _pi.get('unit_price')   # float, or None for To-Be-Defined (Milk)
                _val = _pi.get('value')
                _up_cell = _up if _up is not None else ('TBD' if _present else '')
                _val_cell = _val if _val is not None else ('TBD' if _present else 0.0)
                # Reference the per-licence sheet cells (edit there → summary
                # updates), falling back to the static value when no ref exists.
                _iref = _refs132.get(_cat) or {}
                _scell(_sw, _sr, _cc,     _sheet_formula(_row, _iref.get('qty')) or _q, fill=_rf, align='right', num_fmt='#,##0.00')
                _scell(_sw, _sr, _cc + 1, _sheet_formula(_row, _iref.get('unit_price')) or _up_cell, fill=_rf, align='right', num_fmt='#,##0.00')
                _scell(_sw, _sr, _cc + 2, _sheet_formula(_row, _iref.get('value')) or _val_cell, fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, _E132_TOTAL_COL, _sheet_formula(_row, _row.get('e132_total_value_ref')) or (_row.get('e132_total_value') or 0.0), fill=_rf, bold=True, align='right', num_fmt='#,##0.00')
            _sr += 1
        _e132_data_end = _sr - 1

        # E132 total row
        _scell(_sw, _sr, 1, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 2, 'TOTAL', fill=TOTAL_FILL, bold=True, align='center')
        _scell(_sw, _sr, 3, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 4, '', fill=TOTAL_FILL)
        _scell(_sw, _sr, 5, _sum_formula(5, _e132_data_start, _e132_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, 6, _sum_formula(6, _e132_data_start, _e132_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, 7, '', fill=TOTAL_FILL)
        for _ci in range(len(_E132_LABELS)):
            _cc = _E132_CAT_START + _ci * 3
            # SUM ignores 'TBD' text cells, so Milk's undefined value is excluded.
            _scell(_sw, _sr, _cc,     _sum_formula(_cc, _e132_data_start, _e132_data_end),     fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, _cc + 1, '',                                                       fill=TOTAL_FILL)
            _scell(_sw, _sr, _cc + 2, _sum_formula(_cc + 2, _e132_data_start, _e132_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _scell(_sw, _sr, _E132_TOTAL_COL, _sum_formula(_E132_TOTAL_COL, _e132_data_start, _e132_data_end), fill=TOTAL_FILL, bold=True, align='right', num_fmt='#,##0.00')
        _sr += 2

    # ── Other licenses section ─────────────────────────────────────────────
    # Layout chosen to share column widths with the E1/E5 tables above:
    #   A=License No, B=License Date, C=License Expiry Date,
    #   D=Exporter, E=Balance CIF, F=IEC, G=Port.
    if _other_rows:
        _merge_hdr(_sw, _sr, 1, 9, 'OTHER LICENSES', "595959")
        _sr += 1
        _shdr(_sw, _sr, 1, 'Sr No')
        _shdr(_sw, _sr, 2, 'License No')
        _shdr(_sw, _sr, 3, 'License Date')
        _shdr(_sw, _sr, 4, 'License Expiry Date')
        _shdr(_sw, _sr, 5, 'Total CIF $')
        _shdr(_sw, _sr, 6, 'Balance CIF $')
        _shdr(_sw, _sr, 7, 'Exporter Name')
        _shdr(_sw, _sr, 8, 'IEC')
        _shdr(_sw, _sr, 9, 'Port')
        _sr += 1
        for _i, _row in enumerate(_other_rows):
            _rf = None if _i % 2 == 0 else ALT_FILL
            _refs = _row.get('cell_refs') or {}
            _ld = _row.get('license_date')
            _ed = _row.get('license_expiry_date')
            _ld_str = _ld.strftime('%d-%m-%Y') if _ld else '-'
            _ed_str = _ed.strftime('%d-%m-%Y') if _ed else '-'
            _global_sr[0] += 1
            _scell(_sw, _sr, 1, _global_sr[0], fill=_rf, bold=True, align='center')
            _scell(_sw, _sr, 2, _row['lic_no'], fill=_rf, bold=True)
            _scell(_sw, _sr, 3, _ld_str, fill=_rf, align='center')
            _scell(_sw, _sr, 4, _ed_str, fill=_rf, align='center')
            _scell(_sw, _sr, 5, _row.get('total_license_cif') or 0.0, fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 6, _sheet_formula(_row, _refs.get('balance_cif')) or _row['balance_cif'], fill=_rf, align='right', num_fmt='#,##0.00')
            _scell(_sw, _sr, 7, _row.get('exporter_name') or '-', fill=_rf)
            _scell(_sw, _sr, 8, _row.get('iec') or '-', fill=_rf, align='center')
            _scell(_sw, _sr, 9, _row.get('port_code') or '-', fill=_rf, align='center')
            _sr += 1

    # Column widths for summary sheet
    _sw.column_dimensions['A'].width = 6   # Sr No
    _sw.column_dimensions['B'].width = 18  # License No
    _sw.column_dimensions['C'].width = 14  # License Date
    _sw.column_dimensions['D'].width = 18  # Expiry Date
    _sw.column_dimensions['E'].width = 16  # Balance CIF
    _sw.column_dimensions['F'].width = 16  # Total CIF
    _sw.column_dimensions['G'].width = 28  # Exporter
    for _col_idx in range(8, _MAX_COL + 1):
        _sw.column_dimensions[_gcl(_col_idx)].width = 14
    _sw.freeze_panes = 'A4'

    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True

    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="bulk_license_summary.xlsx"'
    return response
