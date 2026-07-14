"""
Live "already-allotted" aggregates for utilization-plan cap enforcement.

The denormalized `LicenseImportItemsModel.allotted_quantity` / `allotted_value`
columns are refreshed via `transaction.on_commit` (see
`apps/allotment/models.py::update_stock`), so they LAG the current request's
writes. Plan-cap checks that read those fields would under-count and let an
over-plan allotment slip through. These helpers compute the value LIVE from
`AllotmentItems`, using the SAME filter as `calculate_allotted_quantity`
(`apps/core/scripts/calculate_balance.py`): non-BOE allotments of type "AT".
Keeping the filter identical means plan math agrees with the availability the
user sees in the UI.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.core.constants import DEC_0, DEC_000

# Match calculate_balance.py's "allotted" filter exactly.
_ALLOTTED_FILTER = Q(
    allotment__bill_of_entry__isnull=True,
    allotment__type="AT",
)


def live_allotted_qty(item) -> Decimal:
    """Sum of quantity already allotted (non-BOE, type=AT) for this import item."""
    from apps.allotment.models import AllotmentItems
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item=item).aggregate(
        total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
    )["total"] or DEC_000


def live_allotted_value(item) -> Decimal:
    """Sum of CIF-FC already allotted (non-BOE, type=AT) for this import item."""
    from apps.allotment.models import AllotmentItems
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item=item).aggregate(
        total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
    )["total"] or DEC_0


def live_allotted_qty_for(item_ids) -> Decimal:
    """Sum of quantity already allotted across a set of import items (group cap)."""
    from apps.allotment.models import AllotmentItems
    ids = list(item_ids)
    if not ids:
        return DEC_000
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id__in=ids).aggregate(
        total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
    )["total"] or DEC_000


def live_allotted_value_for(item_ids) -> Decimal:
    """Sum of CIF-FC already allotted across a set of import items (group cap)."""
    from apps.allotment.models import AllotmentItems
    ids = list(item_ids)
    if not ids:
        return DEC_0
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id__in=ids).aggregate(
        total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
    )["total"] or DEC_0
