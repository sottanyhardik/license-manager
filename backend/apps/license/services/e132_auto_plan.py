"""
E132 Auto-Plan service.

Delegates classification and allocation entirely to the existing, tested
e132_plan engine (classify_e132_record / plan_e132_per_item_split), then
converts the result into ready-to-save LicenseItemPlan line dicts.

GROUP-ANCHORED, not per-raw-import-item: planning happens once per PHYSICAL
PRODUCT group (`plan_grouping.plan_group_key` — HSN + normalized
description), the same grouping every other planning-aware part of this app
already uses (display: `plan_utilization.py`; real allotment-cap
enforcement: `plan_enforcement.py::plan_status_for`, called from
`views_actions.py::allocate_items`). A licence can have one physical product
spread across several `LicenseImportItemsModel` rows (e.g. after a DGFT
re-serialization splits one row into several smaller ones) — planning each
row independently would let a stale, already-generated split on one row
silently coexist with a freshly-generated split on its new siblings, and
since the DISPLAY/ENFORCEMENT layers sum the whole group together, that
manifests as a double-counted plan (both a real UI bug and a real
allotment-cap bug this fix addresses). E126/E132, E1, and E5 all group via
the SAME canonical `plan_grouping.merge_items_for_classification` — no
Auto-Plan engine invents its own grouping logic.

Pipeline:
  1. Load import items, group them by `plan_group_key`
     (`merge_items_for_classification`) — one group per physical product,
     `available_quantity` SUMMED across every member. Skip any group whose
     summed available_quantity < MIN_PLAN_QTY.
  2. Build a records list keyed by the GROUP's representative import item id
     (lowest serial number in the group — matches `plan_grouping.py`'s
     documented invariant: "a group's plan is stored on its representative
     import item"), using the group's summed available_quantity as the
     planning quantity — for EVERY category, including the Vegetable Oil
     PKO/Cheese split target (the split is 40%/60% of the group's CURRENT
     total available quantity — see e132_plan.py's module docstring — but
     ONLY the first time it's generated; see step 4).
  3. Call plan_e132_per_item_split(records, balance_cif) — this runs the
     E132 waterfall (classify, allocate, wastage-reduction rebalance).
  4. PKO/Cheese balance tracking (business rule: once generated, a
     Vegetable Oil group's split becomes a FIXED commitment — Auto-Plan
     must never regenerate or recalculate it from the current
     available_quantity again). For any group the engine still classifies
     as split-eligible, check for EXISTING PKO/Cheese `LicenseItemPlan`
     rows across EVERY member of the group
     (`plan_grouping.existing_split_balances_for_groups` — not just its
     current representative, since a split generated before a
     re-serialization may still be sitting on a now-non-representative
     member): if EITHER target is found anywhere in the group, the WHOLE
     split is treated as already generated and BOTH targets re-emit their
     current, group-SUMMED `remaining_quantity`/`remaining_cif_fc`
     unchanged instead of the engine's freshly (re)computed 40/60 split
     (never just one side — see `compute_e132_auto_plan`'s inline comment
     for why partial overriding would risk breaking quantity conservation).
     Only a group with NO existing split plan anywhere among its members
     gets the engine's fresh split as its starting point. This is the only
     reason this file reads `LicenseItemPlan` — everything else here is a
     pure recompute from `available_quantity`, same as every other E132
     category.
  5. For each (representative, [split_lines]) map planning_item_name →
     ItemNameModel.id so the frontend can display the item-name labels.
  6. Return (lines, remaining_cif) — every line's `import_item` is a
     group's representative id; non-representative members never get a
     `LicenseItemPlan` row of their own.

Real debits/allotments against a specific plan line are attributed via
`plan_line_id` in the allocate-items request (see
`views_actions.py::allocate_items`), which decrements THAT line's
`remaining_quantity`/`remaining_cif_fc` directly — never derived from any
import item's `available_quantity`, which cannot tell PKO and Cheese apart.
This file's job is only to make sure Auto-Plan doesn't stomp on that
independently-draining balance once it exists.

MIN_PLAN_QTY = 50 — groups with a summed available_quantity below this
threshold are silently excluded.
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Optional

from apps.license.services.e132_plan import CHEESE, PKO, PLANNING_ORDER, UNIT_PRICE, plan_e132_per_item_split
from apps.license.services.plan_grouping import (
    existing_split_balances_for_groups,
    merge_items_for_classification,
    validate_group_plan_lines,
)

logger = logging.getLogger(__name__)

MIN_PLAN_QTY: float = 50.0

# Only these two planning items are ever "fixed once generated" — every
# other E132 category has no cross-target attribution ambiguity (a single
# item_name per group), so it's always safe (and desired) to keep
# recomputing them fresh from available_quantity on every run.
_SPLIT_TARGET_NAMES = (PKO, CHEESE)


def _r2(x) -> float:
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return 0.0


def _floor_qty(x) -> float:
    try:
        return float(math.floor(float(x)))
    except (TypeError, ValueError):
        return 0.0


def compute_e132_auto_plan(license_obj) -> tuple[list[dict], float]:
    """
    Run the E132 Auto Plan for *license_obj*.

    Returns (lines, remaining_cif):
      lines        — ready-to-save plan line dicts.
      remaining_cif — balance CIF not consumed by the plan (wastage).
    """
    from apps.core.models import ItemNameModel

    # ── Pre-fetch ItemNameModel IDs for all E132 planning-item labels ─────────
    name_ids: dict[str, Optional[int]] = {n: None for n in PLANNING_ORDER}
    for obj in ItemNameModel.objects.filter(name__in=list(PLANNING_ORDER)):
        name_ids[obj.name] = obj.id

    # ── Load import items and group by physical product ──────────────────────
    # `prefetch_related('items')` is needed by `merge_items_for_classification`
    # (its item-name-tag fallback reads `.items.all()` per item).
    import_items = list(
        license_obj.import_license.all()
        .select_related('hs_code')
        .prefetch_related('items')
        .order_by('serial_number')
    )
    groups = merge_items_for_classification(import_items)

    _live_balance_cif = license_obj.get_balance_cif
    balance_cif = float(
        _live_balance_cif if _live_balance_cif is not None else (license_obj.balance_cif or 0)
    )

    # ── Build records for the E132 classifier — one per GROUP ─────────────────
    # Use the group's summed available_quantity (not any single member's, and
    # never an original/total import quantity) as the planning qty for EVERY
    # category — including the Vegetable Oil 40/60 split target.
    records: list[dict] = []
    rep_to_group: dict[int, dict] = {}

    for group in groups:
        avail = float(group['available_quantity'] or 0)
        if avail < MIN_PLAN_QTY:
            continue   # below global minimum — skip silently
        rep_id = group['representative_id']
        records.append({
            'record_id':   rep_id,
            'hs_code':     group['hs_code'] or None,
            'description': group['description'] or None,
            'quantity':    Decimal(str(avail)),   # planning qty = group's summed available qty
        })
        rep_to_group[rep_id] = group

    if not records:
        return [], balance_cif

    # ── Call the E132 waterfall ───────────────────────────────────────────────
    # plan_e132_per_item_split returns:
    #   {record_id: [ {planning_item, reason, planned_quantity,
    #                  unit_price, planned_cif}, ... ]}
    split_result = plan_e132_per_item_split(records, balance_cif)

    # ── PKO/Cheese balance preservation (module docstring, step 4) ───────────
    # Only groups the engine STILL classifies as split-eligible (same
    # HSN/description match today) are candidates — this never revives a
    # stale balance for a group that's since been reclassified. Looks across
    # EVERY member of each group, not just its representative — see
    # `existing_split_balances_for_groups`'s docstring for why.
    existing_balances = existing_split_balances_for_groups(
        license_obj, list(rep_to_group.values()), _SPLIT_TARGET_NAMES,
    )

    # ── Convert to plan line dicts ────────────────────────────────────────────
    lines: list[dict] = []
    total_planned_cif = 0.0

    for rec in records:
        rid = rec['record_id']
        avail_qty = rec['quantity']   # Decimal — the group's summed available qty
        item_splits = split_result.get(rid)
        if not item_splits:
            continue

        # Built per-group, then validated as a whole before ever touching the
        # outer `lines`/`total_planned_cif` accumulators — see validation
        # gate below.
        item_lines: list[dict] = []
        item_planning_items: list[str] = []
        item_cif = 0.0

        preserved_for_item = existing_balances.get(rid)
        if preserved_for_item:
            # Fixed commitment already generated for this group — preservation
            # applies to the WHOLE split (PKO + Cheese together, since both
            # are always generated in the SAME Auto-Plan run), never one
            # target alone. Overriding just one side while leaving the other
            # to the engine's fresh computation would let the engine's own
            # wastage-rebalance (which has no idea a preserved balance
            # exists) inflate the non-preserved side using its OWN default
            # 40/60 assumption — silently breaking quantity conservation. A
            # target with no row of its own (shouldn't normally happen; both
            # are always created together) falls back to 0 remaining rather
            # than a fresh computed share, for the same reason.
            for planning_item in _SPLIT_TARGET_NAMES:
                preserved = preserved_for_item.get(planning_item, {
                    'remaining_quantity': Decimal('0'),
                    'remaining_cif_fc': Decimal('0'),
                    'unit_price': UNIT_PRICE.get(planning_item, Decimal('0')),
                })
                preserved_qty = _floor_qty(preserved['remaining_quantity'])
                preserved_cif = _r2(preserved['remaining_cif_fc'])
                # Still emitted at 0 remaining (e.g. fully consumed) so the
                # row — and its history — isn't silently dropped on the next
                # regenerate-and-replace.
                item_lines.append({
                    'import_item':        rid,
                    'item_name':          name_ids.get(planning_item),
                    'planned_quantity':   preserved_qty,
                    'unit_price':         _r2(preserved['unit_price']),
                    'planned_cif_fc':     preserved_cif,
                    'remaining_quantity': preserved_qty,
                    'remaining_cif_fc':   preserved_cif,
                    'note': f"Auto-planned (E132 — {planning_item}) — existing plan preserved",
                })
                item_planning_items.append(planning_item)
                item_cif += preserved_cif
        else:
            for sp in item_splits:
                planning_item = sp.get('planning_item')
                planned_qty   = sp.get('planned_quantity')
                unit_price    = sp.get('unit_price')
                planned_cif   = sp.get('planned_cif')

                # Skip lines with no quantity or no value
                if not planned_qty or float(planned_qty) <= 0:
                    continue
                if planned_cif is None:
                    continue

                fqty = _floor_qty(planned_qty)
                cif  = _r2(planned_cif)

                if fqty <= 0 or cif <= 0:
                    continue

                item_lines.append({
                    'import_item':      rid,
                    'item_name':        name_ids.get(planning_item),
                    'planned_quantity': fqty,
                    'unit_price':       _r2(unit_price) if unit_price is not None else 0.0,
                    'planned_cif_fc':   cif,
                    'note': (
                        f"Auto-planned (E132 — {planning_item or 'Unclassified'})"
                    ),
                })
                item_planning_items.append(planning_item)
                item_cif += cif

        if not item_lines:
            continue

        # ── Mandatory validation (never skip this) ────────────────────────
        # Shared across every Auto-Plan engine — see
        # `validate_group_plan_lines`'s docstring for the exact price-
        # ceiling / qty-vs-available rules and why the qty check is skipped
        # for a preserved (fixed-once-generated) split.
        if not validate_group_plan_lines(
            item_lines, item_planning_items, avail_qty, UNIT_PRICE,
            is_preserved=bool(preserved_for_item),
        ):
            logger.warning(
                "compute_e132_auto_plan: rejecting plan for group represented by "
                "import_item %s (preserved=%s) — planned_quantity=%s available=%s "
                "prices=%s max_prices=%s; likely stale/legacy LicenseItemPlan "
                "data requiring manual review.",
                rid, bool(preserved_for_item),
                [ln['planned_quantity'] for ln in item_lines], avail_qty,
                [ln['unit_price'] for ln in item_lines],
                [UNIT_PRICE.get(name) for name in item_planning_items],
            )
            continue

        lines.extend(item_lines)
        total_planned_cif += item_cif

    remaining_cif = round(balance_cif - total_planned_cif, 2)
    return lines, remaining_cif
