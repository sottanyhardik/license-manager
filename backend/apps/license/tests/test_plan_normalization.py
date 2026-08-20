from decimal import Decimal

from apps.license.services.plan_normalization import normalize_requested_plan


def test_requested_quantity_is_capped_to_available_quantity():
    position = normalize_requested_plan(
        requested_qty=Decimal("620.000"), available_qty=Decimal("613.180"),
    )
    assert position["effective_planned_qty"] == Decimal("613.180")
    assert position["capped_qty"] == Decimal("6.820")
    assert position["balance_qty"] == Decimal("0.000")
    assert position["was_quantity_capped"] is True


def test_normalization_never_returns_negative_quantities():
    position = normalize_requested_plan(requested_qty=Decimal("-1"), available_qty=None)
    assert all(value >= Decimal("0") for key, value in position.items() if key != "was_quantity_capped")
