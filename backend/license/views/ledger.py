"""
License Ledger Views - Unified view for DFIA and Incentive license balances
"""
from decimal import Decimal
from django.db.models import Q, F, Value, CharField, DecimalField
from django.db.models.functions import Coalesce
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.mixins import NestedViewSetMixin
from license.models import LicenseDetailsModel, IncentiveLicense
from license.serializers import LicenseDetailsSerializer, IncentiveLicenseSerializer


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
        data = []
        for license in queryset:
            data.append({
                'id': license.id,
                'license_type': 'DFIA',
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port.port_name if license.port else '',
                'total_value': float(license.total_cif or 0),
                'balance_value': float(license.balance_cif or 0),
                'sold_value': float((license.total_cif or 0) - (license.balance_cif or 0)),
                'currency': 'USD',
                'is_expired': license.is_expired,
                'is_active': not license.is_expired,
                'sold_status': self._get_sold_status(
                    license.total_cif or 0,
                    license.balance_cif or 0
                ),
            })
        return data

    def _prepare_incentive_data(self, queryset):
        """Prepare Incentive license data for ledger view"""
        data = []
        for license in queryset:
            data.append({
                'id': license.id,
                'license_type': license.license_type,
                'license_number': license.license_number,
                'license_date': license.license_date,
                'license_expiry_date': license.license_expiry_date,
                'exporter_name': license.exporter.name if license.exporter else '',
                'exporter_id': license.exporter.id if license.exporter else None,
                'port_name': license.port_code.port_name if license.port_code else '',
                'total_value': float(license.license_value or 0),
                'balance_value': float(license.balance_value or 0),
                'sold_value': float(license.sold_value or 0),
                'currency': 'INR',
                'is_expired': license.license_expiry_date < timezone.now().date() if license.license_expiry_date else False,
                'is_active': license.is_active,
                'sold_status': license.sold_status,
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
        dfia_total = sum(float(lic.total_cif or 0) for lic in dfia_qs)
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

        return Response({
            'dfia': {
                'total_licenses': dfia_qs.count(),
                'total_value_usd': round(dfia_total, 2),
                'sold_value_usd': round(dfia_sold, 2),
                'balance_value_usd': round(dfia_balance, 2),
            },
            'incentive': {
                'total_licenses': incentive_qs.count(),
                'total_value_inr': round(incentive_total, 2),
                'sold_value_inr': round(incentive_sold, 2),
                'balance_value_inr': round(incentive_balance, 2),
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
