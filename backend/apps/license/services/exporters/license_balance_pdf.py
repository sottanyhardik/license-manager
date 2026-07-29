"""PDF renderer for the license balance report.

Extracted verbatim from ``LicenseDetailsViewSet.balance_pdf`` as part of the
clean-architecture refactor: the viewset (delivery layer) now only resolves the
license and delegates rendering here. Behaviour is unchanged.

The report also renders a "Licence Financial Ledger" (bank-statement style
CIF reconciliation) ahead of the original Export/Import/BOE/Allotment tables
("the Customs Ledger"), plus a Final Reconciliation Summary at the end. See
`_build_financial_ledger_elements` / `_build_final_reconciliation_elements`.
"""
import re
from decimal import Decimal


def _split_invoice_numbers(raw):
    """Split a free-text invoice field into a clean, ordered, deduped list.

    Only splits on comma/semicolon/newline — NOT '/', because this system's
    own generated invoice numbers (`LicenseTrade.next_invoice_number`) are
    themselves in `PREFIX/FY/NNNN` form (e.g. "LGL/2026-27/0016"); splitting
    on '/' would shred a single invoice number into three fragments.
    """
    if not raw:
        return []
    seen = []
    for part in re.split(r'[,\n;]+', str(raw)):
        part = part.strip()
        if part and part not in seen:
            seen.append(part)
    return seen


def _format_invoice_list(invoice_numbers):
    return ', '.join(invoice_numbers) if invoice_numbers else '-'


def _item_display_name(license_import_item, fallback=''):
    """Same "join item names, else description" convention already used
    elsewhere in this file (e.g. the existing BOE/Allotment summary tables)."""
    if license_import_item is None:
        return fallback or '-'
    if license_import_item.items.exists():
        return ', '.join(i.name for i in license_import_item.items.all())
    return license_import_item.description or fallback or '-'


def _boe_invoice_allocation_map(license_obj):
    """
    {row_details_id: [invoice_number, ...]} of invoice numbers reconciled to
    each BOE debit row via active `InvoiceBOEAllocation` matches (the
    reconciliation panel), so the Financial Ledger and the enriched Customs
    Ledger both show invoices matched there too, not just the BOE's own
    free-text `invoice_no` field. One query for the whole license (not
    per-row), to stay cheap on licenses with hundreds of BOEs.
    """
    from apps.reconciliation.models import InvoiceBOEAllocation

    alloc_map = {}
    rows = InvoiceBOEAllocation.objects.filter(
        row_details__sr_number__license=license_obj,
        status=InvoiceBOEAllocation.STATUS_ACTIVE,
        is_current=True,
    ).values_list('row_details_id', 'trade_line__trade__invoice_number')
    for row_details_id, invoice_number in rows:
        if invoice_number:
            alloc_map.setdefault(row_details_id, []).append(invoice_number)
    return alloc_map


def _boe_row_invoice_numbers(row_details, alloc_map):
    """Union of the BOE's own free-text invoice(s) and any invoice numbers
    matched to this exact row via the reconciliation panel."""
    boe = row_details.bill_of_entry
    numbers = _split_invoice_numbers(boe.invoice_no if boe else None)
    for invoice_number in alloc_map.get(row_details.id, []):
        for piece in _split_invoice_numbers(invoice_number):
            if piece not in numbers:
                numbers.append(piece)
    return numbers


