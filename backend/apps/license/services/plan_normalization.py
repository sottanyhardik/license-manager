"""Shared reporting-safe quantity cap for every planning allocation path."""
from decimal import Decimal

ZERO_QTY = Decimal("0.000")
PLANNING_TOLERANCE = Decimal("10.000")


def normalize_requested_plan(*, requested_qty, available_qty):
    requested = max(Decimal(str(requested_qty or ZERO_QTY)), ZERO_QTY)
    available = max(Decimal(str(available_qty or ZERO_QTY)), ZERO_QTY)
    effective = min(requested, available)
    capped = max(requested - effective, ZERO_QTY)
    return {
        "requested_planned_qty": requested,
        "effective_planned_qty": effective,
        "capped_qty": capped,
        "was_quantity_capped": capped > ZERO_QTY,
        "balance_qty": max(available - effective, ZERO_QTY),
    }
