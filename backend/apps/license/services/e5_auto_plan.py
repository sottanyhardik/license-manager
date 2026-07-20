"""
E5 Auto-Plan service — 3-rule waterfall with special milk-priority validation.

Processing sequence — Normal Flow:
  Rule 1  Dietary Fibre         @ $3.00   (classify_e5_item → DIETARY FIBRE)
  ─── Special Validation ───────────────────────────────────────────────────────
  Rule 2  Edible Oils (waterfall)
            Case 2.1  Palm Kernel Oil  @ $2.30  (HSN 1513 or desc "Vegetable Oil")
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

MIN_PLAN_QTY: float = 50.0

# E5 item-name labels stored in ItemNameModel
E5_RULE_NAMES: tuple[str, ...] = (
    'Dietary Fibre - E5',
    'PALM KERNEL OIL - E5',
    'RBD PALMOLEIN OIL - E5',
    'OLIVE OIL - E5',
    'SWP - E5',
    'DWP - E5',
    'WPC - E5',
    'Wheat Flour - E5',   # final mop-up — absorbs all remaining balance CIF
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


# ─── Milk-split algorithm (E5 variant) ───────────────────────────────────────

def _milk_splits_e5(
    avail_qty: float,
    remaining_cif: float,
    name_ids: dict[str, Optional[int]],
) -> list[dict]:
    """
    Rule 3: avg-price-based milk split with E5 item names.
    Identical split arithmetic to E1; only item-name labels differ (-E5 suffix).
    """
    if avail_qty <= 0 or remaining_cif <= 0:
        return []

    avg = remaining_cif / avail_qty

    # Case 3.1 — avg < 1.50: single SWP-E5 @ 1.50
    if avg < 1.50:
        qty = _floor_qty(remaining_cif / 1.50)
        return [{
            'item_name_id':    name_ids.get('SWP - E5'),
            'item_name_label': 'SWP - E5',
            'planned_quantity': qty,
            'unit_price':      1.50,
            'planned_cif_fc':  _r2(qty * 1.50),
        }]

    # Case 3.2 — 1.50 ≤ avg < 5.00: SWP-E5 @ 1.50 + DWP-E5 @ 5.00
    if avg < 5.00:
        fqty2 = _floor_qty(max(0.0, (remaining_cif - avail_qty * 1.50) / (5.00 - 1.50)))
        fqty1 = _floor_qty(avail_qty - fqty2)
        lines = []
        if fqty1 > 0:
            lines.append({
                'item_name_id':    name_ids.get('SWP - E5'),
                'item_name_label': 'SWP - E5',
                'planned_quantity': fqty1,
                'unit_price':      1.50,
                'planned_cif_fc':  _r2(fqty1 * 1.50),
            })
        if fqty2 > 0:
            lines.append({
                'item_name_id':    name_ids.get('DWP - E5'),
                'item_name_label': 'DWP - E5',
                'planned_quantity': fqty2,
                'unit_price':      5.00,
                'planned_cif_fc':  _r2(fqty2 * 5.00),
            })
        return lines

    # Case 3.3 — 5.00 ≤ avg < 20.00: DWP-E5 @ 5.00 + WPC-E5 @ 20.00
    if avg < 20.00:
        fqty2 = _floor_qty(max(0.0, (remaining_cif - avail_qty * 5.00) / (20.00 - 5.00)))
        fqty1 = _floor_qty(avail_qty - fqty2)
        lines = []
        if fqty1 > 0:
            lines.append({
                'item_name_id':    name_ids.get('DWP - E5'),
                'item_name_label': 'DWP - E5',
                'planned_quantity': fqty1,
                'unit_price':      5.00,
                'planned_cif_fc':  _r2(fqty1 * 5.00),
            })
        if fqty2 > 0:
            lines.append({
                'item_name_id':    name_ids.get('WPC - E5'),
                'item_name_label': 'WPC - E5',
                'planned_quantity': fqty2,
                'unit_price':      20.00,
                'planned_cif_fc':  _r2(fqty2 * 20.00),
            })
        return lines

    # Cases 3.4/3.5 — avg ≥ 20.00: WPC-E5, full qty + full remaining CIF
    return [{
        'item_name_id':    name_ids.get('WPC - E5'),
        'item_name_label': 'WPC - E5',
        'planned_quantity': _floor_qty(avail_qty),
        'unit_price':      _r2(avg),
        'planned_cif_fc':  _r2(remaining_cif),
    }]


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
    from apps.core.models import ItemNameModel
    from apps.license.services.e5_plan import classify_e5_item

    # ── Pre-fetch item-name IDs ───────────────────────────────────────────────
    name_ids: dict[str, Optional[int]] = {n: None for n in E5_RULE_NAMES}
    for obj in ItemNameModel.objects.filter(name__in=E5_RULE_NAMES):
        name_ids[obj.name] = obj.id

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
    palm_kernel:   list = []   # Case 2.1 — PKO  @ $2.30
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
        # Case 2.3: Olive oil — not covered under HSN 1513 or 1511
        elif cat == 'OLIVE OIL' or (
            'oil' in desc_l
            and not hs_l.startswith('1513')
            and not hs_l.startswith('1511')
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
    for ii in dietary_fibre:
        if remaining_cif <= 0:
            break
        avail = float(ii.available_quantity or 0)
        if avail < MIN_PLAN_QTY:
            continue
        line, remaining_cif = _simple_line_e5(
            ii, avail, remaining_cif, 3.00,
            name_ids.get('Dietary Fibre - E5'),
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
        """Inner helper: execute edible-oil rules against current remaining_cif."""
        nonlocal remaining_cif

        # Case 2.1: Palm Kernel Oil @ $2.30
        for ii in palm_kernel:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                ii, avail, remaining_cif, 2.30,
                name_ids.get('PALM KERNEL OIL - E5'),
                'Rule 2.1 – Palm Kernel Oil',
            )
            if line:
                lines.append(line)

        # Case 2.2: RBD Palmolein Oil @ $1.20
        for ii in rbd:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                ii, avail, remaining_cif, 1.20,
                name_ids.get('RBD PALMOLEIN OIL - E5'),
                'Rule 2.2 – RBD Palmolein',
            )
            if line:
                lines.append(line)

        # Case 2.3: Olive Oil @ $5.00
        for ii in olive_oil:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                ii, avail, remaining_cif, 5.00,
                name_ids.get('OLIVE OIL - E5'),
                'Rule 2.3 – Olive Oil',
            )
            if line:
                lines.append(line)

    if special_milk_triggered:
        # Special flow: milk CIF priority.
        # Planned Qty = FLOOR(remaining_cif ÷ 1.50); CIF = planned_qty × 1.50.
        # Only the first milk import item absorbs all remaining CIF;
        # subsequent items see remaining_cif ≈ 0 and produce no line.
        for ii in milk:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line_e5(
                ii, avail, remaining_cif, 1.50,
                name_ids.get('SWP - E5'),
                'Rule Special – Milk priority SWP-E5',
            )
            if line:
                lines.append(line)
        _plan_oils()
        # Rule 3 (normal milk) is SKIPPED — milk already planned above.

    else:
        # Normal flow: oils first, then milk splits
        _plan_oils()

        # ── Rule 3: Milk & Milk — avg-price split ────────────────────────────
        for ii in milk:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            splits = _milk_splits_e5(avail, remaining_cif, name_ids)
            for sp in splits:
                lines.append({
                    'import_item':      ii.id,
                    'item_name':        sp['item_name_id'],
                    'planned_quantity': sp['planned_quantity'],
                    'unit_price':       sp['unit_price'],
                    'planned_cif_fc':   sp['planned_cif_fc'],
                    'note':             f"Auto-planned (E5 Rule 3 — {sp['item_name_label']})",
                })
                remaining_cif = _r2(remaining_cif - sp['planned_cif_fc'])

    # ── Final mop-up: Wheat Flour absorbs ALL remaining balance CIF ─────────
    # Unit price is dynamic: remaining_cif ÷ total plannable wheat-flour qty,
    # so the entire remaining balance is consumed in one pass.
    if remaining_cif > 0 and wheat_flour:
        wf_plannable_qty = sum(
            float(ii.available_quantity or 0)
            for ii in wheat_flour
            if float(ii.available_quantity or 0) >= MIN_PLAN_QTY
        )
        if wf_plannable_qty > 0:
            wf_unit_price = _r2(remaining_cif / wf_plannable_qty)
            for ii in wheat_flour:
                if remaining_cif <= 0:
                    break
                avail = float(ii.available_quantity or 0)
                if avail < MIN_PLAN_QTY:
                    continue
                line, remaining_cif = _simple_line_e5(
                    ii, avail, remaining_cif, wf_unit_price,
                    name_ids.get('Wheat Flour - E5'),
                    'Final – Wheat Flour mop-up',
                )
                if line:
                    lines.append(line)

    return lines, remaining_cif
