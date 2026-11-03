"""Licence item movement balance (CIF and quantity), presented as mutually exclusive components.

Pure calculation built on `sale_boe_allocation.compute_utilisation`. It adds no new
arithmetic. It maps the approved result onto the four components the item table shows:

    Original  = authorised amount of the item
    Debited   = BOE amount not covered by any sale, plus over-linked excess
    Allotted  = outstanding allotment reservation (passed in; computed by the caller)
    Invoiced  = sales on the item (full amount). The BOE-covered part is shown as a sub-amount.
    Available = Original − Debited − Allotted − Invoiced   (no zero floor)

Identity: Original = Debited + Allotted + Invoiced + Available. It is checked on every result.

Unmapped amounts (transactions that cannot be attributed to this item) are reported
separately and are never deducted, so they cannot silently change Available.

Units: quantity is only comparable within one declared unit. Mixed units raise.
Only `kg` (case-insensitive) is a verified unit here. Other labels, such as `mts`, are
accepted but marked UNIT_UNVERIFIED so the balance is REVIEW REQUIRED, not RECONCILED.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Sequence

from apps.license.services.sale_boe_allocation import (
    AllocationError,
    BoeEntry,
    BoeLink,
    SaleEntry,
    compute_utilisation,
)

ZERO = Decimal("0")

RECONCILED = "RECONCILED"
REVIEW_REQUIRED = "REVIEW REQUIRED"
OVER_UTILISED = "OVER-UTILISED"
UNMAPPED_ITEM = "UNMAPPED ITEM"
OVER_ALLOCATED = "OVER-ALLOCATED"

UNIT_VERIFIED = "VERIFIED"
UNIT_UNVERIFIED = "UNIT_UNVERIFIED"

_VERIFIED_UNITS = {"kg"}


def normalise_unit(label: Optional[str]) -> tuple[Optional[str], str]:
    """Return (canonical unit, status). Case variants of kg map to kg."""
    if label is None or not str(label).strip():
        return None, UNIT_UNVERIFIED
    key = str(label).strip()
    canonical = key.lower()
    if canonical in _VERIFIED_UNITS:
        return "kg", UNIT_VERIFIED
    return key, UNIT_UNVERIFIED


def ensure_same_unit(units: Sequence[Optional[str]]) -> None:
    """Refuse to combine quantities declared in different units."""
    canon = {normalise_unit(u)[0] for u in units}
    if len(canon) > 1:
        raise AllocationError(f"incompatible quantity units {sorted(map(str, canon))}; conversion is required")


@dataclass(frozen=True)
class ItemMovementBalance:
    measure: str
    unit: Optional[str]
    unit_status: str
    original: Decimal
    debited: Decimal
    allotted: Decimal
    invoiced: Decimal
    invoiced_boe_covered: Decimal
    available: Decimal
    identity_ok: bool
    unmapped: Decimal
    is_over_utilised: bool
    over_utilised_amount: Decimal
    status: str
    flags: tuple[str, ...] = field(default=())


def build_item_balance(
    *,
    measure: str,
    original,
    sales: Sequence[SaleEntry],
    boes: Sequence[BoeEntry],
    links: Sequence[BoeLink] = (),
    outstanding_allotment=ZERO,
    unit: Optional[str] = None,
    unmapped=ZERO,
    extra_flags: Sequence[str] = (),
) -> ItemMovementBalance:
    """Build the four-component balance for one licence item and one measure."""
    canonical_unit, unit_status = normalise_unit(unit) if measure == "qty" else (None, UNIT_VERIFIED)

    result = compute_utilisation(
        measure=measure,
        original=original,
        sales=sales,
        boes=boes,
        links=links,
        outstanding_allotment=outstanding_allotment,
    )

    debited = result.uncovered_boe_total + result.over_linked_total
    allotted = result.outstanding_allotment
    invoiced = result.sold_total
    available = result.original - debited - allotted - invoiced
    identity_ok = result.original == debited + allotted + invoiced + available
    if not identity_ok:  # pragma: no cover - defensive
        raise AllocationError("item identity failed")

    if isinstance(unmapped, (float, bool)):
        raise TypeError("unmapped must be Decimal, int or str")
    unmapped_amt = Decimal(unmapped)
    if unmapped_amt < ZERO:
        raise AllocationError("unmapped amount cannot be negative")

    flags = list(extra_flags)
    if unit_status == UNIT_UNVERIFIED and measure == "qty":
        flags.append(UNIT_UNVERIFIED)
    if unmapped_amt > ZERO:
        flags.append("UNMAPPED_AMOUNT")
    if result.over_linked_total > ZERO:
        flags.append("OVER_LINKED")

    is_over = available < ZERO
    if is_over:
        status = OVER_UTILISED
    elif unmapped_amt > ZERO:
        status = UNMAPPED_ITEM
    elif flags:
        status = REVIEW_REQUIRED
    else:
        status = RECONCILED

    return ItemMovementBalance(
        measure=measure,
        unit=canonical_unit,
        unit_status=unit_status,
        original=result.original,
        debited=debited,
        allotted=allotted,
        invoiced=invoiced,
        invoiced_boe_covered=result.covered_total,
        available=available,
        identity_ok=identity_ok,
        unmapped=unmapped_amt,
        is_over_utilised=is_over,
        over_utilised_amount=-available if is_over else ZERO,
        status=status,
        flags=tuple(flags),
    )


def aggregate_items(items: Sequence[ItemMovementBalance]) -> ItemMovementBalance:
    """Sum item balances of one measure into a licence-level balance. Units must agree."""
    if not items:
        raise AllocationError("nothing to aggregate")
    measures = {i.measure for i in items}
    if len(measures) != 1:
        raise AllocationError("cannot aggregate CIF and quantity together")
    ensure_same_unit([i.unit for i in items])

    original = sum((i.original for i in items), ZERO)
    debited = sum((i.debited for i in items), ZERO)
    allotted = sum((i.allotted for i in items), ZERO)
    invoiced = sum((i.invoiced for i in items), ZERO)
    covered = sum((i.invoiced_boe_covered for i in items), ZERO)
    unmapped = sum((i.unmapped for i in items), ZERO)
    available = original - debited - allotted - invoiced
    flags = sorted({f for i in items for f in i.flags})
    is_over = available < ZERO
    if is_over:
        status = OVER_UTILISED
    elif unmapped > ZERO:
        status = UNMAPPED_ITEM
    elif flags or any(i.status != RECONCILED for i in items):
        status = REVIEW_REQUIRED
    else:
        status = RECONCILED
    return ItemMovementBalance(
        measure=items[0].measure,
        unit=items[0].unit,
        unit_status=UNIT_VERIFIED if all(i.unit_status == UNIT_VERIFIED for i in items) else UNIT_UNVERIFIED,
        original=original,
        debited=debited,
        allotted=allotted,
        invoiced=invoiced,
        invoiced_boe_covered=covered,
        available=available,
        identity_ok=original == debited + allotted + invoiced + available,
        unmapped=unmapped,
        is_over_utilised=is_over,
        over_utilised_amount=-available if is_over else ZERO,
        status=status,
        flags=tuple(flags),
    )
