"""
Custom Filter Backends for License Manager API

Provides comprehensive filtering, searching, and ordering capabilities
with advanced features like:
- Case-insensitive search
- Date range filtering
- Numeric range filtering
- Multiple field search
- Custom ordering with nulls handling
- Filter validation and sanitization
"""

from rest_framework import filters
from django_filters import rest_framework as django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from typing import List, Optional
import operator
from functools import reduce


# ============================================================================
# Enhanced Search Filter
# ============================================================================

class EnhancedSearchFilter(filters.SearchFilter):
    """
    Enhanced search filter with case-insensitive search and multiple operators.

    Features:
    - Case-insensitive search (icontains)
    - Exact match with = prefix
    - Starts with ^ prefix
    - Ends with $ prefix
    - Multiple search terms (AND logic)

    Usage:
        search_fields = ['name', 'email', '=license_number', '^company__name']

    Examples:
        ?search=john              # icontains across all fields
        ?search=john doe          # AND logic: contains "john" AND "doe"
        ?search==license123       # Exact match for fields with = prefix
        ?search=^Parle            # Starts with for fields with ^ prefix
    """

    def get_search_terms(self, request):
        """
        Get search terms from request.
        Split by spaces to support multiple terms with AND logic.
        """
        params = request.query_params.get(self.search_param, '')
        params = params.replace('\x00', '')  # strip null characters
        params = params.replace(',', ' ')    # support comma-separated
        return params.split()

    def construct_search(self, field_name):
        """
        Construct search query with appropriate lookup.

        Supports:
        - 'field': case-insensitive contains
        - '=field': exact match
        - '^field': starts with
        - '$field': ends with
        - '@field': word search (useful for full-text)
        """
        lookup = self.lookup_prefixes.get(field_name[0])
        if lookup:
            field_name = field_name[1:]
            # Use iexact, istartswith, iendswith for case-insensitive
            if lookup == 'exact':
                lookup = 'iexact'
            elif lookup == 'startswith':
                lookup = 'istartswith'
            elif lookup == 'endswith':
                lookup = 'iendswith'
        else:
            lookup = 'icontains'

        return f"{field_name}__{lookup}"

    def filter_queryset(self, request, queryset, view):
        """
        Apply search filtering with multiple terms (AND logic).
        """
        search_fields = self.get_search_fields(view, request)
        search_terms = self.get_search_terms(request)

        if not search_fields or not search_terms:
            return queryset

        orm_lookups = [
            self.construct_search(str(search_field))
            for search_field in search_fields
        ]

        # Build OR queries for each term across all fields
        queries = []
        for search_term in search_terms:
            term_queries = [
                Q(**{orm_lookup: search_term})
                for orm_lookup in orm_lookups
            ]
            # OR across fields for this term
            queries.append(reduce(operator.or_, term_queries))

        # AND across all search terms
        if queries:
            queryset = queryset.filter(reduce(operator.and_, queries))

        return queryset.distinct()


# ============================================================================
# Advanced Ordering Filter
# ============================================================================

