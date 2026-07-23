"""
E5 Auto-Plan service — 3-rule waterfall with special milk-priority validation.

Processing sequence — Normal Flow:
  Rule 1  Dietary Fibre         @ $3.00   (classify_e5_item → DIETARY FIBRE)
  ─── Special Validation ───────────────────────────────────────────────────────
  Rule 2  Edible Oils (waterfall)
            Case 2.1  Palm Kernel Oil  @ $1.80  (HSN 1513 or desc "Vegetable Oil")
            Case 2.2  RBD Palmolein   @ $1.20  (HSN 15119020 / RBD category)
            Case 2.3  Olive Oil        @ $5.00  (all other oils)
  Rule 3  Milk & Milk avg-price split
            avg < 1.50            → SWP-E5 @ 1.50
            1.50 ≤ avg < 5.00     → SWP-E5 @ 1.50 + DWP-E5 @ 5.00
            5.00 ≤ avg < 20.00    → DWP-E5 @ 5.00 + WPC-E5 @ 20.00
            avg ≥ 20.00           → WPC-E5 (full qty + full remaining CIF)

Special Validation (executed AFTER Rule 1):
  If remaining_cif < (milk_total_qty × 1.50):
    → Plan ALL milk @ $1.50 as SWP-E5 FIRST
    → Then execute Rule 2 (Edible Oils) with whatever CIF remains
    → SKIP the normal Rule 3 (milk already planned)

Minimum plannable qty: MIN_PLAN_QTY = 50 (shared constant)
Quantities: FLOOR to 0 decimal places.
"""
from __future__ import annotations

import math
from typing import Optional

from apps.license.services.auto_plan_shared import (
    ensure_plan_item_names as _ensure_names,
    group_by_desc as _group_by_desc,
    optimal_milk_split as _optimal_milk_split,
)

MIN_PLAN_QTY: float = 50.0

# Each entry: (item_name, norm_code).  ensure_plan_item_names creates any
# missing rows so Auto Plan never fails because a name is absent from the DB.
_RULE_NAMES_E5: tuple[tuple[str, str], ...] = (
    ('DIETARY FIBRE - E5',    'E5'),
    ('PALM KERNEL OIL - E5',  'E5'),
    ('RBD PALMOLEIN OIL - E5','E5'),
    ('OLIVE OIL - E5',        'E5'),
    ('SWP - E5',              'E5'),
    ('DWP - E5',              'E5'),
    ('WPC - E5',              'E5'),
    ('ALUMINIUM FOIL - E5',   'E5'),   # ensured per §2 (no E5 detection rule yet)
    ('WHEAT FLOUR - E5',      'E5'),   # final mop-up
)

# Keywords that identify milk/dairy import items (lowercase).
_MILK_KW = frozenset({
    'swp', 'dwp', 'wpc', 'whey', 'milk', 'skimmed', 'lactose',
    'casein', 'permeate', 'butter', 'cream',
})


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _r2(x: float) -> float:
    return round(x, 2)


def _floor_qty(x: float) -> float:
    """Floor to whole-number quantity."""
    return float(math.floor(x))


def _is_milk_group(item_name_list: list[str], e5_cat: Optional[str]) -> bool:
    """True when this import item is a milk/dairy product under E5."""
    if e5_cat == 'SWP':   # E5 SWP category covers milk-protein products (HSN 0404)
        return True
    for name in item_name_list:
        if any(kw in name.lower() for kw in _MILK_KW):
            return True
    return False



def _simple_line_e5(
    ii,
    avail: float,
    remaining_cif: float,
    unit_price: float,
    item_name_id: Optional[int],
    rule_label: str,
) -> tuple[Optional[dict], float]:
    """
    Build one fixed-price plan line.

    Steps:
      1. Cap raw CIF at min(avail × rate, remaining_cif).
      2. Floor the quantity: planned_qty = FLOOR(raw_cif ÷ rate).
      3. Recalculate CIF from the floored qty: planned_cif = planned_qty × rate.
         Ensures planned_cif = planned_qty × unit_price exactly.
         Example: FLOOR(28326.80 ÷ 1.50) = 18884 → CIF = 18884 × 1.50 = 28326.00
      4. Return None when planned_qty is 0 (callers must guard with `if line:`).

    Returns (line_dict | None, new_remaining_cif).
    """
    if unit_price <= 0:
        return None, remaining_cif                        # guard: zero rate → skip
    raw_cif     = min(avail * unit_price, remaining_cif)
    planned_qty = _floor_qty(raw_cif / unit_price)
    planned_cif = _r2(planned_qty * unit_price)          # re-derive from floored qty
    if planned_qty <= 0 or planned_cif <= 0:
        return None, remaining_cif                        # nothing plannable
    line = {
        'import_item':      ii.id,
        'item_name':        item_name_id,
        'planned_quantity': planned_qty,
        'unit_price':       unit_price,
        'planned_cif_fc':   planned_cif,
        'note':             f'Auto-planned (E5 {rule_label})',
    }
    return line, _r2(remaining_cif - planned_cif)


# ─── Main entry point ──────────────────────────────────────────────────────────

