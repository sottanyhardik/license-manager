"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
from decimal import Decimal

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from license.models import LicenseDetailsModel, IncentiveLicense


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
            combined.sort(key=lambda x: x.get('license_date', ''), reverse=True)
            return combined

    def _prepare_dfia_data(self, queryset):
        """Prepare DFIA license data for ledger view"""
        from trade.models import LicenseTrade
        from django.db.models import Sum, Q

        data = []
        for license in queryset:
            # Calculate purchase and sale amounts for this specific license
            purchase_amount = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='PURCHASE',
                lines__sr_number__license=license
            ).aggregate(total=Sum('lines__amount_inr'))['total'] or 0

            sale_amount = LicenseTrade.objects.filter(
                license_type='DFIA',
                direction='SALE',
                lines__sr_number__license=license
            ).aggregate(total=Sum('lines__amount_inr'))['total'] or 0

            profit_loss = float(sale_amount) - float(purchase_amount)

            data.append({
                'id': license.id,
                'license_type': 'DFIA',
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port.name if license.port else '',
                'total_value': float(license.opening_balance or 0),
                'balance_value': float(license.balance_cif or 0),
                'sold_value': float(license.opening_balance or 0) - float(license.balance_cif or 0),
                'purchase_amount': float(purchase_amount),
                'sale_amount': float(sale_amount),
                'profit_loss': profit_loss,
                'currency': 'USD',
                'is_expired': license.is_expired,
                'is_active': not license.is_expired,
                'sold_status': self._get_sold_status(
                    license.opening_balance or 0,
                    license.balance_cif or 0
                ),
            })
        return data

    def _prepare_incentive_data(self, queryset):
        """Prepare Incentive license data for ledger view"""
        from trade.models import LicenseTrade
        from django.db.models import Sum, Q

        data = []
        for license in queryset:
            # Calculate purchase and sale amounts for this specific incentive license
            purchase_amount = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='PURCHASE',
                incentive_lines__incentive_license=license
            ).aggregate(total=Sum('incentive_lines__amount_inr'))['total'] or 0

            sale_amount = LicenseTrade.objects.filter(
                license_type='INCENTIVE',
                direction='SALE',
                incentive_lines__incentive_license=license
            ).aggregate(total=Sum('incentive_lines__amount_inr'))['total'] or 0

            profit_loss = float(sale_amount) - float(purchase_amount)

            total_value = float(license.license_value or 0)
            balance_value = float(license.balance_value or 0)
            sold_value = total_value - balance_value

            data.append({
                'id': license.id,
                'license_type': license.license_type,
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port_code.name if license.port_code else '',
                'total_value': total_value,
                'balance_value': balance_value,
                'sold_value': sold_value,
                'purchase_amount': float(purchase_amount),
                'sale_amount': float(sale_amount),
                'profit_loss': profit_loss,
                'currency': 'INR',
                'is_expired': license.license_expiry_date < timezone.now().date() if license.license_expiry_date else False,
                'is_active': license.is_active,
                'sold_status': self._get_sold_status(total_value, balance_value),
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
                if search_lower in item.get('license_number', '').lower()
                   or search_lower in item.get('exporter_name', '').lower()
            ]

        # Apply ordering
        ordering = request.query_params.get('ordering', '-license_date')
        if isinstance(data, list):
            reverse = ordering.startswith('-')
            order_field = ordering.lstrip('-')
            if order_field in ['license_date', 'balance_value', 'license_expiry_date']:
                data.sort(key=lambda x: x.get(order_field, ''), reverse=reverse)

        # Pagination
        page = self.paginate_queryset(data)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get summary statistics for license balances
        """
        from django.utils import timezone

        # DFIA Summary
        dfia_qs = LicenseDetailsModel.objects.filter(is_expired=False)
        dfia_total = sum(float(lic.opening_balance or 0) for lic in dfia_qs)
        dfia_balance = sum(float(lic.balance_cif or 0) for lic in dfia_qs)
        dfia_sold = dfia_total - dfia_balance

        # Incentive Summary
        incentive_qs = IncentiveLicense.objects.filter(
            is_active=True,
            license_expiry_date__gte=timezone.now().date()
        )
        incentive_total = sum(float(lic.license_value or 0) for lic in incentive_qs)
        incentive_balance = sum(float(lic.balance_value or 0) for lic in incentive_qs)
        incentive_sold = sum(float(lic.sold_value or 0) for lic in incentive_qs)

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
        """
        from django.utils import timezone
        from trade.models import LicenseTrade

        license_type = request.query_params.get('license_type', 'DFIA')

        if license_type == 'DFIA':
            try:
                # Try to lookup by ID first (if pk is numeric), otherwise by license_number
                try:
                    license_id = int(pk)
                    license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(pk=license_id)
                except (ValueError, TypeError):
                    # pk is not a number, treat as license_number
                    license = LicenseDetailsModel.objects.select_related('exporter', 'port').get(license_number=pk)
            except LicenseDetailsModel.DoesNotExist:
                return Response({'error': 'License not found'}, status=404)

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
                total_purchase_amount = 0  # No purchase cost for original license

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
                    'debit_amount': 0,
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

                for line in trans_obj.lines.all():
                    # Only include lines that reference THIS specific license
                    if line.sr_number and line.sr_number.license_id != license.id:
                        continue

                    # For DFIA trades, we need CIF in USD
                    # If exc_rate is available and cif_inr is set, calculate: cif_usd = cif_inr / exc_rate
                    # Otherwise use cif_fc directly (which should be in USD for DFIA)
                    if line.exc_rate and line.exc_rate > 0 and line.cif_inr:
                        cif_usd = float(line.cif_inr) / float(line.exc_rate)
                    else:
                        cif_usd = float(line.cif_fc or 0)

                    total_cif_usd += cif_usd
                    total_amount += float(line.amount_inr or 0)

                    if line.sr_number and line.sr_number.items and line.sr_number.items.name:
                        items_desc.append(line.sr_number.items.name)

                # Calculate rate and update balance
                rate = total_amount / total_cif_usd if total_cif_usd > 0 else 0

                if trans_type == 'PURCHASE':
                    running_balance += total_cif_usd
                    total_purchase_cif += total_cif_usd
                    total_purchase_amount += total_amount

                    # First purchase is the opening balance (only if no original opening balance)
                    if idx == 0 and len(transactions) == 0:
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
                            'type': 'PURCHASE',
                            'particular': f'Purchase DFIA - {trans_obj.from_company.name if trans_obj.from_company else "N/A"}',
                            'invoice_number': trans_obj.invoice_number or '',
                            'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                            'qty': sum(float(line.qty_kg or 0) for line in trans_obj.lines.all() if line.sr_number and line.sr_number.license_id == license.id),
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

                else:  # SALE
                    running_balance -= total_cif_usd
                    total_sales_amount += total_amount

                    # Calculate cumulative profit: Total Sales So Far - Total Purchase Amount
                    cumulative_profit = total_sales_amount - total_purchase_amount

                    transactions.append({
                        'date': trans_date,
                        'type': 'SALE',
                        'particular': f'DFIA Sale - {trans_obj.to_company.name if trans_obj.to_company else "N/A"}',
                        'invoice_number': trans_obj.invoice_number or '',
                        'items': ', '.join(set(items_desc))[:100] if items_desc else 'N/A',
                        'qty': sum(float(line.qty_kg or 0) for line in trans_obj.lines.all() if line.sr_number and line.sr_number.license_id == license.id),
                        'cif_usd': total_cif_usd,
                        'debit_cif': 0,
                        'credit_cif': total_cif_usd,  # Sale is credit (asset decreases)
                        'rate': round(rate, 2),
                        'amount': total_amount,
                        'debit_amount': 0,
                        'credit_amount': total_amount,  # Sale amount is credit (revenue)
                        'balance': round(running_balance, 2),
                        'profit_loss': round(cumulative_profit, 2),  # Show cumulative profit
                    })

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
            try:
                # Try to lookup by ID first (if pk is numeric), otherwise by license_number
                try:
                    license_id = int(pk)
                    license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(pk=license_id)
                except (ValueError, TypeError):
                    # pk is not a number, treat as license_number
                    license = IncentiveLicense.objects.select_related('exporter', 'port_code').get(license_number=pk)
            except IncentiveLicense.DoesNotExist:
                return Response({'error': 'License not found'}, status=404)

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

                if trade.direction == 'PURCHASE':
                    running_balance += license_value
                    total_purchase_value += license_value
                    total_purchase_amount += amount

                    # First purchase is the opening balance
                    if is_first_transaction:
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
                            'type': 'PURCHASE',
                            'particular': f'Purchase {license.license_type} - {trade.from_company.name if trade.from_company else "N/A"}',
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

                else:  # SALE
                    running_balance -= license_value
                    total_sales_amount += amount

                    # Calculate cumulative profit: Total Sales So Far - Total Purchase Amount
                    cumulative_profit = total_sales_amount - total_purchase_amount

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
                        'profit_loss': round(cumulative_profit, 2),  # Show cumulative profit
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


# Import timezone at top
from django.utils import timezone
