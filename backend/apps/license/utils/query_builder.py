"""
Reusable query builder utilities for license filtering.

This module provides a clean, composable API for building complex Django Q objects
and querysets with date ranges, filters, exclusions, and logical combinations.
"""
import datetime
from typing import Dict, List, Optional, Any

from django.conf import settings
from django.db.models import Q, QuerySet


class QueryFilterBuilder:
    """
    Composable query filter builder for creating complex Q objects.

    Example:
        builder = QueryFilterBuilder()
        builder.add_and_filters({'purchase_status': 'GE', 'is_au': False})
        builder.add_or_filters({'exporter__name__icontains': ['Parle', 'Britannia']})
        builder.add_exclude_filters({'export_license__old_quantity': 0})
        q_object = builder.build()
    """

    def __init__(self):
        self.base_filter = Q()

    def add_and_filters(self, filters: Dict[str, Any]) -> 'QueryFilterBuilder':
        """Add AND filters to the query."""
        for key, value in filters.items():
            self.base_filter &= Q(**{key: value})
        return self

    def add_or_filters(self, filters: Dict[str, Any]) -> 'QueryFilterBuilder':
        """
        Add OR filters to the query.
        Supports list values for __icontains fields.
        """
        for key, value in filters.items():
            if isinstance(value, list) and '__icontains' in key:
                or_filter = Q()
                for v in value:
                    or_filter |= Q(**{key: v})
                self.base_filter &= or_filter
            else:
                self.base_filter &= Q(**{key: value})
        return self

    def add_exclude_filters(self, filters: Dict[str, Any]) -> 'QueryFilterBuilder':
        """
        Add exclusion filters to the query.
        Supports list values for __icontains fields.
        """
        for key, value in filters.items():
            if isinstance(value, list) and '__icontains' in key:
                exclude_filter = Q()
                for v in value:
                    exclude_filter |= Q(**{key: v})
                self.base_filter &= ~exclude_filter
            else:
                self.base_filter &= ~Q(**{key: value})
        return self

    def add_and_or_filters(self, filter_groups: List[Dict[str, Any]]) -> 'QueryFilterBuilder':
        """
        Add groups of AND filters combined with OR.
        Example: (A AND B) OR (C AND D)
        """
        combined_filter = Q()
        for group in filter_groups:
            group_filter = Q()
            for key, value in group.items():
                group_filter &= Q(**{key: value})
            combined_filter |= group_filter
        self.base_filter &= combined_filter
        return self

    def build(self) -> Q:
        """Return the constructed Q object."""
        return self.base_filter


class DateRangeHandler:
    """Handle date range logic for license queries."""

    @staticmethod
    def parse_date_range(
        date_range: Optional[Dict[str, str]] = None,
        default_offset_days: int = 15,
        field_name: str = 'license_expiry_date'
    ) -> Dict[str, datetime.datetime]:
        """
        Parse date range and return filter dict.

        Args:
            date_range: Dict with 'start' and 'end' keys (YYYY-MM-DD format)
            default_offset_days: Days to offset from today if no range provided
            field_name: The field name to apply date filters to

        Returns:
            Dict with field__gte and field__lte keys
        """
        filters = {}

        if date_range:
            start = date_range.get('start')
            end = date_range.get('end')

            if start:
                start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
                filters[f'{field_name}__gte'] = start_date

            if end:
                end_date = datetime.datetime.strptime(end, '%Y-%m-%d')
                filters[f'{field_name}__lte'] = end_date
        else:
            # Default: filter by expiry limit
            expiry_limit = datetime.datetime.today() - datetime.timedelta(days=default_offset_days)
            filters[f'{field_name}__gte'] = expiry_limit

        return filters

    @staticmethod
    def get_expiry_filters(
        is_expired: bool = False,
        expiry_days: Optional[int] = None,
        field_name: str = 'license_expiry_date'
    ) -> Dict[str, datetime.datetime]:
        """
        Get date filters for expired or active licenses.

        Args:
            is_expired: If True, return filters for expired licenses
            expiry_days: Override settings.EXPIRY_DAY
            field_name: The field name to apply date filters to

        Returns:
            Dict with field__gte and optional field__lte keys
        """
        expiry_days = expiry_days or getattr(settings, 'EXPIRY_DAY', 15)
        expiry_limit = datetime.datetime.today() - datetime.timedelta(days=expiry_days)

        filters = {}

        if is_expired:
            # Expired licenses: between 60 days ago and expiry_limit
            start = datetime.datetime.today() - datetime.timedelta(days=60)
            filters[f'{field_name}__gte'] = start
            filters[f'{field_name}__lte'] = expiry_limit
        else:
            # Active licenses: after expiry_limit
            filters[f'{field_name}__gte'] = expiry_limit

        return filters


class LicenseQueryBuilder:
    """
    High-level builder for license querysets with common patterns.

    Example:
        builder = LicenseQueryBuilder(LicenseDetailsModel)
        queryset = (builder
            .with_date_range(date_range)
            .with_purchase_status('GE')
            .with_norm_class('E5')
            .exclude_party(['Unwanted Company'])
            .build()
        )
    """

    def __init__(self, model):
        self.model = model
        self.filter_builder = QueryFilterBuilder()
        self.ordering = []

    def with_base_filters(self, **kwargs) -> 'LicenseQueryBuilder':
        """Add base filters."""
        self.filter_builder.add_and_filters(kwargs)
        return self

    def with_date_range(
        self,
        date_range: Optional[Dict[str, str]] = None,
        field_name: str = 'license_expiry_date',
        default_offset_days: int = 15
    ) -> 'LicenseQueryBuilder':
        """Add date range filters."""
        date_filters = DateRangeHandler.parse_date_range(
            date_range, default_offset_days, field_name
        )
        self.filter_builder.add_and_filters(date_filters)
        return self

    def with_expiry_filters(
        self,
        is_expired: bool = False,
        field_name: str = 'license_expiry_date'
    ) -> 'LicenseQueryBuilder':
        """Add expiry-based filters."""
        expiry_filters = DateRangeHandler.get_expiry_filters(is_expired, field_name=field_name)
        self.filter_builder.add_and_filters(expiry_filters)
        return self

    def with_purchase_status(self, status: str) -> 'LicenseQueryBuilder':
        """Add purchase status filter."""
        self.filter_builder.add_and_filters({'purchase_status': status})
        return self

    def with_norm_class(self, norm_class: str) -> 'LicenseQueryBuilder':
        """Add norm class filter."""
        self.filter_builder.add_and_filters({
            'export_license__norm_class__norm_class': norm_class
        })
        return self

    def with_party(self, parties: List[str]) -> 'LicenseQueryBuilder':
        """Filter by party names (OR logic)."""
        if parties:
            self.filter_builder.add_or_filters({
                'exporter__name__icontains': parties
            })
        return self

    def exclude_party(self, parties: List[str]) -> 'LicenseQueryBuilder':
        """Exclude party names."""
        if parties:
            self.filter_builder.add_exclude_filters({
                'exporter__name__icontains': parties
            })
        return self

    def with_is_au(self, is_au: bool = False) -> 'LicenseQueryBuilder':
        """Add is_au filter."""
        self.filter_builder.add_and_filters({'is_au': is_au})
        return self

    def order_by(self, *fields) -> 'LicenseQueryBuilder':
        """Add ordering."""
        self.ordering.extend(fields)
        return self

    def build(self) -> QuerySet:
        """Build and return the queryset."""
        q_object = self.filter_builder.build()
        queryset = self.model.objects.filter(q_object)

        if self.ordering:
            queryset = queryset.order_by(*self.ordering)

        return queryset.distinct()
