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


def group_used_snapshot(item) -> tuple[Decimal, Decimal]:
    """
    Live-allotted qty/CIF for `item`'s plan-group, RIGHT NOW.

    This is the snapshot `save_plan_lines_for_license` stamps onto every new
    `LicenseItemPlan` row as `baseline_used_quantity`/`baseline_used_cif_fc`
    — see that function and `plan_status_for` for why a snapshot, not a
    timestamp filter, is what makes "used since this plan" correct.
    """
    from apps.license.services.plan_grouping import group_ids_of
    gids = group_ids_of(item)
    return live_allotted_qty_for(gids), live_allotted_value_for(gids)


def save_plan_lines_for_license(license_obj, lines, *, delete_existing=True) -> list:
    """
    Full-replace: delete a license's existing `LicenseItemPlan` rows and
    create new ones from `lines` (dicts with `import_item`, `item_name`,
    `planned_quantity`, `unit_price`, `planned_cif_fc`, `note`, and
    optionally `remaining_quantity`/`remaining_cif_fc`) — the shape
    `bulk_upsert`, `auto_plan`/`e1_auto_plan`/`auto_plan_all`
    (`views/item_plan.py`) and the `plan_norms` management command all
    already produce.

    Stamps each new row with `baseline_used_quantity`/`baseline_used_cif_fc`
    = `group_used_snapshot(item)` at creation time, so `plan_status_for` can
    later compute "used SINCE this plan was saved" without relying on
    `AllotmentItems.created_on` — which breaks the moment `allocate_items`
    "amends" an existing row (`qty += ...`) instead of creating a new one:
    that row's `created_on` never advances, so a since-filter would silently
    miss any such amendment made after a re-plan. A snapshot doesn't care
    how the live total changed, only that it did.

    `remaining_quantity`/`remaining_cif_fc` — the live, independently-
    draining balance `allocate_items` decrements when an allotment names
    this specific line via `plan_line_id` (see views_actions.py) — default
    to the freshly-planned amount for a brand-new line. A caller that wants
    to PRESERVE an existing line's already-decremented balance across a
    regenerate-and-replace cycle (e.g. `e132_auto_plan.py` re-emitting an
    already-generated Vegetable Oil split unchanged) passes them explicitly.
    """
    from apps.license.models import LicenseItemPlan

    items_by_id = {it.id: it for it in license_obj.import_license.all()}
    baseline_cache: dict[int, tuple[Decimal, Decimal]] = {}

    def _baseline(item_id):
        if item_id not in baseline_cache:
            item = items_by_id.get(item_id)
            baseline_cache[item_id] = group_used_snapshot(item) if item is not None else (DEC_000, DEC_0)
        return baseline_cache[item_id]

    if delete_existing:
        LicenseItemPlan.objects.filter(license=license_obj).delete()

    created = []
    for ln in lines:
        baseline_qty, baseline_val = _baseline(ln.get("import_item"))
        planned_quantity = ln.get("planned_quantity", 0) or 0
        planned_cif_fc = ln.get("planned_cif_fc", 0) or 0
        remaining_quantity = ln["remaining_quantity"] if ln.get("remaining_quantity") is not None else planned_quantity
        remaining_cif_fc = ln["remaining_cif_fc"] if ln.get("remaining_cif_fc") is not None else planned_cif_fc
        created.append(LicenseItemPlan.objects.create(
            license=license_obj,
            import_item_id=ln.get("import_item"),
            item_name_id=ln.get("item_name"),
            planned_quantity=planned_quantity,
            unit_price=ln.get("unit_price", 0) or 0,
            planned_cif_fc=planned_cif_fc,
            remaining_quantity=remaining_quantity,
            remaining_cif_fc=remaining_cif_fc,
            note=ln.get("note", ""),
            planning_rule_id=ln.get("planning_rule_id"),
            planning_rule_version=ln.get("planning_rule_version"),
            planning_rule_priority=ln.get("planning_rule_priority"),
            allocation_provenance=ln.get("allocation_provenance", {}),
            baseline_used_quantity=baseline_qty,
            baseline_used_cif_fc=baseline_val,
        ))
    return created


