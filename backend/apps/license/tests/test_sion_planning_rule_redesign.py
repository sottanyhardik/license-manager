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
    LicenseItemPlan, LicenseReplanRequest, SionPlanningRule, SionPlanningUnitValueRow, SionPlanningPercentageRow,
)
from apps.license.serializers.incentive import SionPlanningRuleSerializer
from apps.license.services.sion_rule_engine import SionRulePlanningService


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


class TestPercentageRuleVersionedUpdate:
    def _rule(self, setup):
        rule = SionPlanningRule.objects.create(
            sion=setup["sion"], name="PKO & OIL", version=2, priority=1,
            strategy="SPLIT_BY_PERCENT", expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("10.00"), unit="kg", is_active=True,
        )
        SionPlanningPercentageRow.objects.create(
            rule=rule, import_item=setup["pko_item"], percentage=Decimal("50.00"),
            unit_price=Decimal("1.80"), priority=0,
        )
        SionPlanningPercentageRow.objects.create(
            rule=rule, import_item=setup["olive_item"], percentage=Decimal("50.00"),
            unit_price=Decimal("5.00"), priority=1,
        )
        return rule

    def _payload(self, setup, pko="40.00", olive="60.00"):
        return {
            "sion": setup["sion"].pk, "name": "PKO & OIL",
            "strategy": "SPLIT_BY_PERCENT",
            "expression": {"operator": "AND", "conditions": []},
            "max_unit_price": "10.00", "unit": "kg", "is_active": True,
            "percentage_rows": [
                {"import_item": setup["pko_item"].pk, "percentage": pko,
                 "unit_price": "1.80", "priority": 0},
                {"import_item": setup["olive_item"].pk, "percentage": olive,
                 "unit_price": "5.00", "priority": 1},
            ],
        }

    def test_patch_creates_active_version_with_edited_decimal_rows(self, redesign_setup):
        current = self._rule(redesign_setup)
        response = redesign_setup["client"].patch(
            f"/api/sion-planning-rules/{current.pk}/",
            self._payload(redesign_setup), format="json",
        )
        assert response.status_code == 200, response.data
        created = SionPlanningRule.objects.get(pk=response.data["id"])
        current.refresh_from_db()
        assert current.is_active is False
        assert created.is_active is True
        assert created.version == 3
        assert list(created.percentage_rows.order_by("priority").values_list("percentage", "unit_price")) == [
            (Decimal("40.00"), Decimal("1.80")),
            (Decimal("60.00"), Decimal("5.00")),
        ]

        changed_back = redesign_setup["client"].patch(
            f"/api/sion-planning-rules/{created.pk}/",
            self._payload(redesign_setup, "50.00", "50.00"), format="json",
        )
        assert changed_back.status_code == 200, changed_back.data
        newest = SionPlanningRule.objects.get(pk=changed_back.data["id"])
        assert newest.version == 4
        assert list(newest.percentage_rows.order_by("priority").values_list("percentage", flat=True)) == [
            Decimal("50.00"), Decimal("50.00"),
        ]

    @pytest.mark.parametrize("rows", [
        (("40.00", "50.00", "pko", "olive")),
        (("50.00", "50.00", "pko", "pko")),
    ])
    def test_patch_rejects_invalid_total_and_duplicate_items(self, redesign_setup, rows):
        current = self._rule(redesign_setup)
        pko_pct, olive_pct, first_name, second_name = rows
        payload = self._payload(redesign_setup, pko_pct, olive_pct)
        payload["percentage_rows"][0]["import_item"] = redesign_setup[f"{first_name}_item"].pk
        payload["percentage_rows"][1]["import_item"] = redesign_setup[f"{second_name}_item"].pk
        response = redesign_setup["client"].patch(
            f"/api/sion-planning-rules/{current.pk}/", payload, format="json",
        )
        assert response.status_code == 400
        current.refresh_from_db()
        assert current.is_active is True
        assert SionPlanningRule.objects.filter(stable_key=current.stable_key).count() == 1


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

        assert response.status_code == 202, response.data
        request = LicenseReplanRequest.objects.get(pk=response.data["replan_request_id"])
        assert request.license_id == license_obj.pk
        # The request path must not calculate or replace plans inline.
        assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0

        # Calculation persistence remains covered separately from HTTP.  This
        # is the same canonical execution invoked by the worker.
        result = SionRulePlanningService.plan_sion(
            setup["sion"].pk, [license_obj.pk], company_id=setup["company"].pk,
            mode="ALL", force_plan=True,
        )
        assert result["write_results"]
        assert LicenseItemPlan.objects.filter(license=license_obj).count() == 2
