"""Correct Split-by-% Planning: Calculate ALL requirements BEFORE allocation.

Implements proper business logic order:
1. Calculate gross entitlements from TOTAL ORIGINAL QUANTITY
2. Get existing utilization for each input (independently)
3. Calculate new targets (gross - existing)
4. Build complete CIF waterfall
5. Build requirement table (all inputs)
6. THEN run candidate allocation
7. Persist actual allocations
8. Track unmatched as SKIPPED_NO_MATCH
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from typing import Dict, List, Optional, Any


@dataclass
class InputRequirement:
    """Calculated requirement for one percentage input."""
    input_group: str
    percentage: Decimal
    gross_entitlement_qty: Decimal  # TOTAL × percentage / 100
    existing_boe_qty: Decimal
    existing_boe_cif: Decimal
    existing_allotment_qty: Decimal
    existing_allotment_cif: Decimal
    relevant_existing_qty: Decimal  # Total existing after lifecycle dedup
    relevant_existing_cif: Decimal
    target_new_qty: Decimal  # gross - existing
    cif_mode: str  # FIXED_UNIT_PRICE or RESIDUAL_CIF
    unit_price: Optional[Decimal] = None
    target_new_cif: Decimal = Decimal("0")  # For FIXED_UNIT_PRICE


@dataclass
class RequirementCalculationResult:
    """Complete requirement calculation before allocation."""
    total_original_qty: Decimal
    total_available_cif: Decimal
    requirements: List[InputRequirement]

    # CIF waterfall breakdown
    total_existing_cif: Decimal
    protected_reserves_cif: Decimal
    fixed_price_cif: Decimal
    residual_cif: Decimal

    # Metadata
    calculation_audit: Dict[str, Any] = field(default_factory=dict)


class SplitByPercentageRequirementCalculator:
    """Calculate ALL Split-by-% requirements BEFORE candidate allocation."""

    @staticmethod
    def calculate_requirements(
        total_original_qty: Decimal,
        available_cif: Decimal,
        percentage_inputs: List[Dict[str, Any]],
        existing_utilization: Dict[str, Dict[str, Decimal]],
        protected_cif_amount: Decimal = Decimal("0"),
    ) -> RequirementCalculationResult:
        """
        Calculate complete requirements for all percentage inputs.

        Args:
            total_original_qty: The ORIGINAL total planning quantity (NOT available qty)
            available_cif: Available CIF for new planning
            percentage_inputs: List of {input_group, percentage, cif_mode, unit_price}
            existing_utilization: Dict per input_group of {boe_qty, boe_cif, allotment_qty, allotment_cif}
            protected_cif_amount: CIF to reserve (e.g., Nut Products)

        Returns:
            RequirementCalculationResult with all calculations
        """
        from apps.core.constants import DEC_000

        # Step 1: Calculate gross entitlements for ALL inputs
        requirements = []
        audit = {
            "step_1_gross_entitlements": {},
            "step_2_existing_utilization": {},
            "step_3_new_targets": {},
            "step_4_cif_targets": {},
        }

        for input_config in percentage_inputs:
            input_group = input_config["input_group"]
            percentage = Decimal(str(input_config["percentage"]))

            # STEP 1: Gross entitlement from ORIGINAL total
            gross_qty = (total_original_qty * percentage / Decimal("100")).quantize(
                DEC_000, rounding=ROUND_HALF_UP
            )
            audit["step_1_gross_entitlements"][input_group] = str(gross_qty)

            # STEP 2: Get existing utilization
            existing = existing_utilization.get(input_group, {
                "boe_qty": Decimal("0"),
                "boe_cif": Decimal("0"),
                "allotment_qty": Decimal("0"),
                "allotment_cif": Decimal("0"),
            })

            existing_boe_qty = Decimal(str(existing.get("boe_qty", 0)))
            existing_boe_cif = Decimal(str(existing.get("boe_cif", 0)))
            existing_allotment_qty = Decimal(str(existing.get("allotment_qty", 0)))
            existing_allotment_cif = Decimal(str(existing.get("allotment_cif", 0)))

            # Lifecycle deduplication: if BOE realizes Allotment, use relevant existing
            # For now, assume independent (sum both)
            relevant_existing_qty = existing_boe_qty + existing_allotment_qty
            relevant_existing_cif = existing_boe_cif + existing_allotment_cif

            audit["step_2_existing_utilization"][input_group] = {
                "boe_qty": str(existing_boe_qty),
                "boe_cif": str(existing_boe_cif),
                "allotment_qty": str(existing_allotment_qty),
                "allotment_cif": str(existing_allotment_cif),
                "relevant_existing_qty": str(relevant_existing_qty),
                "relevant_existing_cif": str(relevant_existing_cif),
            }

            # STEP 3: Calculate new target (gross - existing)
            target_new_qty = max(
                Decimal("0"),
                gross_qty - relevant_existing_qty
            ).quantize(DEC_000, rounding=ROUND_HALF_UP)

            audit["step_3_new_targets"][input_group] = str(target_new_qty)

            # STEP 4: Calculate target CIF for FIXED_UNIT_PRICE mode
            cif_mode = input_config.get("cif_mode", "RESIDUAL_CIF")
            unit_price = Decimal(str(input_config.get("unit_price", 0))) if input_config.get("unit_price") else Decimal("0")
            target_new_cif = Decimal("0")

            if cif_mode == "FIXED_UNIT_PRICE" and unit_price > 0:
                target_new_cif = (target_new_qty * unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

            audit["step_4_cif_targets"][input_group] = {
                "mode": cif_mode,
                "unit_price": str(unit_price),
                "target_cif": str(target_new_cif),
            }

            # Create requirement
            requirement = InputRequirement(
                input_group=input_group,
                percentage=percentage,
                gross_entitlement_qty=gross_qty,
                existing_boe_qty=existing_boe_qty,
                existing_boe_cif=existing_boe_cif,
                existing_allotment_qty=existing_allotment_qty,
                existing_allotment_cif=existing_allotment_cif,
                relevant_existing_qty=relevant_existing_qty,
                relevant_existing_cif=relevant_existing_cif,
                target_new_qty=target_new_qty,
                cif_mode=cif_mode,
                unit_price=unit_price if cif_mode == "FIXED_UNIT_PRICE" else None,
                target_new_cif=target_new_cif,
            )
            requirements.append(requirement)

        # STEP 5: Build CIF waterfall
        total_existing_cif = sum(
            (req.relevant_existing_cif for req in requirements),
            Decimal("0")
        )
        fixed_price_cif = sum(
            (req.target_new_cif for req in requirements if req.cif_mode == "FIXED_UNIT_PRICE"),
            Decimal("0")
        )
        residual_cif = available_cif - total_existing_cif - protected_cif_amount - fixed_price_cif

        audit["step_5_cif_waterfall"] = {
            "total_available": str(available_cif),
            "existing_utilization": str(total_existing_cif),
            "protected_reserves": str(protected_cif_amount),
            "fixed_price_allocations": str(fixed_price_cif),
            "residual_cif": str(residual_cif),
        }

        # Assign residual CIF to residual-mode inputs
        residual_inputs = [r for r in requirements if r.cif_mode == "RESIDUAL_CIF"]
        if residual_inputs and len(residual_inputs) == 1:
            residual_inputs[0].target_new_cif = residual_cif

        return RequirementCalculationResult(
            total_original_qty=total_original_qty,
            total_available_cif=available_cif,
            requirements=requirements,
            total_existing_cif=total_existing_cif,
            protected_reserves_cif=protected_cif_amount,
            fixed_price_cif=fixed_price_cif,
            residual_cif=residual_cif,
            calculation_audit=audit,
        )

    @staticmethod
    def validate_requirements(result: RequirementCalculationResult) -> List[str]:
        """Validate requirement calculations. Return list of errors if any."""
        errors = []

        # Verify invariants
        for req in result.requirements:
            # actual_planned_qty must never exceed target
            if req.target_new_qty < 0:
                errors.append(f"{req.input_group}: target qty negative ({req.target_new_qty})")

            # target must never exceed gross
            if req.target_new_qty > req.gross_entitlement_qty:
                errors.append(
                    f"{req.input_group}: target ({req.target_new_qty}) > gross ({req.gross_entitlement_qty})"
                )

        # Verify CIF waterfall
        if result.residual_cif < 0:
            errors.append(f"Residual CIF negative ({result.residual_cif})")

        return errors
