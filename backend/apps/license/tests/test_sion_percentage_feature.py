"""Comprehensive tests for SION percentage allocation feature.

Tests E126/E132 percentage cap calculations and SPLIT_BY_PERCENTAGE strategy.
"""
import pytest
from decimal import Decimal

from apps.core.models import SionNormClassModel, ItemNameModel, HeadSIONNormsModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, SionPlanningRule, LicenseItemPlan,
)
from apps.allotment.models import AllotmentModel, AllotmentItems
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.license.services.sion_product_classifier import (
    SionProductClassifier, CanonicalInput,
)
from apps.license.services.sion_percentage_capacity import SionPercentageCapacity


@pytest.fixture
def sion_e126(db):
    """Create E126 SION norm."""
    head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="E Norms")
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E126",
        defaults={"head_norm": head_norm, "description": "Imported Vegetable Oils"}
    )
    return sion


@pytest.fixture
def sion_e132(db):
    """Create E132 SION norm."""
    head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="E Norms")
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E132",
        defaults={"head_norm": head_norm, "description": "Imported Fats & Cheese"}
    )
    return sion


@pytest.fixture
def license_e126(db, sion_e126):
    """Create a license with E126 export item."""
    license_obj = LicenseDetailsModel.objects.create(
        license_number="TEST-E126-001",
    )
    # 1000 KG total eligible quantity for E126
    LicenseExportItemModel.objects.create(
        license=license_obj,
        norm_class=sion_e126,
        net_quantity=Decimal("1000.00"),
        unit="KG",
    )
    return license_obj


@pytest.fixture
def license_e132(db, sion_e132):
    """Create a license with E132 export item."""
    license_obj = LicenseDetailsModel.objects.create(
        license_number="TEST-E132-001",
    )
    # 1000 KG total eligible quantity for E132
    LicenseExportItemModel.objects.create(
        license=license_obj,
        norm_class=sion_e132,
        net_quantity=Decimal("1000.00"),
        unit="KG",
    )
    return license_obj


class TestProductClassification:
    """Test product name normalization and classification."""

    def test_normalize_pko_variants(self):
        """PKO aliases normalize correctly."""
        assert SionProductClassifier.normalize_product_name("PKO") == "PKO"
        assert SionProductClassifier.normalize_product_name("pko") == "PKO"
        assert SionProductClassifier.normalize_product_name("  pko  ") == "PKO"
        assert SionProductClassifier.normalize_product_name("PALM KERNEL OIL") == "PALM KERNEL OIL"
        assert SionProductClassifier.normalize_product_name("  palm   kernel   oil  ") == "PALM KERNEL OIL"

    def test_resolve_pko(self):
        """PKO aliases resolve to PKO canonical input."""
        assert SionProductClassifier.resolve_canonical_input("PKO") == CanonicalInput.PKO
        assert SionProductClassifier.resolve_canonical_input("pko") == CanonicalInput.PKO
        assert SionProductClassifier.resolve_canonical_input("PALM KERNEL OIL") == CanonicalInput.PKO
        assert SionProductClassifier.resolve_canonical_input("Palm Kernel Oil") == CanonicalInput.PKO

    def test_resolve_olive_oil(self):
        """Olive Oil aliases resolve correctly."""
        assert SionProductClassifier.resolve_canonical_input("OLIVE OIL") == CanonicalInput.OLIVE_OIL
        assert SionProductClassifier.resolve_canonical_input("olive oil") == CanonicalInput.OLIVE_OIL

    def test_resolve_cheese(self):
        """Cheese aliases resolve correctly."""
        assert SionProductClassifier.resolve_canonical_input("CHEESE") == CanonicalInput.CHEESE
        assert SionProductClassifier.resolve_canonical_input("cheese") == CanonicalInput.CHEESE

    def test_unknown_product_unmapped(self):
        """Unknown products resolve to UNMAPPED."""
        assert SionProductClassifier.resolve_canonical_input("PALM OIL") == CanonicalInput.UNMAPPED
        assert SionProductClassifier.resolve_canonical_input("UNKNOWN") == CanonicalInput.UNMAPPED
        assert SionProductClassifier.resolve_canonical_input("") == CanonicalInput.UNMAPPED
        assert SionProductClassifier.resolve_canonical_input(None) == CanonicalInput.UNMAPPED

    def test_is_mapped(self):
        """is_mapped correctly identifies mapped vs unmapped names."""
        assert SionProductClassifier.is_mapped("PKO") is True
        assert SionProductClassifier.is_mapped("PALM KERNEL OIL") is True
        assert SionProductClassifier.is_mapped("UNKNOWN") is False
        assert SionProductClassifier.is_mapped("") is False


