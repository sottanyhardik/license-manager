"""Integration tests for generic SION rule engine.

Tests that the complete system works end-to-end for any SION norm with
any number of inputs, regardless of norm code.
"""
import pytest
from decimal import Decimal

from apps.core.models import SionNormClassModel, ItemNameModel, HeadSIONNormsModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, SionPlanningRule, LicenseItemPlan,
    SionInputAliasConfig,
)
from apps.license.services.sion_rule_resolver import SionRuleResolver
from apps.license.services.sion_percentage_capacity import SionPercentageCapacity
from apps.core.constants import DEC_0


@pytest.fixture
def setup_generic_norm(db):
    """Set up a completely generic SION norm with 4 inputs, custom codes, custom products."""
    head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="Custom Norms")
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="CUSTOM",
        defaults={"head_norm": head_norm, "description": "Custom Multi-Input Norm"}
    )

    # Create output item
    output_item, _ = ItemNameModel.objects.get_or_create(
        name="MIXED_GOODS",
        defaults={"sion_norm_class": sion}
    )

    # Create custom input aliases (not PKO/OLIVE_OIL - completely different)
    aliases = [
        ("COMPONENT_A", "RAW MATERIAL A"),
        ("COMPONENT_A", "MATERIAL_A"),  # Alternate name
        ("COMPONENT_B", "RAW MATERIAL B"),
        ("COMPONENT_C", "RAW MATERIAL C"),
        ("COMPONENT_D", "RAW MATERIAL D"),
    ]
    for canonical, alias in aliases:
        SionInputAliasConfig.objects.get_or_create(
            sion=sion,
            alias_normalized=SionRuleResolver.normalize_product_name(alias),
            defaults={
                "canonical_input_code": canonical,
                "source_description": f"Custom norm mapping: {alias} → {canonical}",
                "is_active": True,
            }
        )

    # Create 4-way split rule: 35/30/20/15
    # First create PERCENTAGE_CAP rules (master caps) and SPLIT_PERCENTAGE rules (for splitting)
    for i, (name, pct) in enumerate([
        ("COMPONENT_A", "35"),
        ("COMPONENT_B", "30"),
        ("COMPONENT_C", "20"),
        ("COMPONENT_D", "15"),
    ], start=1):
        # Create PERCENTAGE_CAP rule (master entitlement cap)
        SionPlanningRule.objects.create(
            sion=sion,
            import_item=output_item,
            name=name,
            max_unit_price=Decimal("100.00"),
            unit="KG",
            priority=i,
            is_active=True,
            percentage_constraint=Decimal(pct),
            rule_type="PERCENTAGE_CAP",
            rule_group_id="CUSTOM_4way",
        )
        # Create SPLIT_PERCENTAGE rule (for transaction splitting)
        SionPlanningRule.objects.create(
            sion=sion,
            import_item=output_item,
            name=f"{name}_SPLIT",
            max_unit_price=Decimal("100.00"),
            unit="KG",
            priority=i + 100,
            is_active=True,
            percentage_constraint=Decimal(pct),
            rule_type="SPLIT_PERCENTAGE",
            rule_group_id="CUSTOM_4way",
        )

    # Create license with 1000 KG eligible quantity
    license_obj = LicenseDetailsModel.objects.create(
        license_number="CUSTOM-TEST-001",
    )
    LicenseExportItemModel.objects.create(
        license=license_obj,
        norm_class=sion,
        net_quantity=Decimal("1000.00"),
        unit="KG",
    )

    return {
        "sion": sion,
        "output_item": output_item,
        "license": license_obj,
        "aliases": {
            "COMPONENT_A": ["RAW MATERIAL A", "MATERIAL_A"],
            "COMPONENT_B": ["RAW MATERIAL B"],
            "COMPONENT_C": ["RAW MATERIAL C"],
            "COMPONENT_D": ["RAW MATERIAL D"],
        }
    }


