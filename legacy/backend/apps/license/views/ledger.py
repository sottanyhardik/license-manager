"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
import logging
from decimal import Decimal
from datetime import datetime

from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicenseLedgerViewPermission
from apps.license.models import LicenseDetailsModel, IncentiveLicense

# Initialize logger
logger = logging.getLogger(__name__)


def _get_safe_balance(license, balance_field):
    """Safely get balance value with fallback"""
    try:
        value = getattr(license, balance_field, None)
        if value is None:
            return 0.0
        return float(value)
    except (ValueError, TypeError, AttributeError):
        logger.warning(f"Invalid balance value for license {license.id}")
        return 0.0



class LicenseLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Unified ledger view for both DFIA and Incentive licenses.
    Shows available balance for selling licenses.

    Returns:
    - DFIA licenses: balance_cif (available CIF $ balance)
    - Incentive licenses: balance_value (available INR balance)
    """
    permission_classes = [LicenseLedgerViewPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['license_number', 'exporter__name']
    ordering_fields = ['license_date', 'balance_value', 'license_expiry_date']
    ordering = ['-license_date']

    def get_queryset(self):
        """Return unified filtered list of DFIA + Incentive license dicts."""
        from apps.license.services.ledger_service import build_license_queryset
        return build_license_queryset(self.request.query_params)

    def _prepare_dfia_data(self, queryset):
        from apps.license.services.ledger_service import prepare_dfia_data
        return prepare_dfia_data(queryset)

    def _prepare_incentive_data(self, queryset):
        from apps.license.services.ledger_service import prepare_incentive_data
        return prepare_incentive_data(queryset)

    def _get_sold_status(self, total, balance):
        from apps.license.services.ledger_service import get_sold_status
        return get_sold_status(total, balance)

    def _get_incentive_breakdown(self, incentive_qs):
        from apps.license.services.ledger_service import get_incentive_breakdown
        return get_incentive_breakdown(incentive_qs)

    def list(self, request, *args, **kwargs):
        """Override list to handle non-queryset data"""
        data = self.get_queryset()

        # Apply search filter manually for combined data
        search = request.query_params.get('search')
        if search and isinstance(data, list):
            # Support comma-separated license numbers (e.g. "0311045100,0311045787")
            terms = [t.strip().lower() for t in search.split(',') if t.strip()]
            if len(terms) > 1:
                data = [
                    item for item in data
                    if (item.get('license_number') or '').lower() in terms
                ]
            else:
                search_lower = terms[0] if terms else ''
                data = [
                    item for item in data
                    if search_lower in (item.get('license_number') or '').lower()
                       or search_lower in (item.get('exporter_name') or '').lower()
                ]

        # Apply ordering
        ordering = request.query_params.get('ordering', '-license_date')
        if isinstance(data, list):
            reverse = ordering.startswith('-')
            order_field = ordering.lstrip('-')
            if order_field in ['license_date', 'balance_value', 'license_expiry_date']:
                # Handle None values in date/numeric fields
                from datetime import date
                if order_field in ['license_date', 'license_expiry_date']:
                    # For date fields, use date.min for None values
                    data.sort(key=lambda x: x.get(order_field) or date.min, reverse=reverse)
                else:
                    # For numeric fields (balance_value), use 0 for None values
                    data.sort(key=lambda x: x.get(order_field) or 0, reverse=reverse)

        # Pagination
        page = self.paginate_queryset(data)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(data)

    def _find_license_by_id_or_number(self, pk, search_dfia=True, search_incentive=True):
        """
        Helper method to find license in DFIA and/or Incentive tables by ID or license_number.

        Args:
            pk: License ID (int) or license_number (str)
            search_dfia: Whether to search in DFIA licenses
            search_incentive: Whether to search in Incentive licenses

        Returns:
            Tuple of (license_type, license_object) or (None, None) if not found
        """
        # Search DFIA if requested
        if search_dfia:
            try:
                if pk.isdigit() and not pk.startswith('0'):
                    try:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=int(pk))
                        return ('DFIA', license)
                    except LicenseDetailsModel.DoesNotExist:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
                        return ('DFIA', license)
                else:
                    try:
                        license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
                        return ('DFIA', license)
                    except LicenseDetailsModel.DoesNotExist:
                        try:
                            license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=int(pk))
                            return ('DFIA', license)
                        except (ValueError, TypeError, LicenseDetailsModel.DoesNotExist):
                            pass
            except LicenseDetailsModel.DoesNotExist:
                pass

        # Search Incentive if requested
        if search_incentive:
            try:
                if pk.isdigit() and not pk.startswith('0'):
                    try:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=int(pk))
                        return ('INCENTIVE', license)
                    except IncentiveLicense.DoesNotExist:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
                        return ('INCENTIVE', license)
                else:
                    try:
                        license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
                        return ('INCENTIVE', license)
                    except IncentiveLicense.DoesNotExist:
                        try:
                            license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=int(pk))
                            return ('INCENTIVE', license)
                        except (ValueError, TypeError, IncentiveLicense.DoesNotExist):
                            pass
            except IncentiveLicense.DoesNotExist:
                pass

        return (None, None)

    def retrieve(self, request, pk=None, *args, **kwargs):
        """
        Retrieve a single license by ID or license_number.
        Supports both DFIA and Incentive licenses.
        Auto-searches both tables if not found in the specified type.
        """
        license_type = request.query_params.get('license_type', 'AUTO')

        # Determine search strategy based on license_type parameter
        if license_type == 'DFIA':
            found_type, license = self._find_license_by_id_or_number(pk, search_dfia=True, search_incentive=False)
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            found_type, license = self._find_license_by_id_or_number(pk, search_dfia=False, search_incentive=True)
        else:  # AUTO or ALL - search both
            found_type, license = self._find_license_by_id_or_number(pk, search_dfia=True, search_incentive=True)

        # If not found, return 404
        if not license:
            return Response({
                'error': f'License not found: {pk}',
                'searched_in': 'DFIA only' if license_type == 'DFIA' else 'Incentive only' if license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'] else 'both DFIA and Incentive'
            }, status=404)

        # Prepare and return data based on found type
        if found_type == 'DFIA':
            dfia_data = self._prepare_dfia_data([license])
            if dfia_data:
                return Response(dfia_data[0])
        else:  # INCENTIVE
            incentive_data = self._prepare_incentive_data([license])
            if incentive_data:
                return Response(incentive_data[0])

        return Response({'error': 'License data preparation failed'}, status=500)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get summary statistics for license balances.
        Filters by company, license_type, date range, and other parameters.
        """
        from apps.license.services.ledger_service import get_ledger_summary
        return Response(get_ledger_summary(request.query_params))

    @action(detail=True, methods=['get'])
    def ledger_detail(self, request, pk=None):
        """
        Get detailed ledger view for a specific license showing all transactions.
        Works for both DFIA and Incentive licenses.
        Accepts either ID (integer) or license_number (string) as pk parameter.
        Auto-searches both tables if license_type not specified.

        Optional company parameter: If provided, only shows transactions involving that company.
        """
        from django.utils import timezone
        from apps.trade.models import LicenseTrade
        from django.db.models import Q

        license_type = request.query_params.get('license_type', 'AUTO')
        company_id = request.query_params.get('company')  # Optional company filter

        # Determine search strategy
        if license_type == 'DFIA':
            found_type, license = self._find_license_by_id_or_number(pk, search_dfia=True, search_incentive=False)
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            found_type, license = self._find_license_by_id_or_number(pk, search_dfia=False, search_incentive=True)
        else:  # AUTO - search both
            found_type, license = self._find_license_by_id_or_number(pk, search_dfia=True, search_incentive=True)

        # If not found, return 404
        if not license:
            return Response({
                'error': f'License not found: {pk}',
                'searched_in': 'DFIA only' if license_type == 'DFIA' else 'Incentive only' if license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'] else 'both DFIA and Incentive'
            }, status=404)

        # Delegate transaction building to the ledger_pdf service — keeps the
        # view thin and the business logic testable in isolation.
        from apps.license.services.exporters.ledger_pdf import (
            build_dfia_ledger_detail,
            build_incentive_ledger_detail,
        )

        if found_type == 'DFIA':
            return Response(build_dfia_ledger_detail(license, company_id=company_id))
        else:  # INCENTIVE
            return Response(build_incentive_ledger_detail(license, company_id=company_id))

    @action(detail=False, methods=['get'])
    def available_for_sale(self, request):
        """
        Get licenses with available balance for sale.
        Filters out expired and fully sold licenses.
        """
        from django.utils import timezone

        min_balance = Decimal(request.query_params.get('min_balance', '100'))

        # DFIA with balance
        dfia_data = self._prepare_dfia_data(
            LicenseDetailsModel.objects.filter(
                flags__is_expired=False,
                balance__balance_cif__gte=min_balance
            ).select_related('exporter', 'port')
        )

        # Incentive with balance
        incentive_data = self._prepare_incentive_data(
            IncentiveLicense.objects.filter(
                is_active=True,
                license_expiry_date__gte=timezone.now().date(),
                balance_value__gte=min_balance
            ).select_related('exporter', 'port_code')
        )

        combined = list(dfia_data) + list(incentive_data)
        combined.sort(key=lambda x: x.get('balance_value', 0), reverse=True)

        return Response({
            'count': len(combined),
            'min_balance_filter': float(min_balance),
            'licenses': combined
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search DFIA + Incentive licenses by license number or exporter name.
        Requires query param ``q``.
        """
        from apps.license.services.ledger_service import search_licenses
        result = search_licenses(request.query_params)
        if result is None:
            return Response({'error': 'Search query parameter "q" is required'}, status=400)
        return Response(result)

    @action(detail=False, methods=['get'], url_path='export/all')
    def export_all(self, request):
        """
        Export all licenses (or filtered licenses) to a single PDF file.

        Query params (same as list):
        - license_type: Filter by type (DFIA, INCENTIVE, RODTEP, ROSTL, MEIS, or ALL) - default: ALL
        - active_only: Filter only active licenses (default: true)
        - min_balance: Minimum balance filter
        - exporter: Filter by exporter ID
        - search: Search by license number or exporter name
        """
        # Get filtered data using same logic as list()
        data = self.get_queryset()

        # Apply search filter manually for combined data
        search = request.query_params.get('search')
        if search and isinstance(data, list):
            # Support comma-separated license numbers (e.g. "0311045100,0311045787")
            terms = [t.strip().lower() for t in search.split(',') if t.strip()]
            if len(terms) > 1:
                data = [
                    item for item in data
                    if (item.get('license_number') or '').lower() in terms
                ]
            else:
                search_lower = terms[0] if terms else ''
                data = [
                    item for item in data
                    if search_lower in (item.get('license_number') or '').lower()
                       or search_lower in (item.get('exporter_name') or '').lower()
                ]

        # Apply ordering
        ordering = request.query_params.get('ordering', '-license_date')
        if isinstance(data, list):
            reverse = ordering.startswith('-')
            order_field = ordering.lstrip('-')
            if order_field in ['license_date', 'balance_value', 'license_expiry_date']:
                from datetime import date
                if order_field in ['license_date', 'license_expiry_date']:
                    data.sort(key=lambda x: x.get(order_field) or date.min, reverse=reverse)
                else:
                    data.sort(key=lambda x: x.get(order_field) or 0, reverse=reverse)

        # Check if detailed view is requested
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'

        # Generate PDF (detailed or summary)
        if detailed:
            pdf_content = self._generate_detailed_licenses_pdf(data, request.query_params)
            filename = f"license_ledger_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        else:
            pdf_content = self._generate_all_licenses_pdf(data, request.query_params)
            filename = f"license_ledger_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    def _get_license_transactions(self, lic_data, company_id=None):
        from apps.license.services.exporters.ledger_pdf import get_license_transactions
        return get_license_transactions(lic_data, company_id=company_id)
    def _generate_detailed_licenses_pdf(self, licenses_data, query_params):
        from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf
        return generate_detailed_licenses_pdf(licenses_data, query_params)
    def _generate_all_licenses_pdf(self, licenses_data, query_params):
        from apps.license.services.exporters.ledger_pdf import generate_all_licenses_pdf
        return generate_all_licenses_pdf(licenses_data, query_params)
    @action(detail=False, methods=['get'], url_path='company-ledger')
    def company_ledger(self, request):
        """
        Get ledger view for a specific company showing only licenses
        where the company appears in trades (either as buyer or seller).

        Query params:
        - company: Company ID (required)
        - license_type: Filter by type (DFIA, INCENTIVE, etc.) - default: ALL
        - active_only: Filter only active licenses (default: true)
        """
        company_id = request.query_params.get('company')

        if not company_id:
            return Response({'error': 'company parameter is required'}, status=400)

        # Use existing get_queryset logic which already filters by company
        data = self.get_queryset()

        # Add company transaction count for each license
        from apps.trade.models import LicenseTrade
        from django.db.models import Q, Count

        try:
            company_id_int = int(company_id)

            for item in data if isinstance(data, list) else []:
                license_id = item.get('license_id')
                license_type = item.get('license_type')

                if license_type == 'DFIA':
                    # Count trades for this license involving the company
                    trade_count = LicenseTrade.objects.filter(
                        Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int),
                        license_type='DFIA',
                        lines__sr_number__license_id=license_id
                    ).count()
                else:
                    # Incentive license
                    trade_count = LicenseTrade.objects.filter(
                        Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int),
                        license_type='INCENTIVE',
                        incentive_lines__incentive_license_id=license_id
                    ).count()

                item['company_transaction_count'] = trade_count

        except (ValueError, TypeError) as e:
            logger.error(f"Invalid company_id: {company_id} - {e}")
            return Response({'error': 'Invalid company ID'}, status=400)

        return Response({'results': data})

    @action(detail=False, methods=['get'], url_path='company-ledger/export')
    def company_ledger_export(self, request):
        """
        Export company-specific ledger to PDF.

        Query params:
        - company: Company ID (required)
        - license_type: Filter by type (default: ALL)
        - active_only: Filter only active licenses (default: true)
        """
        company_id = request.query_params.get('company')

        if not company_id:
            return Response({'error': 'company parameter is required'}, status=400)

        # Get company name
        from apps.core.models import CompanyModel
        try:
            company = CompanyModel.objects.get(pk=int(company_id))
            company_name = company.name
        except (CompanyModel.DoesNotExist, ValueError):
            return Response({'error': 'Company not found'}, status=404)

        # Get filtered data
        data = self.get_queryset()

        # Generate PDF
        pdf_content = self._generate_company_ledger_pdf(data, company_name, request.query_params)

        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        safe_company_name = "".join(c for c in company_name if c.isalnum() or c in (' ', '_')).strip()
        filename = f"company_ledger_{safe_company_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    def _generate_company_ledger_pdf(self, licenses_data, company_name, query_params):
        from apps.license.services.exporters.ledger_pdf import generate_company_ledger_pdf
        return generate_company_ledger_pdf(licenses_data, company_name, query_params)
    @action(detail=False, methods=['get'], url_path='company-wise')
    def company_wise(self, request):
        """
        Returns all trades grouped by company with purchases, sales, and a grand summary.
        """
        from apps.license.services.ledger_service import get_company_wise_trades
        return Response(get_company_wise_trades(request.query_params))

    @action(detail=False, methods=['get'], url_path='license-wise')
    def license_wise(self, request):
        """
        Returns trades grouped by license, then by company within each license.
        Structure: license → [company → purchases/sales/totals]
        """
        from apps.license.services.ledger_service import get_license_wise_trades
        return Response(get_license_wise_trades(request.query_params))
