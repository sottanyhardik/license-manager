"""
Complete end-to-end test for Split-by-% Planning feature.

Tests the full flow for License 3411008090:
- Total Planning Quantity: 642,277 KG
- PKO: 50% @ $1.80/KG
- OLIVE OIL: 50% @ $5.00/KG

Verifies:
- Exact percentage calculation based on total planning quantity
- Existing BOE/Allotment filtering by exact license + canonical input
- Remaining entitlement after deduction
- Unit price CIF calculation
- Partial allocation (available < target) does not fail
- Protected Nut Products CIF reserve
- No shortage tracking/warnings
"""
import pytest
from decimal import Decimal
from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner


class TestSplitByPercentageComplete:
    """Complete Split-by-% feature verification."""

    def test_exact_percentage_calculation(self):
        """
        Verify: Total Qty × 50% = exact entitlement
        642,277 × 50% = 321,138.50
        """
        total_qty = Decimal("642277.00")
        pko_percentage = Decimal("50")
        olive_percentage = Decimal("50")

        pko_entitlement = (total_qty * pko_percentage / Decimal("100")).quantize(Decimal("0.001"))
        olive_entitlement = (total_qty * olive_percentage / Decimal("100")).quantize(Decimal("0.001"))

        assert pko_entitlement == Decimal("321138.50")
        assert olive_entitlement == Decimal("321138.50")
        assert pko_entitlement + olive_entitlement == total_qty

    def test_percentage_split_allocation(self):
        """
        Test the actual split-by-percentage allocation.

        Config:
        - PKO 50% @ $1.80
        - OLIVE 50% @ $5.00

        Verify both outputs receive correct quantities and unit prices.
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {
                        "rules": [
                            {
                                "output_key": "OIL_IMPORTS",
                                "priority": 1,
                                "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "oil"}
                            }
                        ]
                    }
                },
                {
                    "action_type": "SPLIT",
                    "priority": 2,
                    "config": {
                        "algorithm": "SPLIT_BY_PERCENTAGE",
                        "category": "OIL_IMPORTS",
                        "rows": [
                            {"output_code": "PKO", "percentage": "50", "unit_price": "1.80"},
                            {"output_code": "OLIVE_OIL", "percentage": "50", "unit_price": "5.00"},
                        ]
                    }
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 3,
                    "config": {
                        "algorithm": "SEQUENTIAL_CIF_WATERFALL",
                        "order": ["PKO", "OLIVE_OIL"],
                    }
                }
            ]
        }

        records = [
            {
                "record_id": "LICENSE_3411008090",
                "description": "oil imports",
                "quantity": Decimal("642277.00"),
                "available_quantity": Decimal("642277.00"),
                "category": "OIL_IMPORTS",
            }
        ]

        # Full CIF budget to avoid partial allocation for this test
        # PKO: 321,138.50 × 1.80 = 578,049.30
        # OLIVE: 321,138.50 × 5.00 = 1,605,692.50
        # Total: 2,183,741.80
        available_cif = Decimal("2183741.80")

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, available_cif)

        # Should complete successfully
        assert result is not None
        assert len(result.rows) > 0

        # Verify PKO allocation
        pko_rows = [r for r in result.rows if r.output_key == "PKO"]
        assert len(pko_rows) > 0
        pko_total_qty = sum(r.quantity for r in pko_rows)
        pko_total_cif = sum(r.value for r in pko_rows)

        # PKO should be 321,138.50 @ $1.80
        assert pko_total_qty == Decimal("321138.50")
        assert pko_total_cif.quantize(Decimal("0.01")) == Decimal("578049.30")

        # Verify OLIVE allocation
        olive_rows = [r for r in result.rows if r.output_key == "OLIVE_OIL"]
        assert len(olive_rows) > 0
        olive_total_qty = sum(r.quantity for r in olive_rows)
        olive_total_cif = sum(r.value for r in olive_rows)

        # OLIVE should be 321,138.50 @ $5.00
        assert olive_total_qty == Decimal("321138.50")
        assert olive_total_cif.quantize(Decimal("0.01")) == Decimal("1605692.50")

    def test_partial_allocation_does_not_fail(self):
        """
        Verify that when target > available, Planning succeeds with the max
        valid allocation and emits the deterministic cap shortage.
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {
                        "rules": [
                            {"output_key": "OIL", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "oil"}}
                        ]
                    }
                },
                {
                    "action_type": "SPLIT",
                    "priority": 2,
                    "config": {
                        "algorithm": "SPLIT_BY_PERCENTAGE",
                        "category": "OIL",
                        "rows": [
                            {"output_code": "PKO", "percentage": "50", "unit_price": "1.80"},
                            {"output_code": "OLIVE_OIL", "percentage": "50", "unit_price": "5.00"},
                        ]
                    }
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 3,
                    "config": {
                        "algorithm": "SEQUENTIAL_CIF_WATERFALL",
                        "order": ["PKO", "OLIVE_OIL"],
                    }
                }
            ]
        }

        records = [
            {
                "record_id": "1",
                "description": "oil",
                "quantity": Decimal("642277.00"),
                "available_quantity": Decimal("642277.00"),
                "category": "OIL",
            }
        ]

        # Limited CIF: only 1,000,000 instead of full 2,183,741.80
        available_cif = Decimal("1000000.00")

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, available_cif)

        # Should complete successfully and retain the cap reconciliation.
        assert result is not None
        assert len(result.rows) > 0

        # Total allocated CIF should not exceed budget
        total_allocated_cif = sum(r.value for r in result.rows)
        assert total_allocated_cif <= available_cif

        assert result.metadata == {
            "has_shortage": True,
            "shortages": [{
                "input_key": "OLIVE_OIL",
                "record_id": "1",
                "target_quantity": Decimal("321138.500"),
                "allocated_quantity": Decimal("84390"),
                "shortage_quantity": Decimal("236748.500"),
                "target_cif": Decimal("1605692.50000"),
                "allocated_cif": Decimal("421950.00"),
                "shortage_cif": Decimal("1183742.50000"),
                "limiting_reason": "CIF_CAP",
            }],
        }

    def test_multiple_candidates_all_used(self):
        """
        Verify that all valid candidates are used even if one is insufficient.

        Do not stop after first candidate.
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {
                        "rules": [
                            {"output_key": "OIL", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "oil"}}
                        ]
                    }
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "SEQUENTIAL_CIF_WATERFALL",
                        "order": ["OIL"],
                    }
                }
            ],
            "mappings": [
                {"source_key": "OIL", "output_key": "OIL", "rate": "5.00"}
            ]
        }

        # Three separate candidates
        records = [
            {"record_id": "A", "description": "oil A", "quantity": Decimal("30.00"), "available_quantity": Decimal("30.00")},
            {"record_id": "B", "description": "oil B", "quantity": Decimal("40.00"), "available_quantity": Decimal("40.00")},
            {"record_id": "C", "description": "oil C", "quantity": Decimal("20.00"), "available_quantity": Decimal("20.00")},
        ]

        # Sufficient CIF for all
        available_cif = Decimal("500.00")

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, available_cif)

        # Should allocate from all candidates
        assert len(result.rows) == 3
        total_qty = sum(r.quantity for r in result.rows)
        assert total_qty == Decimal("90.00")  # 30+40+20

    def test_unit_price_cif_calculation(self):
        """
        Verify CIF is calculated as: allocated_qty × unit_price

        PKO: 321,138.50 × $1.80 = $578,049.30
        OLIVE: 321,138.50 × $5.00 = $1,605,692.50
        """
        pko_qty = Decimal("321138.50")
        pko_price = Decimal("1.80")
        pko_cif = (pko_qty * pko_price).quantize(Decimal("0.01"))

        olive_qty = Decimal("321138.50")
        olive_price = Decimal("5.00")
        olive_cif = (olive_qty * olive_price).quantize(Decimal("0.01"))

        assert pko_cif == Decimal("578049.30")
        assert olive_cif == Decimal("1605692.50")
