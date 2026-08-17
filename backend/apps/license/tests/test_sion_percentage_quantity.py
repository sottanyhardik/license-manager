"""SION percentage-based allocation tests using QUANTITY (not CIF/value).

This feature enforces percentage-based caps on allocation quantities.

Example (E126):
  Total Eligible Quantity = 1,000 KG
  PKO cap = 1,000 KG × 50% = 500 KG
  OLIVE_OIL cap = 1,000 KG × 50% = 500 KG
"""
import pytest
from decimal import Decimal

from apps.core.constants import DEC_0
from apps.core.models import SionNormClassModel, HeadSIONNormsModel
from apps.license.models import (
    SionCanonicalInput, SionInputAlias,
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
)
from apps.license.services.sion_input_classifier import SionInputClassifier
from apps.license.services.sion_percentage_rule import SionPercentageRule
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestSionInputNormalization:
    """Test product name normalization and alias matching."""

    def test_normalize_pko_variants(self):
        """PKO variations normalize correctly."""
        classifier = SionInputClassifier()

        assert classifier.normalize_product_name("PKO") == "PKO"
        assert classifier.normalize_product_name("pko") == "PKO"
        assert classifier.normalize_product_name("PALM KERNEL OIL") == "PALM KERNEL OIL"

    def test_resolve_pko_exact_match(self):
        """PKO canonical input is resolved from exact alias."""
        pko = SionCanonicalInput.objects.get(code="PKO")
        assert pko is not None
        assert pko.display_name == "Palm Kernel Oil"

        # Verify alias exists
        alias = SionInputAlias.objects.filter(
            canonical_input=pko,
            normalized_alias="PALM KERNEL OIL"
        ).exists()
        assert alias

    def test_resolve_olive_oil(self):
        """OLIVE_OIL canonical input resolves."""
        olive = SionCanonicalInput.objects.get(code="OLIVE_OIL")
        assert olive is not None

    def test_resolve_cheese(self):
        """CHEESE canonical input resolves."""
        cheese = SionCanonicalInput.objects.get(code="CHEESE")
        assert cheese is not None

    def test_unmapped_product_returns_none(self):
        """Unknown products return None."""
        classifier = SionInputClassifier()
        result = classifier.resolve_canonical_input("UNKNOWN PRODUCT XYZ")
        assert result is None


@pytest.mark.django_db
class TestE126PercentageRule:
    """Test E126 (PKO 50%, OLIVE_OIL 50%) percentage allocation in QUANTITY."""

    @pytest.fixture
    def sion_e126(self):
        """Create E126 SION norm."""
        head = HeadSIONNormsModel.objects.create(name="E Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E126",
            defaults={"head_norm": head}
        )
        return sion

    @pytest.fixture
    def license_e126(self, sion_e126):
        """Create license with E126 export."""
        license_obj = LicenseDetailsModel.objects.create(
            license_number="E126LIC001"
        )

        # Create export items for E126
        LicenseExportItemModel.objects.create(
            license=license_obj,
            norm_class=sion_e126,
            net_quantity=Decimal("1000.000"),  # 1000 KG total
            unit="KG"
        )

        return license_obj

    def test_total_eligible_quantity_e126(self, license_e126, sion_e126):
        """Total eligible quantity for E126 is sum of net_quantity."""
        total = SionPercentageRule.calculate_total_eligible_quantity(
            license_e126, sion_e126.pk
        )
        assert total == Decimal("1000.000")

    def test_pko_cap_50_percent(self, license_e126, sion_e126):
        """PKO cap is 50% of total = 500 KG."""
        cap = SionPercentageRule.get_percentage_cap_for_input(
            license_e126,
            sion_e126.pk,
            Decimal("50.00")
        )
        assert cap == Decimal("500.000")

    def test_olive_oil_cap_50_percent(self, license_e126, sion_e126):
        """OLIVE_OIL cap is 50% of total = 500 KG."""
        cap = SionPercentageRule.get_percentage_cap_for_input(
            license_e126,
            sion_e126.pk,
            Decimal("50.00")
        )
        assert cap == Decimal("500.000")

    def test_remaining_capacity_initial(self, license_e126, sion_e126):
        """Initial remaining capacity equals cap (nothing allotted/debited yet)."""
        remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_e126,
            sion_e126.pk,
            "PKO",
            Decimal("50.00")
        )
        assert remaining == Decimal("500.000")