def plan_status_for_ids(gids) -> dict | None:
    """
    Same computation as `plan_status_for`, factored out to accept an
    already-computed group-id list instead of an import item.

    For callers that already grouped the license's FULL import-item list in
    Python using the exact same `plan_grouping.plan_group_key` function (e.g.
    `plan_utilization.plan_utilization_rows` when it was not handed a
    caller-filtered `items` subset) — their computed member-id list for a
    group is guaranteed set-identical to what `group_ids_of(representative)`
    would return via a fresh DB query, since both iterate the same
    `license_id`-scoped item set with the same key function. Such callers can
    pass that list here directly and skip `group_ids_of`'s redundant
    re-query of the license's full item list.

    `plan_status_for(item)` is now a thin wrapper around this function — see
    it for the full behavior contract (Original/Used/Remaining semantics).
    Do not call this with an id list that is not provably equal to
    `group_ids_of` for some item in that group; the two must stay
    interchangeable for identical results.
    """
    from django.db.models import Min

    from apps.license.models import LicenseItemPlan

    if not gids:
        return None
    plans = LicenseItemPlan.objects.filter(import_item_id__in=gids)
    baseline = plans.aggregate(
        bq=Min("baseline_used_quantity"), bv=Min("baseline_used_cif_fc"),
    )
    if baseline["bq"] is None:
        return None  # no plan rows for this group at all

    original_qty, original_val = planned_totals_for(gids)
    current_used_qty = live_allotted_qty_for(gids)
    current_used_val = live_allotted_value_for(gids)
    used_qty = max(DEC_000, current_used_qty - baseline["bq"])
    used_val = max(DEC_0, current_used_val - baseline["bv"])
    return {
        "original_quantity": original_qty,
        "allocated_quantity": current_used_qty,
        "used_quantity": used_qty,
        "remaining_quantity": original_qty - used_qty,
        "original_cif_fc": original_val,
        "allocated_cif_fc": current_used_val,
        "used_cif_fc": used_val,
        "remaining_cif_fc": original_val - used_val,
    }


def plan_status_for(item) -> dict | None:
    """
    Original / Used / Remaining planned quantity & CIF-FC for an import
    item's plan-group (see `plan_grouping.group_ids_of`).

    "Remaining" is deliberately NOT a stored, debited/credited field — it's
    Original (from `LicenseItemPlan`, immutable from allotment code) minus
    Used. That means creating/deleting/editing an allotment automatically
    changes what this function returns on the very next call, with no
    explicit "credit"/"debit" step and no risk of drift between what's
    displayed and what `allocate_items` enforces — both call this function.

    "Used" = (current all-time live-allotted total for the group) minus
    (the `baseline_used_quantity`/`baseline_used_cif_fc` snapshot stamped on
    the group's plan rows when they were saved — see
    `save_plan_lines_for_license`). Replacing a plan (bulk_upsert / auto-plan)
    always re-snapshots the baseline to "right now", so Used resets to 0 and
    Remaining resets to the new Original — even though allotments already
    exist for the group from before the re-plan. Without this, re-planning a
    group that already had allotments against an OLDER, larger plan (e.g.
    shrinking the plan to match what's left after most of it was already
    used) would show a permanently negative Remaining, even though the
    person replanning clearly intends the new number to be what's allocable
    going forward, not a historical ledger.

    Returns None when the group has no `LicenseItemPlan` rows at all (i.e.
    the item is unconstrained by any plan — falls back to availability-based
    behavior everywhere else in the app).
    """
    from apps.license.services.plan_grouping import group_ids_of

    gids = group_ids_of(item)
    return plan_status_for_ids(gids)


