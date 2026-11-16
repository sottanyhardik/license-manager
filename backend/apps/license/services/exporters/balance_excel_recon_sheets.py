"""Worksheet writers (Reconciliation, Audit Log) for the licence balance workbook.
Split out of ``license_balance_excel.py``; behaviour unchanged.
"""


def _import_items_with_names(license_obj):
    """Import items with ``items`` prefetched (one query for all names).

    Keeps an existing prefetch (bulk export) untouched; otherwise adds one.
    """
    if 'import_license' in getattr(license_obj, '_prefetched_objects_cache', {}):
        return license_obj.import_license.all()
    return license_obj.import_license.prefetch_related('items')


def _write_reconciliation_sheet(wb, license_obj, financial_summary, customs_summary, reconciliation):
    """
    Adds a "Reconciliation" worksheet: the three-way Financial Ledger vs.
    Customs Ledger vs. Balance Engine comparison from
    `LicenseBalanceLedgerBuilder.build_reconciliation_summary()`
    (`reconciliation`, passed in — computed once by the caller), plus the
    pre-existing (real, tested) "Summary (BOE & Allotments)" table and Plan
    Utilization section that used to live on this workbook's old "Summary"
    sheet — folded in here rather than dropped.

    `financial_summary`/`customs_summary` are accepted for symmetry with
    the other `_write_X_sheet` helpers but are not directly rendered here
    (their numbers already feed `reconciliation`); kept as explicit
    parameters so a future addition to this sheet never has to recompute
    them.
    """
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from datetime import date as _date_cls
    from apps.license.services.item_usage import get_item_usage

    ws = wb.create_sheet("Reconciliation")

    HDR_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
    BOE_FILL = PatternFill(start_color="DEEAF1", end_color="DEEAF1", fill_type="solid")
    ALLOT_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    MISMATCH_FILL = PatternFill(start_color="F5B7B1", end_color="F5B7B1", fill_type="solid")
    BOLD = Font(bold=True, size=9)
    NORM = Font(size=9)
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

    # ── Collect summary rows (BOE & Allotments) ─────────────────────────
    summary_rows = []
    total_cif = 0.0

    for item in _import_items_with_names(license_obj):
        item_name = ', '.join(_nm) if (_nm := [i.name for i in item.items.all()]) else (item.description or '-')

        _usage = get_item_usage(item)
        boes = _usage['boes']

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

        allotments = _usage['allotments']

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
    r += 2

    # ══════════════════════════════════════════════════════════════════════
    # Section 2: Final Reconciliation Summary (three-way)
    # ══════════════════════════════════════════════════════════════════════
    ws.merge_cells(f'A{r}:G{r}')
    sh = ws[f'A{r}']
    sh.value = 'FINAL RECONCILIATION SUMMARY'
    sh.fill = PatternFill(start_color="0B3D59", end_color="0B3D59", fill_type="solid")
    sh.font = Font(bold=True, color="FFFFFF", size=11)
    sh.alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    rec_rows = [
        ('Financial Ledger Balance', reconciliation['financial_ledger_balance']),
        ('Customs Ledger Balance', reconciliation['customs_ledger_balance']),
        ('Licence Balance Engine', reconciliation['balance_engine']),
        ('Difference', reconciliation['difference']),
        ('Tolerance', reconciliation['tolerance']),
    ]
    diff_row = None
    for label, value in rec_rows:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        vcell = ws.cell(row=r, column=2, value=float(value))
        vcell.number_format = '#,##0.00'
        if label == 'Difference':
            diff_row = r
        r += 1
    if not reconciliation['matched'] and diff_row:
        ws.cell(row=diff_row, column=1).fill = MISMATCH_FILL
        ws.cell(row=diff_row, column=2).fill = MISMATCH_FILL

    r += 1
    status_text = '✓ MATCHED' if reconciliation['matched'] else '⚠ DIFFERENCE FOUND'
    status_color = '1E8449' if reconciliation['matched'] else 'C0392B'
    ws.merge_cells(f'A{r}:G{r}')
    ws[f'A{r}'] = status_text
    ws[f'A{r}'].font = Font(bold=True, color=status_color, size=12)
    ws[f'A{r}'].alignment = Alignment(horizontal='center')
    r += 2

    # ══════════════════════════════════════════════════════════════════════
    # Section 3: Summary (BOE & Allotments)
    # ══════════════════════════════════════════════════════════════════════
    ws.merge_cells(f'A{r}:G{r}')
    sh = ws[f'A{r}']
    sh.value = 'Summary (BOE & Allotments)'
    sh.fill = HDR_FILL; sh.font = Font(bold=True, color="FFFFFF", size=10)
    sh.alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    SUMM_COLS = ['Item', 'Type', 'Company', 'Reference', 'Qty', 'Rate', 'CIF Value (FC)']
    for col, h in enumerate(SUMM_COLS, 1):
        _hdr(ws, r, col, h)
    r += 1

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
    # Section 4: Plan Utilization  (matches the PlanTab UI exactly)
    # Shared with the bulk exporter's per-license sheet builder and the
    # "Utilization Planning Summary" sheet — see render_plan_utilization_section.
    # ══════════════════════════════════════════════════════════════════════
    from apps.license.services.plan_reporting import plan_map_for_license as _plan_map_fn
    from apps.license.services.exporters.planning_split_rows import render_plan_utilization_section
    _user_plan_map = _plan_map_fn(license_obj.id)

    r = render_plan_utilization_section(ws, r, license_obj, _license_balance, plan_map=_user_plan_map)

    # ── Column widths  (A=Item | B=HS | C=S.No | D=Status | E=Avail | F=Planned | G=Rem | H=PlannedCIF | I=RemCIF)
    ws.column_dimensions['A'].width = 38  # Item Description
    ws.column_dimensions['B'].width = 14  # HS Code
    ws.column_dimensions['C'].width = 14  # S.No
    ws.column_dimensions['D'].width = 14  # Status
    ws.column_dimensions['E'].width = 14  # Available Qty
    ws.column_dimensions['F'].width = 14  # Planned Qty
    ws.column_dimensions['G'].width = 14  # Remaining Qty
    ws.column_dimensions['H'].width = 16  # Planned CIF
    ws.column_dimensions['I'].width = 16  # Remaining CIF
    ws.column_dimensions['J'].width = 12

    ws.freeze_panes = 'A2'


