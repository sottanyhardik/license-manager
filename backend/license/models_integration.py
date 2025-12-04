"""
Integration layer for license models to use new services.

This module provides mixin classes and property updates that integrate
the new service layer with existing models, allowing gradual migration.
"""

from decimal import Decimal
from typing import Dict

from django.db import models
from django.utils.functional import cached_property

from core.constants import DEC_0
from license.services.balance_calculator import LicenseBalanceCalculator, ItemBalanceCalculator
from license.services.restriction_calculator import RestrictionCalculator
from license.services.validation_service import LicenseValidationService


class LicenseBalanceMixin:
    """
    Mixin to add service-based balance methods to LicenseDetailsModel.
    
    Add this to LicenseDetailsModel to use new service layer while
    maintaining backward compatibility with existing code.
    """

    @property
    def get_balance_cif(self) -> Decimal:
        """
        Get license balance using centralized calculator service.
        """
        return LicenseBalanceCalculator.calculate_balance(self)

    def get_restriction_balances(self) -> Dict[Decimal, Decimal]:
        """
        Get restriction balances using centralized calculator service.
        """
        total_export_cif = self._calculate_license_credit()
        return RestrictionCalculator.calculate_all_restriction_balances(self, total_export_cif)

    def _calculate_license_credit(self) -> Decimal:
        """Calculate total credit using service."""
        return LicenseBalanceCalculator.calculate_credit(self)

    def _calculate_license_debit(self) -> Decimal:
        """Calculate total debit using service."""
        return LicenseBalanceCalculator.calculate_debit(self)

    def _calculate_license_allotment(self) -> Decimal:
        """Calculate total allotment using service."""
        return LicenseBalanceCalculator.calculate_allotment(self)

    def validate_active(self) -> tuple[bool, str]:
        """Validate if license is active."""
        return LicenseValidationService.validate_license_active(self)

    def update_status_flags(self) -> Dict[str, bool]:
        """Update all license status flags."""
        flags = LicenseValidationService.update_license_flags(self)

        # Apply flags to model
        for flag_name, flag_value in flags.items():
            if hasattr(self, flag_name):
                setattr(self, flag_name, flag_value)

        return flags


class LicenseItemBalanceMixin:
    """
    Mixin to add service-based balance methods to LicenseImportItemsModel.
    
    Add this to LicenseImportItemsModel to use new service layer.
    """

    @property
    def get_balance_cif(self) -> Decimal:
        """Get item balance using service."""
        return ItemBalanceCalculator.calculate_item_balance(self)

    @property
    def available_quantity(self) -> Decimal:
        """Get available quantity using service."""
        return ItemBalanceCalculator.calculate_available_quantity(self)

    @property
    def balance_cif_fc(self) -> Decimal:
        """Alias for get_balance_cif for backward compatibility."""
        return self.get_balance_cif

    def get_balance_components(self) -> Dict[str, Decimal]:
        """Get all balance components."""
        return ItemBalanceCalculator.calculate_item_components(self)

    def calculate_max_allocation(self, unit_price: Decimal, required_value_with_buffer: Decimal = None) -> Dict[
        str, Decimal]:
        """Calculate maximum allocation for this item."""
        return ItemBalanceCalculator.calculate_available_value_for_allocation(
            self, unit_price, required_value_with_buffer
        )


# Example of how to integrate with existing LicenseDetailsModel:
"""
# In license/models.py, update the LicenseDetailsModel class:

from license.models_integration import LicenseBalanceMixin

class LicenseDetailsModel(AuditModel, LicenseBalanceMixin):
    # ... existing fields ...
    
    # Now all balance methods from the mixin are available
    # Old code continues to work: license.get_balance_cif
    # But now it uses the service layer
"""

# Example of how to integrate with LicenseImportItemsModel:
"""
# In license/models.py, update the LicenseImportItemsModel class:

from license.models_integration import LicenseItemBalanceMixin

class LicenseImportItemsModel(AuditModel, LicenseItemBalanceMixin):
    # ... existing fields ...
    
    # Now all balance methods from the mixin are available
"""
