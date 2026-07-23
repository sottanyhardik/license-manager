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


def _item_pk(item):
    if item is None:
        return None
    return getattr(item, "pk", item)


def _normalize_item_ids(item_ids) -> list:
    if item_ids is None:
        return []

    ids = []
    for item_id in item_ids:
        item_id = _item_pk(item_id)
        if item_id not in (None, ""):
            ids.append(item_id)
    return list(dict.fromkeys(ids))


def live_allotted_qty(item) -> Decimal:
    """Sum of quantity already allotted (non-BOE, type=AT) for this import item."""
    from apps.allotment.models import AllotmentItems
    item_id = _item_pk(item)
    if item_id is None:
        return DEC_000
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id=item_id).aggregate(
        total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
    )["total"] or DEC_000


def live_allotted_value(item) -> Decimal:
    """Sum of CIF-FC already allotted (non-BOE, type=AT) for this import item."""
    from apps.allotment.models import AllotmentItems
    item_id = _item_pk(item)
    if item_id is None:
        return DEC_0
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id=item_id).aggregate(
        total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
    )["total"] or DEC_0


def live_allotted_qty_for(item_ids) -> Decimal:
    """Sum of quantity already allotted across a set of import items (group cap)."""
    from apps.allotment.models import AllotmentItems
    ids = _normalize_item_ids(item_ids)
    if not ids:
        return DEC_000
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id__in=ids).aggregate(
        total=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
    )["total"] or DEC_000


def live_allotted_value_for(item_ids) -> Decimal:
    """Sum of CIF-FC already allotted across a set of import items (group cap)."""
    from apps.allotment.models import AllotmentItems
    ids = _normalize_item_ids(item_ids)
    if not ids:
        return DEC_0
    return AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id__in=ids).aggregate(
        total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
    )["total"] or DEC_0


def planned_totals_for(item_ids) -> tuple[Decimal, Decimal]:
    """
    Sum of LicenseItemPlan.planned_quantity / planned_cif_fc across a group —
    the "Original Plan" (immutable outside the Plan tab / auto-plan; never
    touched by allotment create/delete/edit).

    Same aggregate the allocate-time `plan_exceeded` check uses (see
    `apps/allotment/views_actions.py::allocate_items`), factored out so any
    read-only display of "what's the plan cap for this item" (e.g. the
    Allocate screen's Planned Qty/$ display) can never drift from what is
    actually enforced. Prefer `plan_status_for` below when you also need the
    Used/Remaining breakdown — it composes this with the live-allotted sums.
    """
    from apps.license.models import LicenseItemPlan
    ids = _normalize_item_ids(item_ids)
    if not ids:
        return DEC_000, DEC_0
    agg = LicenseItemPlan.objects.filter(import_item_id__in=ids).aggregate(
        pq=Coalesce(Sum("planned_quantity"), Value(DEC_000), output_field=DecimalField()),
        pv=Coalesce(Sum("planned_cif_fc"), Value(DEC_0), output_field=DecimalField()),
    )
    return agg["pq"] or DEC_000, agg["pv"] or DEC_0


def plan_status_for(item) -> dict | None:
    """
    Original / Used / Remaining planned quantity & CIF-FC for an import
    item's plan-group (see `plan_grouping.group_ids_of`).

    "Remaining" is deliberately NOT a stored, debited/credited field — it's
    Original (from `LicenseItemPlan`, immutable from allotment code) minus
    Used (live-summed from `AllotmentItems` via `live_allotted_*_for`). That
    means creating/deleting/editing an allotment automatically changes what
    this function returns on the very next call, with no explicit "credit"
    or "debit" step required and no risk of drift between what's displayed
    and what `allocate_items` enforces — both call this same function.

    Returns None when the group has no `LicenseItemPlan` rows at all (i.e.
    the item is unconstrained by any plan — falls back to availability-based
    behavior everywhere else in the app).
    """
    from apps.license.models import LicenseItemPlan
    from apps.license.services.plan_grouping import group_ids_of

    gids = group_ids_of(item)
    if not gids or not LicenseItemPlan.objects.filter(import_item_id__in=gids).exists():
        return None

    original_qty, original_val = planned_totals_for(gids)
    used_qty = live_allotted_qty_for(gids)
    used_val = live_allotted_value_for(gids)
    return {
        "original_quantity": original_qty,
        "used_quantity": used_qty,
        "remaining_quantity": original_qty - used_qty,
        "original_cif_fc": original_val,
        "used_cif_fc": used_val,
        "remaining_cif_fc": original_val - used_val,
    }
