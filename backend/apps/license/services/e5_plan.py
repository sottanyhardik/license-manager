"""
E5 (biscuits) utilization-planning waterfall.

The biscuits norm (E5) allocates the licence balance across several input
categories used in biscuit manufacturing. The user-defined waterfall is:

    Step 0  DIETARY FIBRE (HSN 0802)        — capped by the 10% condition pool
                                              AND by a max unit rate of 2.7
    Step 1  MILK (0404)                     — first pass at rate 1.5
    Step 2  VEGETABLE OIL (1513)            — rate 2.26
    Step 3  VEGETABLE OIL (15119020)        — rate 1.1
    Step 4  OTHER OILS (HSN 15xx residual)  — rate climbs up to a 6.0 cap
    Step 5  MILK (0404) bump                — escalate to 3.75 if anything left
    Step 6  MILK (3502)                     — rate 14.0 (combo logic — see below)
    Step 7  WHEAT FLOUR (HSN 11010000)      — mops up the residual

Combo logic for MILK (0404) and MILK (3502): when both items exist on the
licence AND `license_balance / (qty_0404 + qty_3502) > 4`, allocate 3502
first at 14.0 (its high rate consumes the balance fastest) and then bump
0404 up to rate 3.75 on whatever is left. Otherwise prefer 0404 alone —
3502 only kicks in if there is no 0404 at all.
"""
from __future__ import annotations

from decimal import Decimal


# Display order of the E5 categories.
E5_CATS: tuple[str, ...] = (
    'DIETARY FIBRE',
    'MILK (0404)',
    'VEGETABLE OIL (1513)',
    'VEGETABLE OIL (15119020)',
    'OTHER OILS (15xx)',
    'MILK (3502)',
    'WHEAT FLOUR',
)

# Categories that participate in `e5_totals` (everything except the
# WHEAT FLOUR fallback, which has its own `wf_qty` aggregate).
E5_PLAN_CATS: tuple[str, ...] = tuple(c for c in E5_CATS if c != 'WHEAT FLOUR')

# HSN-substring → category. ORDER MATTERS — more specific entries (1513,
# 15119020, 3502) come *before* the "15" catchall so substring matching
# does not grab specific oils into the OTHER OILS bucket.
_E5_HSN_MAP: tuple[tuple[str, str], ...] = (
    ('0802',     'DIETARY FIBRE'),
    ('0404',     'MILK (0404)'),
    ('1513',     'VEGETABLE OIL (1513)'),
    ('15119020', 'VEGETABLE OIL (15119020)'),
    ('3502',     'MILK (3502)'),
    ('15',       'OTHER OILS (15xx)'),
)

# Wheat-flour HSN fallback (handled separately from the planner categories).
_WF_HSN: tuple[str, ...] = ('11010000',)


def classify_e5_hsn(hs_code: str | None) -> str | None:
    """Return the E5 planner category for an HSN, or None if the HSN is
    either wheat flour (caller routes via `is_wheat_flour`) or fully
    unclassified."""
    hs = (hs_code or '').lower()
    if not hs:
        return None
    for needle, label in _E5_HSN_MAP:
        if needle in hs:
            return label
    return None


def is_wheat_flour(hs_code: str | None) -> bool:
    hs = (hs_code or '').lower()
    return any(k in hs for k in _WF_HSN)


def _f(x) -> float:
    """Tolerant float coercion — handles None / Decimal / str."""
    if x is None:
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0


