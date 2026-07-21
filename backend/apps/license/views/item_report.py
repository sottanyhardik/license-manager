"""
Item Report - List all License Import Items with filters and inline editing support
"""

import logging

from django.db.models import Prefetch
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.accounts.permissions import ReportPermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel

def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default



logger = logging.getLogger(__name__)


class ItemReportView(APIView):
    """
    Report showing all License Import Items with filters.

    GET parameters:
        - item_names: Comma-separated item name IDs for filtering (multiselect)
        - format: 'json' or 'excel' (default: json)
    """
    permission_classes = [ReportPermission]

    def get(self, request, *args, **kwargs):
        # DRF intercepts ?format= as a content-negotiation override and raises
        # NotAcceptable for unknown formats like 'excel'.  The frontend sends
        # ?_format=excel (underscore prefix) to bypass that interception.
        # Support both forms for backward compatibility.
        output_format = (
            request.GET.get('_format')
            or request.GET.get('format', 'json')
        ).lower()
        item_names = request.GET.get('item_names')  # Comma-separated item name IDs
        company_ids = request.GET.get('company_ids')  # Comma-separated company IDs
        exclude_company_ids = request.GET.get('exclude_company_ids')  # Comma-separated company IDs to exclude
        min_balance = _safe_int(request.GET.get('min_balance'), 200)
        min_avail_qty = float(request.GET.get('min_avail_qty', 0))
        license_status = request.GET.get('license_status', 'active')
        is_restricted = request.GET.get('is_restricted')  # 'true', 'false', or None for all
        purchase_status = request.GET.get('purchase_status')  # Comma-separated purchase status codes
        product_description = request.GET.get('product_description')  # Product description search
        hsn_code = request.GET.get('hsn_code')  # HSN code search
        norms = request.GET.get('norms')  # Comma-separated SION norm classes
        notification_numbers = request.GET.get('notification_numbers')  # Comma-separated notification numbers
        expiry_date_from = request.GET.get('expiry_date_from')  # YYYY-MM-DD
        expiry_date_to = request.GET.get('expiry_date_to')      # YYYY-MM-DD

        if output_format == 'excel':
            try:
                return self.export_to_excel(item_names, company_ids, exclude_company_ids, min_balance, min_avail_qty, license_status, is_restricted, purchase_status, product_description, hsn_code, norms, notification_numbers, expiry_date_from, expiry_date_to)
            except Exception as e:
                logger.exception("Error exporting item report to Excel")
                return JsonResponse({'error': str(e)}, status=500)

        # For JSON, generate full report
        try:
            report_data = self.generate_report(item_names, company_ids, exclude_company_ids, min_balance, min_avail_qty, license_status, is_restricted, purchase_status, product_description, hsn_code, norms, notification_numbers, expiry_date_from, expiry_date_to)
        except Exception as e:
            logger.exception("Error generating item report")
            return JsonResponse({'error': str(e)}, status=500)

        return JsonResponse(report_data, safe=False)

    def generate_report(self, item_names=None, company_ids=None, exclude_company_ids=None, min_balance=200, min_avail_qty=0, license_status='active', is_restricted=None, purchase_status=None, product_description=None, hsn_code=None, norms=None, notification_numbers=None, expiry_date_from=None, expiry_date_to=None):
        """
        Generate item report with all license import items.

        Args:
            item_names: Comma-separated item name IDs for filtering
            company_ids: Comma-separated company IDs to include (optional)
            exclude_company_ids: Comma-separated company IDs to exclude (optional)
            min_balance: Minimum balance CIF to include (default 200)
            min_avail_qty: Minimum available quantity to include (default 0)
            license_status: Filter by status - 'active', 'expired', 'expiring_soon', 'all' (default 'active')
            is_restricted: Filter by restriction status - 'true', 'false', or None for all
            purchase_status: Comma-separated purchase status codes (e.g., 'GE,MI,SM')
            product_description: Search text for product description (case-insensitive contains search)
            hsn_code: Search text for HSN code (case-insensitive contains search)
            norms: Comma-separated SION norm classes (e.g., '019/2015,098/2009')
            notification_numbers: Comma-separated license notification numbers (e.g., '019/2015,098/2009')

        Returns:
            Dictionary with report data
        """
        from datetime import date, timedelta
        today = date.today()

        # Base query - all import items with licenses
        from apps.license.models import LicenseTransferModel

        # Prefetch only the latest transfer for each license
        latest_transfer_prefetch = Prefetch(
            'license__transfers',
            queryset=LicenseTransferModel.objects.select_related('from_company', 'to_company').order_by('-transfer_date', '-transfer_initiation_date'),
            to_attr='latest_transfers'
        )

        items = LicenseImportItemsModel.objects.select_related(
            'license',
            'license__exporter',
            'license__ownership__current_owner',
            'license__balance',        # fix N+1: balance_cif
            'license__notes',          # fix N+1: balance_report_notes, condition_sheet
            'license__notification_number',
            'license__purchase_status',
            'hs_code'
        ).prefetch_related('items', latest_transfer_prefetch)

        # Apply license status filter
        if license_status == 'active':
            items = items.filter(
                license__flags__is_active=True,
                license__license_expiry_date__gt=today - timedelta(days=30)
            )
        elif license_status == 'expired':
            items = items.filter(license__license_expiry_date__lt=today)
        elif license_status == 'expiring_soon':
            items = items.filter(
                license__flags__is_active=True,
                license__license_expiry_date__gte=today,
                license__license_expiry_date__lte=today + timedelta(days=30)
            )
        # If 'all', no date or is_active filter applied

        # Apply explicit expiry date range filter
        if expiry_date_from:
            from datetime import datetime as _dt
            items = items.filter(license__license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date())
        if expiry_date_to:
            from datetime import datetime as _dt
            items = items.filter(license__license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date())

        # Filter by min_balance using stored available_value field (can be done in query)
        # This pre-filters before iteration for better performance
        items = items.filter(available_value__gte=min_balance)

        # Filter by min_avail_qty (can be done in query)
        if min_avail_qty > 0:
            items = items.filter(available_quantity__gte=min_avail_qty)

        # Filter by company IDs if specified
        if company_ids:
            company_id_list = [int(cid.strip()) for cid in company_ids.split(',') if cid.strip()]
            items = items.filter(license__exporter_id__in=company_id_list)

        # Exclude company IDs if specified
        if exclude_company_ids:
            exclude_id_list = [int(cid.strip()) for cid in exclude_company_ids.split(',') if cid.strip()]
            items = items.exclude(license__exporter_id__in=exclude_id_list)

        # Filter by item names if specified
        if item_names:
            item_name_ids = [int(id.strip()) for id in item_names.split(',') if id.strip()]
            items = items.filter(items__id__in=item_name_ids).distinct()

        # Filter by is_restricted if specified
        if is_restricted is not None:
            if is_restricted == 'true':
                items = items.filter(is_restricted=True)
            elif is_restricted == 'false':
                items = items.filter(is_restricted=False)

        # Filter by purchase_status if specified
        if purchase_status:
            purchase_status_list = [ps.strip() for ps in purchase_status.split(',') if ps.strip()]
            items = items.filter(license__purchase_status__code__in=purchase_status_list)

        # Filter by product description if specified (case-insensitive contains search)
        if product_description:
            items = items.filter(description__icontains=product_description)

        # Filter by HSN code if specified (case-insensitive contains search)
        if hsn_code:
            items = items.filter(hs_code__hs_code__icontains=hsn_code)

        # Filter by norms (SION norm class) if specified
        if norms:
            norms_list = [n.strip() for n in norms.split(',') if n.strip()]
            items = items.filter(items__sion_norm_class__norm_class__in=norms_list).distinct()

        # Filter by notification numbers (license notification) if specified
        if notification_numbers:
            notification_list = [n.strip() for n in notification_numbers.split(',') if n.strip()]
            items = items.filter(license__notification_number__in=notification_list).distinct()

        # Order by license number and serial number
        items = items.order_by('license__license_number', 'serial_number')

        # Materialise the queryset once so the plan pre-fetch can use the IDs
        # without issuing a second DB round-trip.
        item_list = list(items)

        # Utilization plan per item. Per LICENSE we use the manual plan if one
        # exists, otherwise the norm (E1/E5/E132) plan — never both.
        # Pre-compute for ALL unique licenses in one pass rather than calling
        # effective_plan_for_license() inside the loop (was O(N) DB round-trips).
        from apps.license.services.plan_reporting import plan_map_for_import_items
        from apps.license.services.norm_plan import effective_plan_for_license
        manual_splits = plan_map_for_import_items([it.id for it in item_list])

        # Build per-license effective-plan cache from the already-loaded licenses
        # (select_related already pulled them; no extra queries needed here).
        _eff_cache: dict = {}
        seen_license_ids: set = set()
        for it in item_list:
            lid = it.license_id
            if lid not in seen_license_ids:
                seen_license_ids.add(lid)
                _eff_cache[lid] = effective_plan_for_license(it.license)

        # Build report data
        report_items = []
        for item in item_list:
            # Get item names
            item_names_list = [{"id": i.id, "name": i.name} for i in item.items.all()]
            _plan_source, _eff = _eff_cache[item.license_id]
            plan = _eff.get(item.id)
            _ms = manual_splits.get(item.id)

            # Use the stored available_value field (updated by balance update task)
            # This field already contains the correct value:
            # - For restricted items: restriction-based calculated value
            # - For non-restricted items: license balance_cif
            # Note: Make sure to run "Update Balance" in Item Pivot Report to refresh these values
            available_balance = float(item.available_value or 0)

            # Get latest transfer information
            latest_transfer_info = None
            if hasattr(item.license, 'latest_transfers') and item.license.latest_transfers:
                latest_transfer = item.license.latest_transfers[0]
                latest_transfer_info = str(latest_transfer)  # Uses the __str__ method which formats it nicely

            report_items.append({
                'id': item.id,
                'license_id': item.license.id,
                'license_number': item.license.license_number,
                'license_date': item.license.license_date.isoformat() if item.license.license_date else None,
                'license_expiry_date': item.license.license_expiry_date.isoformat() if item.license.license_expiry_date else None,
                'ledger_date': item.license.ledger_date.isoformat() if item.license.ledger_date else None,
                'exporter_name': item.license.exporter.name if item.license.exporter else None,
                'current_owner': item.license.current_owner.name if item.license.current_owner else None,
                'latest_transfer': latest_transfer_info,
                'hs_code': item.hs_code.hs_code if item.hs_code else None,
                'product_description': item.description or '',
                'item_names': item_names_list,
                'quantity': float(item.quantity or 0),
                'available_quantity': float(item.available_quantity or 0),
                'available_balance': available_balance,
                'balance_cif': float(item.license.balance_cif or 0),
                'is_restricted': item.is_restricted,
                'condition_type': item.condition_type or '',
                'notes': item.license.balance_report_notes or '',
                'condition_sheet': item.license.condition_sheet or '',
                'unit': item.unit,
                'serial_number': item.serial_number,
                # Effective plan (manual if the license is manually planned,
                # else norm). Splits are shown only for manual plans.
                'planned_quantity': plan['planned_quantity'] if plan else 0,
                'planned_cif': plan['planned_cif'] if plan else 0,
                'plan_source': _plan_source,
                'planned_splits': (_ms['splits'] if (_plan_source == 'manual' and _ms) else []),
            })

        return {
            'report_date': date.today().isoformat(),
            'total_items': len(report_items),
            'items': report_items
        }

    def export_to_excel(self, item_names=None, company_ids=None, exclude_company_ids=None, min_balance=200, min_avail_qty=0, license_status='active', is_restricted=None, purchase_status=None, product_description=None, hsn_code=None, norms=None, notification_numbers=None, expiry_date_from=None, expiry_date_to=None):
        """Export item report to Excel with separate sheets for Restricted and Not Restricted items"""
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
        from io import BytesIO
        from apps.license.utils.condition_excel import annotate_cell as _annotate_condition_cell

        # Strip control chars that openpyxl rejects (\x00-\x08, \x0b-\x0c, \x0e-\x1f).
        # PDF-sourced fields like condition_sheet sometimes carry these.
        def _safe(v):
            if isinstance(v, str):
                return ILLEGAL_CHARACTERS_RE.sub('', v)
            return v

        # Generate report data
        report_data = self.generate_report(item_names, company_ids, exclude_company_ids, min_balance, min_avail_qty, license_status, is_restricted, purchase_status, product_description, hsn_code, norms, notification_numbers, expiry_date_from, expiry_date_to)
        items = report_data['items']

        # Separate items into restricted and not restricted
        restricted_items = [item for item in items if item['is_restricted']]
        not_restricted_items = [item for item in items if not item['is_restricted']]

        # Create workbook
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet

        # Header style
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Headers — "Condition" sits next to "Serial Number" so it's obvious
        # which licence item the AU / N% restriction applies to.
        headers = [
            'Sr No', 'License No', 'License Date', 'License Expiry Date', 'Ledger Date', 'Exporter Name',
            'Serial Number', 'Condition', 'HSN Code', 'Product Description', 'Item Name',
            'Available Quantity', 'Available Balance', 'Balance CIF', 'Notes', 'Condition Sheet', 'Transfer Status',
            'Plan Qty', 'Plan CIF'
        ]

        def create_sheet(workbook, sheet_name, items_list):
            """Helper function to create a sheet with given items, grouped by license"""
            from openpyxl.styles import Border, Side

            ws = workbook.create_sheet(title=sheet_name)

            # Add headers
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment

            # Set column widths
            ws.column_dimensions['A'].width = 8   # Sr No
            ws.column_dimensions['B'].width = 18  # License No
            ws.column_dimensions['C'].width = 15  # License Date
            ws.column_dimensions['D'].width = 18  # License Expiry Date
            ws.column_dimensions['E'].width = 15  # Ledger Date
            ws.column_dimensions['F'].width = 25  # Exporter Name
            ws.column_dimensions['G'].width = 12  # Serial Number
            ws.column_dimensions['H'].width = 11  # Condition
            ws.column_dimensions['I'].width = 12  # HSN Code
            ws.column_dimensions['J'].width = 40  # Product Description
            ws.column_dimensions['K'].width = 25  # Item Name
            ws.column_dimensions['L'].width = 18  # Available Quantity
            ws.column_dimensions['M'].width = 18  # Available Balance
            ws.column_dimensions['N'].width = 18  # Balance CIF
            ws.column_dimensions['O'].width = 30  # Notes
            ws.column_dimensions['P'].width = 30  # Condition Sheet
            ws.column_dimensions['Q'].width = 35  # Transfer Status
            ws.column_dimensions['R'].width = 14  # Plan Qty
            ws.column_dimensions['S'].width = 16  # Plan CIF

            # Group items by license
            grouped_items = {}
            for item in items_list:
                license_id = item['license_id']
                if license_id not in grouped_items:
                    grouped_items[license_id] = []
                grouped_items[license_id].append(item)

            # Define border style for merged cells
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            # Add data rows with merged cells for same license
            current_row = 2
            sr_no = 1

            for license_id, license_items in grouped_items.items():
                row_span = len(license_items)
                start_row = current_row

                # Add each item in this license group
                for item_idx, item in enumerate(license_items):
                    item_names_str = ', '.join([i['name'] for i in item['item_names']])

                    # License-level columns (only for first row, will be merged)
                    if item_idx == 0:
                        ws.cell(row=current_row, column=1, value=sr_no)  # Sr No
                        ws.cell(row=current_row, column=2, value=_safe(item['license_number']))  # License No
                        ws.cell(row=current_row, column=3, value=_safe(item['license_date']))  # License Date
                        ws.cell(row=current_row, column=4, value=_safe(item['license_expiry_date']))  # License Expiry Date
                        ws.cell(row=current_row, column=5, value=_safe(item.get('ledger_date')))  # Ledger Date
                        ws.cell(row=current_row, column=6, value=_safe(item['exporter_name']))  # Exporter Name
                        ws.cell(row=current_row, column=13, value=item['available_balance'])  # Available Balance
                        ws.cell(row=current_row, column=14, value=item['balance_cif'])  # Balance CIF
                        ws.cell(row=current_row, column=15, value=_safe(item['notes']))  # Notes
                        ws.cell(row=current_row, column=16, value=_safe(item['condition_sheet']))  # Condition Sheet
                        ws.cell(row=current_row, column=17, value=_safe(item.get('latest_transfer', '')))  # Transfer Status

                    # Item-level columns (for each row)
                    sn_cell = ws.cell(row=current_row, column=7, value=item['serial_number'])  # Serial Number
                    cond = (item.get('condition_type') or '')
                    cond_cell = ws.cell(row=current_row, column=8, value=cond)  # Condition
                    # Tint both Serial-Number and Condition cells so the row
                    # stands out at a glance.
                    _annotate_condition_cell(sn_cell, cond)
                    _annotate_condition_cell(cond_cell, cond)
                    ws.cell(row=current_row, column=9, value=_safe(item['hs_code']))  # HSN Code
                    ws.cell(row=current_row, column=10, value=_safe(item['product_description']))  # Product Description
                    ws.cell(row=current_row, column=11, value=_safe(item_names_str))  # Item Name
                    ws.cell(row=current_row, column=12, value=item['available_quantity'])  # Available Quantity
                    # Utilization plan (per item) — appended so merged license
                    # columns (13–17) keep their indices.
                    ws.cell(row=current_row, column=18, value=item.get('planned_quantity') or 0)  # Plan Qty
                    ws.cell(row=current_row, column=19, value=item.get('planned_cif') or 0)  # Plan CIF

                    current_row += 1

                # Merge cells for license-level columns
                if row_span > 1:
                    end_row = start_row + row_span - 1

                    # Merge Sr No (column A / 1)
                    ws.merge_cells(start_row=start_row, start_column=1, end_row=end_row, end_column=1)
                    # Merge License No (column B / 2)
                    ws.merge_cells(start_row=start_row, start_column=2, end_row=end_row, end_column=2)
                    # Merge License Date (column C / 3)
                    ws.merge_cells(start_row=start_row, start_column=3, end_row=end_row, end_column=3)
                    # Merge License Expiry Date (column D / 4)
                    ws.merge_cells(start_row=start_row, start_column=4, end_row=end_row, end_column=4)
                    # Merge Ledger Date (column E / 5)
                    ws.merge_cells(start_row=start_row, start_column=5, end_row=end_row, end_column=5)
                    # Merge Exporter Name (column F / 6)
                    ws.merge_cells(start_row=start_row, start_column=6, end_row=end_row, end_column=6)
                    # Merge Available Balance (column M / 13)
                    ws.merge_cells(start_row=start_row, start_column=13, end_row=end_row, end_column=13)
                    # Merge Balance CIF (column N / 14)
                    ws.merge_cells(start_row=start_row, start_column=14, end_row=end_row, end_column=14)
                    # Merge Notes (column O / 15)
                    ws.merge_cells(start_row=start_row, start_column=15, end_row=end_row, end_column=15)
                    # Merge Condition Sheet (column P / 16)
                    ws.merge_cells(start_row=start_row, start_column=16, end_row=end_row, end_column=16)
                    # Merge Transfer Status (column Q / 17)
                    ws.merge_cells(start_row=start_row, start_column=17, end_row=end_row, end_column=17)

                    # Apply vertical center alignment to merged cells
                    for col in [1, 2, 3, 4, 5, 6, 13, 14, 15, 16, 17]:
                        cell = ws.cell(row=start_row, column=col)
                        cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
                        cell.border = thin_border

                sr_no += 1

            return ws

        # Create sheets (Restricted first, then Not Restricted)
        if restricted_items:
            create_sheet(wb, "Restricted", restricted_items)

        if not_restricted_items:
            create_sheet(wb, "Not Restricted", not_restricted_items)

        # If no items at all, create an empty sheet with message
        if not restricted_items and not not_restricted_items:
            ws = wb.create_sheet(title="No Data")
            ws.cell(row=1, column=1, value="No items found matching the filter criteria")

        # Save to bytes
        excel_file = BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        # Create response
        response = HttpResponse(
            excel_file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=item_report.xlsx'
        return response


class ItemReportViewSet(viewsets.ViewSet):
    """
    ViewSet for Item Report actions like getting available items for filter.
    """
    permission_classes = [ReportPermission]

    @action(detail=False, methods=['get'], url_path='available-items')
    def available_items(self, request):
        """
        Get item names that actually have linked import items with
        available_value > 0.  Only these names will produce results
        in the report, so showing the rest in the multi-select filter
        is misleading.
        Returns: List of {id, name} dicts ordered by name.
        """
        item_names = (
            ItemNameModel.objects
            .filter(
                is_active=True,
                license_import_item__available_value__gt=0,   # has plannable items
            )
            .distinct()
            .order_by('name')
            .values('id', 'name')
        )
        return Response(list(item_names))
