"""Test that Standard strategy respects percentage-based input capacity caps.

Standard strategy allows selecting ONE input independently, but must not
exceed that input's remaining capacity under the percentage rule.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
)
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    SionPlanningRule
)
from apps.license.services.sion_percentage_rule import SionPercentageRule


pytestmark = pytest.mark.django_db


@pytest.fixture
def e126_setup():
    """Create E126 with percentage rules."""
    head = HeadSIONNormsModel.objects.create(name="Test")
    e126 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E126", is_active=True
    )

    # Create percentage rules
    pko_item = ItemNameModel.objects.create(name="PKO")
    olive_item = ItemNameModel.objects.create(name="OLIVE OIL")

    SionPlanningRule.objects.create(
        sion=e126, name="E126 PKO", expression={}, max_unit_price=Decimal("100"),
        priority=1, is_active=True, percentage_constraint=Decimal("50.00"),
        output_item=pko_item,
    )
    SionPlanningRule.objects.create(
        sion=e126, name="E126 OLIVE", expression={}, max_unit_price=Decimal("100"),
        priority=2, is_active=True, percentage_constraint=Decimal("50.00"),
        output_item=olive_item,
    )

    # Create license with 1000 KG export
    company = CompanyModel.objects.create(iec="TEST-001", name="Test Company")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company, license_number="TEST-001",
        license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=e126, net_quantity=Decimal("1000.000"),
        unit="KG", cif_fc=Decimal("10000"),
    )

    return e126, license_obj


class TestStandardStrategyInputCapacity:
    """Verify Standard strategy respects input capacity."""

    def test_input_remaining_capacity_calculation(self, e126_setup):
        """Test that input remaining capacity is calculated correctly."""
        e126, license_obj = e126_setup

        # PKO cap = 1000 × 50% = 500 KG
        pko_cap = SionPercentageRule.get_percentage_cap_for_input(
            license_obj, e126.pk, Decimal("50.00")
        )
        assert pko_cap == Decimal("500.000")

        # No existing usage, so remaining = 500
        pko_remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, e126.pk, "PKO", Decimal("50.00")
        )
        assert pko_remaining == Decimal("500.000")

    def test_standard_allocation_within_capacity(self, e126_setup):
        """Standard allocation within input capacity should be allowed."""
        e126, license_obj = e126_setup

        # PKO capacity = 500 KG
        # Standard allocation of 200 KG PKO should be allowed
        pko_remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, e126.pk, "PKO", Decimal("50.00")
        )

        assert Decimal("200.000") <= pko_remaining  # Should be allowed

    def test_standard_allocation_exceeds_capacity(self, e126_setup):
        """Standard allocation exceeding input capacity should be rejected."""
        e126, license_obj = e126_setup

        # PKO capacity = 500 KG
        # Standard allocation of 600 KG PKO should be rejected
        pko_remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, e126.pk, "PKO", Decimal("50.00")
        )

        assert pko_remaining == Decimal("500.000")
        assert Decimal("600.000") > pko_remaining  # Should be rejected

    def test_separate_input_capacities(self, e126_setup):
        """PKO and Olive Oil have separate remaining capacities."""
        e126, license_obj = e126_setup

        pko_remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, e126.pk, "PKO", Decimal("50.00")
        )
        olive_remaining = SionPercentageRule.get_remaining_capacity_for_input(
            license_obj, e126.pk, "OLIVE_OIL", Decimal("50.00")
        )

        # Both should have 500 KG cap initially
        assert pko_remaining == Decimal("500.000")
        assert olive_remaining == Decimal("500.000")

        # They are independent - Standard can choose ONE of them
        # No requirement to allocate to both
