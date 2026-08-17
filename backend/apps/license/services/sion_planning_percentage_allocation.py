"""Calculate percentage-based quantity splits for SION planning.

Implements the SPLIT_BY_PERCENTAGE strategy which allocates a total planning
quantity across multiple percentage-constrained inputs according to configured
percentage rules.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from apps.core.constants import DEC_0
from apps.license.models import (
    LicenseDetailsModel, SionPlanningRule, LicenseExportItemModel
)
from apps.license.services.sion_input_classifier import SionInputClassifier
from apps.license.services.sion_percentage_rule import SionPercentageRule
from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier


class PercentageAllocationFailure(ValueError):
    """Raised when percentage allocation cannot be executed."""
    def __init__(self, message: str, status: str = "FAILED"):
        self.message = message
        self.status = status
        super().__init__(message)


class SionPlanningPercentageAllocationService:
    """Calculate and validate percentage-based quantity allocations for planning."""

    @staticmethod
    def allocate_by_percentage(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        planning_quantity: Decimal,
    ) -> Dict[str, any]:
        """Allocate planning quantity according to percentage rules for a SION.

        Args:
            license_obj: LicenseDetailsModel instance
            sion_id: SionNormClassModel.id
            planning_quantity: Total quantity (in native units) to allocate

        Returns:
            {
                'status': 'SUCCESS' | 'CAPACITY_EXCEEDED' | 'INVALID_CONFIG' | 'NO_RULES',
                'total_quantity': Decimal (requested),
                'max_quantity': Decimal (maximum possible under constraints),
                'allocations': [
                    {
                        'input': 'PKO',
                        'percentage': Decimal('50.00'),
                        'allocated_quantity': Decimal('500.000'),
                        'cap_quantity': Decimal('500.000'),
                        'remaining_capacity': Decimal('200.000'),
                        'status': 'OK' | 'CAPACITY_EXCEEDED',
                        'message': str or None,
                    },
                    ...
                ],
            }
        """
        if not license_obj or not sion_id or not planning_quantity:
            return {
                'status': 'INVALID_CONFIG',
                'message': 'License, SION, and quantity are required.',
                'total_quantity': planning_quantity,
                'allocations': [],
            }

        # Get all percentage-constrained rules for this SION
        rules = list(SionPlanningRule.objects.filter(
            sion_id=sion_id,
            percentage_constraint__isnull=False,
        ).exclude(percentage_constraint=DEC_0).order_by('output_item__name'))

        if not rules:
            return {
                'status': 'NO_RULES',
                'message': 'No percentage-constrained rules found for this SION.',
                'total_quantity': planning_quantity,
                'allocations': [],
            }

        # Validate percentages sum to 100%
        total_percentage = sum(Decimal(str(rule.percentage_constraint or 0)) for rule in rules)
        if total_percentage != Decimal('100'):
            return {
                'status': 'INVALID_CONFIG',
                'message': f'Percentage rules must sum to 100%, got {total_percentage}%',
                'total_quantity': planning_quantity,
                'allocations': [],
            }

        # Calculate allocations
        allocations = []
        has_failure = False

        for rule in rules:
            percentage = Decimal(str(rule.percentage_constraint))
            canonical_code = (rule.output_item.name if rule.output_item else '').upper()

            # Calculate allocated quantity for this input
            allocated_qty = (planning_quantity * percentage / Decimal('100')).quantize(
                Decimal('0.001'), rounding=ROUND_HALF_UP
            )

            # Get current usage (allotted + debited)
            allotted = SionPercentageRule.get_allotted_for_input(license_obj, canonical_code)
            debited = SionPercentageRule.get_debited_for_input(license_obj, canonical_code)
            cap = SionPercentageRule.get_percentage_cap_for_input(license_obj, sion_id, percentage)
            used = allotted + debited
            remaining = max(DEC_0, cap - used)

            # Check if allocation is within capacity
            allocation_ok = allocated_qty <= remaining
            if not allocation_ok:
                has_failure = True

            allocations.append({
                'input': canonical_code,
                'percentage': percentage,
                'allocated_quantity': allocated_qty,
                'cap_quantity': cap,
                'used_quantity': used,
                'allotted_quantity': allotted,
                'debited_quantity': debited,
                'remaining_capacity': remaining,
                'status': 'OK' if allocation_ok else 'CAPACITY_EXCEEDED',
                'message': (
                    None if allocation_ok
                    else f'{canonical_code} would exceed capacity by {allocated_qty - remaining} units'
                ),
                'rule_id': rule.pk,
            })

        return {
            'status': 'CAPACITY_EXCEEDED' if has_failure else 'SUCCESS',
            'total_quantity': planning_quantity,
            'max_quantity': SionPlanningPercentageAllocationService._calculate_max_quantity(
                license_obj, sion_id, rules
            ),
            'allocations': allocations,
        }

    @staticmethod
    def _calculate_max_quantity(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        rules: List[SionPlanningRule],
    ) -> Decimal:
        """Calculate the maximum quantity that can be allocated under percentage constraints.

        For each input:
            input_max = remaining_capacity / (percentage / 100)

        Overall max:
            max = MIN(all input_max values)
        """
        if not rules:
            return DEC_0

        input_maxes = []

        for rule in rules:
            percentage_frac = Decimal(str(rule.percentage_constraint or 0)) / Decimal('100')
            if percentage_frac <= DEC_0:
                continue

            canonical_code = (rule.output_item.name if rule.output_item else '').upper()
            cap = SionPercentageRule.get_percentage_cap_for_input(license_obj, sion_id, rule.percentage_constraint)
            allotted = SionPercentageRule.get_allotted_for_input(license_obj, canonical_code)
            debited = SionPercentageRule.get_debited_for_input(license_obj, canonical_code)
            remaining = max(DEC_0, cap - (allotted + debited))

            # How much total quantity can we allocate if this input gets its percentage?
            input_max = (remaining / percentage_frac).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            input_maxes.append(input_max)

        return min(input_maxes) if input_maxes else DEC_0

    @staticmethod
    def validate_allocation_request(
        license_obj: LicenseDetailsModel,
        sion_id: int,
        planning_quantity: Decimal,
    ) -> Tuple[bool, Optional[str]]:
        """Validate that a percentage allocation request is feasible.

        Returns:
            (allowed: bool, error_message: str or None)
        """
        result = SionPlanningPercentageAllocationService.allocate_by_percentage(
            license_obj, sion_id, planning_quantity
        )

        if result['status'] != 'SUCCESS':
            failures = [
                a['message'] for a in result.get('allocations', [])
                if a.get('message')
            ]
            message = result.get('message') or '; '.join(failures) or 'Allocation failed'
            return False, message

        return True, None
