"""
License validation service.

This module handles business rule validation for licenses and items.
"""

from datetime import timedelta
from decimal import Decimal
from typing import List, Dict

from django.utils import timezone

from core.constants import GE, DEC_0
from core.utils.date_utils import is_date_expired
from core.utils.decimal_utils import to_decimal


class LicenseValidationService:
    """
    Service for validating licenses and checking business rules.
    """

    @staticmethod
    def validate_license_active(license_obj) -> tuple[bool, str]:
        """
        Check if license is active and can be used for transactions.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []

        # Check purchase status
        if license_obj.purchase_status != GE:
            errors.append("License purchase status is not GE (Goods Exported)")

        # Check expiry date
        if license_obj.is_expired:
            errors.append("License has expired")

        # Check balance
        if license_obj.get_balance_cif < 500:
            errors.append("License balance is below minimum threshold (500)")

        # Check AU status
        if license_obj.is_au:
            errors.append("License is marked as AU (Authorization Under)")

        if errors:
            return False, "; ".join(errors)

        return True, ""

    @staticmethod
    def validate_license_complete(license_obj) -> tuple[bool, List[str]]:
        """
        Check if license has all required fields.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Tuple of (is_complete, missing_fields)
        """
        missing_fields = []

        if not license_obj.license_expiry_date:
            missing_fields.append("license_expiry_date")

        if not license_obj.file_number:
            missing_fields.append("file_number")

        if not license_obj.notification_number:
            missing_fields.append("notification_number")

        # Check if export items have norm_class
        if not license_obj.export_license.filter(norm_class__isnull=False).exists():
            missing_fields.append("export_license.norm_class")

        return len(missing_fields) == 0, missing_fields

    @staticmethod
    def check_license_expiring_soon(license_obj, days: int = 90) -> bool:
        """
        Check if license is expiring within specified days.
        
        Args:
            license_obj: LicenseDetailsModel instance
            days: Number of days to check
            
        Returns:
            True if expiring within days, False otherwise
        """
        if not license_obj.license_expiry_date:
            return False

        today = timezone.now().date()
        threshold_date = today + timedelta(days=days)

        return license_obj.license_expiry_date <= threshold_date

    @staticmethod
    def validate_sufficient_balance(
            license_obj,
            required_value: Decimal
    ) -> tuple[bool, str]:
        """
        Validate that license has sufficient balance for allocation.
        
        Args:
            license_obj: LicenseDetailsModel instance
            required_value: Required value to allocate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        available_balance = license_obj.get_balance_cif
        required = to_decimal(required_value, DEC_0)

        if available_balance < required:
            return False, f"Insufficient balance. Available: {available_balance}, Required: {required}"

        return True, ""

    @staticmethod
    def validate_sufficient_quantity(
            import_item,
            required_quantity: Decimal
    ) -> tuple[bool, str]:
        """
        Validate that import item has sufficient quantity.
        
        Args:
            import_item: LicenseImportItemsModel instance
            required_quantity: Required quantity to allocate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        from license.services.balance_calculator import ItemBalanceCalculator

        available_qty = ItemBalanceCalculator.calculate_available_quantity(import_item)
        required = to_decimal(required_quantity, DEC_0)

        if available_qty < required:
            return False, f"Insufficient quantity. Available: {available_qty}, Required: {required}"

        return True, ""

    @staticmethod
    def validate_restriction_limit(
            license_obj,
            import_item,
            required_value: Decimal
    ) -> tuple[bool, str]:
        """
        Validate that allocation doesn't exceed restriction limits.
        
        Args:
            license_obj: LicenseDetailsModel instance
            import_item: LicenseImportItemsModel instance
            required_value: Required value to allocate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        from license.services.restriction_calculator import RestrictionCalculator

        # Get restriction percentage for this item
        restriction_pct = RestrictionCalculator.get_item_restriction_percentage(import_item)

        if restriction_pct <= DEC_0:
            # No restriction, always valid
            return True, ""

        # Get restriction balance
        total_export_cif = license_obj._calculate_license_credit()
        restriction_balance = RestrictionCalculator.calculate_restriction_balance(
            license_obj,
            restriction_pct,
            total_export_cif
        )

        required = to_decimal(required_value, DEC_0)

        if restriction_balance < required:
            return False, f"Exceeds {restriction_pct}% restriction limit. Available: {restriction_balance}, Required: {required}"

        return True, ""

    @classmethod
    def validate_allocation(
            cls,
            license_obj,
            import_item,
            quantity: Decimal,
            value: Decimal
    ) -> tuple[bool, List[str]]:
        """
        Comprehensive validation for allocation.
        
        Args:
            license_obj: LicenseDetailsModel instance
            import_item: LicenseImportItemsModel instance
            quantity: Quantity to allocate
            value: Value to allocate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check license is active
        is_active, active_error = cls.validate_license_active(license_obj)
        if not is_active:
            errors.append(active_error)

        # Check sufficient balance
        has_balance, balance_error = cls.validate_sufficient_balance(license_obj, value)
        if not has_balance:
            errors.append(balance_error)

        # Check sufficient quantity
        has_quantity, quantity_error = cls.validate_sufficient_quantity(import_item, quantity)
        if not has_quantity:
            errors.append(quantity_error)

        # Check restriction limits
        within_restriction, restriction_error = cls.validate_restriction_limit(
            license_obj,
            import_item,
            value
        )
        if not within_restriction:
            errors.append(restriction_error)

        return len(errors) == 0, errors

    @staticmethod
    def check_individual_license(license_obj) -> bool:
        """
        Check if license is individual (has .01 CIF items).
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            True if individual license, False otherwise
        """
        return license_obj.import_license.filter(cif_fc=Decimal('0.01')).exists()

    @staticmethod
    def update_license_flags(license_obj) -> Dict[str, bool]:
        """
        Update all license status flags.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Dictionary of updated flags
        """
        flags = {}

        # Check if null (low balance)
        balance = license_obj.get_balance_cif
        flags['is_null'] = balance < 500

        # Check if expired
        flags['is_expired'] = is_date_expired(license_obj.license_expiry_date)

        # Check if active
        if license_obj.purchase_status != GE:
            flags['is_active'] = False
        elif flags['is_expired'] or flags['is_null'] or license_obj.is_au:
            flags['is_active'] = False
        else:
            flags['is_active'] = True

        # Check if incomplete
        is_complete, _ = LicenseValidationService.validate_license_complete(license_obj)
        flags['is_incomplete'] = not is_complete

        # Check if individual
        flags['is_individual'] = LicenseValidationService.check_individual_license(license_obj)

        return flags
