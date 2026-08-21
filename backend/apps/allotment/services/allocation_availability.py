"""Canonical Decimal availability state for allotment allocation."""
from dataclasses import dataclass
from decimal import Decimal

ZERO_QTY = Decimal("0.000")
ZERO_CIF = Decimal("0.00")


@dataclass(frozen=True)
class AllocationAvailability:
    actual_quantity: Decimal
    actual_cif: Decimal
    plan_quantity: Decimal
    plan_cif: Decimal
    allotment_quantity: Decimal
    allotment_cif: Decimal
    actual_effective_quantity: Decimal
    actual_effective_cif: Decimal
    plan_effective_quantity: Decimal
    plan_effective_cif: Decimal
    actual_paired_quantity: Decimal
    actual_paired_cif: Decimal
    plan_paired_quantity: Decimal
    plan_paired_cif: Decimal


def calculate_allocation_availability(*, actual_quantity, actual_cif,
                                      plan_quantity=None, plan_cif=None,
                                      allotment_quantity=None, allotment_cif=None,
                                      unit_price=ZERO_CIF, quantity_step=Decimal("1.000"),
                                      settlement_quantity=None, settlement_cif=None):
    """Return the only pre-price ceilings used by either debit basis."""
    as_qty = lambda value: max(Decimal(str(value if value is not None else ZERO_QTY)), ZERO_QTY)
    as_cif = lambda value: max(Decimal(str(value if value is not None else ZERO_CIF)), ZERO_CIF)
    actual_quantity, actual_cif = as_qty(actual_quantity), as_cif(actual_cif)
    plan_quantity, plan_cif = as_qty(plan_quantity), as_cif(plan_cif)
    allotment_quantity = as_qty(allotment_quantity if allotment_quantity is not None else actual_quantity)
    allotment_cif = as_cif(allotment_cif if allotment_cif is not None else actual_cif)
    actual_q, actual_v = min(actual_quantity, allotment_quantity), min(actual_cif, allotment_cif)
    from apps.allotment.services.paired_allocation_max import calculate_paired_allocation_max
    actual_pair = calculate_paired_allocation_max(
        quantity_ceiling=actual_q, cif_ceiling=actual_v, unit_price=unit_price,
        quantity_step=quantity_step, settlement_quantity=settlement_quantity, settlement_cif=settlement_cif,
    )
    plan_q, plan_v = min(actual_q, plan_quantity), min(actual_v, plan_cif)
    plan_pair = calculate_paired_allocation_max(
        quantity_ceiling=plan_q, cif_ceiling=plan_v, unit_price=unit_price,
        quantity_step=quantity_step, settlement_quantity=settlement_quantity, settlement_cif=settlement_cif,
    )
    return AllocationAvailability(
        actual_quantity, actual_cif, plan_quantity, plan_cif, allotment_quantity, allotment_cif,
        actual_q, actual_v,
        plan_q, plan_v,
        actual_pair.quantity, actual_pair.cif, plan_pair.quantity, plan_pair.cif,
    )
