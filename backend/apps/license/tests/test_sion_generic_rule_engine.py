"""Tests for generic SION rule engine supporting any norm and any number of inputs.

Tests the new data-driven alias system and rule resolver that makes the
architecture work for any SION norm, not just E126/E132.
"""
import pytest
from decimal import Decimal

from apps.core.models import SionNormClassModel, ItemNameModel, HeadSIONNormsModel
from apps.license.models import (
    LicenseDetailsModel, SionPlanningRule, SionInputAliasConfig,
)
from apps.license.services.sion_rule_resolver import SionRuleResolver
from apps.core.constants import DEC_0


@pytest.fixture
def head_norm(db):
    """Create HeadSIONNormsModel."""
    head, _ = HeadSIONNormsModel.objects.get_or_create(name="E Norms")
    return head


@pytest.fixture
def sion_e126(db, head_norm):
    """Create E126 SION norm."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E126",
        defaults={"head_norm": head_norm, "description": "Imported Vegetable Oils"}
    )
    return sion


@pytest.fixture
def sion_e132(db, head_norm):
    """Create E132 SION norm."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E132",
        defaults={"head_norm": head_norm, "description": "Imported Fats & Cheese"}
    )
    return sion


@pytest.fixture
def sion_custom_3way(db, head_norm):
    """Create a custom SION norm with 3-way split for testing."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E199",
        defaults={"head_norm": head_norm, "description": "Custom 3-way test norm"}
    )
    return sion


@pytest.fixture
def output_item_e126(db, sion_e126):
    """Create an output item for E126."""
    item, _ = ItemNameModel.objects.get_or_create(
        name="OIL - E126",
        defaults={"sion_norm_class": sion_e126}
    )
    return item


@pytest.fixture
def output_item_e132(db, sion_e132):
    """Create an output item for E132."""
    item, _ = ItemNameModel.objects.get_or_create(
        name="FATS - E132",
        defaults={"sion_norm_class": sion_e132}
    )
    return item


@pytest.fixture
def output_item_custom(db, sion_custom_3way):
    """Create an output item for custom 3-way norm."""
    item, _ = ItemNameModel.objects.get_or_create(
        name="MIXED - E199",
        defaults={"sion_norm_class": sion_custom_3way}
    )
    return item


class TestSionRuleResolverBasics:
    """Test basic rule resolver functionality."""

    def test_normalize_product_name_basic(self):
        """Product name normalization works correctly."""
        assert SionRuleResolver.normalize_product_name("PKO") == "PKO"
        assert SionRuleResolver.normalize_product_name("pko") == "PKO"
        assert SionRuleResolver.normalize_product_name("  pko  ") == "PKO"
        assert SionRuleResolver.normalize_product_name("PALM KERNEL OIL") == "PALM KERNEL OIL"
        assert SionRuleResolver.normalize_product_name("palm   kernel   oil") == "PALM KERNEL OIL"

    @pytest.mark.django_db
    def test_resolve_canonical_input_with_legacy_fallback(self):
        """Fallback to legacy aliases when SionInputAliasConfig not present."""
        # Without explicit alias config, should use legacy hardcoded aliases
        mapping = SionRuleResolver.resolve_canonical_input("PKO")
        assert mapping.canonical_code == "PKO"
        assert mapping.is_mapped is True

        mapping = SionRuleResolver.resolve_canonical_input("PALM KERNEL OIL")
        assert mapping.canonical_code == "PKO"
        assert mapping.is_mapped is True

    @pytest.mark.django_db
    def test_resolve_unknown_product(self):
        """Unknown products resolve to UNMAPPED."""
        mapping = SionRuleResolver.resolve_canonical_input("UNKNOWN PRODUCT")
        assert mapping.canonical_code == "UNMAPPED"
        assert mapping.is_mapped is False


class TestDataDrivenAliasResolution:
    """Test data-driven SionInputAliasConfig alias resolution."""

    def test_alias_creation_and_lookup(self, db, sion_e126):
        """Aliases can be created and looked up."""
        alias = SionInputAliasConfig.objects.create(
            sion=sion_e126,
            canonical_input_code="PKO_TEST",
            alias_normalized="PKO_TEST",
            source_description="E126 PKO",
            is_active=True,
        )
        assert alias.id is not None

    def test_sion_scoped_alias_resolution(self, db, sion_e126, sion_e132):
        """Aliases are scoped to specific SION norms."""
        # Create PKO -> "PRODUCT_A" mapping for E126 only
        SionInputAliasConfig.objects.create(
            sion=sion_e126,
            canonical_input_code="PKO",
            alias_normalized="PRODUCT_A",
            is_active=True,
        )

        # Create PKO -> "PRODUCT_B" mapping for E132 only
        SionInputAliasConfig.objects.create(
            sion=sion_e132,
            canonical_input_code="PKO",
            alias_normalized="PRODUCT_B",
            is_active=True,
        )

        # Resolve should use sion-scoped aliases
        mapping_e126 = SionRuleResolver.resolve_canonical_input(
            "PRODUCT_A", sion=sion_e126
        )
        assert mapping_e126.canonical_code == "PKO"

        mapping_e132 = SionRuleResolver.resolve_canonical_input(
            "PRODUCT_B", sion=sion_e132
        )
        assert mapping_e132.canonical_code == "PKO"

    def test_inactive_aliases_ignored(self, db, sion_e126):
        """Inactive aliases are not used in resolution."""
        SionInputAliasConfig.objects.create(
            sion=sion_e126,
            canonical_input_code="PKO",
            alias_normalized="OLD_PRODUCT",
            is_active=False,
        )

        mapping = SionRuleResolver.resolve_canonical_input(
            "OLD_PRODUCT", sion=sion_e126
        )
        assert mapping.is_mapped is False


class TestGenericRuleResolution:
    """Test rule resolution that works for any SION norm."""

    def test_rules_by_output_item(self, db, sion_e126, output_item_e126):
        """Rules can be retrieved by output_item and sion."""
        # Create rules for this output item
        rule1 = SionPlanningRule.objects.create(
            sion=sion_e126,
            import_item=output_item_e126,
            name="PKO",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=1,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            rule_type="PERCENTAGE_CAP",
        )
        rule2 = SionPlanningRule.objects.create(
            sion=sion_e126,
            import_item=output_item_e126,
            name="OLIVE_OIL",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=2,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            rule_type="PERCENTAGE_CAP",
        )

        rules = SionRuleResolver.get_rules_for_output_item(
            output_item_e126, sion_e126
        )
        assert len(rules) == 2
        assert rules[0].rule.id == rule1.id
        assert rules[1].rule.id == rule2.id

    def test_percentage_rules_dict(self, db, sion_e126, output_item_e126):
        """Percentage rules are returned as dict mapping input->percentage."""
        SionPlanningRule.objects.create(
            sion=sion_e126,
            import_item=output_item_e126,
            name="PKO",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=1,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            rule_type="PERCENTAGE_CAP",
        )
        SionPlanningRule.objects.create(
            sion=sion_e126,
            import_item=output_item_e126,
            name="OLIVE_OIL",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=2,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            rule_type="PERCENTAGE_CAP",
        )

        rules_dict = SionRuleResolver.get_percentage_rules_for_output_item(
            output_item_e126, sion_e126
        )
        assert rules_dict == {
            "PKO": Decimal("50.00"),
            "OLIVE_OIL": Decimal("50.00"),
        }

    def test_split_percentage_rules_valid(self, db, sion_custom_3way, output_item_custom):
        """Split rules are returned only if they sum to 100%."""
        # Create valid 40/35/25 split
        for i, (name, pct) in enumerate([("INPUT_A", "40"), ("INPUT_B", "35"), ("INPUT_C", "25")], start=1):
            SionPlanningRule.objects.create(
                sion=sion_custom_3way,
                import_item=output_item_custom,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="SPLIT_PERCENTAGE",
                rule_group_id="3way_split",
            )

        split_dict = SionRuleResolver.get_split_rules_for_output_item(
            output_item_custom, sion_custom_3way, "3way_split"
        )
        assert len(split_dict) == 3
        assert split_dict["INPUT_A"] == Decimal("40")
        assert split_dict["INPUT_B"] == Decimal("35")
        assert split_dict["INPUT_C"] == Decimal("25")

    def test_split_percentage_rules_invalid_total(self, db, sion_custom_3way, output_item_custom):
        """Invalid split rules (not summing to 100%) are rejected."""
        # Create invalid 50/30/15 split (not 100%)
        for i, (name, pct) in enumerate([("INPUT_A", "50"), ("INPUT_B", "30"), ("INPUT_C", "15")], start=1):
            SionPlanningRule.objects.create(
                sion=sion_custom_3way,
                import_item=output_item_custom,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="SPLIT_PERCENTAGE",
                rule_group_id="invalid_split",
            )

        split_dict = SionRuleResolver.get_split_rules_for_output_item(
            output_item_custom, sion_custom_3way, "invalid_split"
        )
        # Should return empty dict because total is not 100%
        assert split_dict == {}


class TestSplitRuleValidation:
    """Test split rule validation."""

    def test_validate_valid_split(self):
        """Valid split configuration is accepted."""
        rule_dict = {
            "INPUT_A": Decimal("50"),
            "INPUT_B": Decimal("50"),
        }
        is_valid, msg = SionRuleResolver.validate_split_rule_configuration(rule_dict)
        assert is_valid is True
        assert msg is None

    def test_validate_3way_split(self):
        """Valid 3-way split is accepted."""
        rule_dict = {
            "INPUT_A": Decimal("40"),
            "INPUT_B": Decimal("35"),
            "INPUT_C": Decimal("25"),
        }
        is_valid, msg = SionRuleResolver.validate_split_rule_configuration(rule_dict)
        assert is_valid is True

    def test_validate_invalid_total(self):
        """Split not summing to 100% is rejected."""
        rule_dict = {
            "INPUT_A": Decimal("50"),
            "INPUT_B": Decimal("30"),
        }
        is_valid, msg = SionRuleResolver.validate_split_rule_configuration(rule_dict)
        assert is_valid is False
        assert "sum to 100" in msg.lower()

    def test_validate_empty_config(self):
        """Empty configuration is rejected."""
        is_valid, msg = SionRuleResolver.validate_split_rule_configuration({})
        assert is_valid is False
        assert "no configured inputs" in msg.lower()

    def test_validate_zero_percentage(self):
        """Zero percentage is rejected."""
        rule_dict = {
            "INPUT_A": Decimal("100"),
            "INPUT_B": Decimal("0"),
        }
        is_valid, msg = SionRuleResolver.validate_split_rule_configuration(rule_dict)
        assert is_valid is False
        assert "invalid percentage" in msg.lower()


class TestGenericNormSupport:
    """Test that the system works for norms beyond E126/E132."""

    def test_custom_norm_rules(self, db, sion_custom_3way, output_item_custom):
        """Custom norms with custom input codes work generically."""
        # Create rules with custom input codes
        for i, (name, pct) in enumerate([("CUSTOM_A", "40"), ("CUSTOM_B", "35"), ("CUSTOM_C", "25")], start=1):
            SionPlanningRule.objects.create(
                sion=sion_custom_3way,
                import_item=output_item_custom,
                name=name,
                max_unit_price=Decimal("50.00"),
                unit="KG",
                priority=i,
                is_active=True,
                percentage_constraint=Decimal(pct),
                rule_type="PERCENTAGE_CAP",
            )

        rules_dict = SionRuleResolver.get_percentage_rules_for_output_item(
            output_item_custom, sion_custom_3way
        )
        assert "CUSTOM_A" in rules_dict
        assert "CUSTOM_B" in rules_dict
        assert "CUSTOM_C" in rules_dict

    def test_multiple_norms_isolation(self, db, sion_e126, sion_e132, output_item_e126, output_item_e132):
        """Rules for different norms don't interfere with each other."""
        # E126: 50/50
        SionPlanningRule.objects.create(
            sion=sion_e126,
            import_item=output_item_e126,
            name="PKO",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=1,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            rule_type="PERCENTAGE_CAP",
        )
        SionPlanningRule.objects.create(
            sion=sion_e126,
            import_item=output_item_e126,
            name="OLIVE_OIL",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=2,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            rule_type="PERCENTAGE_CAP",
        )

        # E132: 60/40
        SionPlanningRule.objects.create(
            sion=sion_e132,
            import_item=output_item_e132,
            name="PKO",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=1,
            is_active=True,
            percentage_constraint=Decimal("60.00"),
            rule_type="PERCENTAGE_CAP",
        )
        SionPlanningRule.objects.create(
            sion=sion_e132,
            import_item=output_item_e132,
            name="CHEESE",
            max_unit_price=Decimal("50.00"),
            unit="KG",
            priority=2,
            is_active=True,
            percentage_constraint=Decimal("40.00"),
            rule_type="PERCENTAGE_CAP",
        )

        # Verify isolation
        e126_rules = SionRuleResolver.get_percentage_rules_for_output_item(
            output_item_e126, sion_e126
        )
        e132_rules = SionRuleResolver.get_percentage_rules_for_output_item(
            output_item_e132, sion_e132
        )

        assert "OLIVE_OIL" in e126_rules and "OLIVE_OIL" not in e132_rules
        assert "CHEESE" in e132_rules and "CHEESE" not in e126_rules
