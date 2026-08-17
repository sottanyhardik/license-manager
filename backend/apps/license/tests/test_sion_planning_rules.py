from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, HeadSIONNormsModel, HSCodeModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel,
    LicenseItemPlan, SionPlanningRule,
)
from apps.license.services.canonical_planning_service import CanonicalPlanningService
from apps.license.services.sion_rule_engine import (
    SionRulePlanningService, evaluate_expression, validate_expression,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def rule_world():
    head = HeadSIONNormsModel.objects.create(name="Rule engine")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="R77", is_active=True)
    company = CompanyModel.objects.create(iec="9200000001", name="Rule Company")
    license_obj = LicenseDetailsModel.objects.create(
        exporter=company, license_number="RULE-LIC-1", license_date=date.today(),
        license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(
        license=license_obj, norm_class=sion, cif_fc=Decimal("100.00"),
    )
    hs = HSCodeModel.objects.create(
        hs_code="001701", product_description="Refined   Sugar",
        unit_price=Decimal("2.25"), unit="kg",
    )
    item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs,
        description=" Refined   Sugar ", unit="kg", quantity=Decimal("10.000"),
        available_quantity=Decimal("8.000"),
    )
    rule = SionPlanningRule.objects.create(
        sion=sion, name="Sugar", unit="kg", max_unit_price=Decimal("2.50"),
        priority=1,
        expression={"operator": "AND", "conditions": [
            {"field": "HSN", "comparator": "CONTAINS", "value": "1701"},
            {"operator": "NOT", "conditions": [{
                "field": "PRODUCT_DESCRIPTION", "comparator": "NOT_CONTAINS", "value": "sugar",
            }]},
        ]},
    )
    return company, sion, license_obj, item, rule


def _client(company):
    user = get_user_model().objects.create_user(username="rule-manager", company=company)
    role, _ = Group.objects.get_or_create(name="LICENSE_MANAGER")
    user.groups.add(role)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def test_safe_nested_expression_normalizes_case_space_and_hsn_zeroes():
    expression = {"operator": "AND", "conditions": [
        {"field": "HSN", "comparator": "CONTAINS", "value": " 1701 "},
        {"operator": "NOT", "condition": {
            "field": "PRODUCT_DESCRIPTION", "comparator": "NOT_CONTAINS", "value": "sugar",
        }},
    ]}
    assert evaluate_expression(expression, {"hs_code": "001701", "description": "Refined   SUGAR"})


def test_unknown_expression_field_is_rejected():
    with pytest.raises(Exception, match="Unsupported rule field"):
        validate_expression({"field": "__class__", "comparator": "EQ", "value": "x"})