def compute_e5_plan(
    e5_totals: dict[str, float],
    wf_qty: float,
    license_balance,
    pool_10pct,
) -> tuple[dict[str, float], dict[str, float]]:
    """Run the E5 waterfall.

    Returns `(planned_per_cat, rate_per_cat)` keyed by every entry in
    `E5_CATS`. The rate is the *effective* per-unit rate (Planned/Qty) for
    variable-rate rows (DIETARY FIBRE, MILK (0404), OTHER OILS, WHEAT FLOUR)
    and the fixed nominal rate for the others.
    """
    remaining = _f(license_balance)
    initial_balance = remaining
    planned: dict[str, float] = {c: 0.0 for c in E5_CATS}
    rate: dict[str, float] = {c: 0.0 for c in E5_CATS}

    qty_df        = _f(e5_totals.get('DIETARY FIBRE'))
    qty_0404      = _f(e5_totals.get('MILK (0404)'))
    qty_1513      = _f(e5_totals.get('VEGETABLE OIL (1513)'))
    qty_15119020  = _f(e5_totals.get('VEGETABLE OIL (15119020)'))
    qty_other_oil = _f(e5_totals.get('OTHER OILS (15xx)'))
    qty_3502      = _f(e5_totals.get('MILK (3502)'))
    wf_qty_f      = _f(wf_qty)

    # ── Step 0: DIETARY FIBRE — 10% pool cap AND 2.7 max-unit-rate cap ────
    # Effective unit rate is bounded by 2.7, so planned CIF is bounded by
    # min(2.7 × qty, 10% pool, remaining). Whichever bites first wins.
    pool = _f(pool_10pct)
    df_cap = 2.7 * qty_df
    planned['DIETARY FIBRE'] = max(min(df_cap, pool, remaining), 0.0)
    remaining -= planned['DIETARY FIBRE']
    rate['DIETARY FIBRE'] = (planned['DIETARY FIBRE'] / qty_df) if qty_df else 0.0

    # ── Step 1: MILK (0404) — first pass at rate 1.5 ───────────────────────
    planned['MILK (0404)'] = max(min(1.5 * qty_0404, remaining), 0.0)
    remaining -= planned['MILK (0404)']

    # ── Step 2: VEGETABLE OIL (1513) @ 2.26 ───────────────────────────────
    planned['VEGETABLE OIL (1513)'] = max(min(2.26 * qty_1513, remaining), 0.0)
    remaining -= planned['VEGETABLE OIL (1513)']
    rate['VEGETABLE OIL (1513)'] = 2.26

    # ── Step 3: VEGETABLE OIL (15119020) @ 1.1 ────────────────────────────
    planned['VEGETABLE OIL (15119020)'] = max(min(1.1 * qty_15119020, remaining), 0.0)
    remaining -= planned['VEGETABLE OIL (15119020)']
    rate['VEGETABLE OIL (15119020)'] = 1.1

    # ── Step 4: OTHER OILS (15xx) — rate climbs to cap 6.0 ────────────────
    planned['OTHER OILS (15xx)'] = max(min(6.0 * qty_other_oil, remaining), 0.0)
    remaining -= planned['OTHER OILS (15xx)']
    rate['OTHER OILS (15xx)'] = (
        (planned['OTHER OILS (15xx)'] / qty_other_oil) if qty_other_oil else 0.0
    )

    # ── Steps 5 & 6: MILK (0404) bump and MILK (3502) ─────────────────────
    # Combo logic kicks in only when both 0404 and 3502 exist on the
    # licence and the average balance per kg of milk-side qty exceeds 4 —
    # at that point 14.0 × qty_3502 is needed to soak up the balance.
    total_milk_qty = qty_0404 + qty_3502
    avg_balance_per_milk = (initial_balance / total_milk_qty) if total_milk_qty > 0 else 0.0
    combo = (qty_0404 > 0) and (qty_3502 > 0) and (avg_balance_per_milk > 4.0)

    if combo:
        # 3502 first at 14.0 (high rate eats balance fast).
        planned['MILK (3502)'] = max(min(14.0 * qty_3502, remaining), 0.0)
        remaining -= planned['MILK (3502)']
        # Then bump 0404 up to 3.75 on what is left.
        if remaining > 0 and qty_0404 > 0:
            extra = min(3.75 * qty_0404 - planned['MILK (0404)'], remaining)
            if extra > 0:
                planned['MILK (0404)'] += extra
                remaining -= extra
    else:
        # No combo — bump 0404 first.
        if remaining > 0 and qty_0404 > 0:
            extra = min(3.75 * qty_0404 - planned['MILK (0404)'], remaining)
            if extra > 0:
                planned['MILK (0404)'] += extra
                remaining -= extra
        # 3502 only applies when 0404 is absent (otherwise 0404 path
        # has already absorbed everything it can).
        if qty_3502 > 0 and qty_0404 == 0:
            planned['MILK (3502)'] = max(min(14.0 * qty_3502, remaining), 0.0)
            remaining -= planned['MILK (3502)']

    rate['MILK (0404)'] = (planned['MILK (0404)'] / qty_0404) if qty_0404 else 0.0
    rate['MILK (3502)'] = 14.0

    # ── Step 7: WHEAT FLOUR — residual mop-up ─────────────────────────────
    planned['WHEAT FLOUR'] = max(remaining, 0.0)
    rate['WHEAT FLOUR'] = (planned['WHEAT FLOUR'] / wf_qty_f) if wf_qty_f else 0.0

    return planned, rate
