"""
Balance calculation service for licenses and items.

This module centralizes all balance calculation logic for:
- License-level balances (credit, debit, allotment, final balance)
- Import/Export item balances
- Available values for allocation
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple, Optional

from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce

from core.constants import DEC_0, DEBIT
from core.utils.decimal_utils import to_decimal


def quantize_2dp(value: Decimal) -> Decimal:
    """Quantize decimal to 2 decimal places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LicenseBalanceCalculator:
    """
    Service for calculating license-level balances.
    
    Centralizes the calculation of:
    - Credit (total export CIF)
    - Debit (total BOE debits)
    - Allotment (total non-BOE allotments)
    - Final balance
    """

    @staticmethod
    def calculate_credit(license_obj) -> Decimal:
        """
        Calculate total credit (export CIF) for license.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Total export CIF as Decimal
        """
        from license.models import LicenseExportItemModel

        return to_decimal(
            LicenseExportItemModel.objects.filter(
                license=license_obj
            ).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_debit(license_obj) -> Decimal:
        """
        Calculate total debit (BOE transactions) for license.
        
        Args:
            license_obj: LicenseDetailsModel instance
            
        Returns:
            Total debit CIF as Decimal
        """
        from bill_of_entry.models import RowDetails

        return to_decimal(
            RowDetails.objects.filter(
                sr_number__license=license_obj,
                transaction_type=DEBIT
            ).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_allotment(license_obj) -> Decimal:
        """
        Calculate total allotment (non-BOE) for license.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total allotment CIF as Decimal
        """
        from allotment.models import AllotmentItems

        return to_decimal(
            AllotmentItems.objects.filter(
                item__license=license_obj,
                allotment__bill_of_entry__isnull=True
            ).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @staticmethod
    def calculate_trade(license_obj) -> Decimal:
        """
        Calculate total trade CIF $ for license.
        Only counts SALE trade lines where:
        1. Trade is linked to a BOE that has NO invoice, OR
        2. Trade is NOT linked to any BOE at all

        NOTE: Only SALE trades debit the license. PURCHASE trades add to the license (already counted in allotments).

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Total trade CIF as Decimal
        """
        from django.db.models import Q
        from trade.models import LicenseTradeLine

        return to_decimal(
            LicenseTradeLine.objects.filter(
                sr_number__license=license_obj,
                trade__direction='SALE'  # Only count SALE trades that debit the license
            ).filter(
                Q(trade__boe__isnull=True) | Q(trade__boe__invoice_no__isnull=True) | Q(trade__boe__invoice_no='')
            ).aggregate(
                total=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["total"],
            DEC_0,
        )

    @classmethod
    def calculate_balance(cls, license_obj) -> Decimal:
        """
        Calculate final balance for license.

        Formula: Credit - (Debit + Allotment + Trade)

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Final balance as Decimal (minimum 0), quantized to 2 decimal places
        """
        credit = cls.calculate_credit(license_obj)
        debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        trade = cls.calculate_trade(license_obj)

        balance = credit - (debit + allotment + trade)
        balance = quantize_2dp(balance)
        return balance if balance >= DEC_0 else DEC_0

    @classmethod
    def calculate_all_components(cls, license_obj) -> Dict[str, Decimal]:
        """
        Calculate all balance components at once.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dictionary with credit, debit, allotment, trade, and balance (all quantized to 2dp)
        """
        credit = cls.calculate_credit(license_obj)
        debit = cls.calculate_debit(license_obj)
        allotment = cls.calculate_allotment(license_obj)
        trade = cls.calculate_trade(license_obj)
        balance = credit - (debit + allotment + trade)
        balance = quantize_2dp(balance)

        return {
            'credit': quantize_2dp(credit),
            'debit': quantize_2dp(debit),
            'allotment': quantize_2dp(allotment),
            'trade': quantize_2dp(trade),
            'balance': balance if balance >= DEC_0 else DEC_0,
        }


class ItemBalanceCalculator:
    """
    Service for calculating item-level balances.
    
    Handles calculations for import and export items.
    """

    @staticmethod
    def calculate_item_credit_debit(import_item) -> Tuple[Decimal, Decimal]:
        """
        Calculate credit and debit for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Tuple of (credit, total_debit) as Decimals
        """
        from license.models import LicenseExportItemModel
        from bill_of_entry.models import RowDetails
        from allotment.models import AllotmentItems

        # Calculate credit
        if not import_item.cif_fc or import_item.cif_fc == 0:
            # Use total export CIF if item CIF is 0
            credit = to_decimal(
                LicenseExportItemModel.objects.filter(
                    license=import_item.license
                ).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )

            # Debit is for entire license
            debit = to_decimal(
                RowDetails.objects.filter(
                    sr_number__license=import_item.license,
                    transaction_type=DEBIT
                ).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )
        else:
            # Use specific item CIF
            credit = to_decimal(import_item.cif_fc, DEC_0)

            # Debit is for this specific item
            debit = to_decimal(
                RowDetails.objects.filter(
                    sr_number=import_item,
                    transaction_type=DEBIT
                ).aggregate(
                    Sum('cif_fc')
                )['cif_fc__sum'],
                DEC_0
            )

        # Add allotments to debit
        allotment = to_decimal(
            AllotmentItems.objects.filter(
                item=import_item,
                allotment__bill_of_entry__isnull=True
            ).aggregate(
                Sum('cif_fc')
            )['cif_fc__sum'],
            DEC_0
        )

        total_debit = debit + allotment

        return credit, total_debit

    @classmethod
    def calculate_item_balance(cls, import_item) -> Decimal:
        """
        Calculate balance for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Balance as Decimal (minimum 0)
        """
        credit, debit = cls.calculate_item_credit_debit(import_item)
        balance = credit - debit
        return balance if balance >= DEC_0 else DEC_0

    @staticmethod
    def calculate_available_quantity(import_item) -> Decimal:
        """
        Calculate available quantity for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Available quantity as Decimal
        """
        from bill_of_entry.models import RowDetails
        from allotment.models import AllotmentItems

        total_quantity = to_decimal(import_item.quantity, DEC_0)

        # Sum debited quantities
        debited = to_decimal(
            RowDetails.objects.filter(
                sr_number=import_item,
                transaction_type=DEBIT
            ).aggregate(
                Sum('qty')
            )['qty__sum'],
            DEC_0
        )

        # Sum allotted quantities
        allotted = to_decimal(
            AllotmentItems.objects.filter(
                item=import_item,
                allotment__bill_of_entry__isnull=True
            ).aggregate(
                Sum('qty')
            )['qty__sum'],
            DEC_0
        )

        available = total_quantity - debited - allotted
        return available if available >= DEC_0 else DEC_0

    @classmethod
    def calculate_item_components(cls, import_item) -> Dict[str, Decimal]:
        """
        Calculate all components for an import item.
        
        Args:
            import_item: LicenseImportItemsModel instance
            
        Returns:
            Dictionary with credit, debit, balance, and available_quantity
        """
        credit, debit = cls.calculate_item_credit_debit(import_item)
        balance = credit - debit
        available_qty = cls.calculate_available_quantity(import_item)

        return {
            'credit': credit,
            'debit': debit,
            'balance': balance if balance >= DEC_0 else DEC_0,
            'available_quantity': available_qty,
        }

    @staticmethod
    def calculate_available_value_for_allocation(
            import_item,
            unit_price: Decimal,
            required_value_with_buffer: Optional[Decimal] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate maximum available value for allocation considering all constraints.
        
        Args:
            import_item: LicenseImportItemsModel instance
            unit_price: Price per unit
            required_value_with_buffer: Required value with buffer for allotment
            
        Returns:
            Dictionary with max_quantity and max_value
        """
        available_qty = ItemBalanceCalculator.calculate_available_quantity(import_item)
        balance_cif = ItemBalanceCalculator.calculate_item_balance(import_item)

        # Start with available quantity
        max_qty = available_qty
        max_value = max_qty * unit_price

        # Check CIF constraint
        if max_value > balance_cif:
            max_qty = balance_cif / unit_price if unit_price > 0 else DEC_0
            max_value = max_qty * unit_price

        # Check required value constraint if provided
        if required_value_with_buffer and max_value > required_value_with_buffer:
            max_qty = required_value_with_buffer / unit_price if unit_price > 0 else DEC_0
            max_value = max_qty * unit_price

        return {
            'max_quantity': max_qty,
            'max_value': max_value,
        }
