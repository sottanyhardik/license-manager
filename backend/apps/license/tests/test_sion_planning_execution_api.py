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
from apps.license.views.sion_planning_rule import SionPlanRequestSerializer


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("code,hsn,description,legacy_compute", [
    ("E1", "080211", "Almond", compute_e1_auto_plan),
    ("E5", "210600", "Dietary fibre", compute_e5_auto_plan),
])
def test_plan_sion_api_uses_db_classifier_and_preserves_legacy_mechanics(
    code, hsn, description, legacy_compute,
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
