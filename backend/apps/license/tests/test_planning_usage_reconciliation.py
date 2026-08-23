"""Usage reconciliation uses explicit source/target identities, never name families."""
from decimal import Decimal

from apps.license.services.planning_usage_reconciliation import reconcile_split_allocation


def test_split_reconciliation_moves_unused_theoretical_quantity_to_actual_commitment():
    result = reconcile_split_allocation(Decimal("100"), [
        {"key": "PKO", "theoretical_qty": Decimal("60")},
        {"key": "CHEESE", "theoretical_qty": Decimal("40")},
    ], {"PKO": Decimal("30"), "CHEESE": Decimal("70")})
    assert {row["key"]: row["reconciled_qty"] for row in result["rows"]} == {
        "PKO": Decimal("30"), "CHEESE": Decimal("70"),
    }
    assert result["group_excess_quantity"] == Decimal("0")
    assert result["manual_review_required"] is False


def test_reconciliation_reports_excess_instead_of_overplanning_source_capacity():
    result = reconcile_split_allocation(Decimal("100"), [
        {"key": "PKO", "theoretical_qty": Decimal("60")},
        {"key": "CHEESE", "theoretical_qty": Decimal("40")},
    ], {"PKO": Decimal("80"), "CHEESE": Decimal("50")})
    assert result["reconciled_total"] == Decimal("100")
    assert result["group_excess_quantity"] == Decimal("30")
    assert result["manual_review_required"] is True