def compute_e5_auto_plan(license_obj) -> tuple[list[dict], float]:
    """
    Run the full E5 Auto Plan waterfall.

    Normal flow:
      1 → Dietary Fibre  2 → Edible Oils  3 → Milk & Milk

    Special flow (triggered when remaining CIF after Rule 1 is less than
    milk_total_qty × $1.50):
      1 → Dietary Fibre  2 → Milk (full qty @ $1.50 as SWP-E5)
      3 → Edible Oils    [Rule 3 skipped]

    Returns (lines, remaining_cif).
    """
    from apps.license.services.e5_plan import classify_e5_item

    # ── Get-or-create all planned item names (§2: never fail on missing) ────
    name_ids = _ensure_names(list(_RULE_NAMES_E5))

    # ── Load import items ─────────────────────────────────────────────────────
    import_items = (
        license_obj.import_license.all()
        .select_related('hs_code')
        .prefetch_related('items')
        .order_by('serial_number')
    )

    balance_cif   = float(license_obj.get_balance_cif or license_obj.balance_cif or 0)
    remaining_cif = balance_cif

    # ── Bucket import items (hierarchical: first-match wins) ──────────────────
    dietary_fibre: list = []
    milk:          list = []
    palm_kernel:   list = []   # Case 2.1 — PKO  @ $1.80
    rbd:           list = []   # Case 2.2 — RBD  @ $1.20
    olive_oil:     list = []   # Case 2.3 — Olive @ $5.00
    wheat_flour:   list = []   # Final mop-up — dynamic rate, absorbs all remaining CIF

    for ii in import_items:
        item_names = [n.name for n in ii.items.all()]
        key        = ', '.join(sorted(item_names)) if item_names else (ii.description or '-')
        hs         = (ii.hs_code.hs_code if ii.hs_code else '') or ''
        desc       = (ii.description or '')
        hs_l       = hs.lower().replace(' ', '').replace('-', '')
        desc_l     = desc.lower()
        cat        = classify_e5_item(key, hs, desc)

        if cat == 'DIETARY FIBRE':
            dietary_fibre.append(ii)
        elif _is_milk_group(item_names, cat):
            milk.append(ii)
        # Case 2.1: HSN starts with 1513 OR description contains "Vegetable Oil"
        elif hs_l.startswith('1513') or 'vegetable oil' in desc_l or cat == 'PKO':
            palm_kernel.append(ii)
        # Case 2.2: HSN 15119020 (RBD Palmolein) — only if Case 2.1 not applicable
        elif hs_l.startswith('15119') or cat == 'RBD':
            rbd.append(ii)
        # Case 2.3: Olive oil — edible-oil items NOT covered by palm kernel (1513)
        # or RBD (1511). Use HSN chapter 15 (fats/oils) or explicit phrases;
        # DO NOT use bare 'oil' substring — 'aluminium foil' contains 'oil' and
        # would wrongly match packing materials with HSN 39xx.
        elif cat == 'OLIVE OIL' or (
            (
                hs_l.startswith('15')               # HSN chapter 15 = fats & oils
                and not hs_l.startswith('1513')     # already in palm_kernel
                and not hs_l.startswith('1511')     # already in rbd
            ) or (
                ('vegetable oil' in desc_l or 'edible oil' in desc_l)
                and not hs_l.startswith('1513')
                and not hs_l.startswith('1511')
            )
        ):
            olive_oil.append(ii)
        elif cat == 'WHEAT FLOUR':
            wheat_flour.append(ii)
        # else: unclassified — left unplanned

    # Total milk quantity (needed for special validation)
    milk_total_qty = sum(float(ii.available_quantity or 0) for ii in milk)
    min_milk_cif   = _r2(milk_total_qty * 1.50)

    lines: list[dict] = []

    # ── Rule 1: Dietary Fibre @ $3.00 ────────────────────────────────────────
    # One plan line PER DESCRIPTION GROUP, saved on the group's lowest-serial
    # representative — matching the Plan Tab anchor so the group shows Planned.
    for rep, group_avail in _group_by_desc(dietary_fibre):
        if remaining_cif <= 0:
            break
        if group_avail < MIN_PLAN_QTY:
            continue
        line, remaining_cif = _simple_line_e5(
            rep, group_avail, remaining_cif, 3.00,
            name_ids.get('DIETARY FIBRE - E5'),
            'Rule 1 – Dietary Fibre',
        )
        if line:
            lines.append(line)

    # ── Special Validation ────────────────────────────────────────────────────
    # If remaining CIF is less than what milk needs @ $1.50/unit,
    # milk gets priority BEFORE Edible Oils.
    special_milk_triggered = (
        milk_total_qty > 0
        and remaining_cif < min_milk_cif
        and remaining_cif > 0
    )

    def _plan_oils():
        """Inner helper: execute edible-oil rules (group-based) against remaining_cif."""
        nonlocal remaining_cif

        # Case 2.1: Palm Kernel Oil @ $1.80
        for rep, group_avail in _group_by_desc(palm_kernel):
            if remaining_cif <= 0:
                break
            if group_avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                rep, group_avail, remaining_cif, 1.80,
                name_ids.get('PALM KERNEL OIL - E5'),
                'Rule 2.1 – Palm Kernel Oil',
            )
            if line:
                lines.append(line)

        # Case 2.2: RBD Palmolein Oil @ $1.20
        for rep, group_avail in _group_by_desc(rbd):
            if remaining_cif <= 0:
                break
            if group_avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                rep, group_avail, remaining_cif, 1.20,
                name_ids.get('RBD PALMOLEIN OIL - E5'),
                'Rule 2.2 – RBD Palmolein',
            )
            if line:
                lines.append(line)

        # Case 2.3: Olive Oil @ $5.00
        for rep, group_avail in _group_by_desc(olive_oil):
            if remaining_cif <= 0:
                break
            if group_avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                rep, group_avail, remaining_cif, 5.00,
                name_ids.get('OLIVE OIL - E5'),
                'Rule 2.3 – Olive Oil',
            )
            if line:
                lines.append(line)

    # ── Group milk items by description ──────────────────────────────────────
    # Import items for the same product (e.g. "Milk & Milk Products") appear on
    # multiple serial numbers. Plan each description-group as ONE unit so the
    # optimizer sees the full available quantity and produces the best split.
    # The plan lines are all assigned to the group's representative import item
    # (lowest serial number), matching how PlanTab groups them in the UI.
    from collections import defaultdict as _dd
    milk_by_desc: dict = _dd(list)
    for ii in milk:
        key = (ii.description or '').strip().upper()
        milk_by_desc[key].append(ii)

    def _plan_milk_groups(use_optimal: bool) -> None:
        """
        Plan all milk description-groups.

        use_optimal=True  → full SWP→DWP→WPC greedy optimization (Rule 3).
        use_optimal=False → all qty as SWP @ $1.50 (special validation path).
        """
        nonlocal remaining_cif
        for _desc, group in milk_by_desc.items():
            if remaining_cif <= 0:
                break
            group_qty = sum(float(ii.available_quantity or 0) for ii in group)
            if group_qty < MIN_PLAN_QTY:
                continue
            # Representative = lowest serial number in the group
            rep = min(group, key=lambda x: x.serial_number)

            if use_optimal:
                q_swp, q_dwp, q_wpc = _optimal_milk_split(group_qty, remaining_cif)
                prod_rows = [
                    ('SWP - E5', q_swp, 1.50, 'Rule 3'),
                    ('DWP - E5', q_dwp, 5.00, 'Rule 3'),
                    ('WPC - E5', q_wpc, 20.00, 'Rule 3'),
                ]
            else:
                # Special validation: all qty @ $1.50 as SWP-E5
                q_swp = int(math.floor(
                    min(remaining_cif, group_qty * 1.50) / 1.50
                ))
                prod_rows = [('SWP - E5', q_swp, 1.50, 'Rule Special')]

            for prod, qty, price, rule_label in prod_rows:
                if qty <= 0 or remaining_cif <= 0:
                    continue
                cif = _r2(qty * price)
                if cif <= 0:
                    continue
                lines.append({
                    'import_item':      rep.id,
                    'item_name':        name_ids.get(prod),
                    'planned_quantity': float(qty),
                    'unit_price':       price,
                    'planned_cif_fc':   cif,
                    'note': f'Auto-planned (E5 {rule_label} — {prod})',
                })
                remaining_cif = _r2(remaining_cif - cif)

    if special_milk_triggered:
        # Special flow: milk CIF priority — all milk @ $1.50 (SWP-E5) first.
        _plan_milk_groups(use_optimal=False)
        _plan_oils()
        # Rule 3 (normal milk optimization) is SKIPPED — already planned above.

    else:
        # Normal flow: oils first, then full milk optimization.
        _plan_oils()
        # ── Rule 3: Milk & Milk — greedy SWP→DWP→WPC optimizer ──────────────
        _plan_milk_groups(use_optimal=True)

    # ── Final mop-up: Wheat Flour absorbs ALL remaining balance CIF ─────────
    # Group-based: one plan line per description group, on the lowest-serial
    # representative. Dynamic unit price = remaining_cif ÷ total group qty.
    if remaining_cif > 0 and wheat_flour:
        wf_groups = _group_by_desc(wheat_flour)
        wf_plannable_qty = sum(ga for _, ga in wf_groups if ga >= MIN_PLAN_QTY)
        if wf_plannable_qty > 0:
            wf_unit_price = _r2(remaining_cif / wf_plannable_qty)
            if wf_unit_price <= 0:
                wf_plannable_qty = 0  # rate rounds to $0 → skip to avoid division-by-zero
            for rep, group_avail in wf_groups:
                if remaining_cif <= 0:
                    break
                if group_avail < MIN_PLAN_QTY:
                    continue
                line, remaining_cif = _simple_line_e5(
                    rep, group_avail, remaining_cif, wf_unit_price,
                    name_ids.get('WHEAT FLOUR - E5'),
                    'Final – Wheat Flour mop-up',
                )
                if line:
                    lines.append(line)

    return lines, remaining_cif