def test_preview_uses_current_price_and_ceiling_is_not_a_replacement(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    preview = SionRulePlanningService.preview(rule, [], company_id=company.pk)
    line = preview["results"][0]["matched_lines"][0]
    assert line["current_unit_price"] == Decimal("2.25")
    assert line["max_unit_price"] == Decimal("2.50")
    assert line["price_status"] == "WITHIN_MAX"
    assert preview["conflicts"] == []
    assert preview["results"][0]["license_id"] == license_obj.pk


def test_above_ceiling_blocks_plan(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    rule.max_unit_price = Decimal("2.00")
    rule.save()
    preview = SionRulePlanningService.preview(rule, [license_obj.pk], company_id=company.pk)
    assert preview["can_plan"] is False
    assert preview["conflicts"][0]["price_status"] == "ABOVE_MAX"


def test_plan_passes_current_price_to_canonical_writer(rule_world, monkeypatch):
    company, _sion, license_obj, _item, rule = rule_world
    captured = []
    def fake_build(**kwargs):
        captured.append(kwargs)
        return {"license_id": kwargs["license_id"]}
    monkeypatch.setattr(CanonicalPlanningService, "build_canonical_plan", staticmethod(fake_build))
    result = SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)
    assert result["planned_licenses"] == 1
    assert captured[0]["items"][0]["unit_price"] == Decimal("2.25")


def test_preview_never_writes_and_duplicate_ids_are_rejected(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    before = LicenseItemPlan.objects.count()
    SionRulePlanningService.preview(rule, [license_obj.pk], company_id=company.pk)
    assert LicenseItemPlan.objects.count() == before
    with pytest.raises(Exception, match="duplicate"):
        SionRulePlanningService.preview(
            rule, [license_obj.pk, license_obj.pk], company_id=company.pk,
        )


def test_database_rejects_duplicate_active_priority(rule_world):
    _company, sion, _license_obj, _item, rule = rule_world
    with pytest.raises(IntegrityError):
        SionPlanningRule.objects.create(
            sion=sion, name="Sugar duplicate", unit="kg",
            max_unit_price=Decimal("2.50"), priority=rule.priority,
            expression=rule.expression,
        )


def test_inactive_rule_cannot_plan(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    rule.is_active = False
    rule.save(update_fields=["is_active"])
    with pytest.raises(Exception, match="active rule"):
        SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)


def test_repeated_plan_is_idempotent(rule_world):
    company, _sion, license_obj, _item, rule = rule_world
    first = SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)
    plan_ids = list(LicenseItemPlan.objects.values_list("pk", flat=True))
    second = SionRulePlanningService.plan(rule, [license_obj.pk], company_id=company.pk)
    assert first["planned_licenses"] == second["planned_licenses"] == 1
    assert list(LicenseItemPlan.objects.values_list("pk", flat=True)) == plan_ids


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_plan_creates_one_stable_row(rule_world):
    import threading
    from django.db import connections

    company, _sion, license_obj, _item, rule = rule_world
    barrier = threading.Barrier(2)
    results, errors = [], []

    def worker():
        try:
            barrier.wait(timeout=5)
            result = SionRulePlanningService.plan(
                SionPlanningRule.objects.get(pk=rule.pk),
                [license_obj.pk], company_id=company.pk,
            )
            results.append(result)
        except Exception as exc:  # surfaced below with the original exception
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not errors, errors
    assert len(results) == 2
    assert LicenseItemPlan.objects.filter(license=license_obj).count() == 1
    assert any(
        row["write_results"][0].get("mutation_status") == "UNCHANGED"
        for row in results
    )


def test_rule_api_permissions_and_company_isolation(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    viewer = get_user_model().objects.create_user(username="rule-viewer", company=company)
    viewer_group, _ = Group.objects.get_or_create(name="LICENSE_VIEWER")
    viewer.groups.add(viewer_group)
    viewer_client = APIClient()
    viewer_client.force_authenticate(viewer)
    assert viewer_client.get("/api/sion-planning-rules/").status_code == 200
    assert viewer_client.post(
        f"/api/sion-planning-rules/{rule.pk}/test/", {}, format="json",
    ).status_code == 403
    assert viewer_client.post(
        "/api/sion-planning-rules/plan-sion/", {"sion_id": sion.pk}, format="json",
    ).status_code == 403
    assert viewer_client.post(
        "/api/sion-planning-rules/preview-sion/", {"sion_id": sion.pk}, format="json",
    ).status_code == 403

    foreign_company = CompanyModel.objects.create(iec="9200000002", name="Foreign Rule")
    foreign_license = LicenseDetailsModel.objects.create(
        exporter=foreign_company, license_number="RULE-FOREIGN",
        license_date=date.today(), license_expiry_date=date.today() + timedelta(days=30),
    )
    LicenseExportItemModel.objects.create(license=foreign_license, norm_class=sion)
    manager_client, _user = _client(company)
    response = manager_client.post(
        f"/api/sion-planning-rules/{rule.pk}/test/",
        {"license_ids": [foreign_license.pk]}, format="json",
    )
    assert response.status_code == 403


def test_crud_versions_and_delete_retires_history(rule_world):
    company, sion, _license_obj, _item, _rule = rule_world
    client, user = _client(company)
    payload = {
        "sion": sion.pk, "name": "API Rule", "unit": "KG",
        "max_unit_price": "3.00", "priority": 5, "is_active": True,
        "expression": {"operator": "AND", "conditions": [
            {"field": "HSN", "comparator": "CONTAINS", "value": "17"},
        ]},
    }
    created = client.post("/api/sion-planning-rules/", payload, format="json")
    assert created.status_code == 201, created.data
    first_id = created.data["id"]
    assert created.data["version"] == 1
    assert SionPlanningRule.objects.get(pk=first_id).created_by == user
    updated = client.patch(f"/api/sion-planning-rules/{first_id}/", {"max_unit_price": "3.10"}, format="json")
    assert updated.status_code == 200, updated.data
    assert updated.data["id"] != first_id and updated.data["version"] == 2
    assert SionPlanningRule.objects.get(pk=first_id).is_active is False
    retired = client.delete(f"/api/sion-planning-rules/{updated.data['id']}/")
    assert retired.status_code == 204
    assert SionPlanningRule.objects.filter(pk=updated.data["id"], is_active=False).exists()
    assert SionPlanningRule.objects.filter(name="API Rule").count() == 2


def test_database_priority_assignment_is_sion_scoped_and_reorder_persists(rule_world):
    company, sion, _license_obj, _item, existing = rule_world
    client, _user = _client(company)
    head = sion.head_norm
    other_sion = SionNormClassModel.objects.create(
        head_norm=head, norm_class="R78", is_active=True,
    )
    payload = {
        "name": "Second", "unit": "kg", "max_unit_price": "4.20",
        "expression": {"field": "HSN", "comparator": "CONTAINS", "value": "99"},
    }
    second = client.post(
        "/api/sion-planning-rules/", {**payload, "sion": sion.pk, "priority": 88}, format="json",
    )
    first_other = client.post(
        "/api/sion-planning-rules/", {**payload, "sion": other_sion.pk}, format="json",
    )
    assert second.status_code == first_other.status_code == 201
    assert second.data["priority"] == 2
    assert first_other.data["priority"] == 1
    reordered = client.post("/api/sion-planning-rules/reorder/", {
        "sion_id": sion.pk, "rule_order": [second.data["id"], existing.pk],
    }, format="json")
    assert reordered.status_code == 200, reordered.data
    assert list(SionPlanningRule.objects.filter(
        sion=sion, is_active=True,
    ).order_by("priority").values_list("pk", "priority")) == [
        (second.data["id"], 1), (existing.pk, 2),
    ]
    retired = client.delete(f"/api/sion-planning-rules/{second.data['id']}/")
    assert retired.status_code == 204
    existing.refresh_from_db()
    assert existing.priority == 1


def test_plan_sion_uses_only_saved_active_rules_and_records_provenance(rule_world):
    company, sion, license_obj, _item, rule = rule_world
    client, _user = _client(company)
    response = client.post("/api/sion-planning-rules/plan-sion/", {
        "sion_id": sion.pk,
        "license_ids": [license_obj.pk],
        "rules": [{"expression": {"field": "HSN", "operator": "CONTAINS", "value": "fake"}}],
    }, format="json")
    assert response.status_code == 400
    assert not LicenseItemPlan.objects.exists()

    response = client.post("/api/sion-planning-rules/plan-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["rules_executed"] == [{
        "id": rule.pk, "version": 1, "priority": 1,
    }]
    plan = LicenseItemPlan.objects.get()
    assert plan.planning_rule_id == rule.pk
    assert plan.planning_rule_version == 1
    assert plan.planning_rule_priority == 1


def test_sion_preview_is_read_only_database_driven_and_isolated(rule_world):
    company, sion, license_obj, _item, rule = rule_world
    client, _user = _client(company)
    before = LicenseItemPlan.objects.count()
    rejected = client.post("/api/sion-planning-rules/preview-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
        "rules": [{"expression": {"operator": "OR", "conditions": []}}],
    }, format="json")
    assert rejected.status_code == 400

    response = client.post("/api/sion-planning-rules/preview-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["rules_processed"] == [{
        "id": rule.pk, "version": rule.version, "priority": rule.priority,
    }]
    assert response.data["licenses"][0]["status"] == "NOT_PLANNED"
    assert LicenseItemPlan.objects.count() == before

    other_sion = SionNormClassModel.objects.create(
        head_norm=sion.head_norm, norm_class="R79", is_active=True,
    )
    SionPlanningRule.objects.create(
        sion=other_sion, name="Other norm only", unit="kg",
        max_unit_price=Decimal("9.00"), priority=1,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "1701"},
    )
    response = client.post("/api/sion-planning-rules/preview-sion/", {
        "sion_id": sion.pk, "license_ids": [license_obj.pk],
    }, format="json")
    assert [row["id"] for row in response.data["rules_processed"]] == [rule.pk]


def test_norm_preview_runs_canonical_waterfall_in_saved_priority_order(rule_world):
    company, sion, license_obj, _item, first = rule_world
    hs = HSCodeModel.objects.create(
        hs_code="009999", product_description="Second", unit_price=Decimal("2.00"), unit="kg",
    )
    LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=2, hs_code=hs, description="Second",
        unit="kg", quantity=Decimal("10.000"), available_quantity=Decimal("10.000"),
    )
    second = SionPlanningRule.objects.create(
        sion=sion, name="Second", unit="kg", max_unit_price=Decimal("2.00"), priority=2,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "9999"},
    )
    result = SionRulePlanningService.preview_sion(
        sion.pk, [license_obj.pk], company_id=company.pk,
    )
    assert [row["id"] for row in result["rules_processed"]] == [first.pk, second.pk]
    allocated = result["licenses"][0]["allocated_items"]
    assert [row["planning_rule_id"] for row in allocated] == [first.pk, second.pk]
    assert [row["priority"] for row in allocated] == [1, 2]
    assert result["licenses"][0]["remaining_balance_cif"] == (
        result["licenses"][0]["opening_balance_cif"]
        - sum(row["planned_cif_fc"] for row in allocated)
    )
    assert not LicenseItemPlan.objects.exists()
