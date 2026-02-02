"""
Django-Filter FilterSets for License Manager

Pre-configured FilterSets for common filtering patterns.
"""

import django_filters
from django.db import models
from django_filters import rest_framework as filters
from django.db.models import Q


# ============================================================================
# Base FilterSets
# ============================================================================

class BaseFilterSet(filters.FilterSet):
    """
    Base FilterSet with common filters.

    Includes:
    - created_at range
    - updated_at range
    - search across common fields
    """

    created_at_from = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_at_to = filters.DateFilter(field_name='created_at', lookup_expr='lte')
    updated_at_from = filters.DateFilter(field_name='updated_at', lookup_expr='gte')
    updated_at_to = filters.DateFilter(field_name='updated_at', lookup_expr='lte')


class AuditFilterSet(BaseFilterSet):
    """
    FilterSet for models with audit fields (created_by, updated_by).
    """

    created_by = filters.NumberFilter(field_name='created_by_id')
    updated_by = filters.NumberFilter(field_name='updated_by_id')


# ============================================================================
# License FilterSets
# ============================================================================

class LicenseFilterSet(BaseFilterSet):
    """
    Comprehensive FilterSet for License model.

    Supports filtering by:
    - Company (single or multiple)
    - License dates (range)
    - Expiry dates (range)
    - Status (active, expired, expiring soon)
    - Balance (range)
    - Purchase status
    - License number (exact or contains)
    """

    # Company filters
    company = filters.ModelMultipleChoiceFilter(
        field_name='company',
        queryset=None,  # Will be set dynamically
        label='Company (multiple)'
    )
    company_id = filters.NumberFilter(field_name='company_id')
    company_ids = filters.CharFilter(method='filter_company_ids', label='Company IDs (comma-separated)')

    # License date filters
    license_date_from = filters.DateFilter(field_name='license_date', lookup_expr='gte')
    license_date_to = filters.DateFilter(field_name='license_date', lookup_expr='lte')

    # Expiry date filters
    license_expiry_date_from = filters.DateFilter(field_name='license_expiry_date', lookup_expr='gte')
    license_expiry_date_to = filters.DateFilter(field_name='license_expiry_date', lookup_expr='lte')

    # Status filters
    is_active = filters.BooleanFilter(field_name='is_active')
    is_expired = filters.BooleanFilter(field_name='is_expired')
    is_incomplete = filters.BooleanFilter(field_name='is_incomplete')

    # Status special filters
    status = filters.ChoiceFilter(
        method='filter_by_status',
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('expiring_soon', 'Expiring Soon (30 days)'),
            ('incomplete', 'Incomplete'),
        ],
        label='License Status'
    )

    # Balance filters
    balance_cif_min = filters.NumberFilter(field_name='balance_cif', lookup_expr='gte')
    balance_cif_max = filters.NumberFilter(field_name='balance_cif', lookup_expr='lte')
    has_balance = filters.BooleanFilter(method='filter_has_balance', label='Has Balance > 0')

    # Purchase status
    purchase_status = filters.CharFilter(field_name='purchase_status__code')
    purchase_status_ids = filters.CharFilter(method='filter_purchase_status_ids', label='Purchase Status IDs')

    # License number
    license_number = filters.CharFilter(field_name='license_number', lookup_expr='iexact')
    license_number_contains = filters.CharFilter(field_name='license_number', lookup_expr='icontains')

    # Exporter
    exporter = filters.CharFilter(field_name='exporter', lookup_expr='icontains')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set company queryset dynamically
        from core.models import CompanyModel
        if 'company' in self.filters:
            self.filters['company'].queryset = CompanyModel.objects.all()

    def filter_company_ids(self, queryset, name, value):
        """Filter by comma-separated company IDs."""
        if value:
            ids = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            return queryset.filter(company_id__in=ids)
        return queryset

    def filter_by_status(self, queryset, name, value):
        """Filter by license status."""
        from datetime import date, timedelta

        if value == 'active':
            return queryset.filter(is_active=True, is_expired=False)
        elif value == 'expired':
            return queryset.filter(Q(is_expired=True) | Q(license_expiry_date__lt=date.today()))
        elif value == 'expiring_soon':
            today = date.today()
            thirty_days = today + timedelta(days=30)
            return queryset.filter(
                is_active=True,
                license_expiry_date__gte=today,
                license_expiry_date__lte=thirty_days
            )
        elif value == 'incomplete':
            return queryset.filter(is_incomplete=True)

        return queryset

    def filter_has_balance(self, queryset, name, value):
        """Filter licenses with balance > 0."""
        if value:
            return queryset.filter(balance_cif__gt=0)
        else:
            return queryset.filter(balance_cif=0)

    def filter_purchase_status_ids(self, queryset, name, value):
        """Filter by comma-separated purchase status codes."""
        if value:
            codes = [x.strip().upper() for x in value.split(',') if x.strip()]
            return queryset.filter(purchase_status__code__in=codes)
        return queryset

    class Meta:
        fields = {
            'license_number': ['exact', 'icontains'],
            'company__name': ['icontains'],
            'is_active': ['exact'],
            'balance_cif': ['gte', 'lte', 'exact'],
        }


# ============================================================================
# BOE FilterSets
# ============================================================================

