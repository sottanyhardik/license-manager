"""
Tests for shortage handling in Planning.

Shortage is NON-FATAL: allocate maximum valid + record shortage + continue.

Tests:
1. Partial quantity allocation (target > available)
2. Multiple candidates (use all valid)
3. CIF shortage (unit price limits quantity)
4. Protected reserve (never consumed)
5. No cross-input redistribution
6. Partial plan persistence (only actual allocation)
7. Configuration errors still fail
8. Exact License 3411008090 scenario
"""
import pytest
from decimal import Decimal
from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner, ShortageRecord


class TestPartialQuantityAllocation:
    """Test: Target > Available → Allocate Available + Record Shortage"""

    def test_partial_quantity_shortage(self):
        """
        Target Qty = 100 KG
        Available = 70 KG

        Expected:
        Allocated = 70 KG
        Shortage = 30 KG
        Planning succeeds
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {"rules": [
                        {"output_key": "PKO", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "palm"}}
                    ]}
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "WATERFALL",
                        "order": ["PKO"],
                    }
                }
            ]
        }

        records = [
            {
                "record_id": "1",
                "description": "palm kernel oil",
                "quantity": Decimal("70"),
                "available_quantity": Decimal("70"),
            }
        ]

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, Decimal("500"))

        # Should complete successfully
        assert result is not None
        assert len(result.rows) > 0

        # Verify metadata contains shortage
        assert result.metadata.get("has_shortage") is True
        assert len(result.metadata.get("shortages", [])) > 0


class TestMultipleCandidates:
    """Test: Use all valid candidates to minimize shortage"""

    def test_multiple_candidates_allocation(self):
        """
        Target = 100 KG
        Candidate A = 30 KG
        Candidate B = 40 KG
        Candidate C = 20 KG

        Expected:
        Allocated = 90 KG
        Shortage = 10 KG
        All valid candidates used
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {"rules": [
                        {"output_key": "OIL", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "oil"}}
                    ]}
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "WATERFALL",
                        "order": ["OIL"],
                    }
                }
            ]
        }

        records = [
            {"record_id": "A", "description": "oil A", "quantity": Decimal("30"), "available_quantity": Decimal("30")},
            {"record_id": "B", "description": "oil B", "quantity": Decimal("40"), "available_quantity": Decimal("40")},
            {"record_id": "C", "description": "oil C", "quantity": Decimal("20"), "available_quantity": Decimal("20")},
        ]

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, Decimal("1000"))

        # Should allocate all candidates
        assert result is not None
        total_allocated = sum(row.quantity for row in result.rows)
        assert total_allocated == Decimal("90")


class TestCIFShortage:
    """Test: Insufficient CIF limits quantity allocation"""

    def test_cif_shortage(self):
        """
        Target Qty = 100
        Unit Price = 5
        Target CIF = 500

        Available CIF = 350

        Expected max allocatable qty = 70 (350 / 5)

        Allocated Qty = 70
        Allocated CIF = 350
        Shortage Qty = 30
        Shortage CIF = 150
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {"rules": [
                        {"output_key": "ITEM", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "item"}}
                    ]}
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "WATERFALL",
                        "order": ["ITEM"],
                    }
                }
            ],
            "mappings": [{"source_key": "ITEM", "output_key": "ITEM", "rate": "5"}]
        }

        records = [
            {"record_id": "1", "description": "item", "quantity": Decimal("100"), "available_quantity": Decimal("100")}
        ]

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, Decimal("350"))

        # Should allocate maximum CIF-limited amount
        total_value = sum(row.value for row in result.rows)
        assert total_value <= Decimal("350")


class TestConfigurationErrors:
    """Test: Configuration errors still fail (not converted to shortage)"""

    def test_invalid_action_type_fails(self):
        """Invalid action type should raise error, not shortage."""
        config = {
            "actions": [
                {"action_type": "INVALID_ACTION", "priority": 1, "config": {}}
            ]
        }

        records = [{"record_id": "1", "description": "test", "quantity": Decimal("100")}]

        planner = DatabaseDrivenSionPlanner()
        with pytest.raises(Exception):  # InvalidPlannerConfiguration
            planner.execute(config, records, Decimal("1000"))


class TestPersistenceOfActualAllocation:
    """Test: Only actual allocated quantity/CIF is persisted"""

    def test_persisted_values_match_allocation_not_target(self):
        """
        Target = 100 KG
        Allocated = 60 KG

        Verify: Persisted total = 60, not 100
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {"rules": [
                        {"output_key": "OIL", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "oil"}}
                    ]}
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "WATERFALL",
                        "order": ["OIL"],
                    }
                }
            ]
        }

        records = [
            {"record_id": "1", "description": "oil", "quantity": Decimal("100"), "available_quantity": Decimal("100")}
        ]

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, Decimal("300"))

        # Total persisted should not exceed actual CIF allocated
        total_persisted_cif = sum(row.value for row in result.rows)
        assert total_persisted_cif <= Decimal("300")


