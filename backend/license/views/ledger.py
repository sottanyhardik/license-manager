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
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
    permission_classes = [IsAuthenticated]
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
        is_active_only = self.request.query_params.get('active_only', 'true').lower() == 'true'
        purchase_date_from = self.request.query_params.get('purchase_date_from')
        purchase_date_to = self.request.query_params.get('purchase_date_to')

        # Get DFIA licenses
        dfia_qs = LicenseDetailsModel.objects.select_related('exporter', 'port').all()

        # Get Incentive licenses
        incentive_qs = IncentiveLicense.objects.select_related('exporter', 'port_code').all()

        # Apply filters
        if is_active_only:
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

        # Filter by purchase date range
        if purchase_date_from or purchase_date_to:
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

        data = []
        for license in queryset:
            # Calculate purchase and sale amounts (INR) for this specific license
            purchase_amount_inr = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='PURCHASE',
                lines__sr_number__license=license
            ).aggregate(total=Sum('lines__amount_inr'))['total'] or 0

            sale_amount_inr = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='SALE',
                lines__sr_number__license=license
            ).aggregate(total=Sum('lines__amount_inr'))['total'] or 0

            # Calculate purchase and sale amounts in USD (cif_fc)
            purchase_amount_usd = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='PURCHASE',
                lines__sr_number__license=license
            ).aggregate(total=Sum('lines__cif_fc'))['total'] or 0

            sale_amount_usd = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='SALE',
                lines__sr_number__license=license
            ).aggregate(total=Sum('lines__cif_fc'))['total'] or 0

            profit_loss = float(sale_amount_inr) - float(purchase_amount_inr)

            # Calculate balance: Purchase USD - Sold USD
            balance_usd = float(purchase_amount_usd) - float(sale_amount_usd)

            data.append({
                'id': license.id,
                'license_type': 'DFIA',
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port.name if license.port else '',
                'total_value': float(purchase_amount_usd),  # Total purchased USD
                'balance_value': balance_usd,                # Balance = Purchase - Sold
                'sold_value': float(sale_amount_usd),       # Total sold USD
                'purchase_amount': float(purchase_amount_inr),
                'sale_amount': float(sale_amount_inr),
                'profit_loss': profit_loss,
                'currency': 'USD',
                'is_expired': license.is_expired,
                'is_active': not license.is_expired,
                'sold_status': self._get_sold_status(
                    purchase_amount_usd or 0,
                    balance_usd or 0
                ),
            })
        return data

    def _prepare_incentive_data(self, queryset):
        """Prepare Incentive license data for ledger view"""
        from trade.models import LicenseTrade
        from django.db.models import Sum, Q

        data = []
        for license in queryset:
            # Calculate purchase and sale amounts (INR) for this specific incentive license
            purchase_amount_inr = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='PURCHASE',
                incentive_lines__incentive_license=license
            ).aggregate(total=Sum('incentive_lines__amount_inr'))['total'] or 0

            sale_amount_inr = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='SALE',
                incentive_lines__incentive_license=license
            ).aggregate(total=Sum('incentive_lines__amount_inr'))['total'] or 0

            # Calculate total purchased value (INR) from trade lines
            purchase_value_inr = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='PURCHASE',
                incentive_lines__incentive_license=license
            ).aggregate(total=Sum('incentive_lines__license_value'))['total'] or 0

            # Calculate total sold value (INR) from trade lines
            sale_value_inr = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='SALE',
                incentive_lines__incentive_license=license
            ).aggregate(total=Sum('incentive_lines__license_value'))['total'] or 0

            profit_loss = float(sale_amount_inr) - float(purchase_amount_inr)

            # Calculate balance: Purchase INR - Sold INR
            balance_inr = float(purchase_value_inr) - float(sale_value_inr)

            data.append({
                'id': license.id,
                'license_type': license.license_type,
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port_code.name if license.port_code else '',
                'total_value': float(purchase_value_inr),  # Total purchased INR
                'balance_value': balance_inr,              # Balance = Purchase - Sold
                'sold_value': float(sale_value_inr),       # Total sold INR
                'purchase_amount': float(purchase_amount_inr),
                'sale_amount': float(sale_amount_inr),
                'profit_loss': profit_loss,
                'currency': 'INR',
                'is_expired': license.license_expiry_date < timezone.now().date() if license.license_expiry_date else False,
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

    def list(self, request, *args, **kwargs):
        """Override list to handle non-queryset data"""
        data = self.get_queryset()

        # Apply search filter manually for combined data
        search = request.query_params.get('search')
        if search and isinstance(data, list):
            search_lower = search.lower()
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
        Get summary statistics for license balances
        """
        from django.utils import timezone

        # DFIA Summary
        dfia_qs = LicenseDetailsModel.objects.filter(is_expired=False)
        dfia_total = sum(_get_safe_balance(lic, 'opening_balance') for lic in dfia_qs)
        dfia_balance = sum(_get_safe_balance(lic, 'balance_cif') for lic in dfia_qs)
        dfia_sold = dfia_total - dfia_balance

        # Incentive Summary
        incentive_qs = IncentiveLicense.objects.filter(
            is_active=True,
            license_expiry_date__gte=timezone.now().date()
        )
        incentive_total = sum(_get_safe_balance(lic, 'license_value') for lic in incentive_qs)
        incentive_balance = sum(_get_safe_balance(lic, 'balance_value') for lic in incentive_qs)
        incentive_sold = sum(_get_safe_balance(lic, 'sold_value') for lic in incentive_qs)

        # Calculate purchase and sale amounts from trades
        from trade.models import LicenseTrade
        from django.db.models import Sum, Q

        # DFIA Trades
        dfia_purchases = LicenseTrade.objects.filter(
            license_type='DFIA',
            direction='PURCHASE'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        dfia_sales = LicenseTrade.objects.filter(
            license_type='DFIA',
            direction='SALE'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        dfia_profit = float(dfia_sales) - float(dfia_purchases)

        # Incentive Trades
        incentive_purchases = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            direction='PURCHASE'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        incentive_sales = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            direction='SALE'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

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
                'breakdown': {
                    license_type: {
                        'count': incentive_qs.filter(license_type=license_type).count(),
                        'balance': round(sum(
                            float(lic.balance_value or 0)
                            for lic in incentive_qs.filter(license_type=license_type)
                        ), 2)
                    }
                    for license_type in ['RODTEP', 'ROSTL', 'MEIS']
                }
            }
        })

    @action(detail=True, methods=['get'])
    def ledger_detail(self, request, pk=None):
        """
        Get detailed ledger view for a specific license showing all transactions.
        Works for both DFIA and Incentive licenses.
        Accepts either ID (integer) or license_number (string) as pk parameter.
        Auto-searches both tables if license_type not specified.
        """
        from django.utils import timezone
        from trade.models import LicenseTrade

        license_type = request.query_params.get('license_type', 'AUTO')

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
            trades = LicenseTrade.objects.filter(
                license_type='DFIA',
                lines__sr_number__license=license
            ).prefetch_related('lines__sr_number').distinct().order_by('invoice_date', 'id')

            transactions = []
            running_balance = 0

            # Track purchase and sales amounts for profit/loss calculation
            total_purchase_cif = 0
            total_purchase_amount = 0
            total_sales_amount = 0  # Track total sales amount for simple profit calculation

            # Get all trades and sort by date
            all_trans = []
            for trade in trades:
                all_trans.append((trade.direction, trade.invoice_date or timezone.now().date(), trade))

            all_trans.sort(key=lambda x: (x[1], x[0] != 'PURCHASE'))  # Purchases first on same date

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
            for idx, (trans_type, trans_date, trans_obj) in enumerate(all_trans):
                # Get all lines for this trade that belong to THIS specific license
                total_cif_usd = 0
                total_amount = 0
                items_desc = []

                sion_norms = []  # Collect SION norms for this transaction
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

                    # Collect item names and SION norms
                    if line.sr_number:
                        # Get all items linked to this sr_number (import item)
                        for item in line.sr_number.items.all():
                            if item.name:
                                items_desc.append(item.name)
                            # Collect SION norm class if available
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

                    # Commission entries are always shown as expenses (debit)
                    is_commission = trans_type == 'COMMISSION_PURCHASE'
                    txn_type = 'COMMISSION' if is_commission else 'PURCHASE'
                    particular_prefix = 'Commission Paid to' if is_commission else 'Purchase DFIA -'

                    # First purchase is the opening balance (only if no original opening balance and not commission)
                    if idx == 0 and len(transactions) == 0 and not is_commission:
                        transactions.append({
                            'date': trans_date,
                            'type': 'OPENING',
                            'particular': f'Opening Balance - Purchase from {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'cif_usd': total_cif_usd,
                            'debit_cif': total_cif_usd,  # Purchase is debit (asset increases)
                            'credit_cif': 0,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': total_amount,  # Purchase amount is debit (cost)
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                        })
                    else:
                        transactions.append({
                            'date': trans_date,
                            'type': txn_type,
                            'particular': f'{particular_prefix} {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                            'qty': sum(float(line.qty_kg or 0) for line in trans_obj.lines.all() if line.sr_number and line.sr_number.license_id == license.id),
                            'cif_usd': total_cif_usd,
                            'debit_cif': total_cif_usd,  # Purchase/Commission is debit
                            'credit_cif': 0,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': total_amount,  # Purchase/Commission amount is debit (expense)
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                        })

                elif trans_type in ['SALE', 'COMMISSION_SALE']:
                    # Commission sale is also an expense (debit) - commission paid on sale
                    is_commission = trans_type == 'COMMISSION_SALE'

                    if is_commission:
                        # Commission sale is an expense (debit)
                        running_balance += total_cif_usd
                        total_purchase_amount += total_amount

                        transactions.append({
                            'date': trans_date,
                            'type': 'COMMISSION',
                            'particular': f'Commission Paid to {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                            'qty': sum(float(line.qty_kg or 0) for line in trans_obj.lines.all() if line.sr_number and line.sr_number.license_id == license.id),
                            'cif_usd': total_cif_usd,
                            'debit_cif': total_cif_usd,  # Commission is debit (expense)
                            'credit_cif': 0,
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': total_amount,  # Commission amount is debit (expense)
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                        })
                    else:
                        # Regular sale
                        running_balance -= total_cif_usd
                        total_sales_amount += total_amount

                        # Store sale transaction (P/L will be calculated after all transactions)
                        transactions.append({
                            'date': trans_date,
                            'type': 'SALE',
                            'particular': f'DFIA Sale - {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'sion_norms': ', '.join(sion_norms) if sion_norms else '',
                            'qty': sum(float(line.qty_kg or 0) for line in trans_obj.lines.all() if line.sr_number and line.sr_number.license_id == license.id),
                            'cif_usd': total_cif_usd,
                            'debit_cif': 0,
                            'credit_cif': total_cif_usd,  # Sale is credit (asset decreases)
                            'rate': round(rate, 2),
                            'amount': total_amount,
                            'debit_amount': 0,
                            'credit_amount': total_amount,  # Sale amount is credit (revenue)
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,  # Will be updated after all transactions
                        })

            # After all transactions are processed, calculate final P/L and update all SALE rows
            final_profit_loss = round(total_sales_amount - total_purchase_amount, 2)
            for txn in transactions:
                if txn['type'] == 'SALE':
                    txn['profit_loss'] = final_profit_loss

            return Response({
                'license_type': 'DFIA',
                'license_number': license.license_number,
                'license_date': license.license_date,
                'expiry_date': license.license_expiry_date,
                'exporter': license.exporter.name if license.exporter else '',
                'port': license.port.name if license.port else '',
                'total_value': total_purchase_cif,
                'available_balance': round(running_balance, 2),  # Use calculated running balance, not DB field
                'db_balance': float(license.balance_cif or 0),  # Keep DB balance for reference
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
            trades = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                incentive_lines__incentive_license=license
            ).prefetch_related('incentive_lines').distinct().order_by('invoice_date', 'id')

            # Process trades
            for trade in trades:
                # Find the specific line for THIS license
                license_line = trade.incentive_lines.filter(incentive_license=license).first()

                if not license_line:
                    continue

                license_value = float(license_line.license_value or 0)
                rate_pct = float(license_line.rate_pct or 0)
                amount = float(license_line.amount_inr or 0)

                if trade.direction in ['PURCHASE', 'COMMISSION_PURCHASE']:
                    running_balance += license_value
                    total_purchase_value += license_value
                    total_purchase_amount += amount

                    # Commission entries are always shown as expenses (debit)
                    is_commission = trade.direction == 'COMMISSION_PURCHASE'
                    txn_type = 'COMMISSION' if is_commission else 'PURCHASE'
                    particular_prefix = 'Commission Paid to' if is_commission else f'Purchase {license.license_type} -'

                    # First purchase is the opening balance (unless it's commission)
                    if is_first_transaction and not is_commission:
                        transactions.append({
                            'date': trade.invoice_date or license.license_date,
                            'type': 'OPENING',
                            'particular': f'Opening Balance - Purchase from {trade.from_company.name if trade.from_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': license_value,  # Purchase is debit
                            'credit_license_value': 0,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': amount,  # Purchase amount is debit
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                        })
                        is_first_transaction = False
                    else:
                        transactions.append({
                            'date': trade.invoice_date or license.license_date,
                            'type': txn_type,
                            'particular': f'{particular_prefix} {trade.from_company.name if trade.from_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': license_value,  # Purchase/Commission is debit
                            'credit_license_value': 0,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': amount,  # Purchase/Commission amount is debit (expense)
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                        })
                        if is_first_transaction:
                            is_first_transaction = False

                elif trade.direction in ['SALE', 'COMMISSION_SALE']:
                    # Commission sale is an income (still debit in license ledger context as it's money out)
                    is_commission = trade.direction == 'COMMISSION_SALE'

                    if is_commission:
                        # Commission sale is also an expense (debit) - commission paid on sale
                        running_balance += license_value
                        total_purchase_amount += amount

                        transactions.append({
                            'date': trade.invoice_date or timezone.now().date(),
                            'type': 'COMMISSION',
                            'particular': f'Commission Paid to {trade.to_company.name if trade.to_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': license_value,  # Commission is debit (expense)
                            'credit_license_value': 0,
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': amount,  # Commission amount is debit (expense)
                            'credit_amount': 0,
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,
                        })
                    else:
                        # Regular sale
                        running_balance -= license_value
                        total_sales_amount += amount

                        # Store sale transaction (P/L will be calculated after all transactions)
                        transactions.append({
                            'date': trade.invoice_date or timezone.now().date(),
                            'type': 'SALE',
                            'particular': f'{license.license_type} Sale - {trade.to_company.name if trade.to_company else "N/A"}',
                            'invoice_number': trade.invoice_number or '',
                            'license_value': license_value,
                            'debit_license_value': 0,
                            'credit_license_value': license_value,  # Sale is credit
                            'rate': round(rate_pct, 3),
                            'amount': amount,
                            'debit_amount': 0,
                            'credit_amount': amount,  # Sale amount is credit
                            'balance': round(running_balance, 2),
                            'profit_loss': 0,  # Will be updated after all transactions
                        })
                    is_first_transaction = False

            # After all transactions are processed, calculate final P/L and update all SALE rows
            final_profit_loss = round(total_sales_amount - total_purchase_amount, 2)
            for txn in transactions:
                if txn['type'] == 'SALE':
                    txn['profit_loss'] = final_profit_loss

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
            search_lower = search.lower()
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

        # Generate PDF
        pdf_content = self._generate_all_licenses_pdf(data, request.query_params)

        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"license_ledger_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

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
