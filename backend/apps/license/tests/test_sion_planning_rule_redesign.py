"""Tests for SION Planning Rule Redesign: strategy-based architecture."""
import pytest
from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, SionNormClassModel, ItemNameModel,
)
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    SionPlanningRule, SionPlanningUnitValueRow, SionPlanningPercentageRow,
)
from apps.license.serializers.incentive import SionPlanningRuleSerializer


pytestmark = pytest.mark.django_db


@pytest.fixture
def redesign_setup():
    """Setup for testing new strategy-based architecture."""
    head = HeadSIONNormsModel.objects.create(name="Test Redesign")
    sion_e126 = SionNormClassModel.objects.create(head_norm=head, norm_class="E126", is_active=True)

    # Create import items
    pko_item = ItemNameModel.objects.create(name="PKO", sion_norm_class=sion_e126, is_active=True)
    olive_item = ItemNameModel.objects.create(name="OLIVE_OIL", sion_norm_class=sion_e126, is_active=True)

    company = CompanyModel.objects.create(iec="REDESIGN01", name="Redesign Test")
    user = get_user_model().objects.create_user(username="redesign-user", company=company)
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)

    client = APIClient()
    client.force_authenticate(user)

    return {
        "sion": sion_e126,
        "pko_item": pko_item,
        "olive_item": olive_item,
        "company": company,
        "user": user,
        "client": client,
    }


class TestStrategySerializerValidation:
    """Test strategy-aware serializer validation."""

    def test_standard_strategy_requires_import_item(self, redesign_setup):
        """STANDARD strategy requires import_item."""
        setup = redesign_setup
        payload = {
            "sion": setup["sion"].id,
            "name": "Standard Rule",
            "strategy": "STANDARD",
            "import_item": None,
            "expression": {"operator": "AND", "conditions": []},
            "max_unit_price": "10.00",
            "unit": "KG",
            "is_active": True,
        }
        serializer = SionPlanningRuleSerializer(data=payload)
        assert not serializer.is_valid()
        assert "import_item" in serializer.errors or "strategy" in serializer.errors

    def test_standard_strategy_accepts_valid_item(self, redesign_setup):
        """STANDARD strategy accepts valid import_item."""
        setup = redesign_setup
        payload = {
            "sion": setup["sion"].id,
            "name": "PKO Rule",
            "strategy": "STANDARD",
            "import_item": setup["pko_item"].id,
            "expression": {"operator": "AND", "conditions": []},
            "max_unit_price": "10.00",
            "unit": "KG",
            "is_active": True,
        }
        serializer = SionPlanningRuleSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        rule = serializer.save()
        assert rule.strategy == "STANDARD"
        assert rule.import_item_id == setup["pko_item"].id

    def test_split_by_percent_requires_rows(self, redesign_setup):
        """SPLIT_BY_PERCENT requires ≥1 rows."""
        setup = redesign_setup
        payload = {
            "sion": setup["sion"].id,
            "name": "Split Rule",
            "strategy": "SPLIT_BY_PERCENT",
            "percentage_rows": [],
            "expression": {"operator": "AND", "conditions": []},
            "max_unit_price": "10.00",
            "unit": "KG",
            "is_active": True,
        }
        serializer = SionPlanningRuleSerializer(data=payload)
        assert not serializer.is_valid()
        assert "percentage_rows" in serializer.errors

    def test_split_by_percent_validates_total(self, redesign_setup):
        """SPLIT_BY_PERCENT validates total==100%."""
        setup = redesign_setup
        payload = {
            "sion": setup["sion"].id,
            "name": "Split Rule",
            "strategy": "SPLIT_BY_PERCENT",
            "percentage_rows": [
                {"import_item": setup["pko_item"].id, "percentage": "50", "unit_price": "2.70"},
                {"import_item": setup["olive_item"].id, "percentage": "40", "unit_price": "4.00"},
            ],
            "expression": {"operator": "AND", "conditions": []},
            "max_unit_price": "10.00",
            "unit": "KG",
            "is_active": True,
        }
        serializer = SionPlanningRuleSerializer(data=payload)
        assert not serializer.is_valid()
        assert "percentage_rows" in serializer.errors

    def test_split_by_percent_accepts_valid_total(self, redesign_setup):
        """SPLIT_BY_PERCENT accepts rows totaling 100%."""
        setup = redesign_setup
        payload = {
            "sion": setup["sion"].id,
            "name": "Split 50-50",
            "strategy": "SPLIT_BY_PERCENT",
            "percentage_rows": [
                {"import_item": setup["pko_item"].id, "percentage": "50", "unit_price": "2.70"},
                {"import_item": setup["olive_item"].id, "percentage": "50", "unit_price": "4.00"},
            ],
            "expression": {"operator": "AND", "conditions": []},
            "max_unit_price": "10.00",
            "unit": "KG",
            "is_active": True,
        }
        serializer = SionPlanningRuleSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        rule = serializer.save()
        assert rule.strategy == "SPLIT_BY_PERCENT"
        assert rule.percentage_rows.count() == 2


class TestAutoPlanning:
    """Test Auto Plan with new architecture."""

    def test_split_by_percent_planning(self, redesign_setup):
        """Test SPLIT_BY_PERCENT Auto Plan calculation."""
        setup = redesign_setup

        # Create rule
        rule = SionPlanningRule.objects.create(
            sion=setup["sion"],
            name="Split 50-50",
            strategy="SPLIT_BY_PERCENT",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("10.00"),
            unit="KG",
            is_active=True,
        )
        SionPlanningPercentageRow.objects.create(
            rule=rule, import_item=setup["pko_item"], percentage=Decimal("50"), unit_price=Decimal("2.70")
        )
        SionPlanningPercentageRow.objects.create(
            rule=rule, import_item=setup["olive_item"], percentage=Decimal("50"), unit_price=Decimal("4.00")
        )

        # Create license
        license_obj = LicenseDetailsModel.objects.create(
            exporter=setup["company"],
            license_number="TEST-REDESIGN-1",
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=30),
        )

        # Add export item for E126 with 100,000 CIF
        LicenseExportItemModel.objects.create(license=license_obj, norm_class=setup["sion"], cif_fc=Decimal("100000"))

        # Add import item: 10,000 kg total
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Oil",
            quantity=Decimal("10000"), available_quantity=Decimal("10000"),
        )

        # Run Auto Plan
        response = setup["client"].post(f"/api/licenses/{license_obj.pk}/auto-plan/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "EXECUTED"
        # Should have planned the rule
        assert data["total_lines_written"] > 0
