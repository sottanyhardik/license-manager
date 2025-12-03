"""
Dashboard API View
Provides unified endpoint for all dashboard data in a single API call
"""
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from allotment.models import AllotmentModel
from bill_of_entry.models import BillOfEntryModel
from license.models import LicenseDetailsModel


class DashboardDataView(APIView):
    """
    Unified dashboard endpoint that returns all dashboard data in one API call.

    Returns:
        - License statistics (total, active, expired, null, expiring soon)
        - Allotment statistics (total, recent)
        - BOE statistics (total, pending invoices, recent)
        - Expiring licenses (top 5)
        - BOE monthly trend (last 6 months)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """Get all dashboard data"""
        try:
            # Prepare response data structure
            data = {
                'license_stats': self._get_license_stats(),
                'allotment_stats': self._get_allotment_stats(),
                'boe_stats': self._get_boe_stats(),
                'expiring_licenses': self._get_expiring_licenses(),
                'boe_monthly_trend': self._get_boe_monthly_trend(),
            }

            return Response(data)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=500)

    def _get_license_stats(self):
        """Get license statistics"""
        # Active licenses: not expired and not null (balance >= 500)
        active_count = LicenseDetailsModel.objects.filter(
            is_expired=False,
            is_null=False
        ).count()

        # Expired licenses: expired and not null
        expired_count = LicenseDetailsModel.objects.filter(
            is_expired=True,
            is_null=False
        ).count()

        # Null DFIA: balance < 500
        null_count = LicenseDetailsModel.objects.filter(
            is_null=True
        ).count()

        # Total licenses
        total_count = active_count + expired_count + null_count

        # Expiring soon: licenses expiring in next 30 days
        today = date.today()
        expiry_date = today + timedelta(days=30)
        expiring_count = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte=today,
            license_expiry_date__lte=expiry_date,
            is_active=True,
            balance_cif__gte=Decimal('100.00')  # Only count licenses with balance >= $100
        ).count()

        return {
            'total': total_count,
            'active': active_count,
            'expired': expired_count,
            'null_dfia': null_count,
            'expiring_soon': expiring_count,
        }

    def _get_allotment_stats(self):
        """Get allotment statistics"""
        # Total allotments without BOE
        total_count = AllotmentModel.objects.filter(Q(bill_of_entry__isnull=True)).count()

        # Recent 5 allotments ordered by modified_on
        recent_allotments = AllotmentModel.objects.filter(
            Q(is_boe=False) | Q(bill_of_entry__isnull=True)
        ).order_by('-modified_on')[:5]

        recent_data = []
        for allotment in recent_allotments:
            recent_data.append({
                'id': allotment.id,
                'modified_on': allotment.modified_on,
                'item_name': allotment.item_name,
                'required_quantity': str(allotment.required_quantity),
                'cif_fc': str(allotment.cif_fc),
            })

        return {
            'total': total_count,
            'recent': recent_data,
        }

    def _get_boe_stats(self):
        """Get BOE statistics"""
        # Total BOE (all records - both with and without invoices)
        total_count = BillOfEntryModel.objects.count()

        # Pending invoices: where invoice_no is null or blank
        pending_invoices_count = BillOfEntryModel.objects.filter(
            Q(invoice_no__isnull=True) | Q(invoice_no='')
        ).count()

        # Recent 5 BOE ordered by bill_of_entry_date (all BOE records)
        recent_boe = BillOfEntryModel.objects.filter(
            bill_of_entry_date__isnull=False
        ).order_by('-bill_of_entry_date')[:5]

        recent_data = []
        for boe in recent_boe:
            recent_data.append({
                'id': boe.id,
                'bill_of_entry_number': boe.bill_of_entry_number,
                'bill_of_entry_date': boe.bill_of_entry_date,
                'company_name': boe.company.name if boe.company else None,
            })

        return {
            'total': total_count,
            'pending_invoices': pending_invoices_count,
            'recent': recent_data,
        }

    def _get_expiring_licenses(self):
        """Get top 5 expiring licenses in next 30 days"""
        today = date.today()
        expiry_date = today + timedelta(days=30)

        # Get licenses expiring in next 30 days with balance >= $100
        licenses = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte=today,
            license_expiry_date__lte=expiry_date,
            is_active=True,
            balance_cif__gte=Decimal('100.00')
        ).select_related('exporter', 'port').prefetch_related(
            'export_license__norm_class'
        ).order_by('license_expiry_date')[:5]

        licenses_data = []
        for license_obj in licenses:
            # Calculate days to expiry
            days_to_expiry = (license_obj.license_expiry_date - today).days

            # Get SION norms
            sion_norms = list(
                license_obj.export_license.filter(
                    norm_class__isnull=False
                ).values_list('norm_class__norm_class', flat=True).distinct()
            )

            licenses_data.append({
                'license_number': license_obj.license_number,
                'license_expiry_date': license_obj.license_expiry_date,
                'balance_cif': float(license_obj.balance_cif or 0),
                'sion_norms': sion_norms,
                'days_to_expiry': days_to_expiry,
            })

        return licenses_data

    def _get_boe_monthly_trend(self):
        """Get BOE count by month for last 6 months"""
        # Calculate date 6 months ago
        today = date.today()
        six_months_ago = today - relativedelta(months=6)

        # Get all BOE records from last 6 months with valid bill_of_entry_date
        boe_records = BillOfEntryModel.objects.filter(
            bill_of_entry_date__gte=six_months_ago,
            bill_of_entry_date__isnull=False
        ).values('bill_of_entry_date')

        # Initialize months dictionary
        months_data = {}
        for i in range(6):
            month_date = today - relativedelta(months=5 - i)
            month_key = month_date.strftime('%b %Y')
            months_data[month_key] = {
                'month': month_key,
                'count': 0,
                'year': month_date.year,
                'month_num': month_date.month,
            }

        # Count BOE records per month
        for boe in boe_records:
            boe_date = boe['bill_of_entry_date']
            month_key = boe_date.strftime('%b %Y')
            if month_key in months_data:
                months_data[month_key]['count'] += 1

        # Convert to list and sort by date
        monthly_trend = sorted(
            months_data.values(),
            key=lambda x: (x['year'], x['month_num'])
        )

        # Remove year and month_num from final output
        for item in monthly_trend:
            del item['year']
            del item['month_num']

        return monthly_trend
