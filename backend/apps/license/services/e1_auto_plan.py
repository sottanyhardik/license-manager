"""
E1 Auto-Plan service — 6-rule waterfall.

Processing sequence (each rule draws down the shared balance):

  Rule 1 — OTHER CONFECTIONERY INGREDIENTS
    unit_price = 3.0  ·  one line per matching import item.

  Rule 2 — MILK & MILK (SWP / DWP / WPC / Skimmed Milk / Whey)
    Avg Price = remaining CIF ÷ available qty, then:
    Case 2.1  avg < 1.50       → SWP-E1 @ 1.50 (qty = FLOOR(CIF ÷ 1.50))
    Case 2.2  1.50 ≤ avg < 5   → SWP @ 1.50 + DWP @ 5.00 (2 lines)
    Case 2.3  5 ≤ avg < 20     → DWP @ 5.00 + WPC @ 20.00 (2 lines)
    Case 2.4/5 avg ≥ 20        → WPC, full qty + full remaining CIF

  Rule 3 — JUICE  (skipped when ANY milk item is present on the licence)
    Ignores items whose description contains "Actual User".
    item_name = "Juice - E1"  ·  unit_price = 2.50

  Rule 4 — ALUMINIUM FOIL  (HSN starts with "7607" OR desc contains "7607")
    item_name = "Aluminium Foil"  ·  unit_price = 4.50

  Rule 5 — CITRIC / TARTARIC ACID  (desc contains "citric" or "tartaric")
    item_name = "Citric / Tartaric"  ·  unit_price = 1.60

  Rule 6 — PLASTIC PACKING MATERIAL  (HSN starts with "390", min qty 100 KG)
    Only applied when Rule 4 generated NO lines.
    item_name = "Plastic Packing Material"  ·  unit_price = 1.00

Each import item matches the FIRST rule whose condition it satisfies (hierarchical
priority mirrors the processing sequence). Balance CIF is drawn down after every
line so no rule ever overruns the licence balance.
"""
from __future__ import annotations

import math
from typing import Optional


# ─── Item-name labels looked up from ItemNameModel ────────────────────────────

MILK_ITEM_NAMES: tuple[str, ...] = ('SWP - E1', 'DWP - E1', 'WPC - E1')

_ALL_RULE_NAMES: tuple[str, ...] = MILK_ITEM_NAMES + (
    'Other Confectionery Ingredients - E1',
    'Fruit Juice - E1',
    'Aluminium Foil',
    'CITRIC ACID / TARTARIC ACID - E1',
    'Plastic Packing Material',
)

# Minimum available quantity required before an import item is planned.
# Items below this threshold are silently skipped by every rule.
MIN_PLAN_QTY: float = 50.0

# Keywords that flag an import-item group as milk/dairy (lowercase).
_MILK_KW = frozenset({
    'swp', 'dwp', 'wpc', 'whey', 'milk', 'skimmed', 'lactose',
    'casein', 'permeate', 'butter', 'cream',
})


# ─── Pure helpers ─────────────────────────────────────────────────────────────

def _r2(x: float) -> float:
    return round(x, 2)


def _floor_qty(x: float) -> float:
    """Floor to whole number (0 decimal places) — quantities always round down."""
    return float(math.floor(x))


def _is_milk_group(item_name_list: list[str], e1_cat: Optional[str]) -> bool:
    if e1_cat == 'WPC':
        return True
    for name in item_name_list:
        if any(kw in name.lower() for kw in _MILK_KW):
            return True
    return False


# ─── Rule 2 helper ────────────────────────────────────────────────────────────

def _optimal_milk_split(total_qty: int, remaining_cif: float) -> tuple[int, int, int]:
    """
    Greedy optimization: maximize CIF utilization by progressively upgrading
    cheaper milk products to more expensive ones.

    Priority: SWP ($1.50) → DWP ($5.00) → WPC ($20.00)

    1. Allocate ALL qty as SWP (cheapest → max qty utilization).
    2. Upgrade SWP→DWP ($3.50 extra each) until budget is consumed.
    3. Upgrade DWP→WPC ($15.00 extra each) until budget is consumed.
    4. If budget remains after step 3 with no DWP left, upgrade SWP→WPC ($18.50).

    Returns (q_swp, q_dwp, q_wpc) — non-negative integers.
    """
    if total_qty <= 0 or remaining_cif <= 0:
        return 0, 0, 0

    Q = total_qty
    C = remaining_cif

    if C < Q * 1.50:
        return math.floor(C / 1.50), 0, 0

    budget = C - Q * 1.50

    # Step 1: SWP → DWP  ($3.50 extra/unit)
    n_dwp = min(math.floor(budget / 3.50), Q)
    budget -= n_dwp * 3.50

    # Step 2: DWP → WPC  ($15.00 extra/unit)
    n_wpc = 0
    if budget > 0 and n_dwp > 0:
        n_wpc  = min(math.floor(budget / 15.00), n_dwp)
        budget -= n_wpc * 15.00
        n_dwp  -= n_wpc

    # Step 3: SWP → WPC  ($18.50 extra/unit, only when no DWP left)
    q_swp = Q - n_dwp - n_wpc
    if budget > 0 and n_dwp == 0 and q_swp > 0:
        n_swp_wpc = min(math.floor(budget / 18.50), q_swp)
        n_wpc    += n_swp_wpc
        q_swp    -= n_swp_wpc

    return q_swp, n_dwp, n_wpc


