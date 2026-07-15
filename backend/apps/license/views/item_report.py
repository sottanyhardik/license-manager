# license/views/item_report.py
"""
Item Report — flat list of license import items with filters and Excel export.

Ported from legacy/backend/apps/license/views/item_report.py.

New backend field mapping vs legacy model:
  license_obj.balance_cif          → license_obj.balance.balance_cif
  license_obj.balance_report_notes → license_obj.notes.balance_report_notes
  license_obj.condition_sheet      → license_obj.notes.condition_sheet
  license_obj.current_owner        → license_obj.ownership.current_owner
  license_obj.ledger_date          → license_obj.balance.ledger_date

Routes registered in urls.py:
  GET  /api/v1/item-report/                → ItemReportViewSet.list
  GET  /api/v1/item-report/available-items/ → ItemReportViewSet.available_items
  GET  /api/v1/item-report/?format=excel    → ItemReportViewSet.list (Excel branch)
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Prefetch
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReportPermission
from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel, LicenseTransferModel

logger = logging.getLogger(__name__)

DEC_0 = Decimal("0")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_balance_cif(license_obj) -> Decimal:
    """Access balance_cif via the OneToOne LicenseBalance sub-table."""
    try:
        return license_obj.balance.balance_cif or DEC_0
    except Exception:
        return DEC_0


def _get_ledger_date(license_obj):
    """Access ledger_date via the OneToOne LicenseBalance sub-table."""
    try:
        return license_obj.balance.ledger_date
    except Exception:
        return None


def _get_balance_report_notes(license_obj) -> str:
    """Access balance_report_notes via the OneToOne LicenseNotes sub-table."""
    try:
        return license_obj.notes.balance_report_notes or ""
    except Exception:
        return ""


def _get_condition_sheet(license_obj) -> str:
    """Access condition_sheet via the OneToOne LicenseNotes sub-table."""
    try:
        return license_obj.notes.condition_sheet or ""
    except Exception:
        return ""


def _get_current_owner(license_obj):
    """Access current_owner via the OneToOne LicenseOwnership sub-table."""
    try:
        return license_obj.ownership.current_owner
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Report generation (shared between JSON and Excel branches)
# ---------------------------------------------------------------------------

def _generate_report(
    item_names=None,
    company_ids=None,
    exclude_company_ids=None,
    min_balance=200,
    min_avail_qty=0.0,
    license_status='active',
    is_restricted=None,
    purchase_status=None,
    product_description=None,
    hsn_code=None,
    norms=None,
    notification_numbers=None,
    expiry_date_from=None,
    expiry_date_to=None,
) -> dict:
    """Generate item report data."""
    today = date.today()

    # Prefetch latest transfers per license.
    latest_transfer_prefetch = Prefetch(
        'license__transfers',
        queryset=LicenseTransferModel.objects.select_related(
            'from_company', 'to_company'
        ).order_by('-transfer_date', '-transfer_initiation_date'),
        to_attr='latest_transfers',
    )

    items = LicenseImportItemsModel.objects.select_related(
        'license',
        'license__exporter',
        'license__ownership__current_owner',
        'license__balance',
        'license__notes',
        'hs_code',
    ).prefetch_related('items', latest_transfer_prefetch)

    # License status filter.
    if license_status == 'active':
        items = items.filter(
            license__flags__is_active=True,
            license__license_expiry_date__gt=today - timedelta(days=30),
        )
    elif license_status == 'expired':
        items = items.filter(license__license_expiry_date__lt=today)
    elif license_status == 'expiring_soon':
        items = items.filter(
            license__flags__is_active=True,
            license__license_expiry_date__gte=today,
            license__license_expiry_date__lte=today + timedelta(days=30),
        )
    # 'all' → no date filter.

    # Explicit expiry date range filter.
    if expiry_date_from:
        from datetime import datetime as _dt
        items = items.filter(
            license__license_expiry_date__gte=_dt.strptime(expiry_date_from, '%Y-%m-%d').date()
        )
    if expiry_date_to:
        from datetime import datetime as _dt
        items = items.filter(
            license__license_expiry_date__lte=_dt.strptime(expiry_date_to, '%Y-%m-%d').date()
        )

    # Pre-filter by stored available_value.
    items = items.filter(available_value__gte=min_balance)

    if min_avail_qty > 0:
        items = items.filter(available_quantity__gte=min_avail_qty)

    if company_ids:
        company_id_list = [int(cid.strip()) for cid in company_ids.split(',') if cid.strip()]
        items = items.filter(license__exporter_id__in=company_id_list)

    if exclude_company_ids:
        exclude_id_list = [int(cid.strip()) for cid in exclude_company_ids.split(',') if cid.strip()]
        items = items.exclude(license__exporter_id__in=exclude_id_list)

    if item_names:
        item_name_ids = [int(id_.strip()) for id_ in item_names.split(',') if id_.strip()]
        items = items.filter(items__id__in=item_name_ids).distinct()

    if is_restricted is not None:
        if is_restricted == 'true':
            items = items.filter(is_restricted=True)
        elif is_restricted == 'false':
            items = items.filter(is_restricted=False)

    if purchase_status:
        purchase_status_list = [ps.strip() for ps in purchase_status.split(',') if ps.strip()]
        items = items.filter(license__purchase_status__code__in=purchase_status_list)

    if product_description:
        items = items.filter(description__icontains=product_description)

    if hsn_code:
        items = items.filter(hs_code__hs_code__icontains=hsn_code)

    if norms:
        norms_list = [n.strip() for n in norms.split(',') if n.strip()]
        items = items.filter(items__sion_norm_class__norm_class__in=norms_list).distinct()

    if notification_numbers:
        notification_list = [n.strip() for n in notification_numbers.split(',') if n.strip()]
        items = items.filter(license__notification_number__in=notification_list).distinct()

    items = items.order_by('license__license_number', 'serial_number')

    # Utilization plan per item.
    from apps.license.services.plan_reporting import plan_map_for_import_items
    from apps.license.services.norm_plan import effective_plan_for_license

    manual_splits = plan_map_for_import_items([it.id for it in items])
    _eff_cache = {}

    def _effective(lic):
        if lic.id not in _eff_cache:
            _eff_cache[lic.id] = effective_plan_for_license(lic)
        return _eff_cache[lic.id]

    report_items = []
    for item in items:
        item_names_list = [{"id": i.id, "name": i.name} for i in item.items.all()]
        _plan_source, _eff = _effective(item.license)
        plan = _eff.get(item.id)
        _ms = manual_splits.get(item.id)

        available_balance = float(item.available_value or 0)

        latest_transfer_info = None
        if hasattr(item.license, 'latest_transfers') and item.license.latest_transfers:
            latest_transfer = item.license.latest_transfers[0]
            latest_transfer_info = str(latest_transfer)

        current_owner = _get_current_owner(item.license)
        ledger_date = _get_ledger_date(item.license)

        report_items.append({
            'id': item.id,
            'license_id': item.license.id,
            'license_number': item.license.license_number,
            'license_date': item.license.license_date.isoformat() if item.license.license_date else None,
            'license_expiry_date': item.license.license_expiry_date.isoformat() if item.license.license_expiry_date else None,
            'ledger_date': ledger_date.isoformat() if ledger_date else None,
            'exporter_name': item.license.exporter.name if item.license.exporter else None,
            'current_owner': current_owner.name if current_owner else None,
            'latest_transfer': latest_transfer_info,
            'hs_code': item.hs_code.hs_code if item.hs_code else None,
            'product_description': item.description or '',
            'item_names': item_names_list,
            'quantity': float(item.quantity or 0),
            'available_quantity': float(item.available_quantity or 0),
            'available_balance': available_balance,
            'balance_cif': float(_get_balance_cif(item.license)),
            'is_restricted': item.is_restricted,
            'condition_type': item.condition_type or '',
            'notes': _get_balance_report_notes(item.license),
            'condition_sheet': _get_condition_sheet(item.license),
            'unit': item.unit,
            'serial_number': item.serial_number,
            'planned_quantity': plan['planned_quantity'] if plan else 0,
            'planned_cif': plan['planned_cif'] if plan else 0,
            'plan_source': _plan_source,
            'planned_splits': (_ms['splits'] if (_plan_source == 'manual' and _ms) else []),
        })

    return {
        'report_date': today.isoformat(),
        'total_items': len(report_items),
        'items': report_items,
    }


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def _export_to_excel(report_data: dict) -> HttpResponse:
    """Export item report to Excel with separate sheets for Restricted / Not Restricted."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from io import BytesIO
    from apps.license.utils.condition_excel import annotate_cell as _annotate_condition_cell

    def _safe(v):
        if isinstance(v, str):
            return ILLEGAL_CHARACTERS_RE.sub('', v)
        return v

    items = report_data['items']
    restricted_items = [item for item in items if item['is_restricted']]
    not_restricted_items = [item for item in items if not item['is_restricted']]

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = [
        'Sr No', 'License No', 'License Date', 'License Expiry Date', 'Ledger Date', 'Exporter Name',
        'Serial Number', 'Condition', 'HSN Code', 'Product Description', 'Item Name',
        'Available Quantity', 'Available Balance', 'Balance CIF', 'Notes', 'Condition Sheet', 'Transfer Status',
        'Plan Qty', 'Plan CIF',
    ]

    def create_sheet(workbook, sheet_name, items_list):
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'),
        )
        ws = workbook.create_sheet(title=sheet_name)

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment

        col_widths = [8, 18, 15, 18, 15, 25, 12, 11, 12, 40, 25, 18, 18, 18, 30, 30, 35, 14, 16]
        for i, width in enumerate(col_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

        # Group by license.
        grouped_items = {}
        for item in items_list:
            lid = item['license_id']
            grouped_items.setdefault(lid, []).append(item)

        current_row = 2
        sr_no = 1

        for _lid, license_items in grouped_items.items():
            row_span = len(license_items)
            start_row = current_row

            for item_idx, item in enumerate(license_items):
                item_names_str = ', '.join([i['name'] for i in item['item_names']])

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

                sn_cell = ws.cell(row=current_row, column=7, value=item['serial_number'])
                cond = (item.get('condition_type') or '')
                cond_cell = ws.cell(row=current_row, column=8, value=cond)
                _annotate_condition_cell(sn_cell, cond)
                _annotate_condition_cell(cond_cell, cond)
                ws.cell(row=current_row, column=9, value=_safe(item['hs_code']))
                ws.cell(row=current_row, column=10, value=_safe(item['product_description']))
                ws.cell(row=current_row, column=11, value=_safe(item_names_str))
                ws.cell(row=current_row, column=12, value=item['available_quantity'])
                ws.cell(row=current_row, column=18, value=item.get('planned_quantity') or 0)
                ws.cell(row=current_row, column=19, value=item.get('planned_cif') or 0)

                current_row += 1

            # Merge license-level cells when there are multiple items.
            if row_span > 1:
                end_row = start_row + row_span - 1
                for col in [1, 2, 3, 4, 5, 6, 13, 14, 15, 16, 17]:
                    ws.merge_cells(
                        start_row=start_row, start_column=col,
                        end_row=end_row, end_column=col,
                    )
                    cell = ws.cell(row=start_row, column=col)
                    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
                    cell.border = thin_border

            sr_no += 1

        return ws

    if restricted_items:
        create_sheet(wb, "Restricted", restricted_items)
    if not_restricted_items:
        create_sheet(wb, "Not Restricted", not_restricted_items)
    if not restricted_items and not not_restricted_items:
        ws = wb.create_sheet(title="No Data")
        ws.cell(row=1, column=1, value="No items found matching the filter criteria")

    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename=item_report.xlsx'
    return response


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class ItemReportViewSet(viewsets.ViewSet):
    """
    ViewSet for the Item Report.

    GET /api/v1/item-report/                  → JSON report
    GET /api/v1/item-report/?format=excel     → Excel download
    GET /api/v1/item-report/available-items/  → item name lookup list
    """
    permission_classes = [ReportPermission]

    def list(self, request):
        """Return JSON report or trigger Excel download based on ?format=."""
        params = request.GET
        output_format = params.get('format', 'json').lower()

        kwargs = dict(
            item_names=params.get('item_names'),
            company_ids=params.get('company_ids'),
            exclude_company_ids=params.get('exclude_company_ids'),
            min_balance=_safe_int(params.get('min_balance'), 200),
            min_avail_qty=float(params.get('min_avail_qty', 0)),
            license_status=params.get('license_status', 'active'),
            is_restricted=params.get('is_restricted'),
            purchase_status=params.get('purchase_status'),
            product_description=params.get('product_description'),
            hsn_code=params.get('hsn_code'),
            norms=params.get('norms'),
            notification_numbers=params.get('notification_numbers'),
            expiry_date_from=params.get('expiry_date_from'),
            expiry_date_to=params.get('expiry_date_to'),
        )

        try:
            report_data = _generate_report(**kwargs)
        except Exception as exc:
            logger.exception("Error generating item report")
            return Response({'error': str(exc)}, status=500)

        if output_format == 'excel':
            try:
                return _export_to_excel(report_data)
            except Exception as exc:
                logger.exception("Error exporting item report to Excel")
                return Response({'error': str(exc)}, status=500)

        return Response(report_data)

    @action(detail=False, methods=['get'], url_path='available-items')
    def available_items(self, request):
        """Return all active item names for the filter dropdown."""
        item_names = ItemNameModel.objects.filter(
            is_active=True
        ).order_by('name').values('id', 'name')
        return Response(list(item_names))
