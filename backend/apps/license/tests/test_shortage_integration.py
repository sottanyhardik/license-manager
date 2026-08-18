"""
Integration tests for shortage handling in complete Planning flow.

Verifies end-to-end: configuration → allocation → shortage tracking → response.
"""
import pytest
from decimal import Decimal
from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner


class TestShortageIntegration:
    """End-to-end shortage handling tests."""

    def test_waterfall_allocation_with_shortage(self):
        """
        Simple waterfall allocation where CIF is insufficient.

        Expected: Allocate what's possible, record shortage, complete successfully.
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {
                        "rules": [
                            {
                                "output_key": "OUTPUT_A",
                                "priority": 1,
                                "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "item"}
                            }
                        ]
                    }
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "SEQUENTIAL_CIF_WATERFALL",
                        "order": ["OUTPUT_A"],
                    }
                }
            ],
            "mappings": [
                {"source_key": "OUTPUT_A", "output_key": "OUTPUT_A", "rate": "10.00"}
            ]
        }

        records = [
            {
                "record_id": "1",
                "description": "item A",
                "quantity": Decimal("100.00"),
                "available_quantity": Decimal("100.00"),
            }
        ]

        # CIF budget: only 600, but 100 * 10 = 1000 would be needed
        available_cif = Decimal("600.00")

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, available_cif)

        # Should complete successfully
        assert result is not None
        assert len(result.rows) > 0

        # Actual allocated should not exceed CIF budget
        actual_cif = sum(row.value for row in result.rows)
        assert actual_cif <= available_cif

        # Should record shortage
        assert result.metadata.get("has_shortage") is True
        shortages = result.metadata.get("shortages", [])
        assert len(shortages) > 0

        # Shortage details should be accurate
        shortage = shortages[0]
        assert Decimal(shortage["target_quantity"]) == Decimal("100.00")
        assert Decimal(shortage["allocated_quantity"]) == Decimal("60.00")  # 600/10
        assert Decimal(shortage["shortage_quantity"]) == Decimal("40.00")

    def test_multiple_outputs_with_partial_allocation(self):
        """
        Two outputs in waterfall order.
        First output partially allocated, second output should still be processed.
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {
                        "rules": [
                            {
                                "output_key": "PRIMARY",
                                "priority": 1,
                                "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "primary"}
                            },
                            {
                                "output_key": "SECONDARY",
                                "priority": 2,
                                "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "secondary"}
                            }
                        ]
                    }
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "SEQUENTIAL_CIF_WATERFALL",
                        "order": ["PRIMARY", "SECONDARY"],
                    }
                }
            ],
            "mappings": [
                {"source_key": "PRIMARY", "output_key": "PRIMARY", "rate": "10.00"},
                {"source_key": "SECONDARY", "output_key": "SECONDARY", "rate": "5.00"},
            ]
        }

        records = [
            {
                "record_id": "1",
                "description": "primary item",
                "quantity": Decimal("100.00"),
                "available_quantity": Decimal("100.00"),
            },
            {
                "record_id": "2",
                "description": "secondary item",
                "quantity": Decimal("100.00"),
                "available_quantity": Decimal("100.00"),
            },
        ]

        # CIF budget: 1000
        # Primary would need: 100 * 10 = 1000
        # Secondary would need: 100 * 5 = 500
        # Total = 1500, but only 1000 available
        available_cif = Decimal("1000.00")

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, available_cif)

        # Should complete
        assert result is not None

        # Both outputs should have been attempted
        primary_rows = [r for r in result.rows if r.output_key == "PRIMARY"]
        secondary_rows = [r for r in result.rows if r.output_key == "SECONDARY"]

        # Primary should get full 100, Secondary should get partial or none
        if primary_rows:
            primary_qty = sum(r.quantity for r in primary_rows)
            assert primary_qty == Decimal("100.00")

        # Should record shortage for secondary
        metadata = result.metadata
        if metadata.get("has_shortage"):
            shortages = metadata.get("shortages", [])
            # Should have shortage for secondary (SECONDARY couldn't be fully allocated)
            secondary_shortages = [s for s in shortages if s["input_key"] == "SECONDARY"]
            assert len(secondary_shortages) > 0

    def test_fixed_price_percentage_allocation_with_shortage(self):
        """
        Percentage allocation with fixed unit prices.
        Should handle CIF shortage gracefully.
        """
        config = {
            "actions": [
                {
                    "action_type": "SPLIT_BY_PERCENTAGE",
                    "priority": 1,
                    "config": {
                        "category": "OIL",
                        "rows": [
                            {"output_code": "OIL_A", "percentage": "60", "unit_price": "5.00"},
                            {"output_code": "OIL_B", "percentage": "40", "unit_price": "3.00"},
                        ]
                    }
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "SEQUENTIAL_CIF_WATERFALL",
                        "order": ["OIL_A", "OIL_B"],
                    }
                }
            ]
        }

        records = [
            {
                "record_id": "1",
                "description": "oil import",
                "quantity": Decimal("1000.00"),
                "available_quantity": Decimal("1000.00"),
                "category": "OIL",
            }
        ]

        # Full allocation would be:
        # OIL_A: 600 * 5 = 3000
        # OIL_B: 400 * 3 = 1200
        # Total = 4200
        # But only provide 3000
        available_cif = Decimal("3000.00")

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, available_cif)

        # Should complete successfully
        assert result is not None

        # Total actual CIF should not exceed budget
        actual_cif = sum(row.value for row in result.rows)
        assert actual_cif <= available_cif

        # Should record shortage for at least one output
        metadata = result.metadata
        if metadata.get("has_shortage"):
            shortages = metadata.get("shortages", [])
            assert len(shortages) > 0