class AdvancedOrderingFilter(filters.OrderingFilter):
    """
    Advanced ordering filter with nulls handling and multiple fields.

    Features:
    - NULLS FIRST/LAST support
    - Multiple field ordering
    - Case-insensitive ordering
    - Related field ordering

    Usage:
        ordering_fields = ['name', 'created_at', 'company__name']
        ordering = ['-created_at']  # Default ordering

    Examples:
        ?ordering=name                    # ASC
        ?ordering=-name                   # DESC
        ?ordering=name,-created_at        # Multiple fields
        ?ordering=name_nulls_first        # Nulls first
        ?ordering=-name_nulls_last        # Nulls last, DESC
    """

    ordering_param = 'ordering'
    ordering_description = _(
        'Which field to use when ordering the results. '
        'Prefix with - for descending. '
        'Suffix with _nulls_first or _nulls_last for null handling.'
    )

    def get_ordering(self, request, queryset, view):
        """
        Get ordering from request with nulls handling.
        """
        params = request.query_params.get(self.ordering_param)
        if params:
            fields = [param.strip() for param in params.split(',')]
            ordering = self.remove_invalid_fields(queryset, fields, view, request)
            if ordering:
                return ordering

        # Default ordering
        return self.get_default_ordering(view)

    def filter_queryset(self, request, queryset, view):
        """
        Apply ordering with nulls handling support.
        """
        ordering = self.get_ordering(request, queryset, view)

        if ordering:
            # Process nulls handling
            from django.db.models import F
            processed_ordering = []

            for field in ordering:
                # Check for nulls handling suffix
                if '_nulls_first' in field:
                    field = field.replace('_nulls_first', '')
                    desc = field.startswith('-')
                    field_name = field[1:] if desc else field

                    # Use F() with nulls_first
                    if desc:
                        processed_ordering.append(F(field_name).desc(nulls_first=True))
                    else:
                        processed_ordering.append(F(field_name).asc(nulls_first=True))

                elif '_nulls_last' in field:
                    field = field.replace('_nulls_last', '')
                    desc = field.startswith('-')
                    field_name = field[1:] if desc else field

                    # Use F() with nulls_last
                    if desc:
                        processed_ordering.append(F(field_name).desc(nulls_last=True))
                    else:
                        processed_ordering.append(F(field_name).asc(nulls_last=True))
                else:
                    processed_ordering.append(field)

            return queryset.order_by(*processed_ordering)

        return queryset


# ============================================================================
# Date Range Filter Backend
# ============================================================================

class DateRangeFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend for date range filtering.

    Supports filtering by:
    - date_from: start date (>=)
    - date_to: end date (<=)
    - For any date field specified in date_filter_fields

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            date_filter_fields = {
                'created_at': 'created_at',
                'license_date': 'license_date',
            }
            filter_backends = [DateRangeFilterBackend]

    Examples:
        ?created_at_from=2024-01-01
        ?created_at_to=2024-12-31
        ?license_date_from=2024-01-01&license_date_to=2024-06-30
    """

    def filter_queryset(self, request, queryset, view):
        """Apply date range filtering."""
        date_filter_fields = getattr(view, 'date_filter_fields', {})

        for param_prefix, field_name in date_filter_fields.items():
            date_from = request.query_params.get(f'{param_prefix}_from')
            date_to = request.query_params.get(f'{param_prefix}_to')

            if date_from:
                queryset = queryset.filter(**{f'{field_name}__gte': date_from})

            if date_to:
                queryset = queryset.filter(**{f'{field_name}__lte': date_to})

        return queryset

    def get_schema_operation_parameters(self, view):
        """Generate OpenAPI schema for date range filters."""
        date_filter_fields = getattr(view, 'date_filter_fields', {})
        parameters = []

        for param_prefix in date_filter_fields.keys():
            parameters.extend([
                {
                    'name': f'{param_prefix}_from',
                    'required': False,
                    'in': 'query',
                    'description': f'Start date for {param_prefix} (YYYY-MM-DD)',
                    'schema': {'type': 'string', 'format': 'date'},
                },
                {
                    'name': f'{param_prefix}_to',
                    'required': False,
                    'in': 'query',
                    'description': f'End date for {param_prefix} (YYYY-MM-DD)',
                    'schema': {'type': 'string', 'format': 'date'},
                },
            ])

        return parameters


# ============================================================================
# Numeric Range Filter Backend
# ============================================================================

class NumericRangeFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend for numeric range filtering.

    Supports filtering by:
    - field_min: minimum value (>=)
    - field_max: maximum value (<=)
    - For any numeric field specified in numeric_filter_fields

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            numeric_filter_fields = {
                'balance': 'balance_cif',
                'quantity': 'quantity',
            }
            filter_backends = [NumericRangeFilterBackend]

    Examples:
        ?balance_min=1000
        ?balance_max=50000
        ?quantity_min=10&quantity_max=100
    """

    def filter_queryset(self, request, queryset, view):
        """Apply numeric range filtering."""
        numeric_filter_fields = getattr(view, 'numeric_filter_fields', {})

        for param_prefix, field_name in numeric_filter_fields.items():
            min_value = request.query_params.get(f'{param_prefix}_min')
            max_value = request.query_params.get(f'{param_prefix}_max')

            if min_value:
                try:
                    queryset = queryset.filter(**{f'{field_name}__gte': float(min_value)})
                except (ValueError, TypeError):
                    pass  # Invalid numeric value, skip

            if max_value:
                try:
                    queryset = queryset.filter(**{f'{field_name}__lte': float(max_value)})
                except (ValueError, TypeError):
                    pass

        return queryset

    def get_schema_operation_parameters(self, view):
        """Generate OpenAPI schema for numeric range filters."""
        numeric_filter_fields = getattr(view, 'numeric_filter_fields', {})
        parameters = []

        for param_prefix in numeric_filter_fields.keys():
            parameters.extend([
                {
                    'name': f'{param_prefix}_min',
                    'required': False,
                    'in': 'query',
                    'description': f'Minimum value for {param_prefix}',
                    'schema': {'type': 'number'},
                },
                {
                    'name': f'{param_prefix}_max',
                    'required': False,
                    'in': 'query',
                    'description': f'Maximum value for {param_prefix}',
                    'schema': {'type': 'number'},
                },
            ])

        return parameters