@pytest.mark.django_db
class TestE132PercentageRule:
    """Test E132 (PKO 60%, CHEESE 40%) percentage allocation in QUANTITY."""

    @pytest.fixture
    def sion_e132(self):
        """Create E132 SION norm."""
        head = HeadSIONNormsModel.objects.create(name="E Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E132",
            defaults={"head_norm": head}
        )
        return sion

    @pytest.fixture
    def license_e132(self, sion_e132):
        """Create license with E132 export."""
        license_obj = LicenseDetailsModel.objects.create(
            license_number="E132LIC001"
        )

        # Create export items for E132
        LicenseExportItemModel.objects.create(
            license=license_obj,
            norm_class=sion_e132,
            net_quantity=Decimal("1000.000"),  # 1000 KG total
            unit="KG"
        )

        return license_obj

    def test_total_eligible_quantity_e132(self, license_e132, sion_e132):
        """Total eligible quantity for E132 is 1000 KG."""
        total = SionPercentageRule.calculate_total_eligible_quantity(
            license_e132, sion_e132.pk
        )
        assert total == Decimal("1000.000")

    def test_pko_cap_60_percent(self, license_e132, sion_e132):
        """PKO cap is 60% of total = 600 KG."""
        cap = SionPercentageRule.get_percentage_cap_for_input(
            license_e132,
            sion_e132.pk,
            Decimal("60.00")
        )
        assert cap == Decimal("600.000")

    def test_cheese_cap_40_percent(self, license_e132, sion_e132):
        """CHEESE cap is 40% of total = 400 KG."""
        cap = SionPercentageRule.get_percentage_cap_for_input(
            license_e132,
            sion_e132.pk,
            Decimal("40.00")
        )
        assert cap == Decimal("400.000")

    def test_caps_sum_to_100(self, license_e132, sion_e132):
        """E132 caps sum to 100% (600 + 400 = 1000)."""
        pko_cap = SionPercentageRule.get_percentage_cap_for_input(
            license_e132, sion_e132.pk, Decimal("60.00")
        )
        cheese_cap = SionPercentageRule.get_percentage_cap_for_input(
            license_e132, sion_e132.pk, Decimal("40.00")
        )

        assert (pko_cap + cheese_cap) == Decimal("1000.000")


@pytest.mark.django_db
class TestPercentageConstraintValidation:
    """Test validation of allocation requests against percentage constraints."""

    @pytest.fixture
    def sion_e126(self):
        """Create E126."""
        head = HeadSIONNormsModel.objects.create(name="E Norms")
        sion, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E126",
            defaults={"head_norm": head}
        )
        return sion

    @pytest.fixture
    def license_e126(self, sion_e126):
        """Create license with 1000 KG E126 export."""
        license_obj = LicenseDetailsModel.objects.create(
            license_number="E126LIC002"
        )

        LicenseExportItemModel.objects.create(
            license=license_obj,
            norm_class=sion_e126,
            net_quantity=Decimal("1000.000"),
            unit="KG"
        )

        return license_obj

    def test_allowed_allocation_within_cap(self, license_e126, sion_e126):
        """Allocation within cap is allowed."""
        allowed, msg = SionPercentageRule.check_percentage_capacity(
            license_e126,
            sion_e126.pk,
            "PKO",
            Decimal("50.00"),
            Decimal("300.000")  # 300 KG < 500 KG cap
        )
        assert allowed
        assert msg == ""

    def test_rejected_allocation_exceeds_cap(self, license_e126, sion_e126):
        """Allocation exceeding cap is rejected."""
        allowed, msg = SionPercentageRule.check_percentage_capacity(
            license_e126,
            sion_e126.pk,
            "PKO",
            Decimal("50.00"),
            Decimal("600.000")  # 600 KG > 500 KG cap
        )
        assert not allowed
        assert "exceeded" in msg.lower()

    def test_no_constraint_allows_any(self, license_e126, sion_e126):
        """Without percentage constraint, any amount is allowed."""
        allowed, msg = SionPercentageRule.check_percentage_capacity(
            license_e126,
            sion_e126.pk,
            "PKO",
            None,  # No constraint
            Decimal("10000.000")
        )
        assert allowed
        assert msg == ""


@pytest.mark.django_db
class TestCanonicalInputSeeding:
    """Verify minimal seed data for E126/E132."""

    def test_three_canonical_inputs_created(self):
        """Only the 3 required canonical inputs are seeded."""
        inputs = SionCanonicalInput.objects.filter(is_active=True)
        codes = {inp.code for inp in inputs}

        # Must have at least PKO, OLIVE_OIL, CHEESE
        assert "PKO" in codes
        assert "OLIVE_OIL" in codes
        assert "CHEESE" in codes

    def test_pko_aliases(self):
        """PKO has verified aliases."""
        pko = SionCanonicalInput.objects.get(code="PKO")
        aliases = SionInputAlias.objects.filter(canonical_input=pko)

        assert aliases.exists()
        normalized_aliases = {a.normalized_alias for a in aliases}

        # Must have at least these verified aliases
        assert "PKO" in normalized_aliases
        assert "PALM KERNEL OIL" in normalized_aliases

    def test_olive_oil_aliases(self):
        """OLIVE_OIL has verified aliases."""
        olive = SionCanonicalInput.objects.get(code="OLIVE_OIL")
        aliases = SionInputAlias.objects.filter(canonical_input=olive)

        assert aliases.exists()
        normalized_aliases = {a.normalized_alias for a in aliases}
        assert "OLIVE OIL" in normalized_aliases

    def test_cheese_aliases(self):
        """CHEESE has verified aliases."""
        cheese = SionCanonicalInput.objects.get(code="CHEESE")
        aliases = SionInputAlias.objects.filter(canonical_input=cheese)

        assert aliases.exists()
        normalized_aliases = {a.normalized_alias for a in aliases}
        assert "CHEESE" in normalized_aliases

    def test_normalized_alias_uniqueness(self):
        """Each normalized_alias is globally unique (enforced by DB constraint)."""
        all_aliases = SionInputAlias.objects.values_list("normalized_alias", flat=True)
        all_aliases_list = list(all_aliases)

        # If duplicates existed, count would be less than list length
        assert len(set(all_aliases_list)) == len(all_aliases_list)
