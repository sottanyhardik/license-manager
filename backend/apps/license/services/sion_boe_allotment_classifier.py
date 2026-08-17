"""Classify BOE and Allotment records by SION canonical input.

Integrates SionInputClassifier with RowDetails (BOE debits) and AllotmentItems
to provide canonical input classification and QUANTITY aggregation.
"""
from decimal import Decimal
from typing import Optional, Dict
from apps.core.constants import DEC_0
from apps.license.models import LicenseDetailsModel
from apps.bill_of_entry.models import RowDetails
from apps.allotment.models import AllotmentItems
from apps.license.services.sion_input_classifier import SionInputClassifier


class SionBoeAllotmentClassifier:
    """Classify BOE debit and Allotment records by canonical input using QUANTITY."""

    @staticmethod
    def get_boe_canonical_input(boe) -> Optional[str]:
        """Get canonical input code from a BOE (BillOfEntryModel) or RowDetails.

        Args:
            boe: BillOfEntryModel or RowDetails instance

        Returns:
            Canonical input code (e.g., "PKO", "OLIVE_OIL") or None if unmapped
        """
        product_name = getattr(boe, 'product_name', '')
        if not product_name:
            return None

        canonical = SionInputClassifier.resolve_canonical_input(product_name)
        return canonical.code if canonical else None

    @staticmethod
    def get_allotment_canonical_input(allotment) -> Optional[str]:
        """Get canonical input code from an Allotment record.

        Args:
            allotment: AllotmentModel instance

        Returns:
            Canonical input code or None if unmapped
        """
        item_name = allotment.item_name or ''
        if not item_name:
            return None

        canonical = SionInputClassifier.resolve_canonical_input(item_name)
        return canonical.code if canonical else None

    @staticmethod
    def get_allotment_item_canonical_input(allotment_item) -> Optional[str]:
        """Get canonical input code from an AllotmentItems record.

        Args:
            allotment_item: AllotmentItems instance

        Returns:
            Canonical input code or None if unmapped
        """
        # Check the related license item's ItemNameModel first
        if allotment_item.item and allotment_item.item.items.exists():
            item_name = allotment_item.item.items.first().name
            if item_name:
                canonical = SionInputClassifier.resolve_canonical_input(item_name)
                if canonical:
                    return canonical.code

        # Fall back to allotment's item_name
        if allotment_item.allotment:
            return SionBoeAllotmentClassifier.get_allotment_canonical_input(
                allotment_item.allotment
            )

        return None

    @staticmethod
    def classify_boe_rows_by_input(
        license_obj: LicenseDetailsModel
    ) -> Dict[str, list]:
        """Classify all BOE debit rows for a license by canonical input.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dict mapping canonical input code to list of RowDetails instances
        """
        if not license_obj:
            return {}

        # Get all debit rows linked to this license's items
        debit_rows = RowDetails.objects.filter(
            transaction_type='D',
            sr_number__license=license_obj,
        ).select_related('bill_of_entry')

        classified = {}
        for row in debit_rows:
            canonical_code = SionBoeAllotmentClassifier.get_boe_canonical_input(
                row.bill_of_entry
            )
            if canonical_code:
                if canonical_code not in classified:
                    classified[canonical_code] = []
                classified[canonical_code].append(row)

        return classified

    @staticmethod
    def classify_allotment_items_by_input(
        license_obj: LicenseDetailsModel
    ) -> Dict[str, list]:
        """Classify all allotment items for a license by canonical input.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dict mapping canonical input code to list of AllotmentItems instances
        """
        if not license_obj:
            return {}

        # Get all allotment items for this license
        allotment_items = AllotmentItems.objects.filter(
            item__license=license_obj,
        ).select_related('item', 'allotment')

        classified = {}
        for allot_item in allotment_items:
            canonical_code = SionBoeAllotmentClassifier.get_allotment_item_canonical_input(
                allot_item
            )
            if canonical_code:
                if canonical_code not in classified:
                    classified[canonical_code] = []
                classified[canonical_code].append(allot_item)

        return classified

    @staticmethod
    def get_usage_summary_by_input(
        license_obj: LicenseDetailsModel
    ) -> Dict[str, Dict[str, Decimal]]:
        """Get QUANTITY usage by canonical input across BOE and Allotment.

        Aggregates RowDetails.qty (BOE debits) and AllotmentItems.qty (allotments)
        separately, providing a clear picture of allocation vs. debit.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dict mapping canonical input code to:
                {
                    'allotted_quantity': Decimal (native units),
                    'debited_quantity': Decimal (native units),
                    'total_quantity': Decimal (native units),
                }
        """
        result = {}

        # Classify BOE rows and aggregate QUANTITY
        boe_classified = SionBoeAllotmentClassifier.classify_boe_rows_by_input(license_obj)
        for code, rows in boe_classified.items():
            total_qty = sum(
                (Decimal(str(row.qty or DEC_0)) for row in rows),
                DEC_0
            )
            if code not in result:
                result[code] = {'allotted_quantity': DEC_0, 'debited_quantity': DEC_0}
            result[code]['debited_quantity'] = total_qty

        # Classify allotment items and aggregate QUANTITY
        allot_classified = SionBoeAllotmentClassifier.classify_allotment_items_by_input(license_obj)
        for code, items in allot_classified.items():
            total_qty = sum(
                (Decimal(str(item.qty or DEC_0)) for item in items),
                DEC_0
            )
            if code not in result:
                result[code] = {'allotted_quantity': DEC_0, 'debited_quantity': DEC_0}
            result[code]['allotted_quantity'] = total_qty

        # Calculate total for each input
        for code in result:
            result[code]['total_quantity'] = (
                result[code]['allotted_quantity'] + result[code]['debited_quantity']
            ).quantize(Decimal('0.001'))

        return result

    @staticmethod
    def get_inputs_in_license(license_obj: LicenseDetailsModel) -> set:
        """Get all canonical input codes that appear in this license's BOE/Allotments.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Set of canonical input codes (e.g., {"PKO", "OLIVE_OIL"})
        """
        boe_classified = SionBoeAllotmentClassifier.classify_boe_rows_by_input(license_obj)
        allot_classified = SionBoeAllotmentClassifier.classify_allotment_items_by_input(license_obj)

        return set(boe_classified.keys()) | set(allot_classified.keys())