def _write_audit_log_sheet(wb, license_obj):
    """
    Adds an "Audit Log" worksheet: every `ReconciliationLog` row for this
    licence's import items (the same append-only audit trail
    `LicenseBalanceLedgerBuilder.build_timeline()` reuses for its "Manual
    Adjustments" / reconciliation-action events — the
    `ReconciliationLog.objects.filter(license_item__license=license_obj)`
    query is reproduced verbatim here, see that method's docstring) plus
    every persisted `IgnoredWarning` row (ignore/restore history) for this
    licence, if any — both are real, persisted rows, never fabricated.
    """
    import json
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from apps.reconciliation.models import ReconciliationLog, IgnoredWarning

    ws = wb.create_sheet("Audit Log")

    HDR_FILL = PatternFill(start_color="1A1A1A", end_color="1A1A1A", fill_type="solid")
    HDR_FONT = Font(bold=True, color="FFFFFF", size=9)
    ALT_FILL = PatternFill(start_color="F7F9FA", end_color="F7F9FA", fill_type="solid")
    THIN = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    def user_label(user):
        if not user:
            return '-'
        return getattr(user, 'get_full_name', lambda: None)() or getattr(user, 'username', None) or '-'

    def fmt_dt(dt):
        return dt.strftime('%d-%m-%Y %H:%M') if dt else '-'

    def fmt_json(value):
        if not value:
            return '-'
        try:
            return json.dumps(value, default=str)
        except TypeError:
            return str(value)

    ws.merge_cells('A1:I1')
    ws['A1'] = 'AUDIT LOG'
    ws['A1'].font = Font(bold=True, color="FFFFFF", size=14)
    ws['A1'].fill = HDR_FILL
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 26

    r = 2
    ws.merge_cells(f'A{r}:I{r}')
    ws[f'A{r}'] = 'Reconciliation Actions'
    ws[f'A{r}'].font = Font(bold=True, color="FFFFFF", size=10)
    ws[f'A{r}'].fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
    ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    logs = list(
        ReconciliationLog.objects.filter(license_item__license=license_obj)
        .select_related('user')
        .order_by('created_on')
    )
    log_headers = ['Sr', 'Date/Time', 'Action', 'User', 'Reason', 'Before', 'After']
    for col, h in enumerate(log_headers, 1):
        c = ws.cell(row=r, column=col, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.border = THIN
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    r += 1

    if not logs:
        ws.merge_cells(f'A{r}:I{r}')
        ws[f'A{r}'] = 'No reconciliation actions recorded for this licence yet.'
        ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')
        r += 1
    else:
        for i, log in enumerate(logs, 1):
            fill = ALT_FILL if i % 2 == 0 else None
            values = [
                i, fmt_dt(log.created_on), log.get_action_display(),
                user_label(log.user), log.reason or '-',
                fmt_json(log.before), fmt_json(log.after),
            ]
            for col, val in enumerate(values, 1):
                c = ws.cell(row=r, column=col, value=val)
                c.border = THIN
                if fill:
                    c.fill = fill
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            r += 1

    r += 1

    ws.merge_cells(f'A{r}:I{r}')
    ws[f'A{r}'] = 'Ignored / Restored Warnings'
    ws[f'A{r}'].font = Font(bold=True, color="FFFFFF", size=10)
    ws[f'A{r}'].fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
    ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')
    r += 1

    ignored_warnings = list(
        IgnoredWarning.objects.filter(license=license_obj)
        .select_related('ignored_by', 'restored_by')
        .order_by('-ignored_at')
    )
    warn_headers = [
        'Warning Type', 'Entity Type', 'Entity ID', 'Status',
        'Ignored By', 'Ignored At', 'Restored By', 'Restored At', 'Reason',
    ]
    for col, h in enumerate(warn_headers, 1):
        c = ws.cell(row=r, column=col, value=h)
        c.font = HDR_FONT
        c.fill = HDR_FILL
        c.border = THIN
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    r += 1

    if not ignored_warnings:
        ws.merge_cells(f'A{r}:I{r}')
        ws[f'A{r}'] = 'No ignored/restored warnings recorded for this licence yet.'
        ws[f'A{r}'].alignment = Alignment(horizontal='center', vertical='center')
        r += 1
    else:
        for i, iw in enumerate(ignored_warnings, 1):
            fill = ALT_FILL if i % 2 == 0 else None
            values = [
                iw.warning_type, iw.entity_type, iw.entity_id,
                'Ignored' if iw.ignored else 'Restored',
                user_label(iw.ignored_by), fmt_dt(iw.ignored_at),
                user_label(iw.restored_by), fmt_dt(iw.restored_at),
                iw.reason or '-',
            ]
            for col, val in enumerate(values, 1):
                c = ws.cell(row=r, column=col, value=val)
                c.border = THIN
                if fill:
                    c.fill = fill
                c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            r += 1

    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 16
    ws.column_dimensions['E'].width = 40
    ws.column_dimensions['F'].width = 40
    ws.column_dimensions['G'].width = 18
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['I'].width = 30
    ws.freeze_panes = 'A2'
