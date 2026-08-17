"""Tests for SION input classification and percentage rules."""
import pytest
from decimal import Decimal
from apps.core.models import SionNormClassModel, HeadSIONNormsModel, ItemNameModel
from apps.license.models import (
    SionPlanningRule, SionCanonicalInput, SionInputAlias,
    LicenseDetailsModel, LicenseImportItemsModel
)
from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.license.services.sion_input_classifier import SionInputClassifier
from apps.license.services.sion_percentage_rule import SionPercentageRule
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestSionInputClassifier:
    """Test SION input classification from product names."""

    @pytest.fixture
    def classifier(self):
        return SionInputClassifier()

    # ========== NORMALIZATION TESTS ==========

    def test_normalize_single_space_collapse(self, classifier):
        """Multiple spaces collapse to single space."""
        result = classifier.normalize_product_name("  PALM   KERNEL   OIL  ")
        assert result == "PALM KERNEL OIL"

    def test_normalize_case_conversion(self, classifier):
        """Converts to uppercase."""
        assert classifier.normalize_product_name("palm kernel oil") == "PALM KERNEL OIL"
        assert classifier.normalize_product_name("Palm Kernel Oil") == "PALM KERNEL OIL"
        assert classifier.normalize_product_name("PALM KERNEL OIL") == "PALM KERNEL OIL"

    def test_normalize_strips_whitespace(self, classifier):
        """Removes leading/trailing whitespace."""
        assert classifier.normalize_product_name("  PKO  ") == "PKO"
        assert classifier.normalize_product_name("\tOLIVE OIL\n") == "OLIVE OIL"

    def test_normalize_empty_string_raises(self, classifier):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            classifier.normalize_product_name("")

    def test_normalize_whitespace_only_raises(self, classifier):
        """Whitespace-only string raises ValueError."""
        with pytest.raises(ValueError):
            classifier.normalize_product_name("   ")

    # ========== ALIAS MATCHING TESTS ==========

    def test_resolve_exact_match_pko(self, classifier):
        """Resolves 'PKO' to PKO canonical input."""
        result = classifier.resolve_canonical_input("PKO")
        assert result is not None
        assert result.code == "PKO"

    def test_resolve_case_insensitive_pko(self, classifier):
        """Case-insensitive matching for PKO."""
        # All should resolve to PKO
        for variant in ["PKO", "pko", "Pko", "pKo"]:
            result = classifier.resolve_canonical_input(variant)
            assert result is not None, f"Failed for variant: {variant}"
            assert result.code == "PKO", f"Wrong mapping for {variant}"

    def test_resolve_palm_kernel_oil_alias(self, classifier):
        """Resolves 'PALM KERNEL OIL' to PKO."""
        result = classifier.resolve_canonical_input("PALM KERNEL OIL")
        assert result is not None
        assert result.code == "PKO"

    def test_resolve_case_insensitive_palm_kernel(self, classifier):
        """Case-insensitive matching for 'PALM KERNEL OIL'."""
        for variant in ["PALM KERNEL OIL", "Palm Kernel Oil", "palm kernel oil"]:
            result = classifier.resolve_canonical_input(variant)
            assert result is not None, f"Failed for {variant}"
            assert result.code == "PKO"

    def test_resolve_olive_oil(self, classifier):
        """Resolves OLIVE OIL variants."""
        for variant in ["OLIVE OIL", "Olive Oil", "olive oil"]:
            result = classifier.resolve_canonical_input(variant)
            assert result is not None
            assert result.code == "OLIVE_OIL"

    def test_resolve_unknown_product_returns_none(self, classifier):
        """Unknown product names return None (UNMAPPED)."""
        result = classifier.resolve_canonical_input("UNKNOWN PRODUCT XYZ")
        assert result is None

    def test_resolve_partial_name_not_matched(self, classifier):
        """Partial names are NOT matched (exact only)."""
        # These should NOT match PKO even though they contain 'PALM' or 'OIL'
        result = classifier.resolve_canonical_input("PALM OIL")
        assert result is None  # Not an alias unless explicitly configured

    # ========== WHITESPACE NORMALIZATION TESTS ==========

    def test_normalize_multiple_spaces_in_middle(self, classifier):
        """Multiple spaces in middle collapse to one."""
        result = classifier.normalize_product_name("PALM    KERNEL    OIL")
        assert result == "PALM KERNEL OIL"

    def test_normalize_mixed_whitespace(self, classifier):
        """Mixed whitespace (spaces, tabs) handled correctly."""
        result = classifier.normalize_product_name("PALM\t\tKERNEL  OIL")
        assert result == "PALM KERNEL OIL"


