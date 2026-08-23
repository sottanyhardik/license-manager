"""Generic, configuration-driven allocation across two unit-value buckets.

Matching an item is deliberately outside this module.  The allocator only solves
the quantity/value equations for an already matched item, using ``Decimal`` from
input to output.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from enum import Enum
from typing import Sequence


class SplitAllocationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ZERO_AVAILABLE_QUANTITY = "ZERO_AVAILABLE_QUANTITY"
    ABOVE_MAX_SUPPORTED_UNIT_PRICE = "ABOVE_MAX_SUPPORTED_UNIT_PRICE"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_BUCKET_CONFIGURATION = "INVALID_BUCKET_CONFIGURATION"
    PRECISION_CONFLICT = "PRECISION_CONFLICT"


class SplitAllocationMode(str, Enum):
    ALL_LOWER = "ALL_LOWER"
    SPLIT = "SPLIT"
    ALL_UPPER = "ALL_UPPER"


@dataclass(frozen=True)
class SplitBucket:
    code: str
    min_unit_price: Decimal
    max_unit_price: Decimal
    reference_price: Decimal


@dataclass(frozen=True)
class SplitAllocationLine:
    bucket_code: str
    quantity: Decimal
    unit_price: Decimal
    value: Decimal


@dataclass(frozen=True)
class SplitAllocationResult:
    status: SplitAllocationStatus
    quantity: Decimal
    balance_value: Decimal
    effective_unit_price: Decimal | None = None
    mode: SplitAllocationMode | None = None
    allocations: tuple[SplitAllocationLine, ...] = ()
    reason: str | None = None

    @property
    def quantity_remaining(self) -> Decimal:
        return self.quantity - sum((line.quantity for line in self.allocations), Decimal("0"))

    @property
    def value_remaining(self) -> Decimal:
        return self.balance_value - sum((line.value for line in self.allocations), Decimal("0"))


class SplitAllocationService:
    """Allocate quantity and value between two configured price buckets.

    The lower bucket owns values up to its maximum. Values above the upper
    bucket maximum are blocked. Between those boundaries, the two simultaneous
    equations are solved directly and the upper quantity is quantized once.
    Any quantization residual is absorbed by a bucket unit price only when that
    price remains inside its configured band.
    """

    @classmethod
    def allocate(
        cls,
        *,
        quantity: Decimal,
        balance_value: Decimal,
        buckets: Sequence[SplitBucket],
        quantity_quantum: Decimal = Decimal("0.001"),
        rounding: str = ROUND_HALF_UP,
    ) -> SplitAllocationResult:
        invalid = cls._validate(quantity, balance_value, buckets, quantity_quantum)
        if invalid:
            return invalid

        lower, upper = buckets
        quantity = quantity.quantize(quantity_quantum, rounding=rounding)
        if quantity == 0:
            return SplitAllocationResult(
                status=SplitAllocationStatus.ZERO_AVAILABLE_QUANTITY,
                quantity=quantity,
                balance_value=balance_value,
                reason="Available quantity is zero.",
            )

        with localcontext() as context:
            context.prec = 50
            average = balance_value / quantity

            if average > upper.max_unit_price:
                return SplitAllocationResult(
                    status=SplitAllocationStatus.ABOVE_MAX_SUPPORTED_UNIT_PRICE,
                    quantity=quantity,
                    balance_value=balance_value,
                    effective_unit_price=average,
                    reason="Effective unit price exceeds the highest configured bucket maximum.",
                )

            if average <= lower.max_unit_price:
                if average < lower.min_unit_price:
                    return cls._precision_conflict(quantity, balance_value, average)
                line = SplitAllocationLine(lower.code, quantity, average, balance_value)
                return cls._success(quantity, balance_value, average, SplitAllocationMode.ALL_LOWER, (line,))

            denominator = upper.reference_price - lower.reference_price
            raw_upper_qty = (
                balance_value - quantity * lower.reference_price
            ) / denominator
            upper_qty = raw_upper_qty.quantize(quantity_quantum, rounding=rounding)
            upper_qty = min(quantity, max(Decimal("0"), upper_qty))
            lower_qty = quantity - upper_qty

            mode = SplitAllocationMode.SPLIT
            if lower_qty == 0:
                mode = SplitAllocationMode.ALL_UPPER
            lines = cls._absorb_residual(
                balance_value=balance_value,
                lower=lower,
                upper=upper,
                lower_qty=lower_qty,
                upper_qty=upper_qty,
            )
            if lines is None:
                return cls._precision_conflict(quantity, balance_value, average)
            return cls._success(quantity, balance_value, average, mode, lines)

    @staticmethod
    def _validate(quantity, balance_value, buckets, quantity_quantum):
        if not isinstance(quantity, Decimal) or not isinstance(balance_value, Decimal):
            return SplitAllocationResult(
                SplitAllocationStatus.INVALID_INPUT, Decimal("0"), Decimal("0"),
                reason="Quantity and balance value must be Decimal instances.",
            )
        if quantity < 0 or balance_value < 0 or not quantity.is_finite() or not balance_value.is_finite():
            return SplitAllocationResult(
                SplitAllocationStatus.INVALID_INPUT, quantity, balance_value,
                reason="Quantity and balance value must be finite and non-negative.",
            )
        if not isinstance(quantity_quantum, Decimal) or quantity_quantum <= 0 or not quantity_quantum.is_finite():
            return SplitAllocationResult(
                SplitAllocationStatus.INVALID_INPUT, quantity, balance_value,
                reason="Quantity quantum must be a positive finite Decimal.",
            )
        if len(buckets) != 2:
            return SplitAllocationResult(
                SplitAllocationStatus.INVALID_BUCKET_CONFIGURATION, quantity, balance_value,
                reason="Exactly two output buckets are required.",
            )
        lower, upper = buckets
        prices = (
            lower.min_unit_price, lower.max_unit_price, lower.reference_price,
            upper.min_unit_price, upper.max_unit_price, upper.reference_price,
        )
        if (
            not lower.code or not upper.code or lower.code == upper.code
            or any(not isinstance(price, Decimal) or not price.is_finite() for price in prices)
            or lower.min_unit_price < 0
            or lower.min_unit_price > lower.reference_price
            or lower.reference_price > lower.max_unit_price
            or upper.min_unit_price > upper.reference_price
            or upper.reference_price > upper.max_unit_price
            or upper.min_unit_price != lower.max_unit_price
            or upper.max_unit_price <= lower.max_unit_price
            or upper.reference_price <= lower.reference_price
        ):
            return SplitAllocationResult(
                SplitAllocationStatus.INVALID_BUCKET_CONFIGURATION, quantity, balance_value,
                reason="Bucket codes and price bands/reference prices are invalid.",
            )
        return None

    @staticmethod
    def _in_band(bucket: SplitBucket, price: Decimal) -> bool:
        return bucket.min_unit_price <= price <= bucket.max_unit_price

    @classmethod
    def _absorb_residual(cls, *, balance_value, lower, upper, lower_qty, upper_qty):
        # Preferred carrier: upper bucket. Keep lower at its reference price.
        if upper_qty > 0:
            lower_value = lower_qty * lower.reference_price
            upper_value = balance_value - lower_value
            upper_price = upper_value / upper_qty
            if cls._in_band(upper, upper_price):
                lines = []
                if lower_qty:
                    lines.append(SplitAllocationLine(lower.code, lower_qty, lower.reference_price, lower_value))
                lines.append(SplitAllocationLine(upper.code, upper_qty, upper_price, upper_value))
                return tuple(lines)

        # Fallback carrier: lower bucket. Keep upper at its reference price.
        if lower_qty > 0:
            upper_value = upper_qty * upper.reference_price
            lower_value = balance_value - upper_value
            lower_price = lower_value / lower_qty
            if cls._in_band(lower, lower_price):
                lines = [SplitAllocationLine(lower.code, lower_qty, lower_price, lower_value)]
                if upper_qty:
                    lines.append(SplitAllocationLine(upper.code, upper_qty, upper.reference_price, upper_value))
                return tuple(lines)
        return None

    @staticmethod
    def _success(quantity, value, average, mode, lines):
        result = SplitAllocationResult(
            SplitAllocationStatus.SUCCESS, quantity, value, average, mode, tuple(lines)
        )
        assert result.quantity_remaining == 0
        assert result.value_remaining == 0
        return result

    @staticmethod
    def _precision_conflict(quantity, value, average):
        return SplitAllocationResult(
            SplitAllocationStatus.PRECISION_CONFLICT,
            quantity,
            value,
            average,
            reason="Quantity precision cannot conserve value within the configured bucket bands.",
        )