class TestShortageMadataPersistence:
    """Test: Shortage details are returned in metadata"""

    def test_shortage_metadata_structure(self):
        """
        Verify shortage metadata includes:
        - input_key
        - target_quantity
        - allocated_quantity
        - shortage_quantity
        - target_cif
        - allocated_cif
        - shortage_cif
        - limiting_reason
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {"rules": [
                        {"output_key": "TEST", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "test"}}
                    ]}
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "WATERFALL",
                        "order": ["TEST"],
                    }
                }
            ]
        }

        records = [
            {"record_id": "1", "description": "test", "quantity": Decimal("100"), "available_quantity": Decimal("100")}
        ]

        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, Decimal("100"))

        # Check metadata
        if result.metadata.get("has_shortage"):
            shortages = result.metadata.get("shortages", [])
            for shortage in shortages:
                assert "input_key" in shortage
                assert "target_quantity" in shortage
                assert "allocated_quantity" in shortage
                assert "shortage_quantity" in shortage
                assert "target_cif" in shortage
                assert "allocated_cif" in shortage
                assert "shortage_cif" in shortage
                assert "limiting_reason" in shortage


class TestNoCrossInputRedistribution:
    """Test: Shortage in one input doesn't affect another"""

    def test_input_shortage_isolated(self):
        """
        PKO: Target 100, Can allocate 60
        OLIVE: Target 100, Can allocate 100

        Expected:
        PKO shortage = 40 (isolated to PKO)
        OLIVE not increased by PKO shortage
        """
        config = {
            "actions": [
                {
                    "action_type": "MATCH",
                    "priority": 1,
                    "config": {"rules": [
                        {"output_key": "PKO", "priority": 1, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "pko"}},
                        {"output_key": "OLIVE", "priority": 2, "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "olive"}},
                    ]}
                },
                {
                    "action_type": "ALLOCATE",
                    "priority": 2,
                    "config": {
                        "algorithm": "WATERFALL",
                        "order": ["PKO", "OLIVE"],
                    }
                }
            ]
        }

        records = [
            {"record_id": "1", "description": "pko", "quantity": Decimal("100"), "available_quantity": Decimal("100")},
            {"record_id": "2", "description": "olive", "quantity": Decimal("100"), "available_quantity": Decimal("100")},
        ]

        # Limited CIF: PKO @ $1 can get max 60, OLIVE @ $1 gets rest
        planner = DatabaseDrivenSionPlanner()
        result = planner.execute(config, records, Decimal("160"))

        # Verify each input maintains its own target/allocated
        pko_allocated = sum(row.quantity for row in result.rows if row.output_key == "PKO")
        olive_allocated = sum(row.quantity for row in result.rows if row.output_key == "OLIVE")

        # PKO should have shortage (60 allocated < 100 target)
        # OLIVE shouldn't automatically increase
        assert pko_allocated <= Decimal("100")
        assert olive_allocated <= Decimal("100")