def _build_financial_ledger_elements(license_obj, alloc_map):
    """
    Render the "Licence Financial Ledger" — a bank-statement style
    breakdown of CIF utilisation (Opening Balance -> BOE debits ->
    outstanding Active Allotments -> reconciled Trade sales -> Current
    Balance) plus its Financial Summary.

    All calculation lives in `LicenseBalanceLedgerBuilder.build_financial_ledger`
    (the single source of truth also consumed by the JSON API and Excel) —
    this function ONLY formats those rows into a ReportLab table. It cannot
    independently drift from `calculate_balance()` because it never touches
    the underlying querysets itself.

    Returns (elements, summary); `summary` feeds the Final Reconciliation
    Summary appended after the (unmodified) Customs Ledger.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from apps.license.services.license_balance_ledger_builder import (
        LicenseBalanceLedgerBuilder, boe_external_invoice_map,
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('fl_cell', parent=styles['Normal'], fontSize=6, leading=7.5)
    cell_style_r = ParagraphStyle('fl_cell_r', parent=cell_style, alignment=TA_RIGHT)
    header_style = ParagraphStyle(
        'fl_hdr', parent=styles['Normal'], fontSize=6.2, leading=7.5,
        textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=TA_CENTER,
    )

    def C(text):
        return Paragraph('' if text is None else str(text), cell_style)

    def CR(text):
        return Paragraph('' if text is None else str(text), cell_style_r)

    def fmt_money(value):
        return f"{float(value):,.2f}" if value is not None else '-'

    def fmt_qty(value):
        return f"{float(value):,.2f}" if value is not None else '-'

    def fmt_date(d):
        return d.strftime('%d-%m-%Y') if d else '-'

    COLOR_OPENING = colors.HexColor('#1a5276')
    COLOR_BOE = colors.HexColor('#eafaf1')
    COLOR_CHILD = colors.HexColor('#f4f6f7')
    COLOR_ALLOT = colors.HexColor('#fef9e7')
    COLOR_TRADE_PURCHASE = colors.HexColor('#eaf2f8')
    COLOR_TRADE = colors.HexColor('#f4ecf7')
    COLOR_FINAL = colors.HexColor('#2c3e50')
    COLOR_MISMATCH = colors.HexColor('#f5b7b1')
    COLOR_HDR = colors.HexColor('#1a1a1a')
    ROW_KIND_COLORS = {
        'opening': COLOR_OPENING, 'boe': COLOR_BOE,
        'allotment': COLOR_ALLOT, 'trade_purchase': COLOR_TRADE_PURCHASE, 'trade': COLOR_TRADE,
    }
    child_cell_style = ParagraphStyle('fl_child_cell', parent=cell_style, textColor=colors.HexColor('#555555'))
    child_cell_style_r = ParagraphStyle('fl_child_cell_r', parent=child_cell_style, alignment=TA_RIGHT)

    def CC(text):
        return Paragraph('' if text is None else str(text), child_cell_style)

    def CCR(text):
        return Paragraph('' if text is None else str(text), child_cell_style_r)

    ext_map = boe_external_invoice_map(license_obj)
    ledger_rows, summary = LicenseBalanceLedgerBuilder.build_financial_ledger(license_obj, alloc_map, ext_map)

    if not summary['has_trading_activity']:
        # No Purchase or Sale trade at all — this section adds nothing over
        # the (unmodified) Customs Ledger below, so it's omitted from the
        # PDF entirely, matching the UI. `summary` is still returned in
        # full so `_build_final_reconciliation_elements` (called by the
        # caller with this exact return value) keeps working unchanged.
        return [], summary

    header_row = [
        'Sr', 'Txn Date', 'Txn Type', 'Doc Number', 'BOE Number', 'BOE Date',
        'Company (Importer)', 'Item Name', 'Invoice(s)', 'Qty',
        'BOE CIF (USD)', 'BOE INR', 'Credit (USD)', 'Debit (USD)',
        'Running Balance (USD)', 'Remarks',
    ]
    table_data = [[Paragraph(h, header_style) for h in header_row]]
    row_bgs = []

    for r in ledger_rows:
        boe_date_text = r.get('boe_date_display') or fmt_date(r['boe_date'])
        table_data.append([
            CR(r['sr']), C(fmt_date(r['date'])), C(r['type']),
            C(r['document_number'] or '-'), C(r['boe_number'] or '-'), C(boe_date_text),
            C(r['company'] or '-'), C(r['item_name'] or '-'),
            C(_format_invoice_list(r['invoice_numbers'])),
            CR(fmt_qty(r['qty'])),
            CR(fmt_money(r['cif_usd'])), CR(fmt_money(r['cif_inr'])),
            CR(fmt_money(r['credit']) if r['credit'] else '-'),
            CR(fmt_money(r['debit']) if r['debit'] else '-'),
            CR(fmt_money(r['running_balance'])),
            C(r['remarks']),
        ])
        if r['row_kind'] == 'final':
            row_bgs.append(COLOR_MISMATCH if r.get('mismatched') else COLOR_FINAL)
        else:
            row_bgs.append(ROW_KIND_COLORS[r['row_kind']])

        # Hierarchy: child rows are ALWAYS rendered (expanded by default —
        # PDF is static, there's no interactive collapse). Informational
        # only — Credit/Debit/Running Balance stay blank, the parent row
        # above already carries the accounting impact.
        for child in (r.get('children') or []):
            table_data.append([
                CC(''), CC(''), CC(f"↳ {child['type']}"),
                CC(''), CC(child.get('boe_number') or '-'), CC(fmt_date(child.get('boe_date'))),
                CC(child.get('company') or '-'), CC(child.get('item_name') or '-'),
                CC(_format_invoice_list(child.get('invoice_numbers') or [])),
                CCR(fmt_qty(child.get('qty'))),
                CCR(fmt_money(child.get('cif_usd'))), CCR(fmt_money(child.get('cif_inr'))),
                CCR('-'), CCR('-'), CCR('-'),
                CC(f"{child.get('status', '-')} — {child.get('remarks', '-')}"),
            ])
            row_bgs.append(COLOR_CHILD)

    mismatched = summary['mismatched']

    col_w = [
        7 * mm, 14 * mm, 16 * mm, 18 * mm, 16 * mm, 14 * mm, 30 * mm, 25 * mm, 20 * mm, 13 * mm,
        16 * mm, 17 * mm, 14 * mm, 14 * mm, 17 * mm, 24 * mm,
    ]

    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_HDR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    for i, bg in enumerate(row_bgs, start=1):
        text_color = colors.whitesmoke if bg in (COLOR_OPENING, COLOR_FINAL) else colors.black
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
        style_cmds.append(('TEXTCOLOR', (0, i), (-1, i), text_color))
        if bg is COLOR_MISMATCH:
            style_cmds.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))

    ledger_table = Table(table_data, colWidths=col_w, repeatRows=1)
    ledger_table.setStyle(TableStyle(style_cmds))

    def section_bar(text, bg='#0b3d59', size=12):
        bar = Table([[text]], colWidths=[sum(col_w)])
        bar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg)),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), size),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return bar

    elements = [section_bar('LICENCE FINANCIAL LEDGER'), Spacer(1, 3)]

    warning = summary['missing_purchase_warning']
    if warning['show_warning']:
        warning_style = ParagraphStyle(
            'fl_warning', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#7d6608'), alignment=TA_CENTER,
        )
        warning_bar = Table([[Paragraph(f"⚠ {warning['message']}", warning_style)]], colWidths=[sum(col_w)])
        warning_bar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef9e7')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#f1c40f')),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements += [warning_bar, Spacer(1, 4)]

    elements += [ledger_table, Spacer(1, 6)]

    # 3. FINANCIAL SUMMARY & RECONCILIATION
    summary_style = ParagraphStyle('fs_lbl', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
    summary_val_style = ParagraphStyle('fs_val', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)

    summary_rows = [
        ['Original Licence CIF', f"${fmt_money(summary['opening_balance'])}"],
        ['Total BOE Debits', f"${fmt_money(summary['total_boe_debit'])}"],
    ]
    if summary.get('total_invoice_allocation_debit', Decimal('0.00')) > Decimal('0.00'):
        summary_rows.append(['Total Invoice Allocation Debits', f"${fmt_money(summary['total_invoice_allocation_debit'])}"])
    summary_rows.append(['Outstanding Active Allotments', f"${fmt_money(summary['total_allotment_debit'])}"])
    if summary.get('total_purchase_credit', Decimal('0.00')) > Decimal('0.00'):
        summary_rows.append(['Total Purchase Credits', f"${fmt_money(summary['total_purchase_credit'])}"])
    if summary['total_trade_debit'] > Decimal('0.00'):
        summary_rows.append(['Total Trade (Sold) Debits', f"${fmt_money(summary['total_trade_debit'])}"])
    summary_rows += [
        ['Current Available Balance', f"${fmt_money(summary['computed_balance'])}"],
        ['Licence Balance Engine', f"${fmt_money(summary['engine_balance'])}"],
        ['Difference', f"${fmt_money(summary['difference'])}"],
        ['Tolerance', f"${fmt_money(summary['tolerance'])}"],
    ]
    summary_table_data = [[Paragraph(lbl, summary_style), Paragraph(val, summary_val_style)] for lbl, val in summary_rows]
    summary_table = Table(summary_table_data, colWidths=[200 * mm, 75 * mm])
    summary_style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fb')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    last_row = len(summary_table_data) - 1
    if mismatched:
        summary_style_cmds.append(('BACKGROUND', (0, last_row - 1), (-1, last_row - 1), COLOR_MISMATCH))
    summary_table.setStyle(TableStyle(summary_style_cmds))

    status_color = colors.HexColor('#c0392b') if mismatched else colors.HexColor('#1e8449')
    status_text = 'FINANCIAL RECONCILIATION FAILED' if mismatched else 'MATCHED'
    status_style = ParagraphStyle(
        'fs_status', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold',
        textColor=status_color, alignment=TA_CENTER,
    )
    status_bar = Table([[Paragraph(status_text, status_style)]], colWidths=[sum(col_w)])
    status_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fdecea') if mismatched else colors.HexColor('#eafaf1')),
        ('BOX', (0, 0), (-1, -1), 1, status_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements += [
        section_bar('FINANCIAL SUMMARY & RECONCILIATION', bg='#34495e', size=10),
        Spacer(1, 3), summary_table, Spacer(1, 3), status_bar, Spacer(1, 8),
    ]

    return elements, summary


def _build_customs_ledger_elements(license_obj):
    """
    "2. Customs Ledger" — the running CUSTOMS utilisation statement (see
    `LicenseBalanceLedgerBuilder.build_customs_ledger`'s docstring for why
    this deliberately debits every BOE at its FULL raw amount,
    unconditionally, unlike the Financial Ledger). Preceded by its own
    "Customs Summary" block per the report layout.

    Returns (elements, customs_summary) — the summary feeds the Final
    Reconciliation Summary's three-way comparison.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('cl_cell', parent=styles['Normal'], fontSize=6, leading=7.5)
    cell_style_r = ParagraphStyle('cl_cell_r', parent=cell_style, alignment=TA_RIGHT)
    header_style = ParagraphStyle(
        'cl_hdr', parent=styles['Normal'], fontSize=6.2, leading=7.5,
        textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=TA_CENTER,
    )

    def C(text):
        return Paragraph('' if text is None else str(text), cell_style)

    def CR(text):
        return Paragraph('' if text is None else str(text), cell_style_r)

    def fmt_money(value):
        return f"{float(value):,.2f}" if value is not None else '-'

    def fmt_qty(value):
        return f"{float(value):,.2f}" if value is not None else '-'

    def fmt_date(d):
        return d.strftime('%d-%m-%Y') if d else '-'

    COLOR_OPENING = colors.HexColor('#1a5276')
    COLOR_BOE = colors.HexColor('#eaf2f8')
    COLOR_PENDING = colors.HexColor('#fdebd0')
    COLOR_FINAL = colors.HexColor('#2c3e50')
    COLOR_MISMATCH = colors.HexColor('#f5b7b1')
    COLOR_HDR = colors.HexColor('#1a1a1a')
    ROW_KIND_COLORS = {
        'customs_opening': COLOR_OPENING, 'customs_boe': COLOR_BOE, 'customs_pending_allotment': COLOR_PENDING,
    }

    rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(license_obj)

    def section_bar(text, bg='#0b3d59', size=12):
        bar = Table([[text]], colWidths=[275 * mm])
        bar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg)),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), size),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return bar

    # ---- Customs Summary (shown ABOVE the ledger table) ----
    difference = abs(summary['computed_balance'] - summary['engine_balance'])
    summary_style = ParagraphStyle('cs_lbl', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
    summary_val_style = ParagraphStyle('cs_val', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)
    summary_rows = [
        ['Original Licence CIF', f"${fmt_money(summary['opening_balance'])}"],
        ['Total BOE CIF', f"${fmt_money(summary['total_boe_cif'])}"],
        ['Pending Allotment CIF', f"${fmt_money(summary['total_pending_allotment_cif'])}"],
        ['Available Balance', f"${fmt_money(summary['computed_balance'])}"],
        ['Balance Engine', f"${fmt_money(summary['engine_balance'])}"],
        ['Difference', f"${fmt_money(difference)}"],
    ]
    summary_table = Table(
        [[Paragraph(lbl, summary_style), Paragraph(val, summary_val_style)] for lbl, val in summary_rows],
        colWidths=[200 * mm, 75 * mm],
    )
    summary_style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fb')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    if summary['mismatched']:
        summary_style_cmds.append(('BACKGROUND', (0, 5), (-1, 5), COLOR_MISMATCH))
    summary_table.setStyle(TableStyle(summary_style_cmds))

    status_color = colors.HexColor('#c0392b') if summary['mismatched'] else colors.HexColor('#1e8449')
    status_text = 'RECONCILIATION FAILED' if summary['mismatched'] else 'MATCHED'
    status_style = ParagraphStyle(
        'cs_status', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold',
        textColor=status_color, alignment=TA_CENTER,
    )
    status_bar = Table([[Paragraph(status_text, status_style)]], colWidths=[275 * mm])
    status_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fdecea') if summary['mismatched'] else colors.HexColor('#eafaf1')),
        ('BOX', (0, 0), (-1, -1), 1, status_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements = [
        section_bar('CUSTOMS SUMMARY', bg='#34495e', size=10),
        Spacer(1, 3), summary_table, Spacer(1, 3), status_bar, Spacer(1, 8),
    ]

    # ---- Customs Ledger table ----
    header_row = [
        'Sr', 'Date', 'Transaction Type', 'Document Number', 'BOE Number', 'BOE Date',
        'Company', 'Item', 'Quantity', 'CIF (USD)', 'Credit (USD)', 'Debit (USD)',
        'Running Balance (USD)', 'Status', 'Remarks',
    ]
    table_data = [[Paragraph(h, header_style) for h in header_row]]
    row_bgs = []
    for r in rows:
        table_data.append([
            CR(r['sr']), C(fmt_date(r['date'])), C(r['type']),
            C(r['document_number'] or '-'), C(r['boe_number'] or '-'), C(fmt_date(r['boe_date'])),
            C(r['company'] or '-'), C(r['item_name'] or '-'),
            CR(fmt_qty(r['qty'])), CR(fmt_money(r['cif_usd'])),
            CR(fmt_money(r['credit']) if r['credit'] else '-'),
            CR(fmt_money(r['debit']) if r['debit'] else '-'),
            CR(fmt_money(r['running_balance'])),
            C(r.get('status', '-')), C(r['remarks']),
        ])
        if r['row_kind'] == 'final':
            row_bgs.append(COLOR_MISMATCH if r.get('mismatched') else COLOR_FINAL)
        else:
            row_bgs.append(ROW_KIND_COLORS.get(r['row_kind'], colors.white))

    col_w = [
        7 * mm, 16 * mm, 20 * mm, 20 * mm, 18 * mm, 16 * mm, 32 * mm, 28 * mm,
        16 * mm, 20 * mm, 18 * mm, 18 * mm, 22 * mm, 18 * mm, 26 * mm,
    ]
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_HDR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    for i, bg in enumerate(row_bgs, start=1):
        text_color = colors.whitesmoke if bg in (COLOR_OPENING, COLOR_FINAL) else colors.black
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
        style_cmds.append(('TEXTCOLOR', (0, i), (-1, i), text_color))

    ledger_table = Table(table_data, colWidths=col_w, repeatRows=1)
    ledger_table.setStyle(TableStyle(style_cmds))

    elements += [section_bar('CUSTOMS LEDGER'), Spacer(1, 3), ledger_table, Spacer(1, 8)]
    return elements, summary


def _build_timeline_elements(license_obj):
    """"3. Timeline" — real business-lifecycle events only (see
    `LicenseBalanceLedgerBuilder.build_timeline`'s docstring); nothing
    rendered here is fabricated. Expanded by default — child events (e.g.
    each BOE under an "Invoice <-> BOE Reconciled" event) are printed
    immediately indented below their parent, since PDF has no interactive
    collapse."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('tl_cell', parent=styles['Normal'], fontSize=6, leading=7.5)
    header_style = ParagraphStyle(
        'tl_hdr', parent=styles['Normal'], fontSize=6.2, leading=7.5,
        textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    child_style = ParagraphStyle('tl_child', parent=cell_style, textColor=colors.HexColor('#555555'))

    def C(text):
        return Paragraph('' if text is None else str(text), cell_style)

    def CC(text):
        return Paragraph('' if text is None else str(text), child_style)

    def fmt_money(value):
        return f"{float(value):,.2f}" if value is not None else '-'

    def fmt_dt(dt):
        return dt.strftime('%d-%m-%Y %H:%M') if dt else '-'

    TONE_COLORS = {
        'blue': colors.HexColor('#d6eaf8'), 'orange': colors.HexColor('#fdebd0'),
        'green': colors.HexColor('#d5f5e3'), 'purple': colors.HexColor('#e8daef'),
        'teal': colors.HexColor('#d1f2eb'), 'grey': colors.HexColor('#f2f3f4'),
        'red': colors.HexColor('#fadbd8'),
    }

    events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)

    header_row = ['Sr', 'Date', 'Event Type', 'Document Number', 'Company', 'Qty', 'CIF (USD)', 'User', 'Status', 'Remarks']
    table_data = [[Paragraph(h, header_style) for h in header_row]]
    row_bgs = []

    for e in events:
        table_data.append([
            C(e['sr']), C(fmt_dt(e['date'])), C(e['label']),
            C(e.get('document_number') or '-'), C(e.get('company') or '-'),
            C(fmt_money(e.get('quantity'))), C(fmt_money(e.get('cif'))),
            C(e.get('user') or '-'), C(e.get('status') or '-'), C(e.get('remarks') or '-'),
        ])
        row_bgs.append(TONE_COLORS.get(e.get('color'), colors.white))
        for child in (e.get('children') or []):
            table_data.append([
                CC(''), CC(fmt_dt(child.get('date'))), CC(f"↳ {child['label']}"),
                CC(child.get('document_number') or '-'), CC(child.get('company') or '-'),
                CC(fmt_money(child.get('quantity'))), CC(fmt_money(child.get('cif'))),
                CC(child.get('user') or '-'), CC(child.get('status') or '-'), CC(child.get('remarks') or '-'),
            ])
            row_bgs.append(colors.HexColor('#f7f9fa'))

    col_w = [7 * mm, 28 * mm, 32 * mm, 30 * mm, 34 * mm, 20 * mm, 22 * mm, 24 * mm, 20 * mm, 58 * mm]
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    for i, bg in enumerate(row_bgs, start=1):
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

    section_bar = Table([['TIMELINE']], colWidths=[275 * mm])
    section_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0b3d59')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    if not events:
        empty = Paragraph(
            'No timeline events recorded for this licence yet.',
            ParagraphStyle('tl_empty', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER),
        )
        return [section_bar, Spacer(1, 6), empty, Spacer(1, 8)]

    table = Table(table_data, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    return [section_bar, Spacer(1, 3), table, Spacer(1, 8)]


def _build_final_reconciliation_elements(license_obj, ledger_summary, customs_summary=None):
    """
    "6. Final Reconciliation Summary" — the closing three-way check:
    Financial Ledger balance vs. Customs Ledger balance (from the REAL
    running Customs Ledger, `build_customs_ledger`, not the denormalized
    `balance_cif` proxy) vs. the live Balance Engine.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder

    styles = getSampleStyleSheet()

    rec = LicenseBalanceLedgerBuilder.build_reconciliation_summary(license_obj, ledger_summary, customs_summary)
    matched = rec['matched']

    label_style = ParagraphStyle('rec_lbl', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
    value_style = ParagraphStyle('rec_val', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)

    rows = [
        ['Financial Ledger Balance', f"${rec['financial_ledger_balance']:,.2f}"],
        ['Customs Ledger Balance', f"${rec['customs_ledger_balance']:,.2f}"],
        ['Licence Balance Engine', f"${rec['balance_engine']:,.2f}"],
        ['Difference', f"${rec['difference']:,.2f}"],
        ['Tolerance', f"${rec['tolerance']:,.2f}"],
    ]
    rec_table_data = [[Paragraph(lbl, label_style), Paragraph(val, value_style)] for lbl, val in rows]
    rec_table = Table(rec_table_data, colWidths=[140 * mm, 137 * mm])
    rec_style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7f9fb')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    if not matched:
        rec_style_cmds.append(('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#f5b7b1')))
    rec_table.setStyle(TableStyle(rec_style_cmds))

    status_color = colors.HexColor('#1e8449') if matched else colors.HexColor('#c0392b')
    status_text = '✓ MATCHED' if matched else '⚠ DIFFERENCE FOUND'
    status_style = ParagraphStyle(
        'rec_status', parent=styles['Normal'], fontSize=12, fontName='Helvetica-Bold',
        textColor=status_color, alignment=TA_CENTER,
    )
    status_table = Table([[Paragraph(status_text, status_style)]], colWidths=[277 * mm])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eafaf1') if matched else colors.HexColor('#fdecea')),
        ('BOX', (0, 0), (-1, -1), 1, status_color),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    header_bar = Table([['FINANCIAL RECONCILIATION']], colWidths=[277 * mm])
    header_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0b3d59')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    return [Spacer(1, 10), header_bar, Spacer(1, 4), rec_table, Spacer(1, 4), status_table]


def build_balance_pdf_response(license_obj, request):
    """
    Generate PDF report for license balance details with all BOEs and Allotments.
    """
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io
    from datetime import date
    from apps.license.services.item_usage import get_item_usage


    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                          rightMargin=10*mm, leftMargin=10*mm,
                          topMargin=12*mm, bottomMargin=12*mm)

    # Container for PDF elements
    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=3,
        fontName='Helvetica-Bold'
    )

    # Add title
    title = Paragraph(f"<b>License Balance Report</b>", title_style)
    elements.append(title)
    elements.append(Spacer(1, 3))

    # Add license header information split into 2 rows for clarity
    # Check if license has specific document types
    has_tl = license_obj.license_documents.filter(type='TRANSFER LETTER').exists()
    has_copy = license_obj.license_documents.filter(type='LICENSE COPY').exists()

    # Build license number with link if documents exist
    license_number_text = license_obj.license_number or '-'
    if has_tl or has_copy:
        # Get the base URL from request
        base_url = request.build_absolute_uri('/').rstrip('/')
        merge_url = f"{base_url}/api/licenses/{license_obj.id}/merged-documents/"
        license_number_text = f'{license_obj.license_number or "-"} (<link href="{merge_url}" color="blue"><u>Copy</u></link>)'

    header_data = [
        # Row 1: Headers
        ['License Number', 'License Date', 'License Expiry Date', 'Exporter Name', 'Port Name'],
        # Row 1: Values
        [
            Paragraph(license_number_text, styles['Normal']),
            license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-',
            license_obj.license_expiry_date.strftime('%d-%m-%Y') if license_obj.license_expiry_date else '-',
            Paragraph(license_obj.exporter.name if license_obj.exporter else '-', styles['Normal']),
            Paragraph(license_obj.port.name if license_obj.port else '-', styles['Normal'])
        ],
        # Row 2: Headers (spanning to match 5 columns)
        ['Purchase Status', 'Balance CIF', 'Get Norm Class', '', 'Latest Transfer'],
        # Row 2: Values
        [
            license_obj.purchase_status or '-',
            f"{float(license_obj.balance_cif or 0):.2f}",
            license_obj.get_norm_class or '-',
            '',
            Paragraph(str(license_obj.latest_transfer) if license_obj.latest_transfer else '-', styles['Normal'])
        ]
    ]

    # Landscape A4 is ~277mm wide, with margins = ~257mm usable width
    # Split into 5 columns: 50mm, 35mm, 40mm, 70mm, 62mm = 257mm
    header_table = Table(header_data, colWidths=[50*mm, 35*mm, 40*mm, 70*mm, 62*mm])
    header_table.setStyle(TableStyle([
        # Row 1 header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        # Row 2 header
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.whitesmoke),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        # Data rows
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ecf0f1')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ecf0f1')),
        # Common styles
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 2), (-1, 2), 8),
        ('FONTSIZE', (0, 1), (-1, 1), 7.5),
        ('FONTSIZE', (0, 3), (-1, 3), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 5))

    # 2. Financial Licence Ledger (NEW) — bank-statement style CIF
    # reconciliation, inserted before the existing Customs Ledger below.
    alloc_map = _boe_invoice_allocation_map(license_obj)
    ledger_elements, ledger_summary = _build_financial_ledger_elements(license_obj, alloc_map)
    elements.extend(ledger_elements)

    # 4. Existing Customs Ledger — Export Items Section
    if license_obj.export_license.exists():
        # Section header as table row
        export_section_header = Table([['Export Items']], colWidths=[275*mm])
        export_section_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(export_section_header)

        export_data = [['Item', 'Total CIF', 'Balance CIF']]
        for item in license_obj.export_license.all():
            item_desc = item.description or (str(item.norm_class) if item.norm_class else None) or 'None'
            export_data.append([
                Paragraph(item_desc, styles['Normal']),
                f"{float(item.cif_fc or item.fob_fc or 0):.2f}",
                f"{float(license_obj.balance_cif or 0):.2f}"
            ])

        export_table = Table(export_data, colWidths=[185*mm, 45*mm, 45*mm])
        export_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')])
        ]))
        elements.append(export_table)
        elements.append(Spacer(1, 8))

    # Import Items Section with Usage Details
    if license_obj.import_license.exists():
        # Section header as table row
        import_section_header = Table([['Import Items']], colWidths=[275*mm])
        import_section_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(import_section_header)

        for item in license_obj.import_license.all():
            # Main item data
            item_names = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else '-'

            # Get HS code label
            hs_code_display = str(item.hs_code.hs_code if item.hs_code else '-')

            item_data = [[
                'Sr', 'HS Code', 'Description', 'Item', 'Total Qty',
                'Allotted', 'Debited', 'Available', 'CIF FC', 'Bal CIF'
            ], [
                str(item.serial_number or '-'),
                hs_code_display,
                Paragraph(str(item.description or '-'), styles['Normal']),
                Paragraph(item_names, styles['Normal']),
                f"{float(item.quantity or 0):.2f}",
                f"{float(item.allotted_quantity or 0):.2f}",
                f"{float(item.debited_quantity or 0):.2f}",
                f"{float(item.available_quantity or 0):.2f}",
                f"{float(item.cif_fc or 0):.2f}",
                f"{float(item.balance_cif_fc or 0):.2f}"
            ]]

            item_table = Table(item_data, colWidths=[12*mm, 25*mm, 60*mm, 50*mm, 23*mm, 21*mm, 21*mm, 21*mm, 21*mm, 21*mm])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1'))
            ]))
            elements.append(item_table)
            elements.append(Spacer(1, 3))

            # BOEs
            _usage = get_item_usage(item)
            boes = _usage['boes']

            if boes.exists():
                # BOEs header as section row
                boe_section_header = Table([['BOEs']], colWidths=[275*mm])
                boe_section_header.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333')),
                ]))
                elements.append(boe_section_header)

                boe_data = [['BOE Number', 'Date', 'Port', 'Company', 'Qty', 'CIF $', 'CIF INR', 'Invoice(s)']]

                # Calculate totals
                total_qty = 0
                total_cif_fc = 0
                total_cif_inr = 0

                for detail in boes:
                    total_qty += float(detail.qty or 0)
                    total_cif_fc += float(detail.cif_fc or 0)
                    total_cif_inr += float(detail.cif_inr or 0)

                    boe_data.append([
                        detail.bill_of_entry.bill_of_entry_number,
                        detail.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if detail.bill_of_entry.bill_of_entry_date else '-',
                        Paragraph(detail.bill_of_entry.port.name if detail.bill_of_entry.port else '-', styles['Normal']),
                        Paragraph(detail.bill_of_entry.company.name or '-' if detail.bill_of_entry.company else '-', styles['Normal']),
                        f"{float(detail.qty):.2f}",
                        f"{float(detail.cif_fc):.2f}",
                        f"{float(detail.cif_inr):.2f}",
                        Paragraph(_format_invoice_list(_boe_row_invoice_numbers(detail, alloc_map)), styles['Normal']),
                    ])

                # Add total footer row
                boe_data.append([
                    '', '', '', 'Total',
                    f"{total_qty:.2f}",
                    f"{total_cif_fc:.2f}",
                    f"{total_cif_inr:.2f}",
                    '',
                ])

                boe_table = Table(boe_data, colWidths=[40*mm, 25*mm, 40*mm, 55*mm, 25*mm, 30*mm, 35*mm, 25*mm])
                boe_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#e8f5e9')]),
                    # Footer row styling
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, -1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                elements.append(boe_table)
                elements.append(Spacer(1, 5))

            # Allotments — reuses `_usage` fetched above for the BOE table (one
            # get_item_usage() call per item covers both tables now).
            allotments = _usage['allotments']

            if allotments.exists():
                # Allotments header as section row
                allot_section_header = Table([['Allotments']], colWidths=[275*mm])
                allot_section_header.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e67e22')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#333333')),
                ]))
                elements.append(allot_section_header)

                allot_data = [['Company', 'Qty', 'CIF $', 'CIF INR', 'Invoice']]

                # Calculate totals
                total_allot_qty = 0
                total_allot_cif_fc = 0
                total_allot_cif_inr = 0

                for allot in allotments:
                    total_allot_qty += float(allot.qty or 0)
                    total_allot_cif_fc += float(allot.cif_fc or 0)
                    total_allot_cif_inr += float(allot.cif_inr or 0)

                    allot_data.append([
                        Paragraph(allot.allotment.company.name if allot.allotment.company else '-', styles['Normal']),
                        f"{float(allot.qty):.2f}",
                        f"{float(allot.cif_fc):.2f}",
                        f"{float(allot.cif_inr):.2f}",
                        Paragraph(_format_invoice_list(_split_invoice_numbers(allot.allotment.invoice)), styles['Normal']),
                    ])

                # Add total footer row
                allot_data.append([
                    'Total',
                    f"{total_allot_qty:.2f}",
                    f"{total_allot_cif_fc:.2f}",
                    f"{total_allot_cif_inr:.2f}",
                    '',
                ])

                allot_table = Table(allot_data, colWidths=[130*mm, 40*mm, 40*mm, 40*mm, 25*mm])
                allot_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('FONTSIZE', (0, 1), (-1, -2), 7.5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fef5e7')]),
                    # Footer row styling
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fdebd0')),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, -1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                elements.append(allot_table)
                elements.append(Spacer(1, 5))

            # Balance calculation as table footer
            balance = float(item.quantity or 0) - float(item.debited_quantity or 0) - float(item.allotted_quantity or 0)
            balance_table = Table([[f'Balance Quantity: {balance:.2f}']], colWidths=[275*mm])
            balance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e8e8e8')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#e74c3c')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(balance_table)
            elements.append(Spacer(1, 8))

    # Add Notes Section if notes exist
    if license_obj.balance_report_notes:
        notes_header = Table([['Notes']], colWidths=[275*mm])
        notes_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(notes_header)

        notes_content = Table([[Paragraph(license_obj.balance_report_notes, styles['Normal'])]], colWidths=[275*mm])
        notes_content.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffacd')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(notes_content)

    # ── End-of-PDF Summary Table ─────────────────────────────────────────
    # One flat row per BOE/Allotment per item — easy to copy-paste to Excel
    # Light green = BOE rows, Light red = Allotment rows
    COLOR_BOE   = colors.HexColor('#d9ead3')   # light green
    COLOR_ALLOT = colors.HexColor('#fce8e6')   # light red
    COLOR_HDR   = colors.HexColor('#1a1a1a')

    # Paragraph style for wrapping text in summary cells
    wrap_style = ParagraphStyle('wrap', parent=styles['Normal'], fontSize=7.5, leading=10)

    def P(text):
        return Paragraph(str(text), wrap_style)

    # Collect all rows — sort by item name before building table
    # Columns: License No | License Date | Item | Type | Company | Reference | Qty | Rate | CIF Value (FC)
    # BOE Reference  = "BOE number\nDate"
    # Allot Reference = "Invoice\nETA: date" (if available)
    summary_data = [['License No', 'License Date', 'Item', 'Type', 'Company', 'Reference', 'Qty', 'Rate', 'CIF Value (FC)']]
    summary_rows = []  # (sort_key, row_cells, color)
    total_cif    = 0.0

    license_date_str = license_obj.license_date.strftime('%d-%m-%Y') if license_obj.license_date else '-'
    lic_no = license_obj.license_number or '-'

    # Pre-aggregate by item name across all sr numbers.
    from collections import defaultdict
    from decimal import Decimal as _Dec
    from django.db.models import Sum as _Sum, DecimalField as _DF, Value as _Val
    from django.db.models.functions import Coalesce as _Coalesce

    # New restriction model: condition_type on LicenseImportItemsModel is
    # the source of truth. %-conditions share a pool from compute_condition_pools();
    # AU / blank use the full licence balance.
    from apps.license.services.condition_pool import compute_condition_pools as _ccp
    _cond_pools = _ccp(license_obj)

    _bal_agg = defaultdict(lambda: {'qty': 0.0, 'total_qty': 0.0, 'sr_ids': [], 'description': '', 'hs_code': '', 'condition_type': '', 'qty_by_cond': {}})
    for _item in license_obj.import_license.all():
        _key = ', '.join(sorted([i.name for i in _item.items.all()])) if _item.items.exists() else (_item.description or '-')
        _avail = float(_item.available_quantity or 0)
        _bal_agg[_key]['qty'] += _avail
        _bal_agg[_key]['total_qty'] += float(_item.quantity or 0)
        _bal_agg[_key]['sr_ids'].append(_item.serial_number)
        if not _bal_agg[_key]['description']:
            _bal_agg[_key]['description'] = _item.description or _key
        if not _bal_agg[_key]['hs_code']:
            _bal_agg[_key]['hs_code'] = str(_item.hs_code.hs_code if _item.hs_code else '-')
        if _item.condition_type and not _bal_agg[_key]['condition_type']:
            _bal_agg[_key]['condition_type'] = _item.condition_type
        # Per-condition qty breakdown for E1's Display/Util-qty split.
        _ct = (_item.condition_type or '').strip()
        _bal_agg[_key]['qty_by_cond'][_ct] = _bal_agg[_key]['qty_by_cond'].get(_ct, 0.0) + _avail

    for item in license_obj.import_license.all():
        item_name = ', '.join([i.name for i in item.items.all()]) if item.items.exists() else (item.description or '-')

        _usage = get_item_usage(item)
        boes = _usage['boes']

        for rd in boes:
            qty     = float(rd.qty or 0)
            cif     = float(rd.cif_fc or 0)
            rate    = cif / qty if qty else 0.0
            total_cif += cif
            boe_company = rd.bill_of_entry.company.name if rd.bill_of_entry.company else '-'
            ref_no  = rd.bill_of_entry.bill_of_entry_number or '-'
            ref_date = rd.bill_of_entry.bill_of_entry_date.strftime('%d-%m-%Y') if rd.bill_of_entry.bill_of_entry_date else ''
            ref_str = f"{ref_no}\n{ref_date}" if ref_date else ref_no
            product = rd.bill_of_entry.product_name or item_name
            summary_rows.append((product.lower(), [
                P(lic_no), P(license_date_str), P(product),
                P('BOE'), P(boe_company), P(ref_str),
                P(f"{qty:,.2f}"), P(f"{rate:.2f}"), P(f"{cif:,.2f}"),
            ], COLOR_BOE))

        allotments = _usage['allotments']

        for ai in allotments:
            qty     = float(ai.qty or 0)
            cif     = float(ai.cif_fc or 0)
            rate    = cif / qty if qty else 0.0
            total_cif += cif
            company = ai.allotment.company.name if ai.allotment.company else '-'
            invoice = ai.allotment.invoice or '-'
            eta     = ai.allotment.estimated_arrival_date.strftime('%d-%m-%Y') if ai.allotment.estimated_arrival_date else ''
            ref_str = f"{invoice}\nETA: {eta}" if eta else invoice
            product = ai.allotment.item_name or item_name
            summary_rows.append((product.lower(), [
                P(lic_no), P(license_date_str), P(product),
                P('Allotment'), P(company), P(ref_str),
                P(f"{qty:,.2f}"), P(f"{rate:.2f}"), P(f"{cif:,.2f}"),
            ], COLOR_ALLOT))

    # Sort by item name
    summary_rows.sort(key=lambda x: x[0])
    row_colors = []
    for _, row_cells, color in summary_rows:
        summary_data.append(row_cells)
        row_colors.append(color)

    if len(summary_data) > 1:
        # Total row
        summary_data.append([P(''), P(''), P(''), P(''), P('TOTAL'), P(''), P(''), P(''), P(f"{total_cif:,.2f}")])
        row_colors.append(colors.HexColor('#f2f2f2'))

        # ── License info mini-header (License No | License Date | Total CIF) ──
        total_license_cif = total_cif + float(license_obj.balance_cif or 0)
        info_style = ParagraphStyle('info', parent=styles['Normal'], fontSize=8, leading=11,
                                    textColor=colors.white, fontName='Helvetica-Bold')
        def IP(label, value):
            return Paragraph(f"<b>{label}:</b> {value}", info_style)

        info_row = Table([[
            IP('License No', lic_no),
            IP('License Date', license_date_str),
            IP('Total CIF', f"{total_license_cif:,.2f}"),
        ]], colWidths=[92*mm, 92*mm, 93*mm])
        info_row.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_HDR),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(Spacer(1, 10))
        elements.append(info_row)

        # Section header
        summ_hdr = Table([['Summary (BOE & Allotments)']], colWidths=[277*mm])
        summ_hdr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_HDR),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(summ_hdr)

        # col widths: lic_no, lic_date, item, type, company, reference, qty, rate, cif = 277mm
        col_w = [28*mm, 22*mm, 55*mm, 18*mm, 40*mm, 35*mm, 20*mm, 22*mm, 37*mm]
        summ_table = Table(summary_data, colWidths=col_w)

        style_cmds = [
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HDR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('ALIGN', (6, 0), (-1, -1), 'RIGHT'),   # qty, rate, cif right-aligned
            ('ALIGN', (0, 0), (5, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Total row bold
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f2f2f2')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]
        # Apply per-row background colours (skip header row at index 0)
        for i, bg in enumerate(row_colors, start=1):
            if i < len(summary_data):  # skip total row (handled above)
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

        summ_table.setStyle(TableStyle(style_cmds))
        elements.append(summ_table)

    # ── Balance Summary Table ─────────────────────────────────────────────
    if _bal_agg:
        total_bal_cif_fc = float(license_obj.balance_cif or 0)
        COLOR_YELLOW = colors.HexColor('#ffff00')

        # "Summary (Balance Quantity)" section header
        bal_hdr = Table([['Summary (Balance Quantity)']], colWidths=[277*mm])
        bal_hdr.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_HDR),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(Spacer(1, 8))
        elements.append(bal_hdr)

        # col widths: hsn, item_name, bal_qty, unit_price, cif_fc = 277mm
        # 30 + 87 + 45 + 45 + 70 = 277mm
        bal_col_w = [30*mm, 87*mm, 45*mm, 45*mm, 70*mm]

        Pb      = ParagraphStyle('balwrap',     parent=styles['Normal'], fontSize=8, leading=11)
        Pb_hdr  = ParagraphStyle('balwrap_hdr', parent=styles['Normal'], fontSize=8, leading=11,
                                 textColor=colors.white, fontName='Helvetica-Bold')
        Pb_yel  = ParagraphStyle('balwrap_yel', parent=styles['Normal'], fontSize=9, leading=12,
                                 fontName='Helvetica-Bold')

        def BP(text):
            return Paragraph(str(text), Pb)
        def BH(text):   # white bold header cell
            return Paragraph(str(text), Pb_hdr)
        def BY(text):   # yellow-cell (black bold)
            return Paragraph(str(text), Pb_yel)

        _license_balance = float(license_obj.get_balance_cif or 0)
        bal_table_data = [
            # Row 0: cols 0-3 merged "BALANCE CIF $" | col 4 = total (yellow)
            [BH('BALANCE CIF $'), '', '', '', BY(f"{total_bal_cif_fc:,.2f}")],
            # Row 1: column headers
            [BH('HSN Code'), BH('Item Name'), BH('Bal Qty'), BH('Unit Price'), BH('CIF FC')],
        ]
        for item_key in sorted(_bal_agg.keys()):
            b_qty = _bal_agg[item_key]['qty']
            cond = _bal_agg[item_key].get('condition_type') or ''
            if cond in _cond_pools:
                b_cif = float(min(_cond_pools[cond], _Dec(str(_license_balance))))
            else:
                b_cif = _license_balance
            unit_price = b_cif / b_qty if b_qty else 0.0
            desc       = _bal_agg[item_key]['description'] or item_key
            hs         = _bal_agg[item_key]['hs_code']
            bal_table_data.append([
                BP(hs),
                BP(desc),
                BP(f"{b_qty:,.2f}"),
                BP(f"{unit_price:,.2f}"),
                BP(f"{b_cif:,.2f}"),
            ])

        bal_table = Table(bal_table_data, colWidths=bal_col_w)
        bal_style = TableStyle([
            # Row 0: merge cols 0-3, dark header | col 4 yellow
            ('SPAN', (0, 0), (3, 0)),
            ('BACKGROUND', (0, 0), (3, 0), COLOR_HDR),
            ('BACKGROUND', (4, 0), (4, 0), COLOR_YELLOW),
            ('TEXTCOLOR', (4, 0), (4, 0), colors.black),
            ('ALIGN', (0, 0), (3, 0), 'CENTER'),
            ('ALIGN', (4, 0), (4, 0), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            # Row 1: column headers
            ('BACKGROUND', (0, 1), (-1, 1), COLOR_HDR),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            # Data rows: cols 2-4 right-aligned
            ('FONTSIZE', (0, 2), (-1, -1), 8),
            ('ALIGN', (2, 2), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 2), (1, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            # All cells
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ])
        bal_table.setStyle(bal_style)
        elements.append(Spacer(1, 8))
        elements.append(bal_table)

    # 4. Customs Summary + Customs Ledger (running utilisation statement —
    # separate from the itemised Export/Import/BOE/Allotment tables above,
    # which stay untouched as the item-level detail appendix).
    customs_elements, customs_summary = _build_customs_ledger_elements(license_obj)
    elements.extend(customs_elements)

    # 5. Timeline
    elements.extend(_build_timeline_elements(license_obj))

    # 6. Final Reconciliation Summary (three-way: Financial vs Customs vs Engine)
    elements.extend(_build_final_reconciliation_elements(license_obj, ledger_summary, customs_summary))

    # Build PDF
    doc.build(elements)

    # Get PDF from buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{license_obj.license_number}-balance.pdf"'
    response.write(pdf)

    return response
