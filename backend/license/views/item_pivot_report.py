"""
Item-wise Pivot Report

Shows licenses with items as column headers, displaying quantities and values per item.
Similar to the GE DFIA report format.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Set
from collections import defaultdict

from django.db.models import Sum, Q, F, DecimalField, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.views import View
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from core.constants import DEC_0, DEC_000, GE, MI, IP, SM
from license.models import LicenseDetailsModel, LicenseImportItemsModel


class ItemPivotReportView(View):
    """
    Report showing licenses with items as columns (pivot format).

    GET parameters:
        - format: 'json' or 'excel' (default: json)
        - days: Number of days to look back (default: 30)
    """

    def get(self, request, *args, **kwargs):
        output_format = request.GET.get('format', 'json').lower()
        days = int(request.GET.get('days', 30))
        sion_norm = request.GET.get('sion_norm')
        company_ids = request.GET.get('company_ids')  # Comma-separated company IDs
        exclude_company_ids = request.GET.get('exclude_company_ids')  # Comma-separated company IDs to exclude

        try:
            report_data = self.generate_report(days, sion_norm, company_ids, exclude_company_ids)
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)

        if output_format == 'excel':
            return self.export_to_excel(report_data)
        else:
            return JsonResponse(report_data, safe=False)

    def generate_report(self, days: int = 30, sion_norm: str = None, 
                       company_ids: str = None, exclude_company_ids: str = None) -> Dict[str, Any]:
        """
        Generate item-wise pivot report.

        Args:
            days: Number of days to look back for active licenses
            sion_norm: Filter by specific SION norm class (optional)
            company_ids: Comma-separated company IDs to include (optional)
            exclude_company_ids: Comma-separated company IDs to exclude (optional)

        Returns:
            Dictionary with report data
        """
        today = date.today()
        start_date = today - timedelta(days=days)

        # Get active licenses with expiry >= start_date
        licenses = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte=start_date,
            is_active=True,
            purchase_status__in=[GE, MI, IP, SM]
        )

        # Filter by SION norm if specified
        if sion_norm:
            licenses = licenses.filter(export_license__norm_class__norm_class=sion_norm).distinct()

        # Filter by company IDs if specified
        if company_ids:
            company_id_list = [int(cid.strip()) for cid in company_ids.split(',') if cid.strip()]
            licenses = licenses.filter(exporter_id__in=company_id_list)

        # Exclude company IDs if specified
        if exclude_company_ids:
            exclude_id_list = [int(cid.strip()) for cid in exclude_company_ids.split(',') if cid.strip()]
            licenses = licenses.exclude(exporter_id__in=exclude_id_list)

        licenses = licenses.select_related('exporter', 'port').prefetch_related(
            'import_license__items',
            'import_license__hs_code',
            'export_license__norm_class'
        ).order_by('license_number')

        # Collect all unique items across all licenses
        all_items = set()
        for license_obj in licenses:
            for import_item in license_obj.import_license.all():
                for item in import_item.items.all():
                    # Only add items with valid names
                    if item and item.name:
                        all_items.add((item.id, item.name))

        # Sort items by name for consistent column order
        sorted_items = sorted(all_items, key=lambda x: x[1] or '')

        # Build license data with item columns, grouped by notification
        from collections import defaultdict
        licenses_by_notification = defaultdict(list)
        
        for license_obj in licenses:
            # Skip licenses with balance < 100
            balance = license_obj.balance_cif or Decimal('0')
            if balance < Decimal('100.00'):
                continue

            license_row = self._build_license_row(license_obj, sorted_items)
            if license_row:
                notification = license_obj.notification_number or 'Unknown'
                licenses_by_notification[notification].append(license_row)

        # Determine which items have restrictions
        items_with_restrictions = set()
        for notification, licenses_list in licenses_by_notification.items():
            for license_row in licenses_list:
                for item_id, item_name in sorted_items:
                    item_data = license_row.get('items', {}).get(item_name, {})
                    if item_data.get('restriction') is not None:
                        items_with_restrictions.add(item_id)

        return {
            'items': [
                {
                    'id': item_id,
                    'name': item_name,
                    'has_restriction': item_id in items_with_restrictions
                }
                for item_id, item_name in sorted_items
            ],
            'licenses_by_notification': dict(licenses_by_notification),
            'report_date': today.isoformat(),
        }

    def _build_license_row(self, license_obj: LicenseDetailsModel, all_items: List[tuple]) -> Dict[str, Any]:
        """
        Build a single license row with item columns.

        Args:
            license_obj: LicenseDetailsModel instance
            all_items: List of (item_id, item_name) tuples

        Returns:
            Dictionary with license data and item quantities
        """
        # Calculate total CIF from export license items
        total_cif = license_obj.export_license.aggregate(
            total=Sum('cif_fc')
        )['total'] or Decimal('0')
        
        # Aggregate quantities by item (sum across all serial numbers)
        item_quantities = defaultdict(lambda: {
            'quantity': Decimal('0.000'),
            'debited_quantity': Decimal('0.000'),
            'available_quantity': Decimal('0.000'),
            'debited_value': Decimal('0.00'),
            'cif_value': Decimal('0.00'),
            'hs_code': '',
            'description': '',
            'sion_norm_class': None,
            'restriction_percentage': None,
        })

        # Group items by (sion_norm_class, restriction_percentage) to calculate shared restriction limits
        restriction_groups = defaultdict(lambda: {
            'total_cif': Decimal('0.00'),
            'debited_cif': Decimal('0.00'),
            'available_cif': Decimal('0.00'),
            'restriction_percentage': None,
            'sion_norm_class': None,
            'item_ids': []
        })

        for import_item in license_obj.import_license.all():
            for item in import_item.items.all():
                item_quantities[item.id]['quantity'] += import_item.quantity or DEC_000
                item_quantities[item.id]['debited_quantity'] += import_item.debited_quantity or DEC_000
                item_quantities[item.id]['available_quantity'] += import_item.available_quantity or DEC_000
                item_quantities[item.id]['debited_value'] += import_item.debited_value or DEC_0
                item_quantities[item.id]['cif_value'] += import_item.cif_fc or DEC_0
                
                if import_item.hs_code and not item_quantities[item.id]['hs_code']:
                    item_quantities[item.id]['hs_code'] = import_item.hs_code.hs_code
                
                if import_item.description and not item_quantities[item.id]['description']:
                    item_quantities[item.id]['description'] = import_item.description

                # Get restriction from item's sion_norm_class and restriction_percentage
                if item and hasattr(item, 'sion_norm_class') and item.sion_norm_class:
                    sion_norm = item.sion_norm_class.norm_class
                    restriction_pct = item.restriction_percentage

                    item_quantities[item.id]['sion_norm_class'] = sion_norm
                    item_quantities[item.id]['restriction_percentage'] = restriction_pct

                    # Group by (sion_norm_class, restriction_percentage) for shared restriction calculation
                    # Items in same SION norm with same restriction % share the restriction limit
                    restriction_key = f"{sion_norm}_{restriction_pct}"
                    restriction_groups[restriction_key]['sion_norm_class'] = sion_norm
                    restriction_groups[restriction_key]['restriction_percentage'] = restriction_pct
                    restriction_groups[restriction_key]['total_cif'] += import_item.cif_fc or DEC_0
                    restriction_groups[restriction_key]['debited_cif'] += import_item.debited_value or DEC_0
                    if item.id not in restriction_groups[restriction_key]['item_ids']:
                        restriction_groups[restriction_key]['item_ids'].append(item.id)
        
        # Calculate available CIF within restriction for each group
        for group_name, group_data in restriction_groups.items():
            if group_data['restriction_percentage'] and total_cif > 0:
                # Maximum allowed CIF for this restriction group
                max_allowed_cif = (total_cif * group_data['restriction_percentage']) / Decimal('100')
                # Available CIF = max_allowed - debited
                available_cif = max_allowed_cif - group_data['debited_cif']
                group_data['available_cif'] = max(available_cif, Decimal('0'))

        # Build row data
        row_data = {
            'license_number': license_obj.license_number,
            'license_date': license_obj.license_date.isoformat() if license_obj.license_date else None,
            'license_expiry_date': license_obj.license_expiry_date.isoformat(),
            'exporter': str(license_obj.exporter) if license_obj.exporter else '',
            'port': str(license_obj.port) if license_obj.port else '',
            'notification_number': license_obj.notification_number or 'Unknown',
            'total_cif': float(total_cif),
            'balance_cif': float(license_obj.balance_cif or Decimal('0')),
            'items': {}
        }

        # Add item columns
        for item_id, item_name in all_items:
            if item_id in item_quantities:
                item_data = item_quantities[item_id]
                sion_norm = item_data['sion_norm_class']
                restriction_pct = item_data['restriction_percentage']

                # Get restriction percentage only (as number)
                restriction_value = None
                available_cif = Decimal('0')

                if sion_norm and restriction_pct:
                    restriction_key = f"{sion_norm}_{restriction_pct}"
                    if restriction_key in restriction_groups:
                        group = restriction_groups[restriction_key]
                        restriction_value = float(restriction_pct)
                        available_cif = group['available_cif']

                row_data['items'][item_name] = {
                    'hs_code': item_data['hs_code'],
                    'description': item_data['description'],
                    'quantity': float(item_data['quantity']),
                    'debited_quantity': float(item_data['debited_quantity']),
                    'available_quantity': float(item_data['available_quantity']),
                    'restriction': restriction_value,
                    'restriction_value': float(available_cif),
                }
            else:
                row_data['items'][item_name] = {
                    'hs_code': '',
                    'description': '',
                    'quantity': 0,
                    'debited_quantity': 0,
                    'available_quantity': 0,
                    'restriction': None,
                    'restriction_value': 0,
                }

        return row_data

    def export_to_excel(self, report_data: Dict[str, Any]) -> HttpResponse:
        """
        Export report to Excel format with items as columns, split by notification.

        Args:
            report_data: Report data dictionary

        Returns:
            HttpResponse with Excel file
        """
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

        workbook = openpyxl.Workbook()
        # Remove default sheet
        workbook.remove(workbook.active)

        licenses_by_notification = report_data.get('licenses_by_notification', {})
        
        # Create a sheet for each notification
        for notification, licenses_list in sorted(licenses_by_notification.items()):
            # Sanitize sheet name (Excel has 31 char limit and doesn't allow certain chars)
            sheet_name = str(notification)[:31].replace('/', '-').replace('\\', '-').replace('*', '-').replace('[', '(').replace(']', ')')
            worksheet = workbook.create_sheet(title=sheet_name)

            current_row = 1

            # Title
            title = f"Item Pivot Report - {notification}"
            worksheet.merge_cells(f'A{current_row}:Z{current_row}')
            title_cell = worksheet[f'A{current_row}']
            title_cell.value = title
            title_cell.font = Font(bold=True, size=14)
            title_cell.alignment = Alignment(horizontal='center')
            current_row += 2

            # Build headers
            base_headers = [
                'Sr no', 'DFIA No', 'DFIA Dt', 'Expiry Dt', 'Exporter',
                'Total CIF', 'Balance CIF'
            ]

            # Add item columns (HSN Code, Product Description, Total QTY, Debited QTY, Available QTY, Restriction %, Restriction Value)
            item_headers = []
            for item in report_data['items']:
                item_name = item['name']
                has_restriction = item.get('has_restriction', False)

                headers = [
                    f"{item_name} HSN Code",
                    f"{item_name} Product Description",
                    f"{item_name} Total QTY",
                    f"{item_name} Debited QTY",
                    f"{item_name} Available QTY",
                ]

                if has_restriction:
                    headers.extend([
                        f"{item_name} Restriction %",
                        f"{item_name} Restriction Value"
                    ])

                item_headers.extend(headers)

            all_headers = base_headers + item_headers

            # Write headers
            for col_num, header in enumerate(all_headers, 1):
                cell = worksheet.cell(row=current_row, column=col_num)
                cell.value = header
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
            current_row += 1

            # Write data rows for this notification
            for idx, license_data in enumerate(licenses_list, 1):
                col_num = 1

                # Base columns
                worksheet.cell(row=current_row, column=col_num, value=idx)
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=license_data['license_number'])
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=license_data['license_date'])
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=license_data['license_expiry_date'])
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=license_data['exporter'])
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=license_data['total_cif'])
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=license_data['balance_cif'])
                col_num += 1

                # Item columns
                for item in report_data['items']:
                    item_name = item['name']
                    has_restriction = item.get('has_restriction', False)
                    item_data = license_data['items'].get(item_name, {
                        'hs_code': '',
                        'description': '',
                        'quantity': 0,
                        'debited_quantity': 0,
                        'available_quantity': 0,
                        'restriction': None,
                        'restriction_value': 0
                    })

                    worksheet.cell(row=current_row, column=col_num, value=item_data.get('hs_code', ''))
                    col_num += 1
                    worksheet.cell(row=current_row, column=col_num, value=item_data.get('description', ''))
                    col_num += 1
                    worksheet.cell(row=current_row, column=col_num, value=item_data.get('quantity', 0))
                    col_num += 1
                    worksheet.cell(row=current_row, column=col_num, value=item_data.get('debited_quantity', 0))
                    col_num += 1
                    worksheet.cell(row=current_row, column=col_num, value=item_data.get('available_quantity', 0))
                    col_num += 1

                    # Only write restriction columns if item has restrictions
                    if has_restriction:
                        # Write restriction as number only (percentage)
                        restriction_val = item_data.get('restriction')
                        worksheet.cell(row=current_row, column=col_num, value=restriction_val if restriction_val else '')
                        col_num += 1
                        # Write restriction value (available CIF)
                        restriction_value = item_data.get('restriction_value', 0)
                        worksheet.cell(row=current_row, column=col_num, value=restriction_value if restriction_value else '')
                        col_num += 1

                current_row += 1

            # Add totals row for this notification
            worksheet.cell(row=current_row, column=1, value='TOTAL')
            worksheet.cell(row=current_row, column=1).font = Font(bold=True)

            # Calculate totals for CIF columns
            total_cif = sum(lic['total_cif'] for lic in licenses_list)
            balance_cif = sum(lic['balance_cif'] for lic in licenses_list)
            worksheet.cell(row=current_row, column=6, value=total_cif)
            worksheet.cell(row=current_row, column=6).font = Font(bold=True)
            worksheet.cell(row=current_row, column=7, value=balance_cif)
            worksheet.cell(row=current_row, column=7).font = Font(bold=True)

            # Calculate totals for each item
            col_num = 8
            for item in report_data['items']:
                item_name = item['name']
                has_restriction = item.get('has_restriction', False)
                total_qty = sum(
                    lic['items'].get(item_name, {}).get('quantity', 0)
                    for lic in licenses_list
                )
                total_debited = sum(
                    lic['items'].get(item_name, {}).get('debited_quantity', 0)
                    for lic in licenses_list
                )
                total_avail = sum(
                    lic['items'].get(item_name, {}).get('available_quantity', 0)
                    for lic in licenses_list
                )

                col_num += 2  # Skip HSN and Description columns in totals
                worksheet.cell(row=current_row, column=col_num, value=total_qty)
                worksheet.cell(row=current_row, column=col_num).font = Font(bold=True)
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=total_debited)
                worksheet.cell(row=current_row, column=col_num).font = Font(bold=True)
                col_num += 1
                worksheet.cell(row=current_row, column=col_num, value=total_avail)
                worksheet.cell(row=current_row, column=col_num).font = Font(bold=True)
                col_num += 1

                # Only skip restriction columns if item has restrictions
                if has_restriction:
                    col_num += 1  # Skip Restriction % column in totals
                    col_num += 1  # Skip Restriction Value column in totals

            # Auto-adjust column widths
            for col_idx in range(1, len(all_headers) + 1):
                max_length = 0
                column_letter = openpyxl.utils.get_column_letter(col_idx)

                for row in worksheet.iter_rows(min_col=col_idx, max_col=col_idx):
                    for cell in row:
                        try:
                            if cell.value:
                                cell_length = len(str(cell.value))
                                if cell_length > max_length:
                                    max_length = cell_length
                        except:
                            pass

                adjusted_width = min(max(max_length + 2, 10), 30)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="item_pivot_report.xlsx"'

        workbook.save(response)
        return response


class ItemPivotViewSet(viewsets.ViewSet):
    """
    ViewSet for Item Pivot Report.

    Permissions: AllowAny - accessible to all users
    """
    permission_classes = [AllowAny]

    def list(self, request):
        """
        Get item pivot report.

        Query Parameters:
            days: Number of days to look back (default: 30)
        """
        view = ItemPivotReportView()
        return view.get(request)