class TestGenericNormIntegration:
    """Integration tests for generic norm support."""

    def test_generic_norm_product_resolution(self, setup_generic_norm):
        """Products can be resolved using custom aliases."""
        norm = setup_generic_norm["sion"]

        # Test all alias variants
        for canonical, aliases in setup_generic_norm["aliases"].items():
            for alias in aliases:
                mapping = SionRuleResolver.resolve_canonical_input(alias, sion=norm)
                assert mapping.canonical_code == canonical, f"Failed for {alias}"
                assert mapping.is_mapped is True

    def test_generic_norm_percentage_caps(self, setup_generic_norm):
        """Percentage caps work for generic norm with any number of inputs."""
        sion = setup_generic_norm["sion"]
        output_item = setup_generic_norm["output_item"]
        license_obj = setup_generic_norm["license"]

        # Get percentage rules
        rules_dict = SionRuleResolver.get_percentage_rules_for_output_item(
            output_item, sion
        )
        assert rules_dict == {
            "COMPONENT_A": Decimal("35"),
            "COMPONENT_B": Decimal("30"),
            "COMPONENT_C": Decimal("20"),
            "COMPONENT_D": Decimal("15"),
        }

        # Verify total equals 100%
        total = sum(rules_dict.values())
        assert total == Decimal("100")

        # Verify caps are calculated correctly
        total_qty = SionPercentageCapacity.get_total_eligible_quantity(
            license_obj, sion.pk
        )
        assert total_qty == Decimal("1000.00")

        for component, percentage in rules_dict.items():
            cap = SionPercentageCapacity.get_percentage_cap_for_canonical_input(
                license_obj, sion.pk, component, percentage
            )
            expected_cap = total_qty * percentage / Decimal("100")
            assert cap == expected_cap

    def test_generic_norm_split_validation(self, setup_generic_norm):
        """Split rules for generic norm are validated correctly."""
        sion = setup_generic_norm["sion"]
        output_item = setup_generic_norm["output_item"]

        # Get split rules (should be valid)
        split_rules = SionRuleResolver.get_split_rules_for_output_item(
            output_item, sion
        )
        assert len(split_rules) == 4
        assert sum(split_rules.values()) == Decimal("100")

        # Validate
        is_valid, msg = SionRuleResolver.validate_split_rule_configuration(split_rules)
        assert is_valid is True
        assert msg is None

    def test_generic_norm_no_hardcoding(self, setup_generic_norm):
        """No hardcoding of specific norm codes anywhere."""
        sion = setup_generic_norm["sion"]
        output_item = setup_generic_norm["output_item"]

        # The entire system should work without knowing it's "CUSTOM" norm
        # If there was hardcoding of E126/E132, it would fail here
        rules = SionRuleResolver.get_rules_for_output_item(output_item, sion)
        assert len(rules) == 8  # 4 PERCENTAGE_CAP + 4 SPLIT_PERCENTAGE

        # All rule types should be recognized generically
        for rule_info in rules:
            assert rule_info.rule_type in ["PERCENTAGE_CAP", "SPLIT_PERCENTAGE", "QUANTITY_CAP"]
            assert rule_info.percentage is not None

    def test_multiple_norms_different_configs(self, db):
        """Multiple norms can have completely different configurations."""
        head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="Test Norms")

        # Create two completely different norms
        sion_a, _ = SionNormClassModel.objects.get_or_create(
            norm_class="NORM_A",
            defaults={"head_norm": head_norm}
        )
        sion_b, _ = SionNormClassModel.objects.get_or_create(
            norm_class="NORM_B",
            defaults={"head_norm": head_norm}
        )

        output_a, _ = ItemNameModel.objects.get_or_create(
            name="OUTPUT_A",
            defaults={"sion_norm_class": sion_a}
        )
        output_b, _ = ItemNameModel.objects.get_or_create(
            name="OUTPUT_B",
            defaults={"sion_norm_class": sion_b}
        )

        # NORM_A: 3 inputs
        for i, (name, pct) in enumerate([("X", "50"), ("Y", "30"), ("Z", "20")], start=1):
            SionPlanningRule.objects.create(
                sion=sion_a,
                import_item=output_a,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="PERCENTAGE_CAP",
            )

        # NORM_B: 2 inputs
        for i, (name, pct) in enumerate([("M", "60"), ("N", "40")], start=1):
            SionPlanningRule.objects.create(
                sion=sion_b,
                import_item=output_b,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="PERCENTAGE_CAP",
            )

        # Verify isolation
        rules_a = SionRuleResolver.get_percentage_rules_for_output_item(output_a, sion_a)
        rules_b = SionRuleResolver.get_percentage_rules_for_output_item(output_b, sion_b)

        assert len(rules_a) == 3
        assert len(rules_b) == 2
        assert set(rules_a.keys()) == {"X", "Y", "Z"}
        assert set(rules_b.keys()) == {"M", "N"}

    def test_output_item_specific_rules(self, db):
        """Same SION can have different rules for different output items."""
        head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="Test Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E250",
            defaults={"head_norm": head_norm}
        )

        output_1, _ = ItemNameModel.objects.get_or_create(
            name="OUTPUT_1",
            defaults={"sion_norm_class": sion}
        )
        output_2, _ = ItemNameModel.objects.get_or_create(
            name="OUTPUT_2",
            defaults={"sion_norm_class": sion}
        )

        # Output 1: 50/50 split
        for i, (name, pct) in enumerate([("OUTPUT1_A", "50"), ("OUTPUT1_B", "50")], start=1):
            SionPlanningRule.objects.create(
                sion=sion,
                import_item=output_1,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="PERCENTAGE_CAP",
            )

        # Output 2: 60/40 split (different!) - priority continues from output_1
        for i, (name, pct) in enumerate([("OUTPUT2_A", "60"), ("OUTPUT2_C", "40")], start=3):
            SionPlanningRule.objects.create(
                sion=sion,
                import_item=output_2,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="PERCENTAGE_CAP",
            )

        # Verify different rules for different outputs
        rules_1 = SionRuleResolver.get_percentage_rules_for_output_item(output_1, sion)
        rules_2 = SionRuleResolver.get_percentage_rules_for_output_item(output_2, sion)

        assert rules_1 == {"OUTPUT1_A": Decimal("50"), "OUTPUT1_B": Decimal("50")}
        assert rules_2 == {"OUTPUT2_A": Decimal("60"), "OUTPUT2_C": Decimal("40")}

        # Rules for different outputs are completely different
        assert rules_1 != rules_2
