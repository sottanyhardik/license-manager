"""
E1 Auto-Plan service — writes DB plan lines for the confectionery norm.

All business rules (categories, rates, processing order, milk DWP/SWP split,
Remaining CIF drawdown) live in the shared engine ``services/e1_plan.py``
(:func:`plan_e1_items`). This module only handles what's specific to writing
persisted plan lines:

  * bucketing raw import items into groups (one plan line per description
    group, saved on the group's lowest-serial representative — matching how
    the Plan Tab groups them in the UI);
  * mapping the engine's per-item results to ``LicenseItemPlan``-shaped
    line dicts (``import_item``, ``item_name``, ``planned_quantity``,
    ``unit_price``, ``planned_cif_fc``, ``note``);
  * the persistence-layer convention shared with E5/E132: import items below
    50 units are never planned (``min_plan_qty=50``).
"""
from __future__ import annotations

from decimal import Decimal

from apps.license.services.auto_plan_shared import (
    ensure_plan_item_names as _ensure_names,
    group_by_desc as _group_by_desc,
)
from apps.license.services.e1_plan import E1Item, classify_e1_item, plan_e1_items

MIN_PLAN_QTY = Decimal('50')

# Each entry: (item_name, norm_code). ensure_plan_item_names creates any
# missing rows so Auto Plan never fails because a name is absent from the DB.
_RULE_NAMES_E1: tuple[tuple[str, str], ...] = (
    ('OTHER CONFECTIONERY INGREDIENTS - E1',  'E1'),   # Step 1
    ('FRUIT/COCOA - E1',                      'E1'),   # Step 2 — Cocoa Mass
    ('DWP - E1',                              'E1'),   # Step 3 — Milk
    ('SWP - E1',                              'E1'),   # Step 3 — Milk
    ('WPC - E1',                              'E1'),   # Step 4
    ('EGG ALBUMIN - E1',                      'E1'),   # legacy — no longer produced, kept for old plan rows
    ('FRUIT JUICE - E1',                      'E1'),   # Step 5
    ('CITRIC ACID / TARTARIC ACID - E1',      'E1'),   # Step 6 — Tartaric Acid
    ('ALUMINIUM FOIL - E1',                   'E1'),   # Step 7
    ('PP - E1',                               'E1'),   # Step 8 — Polypropylene
)

# Public set of every item name the E1 auto-planner can produce.
# Used by the Item Pivot Report to filter import items that the planner
# never generates so they don't appear as empty columns. When a new rule is
# added to _RULE_NAMES_E1 the report automatically picks it up.
E1_PLANNABLE_NAMES: frozenset[str] = frozenset(name for name, _ in _RULE_NAMES_E1)

# Maps the engine's E1PlanLine.step to the DB item-name string.
_STEP_ITEM_NAME: dict[str, str] = {
    'OTHER CONFECTIONERY INGREDIENTS': 'OTHER CONFECTIONERY INGREDIENTS - E1',
    'COCOA MASS':                      'FRUIT/COCOA - E1',
    'DWP':                             'DWP - E1',
    'SWP':                             'SWP - E1',
    'EGG ALBUMIN':                     'WPC - E1',
    'FRUIT JUICE':                     'FRUIT JUICE - E1',
    'TARTARIC ACID':                   'CITRIC ACID / TARTARIC ACID - E1',
    'ALUMINIUM FOIL':                  'ALUMINIUM FOIL - E1',
    'POLYPROPYLENE':                   'PP - E1',
}

_STEP_LABEL: dict[str, str] = {
    'OTHER CONFECTIONERY INGREDIENTS': 'Step 1 – Other Confectionery',
    'COCOA MASS':                      'Step 2 – Cocoa Mass',
    'DWP':                             'Step 3 – Milk (DWP)',
    'SWP':                             'Step 3 – Milk (SWP)',
    'EGG ALBUMIN':                     'Step 4 – WPC',
    'FRUIT JUICE':                     'Step 5 – Fruit Juice',
    'TARTARIC ACID':                   'Step 6 – Tartaric Acid',
    'ALUMINIUM FOIL':                  'Step 7 – Aluminium Foil',
    'POLYPROPYLENE':                   'Step 8 – Polypropylene',
}


def compute_e1_auto_plan(license_obj) -> tuple[list[dict], float]:
    """Run the full E1 Auto Plan waterfall via the shared engine.

    Returns (lines, remaining_cif).
    """
    name_ids = _ensure_names(list(_RULE_NAMES_E1))

    import_items = (
        license_obj.import_license.all()
        .select_related('hs_code')
        .prefetch_related('items')
        .order_by('serial_number')
    )

    _live_balance_cif = license_obj.get_balance_cif
    balance_cif = Decimal(str(
        _live_balance_cif if _live_balance_cif is not None else (license_obj.balance_cif or 0)
    ))

    # ── Bucket import items by classification (single source of truth:
    # classify_e1_item), then group each bucket by description — one
    # E1Item per group, keyed on the group's lowest-serial representative
    # (matches how the Plan Tab groups items and how manual plans are
    # anchored). ─────────────────────────────────────────────────────────
    buckets: dict[str, list] = {}
    for ii in import_items:
        item_names = [n.name for n in ii.items.all()]
        key = ', '.join(sorted(item_names)) if item_names else (ii.description or '-')
        hs = (ii.hs_code.hs_code if ii.hs_code else '') or ''
        desc = ii.description or ''
        cat = classify_e1_item(key, hs, desc)
        if not cat:
            continue
        buckets.setdefault(cat, []).append(ii)

    rep_by_key: dict = {}
    items: list[E1Item] = []
    for cat, bucket in buckets.items():
        for rep, group_avail in _group_by_desc(bucket):
            rep_by_key[rep.id] = rep
            items.append(E1Item(key=rep.id, category=cat, qty=Decimal(str(group_avail))))

    result = plan_e1_items(items, balance_cif, min_plan_qty=MIN_PLAN_QTY)

    lines: list[dict] = []
    for line in result.lines:
        rep = rep_by_key[line.key]
        lines.append({
            'import_item':      rep.id,
            'item_name':        name_ids.get(_STEP_ITEM_NAME[line.step]),
            'planned_quantity': float(line.planned_qty),
            'unit_price':       float(line.unit_price),
            'planned_cif_fc':   float(line.planned_cif),
            'note':             f'Auto-planned (E1 {_STEP_LABEL[line.step]})',
        })

    return lines, float(result.remaining_cif)
