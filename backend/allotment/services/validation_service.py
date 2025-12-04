"""
Allotment validation service.

This module handles validation rules specific to allotments.
"""

from decimal import Decimal
from typing import Tuple, List

from core.constants import DEC_0
from core.utils.decimal_utils import to_decimal


class AllotmentValidationService:
    """
    Service for validating allotment operations.
    """

    @staticmethod
    def validate_allotment_complete(allotment) -> Tuple[bool, List[str]]:
        """
        Check if allotment has all required fields.
        
        Args:
            allotment: AllotmentModel instance
            
        Returns:
            Tuple of (is_complete, missing_fields)
        """
        missing_fields = []

        if not allotment.company:
            missing_fields.append("company")

        if not allotment.item_name:
            missing_fields.append("item_name")

        if not allotment.unit_value_per_unit:
            missing_fields.append("unit_value_per_unit")

        if not allotment.required_value:
            missing_fields.append("required_value")

        if not allotment.balanced_quantity:
            missing_fields.append("balanced_quantity")

        return len(missing_fields) == 0, missing_fields

    @staticmethod
    def validate_can_allocate(allotment) -> Tuple[bool, str]:
        """
        Check if allotment can receive allocations.
        
        Args:
            allotment: AllotmentModel instance
            
        Returns:
            Tuple of (can_allocate, error_message)
        """
        # Check if already converted to BOE
        if allotment.bill_of_entry:
            return False, "Allotment has already been converted to Bill of Entry"

        # Check if all required fields are present
        is_complete, missing = AllotmentValidationService.validate_allotment_complete(allotment)
        if not is_complete:
            return False, f"Allotment is missing required fields: {', '.join(missing)}"

        # Check if balanced quantity is positive
        if to_decimal(allotment.balanced_quantity, DEC_0) <= DEC_0:
            return False, "Balanced quantity must be greater than zero"

        return True, ""

    @staticmethod
    def validate_allocation_within_limits(
            allotment,
            additional_quantity: Decimal,
            additional_value: Decimal
    ) -> Tuple[bool, str]:
        """
        Check if adding allocation would exceed allotment limits.
        
        Args:
            allotment: AllotmentModel instance
            additional_quantity: Quantity to add
            additional_value: Value to add
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        from django.db.models import Sum
        from allotment.models import AllotmentItems

        # Get current allocations
        current_allocations = AllotmentItems.objects.filter(
            allotment=allotment,
            is_boe=False
        ).aggregate(
            total_qty=Sum('qty'),
            total_value=Sum('cif_fc')
        )

        current_qty = to_decimal(current_allocations['total_qty'], DEC_0)
        current_value = to_decimal(current_allocations['total_value'], DEC_0)

        # Calculate new totals
        new_qty = current_qty + to_decimal(additional_quantity, DEC_0)
        new_value = current_value + to_decimal(additional_value, DEC_0)

        # Check quantity limit
        balanced_qty = to_decimal(allotment.balanced_quantity, DEC_0)
        if new_qty > balanced_qty:
            return False, f"Total quantity ({new_qty}) would exceed balanced quantity ({balanced_qty})"

        # Check value limit (with buffer)
        required_value = to_decimal(allotment.required_value, DEC_0)
        required_with_buffer = to_decimal(
            allotment.required_value_with_buffer or (required_value + Decimal('20')),
            DEC_0
        )
        if new_value > required_with_buffer:
            return False, f"Total value ({new_value}) would exceed required value with buffer ({required_with_buffer})"

        return True, ""

    @staticmethod
    def validate_unit_price_matches(
            allotment,
            quantity: Decimal,
            value: Decimal,
            tolerance: Decimal = Decimal('0.01')
    ) -> Tuple[bool, str]:
        """
        Validate that the unit price calculated from quantity and value
        matches the allotment's unit_value_per_unit.
        
        Args:
            allotment: AllotmentModel instance
            quantity: Quantity to allocate
            value: Value to allocate
            tolerance: Allowed difference in unit price
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        expected_unit_price = to_decimal(allotment.unit_value_per_unit, DEC_0)
        qty = to_decimal(quantity, DEC_0)
        val = to_decimal(value, DEC_0)

        if qty <= DEC_0:
            return False, "Quantity must be greater than zero"

        calculated_unit_price = val / qty
        difference = abs(calculated_unit_price - expected_unit_price)

        if difference > tolerance:
            return False, f"Unit price mismatch. Expected: {expected_unit_price}, Calculated: {calculated_unit_price}"

        return True, ""

    @staticmethod
    def check_allotment_fully_allocated(allotment) -> bool:
        """
        Check if allotment is fully allocated.
        
        Args:
            allotment: AllotmentModel instance
            
        Returns:
            True if fully allocated, False otherwise
        """
        from django.db.models import Sum
        from allotment.models import AllotmentItems

        current_value = to_decimal(
            AllotmentItems.objects.filter(
                allotment=allotment,
                is_boe=False
            ).aggregate(
                total=Sum('cif_fc')
            )['total'],
            DEC_0
        )

        required_value = to_decimal(allotment.required_value, DEC_0)

        # Consider fully allocated if within 1% of required value
        return current_value >= (required_value * Decimal('0.99'))

    @staticmethod
    def get_remaining_allocation_capacity(allotment) -> Dict[str, Decimal]:
        """
        Get remaining capacity for allocation.
        
        Args:
            allotment: AllotmentModel instance
            
        Returns:
            Dictionary with remaining_quantity and remaining_value
        """
        from django.db.models import Sum
        from allotment.models import AllotmentItems

        current_allocations = AllotmentItems.objects.filter(
            allotment=allotment,
            is_boe=False
        ).aggregate(
            total_qty=Sum('qty'),
            total_value=Sum('cif_fc')
        )

        current_qty = to_decimal(current_allocations['total_qty'], DEC_0)
        current_value = to_decimal(current_allocations['total_value'], DEC_0)

        balanced_qty = to_decimal(allotment.balanced_quantity, DEC_0)
        required_value = to_decimal(allotment.required_value, DEC_0)
        required_with_buffer = to_decimal(
            allotment.required_value_with_buffer or (required_value + Decimal('20')),
            DEC_0
        )

        remaining_qty = balanced_qty - current_qty
        remaining_value = required_with_buffer - current_value

        return {
            'remaining_quantity': remaining_qty if remaining_qty > DEC_0 else DEC_0,
            'remaining_value': remaining_value if remaining_value > DEC_0 else DEC_0,
            'current_quantity': current_qty,
            'current_value': current_value,
        }