class BOEFilterSet(BaseFilterSet):
    """
    FilterSet for Bill of Entry model.
    """

    # BOE date filters
    boe_date_from = filters.DateFilter(field_name='boe_date', lookup_expr='gte')
    boe_date_to = filters.DateFilter(field_name='boe_date', lookup_expr='lte')

    # Company filter
    company = filters.NumberFilter(field_name='company_id')
    company_ids = filters.CharFilter(method='filter_company_ids')

    # BOE number
    boe_number = filters.CharFilter(field_name='boe_number', lookup_expr='icontains')

    # Port
    port = filters.CharFilter(field_name='port', lookup_expr='icontains')

    # Recent filter
    recent_days = filters.NumberFilter(method='filter_recent_days', label='Recent Days')

    def filter_company_ids(self, queryset, name, value):
        """Filter by comma-separated company IDs."""
        if value:
            ids = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            return queryset.filter(company_id__in=ids)
        return queryset

    def filter_recent_days(self, queryset, name, value):
        """Filter BOEs from last N days."""
        from datetime import date, timedelta
        if value:
            cutoff_date = date.today() - timedelta(days=value)
            return queryset.filter(boe_date__gte=cutoff_date)
        return queryset


# ============================================================================
# Allotment FilterSets
# ============================================================================

class AllotmentFilterSet(BaseFilterSet):
    """
    FilterSet for Allotment model.
    """

    # Allotment date filters
    allotment_date_from = filters.DateFilter(field_name='allotment_date', lookup_expr='gte')
    allotment_date_to = filters.DateFilter(field_name='allotment_date', lookup_expr='lte')

    # Company filter
    company = filters.NumberFilter(field_name='company_id')
    company_ids = filters.CharFilter(method='filter_company_ids')

    # License filter
    license = filters.NumberFilter(field_name='license_id')

    # Approval status
    is_approved = filters.BooleanFilter(field_name='is_approved')

    # Recent filter
    recent_days = filters.NumberFilter(method='filter_recent_days')

    def filter_company_ids(self, queryset, name, value):
        """Filter by comma-separated company IDs."""
        if value:
            ids = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            return queryset.filter(company_id__in=ids)
        return queryset

    def filter_recent_days(self, queryset, name, value):
        """Filter allotments from last N days."""
        from datetime import date, timedelta
        if value:
            cutoff_date = date.today() - timedelta(days=value)
            return queryset.filter(allotment_date__gte=cutoff_date)
        return queryset


# ============================================================================
# Master Data FilterSets
# ============================================================================

class CompanyFilterSet(BaseFilterSet):
    """FilterSet for Company model."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    email = filters.CharFilter(field_name='email', lookup_expr='icontains')
    iec = filters.CharFilter(field_name='iec', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')


class ItemNameFilterSet(BaseFilterSet):
    """FilterSet for ItemName model."""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    is_restricted = filters.BooleanFilter(field_name='is_restricted')
    item_head = filters.NumberFilter(field_name='item_head_id')


class HSCodeFilterSet(BaseFilterSet):
    """FilterSet for HSCode model."""

    hs_code = filters.CharFilter(field_name='hs_code', lookup_expr='icontains')
    description = filters.CharFilter(field_name='description', lookup_expr='icontains')


# ============================================================================
# Report FilterSets
# ============================================================================

class ItemReportFilterSet(filters.FilterSet):
    """
    FilterSet for Item Report with advanced filtering.
    """

    # Item names (multiple)
    item_names = filters.CharFilter(method='filter_item_names', label='Item Name IDs (comma-separated)')

    # Company filters
    company_ids = filters.CharFilter(method='filter_company_ids')
    exclude_company_ids = filters.CharFilter(method='filter_exclude_company_ids')

    # Balance filters
    min_balance = filters.NumberFilter(field_name='available_cif', lookup_expr='gte')
    min_avail_qty = filters.NumberFilter(field_name='available_quantity', lookup_expr='gte')

    # License status
    license_status = filters.ChoiceFilter(
        method='filter_license_status',
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('expiring_soon', 'Expiring Soon'),
            ('all', 'All'),
        ]
    )

    # Restriction status
    is_restricted = filters.BooleanFilter(field_name='is_restricted')

    # Purchase status
    purchase_status = filters.CharFilter(method='filter_purchase_status')

    def filter_item_names(self, queryset, name, value):
        """Filter by comma-separated item name IDs."""
        if value:
            ids = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            # Assuming queryset has items relationship
            return queryset.filter(items__id__in=ids).distinct()
        return queryset

    def filter_company_ids(self, queryset, name, value):
        """Include only these companies."""
        if value:
            ids = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            return queryset.filter(license__company_id__in=ids)
        return queryset

    def filter_exclude_company_ids(self, queryset, name, value):
        """Exclude these companies."""
        if value:
            ids = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            return queryset.exclude(license__company_id__in=ids)
        return queryset

    def filter_license_status(self, queryset, name, value):
        """Filter by license status."""
        from datetime import date, timedelta

        if value == 'active':
            return queryset.filter(license__is_active=True, license__is_expired=False)
        elif value == 'expired':
            return queryset.filter(
                Q(license__is_expired=True) |
                Q(license__license_expiry_date__lt=date.today())
            )
        elif value == 'expiring_soon':
            today = date.today()
            thirty_days = today + timedelta(days=30)
            return queryset.filter(
                license__is_active=True,
                license__license_expiry_date__gte=today,
                license__license_expiry_date__lte=thirty_days
            )

        return queryset

    def filter_purchase_status(self, queryset, name, value):
        """Filter by purchase status codes (comma-separated)."""
        if value:
            codes = [x.strip().upper() for x in value.split(',') if x.strip()]
            return queryset.filter(license__purchase_status__code__in=codes)
        return queryset
