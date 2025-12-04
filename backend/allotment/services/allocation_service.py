"""
Allocation service for managing allotment operations.

This module handles the business logic for:
- Allocating license items to allotments
- Calculating maximum allocation amounts
- Updating balances after allocation
"""

from decimal import Decimal
from typing import Dict, Tuple, Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from core.constants import DEC_0
from core.utils.decimal_utils import to_decimal, decimal_division


class AllocationService:
    """
    Service for handling allotment allocation operations.
    """

    @staticmethod
    def calculate_max_allocation(
            allotment,
            import_item,
            unit_price: Optional[Decimal] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate maximum quantity and value that can be allocated.
        
        Considers multiple constraints:
        - Available quantity on license item
        - Available CIF balance on license item
        - Required value for allotment (with buffer)
        - Balanced quantity remaining on allotment
        
        Args:
            allotment: AllotmentModel instance
            import_item: LicenseImportItemsModel instance
            unit_price: Price per unit (uses allotment.unit_value_per_unit if not provided)
            
        Returns:
            Dictionary with max_quantity and max_value
        """
        from license.services.balance_calculator import ItemBalanceCalculator

        # Get unit price
        if unit_price is None:
            unit_price = to_decimal(allotment.unit_value_per_unit, DEC_0)

        if unit_price <= DEC_0:
            return {'max_quantity': DEC_0, 'max_value': DEC_0}

        # Get allotment constraints
        balanced_qty = to_decimal(allotment.balanced_quantity or 0, DEC_0)
        required_value = to_decimal(allotment.required_value or 0, DEC_0)
        required_value_with_buffer = to_decimal(
            allotment.required_value_with_buffer or (required_value + Decimal('20')),
            DEC_0
        )
        allotted_value = to_decimal(allotment.allotted_value or 0, DEC_0)
        balanced_value_with_buffer = required_value_with_buffer - allotted_value

        # Get license item constraints
        available_qty = ItemBalanceCalculator.calculate_available_quantity(import_item)
        balance_cif_fc = ItemBalanceCalculator.calculate_item_balance(import_item)

        # Start with minimum of balanced quantity and available quantity
        max_qty = min(balanced_qty, available_qty)
        max_value = max_qty * unit_price

        # Check if value exceeds available CIF FC
        if max_value > balance_cif_fc:
            max_qty = decimal_division(balance_cif_fc, unit_price, decimals=3)
            max_value = max_qty * unit_price

        # Check if value exceeds balanced value with buffer
        if max_value > balanced_value_with_buffer:
            max_qty = decimal_division(balanced_value_with_buffer, unit_price, decimals=3)
            max_value = max_qty * unit_price

        return {
            'max_quantity': max_qty if max_qty > DEC_0 else DEC_0,
            'max_value': max_value if max_value > DEC_0 else DEC_0,
        }

    @staticmethod
    def calculate_allocation_value(
            quantity: Decimal,
            unit_price: Decimal
    ) -> Decimal:
        """
        Calculate value for given quantity and unit price.
        
        Args:
            quantity: Quantity to allocate
            unit_price: Price per unit
            
        Returns:
            Total value as Decimal
        """
        qty = to_decimal(quantity, DEC_0)
        price = to_decimal(unit_price, DEC_0)
        return qty * price

    @classmethod
    def validate_allocation_amount(
            cls,
            allotment,
            import_item,
            quantity: Decimal,
            value: Decimal
    ) -> Tuple[bool, str]:
        """
        Validate that allocation amount is within limits.
        
        Args:
            allotment: AllotmentModel instance
            import_item: LicenseImportItemsModel instance
            quantity: Quantity to allocate
            value: Value to allocate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        qty = to_decimal(quantity, DEC_0)
        val = to_decimal(value, DEC_0)

        if qty <= DEC_0:
            return False, "Quantity must be greater than zero"

        if val <= DEC_0:
            return False, "Value must be greater than zero"

        # Calculate maximum allowed
        max_allocation = cls.calculate_max_allocation(allotment, import_item)

        if qty > max_allocation['max_quantity']:
            return False, f"Quantity exceeds maximum allowed: {max_allocation['max_quantity']}"

        if val > max_allocation['max_value']:
            return False, f"Value exceeds maximum allowed: {max_allocation['max_value']}"

        return True, ""

    @staticmethod
    @transaction.atomic
    def allocate_item(
            allotment,
            import_item,
            quantity: Decimal,
            cif_fc: Decimal,
            user=None
    ) -> 'AllotmentItems':
        """
        Allocate a license item to an allotment.
        
        Creates an AllotmentItems record linking the allotment to the license item.
        
        Args:
            allotment: AllotmentModel instance
            import_item: LicenseImportItemsModel instance
            quantity: Quantity to allocate
            cif_fc: CIF value to allocate
            user: User performing the allocation (optional)
            
        Returns:
            Created AllotmentItems instance
            
        Raises:
            ValidationError: If allocation is invalid
        """
        from allotment.models import AllotmentItems
        from license.services.validation_service import LicenseValidationService

        # Validate allocation
        is_valid, errors = LicenseValidationService.validate_allocation(
            import_item.license,
            import_item,
            quantity,
            cif_fc
        )

        if not is_valid:
            raise ValidationError("; ".join(errors))

        # Create allocation item
        allocation_item = AllotmentItems.objects.create(
            allotment=allotment,
            item=import_item,
            qty=to_decimal(quantity, DEC_0),
            cif_fc=to_decimal(cif_fc, DEC_0),
            is_boe=False,
            created_by=user
        )

        return allocation_item

    @staticmethod
    @transaction.atomic
    def deallocate_item(allocation_item) -> None:
        """
        Remove an allocation (delete AllotmentItems record).
        
        Args:
            allocation_item: AllotmentItems instance to delete
            
        Raises:
            ValidationError: If deallocation is not allowed
        """
        # Check if allocation has been converted to BOE
        if allocation_item.is_boe or allocation_item.allotment.bill_of_entry:
            raise ValidationError(
                "Cannot delete allocation that has been converted to Bill of Entry"
            )

        # Delete the allocation
        allocation_item.delete()

    @staticmethod
    @transaction.atomic
    def update_allocation(
            allocation_item,
            quantity: Optional[Decimal] = None,
            cif_fc: Optional[Decimal] = None
    ) -> 'AllotmentItems':
        """
        Update an existing allocation.
        
        Args:
            allocation_item: AllotmentItems instance to update
            quantity: New quantity (None to keep existing)
            cif_fc: New CIF value (None to keep existing)
            
        Returns:
            Updated AllotmentItems instance
            
        Raises:
            ValidationError: If update is invalid
        """
        from license.services.validation_service import LicenseValidationService

        # Check if allocation has been converted to BOE
        if allocation_item.is_boe or allocation_item.allotment.bill_of_entry:
            raise ValidationError(
                "Cannot update allocation that has been converted to Bill of Entry"
            )

        # Use existing values if not provided
        new_quantity = to_decimal(quantity, allocation_item.qty) if quantity is not None else allocation_item.qty
        new_cif_fc = to_decimal(cif_fc, allocation_item.cif_fc) if cif_fc is not None else allocation_item.cif_fc

        # Validate new values
        is_valid, errors = LicenseValidationService.validate_allocation(
            allocation_item.item.license,
            allocation_item.item,
            new_quantity,
            new_cif_fc
        )

        if not is_valid:
            raise ValidationError("; ".join(errors))

        # Update allocation
        allocation_item.qty = new_quantity
        allocation_item.cif_fc = new_cif_fc
        allocation_item.save()

        return allocation_item

    @staticmethod
    def get_allocation_summary(allotment) -> Dict[str, any]:
        """
        Get summary of allocations for an allotment.
        
        Args:
            allotment: AllotmentModel instance
            
        Returns:
            Dictionary with allocation statistics
        """
        from django.db.models import Sum, Count
        from allotment.models import AllotmentItems

        allocations = AllotmentItems.objects.filter(
            allotment=allotment,
            is_boe=False
        )

        summary = allocations.aggregate(
            total_items=Count('id'),
            total_quantity=Sum('qty'),
            total_value=Sum('cif_fc')
        )

        return {
            'total_items': summary['total_items'] or 0,
            'total_quantity': to_decimal(summary['total_quantity'], DEC_0),
            'total_value': to_decimal(summary['total_value'], DEC_0),
            'required_value': to_decimal(allotment.required_value, DEC_0),
            'balanced_quantity': to_decimal(allotment.balanced_quantity, DEC_0),
        }
