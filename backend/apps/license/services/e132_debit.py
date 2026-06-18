"""
E132 (namkeen) sequential debit — consume the whole Balance CIF.

The objective is to **debit as much of the licence's Balance CIF as possible**.
Every step has a *maximum* unit price; the actual unit price floats in
``[0, max]``. Each matched item debits ``quantity × rate`` from the running
Balance CIF where:

  * if ``quantity × max`` fits the remaining balance → use ``max``;
  * otherwise the rate **drops** to ``balance / quantity`` (≤ max) so the item
    consumes exactly the remaining balance.

There is **no hard stop**: once the balance reaches zero, later items simply
debit nothing (their quantity is "wasted" — acceptable, since the goal is to
exhaust the *balance*, not the quantity).

Processing order (the user-defined spec):

    Step 1  0401 / 0405 / 0406   desc only      max  $5.0     ┐ priority "fat
    Step 2  1513                 desc or HSN     max  $2.7     │ slot": the first
    Step 3  1511                 desc or HSN     max  $1.2     ┘ group with a
                                                                 match debits;
                                                                 the others are
                                                                 skipped.
    Step 4  0802                 desc or HSN     max  $10      ┐ always run,
    Step 5  7607                 desc or HSN     max  $4.5     │ in order,
    Step 6  1104                 desc or HSN     max  $0.6     ┘ each item.

The caller decides which quantity to pass per item (the reports pass the
available / balance quantity). If no item matches any of the six codes the
caller shows: "No applicable E132 norm found. Balance CIF $ remains unchanged."
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


# An item is SUCCESS when it received a debit; EXHAUSTED when the balance was
# already fully consumed before it (its quantity goes unused).
SUCCESS = "Success"
EXHAUSTED = "Balance Exhausted"

NO_MATCH_MESSAGE = "No applicable E132 norm found. Balance CIF $ remains unchanged."

# Ordered step rules. `group='fat'` marks the priority cascade (steps 1-3 — only
# the first group with a match debits); `group='ind'` steps always run.
# `max` is the maximum unit price; the effective rate is in [0, max].
E132_STEPS: tuple[dict, ...] = (
    {'key': 'S1', 'label': 'MILK FATS',      'codes': ('0401', '0405', '0406'),
     'match': 'desc',    'group': 'fat', 'max': Decimal('5')},
    {'key': 'S2', 'label': 'PKO',            'codes': ('1513',),
     'match': 'hsndesc', 'group': 'fat', 'max': Decimal('2.7')},
    {'key': 'S3', 'label': 'RBD',            'codes': ('1511',),
     'match': 'hsndesc', 'group': 'fat', 'max': Decimal('1.2')},
    {'key': 'S4', 'label': 'CASHEW',         'codes': ('0802',),
     'match': 'hsndesc', 'group': 'ind', 'max': Decimal('10')},
    {'key': 'S5', 'label': 'ALUMINIUM FOIL', 'codes': ('7607',),
     'match': 'hsndesc', 'group': 'ind', 'max': Decimal('4.5')},
    {'key': 'S6', 'label': 'CEREAL FLAKES',  'codes': ('1104',),
     'match': 'hsndesc', 'group': 'ind', 'max': Decimal('0.6')},
)

_STEP_BY_KEY = {s['key']: s for s in E132_STEPS}
_FAT_KEYS = tuple(s['key'] for s in E132_STEPS if s['group'] == 'fat')
_IND_KEYS = tuple(s['key'] for s in E132_STEPS if s['group'] == 'ind')


def _norm(value) -> str:
    return (value or '').strip().lower()


def _d(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def _q(value: Decimal) -> float:
    """4-dp quantization for display + comparison stability."""
    return float(_d(value).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def classify_e132_step(item_key, hs_code, description):
    """Return the matching step dict (in spec order) for an item, or None.

    Step 1 matches the dairy codes in the **description only**; every other step
    matches the code in the **HSN code or description**. Precedence is step
    order, so an item that matches more than one code is bucketed to the
    earliest step.
    """
    hs = _norm(hs_code)
    desc = _norm(description)
    item = _norm(item_key)
    for step in E132_STEPS:
        for code in step['codes']:
            if step['match'] == 'desc':
                if code in desc:
                    return step
            else:  # 'hsndesc'
                if code in hs or code in desc or code in item:
                    return step
    return None


def _matched_code_label(step) -> str:
    return ' / '.join(step['codes'])


def _make_row(item, step, unit_rate, debit, prev, new, status) -> dict:
    return {
        'product_code': _matched_code_label(step),
        'step': step['key'],
        'label': step['label'],
        'item_name': item.get('item_name', ''),
        'description': item.get('description', ''),
        'hs_code': item.get('hs_code', ''),
        'total_quantity': _q(item.get('quantity')),
        'unit_rate': _q(unit_rate),
        'debit_amount': _q(debit),
        'previous_balance': _q(prev),
        'new_balance': _q(new),
        'status': status,
    }


def _process_item(item, step, balance):
    """Debit one matched item against ``balance`` at a rate in ``[0, max]``.

    Uses the max rate when ``qty × max`` fits; otherwise drops the rate to
    ``balance / qty`` so the item consumes exactly the remaining balance.
    Returns ``(row, new_balance)``. Never debits more than the balance, so the
    running total can never exceed the opening balance.
    """
    qty = _d(item.get('quantity'))
    mx = step['max']
    prev = balance

    if balance <= 0:
        # Balance already fully debited — this item's quantity is unused.
        return _make_row(item, step, Decimal('0'), Decimal('0'), prev, prev, EXHAUSTED), balance
    if qty <= 0 or mx <= 0:
        return _make_row(item, step, mx, Decimal('0'), prev, balance, SUCCESS), balance

    if qty * mx <= balance:
        rate, debit = mx, qty * mx
    else:
        rate, debit = balance / qty, balance      # drop rate to consume balance
    return _make_row(item, step, rate, debit, prev, balance - debit, SUCCESS), balance - debit


def compute_e132_debit(items, balance_cif):
    """Run the E132 balance-consuming debit sequence.

    Args:
        items: iterable of dicts with keys ``quantity``, ``hs_code``,
            ``description`` and (optionally) ``item_name``. Quantity is whatever
            the caller chooses to debit (the reports pass the balance quantity).
        balance_cif: opening Balance CIF $ the sequence draws down from.

    Returns a dict:
        ``rows``           – per-matched-item result rows (in processing order),
        ``opening_balance``,
        ``final_balance``  – balance left after the last debit (0 when the whole
                             balance was consumed),
        ``total_debited``  – sum of applied debits (== opening − final_balance),
        ``fully_consumed`` – True when the balance reached zero,
        ``any_match``      – False when no item matched any of the six codes
                             (caller shows :data:`NO_MATCH_MESSAGE`).
    """
    opening = _d(balance_cif)
    balance = opening

    buckets: dict[str, list] = {s['key']: [] for s in E132_STEPS}
    for it in items:
        step = classify_e132_step(it.get('item_name'), it.get('hs_code'), it.get('description'))
        if step is not None:
            buckets[step['key']].append(it)

    # Priority "fat slot": only the first of steps 1-3 with a match is processed.
    active_fat = next((k for k in _FAT_KEYS if buckets[k]), None)
    order = ([active_fat] if active_fat else []) + list(_IND_KEYS)
    any_match = bool(active_fat) or any(buckets[k] for k in _IND_KEYS)

    rows: list[dict] = []
    for step_key in order:
        step = _STEP_BY_KEY[step_key]
        for it in buckets[step_key]:
            row, balance = _process_item(it, step, balance)
            rows.append(row)

    return {
        'rows': rows,
        'opening_balance': _q(opening),
        'final_balance': _q(balance),
        'total_debited': _q(opening - balance),
        'fully_consumed': balance <= 0,
        'any_match': any_match,
    }
