from decimal import Decimal

from apps.license.services.percentage_group_solver import solve_balancing_price_group


def test_percentage_group_uses_exact_aggregate_quantity_and_emits_zero_member():
    """A group cap is applied after actuals, without integer truncation."""
    result = solve_balancing_price_group(
        base_qty=Decimal("777589.140"),
        group_available_qty=Decimal("354798.140"),
        group_available_cif=Decimal("1797384.83"),
        members=[
            {
                "percentage": Decimal("60"),
                "configured_max_unit_price": Decimal("5.00"),
                "actual_used_qty": Decimal("34296.000"),
                "actual_used_cif": Decimal("199359.82"),
                "member_sequence": 0,
            },
            {
                "percentage": Decimal("40"),
                "configured_max_unit_price": Decimal("1.80"),
                "actual_used_qty": Decimal("388495.000"),
                "actual_used_cif": Decimal("699291.00"),
                "member_sequence": 1,
            },
        ],
    )

    olive, pko = result["members"]
    assert olive["percentage_target_qty"] == Decimal("466553.484")
    assert pko["percentage_target_qty"] == Decimal("311035.656")
    assert olive["remaining_qty"] == Decimal("354798.140")
    assert pko["remaining_qty"] == Decimal("0.000")
    assert olive["remaining_cif"] == Decimal("1773990.70")
    assert pko["remaining_cif"] == Decimal("0.00")
    assert result["unallocated_cif"] == Decimal("23394.13")
