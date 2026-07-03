from rest_framework.pagination import CursorPagination


class MasterCursorPagination(CursorPagination):
    """Cursor pagination keyed on (modified_on, id) — stable under concurrent
    writes and aligned with the `updated_since` delta cursor."""

    ordering = ("modified_on", "id")
    page_size = 200
    max_page_size = 1000
    page_size_query_param = "limit"


class ChangeFeedCursorPagination(CursorPagination):
    """Cursor pagination for the append-only change feed, keyed on (at, id).
    (MasterChange has no `modified_on`, so it can't use MasterCursorPagination.)"""

    ordering = ("at", "id")
    page_size = 500
    max_page_size = 2000
    page_size_query_param = "limit"
