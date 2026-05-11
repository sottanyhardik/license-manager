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

from accounts.permissions import LicenseLedgerViewPermission

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

from license.models import LicenseDetailsModel, IncentiveLicense

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


def format_indian_number(num, decimals=2):
    """
    Format number in Indian numbering system (lakhs and crores).
    Example: 1,00,00,000.00 (1 crore)
    """
    if num is None:
        return "0"

    # Handle negative numbers
    is_negative = num < 0
    num = abs(num)

    # Split into integer and decimal parts
    if decimals > 0:
        format_str = f"{{:,.{decimals}f}}"
        formatted = format_str.format(num)
        parts = formatted.split('.')
        integer_part = parts[0].replace(',', '')
        decimal_part = parts[1] if len(parts) > 1 else '0' * decimals
    else:
        integer_part = str(int(num))
        decimal_part = None

    # Convert to Indian numbering system
    if len(integer_part) <= 3:
        result = integer_part
    else:
        # Last 3 digits
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]

        # Group remaining digits in pairs from right to left
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]

        groups.reverse()
        result = ','.join(groups) + ',' + last_three

    # Add decimal part if needed
    if decimal_part is not None:
        result = f"{result}.{decimal_part}"

    # Add negative sign if needed
    if is_negative:
        result = f"-{result}"

    return result


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
            dfia_qs = dfia_qs.filter(is_expired=False)
            incentive_qs = incentive_qs.filter(is_active=True, license_expiry_date__gte=timezone.now().date())

        if exporter_id:
            dfia_qs = dfia_qs.filter(exporter_id=exporter_id)
            incentive_qs = incentive_qs.filter(exporter_id=exporter_id)

        if min_balance:
            try:
                min_bal = Decimal(min_balance)
                dfia_qs = dfia_qs.filter(balance_cif__gte=min_bal)
                incentive_qs = incentive_qs.filter(balance_value__gte=min_bal)
            except (ValueError, TypeError):
                pass

        # Filter by purchase date range — skipped when a company filter is active
        # (same rationale as active_only: show the full company history, not just one FY)
        if (purchase_date_from or purchase_date_to) and not company_id:
            from trade.models import LicenseTrade
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
            from trade.models import LicenseTrade
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
            from trade.models import LicenseTrade

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
        from trade.models import LicenseTrade
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
        from trade.models import LicenseTrade
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
        from trade.models import LicenseTrade
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
            dfia_qs = LicenseDetailsModel.objects.filter(is_expired=False)
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
                dfia_qs = dfia_qs.filter(balance_cif__gte=min_bal)
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

        # opening_balance is a @cached_property (not a DB column), must sum in Python
        dfia_total = sum(_get_safe_balance(lic, 'opening_balance') for lic in dfia_qs)
        # balance_cif IS a DB column — aggregate at DB level to avoid loading all objects
        dfia_balance = float(dfia_qs.aggregate(balance=Sum('balance_cif'))['balance'] or 0)
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
        from trade.models import LicenseTrade
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

            trades = trades_query.prefetch_related(
                'incentive_lines__incentive_license',
                'from_company',
                'to_company',
            ).distinct().order_by('invoice_date', 'id')

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
                is_expired=False,
                balance_cif__gte=min_balance
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
                dfia_qs = dfia_qs.filter(is_expired=False)

            if min_balance:
                try:
                    min_bal = Decimal(min_balance)
                    dfia_qs = dfia_qs.filter(balance_cif__gte=min_bal)
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
        """
        Fetch detailed transactions for a single license.
        Returns list of transaction dictionaries with all details.

        When company_id is provided, uses direction-aware filtering (same logic as ledger_detail):
        - PURCHASE/COMMISSION_PURCHASE: only show if company is the BUYER (to_company)
        - SALE/COMMISSION_SALE: only show if company is the SELLER (from_company)
        """
        from trade.models import LicenseTrade
        from django.utils import timezone
        from django.db.models import Q

        license_type = lic_data.get('license_type')
        lic_id = lic_data.get('id')

        if not lic_id:
            return []

        try:
            # Get the actual license object
            if license_type == 'DFIA':
                license_obj = LicenseDetailsModel.objects.get(id=lic_id)
            elif license_type in ['INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']:
                license_obj = IncentiveLicense.objects.get(id=lic_id)
            else:
                return []

            # Direction-aware company filter:
            # - PURCHASE: company is the BUYER (to_company)
            # - SALE: company is the SELLER (from_company)
            company_filter = Q()
            if company_id:
                try:
                    company_id_int = int(company_id)
                    company_filter = (
                        Q(direction__in=['PURCHASE', 'COMMISSION_PURCHASE'], to_company_id=company_id_int) |
                        Q(direction__in=['SALE', 'COMMISSION_SALE'], from_company_id=company_id_int)
                    )
                except (ValueError, TypeError):
                    pass

            if license_type == 'DFIA':
                trades = LicenseTrade.objects.filter(
                    company_filter,
                    license_type='DFIA',
                    lines__sr_number__license=license_obj
                ).prefetch_related('lines__sr_number').distinct().order_by('invoice_date', 'id')
            else:
                # For Incentive licenses, use incentive_lines relationship
                trades = LicenseTrade.objects.filter(
                    company_filter,
                    license_type='INCENTIVE',
                    incentive_lines__incentive_license=license_obj
                ).prefetch_related('incentive_lines').distinct().order_by('invoice_date', 'id')

            transactions = []
            running_balance = 0
            total_purchase_cif = 0
            total_purchase_amount = 0
            total_sales_amount = 0

            # Sort: all purchases before sales so P/L is computed correctly
            all_trans = []
            for trade in trades:
                all_trans.append((trade.direction, trade.invoice_date or timezone.now().date(), trade))

            all_trans.sort(key=lambda x: (x[0] not in ['PURCHASE', 'COMMISSION_PURCHASE'], x[1]))

            # Add opening balance if exists
            if len(all_trans) == 0 and license_type == 'DFIA':
                opening_bal = float(license_obj.opening_balance or 0)
                if opening_bal > 0:
                    running_balance = opening_bal
                    total_purchase_cif = opening_bal
                    transactions.append({
                        'date': license_obj.license_date,
                        'type': 'OPENING',
                        'particular': f'Opening Balance - Original DFIA License',
                        'invoice_number': license_obj.license_number,
                        'cif_usd': opening_bal,
                        'debit_cif': opening_bal,
                        'credit_cif': 0,
                        'rate': 0,
                        'amount': 0,
                        'debit_amount': 0,
                        'credit_amount': 0,
                        'balance': round(running_balance, 2),
                        'profit_loss': 0,
                    })

            # Process each transaction
            for idx, (trans_type, trans_date, trans_obj) in enumerate(all_trans):
                total_cif_usd = 0
                total_amount = 0

                # Get lines for this license only
                if license_type == 'DFIA':
                    lines = trans_obj.lines.filter(sr_number__license_id=lic_id)

                    for line in lines:
                        try:
                            if line.exc_rate and line.cif_inr:
                                exc_rate = float(line.exc_rate)
                                if exc_rate > 0:
                                    cif_usd = float(line.cif_inr) / exc_rate
                                else:
                                    cif_usd = float(line.cif_fc or 0)
                            else:
                                cif_usd = float(line.cif_fc or 0)
                        except (ValueError, TypeError, ZeroDivisionError):
                            cif_usd = 0

                        total_cif_usd += cif_usd
                        total_amount += float(line.amount_inr or 0)
                else:
                    # For Incentive licenses, use incentive_lines
                    incentive_line = trans_obj.incentive_lines.filter(incentive_license_id=lic_id).first()

                    if incentive_line:
                        total_cif_usd = float(incentive_line.license_value or 0)
                        total_amount = float(incentive_line.amount_inr or 0)
                    else:
                        # No line for this license in this trade, skip
                        continue

                # Skip if no value
                if total_cif_usd == 0 and total_amount == 0:
                    continue

                # Calculate rate and update balance
                try:
                    rate = total_amount / total_cif_usd if total_cif_usd != 0 else 0
                except (ZeroDivisionError, ValueError):
                    rate = 0

                debit_cif = 0
                credit_cif = 0
                debit_amount = 0
                credit_amount = 0

                if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
                    debit_cif = total_cif_usd
                    debit_amount = total_amount
                    running_balance += total_cif_usd
                    total_purchase_cif += total_cif_usd
                    total_purchase_amount += total_amount
                elif trans_type in ['SALE', 'COMMISSION_SALE']:
                    credit_cif = total_cif_usd
                    credit_amount = total_amount
                    running_balance -= total_cif_usd
                    total_sales_amount += total_amount

                # Calculate profit/loss for sales
                profit_loss = 0
                if trans_type in ['SALE', 'COMMISSION_SALE'] and total_purchase_cif > 0:
                    avg_purchase_rate = total_purchase_amount / total_purchase_cif
                    purchase_amount_for_this_sale = total_cif_usd * avg_purchase_rate
                    sale_amount_inr = total_amount
                    profit_loss = sale_amount_inr - purchase_amount_for_this_sale

                # Get company names
                from_company = trans_obj.from_company.name if trans_obj.from_company else 'Unknown'
                to_company = trans_obj.to_company.name if trans_obj.to_company else 'Unknown'

                if trans_type in ['PURCHASE', 'COMMISSION_PURCHASE']:
                    particular = f"Purchase from {from_company}"
                else:
                    particular = f"Sale to {to_company}"

                transactions.append({
                    'date': trans_date,
                    'type': trans_type.replace('_', ' ').title(),
                    'particular': particular,
                    'invoice_number': trans_obj.invoice_number or '-',
                    'cif_usd': total_cif_usd,
                    'debit_cif': debit_cif,
                    'credit_cif': credit_cif,
                    'rate': rate,
                    'amount': total_amount,
                    'debit_amount': debit_amount,
                    'credit_amount': credit_amount,
                    'balance': round(running_balance, 2),
                    'profit_loss': round(profit_loss, 2),
                })

            return transactions

        except Exception as e:
            logger.error(f"Error fetching transactions for license {lic_id}: {e}")
            return []

    def _generate_detailed_licenses_pdf(self, licenses_data, query_params):
        """
        Generate a detailed PDF showing all transactions for each license with profit/loss.
        Groups by license and shows purchase/sale transactions chronologically.
        """
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=40,
            bottomMargin=40
        )

        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        title = Paragraph("LICENSE LEDGER - DETAILED TRANSACTIONS", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.2 * inch))

        if not licenses_data:
            no_data = Paragraph("<i>No licenses found</i>", styles['Normal'])
            elements.append(no_data)
        else:
            # Process each license
            for idx, lic_data in enumerate(licenses_data):
                if idx > 0:
                    elements.append(PageBreak())  # New page for each license

                # License Header
                lic_header_style = ParagraphStyle(
                    'LicHeaderStyle',
                    parent=styles['Heading2'],
                    fontSize=14,
                    textColor=colors.HexColor('#2c3e50'),
                    spaceAfter=8,
                    fontName='Helvetica-Bold'
                )

                lic_number = lic_data.get('license_number', 'N/A')
                exporter = lic_data.get('exporter_name', 'N/A')
                lic_type = lic_data.get('license_type', 'N/A')

                header_text = f"License: {lic_number} | Exporter: {exporter} | Type: {lic_type}"
                lic_header = Paragraph(header_text, lic_header_style)
                elements.append(lic_header)

                # License Info Table
                # Fetch transactions first (direction-aware company filter applied inside)
                company_id = query_params.get('company')
                transactions = self._get_license_transactions(lic_data, company_id=company_id)

                lic_date = lic_data.get('license_date')
                exp_date = lic_data.get('license_expiry_date')
                lic_date_str = lic_date.strftime('%d-%b-%Y') if lic_date else '-'
                exp_date_str = exp_date.strftime('%d-%b-%Y') if exp_date else '-'

                total_val = lic_data.get('total_value', 0)
                balance_val = lic_data.get('balance_value', 0)
                currency = lic_data.get('currency', 'USD')

                if company_id and transactions:
                    purchase_amt = sum(t.get('debit_amount', 0) for t in transactions)
                    sale_amt = sum(t.get('credit_amount', 0) for t in transactions)
                    profit_loss = sale_amt - purchase_amt
                else:
                    purchase_amt = lic_data.get('purchase_amount', 0)
                    sale_amt = lic_data.get('sale_amount', 0)
                    profit_loss = lic_data.get('profit_loss', 0)

                info_data = [
                    ['License Date:', lic_date_str, 'Expiry Date:', exp_date_str],
                    [f'Total Value ({currency}):', format_indian_number(total_val, 2),
                     f'Balance ({currency}):', format_indian_number(balance_val, 2)],
                    ['Purchase Amt (INR):', format_indian_number(purchase_amt, 2),
                     'Sale Amt (INR):', format_indian_number(sale_amt, 2)],
                ]

                info_table = Table(info_data, colWidths=[1.5*inch, 2.2*inch, 1.5*inch, 2.2*inch])
                info_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                    ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ecf0f1')),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))

                elements.append(info_table)
                elements.append(Spacer(1, 0.15 * inch))

                # Profit/Loss Summary
                pl_color = colors.green if profit_loss >= 0 else colors.red
                pl_text = f"Profit: ₹{format_indian_number(profit_loss, 2)}" if profit_loss >= 0 else f"Loss: ₹{format_indian_number(abs(profit_loss), 2)}"

                pl_style = ParagraphStyle(
                    'PLStyle',
                    parent=styles['Normal'],
                    fontSize=12,
                    textColor=pl_color,
                    fontName='Helvetica-Bold',
                    alignment=TA_RIGHT
                )

                pl_para = Paragraph(pl_text, pl_style)
                elements.append(pl_para)
                elements.append(Spacer(1, 0.15 * inch))

                if transactions:
                    # Transaction table header
                    txn_title_style = ParagraphStyle(
                        'TxnTitleStyle',
                        parent=styles['Heading3'],
                        fontSize=11,
                        textColor=colors.HexColor('#34495e'),
                        spaceAfter=6,
                        fontName='Helvetica-Bold'
                    )
                    txn_title = Paragraph("Transaction Details", txn_title_style)
                    elements.append(txn_title)

                    # Create transaction table with proper wrapping
                    wrap_style = ParagraphStyle(
                        'WrapStyle',
                        parent=styles['Normal'],
                        fontSize=7,
                        leading=9,
                        wordWrap='CJK',
                        splitLongWords=True
                    )

                    txn_data = [[
                        'Date', 'Type', 'Particulars', 'Invoice No.',
                        'Debit CIF', 'Credit CIF', 'Balance',
                        'Debit Amt', 'Credit Amt', 'P/L'
                    ]]

                    for txn in transactions:
                        # Format values
                        date_str = txn['date'].strftime('%d-%b-%y') if txn.get('date') else '-'
                        txn_type = txn.get('type', '-')
                        particular = txn.get('particular', '-')
                        invoice = txn.get('invoice_number', '-')

                        debit_cif = txn.get('debit_cif', 0)
                        credit_cif = txn.get('credit_cif', 0)
                        balance = txn.get('balance', 0)
                        debit_amt = txn.get('debit_amount', 0)
                        credit_amt = txn.get('credit_amount', 0)
                        pl = txn.get('profit_loss', 0)

                        # Color code profit/loss
                        if pl > 0:
                            pl_text = f"+{format_indian_number(pl, 2)}"
                            pl_para = Paragraph(f'<font color="green">{pl_text}</font>', wrap_style)
                        elif pl < 0:
                            pl_text = format_indian_number(pl, 2)
                            pl_para = Paragraph(f'<font color="red">{pl_text}</font>', wrap_style)
                        else:
                            pl_para = '-'

                        # Wrap all text fields in Paragraph for proper text wrapping
                        txn_data.append([
                            Paragraph(date_str, wrap_style),
                            Paragraph(txn_type, wrap_style),
                            Paragraph(particular, wrap_style),
                            Paragraph(invoice, wrap_style),
                            Paragraph(format_indian_number(debit_cif, 2) if debit_cif > 0 else '-', wrap_style),
                            Paragraph(format_indian_number(credit_cif, 2) if credit_cif > 0 else '-', wrap_style),
                            Paragraph(format_indian_number(balance, 2), wrap_style),
                            Paragraph(format_indian_number(debit_amt, 2) if debit_amt > 0 else '-', wrap_style),
                            Paragraph(format_indian_number(credit_amt, 2) if credit_amt > 0 else '-', wrap_style),
                            pl_para
                        ])

                    # Create table with expanded widths (landscape A4: ~10.5 inches available)
                    txn_table = Table(txn_data, colWidths=[
                        0.7*inch,   # Date
                        0.8*inch,   # Type
                        2.2*inch,   # Particulars (expanded)
                        0.9*inch,   # Invoice No.
                        0.85*inch,  # Debit CIF
                        0.85*inch,  # Credit CIF
                        0.85*inch,  # Balance
                        0.95*inch,  # Debit Amt
                        0.95*inch,  # Credit Amt
                        0.85*inch   # P/L
                    ], repeatRows=1)

                    txn_table.setStyle(TableStyle([
                        # Header
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 7),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

                        # Data rows
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('ALIGN', (0, 1), (3, -1), 'LEFT'),  # Date, Type, Particulars, Invoice left-aligned
                        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),  # All amounts right-aligned
                        ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Top align for better text wrapping

                        # Grid
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                    ]))

                    elements.append(txn_table)
                else:
                    no_txn = Paragraph("<i>No transactions found for this license</i>", styles['Normal'])
                    elements.append(no_txn)

                elements.append(Spacer(1, 0.2 * inch))

        # ── Summary page ──────────────────────────────────────────────────────
        if licenses_data:
            elements.append(PageBreak())

            summary_title_style = ParagraphStyle(
                'SummaryTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=14,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("LICENSE PROFIT / LOSS SUMMARY", summary_title_style))
            elements.append(Spacer(1, 0.15 * inch))

            summary_header = [
                'License No.', 'License Date', 'Expiry Date', 'Type', 'Exporter',
                'CIF $ Purchase', 'CIF $ Sold', 'Balance $',
                'Purchase Amt (₹)', 'Sale Amt (₹)', 'P/L (₹)'
            ]

            summary_rows = [summary_header]
            total_purchase = 0
            total_sale = 0
            total_pl = 0
            total_cif_purchase = 0
            total_cif_sold = 0
            total_cif_balance = 0

            company_id_summary = query_params.get('company')

            for lic_data in licenses_data:
                txns = self._get_license_transactions(lic_data, company_id=company_id_summary)
                if company_id_summary and txns:
                    pur = sum(t.get('debit_amount', 0) for t in txns)
                    sal = sum(t.get('credit_amount', 0) for t in txns)
                    pl  = sal - pur
                else:
                    pur = lic_data.get('purchase_amount', 0)
                    sal = lic_data.get('sale_amount', 0)
                    pl  = lic_data.get('profit_loss', 0)

                cif_purchase = lic_data.get('total_value', 0) or 0
                cif_sold = lic_data.get('sold_value', 0) or 0
                cif_balance = lic_data.get('balance_value', 0) or 0
                currency = lic_data.get('currency', 'USD')

                total_purchase += pur
                total_sale     += sal
                total_pl       += pl
                total_cif_purchase += cif_purchase
                total_cif_sold     += cif_sold
                total_cif_balance  += cif_balance

                pl_color = 'green' if pl >= 0 else 'red'
                pl_sign  = '+' if pl >= 0 else ''
                pl_cell  = Paragraph(
                    f'<font color="{pl_color}">{pl_sign}{format_indian_number(pl, 2)}</font>',
                    ParagraphStyle('plcell', fontSize=7, fontName='Helvetica', alignment=1)
                )

                lic_date = lic_data.get('license_date')
                exp_date = lic_data.get('license_expiry_date')
                lic_date_str = lic_date.strftime('%d-%b-%Y') if lic_date else '-'
                exp_date_str = exp_date.strftime('%d-%b-%Y') if exp_date else '-'

                summary_rows.append([
                    lic_data.get('license_number', '-'),
                    lic_date_str,
                    exp_date_str,
                    lic_data.get('license_type', '-'),
                    lic_data.get('exporter_name', '-'),
                    f"{currency} {format_indian_number(cif_purchase, 2)}",
                    f"{currency} {format_indian_number(cif_sold, 2)}",
                    f"{currency} {format_indian_number(cif_balance, 2)}",
                    format_indian_number(pur, 2),
                    format_indian_number(sal, 2),
                    pl_cell,
                ])

            # Totals row
            total_pl_color = 'green' if total_pl >= 0 else 'red'
            total_pl_sign  = '+' if total_pl >= 0 else ''
            total_pl_cell  = Paragraph(
                f'<font color="{total_pl_color}"><b>{total_pl_sign}{format_indian_number(total_pl, 2)}</b></font>',
                ParagraphStyle('tplcell', fontSize=7, fontName='Helvetica-Bold', alignment=1)
            )
            summary_rows.append([
                Paragraph('<b>TOTAL</b>', ParagraphStyle('tot', fontSize=7, fontName='Helvetica-Bold')),
                '', '', '', '',
                Paragraph(f'<b>{format_indian_number(total_cif_purchase, 2)}</b>', ParagraphStyle('tcp', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
                Paragraph(f'<b>{format_indian_number(total_cif_sold, 2)}</b>',     ParagraphStyle('tcs', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
                Paragraph(f'<b>{format_indian_number(total_cif_balance, 2)}</b>',  ParagraphStyle('tcb', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
                Paragraph(f'<b>{format_indian_number(total_purchase, 2)}</b>', ParagraphStyle('tp', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
                Paragraph(f'<b>{format_indian_number(total_sale, 2)}</b>',     ParagraphStyle('ts', fontSize=7, fontName='Helvetica-Bold', alignment=2)),
                total_pl_cell,
            ])

            summary_table = Table(summary_rows, colWidths=[
                1.3*inch, 0.85*inch, 0.85*inch, 0.6*inch, 1.6*inch,
                1.0*inch, 1.0*inch, 1.0*inch,
                1.1*inch, 1.1*inch, 1.0*inch
            ], repeatRows=1)

            summary_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, 0), 7),
                ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN',     (0, 0), (-1, 0), 'MIDDLE'),
                # Data
                ('FONTNAME',   (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE',   (0, 1), (-1, -1), 7),
                ('ALIGN',      (5, 1), (-1, -1), 'RIGHT'),
                ('ALIGN',      (0, 1), (4, -1), 'LEFT'),
                ('VALIGN',     (0, 1), (-1, -1), 'MIDDLE'),
                # Highlight CIF $ columns
                ('BACKGROUND', (5, 1), (5, -2), colors.HexColor('#fdebd0')),
                ('BACKGROUND', (6, 1), (6, -2), colors.HexColor('#d5f4e6')),
                ('BACKGROUND', (7, 1), (7, -2), colors.HexColor('#e8f5e9')),
                ('FONTNAME',   (7, 1), (7, -2), 'Helvetica-Bold'),
                # Totals row
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
                # Grid
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING',    (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING',   (0, 0), (-1, -1), 4),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ]))

            elements.append(summary_table)

        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()
        return pdf_content

    def _generate_all_licenses_pdf(self, licenses_data, query_params):
        """
        Generate a PDF containing all licenses in a tabular format.
        """
        buffer = None
        try:
            buffer = BytesIO()

            # Create PDF with landscape orientation for better table fit
            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(A4),
                rightMargin=30,
                leftMargin=30,
                topMargin=40,
                bottomMargin=40
            )

            elements = []
            styles = getSampleStyleSheet()

            # Title style
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )

            # Subtitle style
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#555555'),
                spaceAfter=6,
                alignment=TA_CENTER,
                fontName='Helvetica'
            )

            # Title
            title = Paragraph("LICENSE LEDGER - ALL LICENSES", title_style)
            elements.append(title)

            # Add filter information
            license_type = query_params.get('license_type', 'ALL')
            active_only = query_params.get('active_only', 'true').lower() == 'true'

            filter_info = f"License Type: {license_type} | Status: {'Active Only' if active_only else 'All'} | Total: {len(licenses_data)} licenses"
            subtitle = Paragraph(filter_info, subtitle_style)
            elements.append(subtitle)
            elements.append(Spacer(1, 0.2 * inch))

            if not licenses_data:
                no_data = Paragraph("<i>No licenses found matching the criteria</i>", styles['Normal'])
                elements.append(no_data)
            else:
                # Wrap style for text cells - enable multi-line wrapping
                wrap_style = ParagraphStyle(
                    'WrapStyle',
                    parent=styles['Normal'],
                    fontSize=7,
                    leading=9,
                    wordWrap='CJK',  # Enable word wrapping
                    splitLongWords=True
                )

                # Green style for profit values
                profit_style = ParagraphStyle(
                    'ProfitStyle',
                    parent=wrap_style,
                    textColor=colors.green
                )

                # Red style for loss values
                loss_style = ParagraphStyle(
                    'LossStyle',
                    parent=wrap_style,
                    textColor=colors.red
                )

                # Separate licenses into profit and loss groups
                profit_licenses = [lic for lic in licenses_data if lic.get('profit_loss', 0) >= 0]
                loss_licenses = [lic for lic in licenses_data if lic.get('profit_loss', 0) < 0]

                # Helper function to process table for a set of licenses
                def create_license_table(licenses_list, table_title):
                    if not licenses_list:
                        return None, {}

                    # Table header
                    header = [[
                        'License No.',
                        'Type',
                        'Exporter',
                        'License Date',
                        'Expiry',
                        'Purchase\n($)',
                        'Sold\n($)',
                        'Balance\n($)',
                        'Purchase\nAmt (INR)',
                        'Sale\nAmt (INR)',
                        'P/L\n(INR)',
                        'Status'
                    ]]

                    table_data = header[:]
                    no_purchase_rows = []
                    negative_balance_rows = []

                    for idx, license in enumerate(licenses_list):
                        row_num = idx + 1  # +1 for header

                        # Extract data
                        lic_date = license.get('license_date')
                        exp_date = license.get('license_expiry_date')
                        lic_date_str = lic_date.strftime('%d-%b-%y') if lic_date else '-'
                        exp_date_str = exp_date.strftime('%d-%b-%y') if exp_date else '-'

                        total_val = license.get('total_value', 0)
                        balance_val = license.get('balance_value', 0)
                        sold_val = license.get('sold_value', 0)
                        purchase_amt = license.get('purchase_amount', 0)
                        sale_amt = license.get('sale_amount', 0)
                        profit_loss = license.get('profit_loss', 0)
                        currency = license.get('currency', 'USD')
                        status = 'Active' if license.get('is_active', False) else 'Expired'

                        # Wrap exporter name - always use Paragraph for multi-line support
                        exporter_name = license.get('exporter_name') or 'N/A'
                        exporter_para = Paragraph(str(exporter_name), wrap_style)

                        # Calculate balance
                        purchase_usd = total_val
                        sold_usd = sold_val
                        calculated_balance = purchase_usd - sold_usd

                        # Format with Indian number system
                        if currency == 'USD':
                            purchase_str = f"${format_indian_number(purchase_usd, 2)}"
                            sold_str = f"${format_indian_number(sold_usd, 2)}"
                            balance_str = f"${format_indian_number(calculated_balance, 2)}"
                        else:
                            purchase_str = f"INR {format_indian_number(purchase_usd, 2)}"
                            sold_str = f"INR {format_indian_number(sold_usd, 2)}"
                            balance_str = f"INR {format_indian_number(calculated_balance, 2)}"

                        # Track special rows
                        if not purchase_amt or purchase_amt == 0:
                            no_purchase_rows.append(row_num)
                        if calculated_balance < 0:
                            negative_balance_rows.append(row_num)

                        # Wrap all monetary values in Paragraph for text wrapping
                        purchase_amt_str = f"INR {format_indian_number(purchase_amt, 2)}" if purchase_amt else 'No Purchase'
                        sale_amt_str = f"INR {format_indian_number(sale_amt, 2)}" if sale_amt else '-'
                        pl_str = f"INR {format_indian_number(profit_loss, 2)}"

                        # Use green for profit, red for loss
                        pl_paragraph_style = profit_style if profit_loss >= 0 else loss_style

                        # Ensure all values are strings before creating Paragraphs
                        license_number = str(license.get('license_number') or 'N/A')[:14]
                        license_type = str(license.get('license_type') or 'N/A')[:6]

                        table_data.append([
                            Paragraph(license_number, wrap_style),
                            Paragraph(license_type, wrap_style),
                            exporter_para,
                            Paragraph(str(lic_date_str), wrap_style),
                            Paragraph(str(exp_date_str), wrap_style),
                            Paragraph(str(purchase_str), wrap_style),
                            Paragraph(str(sold_str), wrap_style),
                            Paragraph(str(balance_str), wrap_style),
                            Paragraph(str(purchase_amt_str), wrap_style),
                            Paragraph(str(sale_amt_str), wrap_style),
                            Paragraph(str(pl_str), pl_paragraph_style),
                            Paragraph(str(status[:3]), wrap_style)
                        ])

                    # Calculate totals for this group
                    total_purchase_usd = sum(lic.get('total_value', 0) for lic in licenses_list if lic.get('currency') == 'USD')
                    total_sold_usd = sum(lic.get('sold_value', 0) for lic in licenses_list if lic.get('currency') == 'USD')
                    total_balance_usd = sum(lic.get('balance_value', 0) for lic in licenses_list if lic.get('currency') == 'USD')

                    total_purchase_inr_val = sum(lic.get('total_value', 0) for lic in licenses_list if lic.get('currency') == 'INR')
                    total_sold_inr_val = sum(lic.get('sold_value', 0) for lic in licenses_list if lic.get('currency') == 'INR')
                    total_balance_inr_val = sum(lic.get('balance_value', 0) for lic in licenses_list if lic.get('currency') == 'INR')

                    total_purchase_amt = sum(lic.get('purchase_amount', 0) for lic in licenses_list)
                    total_sale_amt = sum(lic.get('sale_amount', 0) for lic in licenses_list)
                    total_pl = sum(lic.get('profit_loss', 0) for lic in licenses_list)

                    # Create bold style for total row
                    total_style = ParagraphStyle(
                        'TotalStyle',
                        parent=wrap_style,
                        fontSize=7.5,
                        leading=9.5,
                        fontName='Helvetica-Bold',
                        wordWrap='CJK',
                        splitLongWords=True
                    )

                    # Create bold profit/loss styles for total row
                    total_profit_style = ParagraphStyle(
                        'TotalProfitStyle',
                        parent=total_style,
                        textColor=colors.green
                    )

                    total_loss_style = ParagraphStyle(
                        'TotalLossStyle',
                        parent=total_style,
                        textColor=colors.red
                    )

                    # Format total values with Paragraph for multi-line support
                    purchase_total_str = f"${format_indian_number(total_purchase_usd, 2)}" if total_purchase_usd else (f"INR {format_indian_number(total_purchase_inr_val, 2)}" if total_purchase_inr_val else '-')
                    sold_total_str = f"${format_indian_number(total_sold_usd, 2)}" if total_sold_usd else (f"INR {format_indian_number(total_sold_inr_val, 2)}" if total_sold_inr_val else '-')
                    balance_total_str = f"${format_indian_number(total_balance_usd, 2)}" if total_balance_usd else (f"INR {format_indian_number(total_balance_inr_val, 2)}" if total_balance_inr_val else '-')

                    # Use green/red for total P/L
                    total_pl_style = total_profit_style if total_pl >= 0 else total_loss_style

                    # Add total row with Paragraphs
                    table_data.append([
                        Paragraph('<b>TOTAL</b>', total_style),
                        '',
                        '',
                        '',
                        '',
                        Paragraph(f'<b>{purchase_total_str}</b>', total_style),
                        Paragraph(f'<b>{sold_total_str}</b>', total_style),
                        Paragraph(f'<b>{balance_total_str}</b>', total_style),
                        Paragraph(f'<b>INR {format_indian_number(total_purchase_amt, 2)}</b>', total_style),
                        Paragraph(f'<b>INR {format_indian_number(total_sale_amt, 2)}</b>', total_style),
                        Paragraph(f'<b>INR {format_indian_number(total_pl, 2)}</b>', total_pl_style),
                        ''
                    ])

                    return table_data, {'no_purchase': no_purchase_rows, 'negative_balance': negative_balance_rows, 'licenses': licenses_list, 'has_total_row': True}

                # Helper function to style and append a table
                def style_and_append_table(table_data, metadata, table_title, title_color):
                    if not table_data:
                        return

                    # Add section title
                    section_title_style = ParagraphStyle(
                        'SectionTitle',
                        parent=styles['Heading2'],
                        fontSize=14,
                        textColor=colors.HexColor(title_color),
                        spaceAfter=10,
                        fontName='Helvetica-Bold'
                    )
                    section_title = Paragraph(table_title, section_title_style)
                    elements.append(section_title)

                    # Create table with appropriate column widths for landscape A4
                    # Landscape A4 width: ~11 inches minus margins = ~10.5 inches available
                    col_widths = [
                        0.9*inch,   # License No.
                        0.55*inch,  # Type
                        1.4*inch,   # Exporter (wider for multi-line)
                        0.7*inch,   # License Date
                        0.7*inch,   # Expiry
                        0.9*inch,   # Purchase ($)
                        0.9*inch,   # Sold ($)
                        0.9*inch,   # Balance ($)
                        0.85*inch,  # Purchase Amt (INR)
                        0.85*inch,  # Sale Amt (INR)
                        0.75*inch,  # P/L (INR)
                        0.5*inch    # Status
                    ]
                    table = Table(table_data, colWidths=col_widths, repeatRows=1)

                    # Style the table
                    no_purchase_rows = metadata.get('no_purchase', [])
                    negative_balance_rows = metadata.get('negative_balance', [])
                    licenses_list = metadata.get('licenses', [])

                    table_style = [
                        # Header row
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

                        # Data rows
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('ALIGN', (0, 1), (2, -1), 'LEFT'),
                        ('ALIGN', (3, 1), (4, -1), 'CENTER'),
                        ('ALIGN', (5, 1), (-1, -1), 'RIGHT'),

                        # Grid and borders
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Align to top for multi-line
                        ('TOPPADDING', (0, 0), (-1, -1), 5),   # Increased padding
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ]

                    # Check if table has total row
                    has_total_row = metadata.get('has_total_row', False)
                    total_row_idx = len(table_data) - 1 if has_total_row else -1

                    # Alternate row colors and highlights
                    for i in range(1, len(table_data)):
                        # Style total row differently
                        if has_total_row and i == total_row_idx:
                            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#e8eaf6')))
                            table_style.append(('LINEABOVE', (0, i), (-1, i), 2, colors.HexColor('#34495e')))
                            table_style.append(('VALIGN', (0, i), (-1, i), 'TOP'))  # Top align for wrapped totals
                            # Note: Font styling handled by Paragraph objects
                            continue

                        if i % 2 == 0:
                            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f9fa')))

                        if i in negative_balance_rows:
                            table_style.append(('BACKGROUND', (7, i), (7, i), colors.HexColor('#d32f2f')))
                            table_style.append(('TEXTCOLOR', (7, i), (7, i), colors.whitesmoke))
                            table_style.append(('FONTNAME', (7, i), (7, i), 'Helvetica-Bold'))

                        if i in no_purchase_rows:
                            table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#ffebee')))
                            table_style.append(('TEXTCOLOR', (8, i), (8, i), colors.HexColor('#c62828')))
                            table_style.append(('FONTNAME', (8, i), (8, i), 'Helvetica-Bold'))

                        if i - 1 < len(licenses_list):
                            license = licenses_list[i - 1]
                            if not license.get('is_active', False) and i not in no_purchase_rows:
                                table_style.append(('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#999999')))

                            profit_loss = license.get('profit_loss', 0)
                            if profit_loss > 0:
                                table_style.append(('TEXTCOLOR', (10, i), (10, i), colors.HexColor('#2e7d32')))
                            elif profit_loss < 0:
                                table_style.append(('TEXTCOLOR', (10, i), (10, i), colors.HexColor('#d32f2f')))

                    table.setStyle(TableStyle(table_style))
                    elements.append(table)
                    elements.append(Spacer(1, 0.3 * inch))

                # Create PROFIT licenses table
                if profit_licenses:
                    profit_table_data, profit_metadata = create_license_table(profit_licenses, "PROFIT LICENSES")
                    style_and_append_table(profit_table_data, profit_metadata, f"PROFIT LICENSES ({len(profit_licenses)} licenses)", '#2e7d32')

                # Create LOSS licenses table
                if loss_licenses:
                    loss_table_data, loss_metadata = create_license_table(loss_licenses, "LOSS LICENSES")
                    style_and_append_table(loss_table_data, loss_metadata, f"LOSS LICENSES ({len(loss_licenses)} licenses)", '#d32f2f')

                # Add summary section
                elements.append(Spacer(1, 0.3 * inch))

                # Calculate totals
                total_balance_dfia = sum(lic.get('balance_value', 0) for lic in licenses_data if lic.get('currency') == 'USD')
                total_balance_inr = sum(lic.get('balance_value', 0) for lic in licenses_data if lic.get('currency') == 'INR')
                total_purchase = sum(lic.get('purchase_amount', 0) for lic in licenses_data)
                total_sale = sum(lic.get('sale_amount', 0) for lic in licenses_data)
                total_profit_loss = sum(lic.get('profit_loss', 0) for lic in licenses_data)

                # Summary title
                summary_title_style = ParagraphStyle(
                    'SummaryTitle',
                    parent=styles['Heading2'],
                    fontSize=12,
                    textColor=colors.HexColor('#2c3e50'),
                    spaceAfter=8,
                    fontName='Helvetica-Bold'
                )
                summary_title = Paragraph("SUMMARY", summary_title_style)
                elements.append(summary_title)

                # Summary data with Indian number format
                summary_data = [
                    ['Total Licenses', 'Profit Licenses', 'Loss Licenses', 'Balance (USD)', 'Balance (INR)', 'Purchase (INR)', 'Sale (INR)', 'Net P/L (INR)'],
                    [
                        str(len(licenses_data)),
                        str(len(profit_licenses)),
                        str(len(loss_licenses)),
                        f"${format_indian_number(total_balance_dfia, 2)}" if total_balance_dfia else '-',
                        f"INR {format_indian_number(total_balance_inr, 2)}" if total_balance_inr else '-',
                        f"INR {format_indian_number(total_purchase, 2)}",
                        f"INR {format_indian_number(total_sale, 2)}",
                        f"INR {format_indian_number(total_profit_loss, 2)}"
                    ]
                ]

                summary_table = Table(summary_data, colWidths=[1*inch, 1*inch, 1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch])
                summary_table_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ecf0f1')),
                    ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 1), (-1, 1), 9),
                    ('ALIGN', (0, 1), (0, 1), 'CENTER'),
                    ('ALIGN', (1, 1), (-1, 1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]

                # Color code profit/loss in summary
                if total_profit_loss > 0:
                    summary_table_style.append(('TEXTCOLOR', (5, 1), (5, 1), colors.HexColor('#2e7d32')))
                elif total_profit_loss < 0:
                    summary_table_style.append(('TEXTCOLOR', (5, 1), (5, 1), colors.HexColor('#d32f2f')))

                summary_table.setStyle(TableStyle(summary_table_style))
                elements.append(summary_table)

            # Footer
            elements.append(Spacer(1, 0.3 * inch))
            footer_text = Paragraph(
                f"<i>Generated on: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}</i>",
                ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
            )
            elements.append(footer_text)

            # Build PDF
            doc.build(elements)

            pdf = buffer.getvalue()
            return pdf

        except Exception as e:
            logger.exception(f"Failed to generate licenses PDF: {e}")
            raise
        finally:
            if buffer:
                try:
                    buffer.close()
                except Exception:
                    pass

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
        from trade.models import LicenseTrade
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
        from core.models import CompanyModel
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
        """Generate PDF for company-specific ledger."""
        buffer = None
        try:
            buffer = BytesIO()

            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(A4),
                rightMargin=30,
                leftMargin=30,
                topMargin=40,
                bottomMargin=40
            )

            elements = []
            styles = getSampleStyleSheet()

            # Title style
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )

            # Subtitle style
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#555555'),
                spaceAfter=6,
                alignment=TA_CENTER,
                fontName='Helvetica'
            )

            # Title
            title = Paragraph(f"COMPANY LEDGER - {company_name.upper()}", title_style)
            elements.append(title)

            # Filter info
            license_type = query_params.get('license_type', 'ALL')
            active_only = query_params.get('active_only', 'true').lower() == 'true'

            filter_info = f"License Type: {license_type} | Status: {'Active Only' if active_only else 'All'} | Total: {len(licenses_data)} licenses"
            subtitle = Paragraph(filter_info, subtitle_style)
            elements.append(subtitle)
            elements.append(Spacer(1, 0.3 * inch))

            # Table data
            table_data = [[
                'License No.',
                'Type',
                'Exporter',
                'Date',
                'Expiry',
                'Total Value',
                'Balance'
            ]]

            for lic in licenses_data:
                currency = 'USD' if lic.get('license_type') == 'DFIA' else 'INR'
                table_data.append([
                    lic.get('license_number', '-'),
                    lic.get('license_type', '-'),
                    (lic.get('exporter_name', '-') or '-')[:25],
                    lic.get('license_date', '-') if lic.get('license_date') else '-',
                    lic.get('expiry_date', '-') if lic.get('expiry_date') else '-',
                    f"{currency} {format_indian_number(lic.get('total_value', 0))}",
                    f"{currency} {format_indian_number(lic.get('available_balance', 0))}"
                ])

            # Create table
            table = Table(table_data, colWidths=[90, 50, 150, 70, 70, 100, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
            ]))

            elements.append(table)

            # Build PDF
            doc.build(elements)

            pdf = buffer.getvalue()
            return pdf

        except Exception as e:
            logger.exception(f"Failed to generate company ledger PDF: {e}")
            raise
        finally:
            if buffer:
                try:
                    buffer.close()
                except Exception:
                    pass

    @action(detail=False, methods=['get'], url_path='company-wise')
    def company_wise(self, request):
        """
        Returns all trades grouped by company with purchases, sales, and a grand summary.
        No query params required.
        """
        from trade.models import LicenseTrade
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
        from trade.models import LicenseTrade
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

            amount = trade.total_amount or Decimal('0')
            row = {
                'trade_id': trade.id,
                'invoice_date': str(trade.invoice_date) if trade.invoice_date else '-',
                'amount': float(amount),
            }

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
