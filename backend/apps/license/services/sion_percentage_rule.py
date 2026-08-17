"""SION percentage rule capacity calculation and enforcement.

Calculates and tracks usage of percentage-constrained output items
during planning and allotment using QUANTITY (not CIF/value).

Formula: input_quantity_cap = total_eligible_quantity × percentage / 100

Example (E126 with 1000 KG total):
  PKO cap = 1000 KG × 50 / 100 = 500 KG
  OLIVE_OIL cap = 1000 KG × 50 / 100 = 500 KG
"""
from decimal import Decimal
from django.db.models import Sum
from apps.core.constants import DEC_0
from apps.license.models import LicenseDetailsModel, AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.license.services.sion_input_classifier import SionInputClassifier


class SionPercentageRule:
    """Calculate percentage rule capacity using QUANTITY (KG, MT, etc.)."""

    @staticmethod
    def calculate_total_eligible_quantity(license_obj: LicenseDetailsModel, sion_id: int) -> Decimal:
        """Calculate TOTAL SION eligible QUANTITY in native units (KG, MT, etc.).

        Sums net_quantity from LicenseExportItemModel for the given SION norm.
        This is the authoritative base for percentage cap calculations.

        Example:
          LicenseExportItemModel records for SION E126:
            PKO: 400 KG
            OLIVE_OIL: 300 KG
            RBD: 300 KG
          Total Eligible Quantity = 1000 KG

        Args:
            license_obj: LicenseDetailsModel instance
            sion_id: SionNormClassModel.id for the rule's norm

        Returns:
            Decimal quantity in native units (KG, MT) or 0 if no exports
        """
        if not license_obj or not sion_id:
            return DEC_0

        # Sum export quantities for this SION norm
        export_items = license_obj.export_license.filter(norm_class_id=sion_id)
        if not export_items.exists():
            return DEC_0

        total = export_items.aggregate(
            total_qty=Sum('net_quantity')
        )['total_qty'] or DEC_0

        return Decimal(str(total))

    @staticmethod
    def get_percentage_cap_for_input(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        percentage: Decimal
    ) -> Decimal:
        """Calculate absolute QUANTITY cap for a canonical input.

        Formula: cap = total_eligible_quantity × (percentage / 100)

        Example (E126, 50% constraint):
          Total Eligible: 1000 KG
          PKO cap = 1000 × 50 / 100 = 500 KG

        Args:
            license_obj: LicenseDetailsModel
            sion_id: SionNormClassModel.id for the rule's norm
            percentage: Decimal percentage (e.g., Decimal("50.00") for 50%)

        Returns:
            Decimal quantity cap in native units
        """
        if not percentage or percentage < DEC_0:
            return DEC_0

        total_qty = SionPercentageRule.calculate_total_eligible_quantity(license_obj, sion_id)
        if total_qty <= DEC_0:
            return DEC_0

        cap = (total_qty * percentage) / Decimal("100")
        return cap.quantize(Decimal("0.001"))

    @staticmethod
    def get_allotted_for_input(license_obj: LicenseDetailsModel, canonical_input_code: str) -> Decimal:
        """Get total allotted QUANTITY for a canonical input.

        Aggregates AllotmentItems.qty where the source item maps to canonical_input_code.

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO", "OLIVE_OIL"

        Returns:
            Decimal total allotted quantity in native units
        """
        if not license_obj:
            return DEC_0

        # Get all allotment items for this license
        allotment_items = AllotmentItems.objects.filter(
            item__license=license_obj,
        ).select_related('item', 'allotment')

        total_qty = DEC_0
        for item in allotment_items:
            # Classify the allotment item's source by product name
            item_name = ""

            # Try to get name from linked license item's ItemNameModel
            if item.item and item.item.items.exists():
                item_name = item.item.items.first().name

            # Fall back to allotment's item_name
            if not item_name and item.allotment:
                item_name = item.allotment.item_name or ""

            classified = SionInputClassifier.resolve_canonical_input(item_name)
            if classified and classified.code == canonical_input_code:
                # Accumulate native quantity
                total_qty += Decimal(str(item.qty or DEC_0))

        return total_qty.quantize(Decimal("0.001"))

    @staticmethod
    def get_debited_for_input(license_obj: LicenseDetailsModel, canonical_input_code: str) -> Decimal:
        """Get total debited QUANTITY for a canonical input.

        Aggregates RowDetails.qty where the BOE item maps to canonical_input_code.

        Args:
            license_obj: LicenseDetailsModel
            canonical_input_code: Code like "PKO", "OLIVE_OIL"

        Returns:
            Decimal total debited quantity in native units
        """
        if not license_obj:
            return DEC_0

        # Get BOE debit rows for items in this license
        debit_rows = RowDetails.objects.filter(
            sr_number__license=license_obj,
            transaction_type='D',
        ).select_related('bill_of_entry', 'sr_number')

        total_qty = DEC_0
        for row in debit_rows:
            # Classify by BOE product_name
            boe_product_name = row.bill_of_entry.product_name or ""
            classified = SionInputClassifier.resolve_canonical_input(boe_product_name)
            if classified and classified.code == canonical_input_code:
                # Accumulate native quantity
                total_qty += Decimal(str(row.qty or DEC_0))

        return total_qty.quantize(Decimal("0.001"))

    @staticmethod
    def get_remaining_capacity_for_input(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        canonical_input_code: str,
        percentage: Decimal
    ) -> Decimal:
        """Calculate remaining QUANTITY capacity for a canonical input.

        Formula: remaining = cap - (allotted + debited)

        Example (E126 PKO 50%):
          Cap: 500 KG
          Allotted: 300 KG
          Debited: 150 KG
          Remaining: 50 KG

        Args:
            license_obj: LicenseDetailsModel
            sion_id: SionNormClassModel.id for the rule's norm
            canonical_input_code: Code like "PKO", "OLIVE_OIL"
            percentage: Decimal percentage (e.g., 50.00)

        Returns:
            Decimal remaining capacity in native units (non-negative)
        """
        if not license_obj or not sion_id:
            return DEC_0

        cap = SionPercentageRule.get_percentage_cap_for_input(license_obj, sion_id, percentage)
        allotted = SionPercentageRule.get_allotted_for_input(license_obj, canonical_input_code)
        debited = SionPercentageRule.get_debited_for_input(license_obj, canonical_input_code)

        used = allotted + debited
        remaining = max(DEC_0, cap - used)

        return remaining.quantize(Decimal("0.001"))

    @staticmethod
    def check_percentage_capacity(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        canonical_input_code: str,
        percentage: Decimal,
        requested_qty: Decimal
    ) -> tuple[bool, str]:
        """Check if a QUANTITY allocation would violate percentage constraint.

        Args:
            license_obj: LicenseDetailsModel
            sion_id: SionNormClassModel.id for the rule's norm
            canonical_input_code: Code like "PKO"
            percentage: Constraint percentage (e.g., 50.00)
            requested_qty: Quantity trying to allocate (in native units)

        Returns:
            (allowed: bool, message: str) where message is empty if allowed
        """
        if not license_obj or not sion_id or not percentage or percentage < DEC_0:
            return True, ""  # No constraint

        remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, sion_id, canonical_input_code, percentage
        )
        requested_qty_dec = Decimal(str(requested_qty))

        if requested_qty_dec > remaining:
            cap = SionPercentageRule.get_percentage_cap_for_input(license_obj, sion_id, percentage)
            allotted = SionPercentageRule.get_allotted_for_input(license_obj, canonical_input_code)
            debited = SionPercentageRule.get_debited_for_input(license_obj, canonical_input_code)
            return False, (
                f"{canonical_input_code} percentage cap exceeded under {percentage}% constraint. "
                f"Cap: {cap}, Allotted: {allotted}, Debited: {debited}, "
                f"Remaining: {remaining}, Requested: {requested_qty_dec}"
            )

        return True, ""
