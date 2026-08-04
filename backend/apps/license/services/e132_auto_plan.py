"""
E132 Auto-Plan service.

Delegates classification and allocation entirely to the existing, tested
e132_plan engine (classify_e132_record / plan_e132_per_item_split), then
converts the result into ready-to-save LicenseItemPlan line dicts.

Pipeline:
  1. Load import items; skip any with available_quantity < MIN_PLAN_QTY.
  2. Build a records list keyed by import_item.id, using available_quantity
     as the planning quantity (not the original import quantity) — except
     the Vegetable Oil 40/60 split target, which is always based on the
     import item's ORIGINAL `quantity` (Rule 8; see `original_quantity`).
  3. Read this licence's existing `LicenseItemPlan` rows for PKO/Cheese so
     the split can be adjusted for what's already been planned (Rule 8) —
     this is the ONLY reason this file touches the database beyond loading
     the licence itself; `e132_plan.py` stays a pure function.
  4. Call plan_e132_per_item_split(records, balance_cif,
     existing_split_allocations=...) — this runs the E132 waterfall.
  5. Reconcile split lines: the engine returns the Rule-8 SHORTFALL (how
     much MORE is needed to reach the 40/60 target); this file adds back
     what was already planned so the line written to the licence is the
     cumulative target-so-far. `save_plan_lines_for_license` full-replaces
     every plan row for the licence on every run (same as every other E132
     category), so this reconciliation is what makes re-running Auto-Plan a
     stable fixed point instead of drifting or zeroing out — see the
     class-level note on `compute_e132_auto_plan` for the worked example.
  6. For each (import_item, [split_lines]) map planning_item_name →
     ItemNameModel.id so the frontend can display the item-name labels.
  7. Return (lines, remaining_cif).

MIN_PLAN_QTY = 50 — import items with available_quantity below this
threshold are silently excluded.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Optional

from apps.license.services.e132_plan import (
    CHEESE,
    PKO,
    PLANNING_ORDER,
    UNIT_PRICE,
    plan_e132_per_item_split,
)

MIN_PLAN_QTY: float = 50.0

# Only these two planning items ever carry a Rule-8 "already planned"
# adjustment (the Vegetable Oil 40/60 split) — every other E132 category is
# always recomputed fresh from `available_quantity` each run, same as today.
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


def _existing_split_allocations(license_obj, import_item_ids: list[int]) -> dict:
    """{import_item_id: {PKO: already_planned_qty, CHEESE: already_planned_qty}}

    Read from this licence's CURRENT `LicenseItemPlan` rows (i.e. whatever
    the previous Auto-Plan run — or a manual edit — left behind), BEFORE
    this run's `save_plan_lines_for_license` full-replace deletes them.
    `LicenseItemPlan` is the only model with item-name-level granularity in
    this schema (`AllotmentItems`, the real debit record, has no item_name
    field at all), so it's the only possible source for "already planned
    per target item".
    """
    from django.db.models import Sum
    from apps.license.models import LicenseItemPlan

    if not import_item_ids:
        return {}

    rows = (
        LicenseItemPlan.objects
        .filter(license=license_obj, import_item_id__in=import_item_ids,
                 item_name__name__in=_SPLIT_TARGET_NAMES)
        .values("import_item_id", "item_name__name")
        .annotate(total=Sum("planned_quantity"))
    )
    out: dict[int, dict[str, Decimal]] = {}
    for row in rows:
        bucket = out.setdefault(row["import_item_id"], {})
        bucket[row["item_name__name"]] = row["total"] or Decimal("0")
    return out


def compute_e132_auto_plan(license_obj) -> tuple[list[dict], float]:
    """
    Run the E132 Auto Plan for *license_obj*.

    Returns (lines, remaining_cif):
      lines        — ready-to-save plan line dicts.
      remaining_cif — balance CIF not consumed by the plan (wastage).

    Worked example for the Rule-8 reconciliation (step 5 above): a 100kg
    Vegetable Oil item's target is PKO=40kg/Cheese=60kg. If a prior run
    already planned PKO=30kg, this run's engine call returns a shortfall of
    PKO=10kg (Cheese=60kg, untouched). This file adds the already-planned
    30kg back, so the line actually written is PKO=40kg (the achieved
    target) — not 10kg (which would silently shrink the licence's plan to
    only what changed this run) and not 70kg split 28/42 (naively
    re-splitting the shortfall by the 40/60 ratio, which the business rules
    explicitly reject). Re-running again with nothing else changed reads
    back already_planned=40/60, shortfall=0/0, and reconciles to the same
    40/60 — a stable fixed point, never drifting or over-allocating.
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
    # Use available_quantity (not the original import quantity) so the plan
    # reflects what can still be allotted / debited — except for the
    # Vegetable Oil split target, which Rule 8 defines against the item's
    # ORIGINAL `quantity` (see `original_quantity` below).
    records: list[dict] = []
    item_map: dict[int, object] = {}   # id → import item object (for note)

    for ii in import_items:
        avail = float(ii.available_quantity or 0)
        if avail < MIN_PLAN_QTY:
            continue   # below global minimum — skip silently
        hs   = ii.hs_code.hs_code if ii.hs_code else None
        desc = ii.description or None
        records.append({
            'record_id':         ii.id,
            'hs_code':           hs,
            'description':       desc,
            'quantity':          Decimal(str(avail)),          # planning qty = available qty
            'original_quantity': Decimal(str(ii.quantity or 0)),  # Rule 8 split-target basis
        })
        item_map[ii.id] = ii

    if not records:
        return [], balance_cif

    existing_split_allocations = _existing_split_allocations(
        license_obj, [r['record_id'] for r in records],
    )

    # ── Call the E132 waterfall ───────────────────────────────────────────────
    # plan_e132_per_item_split returns:
    #   {record_id: [ {planning_item, reason, planned_quantity,
    #                  unit_price, planned_cif,
    #                  already_planned_quantity (split lines only)}, ... ]}
    split_result = plan_e132_per_item_split(records, balance_cif, existing_split_allocations)

    # ── Convert to plan line dicts ────────────────────────────────────────────
    lines: list[dict] = []
    total_planned_cif = 0.0

    for rec in records:
        rid = rec['record_id']
        item_splits = split_result.get(rid)
        if not item_splits:
            continue
        for sp in item_splits:
            planning_item = sp.get('planning_item')
            planned_qty   = sp.get('planned_quantity')
            unit_price    = sp.get('unit_price')
            planned_cif   = sp.get('planned_cif')

            # Rule 8 reconciliation (split lines only — see module docstring
            # and this function's worked example): the engine returns the
            # NEW shortfall; add back what was already planned so the row we
            # write is the cumulative target-so-far, not just this round's
            # delta. Non-split lines have no `already_planned_quantity` key,
            # so `already` is 0 and this is a no-op for them.
            already = sp.get('already_planned_quantity') or 0
            if already:
                planned_qty = (planned_qty or 0) + already
                # The engine's rate reflects only the shortfall portion (and
                # is None when the shortfall was 0 — nothing new competed for
                # balance this round). Re-price the full cumulative quantity:
                # prefer the engine's own effective rate when it computed
                # one, else fall back to the item's fixed ceiling price.
                unit_price = unit_price if unit_price is not None else UNIT_PRICE.get(planning_item)
                planned_cif = (float(planned_qty) * float(unit_price)) if unit_price is not None else None

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
