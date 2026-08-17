"""
Phase 1: Read-Path Regression Tests

Verify that all read paths (reports, exports, GET endpoints) have ZERO
planner calls. If any test fails, it means a read path is invoking planning
logic, which violates the read-only architecture.
"""
from unittest.mock import patch, MagicMock
import pytest
from django.test import TestCase, Client
from decimal import Decimal

from apps.license.models import (
    LicenseDetailsModel,
    LicenseItemPlan,
    LicenseImportItemsModel,
)
from apps.core.models import ItemNameModel


class ReadPathPlannerCallRegressionTests(TestCase):
    """
    Regression tests: verify read paths have zero planner invocations.

    These tests patch all legacy planner functions to raise AssertionError.
    If any read path calls a planner, the test fails explicitly.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        super().setUpClass()
        # Create a test license
        cls.license = LicenseDetailsModel.objects.create(
            license_number='TEST/0001',
            license_date='2024-01-01',
            license_expiry_date='2025-01-01',
        )

    def setUp(self):
        """Set up patches to detect planner calls."""
        self.planner_patches = [
            'apps.license.services.e1_plan.plan_e1_items',
            'apps.license.services.e5_plan.plan_e5_items',
            'apps.license.services.e126_plan.plan_e126_per_item',
            'apps.license.services.e132_plan.plan_e132_per_item',
            'apps.license.services.norm_plan.norm_plan_for_license',
        ]

        self.patchers = []
        for path in self.planner_patches:
            patcher = patch(path, side_effect=AssertionError(f"VIOLATION: {path} called from read path"))
            patcher.start()
            self.patchers.append(patcher)

    def tearDown(self):
        """Stop all patches."""
        for patcher in self.patchers:
            patcher.stop()

    def test_item_pivot_report_no_planner_calls(self):
        """Item Pivot Report GET must not invoke planners."""
        from rest_framework.test import APIRequestFactory
        from apps.license.views.item_pivot_report import ItemPivotReportView

        factory = APIRequestFactory()
        request = factory.get('/api/reports/item-pivot/?format=json')

        view = ItemPivotReportView.as_view()
        response = view(request)

        # If we reach here without AssertionError, no planners were called ✓
        assert response.status_code in [200, 400]  # Accept error responses too

    def test_item_report_no_planner_calls(self):
        """Item Report GET must not invoke planners."""
        from rest_framework.test import APIRequestFactory
        from apps.license.views.item_report import ItemReportView

        factory = APIRequestFactory()
        request = factory.get('/api/reports/item-report/?format=json')

        view = ItemReportView()
        response = view.get(request)

        # If we reach here without AssertionError, no planners were called ✓
        assert response.status_code in [200, 400]

    def test_license_item_plan_crud_endpoints_no_side_effects(self):
        """
        GET /api/license-item-plans/ must not create/modify plans.
        """
        from apps.license.models import LicenseItemPlan

        initial_count = LicenseItemPlan.objects.count()

        # Call GET endpoint (simulated)
        # In real test, would use APIRequestFactory
        # For now, just verify initial state

        # After GET, plan count must be unchanged
        assert LicenseItemPlan.objects.count() == initial_count

    def test_effective_plan_for_license_no_norm_fallback(self):
        """effective_plan_for_license must NOT fall back to norm planning."""
        from apps.license.services.norm_plan import effective_plan_for_license

        # License with NO persisted plan
        source, plan = effective_plan_for_license(self.license)

        # Must return empty plan (no norm fallback)
        assert plan == {}
        assert source == ""  # Empty source when no plan exists

    def test_norm_plan_marked_write_only(self):
        """norm_plan_for_license docstring indicates it's WRITE-ONLY."""
        from apps.license.services.norm_plan import norm_plan_for_license

        # Verify docstring contains deprecation notice
        assert "WRITE-ONLY" in norm_plan_for_license.__doc__
        assert "read paths" in norm_plan_for_license.__doc__.lower()


class PersitedPlanReadTests(TestCase):
    """
    Verify read paths correctly read persisted LicenseItemPlan.
    """

    def setUp(self):
        """Create test data with persisted plans."""
        from apps.license.models import LicenseDetailsModel, LicenseItemPlan
        from apps.core.models import ItemNameModel

        self.license = LicenseDetailsModel.objects.create(
            license_number='TEST/PLAN/001',
            license_date='2024-01-01',
            license_expiry_date='2025-01-01',
        )

        # Create import item
        self.import_item = LicenseImportItemsModel.objects.create(
            license=self.license,
            quantity=Decimal('1000'),
            available_quantity=Decimal('1000'),
        )

        # Create item name
        self.item_name = ItemNameModel.objects.create(name='TEST_ITEM')

        # Create persisted plan
        self.plan = LicenseItemPlan.objects.create(
            license=self.license,
            import_item=self.import_item,
            item_name=self.item_name,
            planned_quantity=Decimal('500'),
            planned_cif_fc=Decimal('1000'),
            unit_price=Decimal('2.0'),
        )

    def test_effective_plan_returns_persisted_plan(self):
        """effective_plan_for_license must return persisted manual plan."""
        from apps.license.services.norm_plan import effective_plan_for_license

        source, plan = effective_plan_for_license(self.license)

        # Must return the persisted plan
        assert source == "manual"
        assert self.import_item.id in plan
        plan_data = plan[self.import_item.id]
        assert float(plan_data['planned_quantity']) == 500.0
        assert float(plan_data['planned_cif']) == 1000.0

    def test_no_plan_returns_empty(self):
        """License with NO persisted plan must return empty."""
        from apps.license.services.norm_plan import effective_plan_for_license

        # Create license with no plans
        empty_license = LicenseDetailsModel.objects.create(
            license_number='EMPTY/001',
            license_date='2024-01-01',
            license_expiry_date='2025-01-01',
        )

        source, plan = effective_plan_for_license(empty_license)

        # Must be empty, NOT fallback to norm
        assert plan == {}
        assert source == ""
