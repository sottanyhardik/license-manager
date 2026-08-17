from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    LicenseItemPlan, SionPlanningRule,
)
from apps.license.services.e1_auto_plan import compute_e1_auto_plan
from apps.license.services.e5_auto_plan import compute_e5_auto_plan
from apps.license.services.sion_planner_config.importer import import_e1_e5_profiles
from apps.license.services.sion_planning_execution import SionPlanningExecutionService
from apps.license.views.sion_planning_rule import SionPlanRequestSerializer


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("code,hsn,description,legacy_compute", [
    ("E1", "080211", "Almond", compute_e1_auto_plan),
    ("E5", "210600", "Dietary fibre", compute_e5_auto_plan),
])
def test_plan_sion_api_uses_db_classifier_and_preserves_legacy_mechanics(
    code, hsn, description, legacy_compute, django_assert_num_queries,
):
    head = HeadSIONNormsModel.objects.create(name="Execution bridge")
    sions = {
        norm: SionNormClassModel.objects.create(
            head_norm=head, norm_class=norm, is_active=True,
        )
        for norm in ("E1", "E5")
    }
    import_e1_e5_profiles(activate=True)
    SionPlanningRule.objects.filter(sion=sions[code]).update(is_active=True)
    company = CompanyModel.objects.create(iec=f"BRIDGE-{code}", name=f"Bridge {code}")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company, license_number=f"BRIDGE-{code}-1",
        license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=sions[code], cif_fc=Decimal("1000"),
    )
    hs = HSCodeModel.objects.create(hs_code=hsn, product_description=description, unit="kg")
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs, description=description,
        unit="kg", quantity=Decimal("100"), available_quantity=Decimal("100"),
    )

    legacy_lines, _ = legacy_compute(license_obj)
    # Make this fixture fully planned after its first write so the established
    # NEW/default >=99% guard is observable.  ALL must still rebuild it.
    planned_cif = sum(Decimal(str(row["planned_cif_fc"])) for row in legacy_lines)
    LicenseExportItemModel.objects.filter(license=license_obj).update(cif_fc=planned_cif)
    legacy_lines, legacy_remaining = legacy_compute(license_obj)
    user = get_user_model().objects.create_user(username=f"bridge-{code}", company=company)
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user)

    preview = client.post(
        "/api/sion-planning-rules/preview-sion/",
        {"sion_id": sions[code].pk, "license_ids": []}, format="json",
    )
    assert preview.status_code == 200, preview.data
    actual_lines = preview.data["licenses"][0]["lines"]
    assert [(Decimal(str(row["requested_quantity"])), Decimal(str(row["unit_price"]))) for row in actual_lines] == [
        (Decimal(str(row["planned_quantity"])), Decimal(str(row["unit_price"])))
        for row in legacy_lines
    ]
    assert Decimal(str(preview.data["licenses"][0]["remaining_balance_cif"])) == Decimal(str(legacy_remaining))
    preview_license = preview.data["licenses"][0]
    assert preview_license["change_status"] == "NEW"
    assert preview_license["matched_item_count"] == 1
    assert preview_license["matched_rule_count"] == 1
    assert preview_license["items"][0]["rule_priority"] >= 1
    assert preview.data["summary"]["licenses_new"] == 1
    assert len({row["license_id"] for row in preview.data["licenses"]}) == len(preview.data["licenses"])

    # The license-level DTO comparison must stay bulk: one import-item query,
    # one item-name prefetch and one current-plan query.  In particular this
    # guards against calling the canonical current-plan lookup once per
    # license while adding existing-vs-proposed change detection.
    configuration = SionPlanningExecutionService.resolve_configuration(sions[code])
    raw_preview = [{
        "license_id": license_obj.pk,
        "license_number": license_obj.license_number,
        "lines": preview_license["lines"],
        "status": "PREVIEWED",
    }]
    with django_assert_num_queries(3):
        regrouped = SionPlanningExecutionService._group_preview(
            raw_preview, [license_obj], configuration, sions[code],
        )
    assert regrouped[0]["license_id"] == license_obj.pk

    shortage_preview = [{**raw_preview[0], "status": "SHORTAGE"}]
    shortage_grouped = SionPlanningExecutionService._group_preview(
        shortage_preview, [license_obj], configuration, sions[code],
    )
    assert shortage_grouped[0]["change_status"] == "SHORTAGE"
    assert shortage_grouped[0]["has_shortage"] is True

    planned = client.post(
        "/api/sion-planning-rules/plan-sion/",
        {"sion_id": sions[code].pk}, format="json",
    )
    assert planned.status_code == 200, planned.data
    assert planned.data["sion"] == code
    assert planned.data["licenses"][0]["license_id"] == license_obj.pk
    assert planned.data["write_results"][0]["status"] == "PLANNED"

    current_preview = client.post(
        "/api/sion-planning-rules/preview-sion/",
        {"sion_id": sions[code].pk, "mode": "ALL"}, format="json",
    )
    assert current_preview.status_code == 200, current_preview.data
    current_license = current_preview.data["licenses"][0]
    assert current_license["change_status"] == "NO_CHANGE"
    assert current_license["existing_plan"]["item_count"] == len(legacy_lines)
    assert current_license["proposed_plan"]["item_count"] == len(legacy_lines)
    assert current_preview.data["summary"]["licenses_unchanged"] == 1

    new_again = client.post(
        "/api/sion-planning-rules/plan-sion/",
        {"sion_id": sions[code].pk, "mode": "NEW"}, format="json",
    )
    assert new_again.status_code == 200, new_again.data
    assert new_again.data["mode"] == "NEW"
    assert new_again.data["write_results"][0]["status"] == "SKIPPED_ALREADY_PLANNED"

    force_all = client.post(
        "/api/sion-planning-rules/plan-sion/",
        {"sion_id": sions[code].pk, "mode": "ALL", "license_ids": []}, format="json",
    )
    assert force_all.status_code == 200, force_all.data
    assert force_all.data["mode"] == "ALL"
    assert force_all.data["write_results"][0]["status"] == "PLANNED"

    force_all_without_license_ids = client.post(
        "/api/sion-planning-rules/plan-sion/",
        {"sion_id": sions[code].pk, "mode": "ALL"}, format="json",
    )
    assert force_all_without_license_ids.status_code == 200, force_all_without_license_ids.data
    assert force_all_without_license_ids.data["mode"] == "ALL"

    LicenseItemPlan.objects.filter(license=license_obj).update(
        planned_quantity=Decimal("0.001"), planned_cif_fc=Decimal("0.01"),
    )
    changed_preview = client.post(
        "/api/sion-planning-rules/preview-sion/",
        {"sion_id": sions[code].pk, "mode": "ALL"}, format="json",
    )
    assert changed_preview.status_code == 200, changed_preview.data
    assert changed_preview.data["licenses"][0]["change_status"] == "CHANGE"
    assert changed_preview.data["summary"]["licenses_changed"] == 1


