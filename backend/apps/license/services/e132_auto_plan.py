"""
E132 Auto-Plan service.

Delegates classification and allocation entirely to the existing, tested
e132_plan engine (classify_e132_record / plan_e132_per_item_split), then
converts the result into ready-to-save LicenseItemPlan line dicts.

Pipeline:
  1. Load import items; skip any with available_quantity < MIN_PLAN_QTY.
  2. Build a records list keyed by import_item.id, using available_quantity
     as the planning quantity — for EVERY category, including the Vegetable
     Oil PKO/Cheese split target (the split is 40%/60% of the item's CURRENT
     available quantity — see e132_plan.py's module docstring — but ONLY the
     first time it's generated; see step 4).
  3. Call plan_e132_per_item_split(records, balance_cif) — this runs the
     E132 waterfall (classify, allocate, wastage-reduction rebalance).
  4. PKO/Cheese balance tracking (business rule: once generated, a
     Vegetable Oil item's split becomes a FIXED commitment — Auto-Plan must
     never regenerate or recalculate it from the current available_quantity
     again). For any import item the engine still classifies as split-
     eligible, check for EXISTING PKO/Cheese `LicenseItemPlan` rows: if
     EITHER is found, the WHOLE split is treated as already generated and
     BOTH targets re-emit their current `remaining_quantity`/
     `remaining_cif_fc` unchanged instead of the engine's freshly
     (re)computed 40/60 split (never just one side — see
     `compute_e132_auto_plan`'s inline comment for why partial overriding
     would risk breaking quantity conservation). Only an item with NO
     existing split plan gets the engine's fresh split as its starting
     point. This is the only reason this file reads `LicenseItemPlan` —
     everything else here is a pure recompute from `available_quantity`,
     same as every other E132 category.
  5. For each (import_item, [split_lines]) map planning_item_name →
     ItemNameModel.id so the frontend can display the item-name labels.
  6. Return (lines, remaining_cif).

Real debits/allotments against a specific plan line are attributed via
`plan_line_id` in the allocate-items request (see
`views_actions.py::allocate_items`), which decrements THAT line's
`remaining_quantity`/`remaining_cif_fc` directly — never derived from the
shared import item's `available_quantity`, which cannot tell PKO and Cheese
apart. This file's job is only to make sure Auto-Plan doesn't stomp on that
independently-draining balance once it exists.

MIN_PLAN_QTY = 50 — import items with available_quantity below this
threshold are silently excluded.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Optional

from apps.license.services.e132_plan import CHEESE, PKO, PLANNING_ORDER, UNIT_PRICE, plan_e132_per_item_split

MIN_PLAN_QTY: float = 50.0

# Only these two planning items are ever "fixed once generated" — every
# other E132 category has no cross-target attribution ambiguity (a single
# item_name per import item), so it's always safe (and desired) to keep
# recomputing them fresh from available_quantity on every run.
_SPLIT_TARGET_NAMES = (PKO, CHEESE)


def _existing_split_balances(license_obj, import_item_ids: list[int]) -> dict:
    """{import_item_id: {planning_item_name: {'remaining_quantity', 'remaining_cif_fc', 'unit_price'}}}

    Read from this licence's CURRENT PKO/Cheese `LicenseItemPlan` rows —
    the live, independently-draining balances `allocate_items` maintains.
    Used ONLY to decide whether an item's split has already been generated
    (and must therefore be preserved, not recalculated) — see module
    docstring, step 4.
    """
    from apps.license.models import LicenseItemPlan

    if not import_item_ids:
        return {}

    rows = (
        LicenseItemPlan.objects
        .filter(license=license_obj, import_item_id__in=import_item_ids,
                 item_name__name__in=_SPLIT_TARGET_NAMES)
        .values("import_item_id", "item_name__name", "remaining_quantity", "remaining_cif_fc", "unit_price")
    )
    out: dict[int, dict[str, dict]] = {}
    for row in rows:
        bucket = out.setdefault(row["import_item_id"], {})
        bucket[row["item_name__name"]] = {
            "remaining_quantity": row["remaining_quantity"] or Decimal("0"),
            "remaining_cif_fc": row["remaining_cif_fc"] or Decimal("0"),
            "unit_price": row["unit_price"] or Decimal("0"),
        }
    return out


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

    # ── Load import items ─────────────────────────────────────────────────────
    import_items = (
        license_obj.import_license.all()
        .select_related('hs_code')
        .order_by('serial_number')
    )

    _live_balance_cif = license_obj.get_balance_cif
    balance_cif = float(
        _live_balance_cif if _live_balance_cif is not None else (license_obj.balance_cif or 0)
    )

    # ── Build records for the E132 classifier ────────────────────────────────
    # Use available_quantity (not the original import quantity) as the
    # planning qty for EVERY category — including the Vegetable Oil 40/60
    # split target.
    records: list[dict] = []
    item_map: dict[int, object] = {}   # id → import item object (for note)

    for ii in import_items:
        avail = float(ii.available_quantity or 0)
        if avail < MIN_PLAN_QTY:
            continue   # below global minimum — skip silently
        hs   = ii.hs_code.hs_code if ii.hs_code else None
        desc = ii.description or None
        records.append({
            'record_id':   ii.id,
            'hs_code':     hs,
            'description': desc,
            'quantity':    Decimal(str(avail)),   # planning qty = available qty
        })
        item_map[ii.id] = ii

    if not records:
        return [], balance_cif

    # ── Call the E132 waterfall ───────────────────────────────────────────────
    # plan_e132_per_item_split returns:
    #   {record_id: [ {planning_item, reason, planned_quantity,
    #                  unit_price, planned_cif}, ... ]}
    split_result = plan_e132_per_item_split(records, balance_cif)

    # ── PKO/Cheese balance preservation (module docstring, step 4) ───────────
    # Only import items the engine STILL classifies as split-eligible (same
    # HSN/description match today) are candidates — this never revives a
    # stale balance for an item that's since been reclassified.
    existing_balances = _existing_split_balances(license_obj, [r['record_id'] for r in records])

    # ── Convert to plan line dicts ────────────────────────────────────────────
    lines: list[dict] = []
    total_planned_cif = 0.0

    for rec in records:
        rid = rec['record_id']
        item_splits = split_result.get(rid)
        if not item_splits:
            continue

        preserved_for_item = existing_balances.get(rid)
        if preserved_for_item:
            # Fixed commitment already generated for this item — preservation
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
                lines.append({
                    'import_item':        rid,
                    'item_name':          name_ids.get(planning_item),
                    'planned_quantity':   preserved_qty,
                    'unit_price':         _r2(preserved['unit_price']),
                    'planned_cif_fc':     preserved_cif,
                    'remaining_quantity': preserved_qty,
                    'remaining_cif_fc':   preserved_cif,
                    'note': f"Auto-planned (E132 — {planning_item}) — existing plan preserved",
                })
                total_planned_cif += preserved_cif
            continue

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

            lines.append({
                'import_item':      rid,
                'item_name':        name_ids.get(planning_item),
                'planned_quantity': fqty,
                'unit_price':       _r2(unit_price) if unit_price is not None else 0.0,
                'planned_cif_fc':   cif,
                'note': (
                    f"Auto-planned (E132 — {planning_item or 'Unclassified'})"
                ),
            })
            total_planned_cif += cif

    remaining_cif = round(balance_cif - total_planned_cif, 2)
    return lines, remaining_cif