class TestE126PercentageCaps:
    """Test E126 percentage cap calculations (50/50)."""

    def test_total_eligible_quantity_e126(self, license_e126, sion_e126):
        """Total eligible quantity is sum of export items."""
        total = SionPercentageCapacity.get_total_eligible_quantity(license_e126, sion_e126.pk)
        assert total == Decimal("1000.00")

    def test_pko_cap_50_percent(self, license_e126, sion_e126):
        """PKO cap is 50% of total."""
        cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e126, sion_e126.pk, Decimal("50.00")
        )
        assert cap == Decimal("500.00")

    def test_olive_oil_cap_50_percent(self, license_e126, sion_e126):
        """Olive Oil cap is 50% of total."""
        cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e126, sion_e126.pk, Decimal("50.00")
        )
        assert cap == Decimal("500.00")

    def test_caps_sum_to_100_e126(self, license_e126, sion_e126):
        """E126 PKO + Olive Oil caps sum to total eligible."""
        pko_cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e126, sion_e126.pk, Decimal("50.00")
        )
        olive_cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e126, sion_e126.pk, Decimal("50.00")
        )
        total = SionPercentageCapacity.get_total_eligible_quantity(license_e126, sion_e126.pk)
        assert pko_cap + olive_cap == total


class TestE132PercentageCaps:
    """Test E132 percentage cap calculations (60/40)."""

    def test_total_eligible_quantity_e132(self, license_e132, sion_e132):
        """Total eligible quantity is sum of export items."""
        total = SionPercentageCapacity.get_total_eligible_quantity(license_e132, sion_e132.pk)
        assert total == Decimal("1000.00")

    def test_pko_cap_60_percent(self, license_e132, sion_e132):
        """PKO cap is 60% of total."""
        cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e132, sion_e132.pk, Decimal("60.00")
        )
        assert cap == Decimal("600.00")

    def test_cheese_cap_40_percent(self, license_e132, sion_e132):
        """Cheese cap is 40% of total."""
        cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e132, sion_e132.pk, Decimal("40.00")
        )
        assert cap == Decimal("400.00")

    def test_caps_sum_to_100_e132(self, license_e132, sion_e132):
        """E132 PKO + Cheese caps sum to total eligible."""
        pko_cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e132, sion_e132.pk, Decimal("60.00")
        )
        cheese_cap = SionPercentageCapacity.get_percentage_cap_for_input(
            license_e132, sion_e132.pk, Decimal("40.00")
        )
        total = SionPercentageCapacity.get_total_eligible_quantity(license_e132, sion_e132.pk)
        assert pko_cap + cheese_cap == total


class TestCapacityValidation:
    """Test capacity validation (Standard strategy)."""

    def test_allowed_within_cap(self, license_e126, sion_e126):
        """Request within remaining capacity is allowed."""
        # With no existing usage, request of 100 < cap of 500 should be allowed
        allowed, msg = SionPercentageCapacity.can_allocate_to_input(
            license_e126, sion_e126.pk,
            CanonicalInput.PKO, Decimal("50.00"),
            Decimal("100.00")
        )
        assert allowed is True
        assert msg is None

    def test_rejected_exceeds_cap(self, license_e126, sion_e126):
        """Request exceeding cap is rejected."""
        # Request of 600 > cap of 500 should be rejected
        allowed, msg = SionPercentageCapacity.can_allocate_to_input(
            license_e126, sion_e126.pk,
            CanonicalInput.PKO, Decimal("50.00"),
            Decimal("600.00")
        )
        assert allowed is False
        assert msg is not None
        assert "exceeds" in msg.lower()

    def test_unmapped_input_allowed(self, license_e126, sion_e126):
        """Unmapped inputs have no cap (always allowed)."""
        # Unmapped inputs should always be allowed since they have no cap
        allowed, msg = SionPercentageCapacity.can_allocate_to_input(
            license_e126, sion_e126.pk,
            CanonicalInput.UNMAPPED, Decimal("50.00"),
            Decimal("1000000.00")
        )
        assert allowed is True


class TestRemainingCapacityCalculation:
    """Test remaining capacity calculation formula."""

    def test_remaining_initial_no_usage(self, license_e126, sion_e126):
        """With no usage, remaining capacity equals the cap."""
        remaining = SionPercentageCapacity.get_remaining_capacity_for_input(
            license_e126, sion_e126.pk,
            CanonicalInput.PKO, Decimal("50.00")
        )
        assert remaining == Decimal("500.00")
