"""
Custom Pagination Classes for License Manager API

Provides multiple pagination strategies optimized for different use cases:
- StandardPagination: Default page number pagination (25 items/page)
- LargePagination: For bulk operations (100 items/page)
- CompactPagination: For dropdowns/selects (10 items/page)
- CursorPagination: For large datasets with filtering (optimal performance)
- UnlimitedPagination: For exports/reports (configurable limit)
"""

from rest_framework.pagination import (
    PageNumberPagination,
    CursorPagination as DRFCursorPagination,
    LimitOffsetPagination
)
from rest_framework.response import Response
from collections import OrderedDict


class StandardPagination(PageNumberPagination):
    """
    Standard pagination for most list views.

    Default: 25 items per page
    URL params:
    - page: Page number (e.g., ?page=2)
    - page_size: Items per page (e.g., ?page_size=50, max 200)

    Response format:
    {
        "count": 1000,
        "next": "http://api/endpoint/?page=3",
        "previous": "http://api/endpoint/?page=1",
        "results": [...]
    }
    """
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        """Enhanced response with additional metadata."""
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page.paginator.per_page),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('results', data)
        ]))


class LargePagination(PageNumberPagination):
    """
    Pagination for bulk operations and exports.

    Default: 100 items per page
    URL params:
    - page: Page number
    - page_size: Items per page (max 1000)

    Use for:
    - Bulk data exports
    - Admin views with many items
    - Reports with large datasets
    """
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page.paginator.per_page),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('results', data)
        ]))


class CompactPagination(PageNumberPagination):
    """
    Compact pagination for dropdowns and select fields.

    Default: 10 items per page
    URL params:
    - page: Page number
    - page_size: Items per page (max 50)

    Use for:
    - AsyncSelect components
    - Autocomplete dropdowns
    - Quick search results
    """
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class CursorPagination(DRFCursorPagination):
    """
    Cursor-based pagination for large datasets with consistent ordering.

    Advantages:
    - Faster than page number pagination for large datasets
    - Consistent results even when data changes
    - Prevents duplicate/missing items during pagination

    Default: 50 items per page
    Ordering: -created_at (newest first)

    URL params:
    - cursor: Encoded cursor string (e.g., ?cursor=cD0yMDIx...)
    - page_size: Items per page (max 200)

    Response format:
    {
        "next": "http://api/endpoint/?cursor=cD0yMDIx...",
        "previous": "http://api/endpoint/?cursor=cj1iYWNr...",
        "results": [...]
    }

    Use for:
    - Transaction history
    - Activity feeds
    - Infinite scroll
    - Real-time data streams
    """
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
    ordering = "-created_at"  # Default ordering
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        """Enhanced response with metadata."""
        return Response(OrderedDict([
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('results', data)
        ]))


class LimitOffsetPaginationWithCount(LimitOffsetPagination):
    """
    Limit-offset pagination with total count.

    More flexible than page number pagination, allows arbitrary offsets.

    Default: 25 items, max 200
    URL params:
    - limit: Number of items to return (e.g., ?limit=50)
    - offset: Starting position (e.g., ?offset=100)

    Response format:
    {
        "count": 1000,
        "next": "http://api/endpoint/?limit=25&offset=50",
        "previous": "http://api/endpoint/?limit=25&offset=0",
        "results": [...]
    }

    Use for:
    - Custom pagination UI
    - "Load more" buttons
    - Virtual scrolling
    """
    default_limit = 25
    max_limit = 200
    limit_query_param = "limit"
    offset_query_param = "offset"


class UnlimitedPagination(PageNumberPagination):
    """
    Pagination with very high limits for exports and reports.

    Default: 1000 items per page
    URL params:
    - page: Page number
    - page_size: Items per page (max 10000)

    ⚠️ Warning: Use with caution! Large page sizes can:
    - Cause memory issues
    - Slow down API responses
    - Timeout on large datasets

    Use for:
    - CSV/Excel exports
    - Full reports
    - Data migrations

    Recommendation: Use with proper filtering and .only()/.defer()
    """
    page_size = 1000
    page_size_query_param = "page_size"
    max_page_size = 10000

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page.paginator.per_page),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('results', data)
        ]))


class OptimizedCursorPagination(DRFCursorPagination):
    """
    Optimized cursor pagination for time-series data.

    Specifically optimized for:
    - License transactions
    - Ledger entries
    - Bill of Entry items
    - Activity logs

    Features:
    - Uses database indexes efficiently
    - Consistent ordering by ID + timestamp
    - Prevents pagination issues during concurrent updates

    Default: 100 items per page
    Ordering: -id (newest first, using primary key)
    """
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = "-id"  # Primary key ordering (most efficient)
    cursor_query_param = "cursor"


# Backward compatibility alias
StandardResultsSetPagination = StandardPagination