# ─── Simple rule helper ───────────────────────────────────────────────────────

def _simple_line(
    ii,
    avail: float,
    remaining_cif: float,
    unit_price: float,
    item_name_id: Optional[int],
    rule_label: str,
) -> tuple[Optional[dict], float]:
    """
    Build one plan line for a fixed-price rule.

    Steps:
      1. Cap raw CIF at min(avail × rate, remaining_cif).
      2. Floor the quantity: planned_qty = FLOOR(raw_cif ÷ rate).
      3. Recalculate CIF from the floored qty: planned_cif = planned_qty × rate.
         This ensures planned_cif = planned_qty × unit_price exactly, matching
         the user-visible formula (e.g. 18,884 × 1.50 = 28,326.00, NOT 28,326.80).
      4. Return None when planned_qty is 0 so callers skip the line safely.

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
        'note':             f'Auto-planned (E1 {rule_label})',
    }
    return line, _r2(remaining_cif - planned_cif)


# ─── Main entry point ──────────────────────────────────────────────────────────

def compute_e1_auto_plan(license_obj) -> tuple[list[dict], float]:
    """
    Run the full E1 Auto Plan waterfall over a licence's import items.

    Processing order (each step draws down the shared balance CIF):
      1. Other Confectionery Ingredients  @ $3.00
      2. Milk & Milk  (SWP / DWP / WPC splits)
      3. Juice  @ $2.50  — ONLY when no Milk & Milk items exist
      4. Aluminium Foil (HSN/desc 7607)  @ $4.50
      5. Citric / Tartaric Acid  @ $1.60
      6. Plastic Packing (HSN 390, min 100 KG) @ $1.00
         — ONLY when Aluminium Foil generated no lines

    Each import item matches the first applicable rule (hierarchical priority).
    Items in no recognised category are left unplanned.

    Returns:
        (lines, remaining_cif)
        lines — ready-to-save dicts for LicenseItemPlan.
        remaining_cif — balance CIF not consumed by the plan.
    """
    from apps.core.models import ItemNameModel
    from apps.license.services.e1_plan import classify_e1_item

    # ── 1. Pre-fetch item-name IDs for all named plan entries ─────────────────
    name_ids: dict[str, Optional[int]] = {n: None for n in _ALL_RULE_NAMES}
    for obj in ItemNameModel.objects.filter(name__in=_ALL_RULE_NAMES):
        name_ids[obj.name] = obj.id

    # ── 2. Load import items and bucket by rule ───────────────────────────────
    import_items = (
        license_obj.import_license.all()
        .select_related('hs_code')
        .prefetch_related('items')
        .order_by('serial_number')
    )

    balance_cif   = float(license_obj.get_balance_cif or license_obj.balance_cif or 0)
    remaining_cif = balance_cif

    # Buckets — each import item lands in exactly one bucket (first-match wins).
    confectionery:    list = []          # Rule 1
    milk:             list = []          # Rule 2  [(ii, item_names), ...]
    juice:            list = []          # Rule 3
    aluminium_foil:   list = []          # Rule 4
    citric_tartaric:  list = []          # Rule 5
    plastic_packing:  list = []          # Rule 6

    for ii in import_items:
        item_names  = [n.name for n in ii.items.all()]
        key         = ', '.join(sorted(item_names)) if item_names else (ii.description or '-')
        hs          = (ii.hs_code.hs_code if ii.hs_code else '') or ''
        desc        = (ii.description or '')
        hs_l        = hs.lower()
        desc_l      = desc.lower()
        cat         = classify_e1_item(key, hs, desc)
        avail       = float(ii.available_quantity or 0)

        # Priority order mirrors the processing sequence.
        if cat == 'OTHER CONFECTIONERY INGREDIENTS':
            confectionery.append(ii)
        elif _is_milk_group(item_names, cat):
            milk.append((ii, item_names))
        elif cat == 'FRUIT JUICE' and 'actual user' not in desc_l:
            # Rule 3: juice items that are not flagged as "Actual User"
            juice.append(ii)
        elif '7607' in hs_l or '7607' in desc_l:
            aluminium_foil.append(ii)
        elif 'citric' in desc_l or 'tartaric' in desc_l:
            citric_tartaric.append(ii)
        elif hs_l.startswith('390') and avail >= 100:
            # Rule 6: plastic packing — only items with ≥ 100 KG available
            plastic_packing.append(ii)
        # else: unclassified — left unplanned

    has_milk = len(milk) > 0

    lines: list[dict] = []

    # ── Rule 1: Other Confectionery Ingredients ── $3.00 ─────────────────────
    for ii in confectionery:
        if remaining_cif <= 0:
            break
        avail = float(ii.available_quantity or 0)
        if avail < MIN_PLAN_QTY:
            continue
        line, remaining_cif = _simple_line(
            ii, avail, remaining_cif, 3.0,
            name_ids.get('Other Confectionery Ingredients - E1'),
            'Rule 1 – Confectionery',
        )
        if line:
            lines.append(line)

    # ── Rule 2: Milk & Milk ── greedy SWP→DWP→WPC optimizer ─────────────────
    # Group milk items by description so the same product across serial numbers
    # is planned as one unit. Plan lines are assigned to the representative
    # import item (lowest serial number), matching PlanTab grouping in the UI.
    from collections import defaultdict as _dd
    milk_by_desc: dict = _dd(list)
    for ii, _ in milk:
        key = (ii.description or '').strip().upper()
        milk_by_desc[key].append(ii)

    for _desc, group in milk_by_desc.items():
        if remaining_cif <= 0:
            break
        group_qty = int(math.floor(
            sum(float(ii.available_quantity or 0) for ii in group)
        ))
        if group_qty < MIN_PLAN_QTY:
            continue
        rep = min(group, key=lambda x: x.serial_number)
        q_swp, q_dwp, q_wpc = _optimal_milk_split(group_qty, remaining_cif)
        for prod, qty, price in [
            ('SWP - E1', q_swp, 1.50),
            ('DWP - E1', q_dwp, 5.00),
            ('WPC - E1', q_wpc, 20.00),
        ]:
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
                'note':             f'Auto-planned (E1 Rule 2 — {prod})',
            })
            remaining_cif = _r2(remaining_cif - cif)

    # ── Rule 3: Juice ── $2.50 (ONLY when no Milk & Milk items on licence) ────
    if not has_milk:
        for ii in juice:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line(
                ii, avail, remaining_cif, 2.50,
                name_ids.get('Fruit Juice - E1'),
                'Rule 3 – Juice',
            )
            if line:
                lines.append(line)

    # ── Rule 4: Aluminium Foil ── $4.50 (HSN/desc contains 7607) ─────────────
    aluminium_lines: list[dict] = []
    for ii in aluminium_foil:
        if remaining_cif <= 0:
            break
        avail = float(ii.available_quantity or 0)
        if avail < MIN_PLAN_QTY:
            continue
        line, remaining_cif = _simple_line(
            ii, avail, remaining_cif, 4.50,
            name_ids.get('Aluminium Foil'),
            'Rule 4 – Aluminium Foil',
        )
        if line:
            aluminium_lines.append(line)
    lines.extend(aluminium_lines)
    aluminium_planned = len(aluminium_lines) > 0

    # ── Rule 5: Citric / Tartaric Acid ── $1.60 ──────────────────────────────
    for ii in citric_tartaric:
        if remaining_cif <= 0:
            break
        avail = float(ii.available_quantity or 0)
        if avail < MIN_PLAN_QTY:
            continue
        line, remaining_cif = _simple_line(
            ii, avail, remaining_cif, 1.60,
            name_ids.get('CITRIC ACID / TARTARIC ACID - E1'),
            'Rule 5 – Citric/Tartaric',
        )
        if line:
            lines.append(line)

    # ── Rule 6: Plastic Packing Material ── $1.00 (ONLY when no Alum. Foil) ──
    if not aluminium_planned:
        for ii in plastic_packing:
            if remaining_cif <= 0:
                break
            avail = float(ii.available_quantity or 0)
            if avail < MIN_PLAN_QTY:
                continue
            line, remaining_cif = _simple_line(
                ii, avail, remaining_cif, 1.00,
                name_ids.get('Plastic Packing Material'),
                'Rule 6 – Plastic Packing',
            )
            if line:
                lines.append(line)

    return lines, remaining_cif
