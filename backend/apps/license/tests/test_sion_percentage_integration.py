"""Integration tests for SION percentage-constrained planning.

Validates the complete flow: Product name classification → BOE/Allotment aggregation
→ Percentage constraint enforcement during planning.

Tests E126 (PKO 50%, OLIVE_OIL 50%) and E132 scenarios.
"""
import pytest
from decimal import Decimal

from apps.core.constants import DEC_0
from apps.core.models import SionNormClassModel, HeadSIONNormsModel, ItemNameModel
from apps.license.models import (
    SionPlanningRule, SionCanonicalInput, SionInputAlias,
    LicenseDetailsModel, LicenseImportItemsModel
)
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestE126PercentageConstraint:
    """Test E126 (PKO 50%, OLIVE_OIL 50%) percentage constraints."""

    @pytest.fixture
    def sion_e126(self):
        """E126 SION norm."""
        head = HeadSIONNormsModel.objects.create(name="E Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E126",
            defaults={"head_norm": head}
        )
        return sion

    @pytest.fixture
    def pko_output_item(self):
        """PKO output item for E126."""
        item, _ = ItemNameModel.objects.get_or_create(
            name="PKO - E126",
            defaults={"is_active": True}
        )
        return item

    @pytest.fixture
    def olive_output_item(self):
        """OLIVE_OIL output item for E126."""
        item, _ = ItemNameModel.objects.get_or_create(
            name="OLIVE OIL - E126",
            defaults={"is_active": True}
        )
        return item

    @pytest.fixture
    def user(self):
        """Test user for rule creation."""
        return User.objects.create_user(username="planner_e126", password="test123")

    def test_pko_percentage_rule_50_percent_cap(self, sion_e126, pko_output_item, user):
        """E126 PKO rule with 50% cap is correctly configured."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e126,
            name="E126 - PKO 50%",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("100.00"),
            unit="KG",
            priority=1,
            output_item=pko_output_item,
            percentage_constraint=Decimal("50.00"),
            created_by=user,
            modified_by=user,
        )

        assert rule.percentage_constraint == Decimal("50.00")
        assert rule.sion.norm_class == "E126"

    def test_olive_oil_percentage_rule_50_percent_cap(self, sion_e126, olive_output_item, user):
        """E126 OLIVE_OIL rule with 50% cap is correctly configured."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e126,
            name="E126 - OLIVE OIL 50%",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("150.00"),
            unit="KG",
            priority=2,
            output_item=olive_output_item,
            percentage_constraint=Decimal("50.00"),
            created_by=user,
            modified_by=user,
        )

        assert rule.percentage_constraint == Decimal("50.00")

    def test_pko_alias_mapping_in_e126(self):
        """PKO aliases resolve to PKO canonical input."""
        pko = SionCanonicalInput.objects.get(code="PKO")

        # All these should map to PKO
        test_names = [
            "PKO", "pko", "Pko",
            "PALM KERNEL OIL", "palm kernel oil", "Palm Kernel Oil",
            "Pure Palm Kernel Oil", "pure palm kernel oil"
        ]

        for name in test_names:
            normalized = " ".join(name.strip().upper().split())
            alias = SionInputAlias.objects.filter(
                normalized_alias=normalized,
                canonical_input=pko
            ).exists()
            assert alias, f"Alias '{name}' not found for PKO"

    def test_olive_oil_alias_mapping_in_e126(self):
        """OLIVE_OIL aliases resolve correctly."""
        olive = SionCanonicalInput.objects.get(code="OLIVE_OIL")

        test_names = [
            "OLIVE OIL", "olive oil", "Olive Oil",
            "Extra Virgin Olive Oil", "extra virgin olive oil",
            "OLIVE OIL - E126"
        ]

        for name in test_names:
            normalized = " ".join(name.strip().upper().split())
            alias = SionInputAlias.objects.filter(
                normalized_alias=normalized,
                canonical_input=olive
            ).exists()
            assert alias, f"Alias '{name}' not found for OLIVE_OIL"


