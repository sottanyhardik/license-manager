"""
E5 Auto-Plan service — writes DB plan lines for the biscuits norm.

All business rules (rates, processing order, Special Validation, per-item
0404/3502 classification with no averaging, Balance CIF recalculation) live
in the shared engine ``services/e5_plan.py`` (:func:`plan_e5_items`). This
module only handles what's specific to writing persisted plan lines:

  * bucketing raw import items into groups (one plan line per description
    group, saved on the group's lowest-serial representative — matching how
    the Plan Tab groups them in the UI);
  * a keyword-based fallback for classifying milk/dairy items whose HSN is
    missing or unreliable (``_is_milk_group``) — a data-quality workaround,
    independent of the shared engine's rules;
  * mapping the engine's per-item results to ``LicenseItemPlan``-shaped
    line dicts (``import_item``, ``item_name``, ``planned_quantity``,
    ``unit_price``, ``planned_cif_fc``, ``note``);
  * the persistence-layer conventions the engine's ``min_plan_qty=50`` /
    ``floor_qty=True`` options implement: import items below 50 units are
    never planned, and fixed-rate steps floor to whole-number quantities.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apps.license.services.auto_plan_shared import (
    ensure_plan_item_names as _ensure_names,
    group_by_desc as _group_by_desc,
)
from apps.license.services.e5_plan import E5Item, classify_e5_item, plan_e5_items

MIN_PLAN_QTY = Decimal('50')

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

# Maps the engine's E5PlanLine.step to the DB item-name string. Public
# (not underscore-prefixed): `item_pivot_report.py` also imports this to
# attribute a LIVE (never-persisted) waterfall recompute's planned CIF back
# to the same item-name column Auto-Plan would save it under — the import
# item's OWN master-data tags (`ii.items.all()`) are a different, unrelated
# thing and must never be used for this attribution.
STEP_ITEM_NAME: dict[str, str] = {
    'DIETARY FIBRE':   'DIETARY FIBRE - E5',
    'PALM KERNEL OIL': 'PALM KERNEL OIL - E5',
    'RBD PALMOLEIN':   'RBD PALMOLEIN OIL - E5',
    'REMAINING OILS':  'OLIVE OIL - E5',
    'DWP':             'DWP - E5',
    'SWP':             'SWP - E5',
    'WPC':             'WPC - E5',
    'WHEAT FLOUR':     'WHEAT FLOUR - E5',
}

_STEP_LABEL: dict[str, str] = {
    'DIETARY FIBRE':   'Rule 1 – Dietary Fibre',
    'PALM KERNEL OIL': 'Rule 2.1 – Palm Kernel Oil',
    'RBD PALMOLEIN':   'Rule 2.2 – RBD Palmolein',
    'REMAINING OILS':  'Rule 2.3 – Olive Oil',
    'DWP':             'Rule 4 — DWP - E5',
    'SWP':             'Rule 4 — SWP - E5',
    'WPC':             'Rule 4 — WPC - E5',
    'WHEAT FLOUR':     'Final – Wheat Flour mop-up',
}

# Keywords that identify milk/dairy import items (lowercase) — fallback for
# items whose HSN is missing/unreliable; `classify_e5_item` is tried first.
_MILK_KW = frozenset({
    'swp', 'dwp', 'wpc', 'whey', 'milk', 'skimmed', 'lactose',
    'casein', 'permeate', 'butter', 'cream',
})
_WPC_KW = frozenset({'wpc', 'egg', 'albumin'})


def _is_milk_group(item_name_list: list[str], e5_cat: Optional[str]) -> bool:
    """True when this import item is a milk/dairy product under E5."""
    if e5_cat in ('MILK PRODUCTS', 'EGG ALBUMIN / WPC'):   # HSN 0404 / 3502
        return True
    for name in item_name_list:
        if any(kw in name.lower() for kw in _MILK_KW):
            return True
    return False


def _milk_category(item_name_list: list[str], e5_cat: Optional[str]) -> str:
    """Which shared-engine milk bucket a milk-classified item belongs to.

    `classify_e5_item`'s own HSN-based category wins when available; items
    only caught by `_is_milk_group`'s keyword fallback (no reliable HSN) are
    routed to EGG ALBUMIN / WPC when their name suggests egg/WPC, else to
    the far more common MILK PRODUCTS (0404, DWP/SWP) bucket.
    """
    if e5_cat in ('MILK PRODUCTS', 'EGG ALBUMIN / WPC'):
        return e5_cat
    for name in item_name_list:
        if any(kw in name.lower() for kw in _WPC_KW):
            return 'EGG ALBUMIN / WPC'
    return 'MILK PRODUCTS'


# ─── Main entry point ──────────────────────────────────────────────────────

def compute_e5_auto_plan(license_obj) -> tuple[list[dict], float]:
    """Run the full E5 Auto Plan waterfall via the shared engine.

    Returns (lines, remaining_cif).
    """
    # ── Get-or-create all planned item names (§2: never fail on missing) ────
    name_ids = _ensure_names(list(_RULE_NAMES_E5))

    # ── Load import items ────────────────────────────────────────────────
    import_items = (
        license_obj.import_license.all()
        .select_related('hs_code')
        .prefetch_related('items')
        .order_by('serial_number')
    )

    _live_balance_cif = license_obj.get_balance_cif
    balance_cif = Decimal(str(_live_balance_cif if _live_balance_cif is not None else (license_obj.balance_cif or 0)))

    # ── Bucket import items (hierarchical: first-match wins) ────────────────
    dietary_fibre: list = []
    milk_0404: list = []
    milk_3502: list = []
    palm_kernel: list = []   # Case 2.1 — PKO  @ $1.80
    rbd: list = []           # Case 2.2 — RBD  @ $1.20
    olive_oil: list = []     # Case 2.3 — Olive @ $5.00
    wheat_flour: list = []   # Final mop-up — dynamic rate, absorbs all remaining CIF

    for ii in import_items:
        item_names = [n.name for n in ii.items.all()]
        key = ', '.join(sorted(item_names)) if item_names else (ii.description or '-')
        hs = (ii.hs_code.hs_code if ii.hs_code else '') or ''
        desc = (ii.description or '')
        hs_l = hs.lower().replace(' ', '').replace('-', '')
        desc_l = desc.lower()
        cat = classify_e5_item(key, hs, desc)

        if cat == 'DIETARY FIBRE':
            dietary_fibre.append(ii)
        elif _is_milk_group(item_names, cat):
            if _milk_category(item_names, cat) == 'EGG ALBUMIN / WPC':
                milk_3502.append(ii)
            else:
                milk_0404.append(ii)
        # Case 2.1: HSN starts with 1513 OR description contains "Vegetable Oil"
        elif hs_l.startswith('1513') or 'vegetable oil' in desc_l or cat == 'PALM KERNEL OIL':
            palm_kernel.append(ii)
        # Case 2.2: HSN 15119020 (RBD Palmolein) — only if Case 2.1 not applicable
        elif hs_l.startswith('15119') or cat == 'RBD PALMOLEIN':
            rbd.append(ii)
        # Case 2.3: Olive oil — edible-oil items NOT covered by palm kernel (1513)
        # or RBD (1511). Use HSN chapter 15 (fats/oils) or explicit phrases;
        # DO NOT use bare 'oil' substring — 'aluminium foil' contains 'oil' and
        # would wrongly match packing materials with HSN 39xx.
        elif cat == 'REMAINING OILS' or (
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

    # ── Group each bucket by description; one E5Item per group, keyed on
    # the group's lowest-serial representative (matches how the Plan Tab
    # groups items and how manual plans are anchored). ──────────────────
    rep_by_key: dict = {}
    items: list[E5Item] = []

    def _add_group(bucket: list, category: str) -> None:
        for rep, group_avail in _group_by_desc(bucket):
            rep_by_key[rep.id] = rep
            items.append(E5Item(key=rep.id, category=category, qty=Decimal(str(group_avail))))

    _add_group(dietary_fibre, 'DIETARY FIBRE')
    _add_group(milk_0404, 'MILK PRODUCTS')
    _add_group(milk_3502, 'EGG ALBUMIN / WPC')
    _add_group(palm_kernel, 'PALM KERNEL OIL')
    _add_group(rbd, 'RBD PALMOLEIN')
    _add_group(olive_oil, 'REMAINING OILS')
    _add_group(wheat_flour, 'WHEAT FLOUR')

    result = plan_e5_items(items, balance_cif, min_plan_qty=MIN_PLAN_QTY, floor_qty=True)

    lines: list[dict] = []
    for line in result.lines:
        rep = rep_by_key[line.key]
        if line.step == 'SWP' and result.special_validation_triggered:
            label = 'Rule Special — SWP - E5'
        else:
            label = _STEP_LABEL[line.step]
        lines.append({
            'import_item':      rep.id,
            'item_name':        name_ids.get(STEP_ITEM_NAME[line.step]),
            'planned_quantity': float(line.planned_qty),
            'unit_price':       float(line.unit_price),
            'planned_cif_fc':   float(line.planned_cif),
            'note':             f'Auto-planned (E5 {label})',
        })

    return lines, float(result.remaining_cif)
