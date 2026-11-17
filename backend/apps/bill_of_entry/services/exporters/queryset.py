"""Queryset shaping for the BOE exports (moved verbatim from api/views_export.py)."""
from django.db.models import Prefetch

from apps.bill_of_entry.models import RowDetails


def build_export_queryset(queryset):
    """Filtered BOE queryset -> BOEs with item details, prefetched + ordered for export."""
    queryset = queryset.prefetch_related(None)

    # Filter only BOEs with item details and order by date first, then company, item, port
    return queryset.filter(
        item_details__isnull=False
    ).select_related(
        'company',
        'port',
    ).prefetch_related(
        Prefetch(
            'item_details',
            queryset=RowDetails.objects.select_related(
                'sr_number',
                'sr_number__license',
                'sr_number__license__exporter',
                'sr_number__license__port',
                'sr_number__hs_code',
            # RowDetails.Meta.ordering plus an 'id' tiebreaker: rows of one BOE tie
            # on (transaction_type, BOE date), so without it the export row order
            # was arbitrary (golden tests flaked inside the full suite).
            ).order_by('transaction_type', 'bill_of_entry__bill_of_entry_date', 'id'),
        ),
    ).distinct().order_by(
        'bill_of_entry_date', 'company__name', 'product_name', 'port__code'
    )
