"""
E5 (biscuits) utilization-planning engine — the single source of truth for
E5 business rules. Every consumer (Auto-Plan, Item Pivot Report + its Excel
export, `norm_plan.py` / License Overview Planning tab + Balance Excel)
calls :func:`plan_e5_items`; none of them may re-implement these rules.

Processing order (each step draws down the same running balance, threaded
through every individual item — the balance is recalculated after every
single planned debit, never reused from before that debit):

    1. DIETARY FIBRE                @ 3.00
    ── Special Validation ── (immediately after step 1) ───────────────────
        milk_total = every Milk Products (0404) + Egg Albumin/WPC (3502)
        item's qty, summed. If remaining < milk_total × 1.50: every milk
        item (0404 AND 3502 alike) is planned right here at a flat SWP
        @ 1.50, individually, then step 3 (Oils) still runs, and step 4
        (Milk) below is skipped entirely.
    2. (reserved — Special Validation sits here in the sequence)
    3. EDIBLE OILS, per item, in this order:
         PALM KERNEL OIL   @ 1.80  (HSN 1513 / desc "Vegetable Oil")
         RBD PALMOLEIN     @ 1.20  (HSN 15119020 / "RBD")
         REMAINING OILS    @ 5.00  (all other edible oils)
    4. MILK — only when Special Validation did NOT fire. Every item is
       classified and priced independently; 0404 and 3502 quantities are
       NEVER averaged together, even when both appear on the same licence:
         all MILK PRODUCTS (0404) items, in input order — each item's OWN
           quantity is partitioned between DWP and SWP by the shared HSN
           0404 optimisation algorithm (``milk_planner.split_milk_0404``):
           DWP is maximised subject to its rate staying within
           [4.40, 5.00], SWP (fixed @ 1.50) absorbs the rest.
         then all EGG ALBUMIN / WPC (3502) items, in input order — each
           one gets WPC-E5 at a dynamic rate capped at 25.00
           (min(implied balance rate, 25.00)).
    5. WHEAT FLOUR mop-up — one dynamic rate (remaining ÷ total wheat-flour
       qty), applied per item.

All calculations use Decimal. Every step's utilization is capped at the
remaining balance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

from apps.license.services.milk_planner import MILK_CONFIG, split_milk_0404
from apps.license.services.planning_allocation import allocate_step, d as _d

_MONEY_4DP = Decimal('0.0001')


def _quantize(value: Decimal) -> Decimal:
    """4-dp quantization for display + comparison stability, staying Decimal
    (unlike ``planning_allocation.quantize_money``, which returns a float —
    not suitable here since callers do further Decimal arithmetic on
    ``E5PlanLine.planned_cif``)."""
    return value.quantize(_MONEY_4DP)


# Classification buckets. Wheat Flour is a preserved legacy bucket, not part
# of the milk-rule spec, appended at the end — real licences still carry
# wheat-flour import items that must stay planned.
E5_CATS: tuple[str, ...] = (
    'DIETARY FIBRE',
    'MILK PRODUCTS',
    'EGG ALBUMIN / WPC',
    'PALM KERNEL OIL',
    'RBD PALMOLEIN',
    'REMAINING OILS',
    'WHEAT FLOUR',
)

# Fixed unit prices for the plain fixed-rate steps. Milk/Egg-Albumin prices
# are the DWP_PRICE/SWP_PRICE/WPC_PRICE constants below; Wheat Flour is a
# dynamic mop-up so it has no fixed price.
E5_UNIT_PRICES: dict[str, Decimal] = {
    'DIETARY FIBRE':    Decimal('3.00'),
    'PALM KERNEL OIL':  Decimal('1.80'),
    'RBD PALMOLEIN':    Decimal('1.20'),
    'REMAINING OILS':   Decimal('5.00'),
}

# Milk/Egg-Albumin prices are the single source of truth in MILK_CONFIG
# (shared with E1) — aliased here so the rest of this module reads the same
# as before.
DWP_PRICE: Decimal = MILK_CONFIG.dwp_price
SWP_PRICE: Decimal = MILK_CONFIG.swp_price
WPC_PRICE: Decimal = MILK_CONFIG.wpc_price


def _norm(value) -> str:
    """Lower-case + strip for case-insensitive substring matching."""
    return (value or '').strip().lower()


def classify_e5_item(
    item_key: str | None,
    hs_code: str | None,
    description: str | None,
) -> str | None:
    """Return the E5 planner bucket for an item, or None if no rule matches.

    Precedence (high → low):

      1. 'dietary fibre' (item OR description)              → DIETARY FIBRE
         NOTE: a bare 'walnut' substring is NOT enough — the row must be
         explicitly tagged Dietary Fibre.
      2. 'wheat flour' item name (legacy, unambiguous — beats any HSN
         signal, same as the pre-existing behaviour)          → WHEAT FLOUR
      3. HSN contains '0404'                                  → MILK PRODUCTS
      4. HSN contains '3502'                                  → EGG ALBUMIN / WPC
      5. 'olive oil' item name (legacy, unambiguous — beats
         HSN 1513/1511 signals, same as the pre-existing
         behaviour)                                           → REMAINING OILS
      6. HSN contains '1513' / desc contains 'vegetable oil' /
         item 'pko'                                            → PALM KERNEL OIL
      7. HSN contains '1511' / item 'rbd'                      → RBD PALMOLEIN
      8. HSN chapter 15 (fats & oils) / desc contains
         'edible oil'                                          → REMAINING OILS
      9. Wheat-flour legacy HSN '11010000'                     → WHEAT FLOUR
    """
    item = _norm(item_key)
    hs = _norm(hs_code)
    desc = _norm(description)
    hs_digits = hs.replace(' ', '').replace('-', '')

    if 'dietary fibre' in item or 'dietary fibre' in desc:
        return 'DIETARY FIBRE'
    if 'wheat flour' in item:
        return 'WHEAT FLOUR'
    if '0404' in hs:
        return 'MILK PRODUCTS'
    if '3502' in hs:
        return 'EGG ALBUMIN / WPC'
    if 'olive oil' in item:
        return 'REMAINING OILS'

    if '1513' in hs or 'vegetable oil' in desc or 'pko' in item:
        return 'PALM KERNEL OIL'
    if '1511' in hs or 'rbd' in item:
        return 'RBD PALMOLEIN'
    if hs_digits.startswith('15') or 'edible oil' in desc:
        return 'REMAINING OILS'

    if '11010000' in hs:
        return 'WHEAT FLOUR'

    return None


def classify_e5_hsn(hs_code: str | None) -> str | None:
    """Backwards-compatible HSN-only classifier — kept so callers that only
    know an HSN can still bucket common cases. Item-name-only rules (Dietary
    Fibre by name, Wheat Flour by name, Olive Oil by name, PKO/RBD acronyms)
    never fire from an HSN-only call."""
    return classify_e5_item(None, hs_code, None)


def is_wheat_flour(hs_code: str | None) -> bool:
    """Kept for backward compatibility — legacy callers ask this directly."""
    return '11010000' in _norm(hs_code)


@dataclass(frozen=True)
class E5Item:
    """One planning input: a raw import item (or a description-group
    representative), already classified into an :data:`E5_CATS` bucket."""
    key: str
    category: str
    qty: Decimal


@dataclass(frozen=True)
class E5PlanLine:
    """One planned allocation against a single :class:`E5Item`.

    ``step`` is the specific rate bucket actually applied — finer-grained
    than ``category`` for MILK PRODUCTS / EGG ALBUMIN items, which each
    produce a 'DWP' and/or 'SWP' and/or 'WPC' step, or a 'SWP' override line
    when Special Validation fires.
    """
    key: str
    category: str
    step: str
    planned_qty: Decimal
    unit_price: Decimal
    planned_cif: Decimal


@dataclass(frozen=True)
class E5PlanResult:
    lines: list[E5PlanLine]
    remaining_cif: Decimal
    special_validation_triggered: bool


def _fixed_rate_line(
    qty: Decimal,
    rate: Decimal,
    remaining: Decimal,
    floor_qty: bool,
) -> tuple[Decimal, Decimal, Decimal]:
    """One fixed-rate-step allocation for a single item.

    ``floor_qty=False`` (reporting): dynamic-rate model — the item's full
    quantity is considered "used"; if the balance can't cover it at ``rate``,
    the effective rate drops to whatever the balance implies (matches
    :func:`allocate_step`).

    ``floor_qty=True`` (Auto-Plan): fixed-rate model — the rate never moves;
    instead the quantity is floored to a whole number so
    ``planned_qty * rate`` never exceeds the balance (matches the historic
    ``_simple_line_e5`` behaviour).

    Returns ``(planned_qty, effective_rate, planned_cif)`` — ``planned_cif``
    is 0 when nothing could be planned.
    """
    if qty <= 0 or rate <= 0 or remaining <= 0:
        return Decimal('0'), rate, Decimal('0')
    if not floor_qty:
        used_cif, eff_rate = allocate_step(qty, rate, remaining)
        if used_cif <= 0:
            return Decimal('0'), rate, Decimal('0')
        return qty, eff_rate, used_cif
    raw_cif = qty * rate
    capped_cif = raw_cif if raw_cif <= remaining else remaining
    planned_qty = (capped_cif / rate).to_integral_value(rounding=ROUND_FLOOR)
    planned_cif = planned_qty * rate
    if planned_qty <= 0 or planned_cif <= 0:
        return Decimal('0'), rate, Decimal('0')
    return planned_qty, rate, planned_cif


def plan_e5_items(
    items: list[E5Item],
    balance_cif,
    *,
    min_plan_qty: Decimal = Decimal('0'),
    floor_qty: bool = False,
    price_overrides: dict[str, Decimal] | None = None,
) -> E5PlanResult:
    """Run the full E5 waterfall over a list of already-classified items.

    Args:
        items: one :class:`E5Item` per import item (or description-group
            representative) — ``category`` must already be one of
            :data:`E5_CATS`; entries with an unrecognised category are
            ignored. Items are processed within each category **in the
            order given** — that order is business-significant whenever the
            balance runs out mid-category.
        balance_cif: the licence's starting balance for this run.
        min_plan_qty: items with ``qty`` below this are skipped entirely
            (no balance consumed) — pass 50 for Auto-Plan's minimum
            plannable quantity, 0 (default) for reporting.
        floor_qty: True for Auto-Plan (integer quantities, fixed rates —
            see :func:`_fixed_rate_line`); False for reporting (continuous
            decimals, dynamic rates). Milk sub-steps (DWP/SWP/WPC) always
            use the dynamic-rate model regardless of this flag — Auto-Plan
            never floored those (they were previously computed by
            ``optimal_milk_split``'s own 3-dp rounding, which this replaces).

    Returns:
        :class:`E5PlanResult` — ``lines`` in processing order, the final
        ``remaining_cif``, and whether Special Validation fired.
    """
    remaining = _d(balance_cif)
    prices = {**E5_UNIT_PRICES, 'EGG ALBUMIN / WPC': WPC_PRICE}
    prices.update({key: _d(value) for key, value in (price_overrides or {}).items() if key in prices})
    min_qty = _d(min_plan_qty)

    all_by_cat: dict[str, list[E5Item]] = {cat: [] for cat in E5_CATS}
    by_cat: dict[str, list[E5Item]] = {cat: [] for cat in E5_CATS}
    for it in items:
        if it.category not in all_by_cat:
            continue
        q = _d(it.qty)
        item = E5Item(key=it.key, category=it.category, qty=q)
        all_by_cat[it.category].append(item)
        if q >= min_qty:
            by_cat[it.category].append(item)

    lines: list[E5PlanLine] = []

    def _emit(item: E5Item, step: str, planned_qty: Decimal, rate: Decimal, cif: Decimal) -> None:
        if cif <= 0:
            return
        lines.append(E5PlanLine(
            key=item.key,
            category=item.category,
            step=step,
            planned_qty=planned_qty,
            unit_price=_quantize(rate),
            planned_cif=_quantize(cif),
        ))

    # Step 1 — Dietary Fibre.
    for item in by_cat['DIETARY FIBRE']:
        pq, rate, cif = _fixed_rate_line(item.qty, prices['DIETARY FIBRE'], remaining, floor_qty)
        _emit(item, 'DIETARY FIBRE', pq, rate, cif)
        remaining -= cif

    # Special Validation — uses the UNFILTERED milk total (matches the
    # historic Auto-Plan behaviour of checking before any threshold skip).
    milk_total_qty = sum(
        (i.qty for i in all_by_cat['MILK PRODUCTS'] + all_by_cat['EGG ALBUMIN / WPC']),
        Decimal('0'),
    )
    special_triggered = (
        milk_total_qty > 0
        and remaining > 0
        and remaining < milk_total_qty * SWP_PRICE
    )

    def _run_oils() -> None:
        nonlocal remaining
        for cat, rate in (
            ('PALM KERNEL OIL', prices['PALM KERNEL OIL']),
            ('RBD PALMOLEIN', prices['RBD PALMOLEIN']),
            ('REMAINING OILS', prices['REMAINING OILS']),
        ):
            for item in by_cat[cat]:
                pq, r, cif = _fixed_rate_line(item.qty, rate, remaining, floor_qty)
                _emit(item, cat, pq, r, cif)
                remaining -= cif

    if special_triggered:
        for item in by_cat['MILK PRODUCTS'] + by_cat['EGG ALBUMIN / WPC']:
            pq, r, cif = _fixed_rate_line(item.qty, SWP_PRICE, remaining, floor_qty)
            _emit(item, 'SWP', pq, r, cif)
            remaining -= cif
        _run_oils()
        # Step 4 (normal milk classification) is skipped — already planned above.
    else:
        _run_oils()
        # 0404 items — each item's own quantity is partitioned between DWP
        # and SWP by the shared HSN 0404 algorithm (never averaged with any
        # 3502 item on the same licence).
        for item in by_cat['MILK PRODUCTS']:
            dwp_qty, dwp_rate, swp_qty = split_milk_0404(item.qty, remaining, MILK_CONFIG)
            if dwp_qty > 0:
                dwp_cif = dwp_qty * dwp_rate
                _emit(item, 'DWP', dwp_qty, dwp_rate, dwp_cif)
                remaining -= dwp_cif
            if swp_qty > 0:
                swp_cif = swp_qty * SWP_PRICE
                _emit(item, 'SWP', swp_qty, SWP_PRICE, swp_cif)
                remaining -= swp_cif
        # 3502 items — WPC, dynamic rate capped at $25, processed after
        # every 0404 item.
        for item in by_cat['EGG ALBUMIN / WPC']:
            wpc_cif, wpc_rate = allocate_step(item.qty, prices['EGG ALBUMIN / WPC'], remaining)
            if wpc_cif > 0:
                _emit(item, 'WPC', item.qty, wpc_rate, wpc_cif)
                remaining -= wpc_cif

    # Step 5 — Wheat Flour mop-up: one dynamic rate across every qualifying
    # item's total quantity, then applied per item.
    wf_items = by_cat['WHEAT FLOUR']
    wf_total_qty = sum((i.qty for i in wf_items), Decimal('0'))
    if remaining > 0 and wf_total_qty > 0:
        wf_rate = remaining / wf_total_qty
        for item in wf_items:
            pq, r, cif = _fixed_rate_line(item.qty, wf_rate, remaining, floor_qty)
            _emit(item, 'WHEAT FLOUR', pq, r, cif)
            remaining -= cif

    return E5PlanResult(
        lines=lines,
        remaining_cif=remaining,
        special_validation_triggered=special_triggered,
    )
