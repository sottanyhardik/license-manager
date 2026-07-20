"""
E132 Auto-Plan service.

Delegates classification and allocation entirely to the existing, tested
e132_plan engine (classify_e132_record / plan_e132_per_item_split), then
converts the result into ready-to-save LicenseItemPlan line dicts.

Pipeline:
  1. Load import items; skip any with available_quantity < MIN_PLAN_QTY.
  2. Build a records list keyed by import_item.id, using available_quantity
     as the planning quantity (not the original import quantity).
  3. Call plan_e132_per_item_split(records, balance_cif) — this runs the
     E132 waterfall with the wastage-reduction promotion baked in.
  4. For each (import_item, [split_lines]) map planning_item_name →
     ItemNameModel.id so the frontend can display the item-name labels.
  5. Return (lines, remaining_cif).

MIN_PLAN_QTY = 50 — import items with available_quantity below this
threshold are silently excluded.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Optional

from apps.license.services.e132_plan import (
    PLANNING_ORDER,
    plan_e132_per_item_split,
)

MIN_PLAN_QTY: float = 50.0


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

    balance_cif = float(
        license_obj.get_balance_cif or license_obj.balance_cif or 0
    )

    # ── Build records for the E132 classifier ────────────────────────────────
    # Use available_quantity (not the original import quantity) so the plan
    # reflects what can still be allotted / debited.
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
