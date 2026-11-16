"""Worksheet writers (Financial Ledger, Customs Ledger, Timeline) for the licence
balance workbook. Split out of ``license_balance_excel.py``; behaviour unchanged.
"""


def _write_financial_ledger_sheet(wb, rows, summary):
    """
    Adds a "Financial Ledger" worksheet — the same bank-statement rows and
    Financial Summary / Reconciliation Summary numbers as the PDF's Licence
    Financial Ledger section and the workspace UI, all read from
    `LicenseBalanceLedgerBuilder` so the three surfaces can never disagree.

    `rows`/`summary` are `LicenseBalanceLedgerBuilder.build_financial_ledger()`'s
    own return value — computed ONCE by the caller (`build_balance_excel`)
    and passed in here; this function does no calculation of its own.
    Hierarchical "trade" (Licence Trade Sold) rows' `children` (one per
    underlying BOE allocation, when the sale is matched to one) are
    rendered immediately below their parent, informational only (blank
    Credit/Debit/Running Balance — same convention as the PDF's
    `_build_financial_ledger_elements`), and grouped via openpyxl's native
    row outlining (`outline_level`) so they can be collapsed/expanded in
    Excel itself — `summaryBelow=False` puts the collapse control on the
    parent row since the parent sits ABOVE its children here, not below.

    Inserted as the FIRST sheet in the workbook.
    """
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    ws = wb.create_sheet("Financial Ledger", 0)
    ws.sheet_properties.outlinePr.summaryBelow = False

    HDR_FILL = PatternFill(start_color="1A1A1A", end_color="1A1A1A", fill_type="solid")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
    ROW_FILLS = {
        'opening': PatternFill(start_color="1A5276", end_color="1A5276", fill_type="solid"),
        'boe': PatternFill(start_color="EAFAF1", end_color="EAFAF1", fill_type="solid"),
        'allotment': PatternFill(start_color="FEF9E7", end_color="FEF9E7", fill_type="solid"),
        'trade_purchase': PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid"),
        'trade': PatternFill(start_color="F4ECF7", end_color="F4ECF7", fill_type="solid"),
        'final': PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid"),
    }
    CHILD_FILL = PatternFill(start_color="F4F6F7", end_color="F4F6F7", fill_type="solid")
    CHILD_FONT = Font(color="555555", size=9)
    MISMATCH_FILL = PatternFill(start_color="F5B7B1", end_color="F5B7B1", fill_type="solid")
    THIN = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    def fmt_date(d):
        return d.strftime('%d-%m-%Y') if d else '-'

    ws.merge_cells('A1:P1')
    ws['A1'] = 'LICENCE FINANCIAL LEDGER'
    ws['A1'].font = Font(bold=True, color="FFFFFF", size=14)
    ws['A1'].fill = HDR_FILL
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 26

    header_row_num = 2
    warning = summary['missing_purchase_warning']
    if warning['show_warning']:
        # Shown instead of a fabricated Opening Balance row when a Sale
        # exists with no matching Purchase — same message as the UI/PDF.
        ws.merge_cells('A2:P2')
        ws['A2'] = f"⚠ {warning['message']}"
        ws['A2'].font = Font(bold=True, color="7D6608", size=10)
        ws['A2'].fill = PatternFill(start_color="FEF9E7", end_color="FEF9E7", fill_type="solid")
        ws['A2'].alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[2].height = 20
        header_row_num = 3

    headers = [
        'Sr', 'Txn Date', 'Txn Type', 'Doc Number', 'BOE Number', 'BOE Date',
        'Company (Importer)', 'Item Name', 'Invoice(s)', 'Qty',
        'BOE CIF (USD)', 'BOE INR', 'Credit (USD)', 'Debit (USD)',
        'Running Balance (USD)', 'Remarks',
    ]
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=header_row_num, column=col, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.border = THIN
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    r = header_row_num + 1
    for row_data in rows:
        fill = MISMATCH_FILL if row_data.get('mismatched') else ROW_FILLS.get(row_data['row_kind'])
        font_white = row_data['row_kind'] in ('opening', 'final') and not row_data.get('mismatched')
        values = [
            row_data['sr'],
            fmt_date(row_data['date']),
            row_data['type'],
            row_data['document_number'] or '-',
            row_data['boe_number'] or '-',
            row_data.get('boe_date_display') or fmt_date(row_data['boe_date']),
            row_data['company'] or '-',
            row_data['item_name'] or '-',
            ', '.join(row_data['invoice_numbers']) if row_data['invoice_numbers'] else '-',
            float(row_data['qty']) if row_data['qty'] is not None else '-',
            float(row_data['cif_usd']) if row_data['cif_usd'] is not None else '-',
            float(row_data['cif_inr']) if row_data['cif_inr'] is not None else '-',
            float(row_data['credit']) if row_data['credit'] else '-',
            float(row_data['debit']) if row_data['debit'] else '-',
            float(row_data['running_balance']),
            row_data['remarks'],
        ]
        for col, val in enumerate(values, 1):
            c = ws.cell(row=r, column=col, value=val)
            c.border = THIN
            if fill:
                c.fill = fill
            if font_white:
                c.font = Font(color="FFFFFF", bold=True)
            if col in (10, 11, 12, 13, 14, 15) and isinstance(val, float):
                c.number_format = '#,##0.00'
                c.alignment = Alignment(horizontal='right')
            else:
                c.alignment = Alignment(horizontal='left', wrap_text=True)
        r += 1

        # Hierarchy — one row per underlying BOE allocation under a
        # consolidated "BOE Allocation" parent row (see `build_financial_
        # ledger`'s docstring). Informational only: Credit/Debit/Running
        # Balance stay blank, the parent row above already carries the
        # accounting impact. `outline_level = 1` groups these rows under
        # their parent for Excel's native collapse/expand.
        for child in (row_data.get('children') or []):
            child_values = [
                '', '', f"↳ {child.get('type', '-')}", '',
                child.get('boe_number') or '-', fmt_date(child.get('boe_date')),
                child.get('company') or '-', child.get('item_name') or '-',
                ', '.join(child.get('invoice_numbers') or []) if child.get('invoice_numbers') else '-',
                float(child['qty']) if child.get('qty') is not None else '-',
                float(child['cif_usd']) if child.get('cif_usd') is not None else '-',
                float(child['cif_inr']) if child.get('cif_inr') is not None else '-',
                '-', '-', '-',
                f"{child.get('status', '-')} — {child.get('remarks', '-')}",
            ]
            for col, val in enumerate(child_values, 1):
                c = ws.cell(row=r, column=col, value=val)
                c.border = THIN
                c.fill = CHILD_FILL
                c.font = CHILD_FONT
                if col == 3:
                    c.alignment = Alignment(horizontal='left', wrap_text=True, indent=2)
                elif col in (10, 11, 12) and isinstance(val, float):
                    c.number_format = '#,##0.00'
                    c.alignment = Alignment(horizontal='right')
                else:
                    c.alignment = Alignment(horizontal='left', wrap_text=True)
            ws.row_dimensions[r].outline_level = 1
            r += 1

    r += 1
    ws.merge_cells(f'A{r}:P{r}')
    ws[f'A{r}'] = 'FINANCIAL SUMMARY & RECONCILIATION'
    ws[f'A{r}'].font = Font(bold=True, color="FFFFFF", size=11)
    ws[f'A{r}'].fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
    ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    summary_rows = [
        ('Original Licence CIF', summary['opening_balance']),
        ('Total BOE Debits', summary['total_boe_debit']),
    ]
    if summary.get('total_invoice_allocation_debit', 0) > 0:
        summary_rows.append(('Total Invoice Allocation Debits', summary['total_invoice_allocation_debit']))
    summary_rows.append(('Outstanding Active Allotments', summary['total_allotment_debit']))
    if summary.get('total_purchase_credit', 0) > 0:
        summary_rows.append(('Total Purchase Credits', summary['total_purchase_credit']))
    if summary['total_trade_debit'] > 0:
        summary_rows.append(('Total Trade (Sold) Debits', summary['total_trade_debit']))
    summary_rows += [
        ('Current Available Balance', summary['computed_balance']),
        ('Licence Balance Engine', summary['engine_balance']),
        ('Difference', summary['difference']),
        ('Tolerance', summary['tolerance']),
    ]
    for label, value in summary_rows:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        vcell = ws.cell(row=r, column=2, value=float(value))
        vcell.number_format = '#,##0.00'
        r += 1

    r += 1
    status_text = 'FINANCIAL RECONCILIATION FAILED' if summary['mismatched'] else 'MATCHED'
    status_color = 'C0392B' if summary['mismatched'] else '1E8449'
    ws.merge_cells(f'A{r}:P{r}')
    ws[f'A{r}'] = status_text
    ws[f'A{r}'].font = Font(bold=True, color=status_color, size=12)
    ws[f'A{r}'].alignment = Alignment(horizontal='center')

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 16
    ws.column_dimensions['D'].width = 16
    ws.column_dimensions['E'].width = 14
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 24
    ws.column_dimensions['H'].width = 22
    ws.column_dimensions['I'].width = 20
    for col in ['J', 'K', 'L', 'M', 'N', 'O']:
        ws.column_dimensions[col].width = 15
    ws.column_dimensions['P'].width = 28
    ws.freeze_panes = f'A{header_row_num + 1}'