def plan_status_for_items(items) -> dict:
    """
    Batched sibling of `plan_status_for` for MANY import items (e.g. a
    paginated page of the Allotment "available-licenses" screen) in a
    small, fixed number of queries instead of ~5 queries PER item
    (`group_ids_of`'s siblings query + the baseline/original/live-allotted
    aggregates in `plan_status_for_ids`). At page_size=100 this measured
    ~315 queries / ~290ms for the per-item loop against a small (2.4k-row)
    dev DB — see `AllotmentActionViewSet.available_licenses`'s own comment
    acknowledging this as a "batch as a follow-up if ever measured slow"
    item; this is that follow-up.

    Byte-identical to calling `plan_status_for(item)` once per item:
    groups every item by `(license_id, plan_group_key)` — the exact same
    grouping `group_ids_of` computes per-item — using ONE query for all
    siblings across every license represented in `items` (not one query
    per item), then resolves baseline/original/live-allotted with grouped
    aggregate queries instead of per-group aggregates.

    Returns `{item_id: dict|None}` — one entry per input item, `None` when
    that item's group has no `LicenseItemPlan` rows at all (unconstrained
    by any plan), exactly matching `plan_status_for`'s own contract.
    """
    from apps.license.models import LicenseImportItemsModel, LicenseItemPlan
    from apps.license.services.plan_grouping import plan_group_key

    items = list(items)
    if not items:
        return {}

    license_ids = {getattr(it, "license_id", None) for it in items}
    license_ids.discard(None)
    if not license_ids:
        return {it.id: None for it in items}

    # Every import item across every license represented on this page —
    # ONE query, mirroring `group_ids_of`'s own per-license siblings query
    # (same select_related/prefetch_related so `plan_group_key` computes
    # identically without triggering further queries).
    siblings = (
        LicenseImportItemsModel.objects
        .filter(license_id__in=license_ids)
        .select_related("hs_code")
        .prefetch_related("items")
    )
    groups: dict[tuple, list] = {}
    for sib in siblings:
        key = (sib.license_id, plan_group_key(sib))
        groups.setdefault(key, []).append(sib.id)

    item_to_gids: dict[int, list] = {}
    all_gids: set = set()
    for it in items:
        key = (it.license_id, plan_group_key(it))
        # Fallback mirrors `group_ids_of`'s behavior for an item with no
        # license (returns `[]` there); here an item always belongs to at
        # least its own group once grouped alongside its real siblings, so
        # this fallback is only reached for the same no-license edge case.
        gids = groups.get(key, [])
        item_to_gids[it.id] = gids
        all_gids.update(gids)

    if not all_gids:
        return {it.id: None for it in items}

    plans_by_item: dict[int, list] = {}
    for p in LicenseItemPlan.objects.filter(import_item_id__in=all_gids).values(
        "import_item_id", "baseline_used_quantity", "baseline_used_cif_fc",
        "planned_quantity", "planned_cif_fc",
    ):
        plans_by_item.setdefault(p["import_item_id"], []).append(p)

    from apps.allotment.models import AllotmentItems
    allotted_by_item: dict[int, tuple] = {}
    for r in (
        AllotmentItems.objects.filter(_ALLOTTED_FILTER, item_id__in=all_gids)
        .values("item_id")
        .annotate(
            q=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
            v=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
        )
    ):
        allotted_by_item[r["item_id"]] = (r["q"], r["v"])

    result: dict = {}
    for it in items:
        gids = item_to_gids.get(it.id) or []
        group_plans = [p for gid in gids for p in plans_by_item.get(gid, [])]
        if not group_plans:
            result[it.id] = None
            continue
        baseline_qty = min(p["baseline_used_quantity"] for p in group_plans)
        baseline_val = min(p["baseline_used_cif_fc"] for p in group_plans)
        original_qty = sum((p["planned_quantity"] for p in group_plans), DEC_000)
        original_val = sum((p["planned_cif_fc"] for p in group_plans), DEC_0)
        current_used_qty = sum((allotted_by_item.get(gid, (DEC_000, DEC_0))[0] for gid in gids), DEC_000)
        current_used_val = sum((allotted_by_item.get(gid, (DEC_000, DEC_0))[1] for gid in gids), DEC_0)
        used_qty = max(DEC_000, current_used_qty - baseline_qty)
        used_val = max(DEC_0, current_used_val - baseline_val)
        result[it.id] = {
            "original_quantity": original_qty,
            "allocated_quantity": current_used_qty,
            "used_quantity": used_qty,
            "remaining_quantity": original_qty - used_qty,
            "original_cif_fc": original_val,
            "allocated_cif_fc": current_used_val,
            "used_cif_fc": used_val,
            "remaining_cif_fc": original_val - used_val,
        }
    return result
