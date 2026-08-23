"""
Dashboard API View
Provides unified endpoint for all dashboard data in a single API call
"""
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import TruncMonth
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.allotment.models import AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.cache_utils import CACHE_TIMEOUT_MEDIUM
from apps.core.utils.exceptions import api_error
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator


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
    # Any authenticated user can reach the dashboard.
    # The data returned is filtered by role inside get() — users with no roles
    # receive an empty payload rather than a 403.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Role-filtered dashboard. Each section is only included when the user
        has the relevant role. Superusers see everything.
        Cache key is per-role-set so different roles get different cached payloads.
        """
        user = request.user
        is_super = user.is_superuser

        def has(role_codes):
            return is_super or user.has_any_role(role_codes)

        # Build a stable cache key from the user's role set
        roles_key = '_'.join(sorted(user.get_role_codes())) if not is_super else 'superuser'
        cache_key = f'view:dashboard:{roles_key}'

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        try:
            data = {}

            if has(['LICENSE_MANAGER', 'LICENSE_VIEWER', 'REPORT_VIEWER']):
                # Both widgets use the exact same live-balance eligibility
                # set. Resolve it once per uncached response so the summary
                # and queue cannot disagree and so the expensive balance
                # service is not evaluated twice.
                expiring_context = self._get_expiring_license_context()
                data['license_stats'] = self._get_license_stats(expiring_context)
                data['expiring_licenses'] = self._get_expiring_licenses(expiring_context)

            if has(['ALLOTMENT_MANAGER', 'ALLOTMENT_VIEWER', 'REPORT_VIEWER']):
                data['allotment_stats'] = self._get_allotment_stats()

            if has(['BOE_MANAGER', 'BOE_VIEWER', 'ACCOUNT_ACCESS', 'REPORT_VIEWER']):
                data['boe_stats'] = self._get_boe_stats()
                data['boe_monthly_trend'] = self._get_boe_monthly_trend()

            cache.set(cache_key, data, CACHE_TIMEOUT_MEDIUM)
            return Response(data)
        except Exception as e:
            return Response(
                api_error('Failed to load dashboard data', e, __name__),
                status=500,
            )

    def _get_license_stats(self, expiring_context=None):
        """Get license statistics"""
        # These categories are intentionally counted independently. The
        # response's `total` has always been their sum, rather than a raw
        # table count, so retain that contract while issuing one aggregate
        # query instead of three separate counts.
        category_counts = LicenseDetailsModel.objects.aggregate(
            active=Count('id', filter=Q(flags__is_expired=False, flags__is_null=False)),
            expired=Count('id', filter=Q(flags__is_expired=True, flags__is_null=False)),
            null_dfia=Count('id', filter=Q(flags__is_null=True)),
        )
        active_count = category_counts['active']
        expired_count = category_counts['expired']
        null_count = category_counts['null_dfia']

        # Total licenses
        total_count = active_count + expired_count + null_count

        # Expiring soon: licenses expiring in next 30 days. BL-LEDGER-02:
        # the cached `balance__balance_cif` column can be stale, so resolve
        # the $100 threshold against the LIVE, batched-computed balance
        # instead of filtering the DB column directly.
        today = date.today()
        expiry_date = today + timedelta(days=30)
        if expiring_context is None:
            expiring_candidate_ids = list(
                LicenseDetailsModel.objects.filter(
                    license_expiry_date__gte=today,
                    license_expiry_date__lte=expiry_date,
                    flags__is_active=True,
                ).values_list('id', flat=True)
            )
            expiring_live_balance = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
                expiring_candidate_ids
            )
        else:
            expiring_candidate_ids, expiring_live_balance = expiring_context
        expiring_count = sum(
            1 for lid in expiring_candidate_ids
            if expiring_live_balance.get(lid, Decimal('0')) >= Decimal('100.00')
        )

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
        # NOTE (Hidden BOEs / previous-owner utilisation, see
        # `apps.bill_of_entry.models.OTH_INVOICE_MARKER`): deliberately NOT
        # filtered here. This dashboard counts BOE records system-wide — a
        # raw activity/record count, not a licence balance or financial
        # figure, which is the one thing hidden BOEs are defined to affect.
        # Out of scope by design; left unfiltered.
        # Total BOE (all records - both with and without invoices)
        total_count = BillOfEntryModel.objects.count()

        # Pending invoices: where invoice_no is null or blank
        pending_invoices_count = BillOfEntryModel.objects.filter(
            Q(invoice_no__isnull=True) | Q(invoice_no='')
        ).count()

        # Recent 5 BOE ordered by bill_of_entry_date (all BOE records)
        recent_boe = BillOfEntryModel.objects.filter(
            bill_of_entry_date__isnull=False
        ).select_related('company').order_by('-bill_of_entry_date')[:5]

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

    def _get_expiring_license_context(self):
        """Return the shared candidate rows and live balances for expiry widgets.

        This deliberately remains request-local. The surrounding endpoint
        cache controls cross-request freshness; sharing it here only removes
        duplicate work while preserving the live-balance contract.
        """
        today = date.today()
        expiry_date = today + timedelta(days=30)

        # BL-LEDGER-02: the cached `balance__balance_cif` column can be
        # stale, so the $100 threshold can no longer be a DB filter. Fetch
        # every active license in the expiry window (unsliced), compute
        # live balance for all of them, THEN filter by balance and take the
        # top 5 soonest-expiring -- same "top 5 among balance >= $100"
        # semantics as before, just resolved against the live figure.
        candidates = LicenseDetailsModel.objects.filter(
            license_expiry_date__gte=today,
            license_expiry_date__lte=expiry_date,
            flags__is_active=True,
        ).select_related(
            'exporter', 'port', 'balance', 'flags',
        ).prefetch_related(
            Prefetch(
                'export_license',
                queryset=LicenseExportItemModel.objects.filter(
                    norm_class__isnull=False,
                ).select_related('norm_class'),
            )
        ).order_by('license_expiry_date')

        candidates = list(candidates)

        # Financial Ledger formula -- see `LicenseDetailsModel.
        # get_balance_cif`'s docstring; every "Balance CIF" the dashboard
        # shows must match the rest of the app.
        live_balance_map = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
            [license_obj.id for license_obj in candidates]
        )
        return candidates, live_balance_map

    def _get_expiring_licenses(self, expiring_context=None):
        """Get top 5 expiring licenses in next 30 days."""
        today = date.today()
        candidates, live_balance_map = expiring_context or self._get_expiring_license_context()

        licenses = [
            license_obj for license_obj in candidates
            if live_balance_map.get(license_obj.id, Decimal('0')) >= Decimal('100.00')
        ][:5]

        licenses_data = []
        for license_obj in licenses:
            # Calculate days to expiry
            days_to_expiry = (license_obj.license_expiry_date - today).days

            # `export_license__norm_class` is preloaded in the context.
            # Filtering the related manager here would clone its queryset and
            # silently reintroduce one SQL request per dashboard row.
            sion_norms = list(dict.fromkeys(
                export_item.norm_class.norm_class
                for export_item in license_obj.export_license.all()
                if export_item.norm_class is not None
            ))

            licenses_data.append({
                'license_number': license_obj.license_number,
                'license_expiry_date': license_obj.license_expiry_date,
                'balance_cif': float(live_balance_map.get(license_obj.id) or 0),
                'sion_norms': sion_norms,
                'days_to_expiry': days_to_expiry,
            })

        return licenses_data

    def _get_boe_monthly_trend(self):
        """Get BOE count by month for last 6 months"""
        # NOTE: same deliberate choice as `_get_boe_stats` above — hidden
        # BOEs are a per-(BOE, licence) concept and this trend is a
        # system-wide, licence-agnostic activity count, not a balance
        # figure. Left unfiltered.
        # Calculate date 6 months ago
        today = date.today()
        six_months_ago = today - relativedelta(months=6)

        # Get all BOE records from last 6 months with valid bill_of_entry_date
        monthly_counts = BillOfEntryModel.objects.filter(
            bill_of_entry_date__gte=six_months_ago,
            bill_of_entry_date__isnull=False
        ).annotate(month_start=TruncMonth('bill_of_entry_date')).values('month_start').annotate(
            count=Count('id')
        ).order_by('month_start')

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

        # The old implementation fetched every BOE date and counted in
        # Python. Group in SQL instead; output still includes all six month
        # buckets, including zero-count months, in the same order.
        for row in monthly_counts:
            month_key = row['month_start'].strftime('%b %Y')
            if month_key in months_data:
                months_data[month_key]['count'] = row['count']

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
