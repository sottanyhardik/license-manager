"""Excel renderers for license balance reports.

Extracted verbatim from ``LicenseDetailsViewSet.balance_excel``,
``balance_excel_unused`` and ``bulk_balance_excel`` as part of the
clean-architecture refactor. The viewset now only resolves inputs and delegates
here; behaviour is unchanged.

Facade module: the sheet writers and the bulk builder live in
``balance_excel_ledger_sheets``, ``balance_excel_recon_sheets`` and
``license_balance_excel_bulk``; every name is re-exported here.
"""
from apps.license.services.exporters.balance_excel_ledger_sheets import (  # noqa: F401
    _write_financial_ledger_sheet,
    _write_customs_ledger_sheet,
    _write_timeline_sheet,
)
from apps.license.services.exporters.balance_excel_recon_sheets import (  # noqa: F401
    _import_items_with_names,
    _write_reconciliation_sheet,
    _write_audit_log_sheet,
)
from apps.license.services.exporters.license_balance_excel_bulk import build_bulk_balance_excel  # noqa: F401


def build_balance_excel_unused(license_obj):
    """Original full balance Excel — kept for reference, no longer exposed."""
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from io import BytesIO

    # BL-LEDGER-02: `license_obj.balance_cif` is a denormalized cache that
    # can be stale -- compute the live figure once and reuse it everywhere
    # this function shows "Balance CIF", matching every other module.
    from apps.license.services.balance_calculator import LicenseBalanceCalculator
    from apps.license.services.condition_pool import available_value_bulk_map
    live_balance_cif = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
    import_items = list(license_obj.import_license.all())
    available_value_map = available_value_bulk_map(import_items)


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
        f"{float(live_balance_cif):.2f}",
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
                f"{float(live_balance_cif):.2f}"
            ]
            for col_num, value in enumerate(values, 1):
                cell = ws.cell(row=current_row, column=col_num, value=value)
                cell.border = thin_border
            current_row += 1

        current_row += 1

    # Import Items Section
    if import_items:
        from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
        from apps.allotment.models import AllotmentItems

        # Section header
        ws.merge_cells(f'A{current_row}:J{current_row}')
        section_cell = ws[f'A{current_row}']
        section_cell.value = "Import Items"
        section_cell.fill = section_fill
        section_cell.font = section_font
        section_cell.alignment = Alignment(horizontal='center', vertical='center')
        current_row += 1

        for item in import_items:
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
            item_names = ', '.join(_nm) if (_nm := [i.name for i in item.items.all()]) else '-'
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
                f"{float(available_value_map.get(item.id, 0)):.2f}"
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
            # Previous-owner "hidden" BOEs (genuinely hidden per audit
            # trail) are excluded — this report is a balance/financial
            # figure, not the Customs History audit view.
            boes = annotate_and_exclude_hidden(
                RowDetails.objects.filter(sr_number_id=item.id, transaction_type='D'),
                boe_field="bill_of_entry",
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

            # Balance calculation — reads the stored, single-source-of-truth
            # `available_quantity` field (`Total − Debited − Outstanding
            # Allotted`, kept correct by `apps.core.scripts.calculate_
            # balance.update_balance_values`) rather than recombining the
            # other three columns independently here.
            current_row += 1
            balance = float(item.available_quantity or 0)
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


def build_balance_excel(license_obj, show_hidden=False):
    """
    Generate the Licence Balance Workspace Excel export: five worksheets —
    "Financial Ledger", "Customs Ledger", "Timeline", "Reconciliation", and
    "Audit Log" — all built from `LicenseBalanceLedgerBuilder` data. Each
    builder method is called exactly ONCE here and its result passed to the
    relevant `_write_X_sheet` helper, so none of these worksheets can
    independently drift from the JSON API workspace or the PDF report —
    and no calculation happens anywhere in this module.

    `show_hidden` mirrors the on-screen "show hidden BOE" toggle for the
    Customs Ledger sheet — see `LicenseBalanceLedgerBuilder.build_customs_ledger`.

    Phase 4E-D: Running balance values sourced from CanonicalLedgerService,
    not independently recalculated.
    """
    from django.http import HttpResponse
    import openpyxl
    from io import BytesIO
    from apps.license.services.license_balance_ledger_builder import (
        LicenseBalanceLedgerBuilder, boe_invoice_allocation_map, boe_external_invoice_map,
    )
    from apps.license.services.canonical_ledger_service import CanonicalLedgerService

    # Fetch canonical dataset once (Phase 4E-D: single authoritative source)
    canonical_data = CanonicalLedgerService.build_canonical_ledger_dataset(
        license_id=license_obj.id,
        license_type='DFIA'
    )

    # Build balance map: transaction_id → running_balance
    canonical_balance_map = {
        txn['id']: txn['license_running_balance']
        for txn in canonical_data.get('transactions', [])
    }

    alloc_map = boe_invoice_allocation_map(license_obj)
    ext_map = boe_external_invoice_map(license_obj)
    financial_rows, financial_summary = LicenseBalanceLedgerBuilder.build_financial_ledger(
        license_obj,
        alloc_map,
        ext_map,
        canonical_balance_map=canonical_balance_map,
        canonical_data=canonical_data
    )
    customs_rows, customs_summary = LicenseBalanceLedgerBuilder.build_customs_ledger(
        license_obj,
        show_hidden=show_hidden,
        canonical_balance_map=canonical_balance_map,
        canonical_data=canonical_data
    )
    timeline_events = LicenseBalanceLedgerBuilder.build_timeline(license_obj)
    reconciliation = LicenseBalanceLedgerBuilder.build_reconciliation_summary(license_obj, financial_summary, customs_summary)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    _write_financial_ledger_sheet(wb, financial_rows, financial_summary)
    _write_customs_ledger_sheet(wb, customs_rows, customs_summary)
    _write_timeline_sheet(wb, timeline_events)
    _write_reconciliation_sheet(wb, license_obj, financial_summary, customs_summary, reconciliation)
    _write_audit_log_sheet(wb, license_obj)

    # ── Save ──────────────────────────────────────────────────────────────
    # Recalculate formulas (e.g. the Plan Utilization TOTAL =SUM) on open so
    # viewers show computed values, not blank cached results.
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
