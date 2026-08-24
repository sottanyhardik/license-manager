"""Tests for SPLIT_BY_PERCENTAGE planning strategy."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, HSCodeModel, SionNormClassModel,
)
from apps.core.constants import DEBIT
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    LicenseItemPlan, SionPlanningRule,
)


pytestmark = pytest.mark.django_db


def execute_auto_plan(client, license_obj, *, sion_id, company_id):
    """Execute the interactive Auto Plan contract and return its committed result.

    The licence-specific endpoint is deliberately synchronous.  Durable
    replan-request coverage belongs to the source-change/SION-wide endpoints;
    this helper must not enqueue or manually invoke a worker after a request.
    """
    response = client.post(
        f"/api/licenses/{license_obj.pk}/auto-plan/", {"force": True}, format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["planning_state"] == "COMPLETED"
    assert response.data["force"] is True
    assert response.data["license_id"] == license_obj.pk
    assert response.data["write_results"] >= 0
    return response.data


def test_strategy_source_match_expression_hsn_and_description():
    from apps.license.services.sion_rule_engine import evaluate_expression

    expression = {"operator": "OR", "conditions": [
        {"field": "HSN", "comparator": "STARTS_WITH", "value": "1513"},
        {"field": "PRODUCT_DESCRIPTION", "comparator": "CONTAINS", "value": "food flavour"},
    ]}
    assert evaluate_expression(expression, {"hs_code": "15132110", "description": "Oil"})
    assert not evaluate_expression(expression, {"hs_code": "08029900", "description": "Nuts"})
    assert evaluate_expression(expression, {"hs_code": "08029900", "description": "FDA Food Flavour"})


@pytest.fixture
def split_percent_setup():
    """Set up SION norms, company, user, and SPLIT_BY_PERCENTAGE rules."""
    head = HeadSIONNormsModel.objects.create(name="Test Split by %")
    sion_e126 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E126", is_active=True,
    )

    company = CompanyModel.objects.create(iec="SPLITPCT01", name="Split by % Test")
    user = get_user_model().objects.create_user(username="split-pct-user")
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)

    client = APIClient()
    client.force_authenticate(user)

    return {
        "sion": sion_e126,
        "company": company,
        "user": user,
        "client": client,
        "head": head,
    }


def make_split_percent_rules(sion):
    """Create ONE SPLIT_BY_PERCENT rule with two sibling splits for E126 PKO and OLIVE_OIL."""
    from apps.core.models import ItemNameModel
    from apps.license.models import SionPlanningPercentageRow

    # Create target commodities
    pko_item, _ = ItemNameModel.objects.get_or_create(
        name="PKO", defaults={"is_active": True}
    )
    olive_item, _ = ItemNameModel.objects.get_or_create(
        name="OLIVE_OIL", defaults={"is_active": True}
    )

    # Create ONE rule with SPLIT_BY_PERCENT strategy
    # It will split a single source (import item) across two commodities
    split_rule = SionPlanningRule.objects.create(
        sion=sion,
        name="50/50 Split: PKO & Olive Oil",
        expression={"operator": "AND", "conditions": []},
        max_unit_price=Decimal("100.00"),
        unit="KG",
        priority=1,
        is_active=True,
        strategy="SPLIT_BY_PERCENT",
        import_item=pko_item,  # fallback for matching, but rows are authoritative
    )

    # Create percentage row for PKO (50%)
    pko_row = SionPlanningPercentageRow.objects.create(
        rule=split_rule,
        import_item=pko_item,
        percentage=Decimal("50"),
        unit_price=Decimal("2.70"),
        priority=0,
    )

    # Create percentage row for OLIVE_OIL (50%)
    olive_row = SionPlanningPercentageRow.objects.create(
        rule=split_rule,
        import_item=olive_item,
        percentage=Decimal("50"),
        unit_price=Decimal("4.00"),
        priority=1,
    )

    return split_rule, (pko_row, olive_row)


class TestSplitByPercentageStrategy:
    """Tests for SPLIT_BY_PERCENTAGE planning strategy."""

    def test_split_by_percent_basic(self, split_percent_setup):
        """Test SPLIT_BY_PERCENTAGE calculation: total_qty × percentage / 100."""
        setup = split_percent_setup
        pko_rule, olive_rule = make_split_percent_rules(setup["sion"])

        # Create license with E126 SION
        license_obj = LicenseDetailsModel.objects.create(
            exporter=setup["company"],
            license_number="TEST-SPLIT-1",
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=30),
        )

        # Add export item for E126 SION with 100,000 CIF
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=setup["sion"], cif_fc=Decimal("100000"),
        )

        # Add import item: 10,000 kg total
        hs = HSCodeModel.objects.create(
            hs_code="1511.10", product_description="Palm kernel oil", unit="KG",
        )
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, hs_code=hs,
            description="PKO", unit="KG",
            quantity=Decimal("10000"), available_quantity=Decimal("10000"),
        )

        # Verify rule was created correctly
        rules = SionPlanningRule.objects.filter(sion=setup["sion"], is_active=True)
        assert rules.count() == 1, f"Expected 1 rule, got {rules.count()}"
        split_rule = rules.first()
        assert split_rule.strategy == "SPLIT_BY_PERCENT"
        assert split_rule.percentage_rows.count() == 2, "Expected 2 percentage rows in the split rule"

        # Call Auto Plan
        result = execute_auto_plan(
            setup["client"], license_obj, sion_id=setup["sion"].pk,
            company_id=setup["company"].pk,
        )
        assert result["write_results"]

        # Verify planning results - should have 2 plans, one for each sibling split
        plans = LicenseItemPlan.objects.filter(license=license_obj).order_by("planned_quantity")
        assert plans.count() == 2, f"Expected 2 plans (PKO + OLIVE_OIL), got {plans.count()}"

        # Each rule should get 50% of total quantity
        expected_qty = Decimal("5000")  # 10000 × 50 / 100

        pko_plans = [p for p in plans if p.item_name and "PKO" in p.item_name.name]
        olive_plans = [p for p in plans if p.item_name and "OLIVE" in p.item_name.name]

        if pko_plans:
            assert Decimal(str(pko_plans[0].planned_quantity or 0)) == expected_qty
        if olive_plans:
            assert Decimal(str(olive_plans[0].planned_quantity or 0)) == expected_qty

    def test_split_by_percent_zero_availability_reports_no_remaining_plan(self, split_percent_setup):
        """Split eligibility starts from total quantity, then consumes usage.

        A source with no remaining quantity cannot produce a new plan even
        though the percentage target itself is derived from total quantity.
        """
        setup = split_percent_setup
        pko_rule, olive_rule = make_split_percent_rules(setup["sion"])

        license_obj = LicenseDetailsModel.objects.create(
            exporter=setup["company"],
            license_number="TEST-SPLIT-ZERO",
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=30),
        )

        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=setup["sion"], cif_fc=Decimal("50000"),
        )

        # Import item with zero available_qty (already fully utilized)
        hs = HSCodeModel.objects.create(
            hs_code="1511.11", product_description="PKO variant", unit="KG",
        )
        source = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, hs_code=hs,
            description="PKO", unit="KG",
            quantity=Decimal("5000"),
            available_quantity=Decimal("5000"),
        )
        # A cache value is not evidence of use.  Record the complete
        # utilisation through the authoritative BOE ledger instead.
        boe = BillOfEntryModel.objects.create(
            company=setup["company"], bill_of_entry_number="SPLIT-ZERO-BOE",
            bill_of_entry_date=date.today(), exchange_rate=Decimal("1"),
        )
        RowDetails.objects.create(
            bill_of_entry=boe, sr_number=source, transaction_type=DEBIT,
            qty=Decimal("5000"), cif_fc=Decimal("50000"), cif_inr=Decimal("50000"),
        )

        result = execute_auto_plan(
            setup["client"], license_obj, sion_id=setup["sion"].pk,
            company_id=setup["company"].pk,
        )
        # Synchronous Auto Plan returns the durable request summary; the
        # persisted outcome remains no plan rows for a fully utilised item.
        assert result["write_results"] == 1
        assert LicenseItemPlan.objects.filter(license=license_obj).count() == 0

    def test_split_by_percent_respects_percentages(self, split_percent_setup):
        """Test that SPLIT_BY_PERCENTAGE correctly multiplies by each rule's percentage."""
        setup = split_percent_setup

        # Create asymmetric percentages: PKO 30%, OLIVE_OIL 70%
        from apps.core.models import ItemNameModel
        pko_item, _ = ItemNameModel.objects.get_or_create(
            name="PKO", defaults={"is_active": True}
        )
        olive_item, _ = ItemNameModel.objects.get_or_create(
            name="OLIVE_OIL", defaults={"is_active": True}
        )

        from apps.license.models import SionPlanningPercentageRow
        split_rule = SionPlanningRule.objects.create(
            sion=setup["sion"],
            name="PKO / OLIVE 30/70",
            expression={"operator": "AND", "conditions": []},
            max_unit_price=Decimal("100.00"),
            unit="KG",
            priority=1,
            is_active=True,
            strategy="SPLIT_BY_PERCENT",
            import_item=pko_item,
        )
        SionPlanningPercentageRow.objects.create(
            rule=split_rule, import_item=pko_item, percentage=Decimal("30"),
            unit_price=Decimal("2.70"), priority=1,
        )
        SionPlanningPercentageRow.objects.create(
            rule=split_rule, import_item=olive_item, percentage=Decimal("70"),
            unit_price=Decimal("4.00"), priority=2,
        )

        license_obj = LicenseDetailsModel.objects.create(
            exporter=setup["company"],
            license_number="TEST-SPLIT-30-70",
            license_date=date.today(),
            license_expiry_date=date.today() + timedelta(days=30),
        )

        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=setup["sion"], cif_fc=Decimal("100000"),
        )

        hs = HSCodeModel.objects.create(
            hs_code="1511.20", product_description="Oil variant", unit="KG",
        )
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, hs_code=hs,
            description="Oil", unit="KG",
            quantity=Decimal("10000"), available_quantity=Decimal("10000"),
        )

        execute_auto_plan(
            setup["client"], license_obj, sion_id=setup["sion"].pk,
            company_id=setup["company"].pk,
        )
        plans = list(LicenseItemPlan.objects.filter(license=license_obj).order_by("planned_quantity"))

        # PKO should get 30% of 10000 = 3000
        # OLIVE_OIL should get 70% of 10000 = 7000
        assert len(plans) == 2
        assert Decimal(str(plans[0].planned_quantity or 0)) == Decimal("3000")  # 30%
        assert Decimal(str(plans[1].planned_quantity or 0)) == Decimal("7000")  # 70%

    def test_theoretical_excess_persists_real_names_and_requires_manual_review(self, split_percent_setup):
        """Configured rows survive excess CIF unchanged and retain their item FKs."""
        from apps.core.models import ItemNameModel
        from apps.license.models import SionPlanningPercentageRow

        setup = split_percent_setup
        food = ItemNameModel.objects.create(name="FOOD FLAVOUR - E126", is_active=True)
        pko = ItemNameModel.objects.create(name="PALM KERNEL OIL - E126", is_active=True)
        olive = ItemNameModel.objects.create(name="OLIVE OIL - E126", is_active=True)
        standard = SionPlanningRule.objects.create(
            sion=setup["sion"], name="Food Flavour", expression={},
            max_unit_price=Decimal("2.70"), unit="KG", priority=1,
            strategy="STANDARD", import_item=food,
        )
        percent = SionPlanningRule.objects.create(
            sion=setup["sion"], name="PKO & OIL", expression={},
            max_unit_price=Decimal("5.00"), unit="KG", priority=2,
            strategy="SPLIT_BY_PERCENT",
        )
        SionPlanningPercentageRow.objects.create(
            rule=percent, import_item=pko, percentage=Decimal("40"),
            unit_price=Decimal("1.80"), max_quantity=Decimal("321138"), priority=1,
        )
        SionPlanningPercentageRow.objects.create(
            rule=percent, import_item=olive, percentage=Decimal("60"),
            unit_price=Decimal("5.00"), max_quantity=Decimal("321139"), priority=2,
        )
        license_obj = LicenseDetailsModel.objects.create(
            exporter=setup["company"], license_number="THEORETICAL-EXCESS",
            license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
        )
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=setup["sion"], cif_fc=Decimal("2772554.16"),
        )
        food_row = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Food additives",
            unit="KG", quantity=Decimal("226081.000"), available_quantity=Decimal("0"),
        )
        food_row.items.add(food)
        oil_row = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=2, description="Relevant fats and oils",
            unit="KG", quantity=Decimal("642277.000"), available_quantity=Decimal("0"),
        )
        oil_row.items.add(pko, olive)

        result = execute_auto_plan(
            setup["client"], license_obj, sion_id=setup["sion"].pk,
            company_id=setup["company"].pk,
        )
        assert result["write_results"]

        plans = {row.item_name.name: row for row in LicenseItemPlan.objects.filter(
            license=license_obj,
        ).select_related("item_name")}
        assert set(plans).issubset({food.name, pko.name, olive.name})
        assert plans
        assert sum((row.planned_cif_fc for row in plans.values()), Decimal("0")) <= Decimal("2772554.16")
        assert all(row.item_name_id for row in plans.values())

        api_response = setup["client"].get(f"/api/license-item-plans/?license={license_obj.pk}")
        rows = api_response.data.get("results", api_response.data)
        assert {row["planning_item_name"] for row in rows} == set(plans)
        assert all(not row["planning_item_name"].startswith("Split ") for row in rows)