def _write_customs_ledger_sheet(wb, rows, summary):
    """
    Adds a "Customs Ledger" worksheet — the running CUSTOMS utilisation
    statement from `LicenseBalanceLedgerBuilder.build_customs_ledger()`
    (see its docstring: every BOE debits the licence at its FULL raw CIF,
    unconditionally, unlike the Financial Ledger's allocation-adjusted
    debit — the two are expected to diverge whenever reconciliation is
    incomplete, which is the actionable signal this report exists to
    surface). Preceded by its own "Customs Summary" block, mirroring the
    PDF's `_build_customs_ledger_elements` column set and section order.

    `rows`/`summary` are computed ONCE by the caller — no calculation
    happens in this function.
    """
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    ws = wb.create_sheet("Customs Ledger")

    HDR_FILL = PatternFill(start_color="1A1A1A", end_color="1A1A1A", fill_type="solid")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
    ROW_FILLS = {
        'customs_opening': PatternFill(start_color="1A5276", end_color="1A5276", fill_type="solid"),
        'customs_boe': PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid"),
        'customs_pending_allotment': PatternFill(start_color="FDEBD0", end_color="FDEBD0", fill_type="solid"),
        'final': PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid"),
    }
    MISMATCH_FILL = PatternFill(start_color="F5B7B1", end_color="F5B7B1", fill_type="solid")
    THIN = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    def fmt_date(d):
        return d.strftime('%d-%m-%Y') if d else '-'

    ws.merge_cells('A1:O1')
    ws['A1'] = 'CUSTOMS SUMMARY'
    ws['A1'].font = Font(bold=True, color="FFFFFF", size=14)
    ws['A1'].fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 26

    difference = abs(summary['computed_balance'] - summary['engine_balance'])
    r = 2
    summary_rows = [
        ('Original Licence CIF', summary['opening_balance']),
        ('Total BOE CIF', summary['total_boe_cif']),
        ('Pending Allotment CIF', summary['total_pending_allotment_cif']),
        ('Available Balance', summary['computed_balance']),
        ('Balance Engine', summary['engine_balance']),
        ('Difference', difference),
    ]
    for label, value in summary_rows:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        vcell = ws.cell(row=r, column=2, value=float(value))
        vcell.number_format = '#,##0.00'
        if summary['mismatched'] and label == 'Difference':
            ws.cell(row=r, column=1).fill = MISMATCH_FILL
            ws.cell(row=r, column=2).fill = MISMATCH_FILL
        r += 1

    r += 1
    status_text = 'RECONCILIATION FAILED' if summary['mismatched'] else 'MATCHED'
    status_color = 'C0392B' if summary['mismatched'] else '1E8449'
    ws.merge_cells(f'A{r}:O{r}')
    ws[f'A{r}'] = status_text
    ws[f'A{r}'].font = Font(bold=True, color=status_color, size=12)
    ws[f'A{r}'].alignment = Alignment(horizontal='center')
    r += 2

    ws.merge_cells(f'A{r}:O{r}')
    ws[f'A{r}'] = 'CUSTOMS LEDGER'
    ws[f'A{r}'].font = Font(bold=True, color="FFFFFF", size=14)
    ws[f'A{r}'].fill = HDR_FILL
    ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    headers = [
        'Sr', 'Date', 'Transaction Type', 'Document Number', 'BOE Number', 'BOE Date',
        'Company', 'Item', 'Quantity', 'CIF (USD)', 'Credit (USD)', 'Debit (USD)',
        'Running Balance (USD)', 'Status', 'Remarks',
    ]
    header_row = r
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=header_row, column=col, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.border = THIN
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    r += 1

    for row_data in rows:
        fill = MISMATCH_FILL if row_data.get('mismatched') else ROW_FILLS.get(row_data['row_kind'])
        font_white = row_data['row_kind'] in ('customs_opening', 'final') and not row_data.get('mismatched')
        values = [
            row_data['sr'],
            fmt_date(row_data['date']),
            row_data['type'],
            row_data['document_number'] or '-',
            row_data['boe_number'] or '-',
            fmt_date(row_data['boe_date']),
            row_data['company'] or '-',
            row_data['item_name'] or '-',
            float(row_data['qty']) if row_data['qty'] is not None else '-',
            float(row_data['cif_usd']) if row_data['cif_usd'] is not None else '-',
            float(row_data['credit']) if row_data['credit'] else '-',
            float(row_data['debit']) if row_data['debit'] else '-',
            float(row_data['running_balance']),
            row_data.get('status', '-'),
            row_data['remarks'],
        ]
        for col, val in enumerate(values, 1):
            c = ws.cell(row=r, column=col, value=val)
            c.border = THIN
            if fill:
                c.fill = fill
            if font_white:
                c.font = Font(color="FFFFFF", bold=True)
            if col in (9, 10, 11, 12, 13) and isinstance(val, float):
                c.number_format = '#,##0.00'
                c.alignment = Alignment(horizontal='right')
            else:
                c.alignment = Alignment(horizontal='left', wrap_text=True)
        r += 1

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 24
    ws.column_dimensions['H'].width = 22
    for col in ['I', 'J', 'K', 'L', 'M']:
        ws.column_dimensions[col].width = 16
    ws.column_dimensions['N'].width = 14
    ws.column_dimensions['O'].width = 28
    ws.freeze_panes = f'A{header_row + 1}'


