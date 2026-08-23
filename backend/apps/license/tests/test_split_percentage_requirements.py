"""Tests for Split-by-% requirement calculation (BEFORE allocation).

Critical: Requirements must be calculated completely BEFORE candidate allocation.
This prevents the bug where first matching item consumed all CIF.
"""

import pytest
from decimal import Decimal

from apps.license.services.split_by_percentage_requirement_calculator import (
    SplitByPercentageRequirementCalculator,
)


class TestBasicPercentageEntitlements:
    """Test basic percentage calculations from original total."""

    def test_simple_50_50_split(self):
        """Verify 50/50 split calculates gross entitlements correctly."""
        # Total = 100 KG, PKO 50%, OLIVE 50%
        result = SplitByPercentageRequirementCalculator.calculate_requirements(
            total_original_qty=Decimal("100"),
            available_cif=Decimal("500"),
            percentage_inputs=[
                {"input_group": "PKO", "percentage": Decimal("50"), "cif_mode": "FIXED_UNIT_PRICE", "unit_price": Decimal("1.80")},
                {"input_group": "OLIVE_OIL", "percentage": Decimal("50"), "cif_mode": "RESIDUAL_CIF"},
            ],
            existing_utilization={},
        )

        assert len(result.requirements) == 2
        pko = [r for r in result.requirements if r.input_group == "PKO"][0]
        olive = [r for r in result.requirements if r.input_group == "OLIVE_OIL"][0]

        assert pko.gross_entitlement_qty == Decimal("50.000")
        assert olive.gross_entitlement_qty == Decimal("50.000")
        assert pko.target_new_qty == Decimal("50.000")  # No existing
        assert olive.target_new_qty == Decimal("50.000")  # No existing


class TestRequirementsWithExistingUtilization:
    """Test requirement calculation after deducting existing utilization."""

    def test_190_residual_example(self):
        """
        Acceptance test: $190 residual example from spec.

        Total Qty = 100
        Total CIF = $500

        PKO = 50%
        Olive = 50%

        Food Flavour Existing CIF = $100
        Olive Existing Qty = 10, CIF = $120
        PKO Existing Qty = 0

        PKO New Unit Price = $1.80

        Expected:
        PKO Target = 50 KG, CIF = $90
        OLIVE Target = 40 KG, Residual CIF = $190
        """
        result = SplitByPercentageRequirementCalculator.calculate_requirements(
            total_original_qty=Decimal("100"),
            available_cif=Decimal("500"),
            percentage_inputs=[
                {"input_group": "PKO", "percentage": Decimal("50"), "cif_mode": "FIXED_UNIT_PRICE", "unit_price": Decimal("1.80")},
                {"input_group": "OLIVE_OIL", "percentage": Decimal("50"), "cif_mode": "RESIDUAL_CIF"},
            ],
            existing_utilization={
                "OLIVE_OIL": {
                    "boe_qty": Decimal("10"),
                    "boe_cif": Decimal("120"),
                    "allotment_qty": Decimal("0"),
                    "allotment_cif": Decimal("0"),
                }
            },
            protected_cif_amount=Decimal("100"),  # Food Flavour
        )

        # Verify requirements
        pko = [r for r in result.requirements if r.input_group == "PKO"][0]
        olive = [r for r in result.requirements if r.input_group == "OLIVE_OIL"][0]

        # Gross entitlements
        assert pko.gross_entitlement_qty == Decimal("50.000")
        assert olive.gross_entitlement_qty == Decimal("50.000")

        # Existing utilization
        assert pko.relevant_existing_qty == Decimal("0.000")
        assert olive.relevant_existing_qty == Decimal("10.000")
        assert olive.relevant_existing_cif == Decimal("120.00")

        # New targets
        assert pko.target_new_qty == Decimal("50.000")
        assert olive.target_new_qty == Decimal("40.000")

        # PKO CIF (fixed price)
        assert pko.target_new_cif == Decimal("90.00")  # 50 × 1.80

        # CIF waterfall
        assert result.total_existing_cif == Decimal("120.00")  # Olive existing
        assert result.protected_reserves_cif == Decimal("100.00")  # Food Flavour
        assert result.fixed_price_cif == Decimal("90.00")  # PKO new

        # Residual: 500 - 120 - 100 - 90 = 190
        assert result.residual_cif == Decimal("190.00")

        # Verify invariants
        errors = SplitByPercentageRequirementCalculator.validate_requirements(result)
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_185_residual_example(self):
        """
        Acceptance test: $185 residual example from spec.

        Total Qty = 100
        Total CIF = $500

        PKO:
        50%
        Existing Qty = 10
        Existing CIF = $23
        New Unit Price = $1.80

        Olive:
        50%
        Existing Qty = 10
        Existing CIF = $120

        Expected:
        PKO Target = 40 KG, CIF = $72
        OLIVE Target = 40 KG, Residual CIF = $185
        """
        result = SplitByPercentageRequirementCalculator.calculate_requirements(
            total_original_qty=Decimal("100"),
            available_cif=Decimal("500"),
            percentage_inputs=[
                {"input_group": "PKO", "percentage": Decimal("50"), "cif_mode": "FIXED_UNIT_PRICE", "unit_price": Decimal("1.80")},
                {"input_group": "OLIVE_OIL", "percentage": Decimal("50"), "cif_mode": "RESIDUAL_CIF"},
            ],
            existing_utilization={
                "PKO": {
                    "boe_qty": Decimal("10"),
                    "boe_cif": Decimal("23"),
                    "allotment_qty": Decimal("0"),
                    "allotment_cif": Decimal("0"),
                },
                "OLIVE_OIL": {
                    "boe_qty": Decimal("10"),
                    "boe_cif": Decimal("120"),
                    "allotment_qty": Decimal("0"),
                    "allotment_cif": Decimal("0"),
                }
            },
            protected_cif_amount=Decimal("100"),  # Food Flavour
        )

        # Verify requirements
        pko = [r for r in result.requirements if r.input_group == "PKO"][0]
        olive = [r for r in result.requirements if r.input_group == "OLIVE_OIL"][0]

        # New targets (gross - existing)
        assert pko.target_new_qty == Decimal("40.000")  # 50 - 10
        assert olive.target_new_qty == Decimal("40.000")  # 50 - 10

        # PKO CIF (fixed price)
        assert pko.target_new_cif == Decimal("72.00")  # 40 × 1.80

        # CIF waterfall
        assert result.total_existing_cif == Decimal("143.00")  # PKO 23 + Olive 120
        assert result.protected_reserves_cif == Decimal("100.00")
        assert result.fixed_price_cif == Decimal("72.00")

        # Residual: 500 - 143 - 100 - 72 = 185
        assert result.residual_cif == Decimal("185.00")

        # Verify invariants
        errors = SplitByPercentageRequirementCalculator.validate_requirements(result)
        assert len(errors) == 0, f"Validation errors: {errors}"