# ============================================================================
# Boolean Filter Backend
# ============================================================================

class BooleanFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend for boolean field filtering with "all" option.

    Supports filtering by:
    - field=true/false/all
    - For any boolean field specified in boolean_filter_fields

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            boolean_filter_fields = ['is_active', 'is_restricted']
            filter_backends = [BooleanFilterBackend]

    Examples:
        ?is_active=true
        ?is_active=false
        ?is_active=all        # No filtering
        ?is_restricted=true
    """

    def filter_queryset(self, request, queryset, view):
        """Apply boolean filtering."""
        boolean_filter_fields = getattr(view, 'boolean_filter_fields', [])

        for field_name in boolean_filter_fields:
            value = request.query_params.get(field_name)

            if value and value.lower() != 'all':
                if value.lower() in ('true', '1', 'yes'):
                    queryset = queryset.filter(**{field_name: True})
                elif value.lower() in ('false', '0', 'no'):
                    queryset = queryset.filter(**{field_name: False})

        return queryset

    def get_schema_operation_parameters(self, view):
        """Generate OpenAPI schema for boolean filters."""
        boolean_filter_fields = getattr(view, 'boolean_filter_fields', [])
        parameters = []

        for field_name in boolean_filter_fields:
            parameters.append({
                'name': field_name,
                'required': False,
                'in': 'query',
                'description': f'Filter by {field_name} (true/false/all)',
                'schema': {
                    'type': 'string',
                    'enum': ['true', 'false', 'all'],
                },
            })

        return parameters


# ============================================================================
# Multiple Choice Filter Backend
# ============================================================================

class MultipleChoiceFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend for filtering by multiple values (IN query).

    Supports filtering by:
    - field=value1,value2,value3
    - For any field specified in multiple_choice_filter_fields

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            multiple_choice_filter_fields = {
                'company': 'company_id',
                'status': 'purchase_status__code',
            }
            filter_backends = [MultipleChoiceFilterBackend]

    Examples:
        ?company=1,2,3        # company_id IN (1,2,3)
        ?status=GE,MI         # purchase_status__code IN ('GE', 'MI')
    """

    def filter_queryset(self, request, queryset, view):
        """Apply multiple choice filtering."""
        multiple_choice_filter_fields = getattr(view, 'multiple_choice_filter_fields', {})

        for param_name, field_name in multiple_choice_filter_fields.items():
            values = request.query_params.get(param_name)

            if values:
                # Split by comma
                values_list = [v.strip() for v in values.split(',') if v.strip()]

                if values_list:
                    queryset = queryset.filter(**{f'{field_name}__in': values_list})

        return queryset

    def get_schema_operation_parameters(self, view):
        """Generate OpenAPI schema for multiple choice filters."""
        multiple_choice_filter_fields = getattr(view, 'multiple_choice_filter_fields', {})
        parameters = []

        for param_name in multiple_choice_filter_fields.keys():
            parameters.append({
                'name': param_name,
                'required': False,
                'in': 'query',
                'description': f'Filter by {param_name} (comma-separated list)',
                'schema': {'type': 'string'},
                'style': 'form',
                'explode': False,
            })

        return parameters


