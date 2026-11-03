"""
Canonical licence financial position (Licence Management V2, business rule D-1).

Pure calculation: no database access, no ORM, no floor at zero. Callers
supply the three utilisation categories already derived from the database;
this module only applies the approved arithmetic and the over-utilisation
presentation rules.

Approved rule (D-1, final):

    Utilised CIF  = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE
    Available CIF = Original CIF - Utilised CIF

Mandatory behaviour:

- Negative available CIF is returned as is; it is never floored at zero.
- Over-utilisation is flagged explicitly and its amount is returned.
- Each CIF amount must appear in exactly one category. The caller is
  responsible for disjointness (see `docs/09-module-implementation/`
  for the reconciliation rules). Passing overlapping amounts double-counts.

Precision:

- Inputs must be `Decimal`, `int` or `str`. `float` is rejected so that no
  binary floating-point value can enter a money calculation.
- Arithmetic is exact. Only the returned amounts are quantized to 2 dp,
  ROUND_HALF_UP, for display and storage.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")


def _as_amount(value, name: str) -> Decimal:
    """Return `value` as a finite, non-negative Decimal, or raise."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise TypeError(
            f"{name} must be a Decimal, int or str; got {type(value).__name__}. "
            "Floats are rejected to keep money arithmetic exact."
        )
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} is not a number: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"{name} must be finite; got {value!r}")
    if amount < ZERO:
        raise ValueError(
            f"{name} cannot be negative; over-utilisation is derived from the "
            "difference, not supplied as a negative category amount."
        )
    return amount


def _cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LicenseFinancialPosition:
    """Structured result of the canonical D-1 calculation (amounts in `currency`)."""

    currency: str
    original_cif: Decimal
    boe_cif: Decimal
    allotment_cif: Decimal
    billed_without_boe_cif: Decimal
    utilised_cif: Decimal
    available_cif: Decimal
    is_over_utilised: bool
    over_utilisation_cif: Decimal
    # Utilised as a share of Original CIF. Not clamped: values above 100 are
    # over-utilisation. None when Original CIF is zero (no authorisation).
    utilisation_pct: Optional[Decimal]
    calculated_at: datetime
    reconciliation_warnings: tuple[str, ...] = ()


def calculate_financial_position(
    *,
    original_cif,
    boe_cif,
    allotment_cif,
    billed_without_boe_cif,
    currency: str = "FC",
    calculated_at: Optional[datetime] = None,
    reconciliation_warnings: tuple[str, ...] = (),
) -> LicenseFinancialPosition:
    """Apply D-1 to disjoint, non-negative category amounts.

    Args:
        original_cif: Authorised CIF of the licence.
        boe_cif: CIF represented by actual BOE transactions.
        allotment_cif: Outstanding CIF reservation not represented by a BOE.
        billed_without_boe_cif: Invoiced CIF not yet represented by a BOE.
        currency: Label for every amount. No conversion is performed here.
        calculated_at: Timestamp of the calculation (defaults to now, UTC).
        reconciliation_warnings: Caller-supplied notes about the inputs.

    Returns:
        A `LicenseFinancialPosition`. `available_cif` may be negative.
    """
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("currency must be a non-empty string")

    original = _as_amount(original_cif, "original_cif")
    boe = _as_amount(boe_cif, "boe_cif")
    allotment = _as_amount(allotment_cif, "allotment_cif")
    billed = _as_amount(billed_without_boe_cif, "billed_without_boe_cif")

    utilised = boe + allotment + billed
    available = original - utilised
    is_over = available < ZERO

    pct = None
    if original > ZERO:
        pct = _cents(utilised * HUNDRED / original)

    return LicenseFinancialPosition(
        currency=currency.strip(),
        original_cif=_cents(original),
        boe_cif=_cents(boe),
        allotment_cif=_cents(allotment),
        billed_without_boe_cif=_cents(billed),
        utilised_cif=_cents(utilised),
        available_cif=_cents(available),
        is_over_utilised=is_over,
        over_utilisation_cif=_cents(-available) if is_over else ZERO.quantize(CENT),
        utilisation_pct=pct,
        calculated_at=calculated_at or datetime.now(timezone.utc),
        reconciliation_warnings=tuple(reconciliation_warnings),
    )
