"""
Canonical sale ↔ BOE allocation for one licence (CIF or quantity).

Pure calculation: no database, no ORM. It applies the approved rule:

- A sale is a utilisation of the original licence. Its full amount reduces the
  seller's available balance immediately, whether or not a BOE is linked.
- A BOE linked to a sale is already represented by that sale. It counts only
  within the sold entitlement and is NOT deducted a second time.
- A BOE (or part of a BOE) not covered by any sale is an additional utilisation.
- Linked BOE amounts above a sale's amount (over-linking) are reported as
  OVER-LINKED and counted as uncovered utilisation. They never vanish.
- Available = Original − Utilised. No zero floor. Negative is reported.

Identity used by the implementation (algebraically equal to the rule):

    utilised = Σ sold + Σ uncovered BOE + Σ over-linked + outstanding allotment
             = Σ sold + Σ BOE − Σ covered + outstanding allotment

where, per sale, linked = Σ links to that sale, covered = min(sold, linked),
over = max(0, linked − sold), and per BOE, uncovered = BOE − Σ links from it.

CIF and quantity are computed from their own fields by the same function. One
dimension never derives the other.

Precision: `Decimal` only. `float` and `bool` are rejected. Outputs are quantised
(CIF to 2 dp, quantity to 3 dp, both ROUND_HALF_UP). Intermediate arithmetic is
exact.

Not decided here (see docs/09-module-implementation/licence-sale-boe-open-business-decisions.md):
- Which BOEs stay covered when a sale is reduced below its linked amount.
  This function is deterministic at the sale-aggregate level and does not choose BOEs.
- Whether a BOE may legitimately cover a sale of a different licence item.
  Callers must enforce item mapping before building links.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal, Optional, Sequence

ZERO = Decimal("0")
CIF_QUANTUM = Decimal("0.01")
QTY_QUANTUM = Decimal("0.001")

Measure = Literal["cif", "qty"]

SALE_NOT_LINKED = "NOT_LINKED"
SALE_PARTIALLY_COVERED = "PARTIALLY_COVERED"
SALE_COVERED = "COVERED"
SALE_OVER_LINKED = "OVER_LINKED"

BOE_UNCOVERED = "UNCOVERED_BOE"
BOE_PARTIALLY_COVERED = "PARTIALLY_COVERED"
BOE_COVERED = "COVERED_BY_SALE"


class AllocationError(ValueError):
    """Raised when links break a financial invariant. Nothing is computed."""


def _amount(value, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise TypeError(f"{name} must be Decimal, int or str; got {type(value).__name__}")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise AllocationError(f"{name} is not a number: {value!r}") from exc
    if not amount.is_finite():
        raise AllocationError(f"{name} must be finite; got {value!r}")
    if amount < ZERO:
        raise AllocationError(f"{name} cannot be negative; got {value!r}")
    return amount


@dataclass(frozen=True)
class SaleEntry:
    """A sale (licence utilisation/reservation) to a customer, for one licence item."""

    sale_id: str
    cif: object = ZERO  # Decimal | int | str; validated on use
    qty: object = ZERO


@dataclass(frozen=True)
class BoeEntry:
    """A customer BOE debit, for one licence item."""

    boe_id: str
    cif: object = ZERO
    qty: object = ZERO


@dataclass(frozen=True)
class BoeLink:
    """One allocation record: a portion of a BOE that covers a portion of a sale."""

    link_id: str
    boe_id: str
    sale_id: str
    cif: object = ZERO
    qty: object = ZERO


@dataclass(frozen=True)
class SaleResult:
    sale_id: str
    sold: Decimal
    linked: Decimal
    covered: Decimal
    over_linked: Decimal
    remaining_customer_entitlement: Decimal
    status: str


@dataclass(frozen=True)
class BoeResult:
    boe_id: str
    boe_amount: Decimal
    allocated: Decimal
    uncovered: Decimal
    status: str


@dataclass(frozen=True)
class UtilisationResult:
    measure: str
    original: Decimal
    outstanding_allotment: Decimal
    sold_total: Decimal
    boe_total: Decimal
    covered_total: Decimal
    uncovered_boe_total: Decimal
    over_linked_total: Decimal
    utilised: Decimal
    available: Decimal
    is_over_utilised: bool
    over_utilised_amount: Decimal
    sales: tuple[SaleResult, ...] = ()
    boes: tuple[BoeResult, ...] = ()
    warnings: tuple[str, ...] = field(default=())
    calculated_at: Optional[datetime] = None


def _quantum(measure: str) -> Decimal:
    return CIF_QUANTUM if measure == "cif" else QTY_QUANTUM


def _round(value: Decimal, measure: str) -> Decimal:
    return value.quantize(_quantum(measure), rounding=ROUND_HALF_UP)


def compute_utilisation(
    *,
    measure: Measure,
    original,
    sales: Sequence[SaleEntry],
    boes: Sequence[BoeEntry],
    links: Sequence[BoeLink] = (),
    outstanding_allotment=ZERO,
    calculated_at: Optional[datetime] = None,
) -> UtilisationResult:
    """Apply the sale/BOE rule to one dimension (`cif` or `qty`) of one licence item.

    Raises AllocationError for duplicate ids, unknown references, negative or
    non-finite amounts, or a BOE allocated beyond its own amount. Over-linking a
    sale is NOT an error: it is reported and counted as utilisation.
    """
    if measure not in ("cif", "qty"):
        raise AllocationError(f"measure must be 'cif' or 'qty'; got {measure!r}")

    def field_of(entry) -> object:
        return entry.cif if measure == "cif" else entry.qty

    original_amt = _amount(original, "original")
    allotment_amt = _amount(outstanding_allotment, "outstanding_allotment")

    sale_ids = [s.sale_id for s in sales]
    boe_ids = [b.boe_id for b in boes]
    link_ids = [l.link_id for l in links]
    for label, ids in (("sale", sale_ids), ("BOE", boe_ids), ("link", link_ids)):
        if len(set(ids)) != len(ids):
            raise AllocationError(f"duplicate {label} id")

    sale_amount = {s.sale_id: _amount(field_of(s), f"sale {s.sale_id} {measure}") for s in sales}
    boe_amount = {b.boe_id: _amount(field_of(b), f"BOE {b.boe_id} {measure}") for b in boes}

    linked_by_sale: dict[str, Decimal] = {sid: ZERO for sid in sale_ids}
    allocated_by_boe: dict[str, Decimal] = {bid: ZERO for bid in boe_ids}
    for link in links:
        if link.sale_id not in sale_amount:
            raise AllocationError(f"link {link.link_id} references unknown sale {link.sale_id}")
        if link.boe_id not in boe_amount:
            raise AllocationError(f"link {link.link_id} references unknown BOE {link.boe_id}")
        amount = _amount(field_of(link), f"link {link.link_id} {measure}")
        linked_by_sale[link.sale_id] += amount
        allocated_by_boe[link.boe_id] += amount

    for boe_id, allocated in allocated_by_boe.items():
        if allocated > boe_amount[boe_id]:
            raise AllocationError(
                f"BOE {boe_id} allocated {allocated} {measure} exceeds its own "
                f"{boe_amount[boe_id]}; the same BOE cannot cover more than it contains"
            )

    warnings: list[str] = []
    sale_rows: list[SaleResult] = []
    covered_total = ZERO
    over_total = ZERO
    for sale in sales:
        sold = sale_amount[sale.sale_id]
        linked = linked_by_sale[sale.sale_id]
        covered = min(sold, linked)
        over = max(ZERO, linked - sold)
        covered_total += covered
        over_total += over
        if linked == ZERO:
            status = SALE_NOT_LINKED
        elif linked > sold:
            status = SALE_OVER_LINKED
            warnings.append(f"sale {sale.sale_id} over-linked by {_round(over, measure)} {measure}")
        elif linked == sold:
            status = SALE_COVERED
        else:
            status = SALE_PARTIALLY_COVERED
        sale_rows.append(
            SaleResult(
                sale_id=sale.sale_id,
                sold=_round(sold, measure),
                linked=_round(linked, measure),
                covered=_round(covered, measure),
                over_linked=_round(over, measure),
                remaining_customer_entitlement=_round(sold - covered, measure),
                status=status,
            )
        )

    boe_rows: list[BoeResult] = []
    uncovered_total = ZERO
    for boe in boes:
        amount = boe_amount[boe.boe_id]
        allocated = allocated_by_boe[boe.boe_id]
        uncovered = amount - allocated
        uncovered_total += uncovered
        if allocated == ZERO:
            status = BOE_UNCOVERED
        elif uncovered == ZERO:
            status = BOE_COVERED
        else:
            status = BOE_PARTIALLY_COVERED
        boe_rows.append(
            BoeResult(
                boe_id=boe.boe_id,
                boe_amount=_round(amount, measure),
                allocated=_round(allocated, measure),
                uncovered=_round(uncovered, measure),
                status=status,
            )
        )

    sold_total = sum(sale_amount.values(), ZERO)
    boe_total = sum(boe_amount.values(), ZERO)

    # Identity check: the two forms must agree exactly. A mismatch means an invariant
    # is broken and the result must not be trusted.
    utilised_exact = sold_total + uncovered_total + over_total + allotment_amt
    utilised_identity = sold_total + boe_total - covered_total + allotment_amt
    if utilised_exact != utilised_identity:  # pragma: no cover - defensive
        raise AllocationError("internal identity failed; refusing to report utilisation")

    available = original_amt - utilised_exact
    is_over = available < ZERO

    return UtilisationResult(
        measure=measure,
        original=_round(original_amt, measure),
        outstanding_allotment=_round(allotment_amt, measure),
        sold_total=_round(sold_total, measure),
        boe_total=_round(boe_total, measure),
        covered_total=_round(covered_total, measure),
        uncovered_boe_total=_round(uncovered_total, measure),
        over_linked_total=_round(over_total, measure),
        utilised=_round(utilised_exact, measure),
        available=_round(available, measure),
        is_over_utilised=is_over,
        over_utilised_amount=_round(-available, measure) if is_over else _round(ZERO, measure),
        sales=tuple(sale_rows),
        boes=tuple(boe_rows),
        warnings=tuple(warnings),
        calculated_at=calculated_at or datetime.now(timezone.utc),
    )


def compute_licence_item_balances(*, cif: "dict[str, dict]", qty: "dict[str, dict]"):
    """Run the CIF and quantity dimensions independently for each licence item.

    `cif` and `qty` map item id → kwargs for `compute_utilisation` (without `measure`).
    Returns item id → (cif_result, qty_result). Nothing is derived across measures.
    """
    if set(cif) != set(qty):
        raise AllocationError("CIF and quantity inputs must cover the same licence items")
    out = {}
    for item_id in cif:
        out[item_id] = (
            compute_utilisation(measure="cif", **cif[item_id]),
            compute_utilisation(measure="qty", **qty[item_id]),
        )
    return out
