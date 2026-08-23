"""Authoritative, data-independent regression for the unit-value solver."""
from decimal import Decimal

from apps.license.services.sion_planning_execution import solve_unit_value_mix


class _Row:
    def __init__(self, pk, price, priority):
        self.pk = pk
        self.priority = priority
        self.preferred_unit_price = Decimal(price)
        self.max_unit_price = Decimal(price)


def test_exact_milk_two_price_mix_consumes_all_quantity_and_cif():
    swp = _Row(1, "1.50", 1)
    dwp = _Row(2, "6.50", 2)

    allocation = dict(solve_unit_value_mix(
        [swp, dwp], Decimal("41822.000"), Decimal("151803.65"),
    ))

    assert allocation[swp] == Decimal("24007.870")
    assert allocation[dwp] == Decimal("17814.130")
    assert sum(allocation.values()) == Decimal("41822.000")
    assert (
        allocation[swp] * Decimal("1.50")
        + allocation[dwp] * Decimal("6.50")
    ) == Decimal("151803.650")


def test_approved_license_total_regression():
    assert (
        Decimal("298141.43") + Decimal("5948.10") + Decimal("151803.65")
    ) == Decimal("455893.18")
