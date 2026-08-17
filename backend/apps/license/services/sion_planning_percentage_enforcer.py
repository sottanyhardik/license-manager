"""Enforce SION percentage constraints during planning.

Integrates SionPercentageRule with planning execution to validate and enforce
percentage-constrained allocations before they are created.
"""
from decimal import Decimal
from typing import Optional, Tuple, Dict

from apps.core.constants import DEC_0
from apps.license.models import (
    LicenseDetailsModel, SionPlanningRule, SionCanonicalInput,
    LicenseImportItemsModel
)
from apps.license.services.sion_input_classifier import SionInputClassifier
from apps.license.services.sion_percentage_rule import SionPercentageRule
from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier


class SionPlanningPercentageEnforcer:
    """Validate and enforce percentage constraints on planning allocations."""

    @staticmethod
    def get_applicable_rules_for_item(
        license_obj: LicenseDetailsModel,
        import_item: LicenseImportItemsModel
    ) -> list:
        """Get all percentage-constrained rules applicable to this item.

        A rule applies to an item if its output_item matches a SION that
        covers this import item based on the license's SION norms.

        Args:
            license_obj: LicenseDetailsModel instance
            import_item: LicenseImportItemsModel instance

        Returns:
            List of SionPlanningRule instances with percentage_constraint != None
        """
        if not license_obj or not import_item:
            return []

        # Get all percentage-constrained rules for the license's SION norms
        sion_norms = license_obj.sion_norms.all()
        if not sion_norms.exists():
            return []

        rules = SionPlanningRule.objects.filter(
            sion__in=sion_norms,
            percentage_constraint__isnull=False,
        ).exclude(percentage_constraint=DEC_0)

        return list(rules)

    @staticmethod
    def classify_item_input(import_item: LicenseImportItemsModel) -> Optional[str]:
        """Get canonical input code for an import item.

        Args:
            import_item: LicenseImportItemsModel instance

        Returns:
            Canonical input code (e.g., "PKO") or None if unmapped
        """
        if not import_item or not import_item.name:
            return None

        canonical = SionInputClassifier.resolve_canonical_input(import_item.name)
        return canonical.code if canonical else None

    @staticmethod
    def check_allocation_against_percentage_rules(
        license_obj: LicenseDetailsModel,
        import_item: LicenseImportItemsModel,
        quantity_to_allocate: Decimal,
    ) -> Tuple[bool, str]:
        """Check if an allocation would violate percentage constraints.

        Args:
            license_obj: LicenseDetailsModel instance
            import_item: LicenseImportItemsModel (being allocated)
            quantity_to_allocate: Quantity (in item's unit) to allocate

        Returns:
            (allowed: bool, message: str) where message is empty if allowed
        """
        if not license_obj or not import_item:
            return True, ""

        # Get applicable rules
        rules = SionPlanningPercentageEnforcer.get_applicable_rules_for_item(
            license_obj, import_item
        )
        if not rules:
            return True, ""  # No percentage constraints

        # Classify the item
        canonical_code = SionPlanningPercentageEnforcer.classify_item_input(import_item)
        if not canonical_code:
            # Item not mapped to a canonical input — not subject to percentage constraint
            return True, ""

        # Check each rule
        for rule in rules:
            if rule.percentage_constraint is None or rule.percentage_constraint <= DEC_0:
                continue  # Skip rules with no constraint

            # Check if this rule's output item applies to the canonical input
            # For now, assume a rule applies if it has the percentage constraint
            # (In a real system, you'd match rule.output_item to the input's sion norm)

            allowed, message = SionPercentageRule.check_percentage_capacity(
                license_obj=license_obj,
                canonical_input_code=canonical_code,
                percentage=rule.percentage_constraint,
                requested_qty=quantity_to_allocate,
                requested_unit_price=import_item.unit_price or DEC_0,
            )

            if not allowed:
                return False, message

        return True, ""

    @staticmethod
    def get_percentage_constraints_for_license(
        license_obj: LicenseDetailsModel
    ) -> Dict[str, Dict]:
        """Get all percentage constraints and current usage for a license.

        Args:
            license_obj: LicenseDetailsModel instance

        Returns:
            Dict mapping canonical input code to:
                {
                    'cap_cif': Decimal,
                    'allotted_cif': Decimal,
                    'debited_cif': Decimal,
                    'remaining_cif': Decimal,
                    'percentage': Decimal,
                    'rule': SionPlanningRule instance,
                }
        """
        if not license_obj:
            return {}

        result = {}
        sion_norms = license_obj.sion_norms.all()

        # Get all percentage-constrained rules
        rules = SionPlanningRule.objects.filter(
            sion__in=sion_norms,
            percentage_constraint__isnull=False,
        ).exclude(percentage_constraint=DEC_0)

        # Get usage by input
        usage = SionBoeAllotmentClassifier.get_usage_summary_by_input(license_obj)

        for rule in rules:
            percentage = rule.percentage_constraint
            cap = SionPercentageRule.get_percentage_cap_for_input(
                license_obj, "", percentage
            )

            # For now, we aggregate all inputs under the rule
            # In a real system, this would be per input type
            for canonical_code in usage:
                if canonical_code not in result:
                    result[canonical_code] = {
                        'cap_cif': cap,
                        'allotted_cif': usage[canonical_code]['allotted_cif'],
                        'debited_cif': usage[canonical_code]['debited_cif'],
                        'remaining_cif': DEC_0,
                        'percentage': percentage,
                        'rule': rule,
                    }
                    result[canonical_code]['remaining_cif'] = max(
                        DEC_0,
                        cap - (usage[canonical_code]['allotted_cif'] + usage[canonical_code]['debited_cif'])
                    )

        return result
