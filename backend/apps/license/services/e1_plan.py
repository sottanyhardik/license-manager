"""
E1 (confectionery) utilization-planning engine — the single source of truth
for E1 business rules. Every consumer (Auto-Plan, Item Pivot Report + its
Excel export, `norm_plan.py` / License Overview Planning tab + Balance Excel)
calls :func:`plan_e1_items`; none of them may re-implement these rules.

Processing order (each step draws down the same running balance; every
import item is classified into exactly one bucket up front by
:func:`classify_e1_item`, so no item is ever evaluated by more than one
step):

    1. OTHER CONFECTIONERY INGREDIENTS   @ 3.00
    2. COCOA MASS                        @ 10.00
    3. MILK PRODUCTS — delegated to the shared milk-planning engine
       (``milk_planner.split_milk_0404``, configured via ``MILK_CONFIG``),
       called once per item exactly as E5's own milk step calls it, so E1
       and E5 never carry two independent implementations of the DWP/SWP
       pricing rules.
    4. EGG ALBUMIN                       @ MILK_CONFIG.wpc_price (25.00)
    5. FRUIT JUICE                       @ 2.50
    6. TARTARIC ACID                     @ 1.50
    7. ALUMINIUM FOIL                    @ 4.50
    8. POLYPROPYLENE                     @ 1.20

Steps 1, 2, 4-8 all share one routine (:func:`_generic_stage`) built on the
existing :func:`~apps.license.services.planning_allocation.allocate_step`
primitive: sum the category's quantity, allocate one shared rate for the
whole category (max price if the balance covers the total, else
``remaining / total_qty``), then give every item in the category that same
rate at its own full quantity. Each step's utilization is capped at the
remaining balance — if the requested ``qty × max_price`` would exceed the
balance, the rate drops to ``balance / qty`` so the step consumes exactly
the balance and later steps see zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.license.services.milk_planner import MILK_CONFIG, split_milk_0404
from apps.license.services.planning_allocation import allocate_step, d as _d

_MONEY_4DP = Decimal('0.0001')


def _quantize(value: Decimal) -> Decimal:
    """4-dp quantization for display + comparison stability, staying Decimal."""
    return value.quantize(_MONEY_4DP)


# Classification buckets, in waterfall priority order.
E1_CATS: tuple[str, ...] = (
    'OTHER CONFECTIONERY INGREDIENTS',
    'COCOA MASS',
    'MILK PRODUCTS',
    'EGG ALBUMIN',
    'FRUIT JUICE',
    'TARTARIC ACID',
    'ALUMINIUM FOIL',
    'POLYPROPYLENE',
)

# Fixed unit prices for the plain generic steps. Milk (DWP/SWP) and Egg
# Albumin reuse MILK_CONFIG — the single source of truth shared with E5 —
# rather than duplicating those literals here.
E1_UNIT_PRICES: dict[str, Decimal] = {
    'OTHER CONFECTIONERY INGREDIENTS': Decimal('3.00'),
    'COCOA MASS':                      Decimal('10.00'),
    'FRUIT JUICE':                     Decimal('2.50'),
    'TARTARIC ACID':                   Decimal('1.50'),
    'ALUMINIUM FOIL':                  Decimal('4.50'),
    'POLYPROPYLENE':                   Decimal('1.20'),
}

EGG_ALBUMIN_PRICE: Decimal = MILK_CONFIG.wpc_price


def _norm(value) -> str:
    """Lower-case + strip for case-insensitive substring matching."""
    return (value or '').strip().lower()


def _hsn_digits(hs_code) -> str:
    """Digits-only HSN for prefix matching (ignores spaces/dashes/case)."""
    return ''.join(c for c in _norm(hs_code) if c.isdigit())


def classify_e1_item(
    item_key: str | None,
    hs_code: str | None,
    description: str | None,
) -> str | None:
    """Return the E1 planner bucket for an item, or None if no rule matches.

    Precedence (high → low) — matches the 8-step waterfall order exactly:

      0. item/description contains 'food flavour'            → excluded from
         step 1 (see below); never classified as OTHER CONFECTIONERY
         INGREDIENTS purely because it happens to carry an HSN under chapter
         0802. Falls through to steps 2-8 like any other item, or None if
         nothing else matches — it is NEVER given a fallback bucket.
      1. HSN starts with '0802', or item/description contains
         'other confectionery' — UNLESS excluded by step 0 above
                                                              → OTHER CONFECTIONERY INGREDIENTS
      2. HSN starts with '1803', or description contains '1803'  → COCOA MASS
      3. (HSN starts with '0404' OR description contains '0404')
         AND description contains 'milk'
         AND NOT (HSN starts with '1803' OR description contains '1803') → MILK PRODUCTS
      4. (HSN starts with '3502' OR description contains '3502')
         AND NOT 1803 AND NOT 0404                             → EGG ALBUMIN
      5. HSN starts with '2009', or description contains 'juice' → FRUIT JUICE
      6. HSN starts with '2918', or description contains '2918',
         or item/description contains 'tartaric'               → TARTARIC ACID
      7. HSN starts with '7607', or item/description contains
         '7607'                                                → ALUMINIUM FOIL
      8. HSN starts with '3902' (checked only once step 7 has
         ruled out any '7607' match — item/description text
         like 'PP'/'Polypropylene' is never used)               → POLYPROPYLENE
    """
    item = _norm(item_key)
    hs = _hsn_digits(hs_code)
    desc = _norm(description)

    is_food_flavour = 'food flavour' in item or 'food flavour' in desc
    if not is_food_flavour and (
        hs.startswith('0802') or 'other confectionery' in item or 'other confectionery' in desc
    ):
        return 'OTHER CONFECTIONERY INGREDIENTS'

    if hs.startswith('1803') or '1803' in desc:
        return 'COCOA MASS'

    has_1803 = hs.startswith('1803') or '1803' in desc
    has_0404 = hs.startswith('0404') or '0404' in desc
    if has_0404 and 'milk' in desc and not has_1803:
        return 'MILK PRODUCTS'

    has_3502 = hs.startswith('3502') or '3502' in desc
    if has_3502 and not has_1803 and not has_0404:
        return 'EGG ALBUMIN'

    if hs.startswith('2009') or 'juice' in desc:
        return 'FRUIT JUICE'

    if hs.startswith('2918') or '2918' in desc or 'tartaric' in item or 'tartaric' in desc:
        return 'TARTARIC ACID'

    if hs.startswith('7607') or '7607' in item or '7607' in desc:
        return 'ALUMINIUM FOIL'

    if hs.startswith('3902'):
        return 'POLYPROPYLENE'

    return None


@dataclass(frozen=True)
class E1Item:
    """One planning input: a raw import item (or a description-group
    representative), already classified into an :data:`E1_CATS` bucket."""
    key: str
    category: str
    qty: Decimal


@dataclass(frozen=True)
class E1PlanLine:
    """One planned allocation against a single :class:`E1Item`.

    ``step`` equals ``category`` for every generic step; MILK PRODUCTS
    produces a 'DWP' and/or 'SWP' step per item (never both averaged).
    """
    key: str
    category: str
    step: str
    planned_qty: Decimal
    unit_price: Decimal
    planned_cif: Decimal


@dataclass(frozen=True)
class E1PlanResult:
    lines: list[E1PlanLine]
    remaining_cif: Decimal


def _generic_stage(
    items: list[E1Item],
    category: str,
    max_rate: Decimal,
    remaining: Decimal,
) -> tuple[list[E1PlanLine], Decimal]:
    """One generic-rule stage: a single shared rate for every item in the
    category — sum the category's quantity, allocate one rate for the whole
    category via :func:`allocate_step` (max_rate if the balance covers the
    total, else ``remaining / total_qty``), then give each item that rate
    at its own full quantity.

    Returns ``(lines, used_cif)`` — ``used_cif`` is the aggregate amount to
    subtract from ``remaining`` (not the sum of individually-rounded lines,
    so no rounding drift accumulates across many items).
    """
    if not items or remaining <= 0:
        return [], Decimal('0')
    total_qty = sum((it.qty for it in items), Decimal('0'))
    if total_qty <= 0:
        return [], Decimal('0')
    used_cif, rate = allocate_step(total_qty, max_rate, remaining)
    if used_cif <= 0:
        return [], Decimal('0')
    lines = [
        E1PlanLine(
            key=it.key,
            category=category,
            step=category,
            planned_qty=it.qty,
            unit_price=_quantize(rate),
            planned_cif=_quantize(it.qty * rate),
        )
        for it in items
    ]
    return lines, used_cif


def plan_e1_items(
    items: list[E1Item],
    balance_cif,
    *,
    min_plan_qty: Decimal = Decimal('0'),
) -> E1PlanResult:
    """Run the full E1 waterfall over a list of already-classified items.

    Args:
        items: one :class:`E1Item` per import item (or description-group
            representative) — ``category`` must already be one of
            :data:`E1_CATS`; entries with an unrecognised category are
            ignored.
        balance_cif: the licence's starting balance for this run.
        min_plan_qty: items with ``qty`` below this are skipped entirely
            (no balance consumed) — pass 50 for Auto-Plan's minimum
            plannable quantity, 0 (default) for reporting.

    Returns:
        :class:`E1PlanResult` — ``lines`` in processing order and the final
        ``remaining_cif``.
    """
    remaining = _d(balance_cif)
    min_qty = _d(min_plan_qty)

    by_cat: dict[str, list[E1Item]] = {cat: [] for cat in E1_CATS}
    for it in items:
        if it.category not in by_cat:
            continue
        q = _d(it.qty)
        if q < min_qty:
            continue
        by_cat[it.category].append(E1Item(key=it.key, category=it.category, qty=q))

    lines: list[E1PlanLine] = []

    def _run_generic(category: str, max_rate: Decimal) -> None:
        nonlocal remaining
        if remaining <= 0:
            return
        cat_lines, used_cif = _generic_stage(by_cat[category], category, max_rate, remaining)
        lines.extend(cat_lines)
        remaining -= used_cif

    # Step 1 — Other Confectionery Ingredients.
    _run_generic('OTHER CONFECTIONERY INGREDIENTS', E1_UNIT_PRICES['OTHER CONFECTIONERY INGREDIENTS'])

    # Step 2 — Cocoa Mass.
    _run_generic('COCOA MASS', E1_UNIT_PRICES['COCOA MASS'])

    # Step 3 — Milk Products. Delegates to the shared milk engine, called
    # once per item exactly as e5_plan.py's own milk step does — E1 and E5
    # never carry two independent implementations of this math. Not a
    # generic stage: each item's own quantity gets its own DWP/SWP split
    # against the balance remaining at that point (sequential, not averaged
    # across items).
    if remaining > 0:
        for item in by_cat['MILK PRODUCTS']:
            if remaining <= 0:
                break
            dwp_qty, dwp_rate, swp_qty = split_milk_0404(item.qty, remaining, MILK_CONFIG)
            if dwp_qty > 0:
                dwp_cif = dwp_qty * dwp_rate
                lines.append(E1PlanLine(
                    key=item.key, category='MILK PRODUCTS', step='DWP',
                    planned_qty=dwp_qty, unit_price=_quantize(dwp_rate),
                    planned_cif=_quantize(dwp_cif),
                ))
                remaining -= dwp_cif
            if swp_qty > 0:
                swp_cif = swp_qty * MILK_CONFIG.swp_price
                lines.append(E1PlanLine(
                    key=item.key, category='MILK PRODUCTS', step='SWP',
                    planned_qty=swp_qty, unit_price=_quantize(MILK_CONFIG.swp_price),
                    planned_cif=_quantize(swp_cif),
                ))
                remaining -= swp_cif

    # Step 4 — Egg Albumin.
    _run_generic('EGG ALBUMIN', EGG_ALBUMIN_PRICE)

    # Step 5 — Fruit Juice.
    _run_generic('FRUIT JUICE', E1_UNIT_PRICES['FRUIT JUICE'])

    # Step 6 — Tartaric Acid.
    _run_generic('TARTARIC ACID', E1_UNIT_PRICES['TARTARIC ACID'])

    # Step 7 — Aluminium Foil.
    _run_generic('ALUMINIUM FOIL', E1_UNIT_PRICES['ALUMINIUM FOIL'])

    # Step 8 — Polypropylene.
    _run_generic('POLYPROPYLENE', E1_UNIT_PRICES['POLYPROPYLENE'])

    return E1PlanResult(lines=lines, remaining_cif=remaining)
