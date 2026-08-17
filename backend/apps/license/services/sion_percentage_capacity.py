"""SION percentage capacity calculations and validation.

Handles:
- Calculating per-input percentage caps from total eligible quantity
- Aggregating current usage (planning, allotments, BOE)
- Determining remaining capacity
- Validating new Planning requests against caps
"""
from decimal import Decimal
from typing import Dict, Optional

from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, SionPlanningRule, LicenseItemPlan
)
from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails
from apps.core.constants import DEC_0
from .sion_product_classifier import SionProductClassifier, CanonicalInput


class SionPercentageCapacity:
    """Calculates and validates SION percentage-based quantity caps."""

    @staticmethod
    def get_total_eligible_quantity(
        license_obj: LicenseDetailsModel,
        sion_id: int,
    ) -> Decimal:
        """Calculate total eligible quantity for a SION norm on this license.

        Sums net_quantity from all LicenseExportItemModel records for the given SION.

        Args:
            license_obj: The license
            sion_id: SionNormClassModel.id

        Returns:
            Total eligible quantity in native units (usually KG)
        """
        from django.db.models import Sum

        export_items = LicenseExportItemModel.objects.filter(
            license=license_obj,
            norm_class_id=sion_id,
        )
        result = export_items.aggregate(
            total_qty=Sum("net_quantity")
        ) or {}

        total = result.get("total_qty") or DEC_0
        return total

    @staticmethod
    def get_percentage_cap_for_input(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        percentage: Decimal,
    ) -> Decimal:
        """Calculate the quantity cap for an input given its percentage.

        Formula: cap = total_eligible_quantity × percentage / 100

        Args:
            license_obj: The license
            sion_id: SionNormClassModel.id
            percentage: The percentage constraint (e.g., Decimal("50.00") for 50%)

        Returns:
            The quantity cap
        """
        total = SionPercentageCapacity.get_total_eligible_quantity(license_obj, sion_id)
        if total <= DEC_0 or percentage <= DEC_0:
            return DEC_0

        cap = (total * percentage / Decimal("100")).quantize(
            Decimal("0.01"), rounding="ROUND_HALF_UP"
        )
        return cap

    @staticmethod
    def get_planned_for_input(
        license_obj: LicenseDetailsModel,
        canonical_input: CanonicalInput,
    ) -> Decimal:
        """Get total quantity already planned for a canonical input.

        Sums planned_quantity from LicenseItemPlan records where the item_name
        can be classified to this canonical input.

        Args:
            license_obj: The license
            canonical_input: CanonicalInput enum

        Returns:
            Total planned quantity
        """
        if canonical_input == CanonicalInput.UNMAPPED:
            return DEC_0

        # Get LicenseItemPlan records for this license
        plans = LicenseItemPlan.objects.filter(
            license=license_obj,
        ).select_related("item_name")

        total = DEC_0
        for plan in plans:
            if plan.item_name:
                item_name = getattr(plan.item_name, "name", "")
                if SionProductClassifier.resolve_canonical_input(item_name) == canonical_input:
                    total += plan.planned_quantity or DEC_0

        return total

    @staticmethod
    def get_allotted_for_input(
        license_obj: LicenseDetailsModel,
        canonical_input: CanonicalInput,
    ) -> Decimal:
        """Get total quantity allotted for a canonical input.

        Sums qty from AllotmentItems where the item product name classifies
        to this canonical input.

        Args:
            license_obj: The license
            canonical_input: CanonicalInput enum

        Returns:
            Total allotted quantity
        """
        if canonical_input == CanonicalInput.UNMAPPED:
            return DEC_0

        try:
            # Get AllotmentItems for this license
            # The link is: AllotmentItems -> AllotmentModel -> license
            items = AllotmentItems.objects.filter(
                allotment__license=license_obj,
            ).select_related("item")

            total = DEC_0
            for item in items:
                if item.item:
                    item_name = getattr(item.item, "name", "")
                    if SionProductClassifier.resolve_canonical_input(item_name) == canonical_input:
                        total += item.qty or DEC_0

            return total
        except Exception:
            # Handle any relationship issues by returning 0
            # This ensures the feature doesn't break if relationships aren't set up
            return DEC_0

    @staticmethod
    def get_debited_for_input(
        license_obj: LicenseDetailsModel,
        canonical_input: CanonicalInput,
    ) -> Decimal:
        """Get total quantity debited (BOE) for a canonical input.

        Sums qty from RowDetails where the bill_of_entry.product_name
        classifies to this canonical input.

        Args:
            license_obj: The license
            canonical_input: CanonicalInput enum

        Returns:
            Total debited quantity
        """
        if canonical_input == CanonicalInput.UNMAPPED:
            return DEC_0

        try:
            # Get RowDetails for this license's BOEs
            # BOE has no direct license field - need to trace via sr_number or allotment
            # For now, return 0 as this requires complex relationship handling
            rows = RowDetails.objects.filter(
                bill_of_entry__allotment__license=license_obj,
            ).select_related("bill_of_entry")

            total = DEC_0
            for row in rows:
                product_name = row.bill_of_entry.product_name or ""
                if SionProductClassifier.resolve_canonical_input(product_name) == canonical_input:
                    total += row.qty or DEC_0

            return total
        except Exception:
            # Handle any relationship issues by returning 0
            return DEC_0

    @staticmethod
    def get_remaining_capacity_for_input(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        canonical_input: CanonicalInput,
        percentage: Decimal,
    ) -> Decimal:
        """Calculate remaining capacity for an input.

        Formula:
            remaining = cap - (planned + allotted + debited)

        Args:
            license_obj: The license
            sion_id: SionNormClassModel.id
            canonical_input: The input to check
            percentage: Its percentage constraint

        Returns:
            Remaining capacity (may be negative if already exceeded)
        """
        cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_obj, sion_id, percentage
        )
        planned = SionPercentageCapacity.get_planned_for_input(license_obj, canonical_input)
        allotted = SionPercentageCapacity.get_allotted_for_input(license_obj, canonical_input)
        debited = SionPercentageCapacity.get_debited_for_input(license_obj, canonical_input)

        used = planned + allotted + debited
        remaining = cap - used

        return remaining

    @staticmethod
    def can_allocate_to_input(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        canonical_input: CanonicalInput,
        percentage: Decimal,
        requested_qty: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """Check if a quantity can be allocated to an input without exceeding cap.

        Args:
            license_obj: The license
            sion_id: SionNormClassModel.id
            canonical_input: The input to allocate to
            percentage: Its percentage constraint
            requested_qty: The quantity being requested

        Returns:
            Tuple of (is_allowed, error_message)
        """
        if canonical_input == CanonicalInput.UNMAPPED or requested_qty <= DEC_0:
            return True, None  # No cap applies

        remaining = SionPercentageCapacity.get_remaining_capacity_for_input(
            license_obj, sion_id, canonical_input, percentage
        )

        if remaining < requested_qty:
            cap = SionPercentageCapacity.get_percentage_cap_for_input(
                license_obj, sion_id, percentage
            )
            return False, (
                f"{canonical_input.value} allocation exceeds remaining capacity. "
                f"Cap: {cap}, Requested: {requested_qty}, Remaining: {remaining}"
            )

        return True, None

    @staticmethod
    def get_split_percentage_maximum(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        percentage_rules: Dict[CanonicalInput, Decimal],
    ) -> Decimal:
        """Calculate maximum quantity that can be split using percentage rules.

        When splitting by percentages, the maximum total quantity is limited by:
        1. Which input has the tightest capacity given its percentage fraction
        2. Overall available balance

        Formula for each input:
            max_for_input = remaining_capacity / (percentage / 100)

        Overall max:
            min(max_for_each_input)

        Args:
            license_obj: The license
            sion_id: SionNormClassModel.id
            percentage_rules: Dict of {CanonicalInput: percentage_decimal}

        Returns:
            The maximum quantity that can be split
        """
        if not percentage_rules:
            return DEC_0

        max_quantities = []

        for canonical_input, percentage in percentage_rules.items():
            remaining = SionPercentageCapacity.get_remaining_capacity_for_input(
                license_obj, sion_id, canonical_input, percentage
            )

            # How much total quantity would this remaining capacity support at this %?
            if percentage > DEC_0:
                supported = (remaining / (percentage / Decimal("100"))).quantize(
                    Decimal("0.001"), rounding="ROUND_HALF_UP"
                )
                max_quantities.append(supported)

        if max_quantities:
            return min(max_quantities)

        return DEC_0