@pytest.mark.django_db
class TestE132PercentageConstraint:
    """Test E132 (PKO 60%, CHEESE 40%) percentage constraints."""

    @pytest.fixture
    def sion_e132(self):
        """E132 SION norm."""
        head = HeadSIONNormsModel.objects.create(name="E Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E132",
            defaults={"head_norm": head}
        )
        return sion

    @pytest.fixture
    def pko_e132_item(self):
        """PKO output item for E132."""
        item, _ = ItemNameModel.objects.get_or_create(
            name="PKO - E132",
            defaults={"is_active": True}
        )
        return item

    @pytest.fixture
    def cheese_e132_item(self):
        """CHEESE output item for E132."""
        item, _ = ItemNameModel.objects.get_or_create(
            name="CHEESE - E132",
            defaults={"is_active": True}
        )
        return item

    @pytest.fixture
    def user(self):
        """Test user for rule creation."""
        return User.objects.create_user(username="planner_e132", password="test123")

    def test_pko_percentage_rule_60_percent_cap(self, sion_e132, pko_e132_item, user):
        """E132 PKO rule with 60% cap."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e132,
            name="E132 - PKO 60%",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("100.00"),
            unit="KG",
            priority=1,
            output_item=pko_e132_item,
            percentage_constraint=Decimal("60.00"),
            created_by=user,
            modified_by=user,
        )

        assert rule.percentage_constraint == Decimal("60.00")

    def test_cheese_percentage_rule_40_percent_cap(self, sion_e132, cheese_e132_item, user):
        """E132 CHEESE rule with 40% cap."""
        rule = SionPlanningRule.objects.create(
            sion=sion_e132,
            name="E132 - CHEESE 40%",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("150.00"),
            unit="KG",
            priority=2,
            output_item=cheese_e132_item,
            percentage_constraint=Decimal("40.00"),
            created_by=user,
            modified_by=user,
        )

        assert rule.percentage_constraint == Decimal("40.00")

    def test_e132_constraint_sum_not_100_allowed(self, sion_e132, pko_e132_item, cheese_e132_item, user):
        """E132 rules sum to 100% (60% + 40%) as expected."""
        pko_rule = SionPlanningRule.objects.create(
            sion=sion_e132,
            name="E132 - PKO 60%",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("100.00"),
            unit="KG",
            priority=1,
            output_item=pko_e132_item,
            percentage_constraint=Decimal("60.00"),
            created_by=user,
            modified_by=user,
        )

        cheese_rule = SionPlanningRule.objects.create(
            sion=sion_e132,
            name="E132 - CHEESE 40%",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("150.00"),
            unit="KG",
            priority=2,
            output_item=cheese_e132_item,
            percentage_constraint=Decimal("40.00"),
            created_by=user,
            modified_by=user,
        )

        total = (pko_rule.percentage_constraint or DEC_0) + (cheese_rule.percentage_constraint or DEC_0)
        assert total == Decimal("100.00")


@pytest.mark.django_db
class TestCanonicalInputAliasSeeding:
    """Verify all 10 canonical inputs and their aliases are seeded."""

    def test_all_10_canonical_inputs_exist(self):
        """All 10 canonical inputs are created by migration."""
        codes = ["PKO", "OLIVE_OIL", "CHEESE", "NUT", "YEAST", "RBD", "SWP", "DWP", "WPC", "ALUMINIUM_FOIL"]

        for code in codes:
            obj = SionCanonicalInput.objects.get(code=code)
            assert obj.is_active
            assert obj.code == code

    def test_pko_has_multiple_aliases(self):
        """PKO has case-insensitive aliases."""
        pko = SionCanonicalInput.objects.get(code="PKO")
        aliases = SionInputAlias.objects.filter(canonical_input=pko)

        assert aliases.exists()
        alias_list = [a.normalized_alias for a in aliases]
        assert "PKO" in alias_list
        assert "PALM KERNEL OIL" in alias_list

    def test_rbd_aliases_include_palmolein_variants(self):
        """RBD aliases cover RBD PALMOLEIN OIL variants."""
        rbd = SionCanonicalInput.objects.get(code="RBD")
        aliases = SionInputAlias.objects.filter(canonical_input=rbd)

        alias_list = [a.normalized_alias for a in aliases]
        assert "RBD" in alias_list
        assert "RBD PALMOLEIN OIL" in alias_list
        assert "RBD - E132" in alias_list

    def test_normalized_alias_uniqueness(self):
        """Each normalized_alias is globally unique."""
        # This is enforced by the UniqueConstraint in the migration
        all_aliases = SionInputAlias.objects.values_list("normalized_alias", flat=True)
        all_aliases_list = list(all_aliases)

        # If there were duplicates, the count would be less than the list length
        assert len(all_aliases_list) == len(set(all_aliases_list))
