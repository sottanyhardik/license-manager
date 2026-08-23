from decimal import Decimal

import pytest

from apps.license.services.split_allocation import (
    SplitAllocationMode,
    SplitAllocationService,
    SplitAllocationStatus,
    SplitBucket,
)


def d(value: str) -> Decimal:
    return Decimal(value)


@pytest.fixture
def swp_dwp_buckets():
    return (
        SplitBucket("SWP", d("0"), d("1.50"), d("1.50")),
        SplitBucket("DWP", d("1.50"), d("6.50"), d("6.50")),
    )


def allocate(quantity, value, buckets, **kwargs):
    return SplitAllocationService.allocate(
        quantity=d(quantity), balance_value=d(value), buckets=buckets, **kwargs
    )


def line(result, code):
    return next(item for item in result.allocations if item.bucket_code == code)


@pytest.mark.parametrize(
    ("quantity", "value", "expected_price"),
    [("1000", "1200", "1.2"), ("1000", "1500", "1.5")],
)
def test_all_lower_bucket_including_boundary(swp_dwp_buckets, quantity, value, expected_price):
    result = allocate(quantity, value, swp_dwp_buckets)

    assert result.status == SplitAllocationStatus.SUCCESS
    assert result.mode == SplitAllocationMode.ALL_LOWER
    assert result.allocations == (
        line(result, "SWP"),
    )
    assert line(result, "SWP").quantity == d("1000.000")
    assert line(result, "SWP").value == d(value)
    assert line(result, "SWP").unit_price == d(expected_price)
    assert result.quantity_remaining == 0
    assert result.value_remaining == 0


def test_deterministic_split_exhausts_quantity_and_value(swp_dwp_buckets):
    result = allocate("1000", "3500", swp_dwp_buckets)

    assert result.status == SplitAllocationStatus.SUCCESS
    assert result.mode == SplitAllocationMode.SPLIT
    assert line(result, "SWP").quantity == d("600.000")
    assert line(result, "SWP").unit_price == d("1.50")
    assert line(result, "SWP").value == d("900.00000")
    assert line(result, "DWP").quantity == d("400.000")
    assert line(result, "DWP").unit_price == d("6.50")
    assert line(result, "DWP").value == d("2600.00000")
    assert result.quantity_remaining == 0
    assert result.value_remaining == 0


def test_exact_upper_boundary_is_all_upper(swp_dwp_buckets):
    result = allocate("1000", "6500", swp_dwp_buckets)

    assert result.status == SplitAllocationStatus.SUCCESS
    assert result.mode == SplitAllocationMode.ALL_UPPER
    assert result.allocations == (
        line(result, "DWP"),
    )
    assert line(result, "DWP").quantity == d("1000.000")
    assert line(result, "DWP").unit_price == d("6.50")
    assert line(result, "DWP").value == d("6500.00000")


def test_above_upper_boundary_is_blocked(swp_dwp_buckets):
    result = allocate("1000", "7000", swp_dwp_buckets)

    assert result.status == SplitAllocationStatus.ABOVE_MAX_SUPPORTED_UNIT_PRICE
    assert result.effective_unit_price == d("7")
    assert result.allocations == ()


def test_fractional_split_uses_quantity_precision_and_absorbs_value_residual(swp_dwp_buckets):
    result = allocate("3", "8", swp_dwp_buckets)

    assert result.status == SplitAllocationStatus.SUCCESS
    assert line(result, "DWP").quantity == d("0.700")
    assert line(result, "SWP").quantity == d("2.300")
    assert result.quantity_remaining == 0
    assert result.value_remaining == 0
    assert d("1.50") <= line(result, "DWP").unit_price <= d("6.50")


def test_whole_quantity_returns_precision_conflict_when_no_bucket_can_absorb_residual(swp_dwp_buckets):
    result = allocate(
        "1", "2", swp_dwp_buckets, quantity_quantum=d("1")
    )

    assert result.status == SplitAllocationStatus.PRECISION_CONFLICT
    assert result.allocations == ()


def test_zero_quantity_does_not_divide(swp_dwp_buckets):
    result = allocate("0", "0", swp_dwp_buckets)

    assert result.status == SplitAllocationStatus.ZERO_AVAILABLE_QUANTITY
    assert result.effective_unit_price is None


@pytest.mark.parametrize(("quantity", "value"), [("-1", "1"), ("1", "-1")])
def test_negative_inputs_are_rejected(swp_dwp_buckets, quantity, value):
    result = allocate(quantity, value, swp_dwp_buckets)
    assert result.status == SplitAllocationStatus.INVALID_INPUT


def test_float_inputs_are_rejected(swp_dwp_buckets):
    result = SplitAllocationService.allocate(
        quantity=1000.0, balance_value=d("3500"), buckets=swp_dwp_buckets
    )
    assert result.status == SplitAllocationStatus.INVALID_INPUT


@pytest.mark.parametrize(
    "buckets",
    [
        (),
        (SplitBucket("ONLY", d("0"), d("1"), d("1")),),
        (
            SplitBucket("A", d("0"), d("2"), d("1")),
            SplitBucket("B", d("3"), d("6"), d("6")),
        ),
        (
            SplitBucket("A", d("0"), d("2"), d("3")),
            SplitBucket("B", d("2"), d("6"), d("6")),
        ),
        (
            SplitBucket("SAME", d("0"), d("2"), d("2")),
            SplitBucket("SAME", d("2"), d("6"), d("6")),
        ),
    ],
)
def test_invalid_bucket_configuration_is_rejected(buckets):
    result = allocate("100", "300", buckets)
    assert result.status == SplitAllocationStatus.INVALID_BUCKET_CONFIGURATION


def test_boundaries_are_configuration_driven_not_swp_dwp_specific():
    buckets = (
        SplitBucket("LOW", d("0"), d("2"), d("2")),
        SplitBucket("HIGH", d("2"), d("10"), d("10")),
    )

    result = allocate("100", "600", buckets)

    assert result.status == SplitAllocationStatus.SUCCESS
    assert result.mode == SplitAllocationMode.SPLIT
    assert line(result, "LOW").quantity == d("50.000")
    assert line(result, "HIGH").quantity == d("50.000")
    assert result.quantity_remaining == result.value_remaining == 0
