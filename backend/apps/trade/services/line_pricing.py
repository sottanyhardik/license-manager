"""
Server-side pricing rules for `LicenseTradeLine` (owner-approved T1–T4, 2026-11-17;
docs/decisions/2026-11-17-trade-line-pricing-and-m2m-consumption.md).

T1  The server is authoritative for `amount_inr`: on every API write that creates a
    line or changes one of its pricing inputs, `amount_inr = compute_amount()` —
    unless the line carries an explicit `amount_override` (with a reason), in which
    case the supplied amount is kept. Lines whose pricing inputs did not change are
    left exactly as stored (historical rows are never recomputed silently).
T2  `compute_amount` uses the stored 3-dp `rate_inr_per_kg` (no 2-dp truncation) —
    implemented in `LicenseTradeLine.compute_amount`.
T3  Line amounts are rounded to paise (2 dp, ROUND_HALF_UP); the trade header keeps
    rounding the total to the rupee with an explicit `roundoff`.
T4  CIF INR consistency is checked, not enforced: when `cif_fc`, `exc_rate` and
    `cif_inr` are all non-zero and `|cif_inr − q2(cif_fc × exc_rate)| > 1.00` INR,
    the line is accepted and an additive warning is reported.

Applied only at the API write boundary (trade create / nested update / `lines/`
endpoint). Model `save()` behaviour for other writers (management commands, tests,
counterpart clones that copy an already-priced line) is unchanged.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

CIF_INR_TOLERANCE = Decimal("1.00")

# Fields whose change makes a line "changed" for T1.
PRICING_FIELDS = (
    "mode", "qty_kg", "rate_inr_per_kg", "cif_inr", "fob_inr", "pct", "amount_inr", "amount_override",
)


def _dec(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def pricing_snapshot(line: Any) -> Dict[str, Any]:
    """Comparable snapshot of a line's pricing inputs (Decimals normalised)."""
    snap: Dict[str, Any] = {}
    for field in PRICING_FIELDS:
        value = getattr(line, field, None)
        snap[field] = value if field in ("mode", "amount_override") else _dec(value)
    return snap


def apply_server_pricing(line: Any, previous: Optional[Dict[str, Any]]) -> bool:
    """
    T1: set `line.amount_inr` from the server formula when the line is new
    (`previous is None`) or its pricing inputs changed, unless `amount_override`.

    Returns True when `amount_inr` was changed on the instance (caller saves).
    """
    if getattr(line, "amount_override", False):
        return False
    if previous is not None and pricing_snapshot(line) == previous:
        return False
    computed = line.compute_amount()
    if _dec(line.amount_inr) == computed:
        return False
    line.amount_inr = computed
    return True


def cif_inr_warnings(line: Any) -> List[str]:
    """T4: additive, non-blocking CIF INR consistency warnings for one line."""
    cif_fc = _dec(getattr(line, "cif_fc", None))
    exc_rate = _dec(getattr(line, "exc_rate", None))
    cif_inr = _dec(getattr(line, "cif_inr", None))
    if not (cif_fc and exc_rate and cif_inr):
        return []
    expected = (cif_fc * exc_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # q2 semantics
    diff = (cif_inr - expected).copy_abs()
    if diff <= CIF_INR_TOLERANCE:
        return []
    return [
        f"cif_inr {cif_inr} differs from cif_fc × exc_rate = {expected} by {diff} "
        f"(tolerance {CIF_INR_TOLERANCE} INR)."
    ]