class TestInvariants:
    """Test calculation invariants."""

    def test_target_never_exceeds_gross(self):
        """Verify target_new_qty <= gross_entitlement_qty always."""
        result = SplitByPercentageRequirementCalculator.calculate_requirements(
            total_original_qty=Decimal("100"),
            available_cif=Decimal("500"),
            percentage_inputs=[
                {"input_group": "PKO", "percentage": Decimal("50"), "cif_mode": "FIXED_UNIT_PRICE", "unit_price": Decimal("1.80")},
            ],
            existing_utilization={
                "PKO": {"boe_qty": Decimal("5"), "boe_cif": Decimal("0"), "allotment_qty": Decimal("0"), "allotment_cif": Decimal("0")}
            },
        )

        pko = result.requirements[0]
        assert pko.target_new_qty <= pko.gross_entitlement_qty

    def test_existing_cannot_exceed_gross(self):
        """If existing > gross, target should be 0, not negative."""
        result = SplitByPercentageRequirementCalculator.calculate_requirements(
            total_original_qty=Decimal("100"),
            available_cif=Decimal("500"),
            percentage_inputs=[
                {"input_group": "PKO", "percentage": Decimal("50"), "cif_mode": "FIXED_UNIT_PRICE", "unit_price": Decimal("1.80")},
            ],
            existing_utilization={
                "PKO": {"boe_qty": Decimal("100"), "boe_cif": Decimal("0"), "allotment_qty": Decimal("0"), "allotment_cif": Decimal("0")}
            },
        )

        pko = result.requirements[0]
        assert pko.target_new_qty == Decimal("0.000")  # 50 - 100 = -50, clamped to 0
        assert pko.target_new_cif == Decimal("0.00")  # 0 × 1.80


class TestNutProductsReserve:
    """Test protected CIF reserve calculation."""

    def test_nut_products_reserve_protects_cif(self):
        """Verify protected CIF is deducted from residual."""
        result = SplitByPercentageRequirementCalculator.calculate_requirements(
            total_original_qty=Decimal("100"),
            available_cif=Decimal("500"),
            percentage_inputs=[
                {"input_group": "PKO", "percentage": Decimal("50"), "cif_mode": "FIXED_UNIT_PRICE", "unit_price": Decimal("1.80")},
                {"input_group": "OLIVE_OIL", "percentage": Decimal("50"), "cif_mode": "RESIDUAL_CIF"},
            ],
            existing_utilization={},
            protected_cif_amount=Decimal("100"),  # Nut Products reserve
        )

        # Residual should exclude protected amount
        # 500 - 0 (existing) - 100 (protected) - 90 (PKO) = 310
        assert result.residual_cif == Decimal("310.00")
        assert result.protected_reserves_cif == Decimal("100.00")