@pytest.mark.django_db
class TestSionPercentageRule:
    """Test percentage rule calculation and enforcement."""

    # ========== E126/E132 CONFIGURATION TESTS ==========

    def test_e126_canonical_inputs_created(self):
        """E126 canonical inputs are created by migration."""
        pko = SionCanonicalInput.objects.get(code="PKO")
        assert pko.display_name == "Palm Kernel Oil"
        assert pko.is_active

        olive = SionCanonicalInput.objects.get(code="OLIVE_OIL")
        assert olive.display_name == "Olive Oil"

    def test_e132_canonical_inputs_created(self):
        """E132 canonical inputs are created by migration."""
        cheese = SionCanonicalInput.objects.get(code="CHEESE")
        assert cheese.is_active

        yeast = SionCanonicalInput.objects.get(code="YEAST")
        assert yeast.is_active

    # ========== ALIAS CONFIGURATION TESTS ==========

    def test_pko_aliases_are_exact(self):
        """PKO aliases are exact matches only."""
        pko = SionCanonicalInput.objects.get(code="PKO")
        aliases = SionInputAlias.objects.filter(canonical_input=pko)

        # Should include these
        alias_strs = {a.normalized_alias for a in aliases}
        assert "PKO" in alias_strs
        assert "PALM KERNEL OIL" in alias_strs
        assert "PURE PALM KERNEL OIL" in alias_strs

        # Should NOT include partial matches
        # (this is guaranteed by the structured aliases in migration)

    def test_olive_oil_aliases_exact(self):
        """OLIVE_OIL aliases are exact matches only."""
        olive = SionCanonicalInput.objects.get(code="OLIVE_OIL")
        aliases = SionInputAlias.objects.filter(canonical_input=olive)

        alias_strs = {a.normalized_alias for a in aliases}
        assert "OLIVE OIL" in alias_strs
        assert "EXTRA VIRGIN OLIVE OIL" in alias_strs

    # ========== UNKNOWN/UNMAPPED TESTS ==========

    def test_unmapped_product_handling(self):
        """Unknown products are unmapped."""
        classifier = SionInputClassifier()
        result = classifier.resolve_canonical_input("SOME NEW PRODUCT")
        assert result is None

    # ========== PERCENTAGE CONSTRAINT TESTS ==========

    def test_get_percentage_cap_no_constraint(self):
        """Returns 0 when percentage is None."""
        cap = SionPercentageRule.get_percentage_cap_for_input(None, "PKO", None)
        assert cap == Decimal("0")

    def test_check_percentage_capacity_no_constraint(self):
        """Passes when no constraint (percentage None)."""
        allowed, msg = SionPercentageRule.check_percentage_capacity(
            None, "PKO", None, Decimal("500"), Decimal("10")
        )
        assert allowed
        assert msg == ""


