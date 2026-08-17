"""Tests for SPLIT_BY_PERCENTAGE planning strategy.

Tests the complete percentage-based allocation flow from calculation through
execution and persistence.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
)
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    SionCanonicalInput, SionInputAlias, SionPlanningRule
)
from apps.license.services.sion_planning_percentage_allocation import (
    SionPlanningPercentageAllocationService
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def head_and_sions():
    """Create SION norms for testing."""
    head = HeadSIONNormsModel.objects.create(name="Test Norms")
    e126 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E126", is_active=True
    )
    e132 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E132", is_active=True
    )
    return head, {"E126": e126, "E132": e132}


@pytest.fixture
def percentage_rules(head_and_sions):
    """Create percentage-constrained rules."""
    head, sions = head_and_sions
    rules = {}

    # E126 rules: PKO 50%, OLIVE_OIL 50%
    pko_item = ItemNameModel.objects.create(name="PKO")
    olive_item = ItemNameModel.objects.create(name="OLIVE OIL")

    rules['E126_PKO'] = SionPlanningRule.objects.create(
        sion=sions['E126'],
        name="E126 PKO 50%",
        expression={},
        max_unit_price=Decimal("100"),
        priority=1,
        is_active=True,
        percentage_constraint=Decimal("50.00"),
        output_item=pko_item,
    )
    rules['E126_OLIVE'] = SionPlanningRule.objects.create(
        sion=sions['E126'],
        name="E126 OLIVE 50%",
        expression={},
        max_unit_price=Decimal("100"),
        priority=2,
        is_active=True,
        percentage_constraint=Decimal("50.00"),
        output_item=olive_item,
    )

    # E132 rules: PKO 60%, CHEESE 40%
    cheese_item = ItemNameModel.objects.create(name="CHEESE")

    rules['E132_PKO'] = SionPlanningRule.objects.create(
        sion=sions['E132'],
        name="E132 PKO 60%",
        expression={},
        max_unit_price=Decimal("100"),
        priority=1,
        is_active=True,
        percentage_constraint=Decimal("60.00"),
        output_item=pko_item,
    )
    rules['E132_CHEESE'] = SionPlanningRule.objects.create(
        sion=sions['E132'],
        name="E132 CHEESE 40%",
        expression={},
        max_unit_price=Decimal("100"),
        priority=2,
        is_active=True,
        percentage_constraint=Decimal("40.00"),
        output_item=cheese_item,
    )

    return rules


@pytest.fixture
def license_with_export(head_and_sions):
    """Create a license with export items for testing."""
    head, sions = head_and_sions
    company = CompanyModel.objects.create(iec="TEST-001", name="Test Company")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company,
        license_number="TEST-L-001",
        license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )

    # Create export items for E126 with 1000 KG
    LicenseExportItemModel.objects.create(
        license=license_obj,
        norm_class=sions['E126'],
        net_quantity=Decimal("1000.000"),
        unit="KG",
        cif_fc=Decimal("10000"),
    )

    # Create export item for E132 with 1000 KG
    LicenseExportItemModel.objects.create(
        license=license_obj,
        norm_class=sions['E132'],
        net_quantity=Decimal("1000.000"),
        unit="KG",
        cif_fc=Decimal("10000"),
    )

    return license_obj


class TestPercentageAllocationService:
    """Test the core percentage allocation calculation service."""

    def test_allocate_e126_50_50_split(self, license_with_export, percentage_rules, head_and_sions):
        """Test E126 50/50 split for 1000 KG."""
        head, sions = head_and_sions
        result = SionPlanningPercentageAllocationService.allocate_by_percentage(
            license_with_export,
            sions['E126'].pk,
            Decimal("1000.000")
        )

        assert result['status'] == 'SUCCESS'
        assert result['total_quantity'] == Decimal("1000.000")
        assert len(result['allocations']) == 2

        # Find allocations by input code
        allocs = {a['input']: a for a in result['allocations']}

        assert 'PKO' in allocs
        assert allocs['PKO']['percentage'] == Decimal('50.00')
        assert allocs['PKO']['allocated_quantity'] == Decimal('500.000')
        assert allocs['PKO']['status'] == 'OK'

        assert 'OLIVE OIL' in allocs
        assert allocs['OLIVE OIL']['percentage'] == Decimal('50.00')
        assert allocs['OLIVE OIL']['allocated_quantity'] == Decimal('500.000')
        assert allocs['OLIVE OIL']['status'] == 'OK'

    def test_allocate_e132_60_40_split(self, license_with_export, percentage_rules, head_and_sions):
        """Test E132 60/40 split for 1000 KG."""
        head, sions = head_and_sions
        result = SionPlanningPercentageAllocationService.allocate_by_percentage(
            license_with_export,
            sions['E132'].pk,
            Decimal("1000.000")
        )

        assert result['status'] == 'SUCCESS'
        assert result['total_quantity'] == Decimal("1000.000")
        assert len(result['allocations']) == 2

        allocs = {a['input']: a for a in result['allocations']}

        assert 'PKO' in allocs
        assert allocs['PKO']['percentage'] == Decimal('60.00')
        assert allocs['PKO']['allocated_quantity'] == Decimal('600.000')

        assert 'CHEESE' in allocs
        assert allocs['CHEESE']['percentage'] == Decimal('40.00')
        assert allocs['CHEESE']['allocated_quantity'] == Decimal('400.000')

    def test_no_percentage_rules(self, license_with_export, head_and_sions):
        """Test that NO_RULES status is returned when no percentage rules exist."""
        head, sions = head_and_sions
        # Create a SION with no percentage rules
        new_sion = SionNormClassModel.objects.create(
            head_norm=head, norm_class="E999", is_active=True
        )

        result = SionPlanningPercentageAllocationService.allocate_by_percentage(
            license_with_export,
            new_sion.pk,
            Decimal("1000.000")
        )

        assert result['status'] == 'NO_RULES'
        assert len(result['allocations']) == 0

    def test_invalid_percentage_sum(self, license_with_export, head_and_sions):
        """Test that INVALID_CONFIG is returned when percentages don't sum to 100%."""
        head, sions = head_and_sions

        # Create rules that sum to 90%
        pko_item = ItemNameModel.objects.create(name="PKO_INVALID")
        olive_item = ItemNameModel.objects.create(name="OLIVE_INVALID")

        new_sion = SionNormClassModel.objects.create(
            head_norm=head, norm_class="E998", is_active=True
        )

        SionPlanningRule.objects.create(
            sion=new_sion,
            name="PKO 50%",
            expression={},
            max_unit_price=Decimal("100"),
            priority=1,
            is_active=True,
            percentage_constraint=Decimal("50.00"),
            output_item=pko_item,
        )
        SionPlanningRule.objects.create(
            sion=new_sion,
            name="OLIVE 40%",
            expression={},
            max_unit_price=Decimal("100"),
            priority=2,
            is_active=True,
            percentage_constraint=Decimal("40.00"),
            output_item=olive_item,
        )

        result = SionPlanningPercentageAllocationService.allocate_by_percentage(
            license_with_export,
            new_sion.pk,
            Decimal("1000.000")
        )

        assert result['status'] == 'INVALID_CONFIG'
        assert '90' in result['message']

    def test_allocate_maximum_quantity_calculation(self, license_with_export, percentage_rules, head_and_sions):
        """Test that max_quantity is correctly calculated."""
        head, sions = head_and_sions
        result = SionPlanningPercentageAllocationService.allocate_by_percentage(
            license_with_export,
            sions['E126'].pk,
            Decimal("500.000")
        )

        assert result['status'] == 'SUCCESS'
        # Should be able to allocate up to 1000 KG total (1000 exported × 50% = 500 each)
        assert result['max_quantity'] == Decimal('1000.000')

    def test_validate_allocation_request_success(self, license_with_export, percentage_rules, head_and_sions):
        """Test validation helper for successful allocation."""
        head, sions = head_and_sions
        allowed, message = SionPlanningPercentageAllocationService.validate_allocation_request(
            license_with_export,
            sions['E126'].pk,
            Decimal("800.000")
        )

        assert allowed is True
        assert message is None
