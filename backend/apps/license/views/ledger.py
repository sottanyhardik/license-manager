"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
import logging
from decimal import Decimal
from io import BytesIO
from datetime import datetime

from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LicenseLedgerViewPermission

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

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
        """
        Return unified queryset combining DFIA and Incentive licenses.
        """
        license_type = self.request.query_params.get('license_type', 'ALL')
        min_balance = self.request.query_params.get('min_balance')
        exporter_id = self.request.query_params.get('exporter')
        company_id = self.request.query_params.get('company')  # Filter by company in trades
        no_purchases = self.request.query_params.get('no_purchases', 'false').lower() == 'true'  # Filter licenses without purchases
        is_active_only = self.request.query_params.get('active_only', 'true').lower() == 'true'
        purchase_date_from = self.request.query_params.get('purchase_date_from')
        purchase_date_to = self.request.query_params.get('purchase_date_to')

        # Get DFIA licenses
        dfia_qs = LicenseDetailsModel.objects.select_related('exporter', 'port').all()

        # Get Incentive licenses
        incentive_qs = IncentiveLicense.objects.select_related('exporter', 'port_code').all()

        # Apply filters
        # When a company filter is active, skip active_only so fully-used or expired licenses
        # that have trades with that company are still shown in the company's history.
        if is_active_only and not company_id:
            dfia_qs = dfia_qs.filter(flags__is_expired=False)
            # IncentiveLicense has its own direct `is_active` field — no flags sub-table here.
            incentive_qs = incentive_qs.filter(is_active=True, license_expiry_date__gte=timezone.now().date())

        if exporter_id:
            dfia_qs = dfia_qs.filter(exporter_id=exporter_id)
            incentive_qs = incentive_qs.filter(exporter_id=exporter_id)

        if min_balance:
            try:
                min_bal = Decimal(min_balance)
                dfia_qs = dfia_qs.filter(balance__balance_cif__gte=min_bal)
                incentive_qs = incentive_qs.filter(balance_value__gte=min_bal)
            except (ValueError, TypeError):
                pass

        # Filter by purchase date range — skipped when a company filter is active
        # (same rationale as active_only: show the full company history, not just one FY)
        if (purchase_date_from or purchase_date_to) and not company_id:
            from apps.trade.models import LicenseTrade
            from datetime import datetime

            # Get license IDs that have purchases within date range
            dfia_purchase_filter = {}
            incentive_purchase_filter = {}

            if purchase_date_from:
                try:
                    date_from = datetime.strptime(purchase_date_from, '%Y-%m-%d').date()
                    dfia_purchase_filter['invoice_date__gte'] = date_from
                    incentive_purchase_filter['invoice_date__gte'] = date_from
                except ValueError:
                    pass

            if purchase_date_to:
                try:
                    date_to = datetime.strptime(purchase_date_to, '%Y-%m-%d').date()
                    dfia_purchase_filter['invoice_date__lte'] = date_to
                    incentive_purchase_filter['invoice_date__lte'] = date_to
                except ValueError:
                    pass

            if dfia_purchase_filter:
                # Get DFIA licenses that have purchases in the date range
                dfia_license_ids = LicenseTrade.objects.filter(
                    license_type='DFIA',
                    direction='PURCHASE',
                    **dfia_purchase_filter
                ).values_list('lines__sr_number__license_id', flat=True).distinct()
                dfia_qs = dfia_qs.filter(id__in=dfia_license_ids)

            if incentive_purchase_filter:
                # Get Incentive licenses that have purchases in the date range
                incentive_license_ids = LicenseTrade.objects.filter(
                    license_type='INCENTIVE',
                    direction='PURCHASE',
                    **incentive_purchase_filter
                ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
                incentive_qs = incentive_qs.filter(id__in=incentive_license_ids)

        # Filter by company (show licenses where company appears in from_company OR to_company of trades)
        if company_id:
            from apps.trade.models import LicenseTrade
            from django.db.models import Q

            try:
                company_id_int = int(company_id)

                # Get DFIA licenses that have trades with this company
                dfia_license_ids = LicenseTrade.objects.filter(
                    Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int),
                    license_type='DFIA'
                ).values_list('lines__sr_number__license_id', flat=True).distinct()
                dfia_qs = dfia_qs.filter(id__in=dfia_license_ids)

                # Get Incentive licenses that have trades with this company
                incentive_license_ids = LicenseTrade.objects.filter(
                    Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int),
                    license_type='INCENTIVE'
                ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
                incentive_qs = incentive_qs.filter(id__in=incentive_license_ids)

            except (ValueError, TypeError):
                logger.warning(f"Invalid company_id: {company_id}")
                pass

        # Filter licenses without purchases (no purchase trades)
        if no_purchases:
            from apps.trade.models import LicenseTrade

            # Get licenses that have purchase trades
            dfia_with_purchases = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='PURCHASE'
            ).values_list('lines__sr_number__license_id', flat=True).distinct()

            incentive_with_purchases = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='PURCHASE'
            ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()

            # Exclude licenses that have purchases
            dfia_qs = dfia_qs.exclude(id__in=dfia_with_purchases)
            incentive_qs = incentive_qs.exclude(id__in=incentive_with_purchases)

        # Filter by license type
        if license_type == 'DFIA':
            return self._prepare_dfia_data(dfia_qs)
        elif license_type in ['RODTEP', 'ROSTL', 'MEIS', 'INCENTIVE']:
            if license_type != 'INCENTIVE':
                incentive_qs = incentive_qs.filter(license_type=license_type)
            return self._prepare_incentive_data(incentive_qs)
        else:
            # Return both (ALL)
            dfia_data = self._prepare_dfia_data(dfia_qs)
            incentive_data = self._prepare_incentive_data(incentive_qs)
            # Combine and sort
            combined = list(dfia_data) + list(incentive_data)
            # Sort by license_date, putting None values at the end
            from datetime import date
            combined.sort(key=lambda x: x.get('license_date') or date.min, reverse=True)
            return combined

    def _prepare_dfia_data(self, queryset):
        """Prepare DFIA license data for ledger view"""
        from apps.trade.models import LicenseTrade
        from django.db.models import Sum, Q

        # Fetch all licenses with related data in one query
        licenses = list(queryset.select_related('exporter', 'port'))
        if not licenses:
            return []

        license_ids = [lic.id for lic in licenses]

        # Batch all 4 aggregate queries into 2 group-by queries instead of 4N queries
        purchase_totals = (
            LicenseTrade.objects
            .filter(license_type='DFIA', direction='PURCHASE', lines__sr_number__license_id__in=license_ids)
            .values('lines__sr_number__license_id')
            .annotate(total_inr=Sum('lines__amount_inr'), total_usd=Sum('lines__cif_fc'))
        )
        sale_totals = (
            LicenseTrade.objects
            .filter(license_type='DFIA', direction='SALE', lines__sr_number__license_id__in=license_ids)
            .values('lines__sr_number__license_id')
            .annotate(total_inr=Sum('lines__amount_inr'), total_usd=Sum('lines__cif_fc'))
        )

        purchase_map = {r['lines__sr_number__license_id']: r for r in purchase_totals}
        sale_map = {r['lines__sr_number__license_id']: r for r in sale_totals}

        data = []
        for license in licenses:
            pur_row = purchase_map.get(license.id, {})
            sal_row = sale_map.get(license.id, {})

            purchase_amount_inr = float(pur_row.get('total_inr') or 0)
            purchase_amount_usd = float(pur_row.get('total_usd') or 0)
            sale_amount_inr = float(sal_row.get('total_inr') or 0)
            sale_amount_usd = float(sal_row.get('total_usd') or 0)

            profit_loss = sale_amount_inr - purchase_amount_inr
            balance_usd = purchase_amount_usd - sale_amount_usd

            data.append({
                'id': license.id,
                'license_type': 'DFIA',
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port.name if license.port else '',
                'total_value': purchase_amount_usd,
                'balance_value': balance_usd,
                'sold_value': sale_amount_usd,
                'purchase_amount': purchase_amount_inr,
                'sale_amount': sale_amount_inr,
                'profit_loss': profit_loss,
                'currency': 'USD',
                'is_expired': license.is_expired,
                'is_active': not license.is_expired,
                'sold_status': self._get_sold_status(purchase_amount_usd, balance_usd),
            })
        return data

    def _prepare_incentive_data(self, queryset):
        """Prepare Incentive license data for ledger view"""
        from apps.trade.models import LicenseTrade
        from django.db.models import Sum

        licenses = list(queryset.select_related('exporter', 'port_code'))
        if not licenses:
            return []

        license_ids = [lic.id for lic in licenses]
        today = timezone.now().date()

        # Batch all 4 aggregate queries into 2 group-by queries instead of 4N queries
        purchase_totals = (
            LicenseTrade.objects
            .filter(license_type='INCENTIVE', direction='PURCHASE', incentive_lines__incentive_license_id__in=license_ids)
            .values('incentive_lines__incentive_license_id')
            .annotate(total_inr=Sum('incentive_lines__amount_inr'), total_value=Sum('incentive_lines__license_value'))
        )
        sale_totals = (
            LicenseTrade.objects
            .filter(license_type='INCENTIVE', direction='SALE', incentive_lines__incentive_license_id__in=license_ids)
            .values('incentive_lines__incentive_license_id')
            .annotate(total_inr=Sum('incentive_lines__amount_inr'), total_value=Sum('incentive_lines__license_value'))
        )

        purchase_map = {r['incentive_lines__incentive_license_id']: r for r in purchase_totals}
        sale_map = {r['incentive_lines__incentive_license_id']: r for r in sale_totals}

        data = []
        for license in licenses:
            pur_row = purchase_map.get(license.id, {})
            sal_row = sale_map.get(license.id, {})

            purchase_amount_inr = float(pur_row.get('total_inr') or 0)
            purchase_value_inr = float(pur_row.get('total_value') or 0)
            sale_amount_inr = float(sal_row.get('total_inr') or 0)
            sale_value_inr = float(sal_row.get('total_value') or 0)

            profit_loss = sale_amount_inr - purchase_amount_inr
            balance_inr = purchase_value_inr - sale_value_inr

            data.append({
                'id': license.id,
                'license_type': license.license_type,
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port_code.name if license.port_code else '',
                'total_value': purchase_value_inr,
                'balance_value': balance_inr,
                'sold_value': sale_value_inr,
                'purchase_amount': purchase_amount_inr,
                'sale_amount': sale_amount_inr,
                'profit_loss': profit_loss,
                'currency': 'INR',
                'is_expired': license.license_expiry_date < today if license.license_expiry_date else False,
                'is_active': license.is_active,
                'sold_status': self._get_sold_status(purchase_value_inr, balance_inr),
            })
        return data

    def _get_sold_status(self, total, balance):
        """Calculate sold status for DFIA licenses"""
        if balance <= 0:
            return 'YES'
        elif balance >= total:
            return 'NO'
        else:
            return 'PARTIAL'

    def _get_incentive_breakdown(self, incentive_qs):
        """
        Return per-type count and balance for RODTEP/ROSTL/MEIS in a single DB query
        instead of 6 queries (count + sum loop × 3 types).
        """
        from django.db.models import Count, Sum
        rows = (
            incentive_qs
            .filter(license_type__in=['RODTEP', 'ROSTL', 'MEIS'])
            .values('license_type')
            .annotate(count=Count('id'), balance=Sum('balance_value'))
        )
        breakdown = {
            row['license_type']: {
                'count': row['count'],
                'balance': round(float(row['balance'] or 0), 2),
            }
            for row in rows
        }
        # Fill any missing types with zeros
        for lt in ['RODTEP', 'ROSTL', 'MEIS']:
            if lt not in breakdown:
                breakdown[lt] = {'count': 0, 'balance': 0.0}
        return breakdown

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
        from django.utils import timezone
        from apps.trade.models import LicenseTrade
        from django.db.models import Sum, Q

        # Get filter parameters
        company_id = request.query_params.get('company')
        license_type = request.query_params.get('license_type', 'ALL')
        is_active_only = request.query_params.get('active_only', 'true').lower() == 'true'
        min_balance = request.query_params.get('min_balance')
        purchase_date_from = request.query_params.get('purchase_date_from')
        purchase_date_to = request.query_params.get('purchase_date_to')

        # DFIA Summary
        if is_active_only:
            dfia_qs = LicenseDetailsModel.objects.filter(flags__is_expired=False)
        else:
            dfia_qs = LicenseDetailsModel.objects.all()

        # Incentive Summary
        if is_active_only:
            incentive_qs = IncentiveLicense.objects.filter(
                is_active=True,
                license_expiry_date__gte=timezone.now().date()
            )
        else:
            incentive_qs = IncentiveLicense.objects.all()

        # Filter by min_balance
        if min_balance:
            try:
                min_bal = Decimal(min_balance)
                dfia_qs = dfia_qs.filter(balance__balance_cif__gte=min_bal)
                incentive_qs = incentive_qs.filter(balance_value__gte=min_bal)
            except (ValueError, TypeError):
                pass

        # Filter by purchase date range
        if purchase_date_from or purchase_date_to:
            from datetime import datetime

            dfia_purchase_filter = {}
            incentive_purchase_filter = {}

            if purchase_date_from:
                try:
                    date_from = datetime.strptime(purchase_date_from, '%Y-%m-%d').date()
                    dfia_purchase_filter['invoice_date__gte'] = date_from
                    incentive_purchase_filter['invoice_date__gte'] = date_from
                except ValueError:
                    pass

            if purchase_date_to:
                try:
                    date_to = datetime.strptime(purchase_date_to, '%Y-%m-%d').date()
                    dfia_purchase_filter['invoice_date__lte'] = date_to
                    incentive_purchase_filter['invoice_date__lte'] = date_to
                except ValueError:
                    pass

            if dfia_purchase_filter:
                dfia_license_ids = LicenseTrade.objects.filter(
                    license_type='DFIA',
                    direction='PURCHASE',
                    **dfia_purchase_filter
                ).values_list('lines__sr_number__license_id', flat=True).distinct()
                dfia_qs = dfia_qs.filter(id__in=dfia_license_ids)

            if incentive_purchase_filter:
                incentive_license_ids = LicenseTrade.objects.filter(
                    license_type='INCENTIVE',
                    direction='PURCHASE',
                    **incentive_purchase_filter
                ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
                incentive_qs = incentive_qs.filter(id__in=incentive_license_ids)

        # Filter by company if specified
        if company_id:
            try:
                company_id_int = int(company_id)

                # Get DFIA licenses that have trades with this company
                dfia_license_ids = LicenseTrade.objects.filter(
                    Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int),
                    license_type='DFIA'
                ).values_list('lines__sr_number__license_id', flat=True).distinct()
                dfia_qs = dfia_qs.filter(id__in=dfia_license_ids)

                # Get Incentive licenses that have trades with this company
                incentive_license_ids = LicenseTrade.objects.filter(
                    Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int),
                    license_type='INCENTIVE'
                ).values_list('incentive_lines__incentive_license_id', flat=True).distinct()
                incentive_qs = incentive_qs.filter(id__in=incentive_license_ids)

            except (ValueError, TypeError):
                logger.warning(f"Invalid company_id in summary: {company_id}")
                pass

        # Filter by license type
        if license_type != 'ALL':
            if license_type == 'DFIA':
                incentive_qs = IncentiveLicense.objects.none()
            elif license_type in ['RODTEP', 'ROSTL', 'MEIS', 'INCENTIVE']:
                dfia_qs = LicenseDetailsModel.objects.none()
                if license_type != 'INCENTIVE':
                    incentive_qs = incentive_qs.filter(license_type=license_type)

        from django.db.models import Count

        # opening_balance == per-licence SUM(export cif_fc) (LicenseBalanceCalculator
        # .calculate_credit). Previously this summed a @cached_property in a Python loop,
        # firing one aggregate query PER licence (an N+1 over the whole filtered set).
        # Compute the same per-licence sums in ONE annotated query and sum them the same
        # way (float per row) to preserve the exact result.
        from decimal import Decimal as _Dec
        from django.db.models import Value, DecimalField
        from django.db.models.functions import Coalesce
        _opening_rows = dfia_qs.annotate(
            _opening=Coalesce(Sum('export_license__cif_fc'), Value(_Dec('0')), output_field=DecimalField())
        ).values_list('_opening', flat=True)
        dfia_total = sum(float(v or 0) for v in _opening_rows)
        # balance_cif is a DB column on the LicenseBalance sub-table — aggregate via the OneToOne relation
        dfia_balance = float(dfia_qs.aggregate(balance=Sum('balance__balance_cif'))['balance'] or 0)
        dfia_sold = dfia_total - dfia_balance

        # license_value, balance_value, sold_value are all real DB columns on IncentiveLicense
        incentive_agg = incentive_qs.aggregate(
            total=Sum('license_value'),
            balance=Sum('balance_value'),
            sold=Sum('sold_value'),
        )
        incentive_total = float(incentive_agg['total'] or 0)
        incentive_balance = float(incentive_agg['balance'] or 0)
        incentive_sold = float(incentive_agg['sold'] or 0)

        # Calculate purchase and sale amounts from trades
        # Build base trade filters
        dfia_trade_filter = {'license_type': 'DFIA'}
        incentive_trade_filter = {'license_type': 'INCENTIVE'}

        # Add date range filters for trades
        if purchase_date_from:
            try:
                date_from = datetime.strptime(purchase_date_from, '%Y-%m-%d').date()
                dfia_trade_filter['invoice_date__gte'] = date_from
                incentive_trade_filter['invoice_date__gte'] = date_from
            except ValueError:
                pass

        if purchase_date_to:
            try:
                date_to = datetime.strptime(purchase_date_to, '%Y-%m-%d').date()
                dfia_trade_filter['invoice_date__lte'] = date_to
                incentive_trade_filter['invoice_date__lte'] = date_to
            except ValueError:
                pass

        # Build query with company and date filters
        if company_id:
            try:
                company_id_int = int(company_id)
                company_q = Q(from_company_id=company_id_int) | Q(to_company_id=company_id_int)

                dfia_purchases = LicenseTrade.objects.filter(
                    company_q,
                    direction='PURCHASE',
                    **dfia_trade_filter
                ).aggregate(total=Sum('total_amount'))['total'] or 0

                dfia_sales = LicenseTrade.objects.filter(
                    company_q,
                    direction='SALE',
                    **dfia_trade_filter
                ).aggregate(total=Sum('total_amount'))['total'] or 0

                incentive_purchases = LicenseTrade.objects.filter(
                    company_q,
                    direction='PURCHASE',
                    **incentive_trade_filter
                ).aggregate(total=Sum('total_amount'))['total'] or 0

                incentive_sales = LicenseTrade.objects.filter(
                    company_q,
                    direction='SALE',
                    **incentive_trade_filter
                ).aggregate(total=Sum('total_amount'))['total'] or 0

            except (ValueError, TypeError):
                dfia_purchases = dfia_sales = incentive_purchases = incentive_sales = 0
        else:
            dfia_purchases = LicenseTrade.objects.filter(
                direction='PURCHASE',
                **dfia_trade_filter
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            dfia_sales = LicenseTrade.objects.filter(
                direction='SALE',
                **dfia_trade_filter
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            incentive_purchases = LicenseTrade.objects.filter(
                direction='PURCHASE',
                **incentive_trade_filter
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            incentive_sales = LicenseTrade.objects.filter(
                direction='SALE',
                **incentive_trade_filter
            ).aggregate(total=Sum('total_amount'))['total'] or 0

        dfia_profit = float(dfia_sales) - float(dfia_purchases)
        incentive_profit = float(incentive_sales) - float(incentive_purchases)

        return Response({
            'dfia': {
                'total_licenses': dfia_qs.count(),
                'total_value_usd': round(dfia_total, 2),
                'sold_value_usd': round(dfia_sold, 2),
                'balance_value_usd': round(dfia_balance, 2),
                'purchase_amount_inr': round(float(dfia_purchases), 2),
                'sale_amount_inr': round(float(dfia_sales), 2),
                'profit_loss_inr': round(dfia_profit, 2),
            },
            'incentive': {
                'total_licenses': incentive_qs.count(),
                'total_value_inr': round(incentive_total, 2),
                'sold_value_inr': round(incentive_sold, 2),
                'balance_value_inr': round(incentive_balance, 2),
                'purchase_amount_inr': round(float(incentive_purchases), 2),
                'sale_amount_inr': round(float(incentive_sales), 2),
                'profit_loss_inr': round(incentive_profit, 2),
                'breakdown': self._get_incentive_breakdown(incentive_qs)
            }
        })

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

        # Now process based on found type
        if found_type == 'DFIA':
            # License already found by helper function, just process it
            # Get all trades for this license
            trades_query = LicenseTrade.objects.filter(
                license_type='DFIA',
                lines__sr_number__license=license
            )

            # Direction-aware company filter:
            # - PURCHASE/COMMISSION_PURCHASE: company is the BUYER (to_company)
            # - SALE/COMMISSION_SALE: company is the SELLER (from_company)
            # This shows only transactions owned by the company, not ones where they
            # are merely the counterparty (e.g. "Sale to LABDHI" is the SELLER's entry).
            if company_id:
                trades_query = trades_query.filter(
                    Q(direction__in=['PURCHASE', 'COMMISSION_PURCHASE'], to_company_id=company_id) |
                    Q(direction__in=['SALE', 'COMMISSION_SALE'], from_company_id=company_id)
                )

            trades = trades_query.prefetch_related(
                'lines__sr_number__items__sion_norm_class',
                'from_company',
                'to_company',
            ).distinct().order_by('invoice_date', 'id')

            transactions = []
            running_balance = 0

            # Track purchase and sales amounts for profit/loss calculation
            total_purchase_cif = 0
            total_purchase_amount = 0
            total_sales_amount = 0  # Track total sales amount for simple profit calculation

            # Per-company purchase tracking for correct P/L per sale
            company_purchase_cif = {}    # company_id -> cumulative purchase CIF USD
            company_purchase_amount = {} # company_id -> cumulative purchase INR

            # Get all trades and sort: purchases always before sales (regardless of date)
            # so running balance and P/L are calculated correctly even when a sale is
            # recorded before its corresponding purchase in chronological order.
            all_trans = []
            for trade in trades:
                all_trans.append((trade.direction, trade.invoice_date or timezone.now().date(), trade))

            all_trans.sort(key=lambda x: (x[0] not in ['PURCHASE', 'COMMISSION_PURCHASE'], x[1]))

            # If there are no trades but there's an opening balance, add it first
            if len(all_trans) == 0 and float(license.opening_balance or 0) > 0:
                opening_cif = float(license.opening_balance or 0)
                running_balance = opening_cif
                total_purchase_cif = opening_cif
                # Opening balance has no cost (original license at face value)
                total_purchase_amount = 0

                transactions.append({
                    'date': license.license_date,
                    'type': 'OPENING',
                    'particular': f'Opening Balance - Original DFIA License',
                    'invoice_number': license.license_number,
                    'cif_usd': opening_cif,
                    'debit_cif': opening_cif,  # Opening balance is debit
                    'credit_cif': 0,
                    'rate': 0,
                    'amount': 0,
                    'debit_amount': 0,  # No cost for original license
                    'credit_amount': 0,
                    'balance': round(running_balance, 2),
                    'profit_loss': 0,
                })

            # Process transactions (all are LicenseTrade objects)
            # The queryset is already filtered to only trades involving the company (from_company or to_company),
            # so no additional per-transaction filtering is needed here.
            for idx, (trans_type, trans_date, trans_obj) in enumerate(all_trans):
                # Get all lines for this trade that belong to THIS specific license
                total_cif_usd = 0
                total_amount = 0
                items_desc = []

                sion_norms = []  # Collect SION norms for this transaction
                qty_kg_total = 0.0
                for line in trans_obj.lines.all():
                    # Only include lines that reference THIS specific license
                    if line.sr_number and line.sr_number.license_id != license.id:
                        continue

                    # For DFIA trades, we need CIF in USD
                    # If exc_rate is available and cif_inr is set, calculate: cif_usd = cif_inr / exc_rate
                    # Otherwise use cif_fc directly (which should be in USD for DFIA)
                    try:
                        if line.exc_rate and line.cif_inr:
                            exc_rate = float(line.exc_rate)
                            if exc_rate > 0:
                                cif_usd = float(line.cif_inr) / exc_rate
                            else:
                                logger.warning(f"Invalid exchange rate {exc_rate} for line {line.id}")
                                cif_usd = float(line.cif_fc or 0)
                        else:
                            cif_usd = float(line.cif_fc or 0)
                    except (ValueError, TypeError, ZeroDivisionError) as e:
                        logger.error(f"Error calculating CIF USD for line {line.id}: {e}")
                        cif_usd = 0

                    total_cif_usd += cif_usd
                    total_amount += float(line.amount_inr or 0)
                    # qty_kg only counted for lines that have a valid sr_number (matches original logic)
                    if line.sr_number:
                        qty_kg_total += float(line.qty_kg or 0)

                    # Collect item names and SION norms
                    if line.sr_number:
                        # Get all items linked to this sr_number (import item) — prefetched
                        for item in line.sr_number.items.all():
                            if item.name:
                                items_desc.append(item.name)
                            # Collect SION norm class if available — prefetched
                            if item.sion_norm_class:
                                sion_norm = item.sion_norm_class.norm_class
                                if sion_norm and sion_norm not in sion_norms:
                                    sion_norms.append(sion_norm)

                # Calculate rate and update balance
                try:
                    if total_cif_usd > 0:
                        rate = total_amount / total_cif_usd
                    else:
                        rate = 0
                except (ZeroDivisionError, TypeError, ValueError) as e:
                    logger.error(f"Error calculating rate: total_amount={total_amount}, total_cif_usd={total_cif_usd}, error={e}")
                    rate = 0

                if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
                    running_balance += total_cif_usd
                    total_purchase_cif += total_cif_usd
                    total_purchase_amount += total_amount

                    # Track per-company so each company's sales use their own avg cost
                    _buyer_id = trans_obj.to_company.id if trans_obj.to_company else None
                    if _buyer_id and trans_type == 'PURCHASE':
                        company_purchase_cif[_buyer_id] = company_purchase_cif.get(_buyer_id, 0) + total_cif_usd
                        company_purchase_amount[_buyer_id] = company_purchase_amount.get(_buyer_id, 0) + total_amount

                    # Commission entries are always shown as expenses (debit)
                    is_commission = trans_type == 'COMMISSION_PURCHASE'
                    txn_type = 'COMMISSION' if is_commission else 'PURCHASE'
                    particular_prefix = 'Commission Paid to' if is_commission else 'Purchase DFIA -'

                    # First purchase is the opening balance (only if no original opening balance and not commission)
                    _co = trans_obj.to_company
                    if idx == 0 and len(transactions) == 0 and not is_commission:
                        transactions.append({
                            'date': trans_date,
                            'type': 'OPENING',
                            'particular': f'Opening Balance - Purchase from {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'cif_usd': total_cif_usd,
                            'debit_cif': total_cif_usd,
                            'credit_cif': 0,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': total_amount,
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trans_obj.id,
                        })
                    else:
                        transactions.append({
                            'date': trans_date,
                            'type': txn_type,
                            'particular': f'{particular_prefix} {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                            'qty': qty_kg_total,
                            'cif_usd': total_cif_usd,
                            'debit_cif': total_cif_usd,
                            'credit_cif': 0,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': total_amount,
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trans_obj.id,
                        })

                elif trans_type in ['SALE', 'COMMISSION_SALE']:
                    is_commission = trans_type == 'COMMISSION_SALE'
                    _co = trans_obj.from_company

                    if is_commission:
                        running_balance += total_cif_usd
                        total_purchase_amount += total_amount

                        transactions.append({
                            'date': trans_date,
                            'type': 'COMMISSION',
                            'particular': f'Commission Paid to {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                            'qty': qty_kg_total,
                            'cif_usd': total_cif_usd,
                            'debit_cif': total_cif_usd,
                            'credit_cif': 0,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': total_amount,
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trans_obj.id,
                        })
                    else:
                        running_balance -= total_cif_usd
                        total_sales_amount += total_amount

                        # Per-sale P/L using this company's own avg purchase cost
                        _seller_id = trans_obj.from_company.id if trans_obj.from_company else None
                        _co_cif = company_purchase_cif.get(_seller_id, 0) if _seller_id else 0
                        _co_amt = company_purchase_amount.get(_seller_id, 0) if _seller_id else 0
                        if _co_cif > 0:
                            avg_purchase_rate = _co_amt / _co_cif
                            purchase_cost_for_sale = total_cif_usd * avg_purchase_rate
                            sale_profit_loss = round(total_amount - purchase_cost_for_sale, 2)
                        elif total_purchase_cif > 0:
                            # Fallback to global avg if no per-company purchase found
                            avg_purchase_rate = total_purchase_amount / total_purchase_cif
                            purchase_cost_for_sale = total_cif_usd * avg_purchase_rate
                            sale_profit_loss = round(total_amount - purchase_cost_for_sale, 2)
                        else:
                            sale_profit_loss = round(total_amount, 2)

                        transactions.append({
                            'date': trans_date,
                            'type': 'SALE',
                            'particular': f'DFIA Sale - {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                            'qty': qty_kg_total,
                            'cif_usd': total_cif_usd,
                            'debit_cif': 0,
                            'credit_cif': total_cif_usd,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': 0,
                            'credit_amount': total_amount,
                            'balance': round(running_balance, 2),
                            'profit_loss': sale_profit_loss,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trans_obj.id,
                        })

            return Response({
                'license_type': 'DFIA',
                'license_number': license.license_number,
                'license_date': license.license_date,
                'expiry_date': license.license_expiry_date,
                'exporter': license.exporter.name if license.exporter else '',
                'port': license.port.name if license.port else '',
                'total_value': total_purchase_cif,
                'available_balance': round(running_balance, 2),
                'db_balance': float(license.balance_cif or 0),
                'transactions': transactions,
            })

        else:  # INCENTIVE
            # License already found by helper function, just process it
            transactions = []
            running_balance = 0

            # Track purchase rates for profit/loss calculation
            total_purchase_value = 0
            total_purchase_amount = 0
            total_sales_amount = 0  # Track total sales amount for simple profit calculation
            is_first_transaction = True

            # Get all trades that have THIS specific incentive license in their incentive_lines
            trades_query = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                incentive_lines__incentive_license=license
            )

            # Direction-aware company filter:
            # - PURCHASE/COMMISSION_PURCHASE: company is the BUYER (to_company)
            # - SALE/COMMISSION_SALE: company is the SELLER (from_company)
            if company_id:
                trades_query = trades_query.filter(
                    Q(direction__in=['PURCHASE', 'COMMISSION_PURCHASE'], to_company_id=company_id) |
                    Q(direction__in=['SALE', 'COMMISSION_SALE'], from_company_id=company_id)
                )

            trades = list(trades_query.prefetch_related(
                'incentive_lines__incentive_license',
                'from_company',
                'to_company',
            ).distinct())

            # Sort: purchases always before sales (regardless of date) so that
            # per-sale P/L can be computed against the accumulated purchase cost,
            # even when a sale is recorded before its corresponding purchase
            # in chronological order (mirrors the DFIA branch above).
            trades.sort(key=lambda t: (
                t.direction not in ('PURCHASE', 'COMMISSION_PURCHASE'),
                t.invoice_date or timezone.now().date(),
                t.id,
            ))

            # Process trades
            # The queryset is already filtered to only trades involving the company (from_company or to_company),
            # so no additional per-trade filtering is needed here.
            for trade in trades:
                # Find the specific line for THIS license — use prefetched data to avoid N+1
                license_line = next(
                    (l for l in trade.incentive_lines.all() if l.incentive_license_id == license.id),
                    None,
                )

                if not license_line:
                    continue

                license_value = float(license_line.license_value or 0)
                rate_pct = float(license_line.rate_pct or 0)
                amount = float(license_line.amount_inr or 0)

                if trade.direction in ['PURCHASE', 'COMMISSION_PURCHASE']:
                    running_balance += license_value
                    total_purchase_value += license_value
                    total_purchase_amount += amount

                    is_commission = trade.direction == 'COMMISSION_PURCHASE'
                    txn_type = 'COMMISSION' if is_commission else 'PURCHASE'
                    particular_prefix = 'Commission Paid to' if is_commission else f'Purchase {license.license_type} -'
                    _co = trade.to_company

                    if is_first_transaction and not is_commission:
                        transactions.append({
                            'date': trade.invoice_date or license.license_date,
                            'type': 'OPENING',
                            'particular': f'Opening Balance - Purchase from {trade.from_company.name if trade.from_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': license_value,
                            'credit_license_value': 0,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': amount,
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trade.id,
                        })
                        is_first_transaction = False
                    else:
                        transactions.append({
                            'date': trade.invoice_date or license.license_date,
                            'type': txn_type,
                            'particular': f'{particular_prefix} {trade.from_company.name if trade.from_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': license_value,
                            'credit_license_value': 0,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': amount,
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trade.id,
                        })
                        if is_first_transaction:
                            is_first_transaction = False

                elif trade.direction in ['SALE', 'COMMISSION_SALE']:
                    is_commission = trade.direction == 'COMMISSION_SALE'
                    _co = trade.from_company

                    if is_commission:
                        running_balance += license_value
                        total_purchase_amount += amount

                        transactions.append({
                            'date': trade.invoice_date or timezone.now().date(),
                            'type': 'COMMISSION',
                            'particular': f'Commission Paid to {trade.to_company.name if trade.to_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': license_value,
                            'credit_license_value': 0,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': amount,
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trade.id,
                        })
                    else:
                        running_balance -= license_value
                        total_sales_amount += amount

                        # Per-sale P/L using average purchase cost per license value unit
                        if total_purchase_value > 0:
                            avg_purchase_rate = total_purchase_amount / total_purchase_value
                            purchase_cost_for_sale = license_value * avg_purchase_rate
                            sale_profit_loss = round(amount - purchase_cost_for_sale, 2)
                        else:
                            sale_profit_loss = round(amount, 2)

                        transactions.append({
                            'date': trade.invoice_date or timezone.now().date(),
                            'type': 'SALE',
                            'particular': f'{license.license_type} Sale - {trade.to_company.name if trade.to_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': 0,
                            'credit_license_value': license_value,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': 0,
                            'credit_amount': amount,
                            'balance': round(running_balance, 2),
                            'profit_loss': sale_profit_loss,
                            'company_id': _co.id if _co else None,
                            'company_name': _co.name if _co else 'N/A',
                            'trade_id': trade.id,
                        })
                    is_first_transaction = False

            return Response({
                'license_type': license.license_type,
                'license_number': license.license_number,
                'license_date': license.license_date,
                'expiry_date': license.license_expiry_date,
                'exporter': license.exporter.name if license.exporter else '',
                'port': license.port_code.name if license.port_code else '',
                'total_value': total_purchase_value,
                'available_balance': round(running_balance, 2),  # Use calculated running balance, not DB field
                'db_balance': float(license.balance_value or 0),  # Keep DB balance for reference
                'transactions': transactions,
            })

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
        Search across both DFIA and Incentive licenses by license number or exporter name.
        Returns combined results from both types.

        Query params:
        - q: Search query (searches license_number and exporter name)
        - license_type: Filter by type (DFIA, INCENTIVE, RODTEP, ROSTL, MEIS, or ALL)
        - active_only: Filter only active licenses (default: true)
        - min_balance: Minimum balance filter
        """
        from django.db.models import Q

        query = request.query_params.get('q', '').strip()
        license_type = request.query_params.get('license_type', 'ALL')
        active_only = request.query_params.get('active_only', 'true').lower() == 'true'
        min_balance = request.query_params.get('min_balance')

        if not query:
            return Response({
                'error': 'Search query parameter "q" is required'
            }, status=400)

        results = []

        # Search DFIA licenses if applicable
        if license_type in ['ALL', 'DFIA']:
            dfia_qs = LicenseDetailsModel.objects.select_related('exporter', 'port').filter(
                Q(license_number__icontains=query) |
                Q(exporter__name__icontains=query)
            )

            if active_only:
                dfia_qs = dfia_qs.filter(flags__is_expired=False)

            if min_balance:
                try:
                    min_bal = Decimal(min_balance)
                    dfia_qs = dfia_qs.filter(balance__balance_cif__gte=min_bal)
                except (ValueError, TypeError):
                    pass

            dfia_data = self._prepare_dfia_data(dfia_qs[:50])  # Limit to 50 results
            results.extend(dfia_data)

        # Search Incentive licenses if applicable
        if license_type in ['ALL', 'INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
            incentive_qs = IncentiveLicense.objects.select_related('exporter', 'port_code').filter(
                Q(license_number__icontains=query) |
                Q(exporter__name__icontains=query)
            )

            if active_only:
                incentive_qs = incentive_qs.filter(
                    is_active=True,
                    license_expiry_date__gte=timezone.now().date()
                )

            if license_type not in ['ALL', 'INCENTIVE']:
                incentive_qs = incentive_qs.filter(license_type=license_type)

            if min_balance:
                try:
                    min_bal = Decimal(min_balance)
                    incentive_qs = incentive_qs.filter(balance_value__gte=min_bal)
                except (ValueError, TypeError):
                    pass

            incentive_data = self._prepare_incentive_data(incentive_qs[:50])  # Limit to 50 results
            results.extend(incentive_data)

        # Sort by license date (most recent first)
        from datetime import date
        results.sort(key=lambda x: x.get('license_date') or date.min, reverse=True)

        return Response({
            'count': len(results),
            'query': query,
            'license_type': license_type,
            'results': results
        })

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
        No query params required.
        """
        from apps.trade.models import LicenseTrade
        from django.db.models import Q
        from decimal import Decimal

        search = request.query_params.get('search', '').strip()
        terms = [t.strip() for t in search.split(',') if t.strip()] if search else []

        qs = LicenseTrade.objects.select_related('from_company', 'to_company').prefetch_related(
            'lines__sr_number__license',
            'incentive_lines__incentive_license',
        ).filter(direction__in=['PURCHASE', 'SALE'])

        if terms:
            if len(terms) == 1:
                t = terms[0]
                qs = qs.filter(
                    Q(lines__sr_number__license__license_number__icontains=t) |
                    Q(incentive_lines__incentive_license__license_number__icontains=t)
                ).distinct()
            else:
                qs = qs.filter(
                    Q(lines__sr_number__license__license_number__in=terms) |
                    Q(incentive_lines__incentive_license__license_number__in=terms)
                ).distinct()

        trades = qs

        companies_dict = {}

        for trade in trades:
            company = trade.to_company if trade.direction == 'PURCHASE' else trade.from_company
            if not company:
                continue

            cid = company.id
            if cid not in companies_dict:
                companies_dict[cid] = {
                    'company_id': cid,
                    'company_name': company.name,
                    'purchases': [],
                    'sales': [],
                    'purchase_total': Decimal('0'),
                    'sale_total': Decimal('0'),
                }

            if trade.license_type == 'DFIA':
                lic_pairs = list({
                    (line.sr_number.license.id, line.sr_number.license.license_number)
                    for line in trade.lines.all()
                    if line.sr_number and line.sr_number.license
                })
            else:
                lic_pairs = list({
                    (tl.incentive_license.id, tl.incentive_license.license_number)
                    for tl in trade.incentive_lines.all()
                    if tl.incentive_license
                })

            license_ids = [p[0] for p in lic_pairs]
            license_numbers = [p[1] for p in lic_pairs]

            row = {
                'trade_id': trade.id,
                'license_ids': license_ids,
                'licenses': license_numbers,
                'license_type': trade.license_type,
                'invoice_date': str(trade.invoice_date) if trade.invoice_date else '-',
                'amount': float(trade.total_amount or 0),
            }

            amount = trade.total_amount or Decimal('0')
            if trade.direction == 'PURCHASE':
                companies_dict[cid]['purchases'].append(row)
                companies_dict[cid]['purchase_total'] += amount
            else:
                companies_dict[cid]['sales'].append(row)
                companies_dict[cid]['sale_total'] += amount

        companies = []
        total_purchase = Decimal('0')
        total_sale = Decimal('0')

        for c in sorted(companies_dict.values(), key=lambda x: x['company_name']):
            pt = c['purchase_total']
            st = c['sale_total']
            c['purchase_total'] = float(pt)
            c['sale_total'] = float(st)
            c['profit_loss'] = float(st - pt)
            total_purchase += pt
            total_sale += st
            companies.append(c)

        return Response({
            'companies': companies,
            'summary': {
                'total_companies': len(companies),
                'total_purchase': float(total_purchase),
                'total_sale': float(total_sale),
                'profit_loss': float(total_sale - total_purchase),
            },
        })

    @action(detail=False, methods=['get'], url_path='license-wise')
    def license_wise(self, request):
        """
        Returns trades grouped by license, then by company within each license.
        Structure: license → [company → purchases/sales/totals]
        """
        from apps.trade.models import LicenseTrade
        from django.db.models import Q
        from decimal import Decimal

        search = request.query_params.get('search', '').strip()
        terms = [t.strip() for t in search.split(',') if t.strip()] if search else []
        license_type = request.query_params.get('license_type', 'ALL')
        purchase_date_from = request.query_params.get('purchase_date_from', '')
        purchase_date_to = request.query_params.get('purchase_date_to', '')

        qs = LicenseTrade.objects.select_related('from_company', 'to_company').prefetch_related(
            'lines__sr_number__license',
            'incentive_lines__incentive_license',
        ).filter(direction__in=['PURCHASE', 'SALE'])

        if license_type and license_type != 'ALL':
            if license_type == 'INCENTIVE':
                qs = qs.filter(license_type__in=['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS'])
            else:
                qs = qs.filter(license_type=license_type)
        if purchase_date_from:
            qs = qs.filter(invoice_date__gte=purchase_date_from)
        if purchase_date_to:
            qs = qs.filter(invoice_date__lte=purchase_date_to)

        if terms:
            if len(terms) == 1:
                t = terms[0]
                qs = qs.filter(
                    Q(lines__sr_number__license__license_number__icontains=t) |
                    Q(incentive_lines__incentive_license__license_number__icontains=t)
                ).distinct()
            else:
                qs = qs.filter(
                    Q(lines__sr_number__license__license_number__in=terms) |
                    Q(incentive_lines__incentive_license__license_number__in=terms)
                ).distinct()

        licenses_dict = {}

        for trade in qs:
            company = trade.to_company if trade.direction == 'PURCHASE' else trade.from_company
            if not company:
                continue

            # Compute per-license amount for this trade so a multi-license invoice
            # does not attribute its FULL total to each license it touches.
            license_amounts = {}  # license_id -> Decimal sum of line.amount_inr
            if trade.license_type == 'DFIA':
                lic_entries = list({
                    (line.sr_number.license.id,
                     line.sr_number.license.license_number,
                     str(line.sr_number.license.license_date) if line.sr_number.license.license_date else '-',
                     trade.license_type)
                    for line in trade.lines.all()
                    if line.sr_number and line.sr_number.license
                    and (not terms or any(t.lower() in line.sr_number.license.license_number.lower() for t in terms))
                })
                for line in trade.lines.all():
                    if line.sr_number and line.sr_number.license:
                        _lid = line.sr_number.license.id
                        license_amounts[_lid] = license_amounts.get(_lid, Decimal('0')) + (line.amount_inr or Decimal('0'))
            else:
                lic_entries = list({
                    (tl.incentive_license.id,
                     tl.incentive_license.license_number,
                     str(tl.incentive_license.license_date) if tl.incentive_license.license_date else '-',
                     trade.license_type)
                    for tl in trade.incentive_lines.all()
                    if tl.incentive_license
                    and (not terms or any(t.lower() in tl.incentive_license.license_number.lower() for t in terms))
                })
                for tl in trade.incentive_lines.all():
                    if tl.incentive_license:
                        _lid = tl.incentive_license.id
                        license_amounts[_lid] = license_amounts.get(_lid, Decimal('0')) + (tl.amount_inr or Decimal('0'))

            for lic_id, lic_num, lic_date, lic_type in lic_entries:
                if lic_id not in licenses_dict:
                    licenses_dict[lic_id] = {
                        'license_id': lic_id,
                        'license_number': lic_num,
                        'license_date': lic_date,
                        'license_type': lic_type,
                        'companies': {},
                    }

                cid = company.id
                if cid not in licenses_dict[lic_id]['companies']:
                    licenses_dict[lic_id]['companies'][cid] = {
                        'company_id': cid,
                        'company_name': company.name,
                        'purchases': [],
                        'sales': [],
                        'purchase_total': Decimal('0'),
                        'sale_total': Decimal('0'),
                    }

                amount = license_amounts.get(lic_id, Decimal('0'))
                row = {
                    'trade_id': trade.id,
                    'invoice_date': str(trade.invoice_date) if trade.invoice_date else '-',
                    'amount': float(amount),
                }
                if trade.direction == 'PURCHASE':
                    licenses_dict[lic_id]['companies'][cid]['purchases'].append(row)
                    licenses_dict[lic_id]['companies'][cid]['purchase_total'] += amount
                else:
                    licenses_dict[lic_id]['companies'][cid]['sales'].append(row)
                    licenses_dict[lic_id]['companies'][cid]['sale_total'] += amount

        result = []
        for lic in sorted(licenses_dict.values(), key=lambda x: x['license_number']):
            companies = []
            for c in sorted(lic['companies'].values(), key=lambda x: x['company_name']):
                pt = c['purchase_total']
                st = c['sale_total']
                c['purchase_total'] = float(pt)
                c['sale_total'] = float(st)
                c['profit_loss'] = float(st - pt)
                companies.append(c)
            lic['companies'] = companies
            result.append(lic)

        return Response({'licenses': result})