def _write_timeline_sheet(wb, events):
    """
    Adds a "Timeline" worksheet — `LicenseBalanceLedgerBuilder.build_timeline()`'s
    real, timestamped business-lifecycle events (never fabricated), with
    hierarchical children (e.g. each BOE under an "Invoice <-> BOE
    Reconciled" parent) rendered immediately below their parent and grouped
    via openpyxl row outlining, same pattern as the Financial Ledger sheet.
    If there are no events, a single explanatory row is written instead of
    an empty table (matches the PDF's empty-state handling).
    """
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    ws = wb.create_sheet("Timeline")
    ws.sheet_properties.outlinePr.summaryBelow = False

    HDR_FILL = PatternFill(start_color="1A1A1A", end_color="1A1A1A", fill_type="solid")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
    TONE_FILLS = {
        'blue': PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid"),
        'orange': PatternFill(start_color="FDEBD0", end_color="FDEBD0", fill_type="solid"),
        'green': PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid"),
        'purple': PatternFill(start_color="E8DAEF", end_color="E8DAEF", fill_type="solid"),
        'teal': PatternFill(start_color="D1F2EB", end_color="D1F2EB", fill_type="solid"),
        'grey': PatternFill(start_color="F2F3F4", end_color="F2F3F4", fill_type="solid"),
        'red': PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid"),
    }
    CHILD_FILL = PatternFill(start_color="F7F9FA", end_color="F7F9FA", fill_type="solid")
    CHILD_FONT = Font(color="555555", size=9)
    THIN = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    def fmt_dt(dt):
        return dt.strftime('%d-%m-%Y %H:%M') if dt else '-'

    def fmt_money(value):
        return float(value) if value is not None else '-'

    ws.merge_cells('A1:J1')
    ws['A1'] = 'TIMELINE'
    ws['A1'].font = Font(bold=True, color="FFFFFF", size=14)
    ws['A1'].fill = PatternFill(start_color="0B3D59", end_color="0B3D59", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 26

    if not events:
        ws.merge_cells('A2:J2')
        ws['A2'] = 'No timeline events recorded for this licence yet.'
        ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
        ws.column_dimensions['A'].width = 20
        return

    headers = ['Sr', 'Date', 'Event Type', 'Document Number', 'Company', 'Qty', 'CIF (USD)', 'User', 'Status', 'Remarks']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.border = THIN
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    r = 3
    for e in events:
        fill = TONE_FILLS.get(e.get('color'))
        values = [
            e['sr'], fmt_dt(e['date']), e['label'],
            e.get('document_number') or '-', e.get('company') or '-',
            fmt_money(e.get('quantity')), fmt_money(e.get('cif')),
            e.get('user') or '-', e.get('status') or '-', e.get('remarks') or '-',
        ]
        for col, val in enumerate(values, 1):
            c = ws.cell(row=r, column=col, value=val)
            c.border = THIN
            if fill:
                c.fill = fill
            if col in (6, 7) and isinstance(val, float):
                c.number_format = '#,##0.00'
                c.alignment = Alignment(horizontal='right')
            else:
                c.alignment = Alignment(horizontal='left', wrap_text=True)
        r += 1

        for child in (e.get('children') or []):
            child_values = [
                '', fmt_dt(child.get('date')), f"↳ {child.get('label', '-')}",
                child.get('document_number') or '-', child.get('company') or '-',
                fmt_money(child.get('quantity')), fmt_money(child.get('cif')),
                child.get('user') or '-', child.get('status') or '-', child.get('remarks') or '-',
            ]
            for col, val in enumerate(child_values, 1):
                c = ws.cell(row=r, column=col, value=val)
                c.border = THIN
                c.fill = CHILD_FILL
                c.font = CHILD_FONT
                if col == 3:
                    c.alignment = Alignment(horizontal='left', wrap_text=True, indent=2)
                elif col in (6, 7) and isinstance(val, float):
                    c.number_format = '#,##0.00'
                    c.alignment = Alignment(horizontal='right')
                else:
                    c.alignment = Alignment(horizontal='left', wrap_text=True)
            ws.row_dimensions[r].outline_level = 1
            r += 1

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 24
    ws.column_dimensions['F'].width = 14
    ws.column_dimensions['G'].width = 16
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['I'].width = 16
    ws.column_dimensions['J'].width = 40
    ws.freeze_panes = 'A3'