def test_plan_sion_rejects_unknown_mode_before_execution():
    serializer = SionPlanRequestSerializer(data={"sion_id": 1, "mode": "EVERYTHING"})
    assert not serializer.is_valid()
    assert "mode" in serializer.errors


def test_registered_sion_uses_db_rules_when_optional_profile_is_absent():
    head = HeadSIONNormsModel.objects.create(name="Profile-independent bridge")
    e1 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E1", is_active=True,
    )
    rule = SionPlanningRule.objects.create(
        sion=e1, name="001 COCOA MASS", expression={
            "operator": "OR", "conditions": [{
                "field": "HSN", "operator": "CONTAINS", "value": "1803",
            }],
        }, max_unit_price=Decimal("10"), unit="kg", priority=1,
        is_active=True, execution_output="",
    )

    assert SionPlanningExecutionService.supports(e1)
    configuration = SionPlanningExecutionService.resolve_configuration(e1)
    assert configuration.rules == (rule,)
    assert configuration.output_by_rule_key[f"pk:{rule.pk}"] == "COCOA MASS"


def test_force_all_plans_every_eligible_e1_license_and_is_idempotent():
    """The batch universe is never reduced to its first license or company."""
    head = HeadSIONNormsModel.objects.create(name="Force-all population")
    e1 = SionNormClassModel.objects.create(head_norm=head, norm_class="E1", is_active=True)
    other = SionNormClassModel.objects.create(head_norm=head, norm_class="E5", is_active=True)
    import_e1_e5_profiles(activate=True)
    SionPlanningRule.objects.filter(sion=e1).update(is_active=True)

    companies = [
        CompanyModel.objects.create(iec=f"FORCE-{index}", name=f"Force {index}")
        for index in range(2)
    ]

    def make_license(number, *, norm=e1, balance="1000", expired=False, company=None, hsn_prefix="0802"):
        license_obj = LicenseDetailsModel.objects.create(
            exporter=company or companies[0], license_number=number,
            license_date=date.today(),
            license_expiry_date=date.today() - timedelta(days=1) if expired else date.today() + timedelta(days=30),
        )
        LicenseExportItemModel.objects.create(
            license=license_obj, norm_class=norm, cif_fc=Decimal(balance),
        )
        hs = HSCodeModel.objects.create(
            hs_code=f"{hsn_prefix}{license_obj.pk:04d}", product_description="Almond", unit="kg",
        )
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, hs_code=hs, description="Almond",
            unit="kg", quantity=Decimal("100"), available_quantity=Decimal("100"),
        )
        return license_obj

    eligible = [
        make_license(f"FORCE-E1-{index}", company=companies[index % 2])
        for index in range(5)
    ]
    exhausted = make_license("FORCE-EXHAUSTED", balance="0")
    expired = make_license("FORCE-EXPIRED", expired=True)
    non_e1 = make_license("FORCE-E5", norm=other)
    existing_unmatched = make_license("FORCE-EXISTING", hsn_prefix="9999")
    existing_item = existing_unmatched.import_license.get()
    existing_plan = LicenseItemPlan.objects.create(
        license=existing_unmatched, import_item=existing_item,
        planned_quantity=Decimal("1"), unit_price=Decimal("1"),
        planned_cif_fc=Decimal("1"),
    )

    first = SionPlanningExecutionService.plan_sion(e1, mode="ALL", company_id=None)
    assert first["eligible_licenses"] == 6
    assert first["planned_licenses"] == 5
    assert first["skipped_count"] == 1
    assert first["failed_count"] == 0
    assert {row["license_id"] for row in first["write_results"]} == {
        *(row.pk for row in eligible), existing_unmatched.pk,
    }
    assert sum(row["status"] == "PLANNED" for row in first["write_results"]) == 5
    assert first["excluded_licenses"] == [{
        "license_id": existing_unmatched.pk,
        "license_number": existing_unmatched.license_number,
        "reason": "SKIPPED_NO_MATCH",
    }]
    assert LicenseItemPlan.objects.filter(pk=existing_plan.pk).exists()
    assert all(LicenseItemPlan.objects.filter(license=row).exists() for row in eligible)
    assert not LicenseItemPlan.objects.filter(
        license_id__in=[exhausted.pk, expired.pk, non_e1.pk],
    ).exists()

    line_count = LicenseItemPlan.objects.filter(license_id__in=[row.pk for row in eligible]).count()
    second = SionPlanningExecutionService.plan_sion(e1, mode="ALL", company_id=None)
    assert second["planned_licenses"] == 5
    assert LicenseItemPlan.objects.filter(
        license_id__in=[row.pk for row in eligible],
    ).count() == line_count
