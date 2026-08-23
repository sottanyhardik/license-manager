"""Regression shape for split-parent reconciliation (without production fixture data)."""
from decimal import Decimal

from apps.license.services.planning_usage_reconciliation import reconcile_split_allocation


def test_milk_split_children_reconcile_exactly_to_the_parent_source_quantity():
    result = reconcile_split_allocation(Decimal("51970.000"), [
        {"key": "DWP", "theoretical_qty": Decimal("48368.483")},
        {"key": "SWP", "theoretical_qty": Decimal("3601.517")},
    ], {"DWP": Decimal("0"), "SWP": Decimal("0")})
    assert result["theoretical_total"] == Decimal("51970.000")
    assert result["reconciled_total"] == Decimal("51970.000")
    assert result["group_excess_quantity"] == Decimal("0")
