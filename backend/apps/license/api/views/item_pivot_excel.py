"""
Item Pivot Report - Excel rendering (export_to_excel_streaming).
"""

import logging
from decimal import Decimal, InvalidOperation


logger = logging.getLogger(__name__)

from apps.license.api.views.item_pivot_helpers import (
    _pivot_item_fill,
    _pivot_item_fields,
    _fit_sheet_columns,
    TOTAL_SUMMARY_TITLE,
    _item_summary_rows_from_projection,
    _item_summary_subtotal,
    _write_item_summary_table,
    _xlsx_safe_row,
    _planning_split_sheet_rows,
    _write_notification_summary_block,
)


_XLSX_TEXT_ITEM_FIELDS = ("hsn_code", "description")


def _xlsx_number(value):
    """The canonical JSON carries Decimals as strings; write them as numeric cells (exact Decimal, no arithmetic)."""
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return value
    return value


def _xlsx_item_value(key, value):
    return value if key in _XLSX_TEXT_ITEM_FIELDS else _xlsx_number(value)


class ItemPivotExcelMixin:
    """Mixin holding methods moved verbatim from ItemPivotReportView."""

    def export_to_excel_streaming(self, days=30, sion_norm=None, company_ids=None,
                                  exclude_company_ids=None, min_balance=200, license_status='active',
                                  expiry_date_from=None, expiry_date_to=None, purchase_status=None,
                                  license_numbers=None):
        """
        Export report to Excel - uses existing generate_report for data, then formats as Excel.
        This ensures consistency with JSON output.

        Returns:
            StreamingHttpResponse with Excel file
        """
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.cell import WriteOnlyCell
        from django.http import StreamingHttpResponse
        import tempfile
        import os
        from apps.license.utils.condition_excel import annotate_cell as _annotate_condition_cell

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_file.close()

        try:
            # Use the working generate_report method
            report_data = self.generate_report(days, sion_norm, company_ids, exclude_company_ids, min_balance, license_status, expiry_date_from, expiry_date_to, purchase_status, license_numbers=license_numbers)

            # Export the exact canonical matrix used by the React pivot.  Do
            # not re-run any plan/usage arithmetic in the spreadsheet path.
            # Use a regular workbook (not write_only) so we can merge cells
            # for the SION group header rows.
            if "groups" in report_data:
                workbook = openpyxl.Workbook()
                workbook.remove(workbook.active)  # remove default sheet
                fixed = ["SR NO", "DFIA NO", "EXPIRY DT", "EXPORTER", "TOTAL CIF", "DEBITED CIF", "ALLOTTED CIF", "PLANNED CIF", "BALANCE CIF"]
                headerFill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
                headerFont = Font(bold=True, size=11)
                sheet = None  # stays None when no group matched the filters
                for group_index, group in enumerate(report_data["groups"], 1):
                    notification_num = group['notification_number'] or 'Pivot'
                    safe_notification = notification_num[:24].replace('/', '-').replace('\\', '-').replace('*', '-').replace('?', '-').replace(':', '-').replace('[', '-').replace(']', '-')
                    sheet = workbook.create_sheet(title=f"{safe_notification}-{group_index}")

                    # Row 1: Title
                    titleRow = 1
                    sheet.cell(row=titleRow, column=1, value=f"Notification Number: {group['notification_number']}")
                    sheet.cell(row=titleRow, column=2, value=group["purchase_status"]["name"])
                    sheet.cell(row=titleRow, column=3, value=f"{group['license_count']} Licences")

                    # Row 2: Blank separator
                    # Row 3: Product category header (merged cells per category)
                    # Row 4: SION group header (merged cells per SION)
                    # Row 5: Item name header (merged cells per item)
                    # Row 6: Field sub-headers (HSN, DESCRIPTION, etc.)
                    # Row 7+: Data rows

                    item_groups = group["item_groups"]
                    numItems = len(item_groups)
                    numFixed = len(fixed)

                    # Item blocks have different widths (RUTILE adds UNIT PRICE, hidden fields drop out);
                    # offsets are cumulative.
                    item_fields = [_pivot_item_fields(item, group) for item in item_groups]
                    item_widths = [len(fields_for_item) for fields_for_item in item_fields]
                    item_starts = [sum(item_widths[:i]) for i in range(numItems)]
                    column_items = [item_idx for item_idx, width in enumerate(item_widths) for _ in range(width)]

                    # Build product category spans: list of (category, startItemIndex, endItemIndex)
                    category_spans = []
                    if numItems > 0:
                        current_category = item_groups[0].get("product_category") or "UNCLASSIFIED"
                        span_start = 0
                        for i in range(1, numItems):
                            item_category = item_groups[i].get("product_category") or "UNCLASSIFIED"
                            if item_category != current_category:
                                category_spans.append((current_category, span_start, i - 1))
                                current_category = item_category
                                span_start = i
                        category_spans.append((current_category, span_start, numItems - 1))


                    # Row 2: Product category header row (row 1 carries the notification title)
                    categoryRow = 2
                    # Fixed columns span 2 rows (Category + Field)
                    for col_idx, name in enumerate(fixed, 1):
                        cell = sheet.cell(row=categoryRow, column=col_idx, value=name)
                        cell.font = headerFont
                        cell.fill = headerFill
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                    # Product category merged cells
                    for cat_name, start_item, end_item in category_spans:
                        start_col = numFixed + item_starts[start_item] + 1
                        end_col = numFixed + item_starts[end_item] + item_widths[end_item]
                        cell = sheet.cell(row=categoryRow, column=start_col, value=cat_name)
                        cell.font = Font(bold=True, size=11)
                        cell.fill = _pivot_item_fill(start_item)
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                        if start_col != end_col:
                            sheet.merge_cells(start_row=categoryRow, start_column=start_col, end_row=categoryRow, end_column=end_col)

                    # Row 3: Field sub-headers
                    fieldRow = 3
                    for col_idx, name in enumerate(fixed, 1):
                        cell = sheet.cell(row=fieldRow, column=col_idx, value=name)
                        cell.font = headerFont
                        cell.fill = headerFill
                        cell.alignment = Alignment(horizontal='center', vertical='center')

                    for item_idx, item in enumerate(item_groups):
                        for field_idx, (_key, name) in enumerate(item_fields[item_idx]):
                            col = numFixed + item_starts[item_idx] + field_idx + 1
                            cell = sheet.cell(row=fieldRow, column=col, value=name)
                            cell.font = headerFont
                            cell.fill = _pivot_item_fill(item_idx)
                            cell.alignment = Alignment(horizontal='center', vertical='center')

                    # Merge fixed columns across both header rows (rows 1-2)
                    for col_idx in range(1, numFixed + 1):
                        sheet.merge_cells(start_row=categoryRow, start_column=col_idx, end_row=fieldRow, end_column=col_idx)

                    # Data rows start at row 4
                    dataStartRow = 4
                    for index, license_row in enumerate(group["licenses"], dataStartRow):
                        row_data = [index - (dataStartRow - 1), license_row["license_number"], license_row["expiry_date"], license_row["exporter"]] + [_xlsx_number(license_row[key]) for key in ("total_cif", "debited_cif", "allotted_cif", "planned_cif", "balance_cif")]
                        for item_idx, item in enumerate(item_groups):
                            cell = license_row["items"].get(item["key"])
                            row_data.extend(_xlsx_item_value(key, cell.get(key)) if cell else None for key, _label in item_fields[item_idx])
                        for col_idx, value in enumerate(row_data, 1):
                            cell = sheet.cell(row=index, column=col_idx, value=value)
                            if col_idx > numFixed:
                                cell.fill = _pivot_item_fill(column_items[col_idx - numFixed - 1])

                    # Totals row
                    totals = group["totals"]
                    totalRow = dataStartRow + len(group["licenses"])
                    total_row_data = [f"TOTAL — {group['license_count']} LICENCES", None, None, None] + [_xlsx_number(totals[key]) for key in ("total_cif", "debited_cif", "allotted_cif", "planned_cif", "balance_cif")]
                    for item_idx, item in enumerate(item_groups):
                        cell = totals["items"][item["key"]]
                        # Identity columns and RESTRICTION % carry no item total.
                        total_row_data.extend(
                            None if key in ("hsn_code", "description", "restriction_percent") else _xlsx_item_value(key, cell.get(key))
                            for key, _label in item_fields[item_idx]
                        )
                    totalFont = Font(bold=True, size=11)
                    totalFill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
                    for col_idx, value in enumerate(total_row_data, 1):
                        cell = sheet.cell(row=totalRow, column=col_idx, value=value)
                        cell.font = totalFont
                        cell.fill = _pivot_item_fill(column_items[col_idx - numFixed - 1]) if col_idx > numFixed else totalFill

                    # Item summary section
                    sheet.cell(row=totalRow + 1, column=1, value="")  # blank row
                    summaryStartRow = totalRow + 2
                    # Same heading and table as the on-screen "Item Summary — Notification … · …" card.
                    summaryTitle = f"Item Summary — Notification {group['notification_number']} · {group['purchase_status']['name']}"
                    # The same canonical projection as the screen and the TOTAL_Summary sheet (Item Name × SION), so the
                    # total is the exact sum of the notification summaries.
                    notification_rows = _item_summary_rows_from_projection(group.get("item_summary", []))
                    _write_item_summary_table(sheet, summaryStartRow, summaryTitle, notification_rows, _item_summary_subtotal(notification_rows), headerFont, headerFill)

                if sheet is not None:
                    _fit_sheet_columns(sheet)

                # ``_Summary`` keeps this additive sheet distinct from the
                # existing per-notification matrix sheets for consumers that
                # discover those sheets by name.
                summary_sheet = workbook.create_sheet(title="TOTAL_Summary")
                summary_rows = _item_summary_rows_from_projection(report_data.get("grand_total", {}).get("item_summary", []))
                _write_item_summary_table(summary_sheet, 1, TOTAL_SUMMARY_TITLE, summary_rows, _item_summary_subtotal(summary_rows), headerFont, headerFill)
                _fit_sheet_columns(summary_sheet)
                workbook.save(temp_file.name)
                def canonical_stream():
                    with open(temp_file.name, 'rb') as generated:
                        yield from iter(lambda: generated.read(8192), b'')
                    os.unlink(temp_file.name)
                response = StreamingHttpResponse(canonical_stream(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = 'attachment; filename="item_pivot_report.xlsx"'
                return response

            workbook = openpyxl.Workbook(write_only=True)
            licenses_by_norm_notif = report_data.get('licenses_by_norm_notification', {})

            for norm_class in sorted(licenses_by_norm_notif.keys()):
                notifications_dict = licenses_by_norm_notif[norm_class]
                for notification, licenses_list in sorted(notifications_dict.items()):
                    # Filter items to only those with actual data in THIS norm-notification.
                    # Must check plan_quantity / plan_cif in addition to quantity: for
                    # manually-planned items whose planned name (e.g. "SWP - E1") is not
                    # a direct import item, quantity = 0 but plan_quantity > 0.
                    items_with_data = []
                    for item in report_data['items']:
                        item_name = item['name']
                        has_data = any(
                            lic['items'].get(item_name, {}).get('quantity', 0) > 0
                            or lic['items'].get(item_name, {}).get('available_quantity', 0) > 0
                            or (lic['items'].get(item_name, {}).get('plan_quantity') or 0) > 0
                            or (lic['items'].get(item_name, {}).get('plan_cif') or 0) > 0
                            for lic in licenses_list
                        )
                        if has_data:
                            items_with_data.append(item)

                    # Create sheet
                    sheet_name = f"{norm_class}_{notification}"[:31].replace('/', '-').replace('\\', '-').replace('*', '-')
                    worksheet = workbook.create_sheet(title=sheet_name)

                    # Title row
                    title_cell = WriteOnlyCell(worksheet, value=f"Item Pivot Report - {norm_class} - {notification}")
                    title_cell.font = Font(bold=True, size=14)
                    title_cell.alignment = Alignment(horizontal='center')
                    worksheet.append(_xlsx_safe_row([title_cell] + [None] * 25))
                    worksheet.append([])

                    # Headers
                    base_headers = ['Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt', 'Exporter', 'Total CIF', 'Debited CIF', 'Alloted CIF', 'Balance CIF', 'Notes', 'Condition Sheet']
                    item_headers = []
                    for item in items_with_data:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        headers = [
                            f"{item_name} HSN Code",
                            f"{item_name} Product Description",
                            f"{item_name} Total QTY",
                            f"{item_name} Allotted QTY",
                            f"{item_name} Debited QTY",
                            f"{item_name} Balance QTY"
                        ]
                        headers.extend([
                            f"{item_name} Import Item Name",
                            f"{item_name} Import Qty",
                        ])
                        if has_restriction:
                            headers.extend([
                                f"{item_name} Restriction %",
                                f"{item_name} Restriction Value"
                            ])
                        # Two new per-item columns sourced from the
                        # e1_plan / e5_plan waterfall so the Excel matches
                        # the bulk Balance report cell-for-cell.
                        headers.extend([
                            f"{item_name} Plan Qty",
                            f"{item_name} Remaining CIF",
                        ])
                        item_headers.extend(headers)

                    all_headers = base_headers + item_headers
                    header_row = []
                    for header in all_headers:
                        cell = WriteOnlyCell(worksheet, value=header)
                        cell.font = Font(bold=True, color='FFFFFF')
                        cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                        cell.alignment = Alignment(horizontal='center', wrap_text=True)
                        header_row.append(cell)
                    worksheet.append(_xlsx_safe_row(header_row))

                    # Data rows
                    for idx, lic in enumerate(licenses_list, 1):
                        row_data = [
                            idx,
                            lic['license_number'],
                            lic['license_date'],
                            lic['license_expiry_date'],
                            lic['exporter'],
                            lic['total_cif'],
                            lic.get('debited_cif', 0),
                            lic['alloted_cif'],
                            lic['balance_cif'],
                            lic.get('balance_report_notes', ''),
                            lic.get('condition_sheet', '')
                        ]

                        for item in items_with_data:
                            item_name = item['name']
                            has_restriction = item.get('has_restriction', False)
                            item_data = lic['items'].get(item_name, {})
                            cond = item_data.get('condition_type') or ''
                            # When this column is backed by more than one
                            # distinct import item, `hs_code`/`description`
                            # are blank (see _build_license_row — a string
                            # can't be merged across items). Match the UI's
                            # own handling instead of leaving the Excel cell
                            # empty: list each import item's own HSN/
                            # Description on its own line within the cell —
                            # never joined without a separator, never one
                            # value picked over another.
                            _pits = item_data.get('planned_import_items') or []
                            if len(_pits) > 1:
                                _hsn_value = '\n'.join(p.get('hs_code') or '-' for p in _pits)
                                _desc_value = '\n'.join(p.get('description') or '-' for p in _pits)
                            else:
                                _hsn_value = item_data.get('hs_code', '')
                                _desc_value = item_data.get('description', '')
                            # Tint the HSN-code cell for this (licence, item)
                            # pair when a condition is set.
                            hsn_cell = WriteOnlyCell(worksheet, value=_hsn_value)
                            _annotate_condition_cell(hsn_cell, cond)
                            if len(_pits) > 1:
                                hsn_cell.alignment = Alignment(wrap_text=True, vertical='top')
                            row_data.append(hsn_cell)
                            desc_cell = WriteOnlyCell(worksheet, value=_desc_value)
                            if len(_pits) > 1:
                                desc_cell.alignment = Alignment(wrap_text=True, vertical='top')
                            row_data.append(desc_cell)
                            row_data.extend([
                                item_data.get('quantity', 0),
                                item_data.get('allotted_quantity', 0),
                                item_data.get('debited_quantity', 0),
                                item_data.get('available_quantity', 0)
                            ])
                            row_data.extend([
                                item_data.get('import_item_name', ''),
                                item_data.get('import_quantity', 0),
                            ])
                            if has_restriction:
                                row_data.extend([
                                    item_data.get('restriction'),
                                    item_data.get('restriction_value', 0)
                                ])
                            # Per-product: manual plan if this product was manually
                            # planned; else norm-derived unit price / planned CIF.
                            # First column is a display convention (quantity when
                            # manually planned, else the unit price rate) — not a
                            # business calculation. Second column is the CIF value
                            # itself, using the single backend selection rule
                            # (_effective_planned_cif / `effective_planned_cif`).
                            _s_plan_q = item_data.get('plan_quantity') or 0
                            _s_plan_c = item_data.get('plan_cif') or 0
                            if _s_plan_q or _s_plan_c:
                                row_data.append(_s_plan_q or 0)
                            else:
                                row_data.append(item_data.get('unit_price') or 0)
                            row_data.append(item_data.get('effective_planned_cif', 0))

                        worksheet.append(_xlsx_safe_row(row_data))

                    # Totals row — reads the backend-computed totals for
                    # this (norm, notification) group; writes only, no
                    # aggregation happens here (Phase 2B.2A; see
                    # docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md).
                    # base_headers = ['Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt',
                    #   'Exporter', 'Total CIF', 'Debited CIF', 'Alloted CIF',
                    #   'Balance CIF', 'Notes', 'Condition Sheet']
                    # 'TOTAL' lands under col 1 (Sr no); cols 2-5 (DFIA No/DFIA
                    # Dt/Expiry Dt/Exporter) are blank; cols 6-9 are the four
                    # CIF sums; cols 10-11 (Notes/Condition Sheet) are blank.
                    group_totals = report_data.get('notification_totals', {}).get(norm_class, {}).get(notification, {})
                    item_totals = group_totals.get('items', {})

                    totals_row = [WriteOnlyCell(worksheet, value='TOTAL')]
                    totals_row[0].font = Font(bold=True)
                    totals_row.extend([None, None, None, None])  # DFIA No, DFIA Dt, Expiry Dt, Exporter

                    total_cif_cell = WriteOnlyCell(worksheet, value=group_totals.get('total_cif', 0))
                    total_cif_cell.font = Font(bold=True)
                    totals_row.append(total_cif_cell)

                    debited_cif_cell = WriteOnlyCell(worksheet, value=group_totals.get('debited_cif', 0))
                    debited_cif_cell.font = Font(bold=True)
                    totals_row.append(debited_cif_cell)

                    alloted_cif_cell = WriteOnlyCell(worksheet, value=group_totals.get('alloted_cif', 0))
                    alloted_cif_cell.font = Font(bold=True)
                    totals_row.append(alloted_cif_cell)

                    balance_cif_cell = WriteOnlyCell(worksheet, value=group_totals.get('balance_cif', 0))
                    balance_cif_cell.font = Font(bold=True)
                    totals_row.append(balance_cif_cell)

                    totals_row.extend([None, None])  # Notes, Condition Sheet

                    for item in items_with_data:
                        item_name = item['name']
                        has_restriction = item.get('has_restriction', False)
                        item_total = item_totals.get(item_name, {})
                        totals_row.extend([None, None])  # HSN, Description
                        for qty_type in ['quantity', 'allotted_quantity', 'debited_quantity', 'available_quantity']:
                            cell = WriteOnlyCell(worksheet, value=item_total.get(qty_type, 0))
                            cell.font = Font(bold=True)
                            totals_row.append(cell)
                        totals_row.extend([None, None])  # Import Item Name, Import Qty
                        if has_restriction:
                            totals_row.append(None)  # Restriction %
                            cell = WriteOnlyCell(worksheet, value=item_total.get('restriction_value', 0))
                            cell.font = Font(bold=True)
                            totals_row.append(cell)
                        # Plan Qty total: a literal sum of plan_quantity only,
                        # matching the on-screen report's `totalPlanQty` total
                        # (frontend/src/pages/reports/ItemPivotReport.tsx). Rows
                        # with no manual plan (norm-derived, shown as a unit-price
                        # rate per-row) contribute 0 here rather than being folded
                        # into a blended rate.
                        cell = WriteOnlyCell(worksheet, value=item_total.get('plan_quantity', 0))
                        cell.font = Font(bold=True)
                        totals_row.append(cell)

                        # Planned CIF total: the single manual-vs-norm selection
                        # rule (_effective_planned_cif), already resolved per
                        # cell and summed by the backend.
                        cell = WriteOnlyCell(worksheet, value=item_total.get('effective_planned_cif', 0))
                        cell.font = Font(bold=True)
                        totals_row.append(cell)

                    worksheet.append(_xlsx_safe_row(totals_row))

                    # Notification Summary (Phase 2B.2B, §7 step 6) — appended
                    # directly after the TOTAL row on this same sheet, reading
                    # verbatim off `report_data['notification_summary']` (no
                    # new backend computation; see design doc §8).
                    notif_summary = report_data.get('notification_summary', {}).get(
                        norm_class, {}
                    ).get(notification, {})
                    _write_notification_summary_block(
                        worksheet, notif_summary, 'Notification Summary'
                    )

                # Norm Summary (Phase 2B.2B, §7 step 6) — one additional
                # sheet per norm, flattened across that norm's notification
                # groups, reading verbatim off `report_data['norm_summary']`.
                # Sheet-per-(norm,notification) is this exporter's existing
                # layout; there is no single existing sheet to append a
                # norm-level summary to, so a dedicated `{norm}_Summary`
                # sheet is created once the inner notification loop finishes.
                norm_summary_data = report_data.get('norm_summary', {}).get(norm_class, {})
                norm_summary_sheet_name = f"{norm_class}_Summary"[:31].replace(
                    '/', '-'
                ).replace('\\', '-').replace('*', '-')
                norm_summary_ws = workbook.create_sheet(title=norm_summary_sheet_name)
                _write_notification_summary_block(
                    norm_summary_ws, norm_summary_data, 'Norm Summary'
                )

            # "Planning Splits" — a separate sheet listing every visible
            # LicenseItemPlan split (flat, one row each) across all licenses
            # in this report. Additive detail; the pivot grid's per-item-name
            # Plan Qty / Plan CIF cells above are unchanged.
            split_rows = _planning_split_sheet_rows(
                licenses_by_norm_notif,
                [item['name'] for item in report_data['items']],
            )
            splits_ws = workbook.create_sheet(title="Planning Splits")
            split_header_row = []
            for header in ('License No', 'Product', 'Item Name', 'Split',
                           'Unit Price', 'Remaining Qty', 'Remaining CIF'):
                cell = WriteOnlyCell(splits_ws, value=header)
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
                split_header_row.append(cell)
            splits_ws.append(_xlsx_safe_row(split_header_row))
            for split_row in split_rows:
                splits_ws.append(_xlsx_safe_row(list(split_row)))

            # Save workbook
            workbook.save(temp_file.name)
            workbook.close()

            # Stream file
            def file_iterator(file_path, chunk_size=8192):
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

            response = StreamingHttpResponse(
                file_iterator(temp_file.name),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="item_pivot_report.xlsx"'
            return response

        except Exception as e:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
            raise e
