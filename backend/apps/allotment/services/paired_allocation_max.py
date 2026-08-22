from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_UP

ZERO_QTY = Decimal("0.000")
ZERO_CIF = Decimal("0.00")
MONEY_QUANTUM = Decimal("0.01")
FINAL_SETTLEMENT_BUFFER = Decimal("20.00")


@dataclass(frozen=True)
class PairedAllocationMaximum:
    quantity: Decimal
    cif: Decimal
    quantity_ceiling: Decimal
    cif_ceiling: Decimal
    unit_price: Decimal
    quantity_step: Decimal
    limiting_factor: str
    final_settlement_applied: bool = False
    rounding_adjustment: Decimal = ZERO_CIF


def calculate_paired_allocation_max(*, quantity_ceiling, cif_ceiling, unit_price, quantity_step,
                                    settlement_quantity=None, settlement_cif=None,
                                    settlement_source_cif_ceiling=None):
    quantity_ceiling = max(Decimal(str(quantity_ceiling)), ZERO_QTY)
    cif_ceiling = max(Decimal(str(cif_ceiling)), ZERO_CIF)
    unit_price = Decimal(str(unit_price))
    quantity_step = Decimal(str(quantity_step))
    if quantity_ceiling <= ZERO_QTY or cif_ceiling <= ZERO_CIF or unit_price <= ZERO_CIF or quantity_step <= ZERO_QTY:
        return PairedAllocationMaximum(ZERO_QTY, ZERO_CIF, quantity_ceiling, cif_ceiling, unit_price, quantity_step, "NONE")
    # Both the CIF-derived and quantity-derived caps must honour the same
    # allocation step; otherwise a fractional quantity ceiling can leak into
    # a whole-unit Max response.
    stepped_quantity_ceiling = (quantity_ceiling / quantity_step).to_integral_value(rounding=ROUND_DOWN) * quantity_step
    # A final row may settle the authoritative residual CIF by one cent when
    # its whole-unit quantity exhausts the remaining requirement.  This is a
    # settlement, not a general epsilon for partial allocations.
    if settlement_quantity is not None and settlement_cif is not None:
        target_qty = Decimal(str(settlement_quantity))
        target_cif = Decimal(str(settlement_cif))
        nominal = (target_qty * unit_price).quantize(MONEY_QUANTUM, rounding=ROUND_UP)
        source_cif_ceiling = Decimal(str(
            settlement_source_cif_ceiling if settlement_source_cif_ceiling is not None else cif_ceiling
        ))
        # Close the final whole-unit quantity when the only shortfall is the
        # allotment's value residual.  Licence/PLAN CIF caps remain absolute;
        # only the allotment value is allowed to exceed its residual by the
        # commercial $20 settlement buffer.
        if (target_qty == stepped_quantity_ceiling and target_qty > ZERO_QTY
                and target_cif >= ZERO_CIF and nominal <= source_cif_ceiling
                and abs(nominal - target_cif) <= MONEY_QUANTUM):
            return PairedAllocationMaximum(
                target_qty, target_cif, quantity_ceiling, cif_ceiling, unit_price,
                quantity_step, "FINAL_SETTLEMENT", True, target_cif - nominal,
            )
        if (target_qty == stepped_quantity_ceiling and target_qty > ZERO_QTY
                and target_cif >= ZERO_CIF and nominal <= source_cif_ceiling
                and nominal <= target_cif + FINAL_SETTLEMENT_BUFFER):
            return PairedAllocationMaximum(
                target_qty, nominal, quantity_ceiling, cif_ceiling, unit_price,
                quantity_step, "FINAL_SETTLEMENT", True, nominal - target_cif,
            )
    by_cif = (cif_ceiling / unit_price / quantity_step).to_integral_value(rounding=ROUND_DOWN) * quantity_step
    quantity = max(min(stepped_quantity_ceiling, by_cif), ZERO_QTY)
    # Allocation CIF is conservatively rounded upward to the cent.  This is
    # the established commercial presentation rule and keeps Max/save at the
    # required 2066.75 / 8.821 -> 234 / 2064.12 boundary.
    cif = (quantity * unit_price).quantize(MONEY_QUANTUM, rounding=ROUND_UP)
    while cif > cif_ceiling and quantity > ZERO_QTY:
        quantity -= quantity_step
        cif = (quantity * unit_price).quantize(MONEY_QUANTUM, rounding=ROUND_UP)
    return PairedAllocationMaximum(quantity, cif, quantity_ceiling, cif_ceiling, unit_price, quantity_step, "CIF" if by_cif < quantity_ceiling else "QUANTITY")
