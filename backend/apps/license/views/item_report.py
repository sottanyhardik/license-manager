"""
Item Report - List all License Import Items with filters and inline editing support
"""

import logging

from django.db.models import Prefetch
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from apps.accounts.permissions import ReportPermission
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class _ExcelPassthroughRenderer(BaseRenderer):
    """
    Dummy renderer that tells DRF 'excel' is an accepted format so that
    ?format=excel (or ?_format=excel) does not fail content negotiation.
    The view returns a plain Django HttpResponse for Excel which DRF
    passes through without calling this renderer at all.
    """
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    format = 'excel'
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data  # never reached — view returns HttpResponse directly


logger = logging.getLogger(__name__)


class ItemReportView(APIView):
    """
    Report showing all License Import Items with filters.

    GET parameters:
        - item_names: Comma-separated item name IDs for filtering (multiselect)
        - format / _format: 'json' or 'excel' (default: json)
    """
    permission_classes = [ReportPermission]
    # Register the excel "format" so DRF content negotiation accepts
    # ?format=excel (or ?_format=excel) without raising NotAcceptable (406).
    renderer_classes = [JSONRenderer, _ExcelPassthroughRenderer]

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
        Generate item report driven by LicenseItemPlan records.

        Each row in the report corresponds to one plan line so that the
        'Item Name' filter targets the *planned* item name (e.g. 'SWP - E5',
        'DWP - E5') rather than the raw import-item M2M tag.

        Returns:
            Dictionary with report data.
        """
        from datetime import date, timedelta
        from apps.license.models import LicenseItemPlan, LicenseTransferModel

        today = date.today()

        # ── Build the plan queryset ───────────────────────────────────────────
        latest_transfer_prefetch = Prefetch(
            'import_item__license__transfers',
            queryset=LicenseTransferModel.objects.select_related(
                'from_company', 'to_company'
            ).order_by('-transfer_date', '-transfer_initiation_date'),
            to_attr='latest_transfers',
        )

        plans = (
            LicenseItemPlan.objects
            .select_related(
                'item_name',
                'import_item',
                'import_item__hs_code',
                'import_item__license',
                'import_item__license__exporter',
                'import_item__license__ownership__current_owner',
                'import_item__license__balance',
                'import_item__license__notes',
                'import_item__license__notification_number',
                'import_item__license__purchase_status',
            )
            .prefetch_related(
                latest_transfer_prefetch,
                'import_item__items',
            )
        )

        # ── License-level filters ─────────────────────────────────────────────
        if license_status == 'active':
            plans = plans.filter(
                import_item__license__flags__is_active=True,
                import_item__license__license_expiry_date__gt=today - timedelta(days=30),
            )
        elif license_status == 'expired':
            plans = plans.filter(import_item__license__license_expiry_date__lt=today)
        elif license_status == 'expiring_soon':
            plans = plans.filter(
                import_item__license__flags__is_active=True,
                import_item__license__license_expiry_date__gte=today,
                import_item__license__license_expiry_date__lte=today + timedelta(days=30),
            )

        if expiry_date_from:
            from datetime import datetime as _dt
            plans = plans.filter(
                import_item__license__license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date()
            )
        if expiry_date_to:
            from datetime import datetime as _dt
            plans = plans.filter(
                import_item__license__license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date()
            )

        if min_balance > 0:
            plans = plans.filter(import_item__available_value__gte=min_balance)
        if min_avail_qty > 0:
            plans = plans.filter(import_item__available_quantity__gte=min_avail_qty)

        if company_ids:
            cids = [int(c.strip()) for c in company_ids.split(',') if c.strip()]
            plans = plans.filter(import_item__license__exporter_id__in=cids)
        if exclude_company_ids:
            eids = [int(c.strip()) for c in exclude_company_ids.split(',') if c.strip()]
            plans = plans.exclude(import_item__license__exporter_id__in=eids)

        if purchase_status:
            ps_list = [p.strip() for p in purchase_status.split(',') if p.strip()]
            plans = plans.filter(import_item__license__purchase_status__code__in=ps_list)

        if product_description:
            plans = plans.filter(import_item__description__icontains=product_description)
        if hsn_code:
            plans = plans.filter(import_item__hs_code__hs_code__icontains=hsn_code)

        if norms:
            norms_list = [n.strip() for n in norms.split(',') if n.strip()]
            plans = plans.filter(
                import_item__items__sion_norm_class__norm_class__in=norms_list
            ).distinct()

        if notification_numbers:
            notif_list = [n.strip() for n in notification_numbers.split(',') if n.strip()]
            plans = plans.filter(
                import_item__license__notification_number__in=notif_list
            ).distinct()

        # ── Plan item-name filter (the primary use-case) ──────────────────────
        if item_names:
            item_name_ids = [int(i.strip()) for i in item_names.split(',') if i.strip()]
            plans = plans.filter(item_name__id__in=item_name_ids)

        if is_restricted is not None:
            if is_restricted == 'true':
                plans = plans.filter(import_item__is_restricted=True)
            elif is_restricted == 'false':
                plans = plans.filter(import_item__is_restricted=False)

        plans = plans.order_by(
            'import_item__license__license_number',
            'import_item__serial_number',
            'item_name__name',
        )

        # ── Build report rows ─────────────────────────────────────────────────
        report_items = []
        for plan in plans:
            ii = plan.import_item
            lic = ii.license

            latest_transfer_info = None
            transfers = getattr(lic, 'latest_transfers', None)
            if transfers:
                latest_transfer_info = str(transfers[0])

            import_item_names = [
                {'id': n.id, 'name': n.name} for n in ii.items.all()
            ]
            planned_item_name = plan.item_name.name if plan.item_name else None

            report_items.append({
                'id':                   ii.id,
                'plan_id':              plan.id,
                'license_id':           lic.id,
                'license_number':       lic.license_number,
                'license_date':         lic.license_date.isoformat() if lic.license_date else None,
                'license_expiry_date':  lic.license_expiry_date.isoformat() if lic.license_expiry_date else None,
                'ledger_date':          lic.ledger_date.isoformat() if lic.ledger_date else None,
                'exporter_name':        lic.exporter.name if lic.exporter else None,
                'current_owner':        lic.current_owner.name if lic.current_owner else None,
                'latest_transfer':      latest_transfer_info,
                'hs_code':              ii.hs_code.hs_code if ii.hs_code else None,
                'product_description':  ii.description or '',
                'serial_number':        ii.serial_number,
                'unit':                 ii.unit,
                'condition_type':       ii.condition_type or '',
                'is_restricted':        ii.is_restricted,
                # Import reference quantities
                'quantity':             float(ii.quantity or 0),
                'available_quantity':   float(ii.available_quantity or 0),
                'available_balance':    float(ii.available_value or 0),
                'balance_cif':          float(lic.balance_cif or 0),
                # Import item names (M2M tags on the import item row)
                'item_names':           import_item_names,
                # ── Plan data (primary output) ────────────────────────────────
                'planned_item_name':    planned_item_name,
                'planned_item_name_id': plan.item_name_id,
                'planned_quantity':     float(plan.planned_quantity or 0),
                'unit_price':           float(plan.unit_price or 0),
                'planned_cif':          float(plan.planned_cif_fc or 0),
                'plan_note':            plan.note or '',
                # House-keeping
                'notes':                lic.balance_report_notes or '',
                'condition_sheet':      lic.condition_sheet or '',
            })

        return {
            'report_date': date.today().isoformat(),
            'total_items': len(report_items),
            'items': report_items,
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

        # Headers — plan-driven: Planned Item Name + plan figures are primary.
        headers = [
            'Sr No', 'License No', 'License Date', 'License Expiry Date', 'Ledger Date', 'Exporter Name',
            'Serial Number', 'Condition', 'HSN Code', 'Product Description',
            'Planned Item Name',        # from LicenseItemPlan.item_name
            'Available Quantity', 'Available Balance', 'Balance CIF',
            'Notes', 'Condition Sheet', 'Transfer Status',
            'Planned Qty', 'Unit Price', 'Planned CIF',
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
            ws.column_dimensions['K'].width = 28  # Planned Item Name
            ws.column_dimensions['L'].width = 18  # Available Quantity
            ws.column_dimensions['M'].width = 18  # Available Balance
            ws.column_dimensions['N'].width = 18  # Balance CIF
            ws.column_dimensions['O'].width = 30  # Notes
            ws.column_dimensions['P'].width = 30  # Condition Sheet
            ws.column_dimensions['Q'].width = 35  # Transfer Status
            ws.column_dimensions['R'].width = 14  # Planned Qty
            ws.column_dimensions['S'].width = 14  # Unit Price
            ws.column_dimensions['T'].width = 16  # Planned CIF

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

                # Add each plan line in this license group
                for item_idx, item in enumerate(license_items):
                    # License-level columns (first row only — merged below)
                    if item_idx == 0:
                        ws.cell(row=current_row, column=1, value=sr_no)
                        ws.cell(row=current_row, column=2, value=_safe(item['license_number']))
                        ws.cell(row=current_row, column=3, value=_safe(item['license_date']))
                        ws.cell(row=current_row, column=4, value=_safe(item['license_expiry_date']))
                        ws.cell(row=current_row, column=5, value=_safe(item.get('ledger_date')))
                        ws.cell(row=current_row, column=6, value=_safe(item['exporter_name']))
                        ws.cell(row=current_row, column=13, value=item['available_balance'])
                        ws.cell(row=current_row, column=14, value=item['balance_cif'])
                        ws.cell(row=current_row, column=15, value=_safe(item['notes']))
                        ws.cell(row=current_row, column=16, value=_safe(item['condition_sheet']))
                        ws.cell(row=current_row, column=17, value=_safe(item.get('latest_transfer', '')))

                    # Plan-line columns (one row per plan entry)
                    sn_cell   = ws.cell(row=current_row, column=7,  value=item['serial_number'])
                    cond      = item.get('condition_type') or ''
                    cond_cell = ws.cell(row=current_row, column=8,  value=cond)
                    _annotate_condition_cell(sn_cell, cond)
                    _annotate_condition_cell(cond_cell, cond)
                    ws.cell(row=current_row, column=9,  value=_safe(item['hs_code']))
                    ws.cell(row=current_row, column=10, value=_safe(item['product_description']))
                    ws.cell(row=current_row, column=11, value=_safe(item.get('planned_item_name') or ''))  # Planned Item Name
                    ws.cell(row=current_row, column=12, value=item['available_quantity'])
                    ws.cell(row=current_row, column=18, value=item.get('planned_quantity') or 0)           # Planned Qty
                    ws.cell(row=current_row, column=19, value=item.get('unit_price') or 0)                 # Unit Price
                    ws.cell(row=current_row, column=20, value=item.get('planned_cif') or 0)                # Planned CIF

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
        Return the distinct planned item names that appear in LicenseItemPlan
        for active licenses with balance > 0.

        These are the names users can filter by (e.g. 'SWP - E5', 'DWP - E5').
        Showing import-side item names here would be misleading because the
        report is now driven by the plan, not the import M2M tags.
        Returns: List of {id, name} dicts ordered by name.
        """
        from apps.license.models import LicenseItemPlan
        item_names = (
            ItemNameModel.objects
            .filter(
                plan_lines__isnull=False,                          # has at least one plan line
                plan_lines__import_item__available_value__gt=0,   # on an import item with balance
                plan_lines__import_item__license__flags__is_active=True,
            )
            .distinct()
            .order_by('name')
            .values('id', 'name')
        )
        return Response(list(item_names))