# ============================================================================
# Combined Filter Backend (All-in-One)
# ============================================================================

class CombinedFilterBackend(filters.BaseFilterBackend):
    """
    Combined filter backend that includes all custom filters.

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            filter_backends = [CombinedFilterBackend, EnhancedSearchFilter, AdvancedOrderingFilter]

            # Configure filters
            date_filter_fields = {'created': 'created_at'}
            numeric_filter_fields = {'balance': 'balance_cif'}
            boolean_filter_fields = ['is_active']
            multiple_choice_filter_fields = {'company': 'company_id'}
    """

    def filter_queryset(self, request, queryset, view):
        """Apply all filter backends."""
        # Date range filtering
        date_backend = DateRangeFilterBackend()
        queryset = date_backend.filter_queryset(request, queryset, view)

        # Numeric range filtering
        numeric_backend = NumericRangeFilterBackend()
        queryset = numeric_backend.filter_queryset(request, queryset, view)

        # Boolean filtering
        boolean_backend = BooleanFilterBackend()
        queryset = boolean_backend.filter_queryset(request, queryset, view)

        # Multiple choice filtering
        multiple_backend = MultipleChoiceFilterBackend()
        queryset = multiple_backend.filter_queryset(request, queryset, view)

        return queryset

    def get_schema_operation_parameters(self, view):
        """Generate combined OpenAPI schema."""
        parameters = []

        # Add all filter parameters
        date_backend = DateRangeFilterBackend()
        parameters.extend(date_backend.get_schema_operation_parameters(view))

        numeric_backend = NumericRangeFilterBackend()
        parameters.extend(numeric_backend.get_schema_operation_parameters(view))

        boolean_backend = BooleanFilterBackend()
        parameters.extend(boolean_backend.get_schema_operation_parameters(view))

        multiple_backend = MultipleChoiceFilterBackend()
        parameters.extend(multiple_backend.get_schema_operation_parameters(view))

        return parameters


# ============================================================================
# Utility Functions
# ============================================================================

def get_filter_fields_from_serializer(serializer_class) -> List[str]:
    """
    Extract filterable fields from serializer.

    Returns list of field names that can be filtered.
    """
    if not serializer_class:
        return []

    serializer = serializer_class()
    return list(serializer.fields.keys())


def build_filter_description(view) -> str:
    """
    Build comprehensive filter description for API documentation.
    """
    descriptions = []

    if hasattr(view, 'search_fields'):
        descriptions.append(f"Search: {', '.join(view.search_fields)}")

    if hasattr(view, 'ordering_fields'):
        descriptions.append(f"Ordering: {', '.join(view.ordering_fields)}")

    if hasattr(view, 'date_filter_fields'):
        descriptions.append(f"Date filters: {', '.join(view.date_filter_fields.keys())}")

    if hasattr(view, 'numeric_filter_fields'):
        descriptions.append(f"Numeric filters: {', '.join(view.numeric_filter_fields.keys())}")

    if hasattr(view, 'boolean_filter_fields'):
        descriptions.append(f"Boolean filters: {', '.join(view.boolean_filter_fields)}")

    return " | ".join(descriptions) if descriptions else "No filters configured"