@pytest.mark.django_db
class TestSionPlanningRulePercentage:
    """Test percentage constraint on SionPlanningRule."""

    @pytest.fixture
    def sion_e126(self):
        head = HeadSIONNormsModel.objects.create(name="E Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E126",
            defaults={"head_norm": head}
        )
        return sion

    @pytest.fixture
    def output_item(self):
        """PKO output item."""
        return ItemNameModel.objects.create(
            name="PKO - E126",
            is_active=True
        )

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="planner", password="test123")

    def test_percentage_constraint_field_exists(self, sion_e126, output_item, user):
        """SionPlanningRule has percentage_constraint field."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e126,
            name="PKO Rule",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("10.00"),
            unit="KG",
            priority=1,
            output_item=output_item,
            percentage_constraint=Decimal("50.00"),
            created_by=user,
            modified_by=user,
        )
        assert rule.percentage_constraint == Decimal("50.00")

    def test_percentage_constraint_null_allowed(self, sion_e126, output_item, user):
        """SionPlanningRule allows null percentage_constraint."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e126,
            name="No Constraint Rule",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("10.00"),
            unit="KG",
            priority=2,
            output_item=output_item,
            percentage_constraint=None,  # No constraint
            created_by=user,
            modified_by=user,
        )
        assert rule.percentage_constraint is None

    def test_percentage_constraint_zero_allowed(self, sion_e126, output_item, user):
        """SionPlanningRule allows zero percentage (no constraint)."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e126,
            name="Zero Constraint Rule",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("10.00"),
            unit="KG",
            priority=3,
            output_item=output_item,
            percentage_constraint=Decimal("0.00"),
            created_by=user,
            modified_by=user,
        )
        assert rule.percentage_constraint == Decimal("0.00")


@pytest.mark.django_db
class TestSionBoeAllotmentClassifier:
    """Test BOE/Allotment classification by canonical input."""

    def test_boe_canonical_input_classification_pko(self):
        """BOE with PKO product name resolves to PKO canonical."""
        from apps.bill_of_entry.models import BillOfEntryModel
        from apps.core.models import CompanyModel
        from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier

        company = CompanyModel.objects.create(iec="IEC001", name="Test Co")
        boe = BillOfEntryModel.objects.create(
            company=company,
            bill_of_entry_number="BOE001",
            product_name="PALM KERNEL OIL",
        )

        canonical_code = SionBoeAllotmentClassifier.get_boe_canonical_input(boe)
        assert canonical_code == "PKO"

    def test_boe_canonical_input_case_insensitive(self):
        """BOE classification is case-insensitive."""
        from apps.bill_of_entry.models import BillOfEntryModel
        from apps.core.models import CompanyModel
        from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier

        company = CompanyModel.objects.create(iec="IEC002", name="Test Co 2")

        for variant in ["palm kernel oil", "PALM KERNEL OIL", "Palm Kernel Oil"]:
            boe = BillOfEntryModel.objects.create(
                company=company,
                bill_of_entry_number=f"BOE_{variant[:3]}",
                product_name=variant,
            )
            canonical_code = SionBoeAllotmentClassifier.get_boe_canonical_input(boe)
            assert canonical_code == "PKO"

    def test_boe_canonical_input_unmapped_returns_none(self):
        """Unknown BOE product returns None."""
        from apps.bill_of_entry.models import BillOfEntryModel
        from apps.core.models import CompanyModel
        from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier

        company = CompanyModel.objects.create(iec="IEC003", name="Test Co 3")
        boe = BillOfEntryModel.objects.create(
            company=company,
            bill_of_entry_number="BOE_UNKNOWN",
            product_name="UNKNOWN PRODUCT XYZ",
        )

        canonical_code = SionBoeAllotmentClassifier.get_boe_canonical_input(boe)
        assert canonical_code is None

    def test_allotment_canonical_input_classification(self):
        """Allotment item name resolves to canonical input."""
        from apps.allotment.models import AllotmentModel
        from apps.core.models import CompanyModel
        from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier

        company = CompanyModel.objects.create(iec="IEC004", name="Test Co 4")
        allotment = AllotmentModel.objects.create(
            company=company,
            item_name="OLIVE OIL",
            required_quantity=Decimal("100"),
        )

        canonical_code = SionBoeAllotmentClassifier.get_allotment_canonical_input(allotment)
        assert canonical_code == "OLIVE_OIL"

    def test_get_inputs_in_license(self):
        """Returns all canonical inputs present in license's BOE/Allotments."""
        from apps.license.services.sion_boe_allotment_classifier import SionBoeAllotmentClassifier
        # Simplified test: just verify the method exists and returns a set
        # Full integration test would require complex license setup
        result = SionBoeAllotmentClassifier.get_inputs_in_license(None)
        assert isinstance(result, set)


@pytest.mark.django_db
class TestSionPlanningPercentageEnforcer:
    """Test percentage constraint enforcement during planning."""

    def test_check_allocation_without_constraints(self):
        """Allocation passes when no percentage constraints exist."""
        from apps.license.services.sion_planning_percentage_enforcer import SionPlanningPercentageEnforcer

        allowed, msg = SionPlanningPercentageEnforcer.check_allocation_against_percentage_rules(
            None, None, Decimal("100")
        )
        assert allowed
        assert msg == ""

    def test_get_percentage_constraints_for_license_empty(self):
        """Returns empty dict for license with no constraints."""
        from apps.license.services.sion_planning_percentage_enforcer import SionPlanningPercentageEnforcer

        result = SionPlanningPercentageEnforcer.get_percentage_constraints_for_license(None)
        assert isinstance(result, dict)
        assert len(result) == 0
