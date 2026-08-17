"""
E1 Auto-Plan service — writes DB plan lines for the confectionery norm.

All business rules (categories, rates, processing order, milk DWP/SWP split,
Remaining CIF drawdown) live in the shared engine ``services/e1_plan.py``
(:func:`plan_e1_items`). This module only handles what's specific to writing
persisted plan lines:

  * bucketing raw import items into groups (one plan line per
    `plan_group_key` group — HSN + normalized description, the same
    canonical grouping `plan_enforcement.py`/`plan_utilization.py`/exports
    use — saved on the group's lowest-serial representative — matching how
    the Plan Tab groups them in the UI);
  * mapping the engine's per-item results to ``LicenseItemPlan``-shaped
    line dicts (``import_item``, ``item_name``, ``planned_quantity``,
    ``unit_price``, ``planned_cif_fc``, ``note``);
  * the persistence-layer convention shared with E5/E132: import items below
    50 units are never planned (``min_plan_qty=50``).

Unlike E126/E132, this module does NOT run
``plan_grouping.validate_group_plan_lines``'s price-ceiling check — E1
includes genuinely dynamic, balance-driven rates (milk DWP/SWP/WPC) with no
fixed business-rule maximum to check against, and there is no "preserve
once generated" concept here for a stale price to drift from. It DOES run
``plan_grouping.validate_fresh_plan_lines`` (non-negative values + total
qty ≤ available), the same "never skip this" mandatory safety net E126/E132
apply — E1's waterfall is structurally bounded and should never trip it,
but a safety net that can't fire is still cheap insurance, not proof it's
unnecessary.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from apps.license.services.auto_plan_shared import ensure_plan_item_names as _ensure_names
from apps.license.services.e1_plan import E1Item, classify_e1_item, plan_e1_items
from apps.license.services.plan_grouping import merge_items_for_classification, validate_fresh_plan_lines

logger = logging.getLogger(__name__)

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

# Maps the engine's E1PlanLine.step to the DB item-name string. Public
# (not underscore-prefixed): `item_pivot_report.py` also imports this to
# attribute a LIVE (never-persisted) waterfall recompute's planned CIF back
# to the same item-name column Auto-Plan would save it under — the import
# item's OWN master-data tags (`ii.items.all()`) are a different, unrelated
# thing and must never be used for this attribution.
STEP_ITEM_NAME: dict[str, str] = {
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


def compute_e1_auto_plan(
    license_obj, *, configuration=None, create_item_names=True,
) -> tuple[list[dict], float]:
    """Run the full E1 Auto Plan waterfall via the shared engine.

    Returns (lines, remaining_cif).
    """
    if create_item_names:
        name_ids = _ensure_names(list(_RULE_NAMES_E1))
    else:
        from apps.license.models import ItemNameModel
        wanted = {name for name, _norm in _RULE_NAMES_E1}
        name_ids = dict(ItemNameModel.objects.filter(name__in=wanted).values_list('name', 'pk'))

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
    # classify_e1_item — unchanged, still per RAW item, since classification
    # partly keys off an item's own M2M item-name tags), then group each
    # already-classified bucket by `plan_group_key` (HSN + normalized
    # description) — the same canonical grouping mechanism every Auto-Plan
    # engine (E1/E5/E126/E132) and every plan-consuming layer (enforcement,
    # display, exports) uses; see `merge_items_for_classification`'s
    # docstring. One E1Item per group, keyed on the group's lowest-serial
    # representative (matches how the Plan Tab groups items and how manual
    # plans are anchored). ─────────────────────────────────────────────────
    buckets: dict[str, list] = {}
    for ii in import_items:
        item_names = [n.name for n in ii.items.all()]
        key = ', '.join(sorted(item_names)) if item_names else (ii.description or '-')
        hs = (ii.hs_code.hs_code if ii.hs_code else '') or ''
        desc = ii.description or ''
        cat = (
            configuration.classify({
                'record_id': ii.pk,
                'item_key': key,
                'hs_code': hs,
                'description': desc,
                'available_quantity': ii.available_quantity,
                'quantity': ii.quantity,
                'unit': ii.unit,
                'serial_number': ii.serial_number,
            })
            if configuration is not None
            else classify_e1_item(key, hs, desc)
        )
        if not cat:
            continue
        buckets.setdefault(cat, []).append(ii)

    rep_by_key: dict = {}
    avail_by_rep: dict[int, Decimal] = {}
    items: list[E1Item] = []
    for cat, bucket in buckets.items():
        items_by_id = {ii.id: ii for ii in bucket}
        for group in merge_items_for_classification(bucket):
            rep_id = group['representative_id']
            rep_by_key[rep_id] = items_by_id[rep_id]
            avail_by_rep[rep_id] = group['available_quantity']
            items.append(E1Item(key=rep_id, category=cat, qty=group['available_quantity']))

    result = plan_e1_items(
        items, balance_cif, min_plan_qty=MIN_PLAN_QTY,
        price_overrides=configuration.price_by_output if configuration is not None else None,
    )

    lines_by_rep: dict[int, list[dict]] = {}
    for line in result.lines:
        rep = rep_by_key[line.key]
        lines_by_rep.setdefault(rep.id, []).append({
            'import_item':      rep.id,
            'item_name':        name_ids.get(STEP_ITEM_NAME[line.step]),
            'planned_quantity': float(line.planned_qty),
            'unit_price':       float(line.unit_price),
            'planned_cif_fc':   float(line.planned_cif),
            'note':             f'Auto-planned (E1 {_STEP_LABEL[line.step]})',
        })

    # ── Mandatory generic validation (never skip this) ────────────────────
    # Same "never skip this" safety net E126/E132 apply — see
    # `validate_fresh_plan_lines`'s docstring for why no price-ceiling check
    # runs here.
    lines: list[dict] = []
    for rep_id, group_lines in lines_by_rep.items():
        if validate_fresh_plan_lines(group_lines, avail_by_rep[rep_id]):
            lines.extend(group_lines)
        else:
            logger.warning(
                "compute_e1_auto_plan: rejecting plan for group represented by "
                "import_item %s — planned_quantity=%s available=%s; likely a "
                "bug in the E1 waterfall, since this should never happen for "
                "its structurally-bounded computation.",
                rep_id, [ln['planned_quantity'] for ln in group_lines], avail_by_rep[rep_id],
            )

    return lines, float(result.remaining_cif)
