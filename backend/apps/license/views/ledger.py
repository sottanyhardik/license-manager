"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
import logging
from decimal import Decimal

from django.http import FileResponse
from django.utils import timezone
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

    SECURITY: ALL endpoints are company-scoped:
    - User must have user.company set
    - List/summary/aggregation endpoints return only user's company data
    - Single-license retrieval validates user can access that license
    - Company-specific endpoints validate user.company == requested company

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
        """
        Return unified filtered list of DFIA + Incentive license dicts,
        SCOPED TO USER'S COMPANY.

        SECURITY FIX: Inject user's company_id into query_params before
        delegating to ledger_service, ensuring the user only sees their
        company's data regardless of query parameters.
        """
        from apps.license.services.ledger_service import build_license_queryset
        from copy import copy

        # CRITICAL: Scope all queries to user's company
        if not self.request.user.is_superuser:
            if not hasattr(self.request.user, 'company') or not self.request.user.company:
                # User has no company assignment — return empty queryset
                return []

            # Create a mutable copy of query_params and inject company_id
            scoped_params = copy(self.request.query_params)
            # Force company_id to user's assigned company, overriding any query param
            scoped_params = {**dict(scoped_params), 'company': str(self.request.user.company.id)}
            return build_license_queryset(scoped_params)

        # Superusers can filter by any company or see all
        return build_license_queryset(self.request.query_params)

    def check_object_permissions(self, request, obj):
        """
        Validate object-level access for retrieve and ledger_detail endpoints.

        For single-license views, verify that:
        1. User's company traded this license (from get_queryset scoping)
        2. OR validate explicit company_id param matches user's company
        """
        super().check_object_permissions(request, obj)

        # Superusers bypass object-level checks
        if request.user.is_superuser:
            return

        # Validate company-specific query parameter if provided
        requested_company_id = request.query_params.get('company')
        if requested_company_id:
            try:
                requested_company_id = int(requested_company_id)
                if not hasattr(request.user, 'company') or not request.user.company:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied(
                        detail='User has no company assignment for ledger access.'
                    )
                if requested_company_id != request.user.company.id:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied(
                        detail='You can only access ledger data for your assigned company.'
                    )
            except (ValueError, TypeError):
                from rest_framework.exceptions import ValidationError
                raise ValidationError(
                    detail='Invalid company parameter.'
                )

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

        SECURITY: Validates user's company can access this license via
        explicit LicenseTrade check (P0 IDOR fix).
        """
        from apps.trade.models import LicenseTrade
        from rest_framework.exceptions import PermissionDenied

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

        # SECURITY (P0 IDOR FIX): Validate that user's company traded this license
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                raise PermissionDenied(
                    detail='User has no company assignment for ledger access.'
                )

            # Verify LicenseTrade exists for this license and user's company
            from django.db.models import Q
            trade_exists = LicenseTrade.objects.filter(
                Q(from_company_id=request.user.company.id) | Q(to_company_id=request.user.company.id),
                license_type=found_type,
                **({'lines__sr_number__license_id': license.id} if found_type == 'DFIA' else {'incentive_lines__incentive_license_id': license.id})
            ).exists()

            if not trade_exists:
                raise PermissionDenied(
                    detail='You do not have access to this license. Your company has not traded it.'
                )

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

        SECURITY (P0 DATA LEAKAGE FIX): Forces company_id to user's assigned company
        before calling service, preventing access to other companies' data.
        Only returns data for licenses the user's company traded.
        """
        from apps.license.services.ledger_service import get_ledger_summary
        from copy import copy

        # CRITICAL (P0 FIX): Force company_id to user's company before calling service
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                return Response({'detail': 'User has no company assignment for ledger access.'}, status=403)

            scoped_params = copy(dict(request.query_params))
            scoped_params['company'] = str(request.user.company.id)
        else:
            scoped_params = dict(request.query_params)

        return Response(get_ledger_summary(scoped_params))

    @action(detail=True, methods=['get'])
    def ledger_detail(self, request, pk=None):
        """
        Get detailed ledger view for a specific license showing all transactions.
        Works for both DFIA and Incentive licenses.
        Accepts either ID (integer) or license_number (string) as pk parameter.
        Auto-searches both tables if license_type not specified.

        Optional company parameter: If provided, only shows transactions involving that company.
        SECURITY: If company parameter is provided, it must match user's assigned company.
        User's company must have traded this license (P0 IDOR fix).

        **Phase 4C:** API consumes CanonicalLedgerService as the single source of truth.
        All financial calculations are performed by CanonicalLedgerService; the API layer
        is a transparent serialization layer with no business logic.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.serializers import CanonicalLedgerSerializer
        from rest_framework.exceptions import PermissionDenied
        from apps.trade.models import LicenseTrade
        from django.db.models import Q

        license_type = request.query_params.get('license_type', 'AUTO')
        company_id = request.query_params.get('company')  # Optional company filter

        # SECURITY: Validate company parameter if provided
        if company_id:
            try:
                company_id_int = int(company_id)
                if not request.user.is_superuser:
                    if not hasattr(request.user, 'company') or not request.user.company:
                        raise PermissionDenied(
                            detail='User has no company assignment for ledger access.'
                        )
                    if company_id_int != request.user.company.id:
                        raise PermissionDenied(
                            detail='You can only access ledger data for your assigned company.'
                        )
            except (ValueError, TypeError):
                from rest_framework.exceptions import ValidationError
                raise ValidationError(detail='Invalid company parameter.')

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

        # SECURITY (P0 IDOR FIX): Validate that user's company traded this license
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                raise PermissionDenied(
                    detail='User has no company assignment for ledger access.'
                )

            # Verify LicenseTrade exists for this license and user's company
            trade_exists = LicenseTrade.objects.filter(
                Q(from_company_id=request.user.company.id) | Q(to_company_id=request.user.company.id),
                license_type=found_type,
                **({'lines__sr_number__license_id': license.id} if found_type == 'DFIA' else {'incentive_lines__incentive_license_id': license.id})
            ).exists()

            if not trade_exists:
                raise PermissionDenied(
                    detail='You do not have access to this license. Your company has not traded it.'
                )

        # Delegate all calculation to CanonicalLedgerService (single source of truth).
        # The API is a transparent serialization layer with NO business logic.
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=license.id,
            license_type=found_type
        )

        # Serialize for response (representation only; no calculations)
        serializer = CanonicalLedgerSerializer(dataset)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def available_for_sale(self, request):
        """
        Get licenses with available balance for sale.
        Filters out expired and fully sold licenses.

        SECURITY (P0 DATA LEAKAGE FIX): Scopes results to licenses user's company traded.
        Uses get_queryset() logic which applies company filtering via LicenseTrade check.
        Only returns licenses the user's company owns or traded.
        """
        from apps.license.services.ledger_service import _dfia_ids_with_min_live_balance
        from apps.trade.models import LicenseTrade
        from django.db.models import Q

        min_balance = Decimal(request.query_params.get('min_balance', '100'))

        # CRITICAL (P0 FIX): Get list of license IDs user's company traded
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                return Response({'detail': 'User has no company assignment for ledger access.'}, status=403)

            # Find DFIA licenses traded by user's company
            dfia_traded_ids = set(
                LicenseTrade.objects.filter(
                    Q(from_company_id=request.user.company.id) | Q(to_company_id=request.user.company.id),
                    license_type='DFIA'
                ).values_list('lines__sr_number__license_id', flat=True).distinct()
            )

            # Find Incentive licenses traded by user's company
            incentive_traded_ids = set(
                LicenseTrade.objects.filter(
                    Q(from_company_id=request.user.company.id) | Q(to_company_id=request.user.company.id),
                    license_type='INCENTIVE'
                ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
            )
        else:
            # Superusers can see all licenses
            dfia_traded_ids = None
            incentive_traded_ids = None

        # DFIA with balance. BL-LEDGER-02: the cached `balance__balance_cif`
        # column can be stale, so resolve `min_balance` against the LIVE,
        # batched-computed balance instead of filtering the DB column.
        active_dfia_qs = LicenseDetailsModel.objects.filter(flags__is_expired=False).select_related('exporter', 'port')

        # Apply company scoping for non-superusers
        if dfia_traded_ids is not None:
            active_dfia_qs = active_dfia_qs.filter(id__in=dfia_traded_ids)

        dfia_data = self._prepare_dfia_data(
            active_dfia_qs.filter(id__in=_dfia_ids_with_min_live_balance(active_dfia_qs, min_balance))
        )

        # Incentive with balance
        incentive_qs = IncentiveLicense.objects.filter(
            is_active=True,
            license_expiry_date__gte=timezone.now().date(),
            balance_value__gte=min_balance
        ).select_related('exporter', 'port_code')

        # Apply company scoping for non-superusers
        if incentive_traded_ids is not None:
            incentive_qs = incentive_qs.filter(id__in=incentive_traded_ids)

        incentive_data = self._prepare_incentive_data(incentive_qs)

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

        SECURITY (P0 DATA LEAKAGE FIX): Forces company_id to user's assigned company
        before calling service, preventing access to other companies' data.
        Only returns licenses the user's company traded.
        """
        from apps.license.services.ledger_service import search_licenses
        from copy import copy

        # CRITICAL (P0 FIX): Force company_id to user's company before calling service
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                return Response({'detail': 'User has no company assignment for ledger access.'}, status=403)

            scoped_params = copy(dict(request.query_params))
            scoped_params['company'] = str(request.user.company.id)
        else:
            scoped_params = dict(request.query_params)

        result = search_licenses(scoped_params)
        if result is None:
            return Response({'error': 'Search query parameter "q" is required'}, status=400)
        return Response(result)


    @action(detail=False, methods=['get'], url_path='company-ledger')
    def company_ledger(self, request):
        """
        Get ledger view for a specific company showing only licenses
        where the company appears in trades (either as buyer or seller).

        Query params:
        - company: Company ID (required, must match user's assigned company)
        - license_type: Filter by type (DFIA, INCENTIVE, etc.) - default: ALL
        - active_only: Filter only active licenses (default: true)

        SECURITY: Validates that the requested company matches user's assigned company.
        """
        from rest_framework.exceptions import PermissionDenied, ValidationError
        from apps.trade.models import LicenseTrade
        from django.db.models import Q, Count

        company_id = request.query_params.get('company')

        if not company_id:
            return Response({'error': 'company parameter is required'}, status=400)

        # SECURITY: Validate company parameter
        try:
            company_id_int = int(company_id)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid company ID'}, status=400)

        # SECURITY: Non-superusers can only access their assigned company
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                raise PermissionDenied(
                    detail='User has no company assignment for ledger access.'
                )
            if company_id_int != request.user.company.id:
                raise PermissionDenied(
                    detail='You can only access ledger data for your assigned company.'
                )

        # Use existing get_queryset logic which already filters by company
        data = self.get_queryset()

        # Add company transaction count for each license
        try:
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

        except Exception as e:
            logger.error(f"Error processing company ledger: {company_id} - {e}")
            return Response({'error': 'Error processing company ledger'}, status=500)

        return Response({'results': data})

    @action(detail=False, methods=['get'], url_path='company-wise')
    def company_wise(self, request):
        """
        Returns all trades grouped by company with purchases, sales, and a grand summary.

        SECURITY (P1 AGGREGATION DATA LEAKAGE FIX): Forces company_id to user's assigned company
        before calling service, preventing access to other companies' aggregation data.
        Only returns aggregation for licenses the user's company traded.
        """
        from apps.license.services.ledger_service import get_company_wise_trades
        from copy import copy

        # CRITICAL (P1 FIX): Force company_id to user's company before calling service
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                return Response({'detail': 'User has no company assignment for ledger access.'}, status=403)

            scoped_params = copy(dict(request.query_params))
            scoped_params['company'] = str(request.user.company.id)
        else:
            scoped_params = dict(request.query_params)

        return Response(get_company_wise_trades(scoped_params))

    @action(detail=False, methods=['get'], url_path='license-wise')
    def license_wise(self, request):
        """
        Returns trades grouped by license, then by company within each license.
        Structure: license → [company → purchases/sales/totals]

        SECURITY (P1 AGGREGATION DATA LEAKAGE FIX): Forces company_id to user's assigned company
        before calling service, preventing access to other companies' aggregation data.
        Only returns aggregation for licenses the user's company traded.
        """
        from apps.license.services.ledger_service import get_license_wise_trades
        from copy import copy

        # CRITICAL (P1 FIX): Force company_id to user's company before calling service
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                return Response({'detail': 'User has no company assignment for ledger access.'}, status=403)

            scoped_params = copy(dict(request.query_params))
            scoped_params['company'] = str(request.user.company.id)
        else:
            scoped_params = dict(request.query_params)

        return Response(get_license_wise_trades(scoped_params))

    @action(detail=False, methods=['get'], url_path='export/all')
    def export_pdf(self, request):
        """
        Export Financial Ledger as PDF.

        Route: GET /api/license-ledger/export/all/

        Data flow:
        1. Get license by ID or number
        2. Validate permissions (company isolation)
        3. Build canonical dataset from CanonicalLedgerService
        4. Render to PDF using pure renderer
        5. Return PDF file

        SECURITY: Validates user can access this license (same as ledger_detail)
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.services.exporters.financial_ledger_pdf_renderer import render_financial_ledger_pdf
        from rest_framework.exceptions import PermissionDenied
        from apps.trade.models import LicenseTrade
        from django.db.models import Q

        license_id = request.query_params.get('license_id')
        if not license_id:
            return Response({'error': 'license_id parameter is required'}, status=400)

        license_type = request.query_params.get('license_type', 'AUTO')

        # Find the license
        if license_type == 'DFIA':
            found_type, license = self._find_license_by_id_or_number(license_id, search_dfia=True, search_incentive=False)
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            found_type, license = self._find_license_by_id_or_number(license_id, search_dfia=False, search_incentive=True)
        else:
            found_type, license = self._find_license_by_id_or_number(license_id, search_dfia=True, search_incentive=True)

        if not license:
            return Response({'error': f'License not found: {license_id}'}, status=404)

        # SECURITY: Validate permissions
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                raise PermissionDenied(detail='User has no company assignment for ledger access.')

            trade_exists = LicenseTrade.objects.filter(
                Q(from_company_id=request.user.company.id) | Q(to_company_id=request.user.company.id),
                license_type=found_type,
                **({'lines__sr_number__license_id': license.id} if found_type == 'DFIA' else {'incentive_lines__incentive_license_id': license.id})
            ).exists()

            if not trade_exists:
                raise PermissionDenied(detail='You do not have access to this license.')

        # Build canonical dataset (single source of truth)
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=license.id,
            license_type=found_type
        )

        # Render to PDF using pure renderer
        pdf_buffer = render_financial_ledger_pdf(dataset)
        pdf_buffer.seek(0)

        # Return PDF file
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f'financial-ledger-{license.license_number}.pdf',
            content_type='application/pdf'
        )

    @action(detail=False, methods=['get'], url_path='export/excel')
    def export_excel(self, request):
        """
        Export Financial Ledger as Excel.

        Route: GET /api/license-ledger/export/excel/

        Data flow:
        1. Get license by ID or number
        2. Validate permissions (company isolation)
        3. Build canonical dataset from CanonicalLedgerService
        4. Render to Excel using pure renderer
        5. Return Excel file

        SECURITY: Validates user can access this license (same as ledger_detail)
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.services.exporters.financial_ledger_excel_renderer import render_single_license_excel
        from apps.license.services.exporters.dto import FinancialLedgerExportDTO
        from rest_framework.exceptions import PermissionDenied
        from apps.trade.models import LicenseTrade
        from django.db.models import Q

        license_id = request.query_params.get('license_id')
        if not license_id:
            return Response({'error': 'license_id parameter is required'}, status=400)

        license_type = request.query_params.get('license_type', 'AUTO')

        # Find the license
        if license_type == 'DFIA':
            found_type, license = self._find_license_by_id_or_number(license_id, search_dfia=True, search_incentive=False)
        elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            found_type, license = self._find_license_by_id_or_number(license_id, search_dfia=False, search_incentive=True)
        else:
            found_type, license = self._find_license_by_id_or_number(license_id, search_dfia=True, search_incentive=True)

        if not license:
            return Response({'error': f'License not found: {license_id}'}, status=404)

        # SECURITY: Validate permissions
        if not request.user.is_superuser:
            if not hasattr(request.user, 'company') or not request.user.company:
                raise PermissionDenied(detail='User has no company assignment for ledger access.')

            trade_exists = LicenseTrade.objects.filter(
                Q(from_company_id=request.user.company.id) | Q(to_company_id=request.user.company.id),
                license_type=found_type,
                **({'lines__sr_number__license_id': license.id} if found_type == 'DFIA' else {'incentive_lines__incentive_license_id': license.id})
            ).exists()

            if not trade_exists:
                raise PermissionDenied(detail='You do not have access to this license.')

        # Build canonical dataset (single source of truth)
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            license_id=license.id,
            license_type=found_type
        )

        # Convert to DTO and render to Excel
        dto = FinancialLedgerExportDTO.from_canonical(dataset)
        excel_buffer = render_single_license_excel(dto)
        excel_buffer.seek(0)

        # Return Excel file
        return FileResponse(
            excel_buffer,
            as_attachment=True,
            filename=f'financial-ledger-{license.license_number}.xlsx',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
