from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
)
from apps.license.services.canonical_planning_service import (
    CanonicalPlanningService,
    CompanyIsolationError,
    SionPlanningError,
)
from apps.license.services.planner_factory import PlanResult, PlannerFactory


pytestmark = pytest.mark.django_db
User = get_user_model()
PLAN_NORM_URL = "/api/license-item-plans/plan-norm/"


@pytest.fixture
def planning_world():
    head = HeadSIONNormsModel.objects.create(name="Single norm QA")
    e1 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E1", is_active=True,
    )
    e5 = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E5", is_active=True,
    )
    inactive = SionNormClassModel.objects.create(
        head_norm=head, norm_class="E132", is_active=False,
    )
    unsupported = SionNormClassModel.objects.create(
        head_norm=head, norm_class="ZZ9", is_active=True,
    )
    company_a = CompanyModel.objects.create(iec="9100000001", name="Single Norm A")
    company_b = CompanyModel.objects.create(iec="9100000002", name="Single Norm B")

    def make_license(company, number, norms):
        license_obj = LicenseDetailsModel.objects.create(
            exporter=company,
            license_number=number,
            license_date=date.today() - timedelta(days=5),
            license_expiry_date=date.today() + timedelta(days=30),
        )
        for norm in norms:
            LicenseExportItemModel.objects.create(
                license=license_obj, norm_class=norm, cif_fc=Decimal("500.00"),
            )
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description=f"Planning item {number}",
            quantity=Decimal("10.000"),
            available_quantity=Decimal("10.000"),
        )
        return license_obj, item

    multi, multi_item = make_license(company_a, "SINGLE-MULTI", [e1, e5])
    e5_only, e5_item = make_license(company_a, "SINGLE-E5", [e5])
    foreign, foreign_item = make_license(company_b, "SINGLE-FOREIGN", [e5])
    return {
        "e1": e1, "e5": e5, "inactive": inactive, "unsupported": unsupported,
        "company_a": company_a, "company_b": company_b,
        "multi": multi, "multi_item": multi_item,
        "e5_only": e5_only, "e5_item": e5_item,
        "foreign": foreign, "foreign_item": foreign_item,
    }


def _fake_planner(monkeypatch, *, fail_license_id=None):
    def run(license_obj, norm_code):
        if license_obj.pk == fail_license_id:
            raise RuntimeError("simulated planner failure")
        item = license_obj.import_license.all()[0]
        price = Decimal("5.00") if norm_code == "E5" else Decimal("1.00")
        return PlanResult(lines=[{
            "import_item": item.pk,
            "planned_quantity": Decimal("2.000"),
            "unit_price": price,
            "planned_cif_fc": Decimal("2.000") * price,
            "note": f"selected {norm_code}",
        }])

    monkeypatch.setattr(PlannerFactory, "run", staticmethod(run))


def _client(company=None, *, superuser=False):
    user = User.objects.create_user(
        username=f"single-norm-{User.objects.count()}", password="test-password",
        company=company, is_superuser=superuser, is_staff=superuser,
    )
    if not superuser:
        role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
        user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_explicit_second_norm_is_used_not_first_export_row(planning_world, monkeypatch):
    _fake_planner(monkeypatch)
    world = planning_world

    result = CanonicalPlanningService.plan_sion_for_licenses(
        world["e5"].pk, [world["multi"].pk], company_id=world["company_a"].pk,
    )

    assert result["norm_class"] == "E5"
    plan = LicenseItemPlan.objects.get(license=world["multi"])
    assert plan.unit_price == Decimal("5.00")
    assert plan.note == "selected E5"


@pytest.mark.parametrize("bad_sion", [None, "", [1], {"id": 1}, True])
def test_sion_id_must_be_one_scalar_integer(planning_world, bad_sion):
    with pytest.raises(SionPlanningError):
        CanonicalPlanningService.plan_sion_for_licenses(
            bad_sion, [planning_world["multi"].pk],
            company_id=planning_world["company_a"].pk,
        )


def test_inactive_unsupported_and_inapplicable_norms_are_rejected(planning_world):
    world = planning_world
    for norm in (world["inactive"], world["unsupported"]):
        with pytest.raises(SionPlanningError):
            CanonicalPlanningService.plan_sion_for_licenses(
                norm.pk, [world["multi"].pk], company_id=world["company_a"].pk,
            )

    with pytest.raises(SionPlanningError) as exc:
        CanonicalPlanningService.plan_sion_for_licenses(
            world["e1"].pk, [world["e5_only"].pk],
            company_id=world["company_a"].pk,
        )
    assert exc.value.details["inapplicable_license_ids"] == [world["e5_only"].pk]


def test_cross_company_batch_is_rejected_before_any_write(planning_world, monkeypatch):
    _fake_planner(monkeypatch)
    world = planning_world
    with pytest.raises(CompanyIsolationError):
        CanonicalPlanningService.plan_sion_for_licenses(
            world["e5"].pk, [world["e5_only"].pk, world["foreign"].pk],
            company_id=world["company_a"].pk,
        )
    assert not LicenseItemPlan.objects.exists()


