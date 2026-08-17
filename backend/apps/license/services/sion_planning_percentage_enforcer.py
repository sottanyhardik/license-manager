"""Enforce SION percentage constraints during planning.

Integrates SionPercentageRule with planning execution to validate and enforce
percentage-constrained QUANTITY allocations before they are created.
"""
from decimal import Decimal
from typing import Optional, Tuple, Dict

from apps.core.constants import DEC_0
from apps.license.models import (
    LicenseDetailsModel, SionPlanningRule,
    LicenseImportItemsModel
)
from apps.license.services.sion_input_classifier import SionInputClassifier
from apps.license.services.sion_percentage_rule import SionPercentageRule
from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier


class SionPlanningPercentageEnforcer:
    """Validate and enforce percentage constraints on planning quantity allocations."""

    @staticmethod
    def get_applicable_rules_for_sion(
        license_obj: LicenseDetailsModel,
        sion_id: int
    ) -> list:
        """Get all percentage-constrained rules for a SION norm.

        Args:
            license_obj: LicenseDetailsModel instance
            sion_id: SionNormClassModel.id

        Returns:
            List of SionPlanningRule instances with percentage_constraint != None
        """
        if not license_obj or not sion_id:
            return []

        rules = SionPlanningRule.objects.filter(
            sion_id=sion_id,
            percentage_constraint__isnull=False,
        ).exclude(percentage_constraint=DEC_0)

        return list(rules)

    @staticmethod
    def classify_item_input(import_item: LicenseImportItemsModel) -> Optional[str]:
        """Get canonical input code for an import item.

        Looks up ItemNameModel names linked to the import item.

        Args:
            import_item: LicenseImportItemsModel instance

        Returns:
            Canonical input code (e.g., "PKO") or None if unmapped
        """
        if not import_item:
            return None

        # Check linked ItemNameModel entries
        if import_item.items.exists():
            item_name = import_item.items.first().name
            canonical = SionInputClassifier.resolve_canonical_input(item_name)
            return canonical.code if canonical else None

        return None

    @staticmethod
    def check_allocation_against_percentage_rules(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        import_item: LicenseImportItemsModel,
        quantity_to_allocate: Decimal,
    ) -> Tuple[bool, str]:
        """Check if a QUANTITY allocation would violate percentage constraints.

        Args:
            license_obj: LicenseDetailsModel instance
            sion_id: SionNormClassModel.id for the rule's SION
            import_item: LicenseImportItemsModel (being allocated)
            quantity_to_allocate: Quantity (in item's unit, e.g., KG) to allocate

        Returns:
            (allowed: bool, message: str) where message is empty if allowed
        """
        if not license_obj or not sion_id or not import_item:
            return True, ""

        # Get applicable rules for this SION
        rules = SionPlanningPercentageEnforcer.get_applicable_rules_for_sion(
            license_obj, sion_id
        )
        if not rules:
            return True, ""  # No percentage constraints

        # Classify the item to canonical input
        canonical_code = SionPlanningPercentageEnforcer.classify_item_input(import_item)
        if not canonical_code:
            # Item not mapped to a canonical input — not subject to percentage constraint
            return True, ""

        # Check each percentage constraint for this item's canonical input
        for rule in rules:
            if rule.percentage_constraint is None or rule.percentage_constraint <= DEC_0:
                continue  # Skip rules with no constraint

            allowed, message = SionPercentageRule.check_percentage_capacity(
                license_obj=license_obj,
                sion_id=sion_id,
                canonical_input_code=canonical_code,
                percentage=rule.percentage_constraint,
                requested_qty=quantity_to_allocate,
            )

            if not allowed:
                return False, message

        return True, ""

    @staticmethod
    def get_percentage_constraints_for_license(
        license_obj: LicenseDetailsModel,
        sion_id: int
    ) -> Dict[str, Dict]:
        """Get all percentage constraints and current QUANTITY usage for a SION.

        Returns structured information suitable for UI display.

        Args:
            license_obj: LicenseDetailsModel instance
            sion_id: SionNormClassModel.id

        Returns:
            Dict mapping canonical input code to:
                {
                    'cap_quantity': Decimal (native units),
                    'allotted_quantity': Decimal (native units),
                    'debited_quantity': Decimal (native units),
                    'remaining_quantity': Decimal (native units),
                    'percentage': Decimal,
                    'rule': SionPlanningRule instance,
                }
        """
        if not license_obj or not sion_id:
            return {}

        result = {}

        # Get all percentage-constrained rules for this SION
        rules = SionPlanningPercentageEnforcer.get_applicable_rules_for_sion(
            license_obj, sion_id
        )
        if not rules:
            return {}

        # Get usage summary by canonical input
        usage = SionBoeAllotmentClassifier.get_usage_summary_by_input(license_obj)

        # For each rule, calculate capacity and remaining quantity
        for rule in rules:
            percentage = rule.percentage_constraint
            cap = SionPercentageRule.get_percentage_cap_for_input(
                license_obj, sion_id, percentage
            )

            # Calculate usage for each input type relevant to this rule
            for canonical_code in usage:
                if canonical_code not in result:
                    allotted = usage[canonical_code]['allotted_quantity']
                    debited = usage[canonical_code]['debited_quantity']

                    result[canonical_code] = {
                        'cap_quantity': cap,
                        'allotted_quantity': allotted,
                        'debited_quantity': debited,
                        'remaining_quantity': max(DEC_0, cap - (allotted + debited)),
                        'percentage': percentage,
                        'rule': rule,
                    }

        return result
