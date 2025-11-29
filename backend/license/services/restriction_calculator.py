"""
Restriction balance calculation service.

This module handles calculation of restriction-based balances for licenses.
Restrictions are percentage-based limits on certain import items.
"""

from decimal import Decimal
from typing import Dict, Set

from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce

from core.constants import DEC_0, DEBIT
from core.utils.decimal_utils import to_decimal


class RestrictionCalculator:
    """
    Service for calculating restriction-based balances.
    
    Handles calculations for items with head-based restrictions
    (e.g., 2%, 3%, 5% restrictions on total license CIF).
    """

    @staticmethod
    def get_unique_restriction_percentages(license_obj) -> Set[Decimal]:
        """
        Get all unique restriction percentages for a license.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Set of restriction percentages as Decimals
        """
        restriction_percentages = set()

        for import_item in license_obj.import_license.all():
            restricted_items = import_item.items.filter(
                sion_norm_class__isnull=False,
                restriction_percentage__gt=0
            )

            for item_name in restricted_items:
                pct = to_decimal(item_name.restriction_percentage or 0, DEC_0)
                if pct > DEC_0:
                    restriction_percentages.add(pct)

        return restriction_percentages

    @staticmethod
    def calculate_restricted_cif(total_export_cif: Decimal, restriction_pct: Decimal) -> Decimal:
        """
        Calculate total restricted CIF for a given percentage.
        
        Formula: total_export_cif × (restriction_percentage / 100)
        
        Args:
            total_export_cif: Total export CIF FC
            restriction_pct: Restriction percentage
            
        Returns:
            Restricted CIF as Decimal
        """
        return total_export_cif * restriction_pct / Decimal('100')

    @staticmethod
    def calculate_restricted_debits_and_allotments(
            license_obj,
            restriction_pct: Decimal
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate debits and allotments for items with specific restriction percentage.
        
        Args:
            license_obj: LicenseDetailsModel instance
            restriction_pct: Restriction percentage to filter by
            
        Returns:
            Tuple of (restricted_debits, restricted_allotments) as Decimals
        """
        from bill_of_entry.models import RowDetails
        from allotment.models import AllotmentItems

        restricted_debits = DEC_0
        restricted_allotments = DEC_0

        for import_item in license_obj.import_license.all():
            # Check if this import item has this specific restriction percentage
            has_this_restriction = import_item.items.filter(
                sion_norm_class__isnull=False,
                restriction_percentage=restriction_pct
            ).exists()

            if has_this_restriction:
                # Sum debits for this item
                restricted_debits += to_decimal(
                    RowDetails.objects.filter(
                        sr_number=import_item,
                        transaction_type=DEBIT
                    ).aggregate(
                        total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
                    )["total"],
                    DEC_0
                )

                # Sum allotments for this item (exclude converted allotments)
                restricted_allotments += to_decimal(
                    AllotmentItems.objects.filter(
                        item=import_item,
                        allotment__bill_of_entry__bill_of_entry_number__isnull=True
                    ).aggregate(
                        total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
                    )["total"],
                    DEC_0
                )

        return restricted_debits, restricted_allotments

    @classmethod
    def calculate_restriction_balance(
            cls,
            license_obj,
            restriction_pct: Decimal,
            total_export_cif: Decimal
    ) -> Decimal:
        """
        Calculate remaining balance for a specific restriction percentage.
        
        Formula: (Export CIF × restriction% / 100) - (debits + allotments for restricted items)
        
        Args:
            license_obj: LicenseDetailsModel instance
            restriction_pct: Restriction percentage
            total_export_cif: Total export CIF FC
            
        Returns:
            Remaining balance as Decimal (minimum 0)
        """
        # Calculate total restricted CIF
        total_restricted_cif = cls.calculate_restricted_cif(total_export_cif, restriction_pct)

        # Calculate debits and allotments
        restricted_debits, restricted_allotments = cls.calculate_restricted_debits_and_allotments(
            license_obj,
            restriction_pct
        )

        # Calculate remaining balance
        balance = total_restricted_cif - restricted_debits - restricted_allotments
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_all_restriction_balances(
            cls,
            license_obj,
            total_export_cif: Decimal
    ) -> Dict[Decimal, Decimal]:
        """
        Calculate restriction balances for all unique restriction percentages.
        
        Args:
            license_obj: LicenseDetailsModel instance
            total_export_cif: Total export CIF FC
            
        Returns:
            Dictionary mapping restriction_percentage -> balance_remaining
        """
        restriction_balances = {}

        # Get all unique restriction percentages
        restriction_percentages = cls.get_unique_restriction_percentages(license_obj)

        # Calculate balance for each restriction percentage
        for restriction_pct in restriction_percentages:
            balance = cls.calculate_restriction_balance(
                license_obj,
                restriction_pct,
                total_export_cif
            )
            restriction_balances[restriction_pct] = balance

        return restriction_balances

    @staticmethod
    def check_item_has_restriction(import_item, restriction_pct: Decimal) -> bool:
        """
        Check if an import item has a specific restriction percentage.
        
        Args:
            import_item: LicenseImportItemsModel instance
            restriction_pct: Restriction percentage to check
            
        Returns:
            True if item has this restriction, False otherwise
        """
        return import_item.items.filter(
            sion_norm_class__isnull=False,
            restriction_percentage=restriction_pct
        ).exists()

    @staticmethod
    def get_item_restriction_percentage(import_item) -> Decimal:
        """
        Get the restriction percentage for an import item.
        
        Returns the first restriction percentage found if item has multiple.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Restriction percentage as Decimal, or 0 if not restricted
        """
        restricted_item = import_item.items.filter(
            sion_norm_class__isnull=False,
            restriction_percentage__gt=0
        ).first()

        if restricted_item:
            return to_decimal(restricted_item.restriction_percentage, DEC_0)

        return DEC_0

    @classmethod
    def calculate_available_for_restriction(
            cls,
            license_obj,
            restriction_pct: Decimal,
            total_export_cif: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate available amounts for a specific restriction.
        
        Args:
            license_obj: LicenseDetailsModel instance
            restriction_pct: Restriction percentage
            total_export_cif: Total export CIF FC
            
        Returns:
            Dictionary with total_allowed, used, and available
        """
        total_allowed = cls.calculate_restricted_cif(total_export_cif, restriction_pct)

        restricted_debits, restricted_allotments = cls.calculate_restricted_debits_and_allotments(
            license_obj,
            restriction_pct
        )

        used = restricted_debits + restricted_allotments
        available = total_allowed - used

        return {
            'total_allowed': total_allowed,
            'used': used,
            'available': available if available >= DEC_0 else DEC_0,
        }