def test_planner_failure_rolls_back_the_complete_batch(planning_world, monkeypatch):
    world = planning_world
    _fake_planner(monkeypatch, fail_license_id=world["e5_only"].pk)
    with pytest.raises(RuntimeError, match="simulated planner failure"):
        CanonicalPlanningService.plan_sion_for_licenses(
            world["e5"].pk, [world["multi"].pk, world["e5_only"].pk],
            company_id=world["company_a"].pk,
        )
    assert not LicenseItemPlan.objects.exists()


def test_repeat_is_idempotent_and_duplicate_license_ids_are_rejected(
    planning_world, monkeypatch,
):
    world = planning_world
    _fake_planner(monkeypatch)
    first = CanonicalPlanningService.plan_sion_for_licenses(
        world["e5"].pk, [world["multi"].pk], company_id=world["company_a"].pk,
    )
    plan_id = LicenseItemPlan.objects.get().pk
    second = CanonicalPlanningService.plan_sion_for_licenses(
        world["e5"].pk, [world["multi"].pk], company_id=world["company_a"].pk,
    )
    assert first["results"][0]["mutation_status"] == "CREATED"
    assert second["results"][0]["mutation_status"] == "UNCHANGED"
    assert first["created"] == 1
    assert second["unchanged"] == 1
    for response in (first, second):
        assert (
            response["created"] + response["updated"] + response["unchanged"]
            + response["blocked"]
        ) == response["licenses_requested"] == len(response["results"])
        row = response["results"][0]
        assert row["license_number"] == world["multi"].license_number
        assert row["sion_id"] == world["e5"].pk
        assert row["norm_class"] == "E5"
        assert row["status"] in {"FEASIBLE", "SHORT"}
        assert row["feasible"] is (row["status"] == "FEASIBLE")
        assert {
            "available_qty", "planned_qty", "allocated_qty", "consumed_qty",
            "remaining_qty", "shortage_qty",
        } <= row.keys()
    assert LicenseItemPlan.objects.get().pk == plan_id

    with pytest.raises(SionPlanningError):
        CanonicalPlanningService.plan_sion_for_licenses(
            world["e5"].pk, [world["multi"].pk, world["multi"].pk],
            company_id=world["company_a"].pk,
        )


def test_plan_norm_endpoint_enforces_company_and_retired_bulk_route_is_unavailable(
    planning_world, monkeypatch,
):
    world = planning_world
    _fake_planner(monkeypatch)
    client = _client(world["company_a"])

    ok = client.post(PLAN_NORM_URL, {
        "sion_id": world["e5"].pk,
        "license_ids": [world["multi"].pk],
    }, format="json")
    assert ok.status_code == 200

    forbidden = client.post(PLAN_NORM_URL, {
        "sion_id": world["e5"].pk,
        "license_ids": [world["foreign"].pk],
    }, format="json")
    assert forbidden.status_code == 403

    retired_routes = (
        ("post", "/api/license-item-plans/auto-plan-all/"),
        ("post", "/api/license-item-plans/auto-plan/"),
        ("post", "/api/license-item-plans/e1-auto-plan/"),
        ("get", f"/api/license-item-plans/norm-prefill/?license={world['multi'].pk}"),
    )
    for method, url in retired_routes:
        retired = getattr(client, method)(url, {}, format="json")
        assert retired.status_code in (404, 405), url


def test_planning_reads_and_url_selected_license_enforce_auth_and_company_scope(
    planning_world,
):
    world = planning_world
    anonymous = APIClient()
    snapshot_url = (
        f"/api/license-item-plans/planning-norms/?sion_id={world['e5'].pk}"
        f"&license_ids={world['multi'].pk}"
    )
    assert anonymous.get(snapshot_url).status_code in (401, 403)
    assert anonymous.get(
        f"/api/licenses/{world['multi'].pk}/plan-utilization/",
    ).status_code in (401, 403)

    client = _client(world["company_a"])
    foreign_snapshot_url = (
        f"/api/license-item-plans/planning-norms/?sion_id={world['e5'].pk}"
        f"&license_ids={world['foreign'].pk}"
    )
    assert client.get(foreign_snapshot_url).status_code == 403
    assert client.get(
        f"/api/licenses/{world['foreign'].pk}/plan-utilization/",
    ).status_code == 404
    # The workspace first resolves URL-selected licence metadata/summary;
    # those detail paths must share the same tenant boundary.
    assert client.get(f"/api/licenses/{world['foreign'].pk}/").status_code == 404
    assert client.get(
        f"/api/licenses/{world['foreign'].pk}/overview-summary/",
    ).status_code == 404


def test_applicable_norm_envelope_supplies_canonical_workspace_summary(planning_world):
    world = planning_world
    response = _client(world["company_a"]).get(
        f"/api/license-item-plans/planning-norms/?license_ids={world['multi'].pk}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["license_ids"] == [world["multi"].pk]
    assert data["summary"]["selected_licenses"] == 1
    assert data["summary"]["applicable_norms"] == len(data["norms"])
    assert set(data["summary"]) == {
        "selected_licenses", "applicable_norms", "existing_plans",
        "shortages_blocked",
    }
    for norm in data["norms"]:
        assert "export_norm" in norm
        assert "import_norm" in norm
