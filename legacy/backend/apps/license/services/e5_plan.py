"""
E5 (biscuits) utilization-planning waterfall.

The biscuits norm (E5) allocates the licence balance across a fixed set of
input categories used in biscuit manufacturing. The waterfall is consumed
sequentially — each step uses the remaining balance left after the prior
step. The user-defined waterfall is:

    Step 1  DIETARY FIBRE   @ 2.7    (Item "Walnut" / desc "Dietary Fibre")
    Step 2  SWP             @ 1.5    (Item "SWP"      / HSN|Desc contains 0404)
    Step 3  PKO             @ 2.3    (Item "PKO"      / HSN|Desc contains 1513)
    Step 4  RBD             @ 1.2    (Item "RBD"      / HSN|Desc contains 1511)
    Step 5  OLIVE OIL       @ 5.5    (Item "Olive Oil")
    Step 6  SWP rate recalc          (if balance remains AND SWP qty > 0, fold
                                      the remainder into SWP rate and zero
                                      the balance before WPC)
    Step 7  WPC             @ 0-22   (Item "WPC" AND HSN|Desc contains 3502;
                                      unit price is dynamic in [0, 22], picked
                                      to maximize utilization without breaching
                                      the balance)
    Step 8  WHEAT FLOUR     dynamic  (Item "Wheat Flour"; absorbs any residual
                                      balance — unit price = balance / qty)

Every step validates that the requested utilization fits within the current
balance — if a step would exceed the balance, only the portion that fits is
allocated.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


# Display order of the E5 categories. The Excel export iterates this tuple.
E5_CATS: tuple[str, ...] = (
    'DIETARY FIBRE',
    'SWP',
    'PKO',
    'RBD',
    'OLIVE OIL',
    'WPC',
    'WHEAT FLOUR',
)

# Categories that participate in the totals input dict. Kept identical to
# E5_CATS for the new waterfall — every category collects quantities up front.
E5_PLAN_CATS: tuple[str, ...] = E5_CATS

# Fixed unit prices ($/unit) for the rate-locked steps. WPC and WHEAT FLOUR
# are dynamic so they are not in this map.
E5_UNIT_PRICES: dict[str, Decimal] = {
    'DIETARY FIBRE': Decimal('2.7'),
    'SWP':           Decimal('1.5'),
    'PKO':           Decimal('2.3'),
    'RBD':           Decimal('1.2'),
    'OLIVE OIL':     Decimal('5.5'),
}

# WPC price band — the unit rate is picked dynamically inside this range
# to consume as much of the balance as possible without exceeding it.
WPC_MIN_PRICE: Decimal = Decimal('0')
WPC_MAX_PRICE: Decimal = Decimal('22')

# Hard-coded reference balance used in the original spec for hand-calculations
# and unit tests. Production callers pass the per-licence balance in instead.
BALANCE_CIF_USD: Decimal = Decimal('69046.90')


def _norm(value) -> str:
    """Lower-case + strip for case-insensitive substring matching."""
    return (value or '').strip().lower()


def _item_tokens(item_key: str | None) -> set[str]:
    """Split a comma-joined item key (e.g. 'WPC, MILK SOLIDS') into tokens
    used for whole-word item matching."""
    norm = _norm(item_key)
    if not norm:
        return set()
    return {t.strip() for t in norm.split(',') if t.strip()}


def classify_e5_item(
    item_key: str | None,
    hs_code: str | None,
    description: str | None,
) -> str | None:
    """Return the E5 planner category for an item, or None if no rule matches.

    Precedence (high → low):

      1. Unambiguous full-name item signals (these BEAT any HSN signal so an
         item explicitly named "OLIVE OIL" with an HSN in the 1513 range
         still routes to OLIVE OIL, not PKO):
            * 'dietary fibre' (in item OR description) → DIETARY FIBRE
            * 'olive oil'                              → OLIVE OIL
            * 'wheat flour'                            → WHEAT FLOUR

         NOTE: a bare 'walnut' substring is NOT enough for DIETARY FIBRE —
         the row must be explicitly tagged DIETARY FIBRE. A combo row like
         'FOOD FLAVOUR - E5, FRUIT JUICE - E5, WALNUT - E5' must not be
         folded into DIETARY FIBRE.

      2. WPC compound rule: item is/contains 'wpc' AND (HSN contains '3502'
         OR description contains '3502').

      3. SWP / PKO / RBD — item-acronym OR HSN/description signal:
            * SWP  ← item 'swp'    or HSN/desc contains '0404'
            * PKO  ← item 'pko'    or HSN/desc contains '1513'
            * RBD  ← item 'rbd'    or HSN/desc contains '1511'

      4. Wheat-flour legacy HSN 11010000.
    """
    item = _norm(item_key)
    hs = _norm(hs_code)
    desc = _norm(description)
    tokens = _item_tokens(item_key)

    # 1. Unambiguous full-name item signals — win over HSN.
    if 'dietary fibre' in item or 'dietary fibre' in desc:
        return 'DIETARY FIBRE'
    if 'olive oil' in item:
        return 'OLIVE OIL'
    if 'wheat flour' in item:
        return 'WHEAT FLOUR'

    # 2. WPC compound rule.
    if ('wpc' in tokens or 'wpc' in item) and ('3502' in hs or '3502' in desc):
        return 'WPC'

    # 3. SWP / PKO / RBD — acronym OR HSN/desc.
    if 'swp' in tokens or 'swp' in item or '0404' in hs or '0404' in desc:
        return 'SWP'
    if 'pko' in tokens or 'pko' in item or '1513' in hs or '1513' in desc:
        return 'PKO'
    if 'rbd' in tokens or 'rbd' in item or '1511' in hs or '1511' in desc:
        return 'RBD'

    # 4. Wheat-flour legacy HSN.
    if '11010000' in hs:
        return 'WHEAT FLOUR'

    return None


def classify_e5_hsn(hs_code: str | None) -> str | None:
    """Backwards-compatible HSN-only classifier — kept so callers that only
    know an HSN can still bucket common cases. WPC requires the item name,
    so an HSN-only call will never produce 'WPC'."""
    return classify_e5_item(None, hs_code, None)


def is_wheat_flour(hs_code: str | None) -> bool:
    """Kept for backward compatibility — the new waterfall handles wheat
    flour as a regular category, but legacy callers still ask this directly."""
    return '11010000' in _norm(hs_code)


def _d(value) -> Decimal:
    """Tolerant decimal coercion — handles None / Decimal / str / float."""
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def _allocate_fixed_rate(qty: Decimal, unit_price: Decimal, balance: Decimal) -> Decimal:
    """One waterfall step at a fixed unit price.

    Returns ``min(qty*unit_price, balance)`` clamped at zero. Callers deduct
    the result from the running balance themselves.
    """
    if qty <= 0 or unit_price <= 0 or balance <= 0:
        return Decimal('0')
    requested = qty * unit_price
    return requested if requested <= balance else balance


def _allocate_wpc(qty: Decimal, balance: Decimal) -> tuple[Decimal, Decimal]:
    """Allocate the dynamic-price WPC step.

    Picks a unit price in ``[WPC_MIN_PRICE, WPC_MAX_PRICE]`` to maximize the
    utilization without exceeding the available balance, and returns
    ``(utilization, unit_price)``.

    With a 0 floor the step is always feasible — if the balance is below
    ``qty * MAX_PRICE`` the rate drops to ``balance / qty`` and consumes the
    entire remaining balance; otherwise the rate caps at ``MAX_PRICE`` and
    Wheat Flour absorbs whatever is left.
    """
    if qty <= 0 or balance <= 0:
        return Decimal('0'), WPC_MIN_PRICE
    requested_at_max = qty * WPC_MAX_PRICE
    if balance >= requested_at_max:
        # Cap at the max — Wheat Flour will absorb the rest.
        return requested_at_max, WPC_MAX_PRICE
    # Pick the rate that consumes the balance exactly.
    return balance, balance / qty


def _quantize_money(value: Decimal) -> float:
    """4-dp quantization for display + comparison stability."""
    return float(value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def compute_e5_plan(
    e5_totals: dict[str, float],
    wf_qty=None,
    license_balance=None,
    pool_10pct=None,       # noqa: ARG001 — legacy signature, unused
) -> tuple[dict[str, float], dict[str, float]]:
    """Run the E5 waterfall and return ``(planned_per_cat, rate_per_cat)``.

    ``e5_totals`` maps each category in :data:`E5_CATS` to its aggregated
    quantity. Missing keys default to zero. ``license_balance`` is the
    starting BALANCE_CIF that the waterfall draws down from — when omitted
    the spec's reference balance :data:`BALANCE_CIF_USD` is used.

    ``wf_qty`` is an explicit override for the WHEAT FLOUR quantity (legacy
    call sites passed it as a separate arg). If supplied it wins over any
    ``e5_totals['WHEAT FLOUR']`` value. ``pool_10pct`` is unused (legacy
    signature compatibility).
    """
    initial_balance = _d(license_balance) if license_balance is not None else BALANCE_CIF_USD
    remaining = initial_balance

    qty = {cat: _d(e5_totals.get(cat)) for cat in E5_CATS}
    if wf_qty is not None:
        # Legacy callers passed wheat-flour quantity separately.
        qty['WHEAT FLOUR'] = _d(wf_qty)

    planned: dict[str, Decimal] = {cat: Decimal('0') for cat in E5_CATS}
    rate: dict[str, Decimal] = {cat: E5_UNIT_PRICES.get(cat, Decimal('0')) for cat in E5_CATS}
    rate['WPC'] = WPC_MIN_PRICE  # default until step 7 picks the real rate

    # Steps 1-5 — fixed-rate waterfall.
    for step in ('DIETARY FIBRE', 'SWP', 'PKO', 'RBD', 'OLIVE OIL'):
        used = _allocate_fixed_rate(qty[step], E5_UNIT_PRICES[step], remaining)
        planned[step] = used
        remaining -= used

    # Step 6 — SWP rate recalc. If any balance remains AND SWP exists, the
    # surplus is folded into SWP so the rate effectively rises and the
    # balance ends at zero before WPC.
    if remaining > 0 and qty['SWP'] > 0:
        planned['SWP'] += remaining
        rate['SWP'] = planned['SWP'] / qty['SWP']
        remaining = Decimal('0')

    # Step 7 — WPC with dynamic unit price in [12, 27].
    wpc_used, wpc_price = _allocate_wpc(qty['WPC'], remaining)
    planned['WPC'] = wpc_used
    rate['WPC'] = wpc_price
    remaining -= wpc_used

    # Step 8 — WHEAT FLOUR mop-up at dynamic unit price = balance / qty.
    if remaining > 0 and qty['WHEAT FLOUR'] > 0:
        planned['WHEAT FLOUR'] = remaining
        rate['WHEAT FLOUR'] = remaining / qty['WHEAT FLOUR']
        remaining = Decimal('0')

    # Caller contract is float-keyed; 4-dp quantization keeps display + tests
    # stable while preserving cents-level precision.
    planned_f = {k: _quantize_money(v) for k, v in planned.items()}
    rate_f = {k: _quantize_money(v) for k, v in rate.items()}
    return planned_f, rate_f
