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
    LicenseItemPlan, SionPlanningAction, SionPlanningProfile, SionPlanningRule,
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


def _split_action(sion, rule):
    rule.execution_output = "MILK PRODUCTS"
    rule.save(update_fields=("execution_output",))
    profile = SionPlanningProfile.objects.create(
        sion=sion, stable_key=f"{sion.norm_class}:PROFILE", is_active=True,
    )
    return SionPlanningAction.objects.create(
        profile=profile, stable_key=f"{sion.norm_class}:SPLIT", action_type="SPLIT",
        priority=1, config={
            "algorithm": "SPLIT_BY_UNIT_VALUE",
            "basis": "BALANCE_CIF_PER_QUANTITY",
            "category": "MILK PRODUCTS",
            "granularity": "ITEM_SEQUENTIAL",
            "buckets": [
                {"code": "SWP", "min_price": "0.00", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "DWP", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        },
    )


def test_allocation_strategy_api_reads_and_updates_canonical_action(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    action = _split_action(sion, rule)
    client, _user = _client(company)

    response = client.get(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/")
    assert response.status_code == 200
    assert response.data["strategy"] == "SPLIT_BY_UNIT_VALUE"
    assert response.data["config"]["buckets"][1]["max_price"] == "6.50"

    changed = response.data["config"]
    changed["buckets"][1]["max_price"] = "6.75"
    response = client.patch(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", {
        "strategy": "SPLIT_BY_UNIT_VALUE", "config": changed,
    }, format="json")
    assert response.status_code == 200
    action.refresh_from_db()
    assert action.config["buckets"][1]["max_price"] == "6.75"
    assert action.config["category"] == "MILK PRODUCTS"
    assert action.config["granularity"] == "ITEM_SEQUENTIAL"
    assert action.version == 2


def test_allocation_strategy_api_rejects_invalid_band(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    _split_action(sion, rule)
    client, _user = _client(company)
    response = client.patch(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", {
        "strategy": "SPLIT_BY_UNIT_VALUE",
        "config": {
            "algorithm": "SPLIT_BY_UNIT_VALUE", "basis": "BALANCE_CIF_PER_QUANTITY",
            "buckets": [
                {"code": "SWP", "min_price": "1.50", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "DWP", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        },
    }, format="json")
    assert response.status_code == 400


def test_allocation_strategy_api_creates_db_action_for_new_rule_and_reloads(rule_world):
    company, _sion, _license_obj, _item, rule = rule_world
    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_UNIT_VALUE",
        "config": {
            "algorithm": "SPLIT_BY_UNIT_VALUE", "basis": "BALANCE_CIF_PER_QUANTITY",
            "buckets": [
                {"code": "LOW", "min_price": "0.00", "max_price": "1.50", "reference_price": "1.50"},
                {"code": "HIGH", "min_price": "1.50", "max_price": "6.50", "reference_price": "6.50"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 200
    action = SionPlanningAction.objects.get(pk=response.data["action_id"])
    assert action.config["source_rule_id"] == rule.pk
    assert action.config["category"] == rule.name

    reloaded = client.get(f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/")
    assert reloaded.status_code == 200
    assert reloaded.data["config"]["buckets"] == payload["config"]["buckets"]


def test_split_by_percentage_accepts_editable_rows(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    output_item = ItemNameModel.objects.create(name="PKO")
    rule.output_item = output_item
    rule.save(update_fields=("output_item",))

    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {
            "algorithm": "SPLIT_BY_PERCENTAGE",
            "rows": [
                {"id": "row-1", "output_code": "PKO", "percentage": "50.00"},
                {"id": "row-2", "output_code": "OLIVE_OIL", "percentage": "50.00"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 200
    action = SionPlanningAction.objects.get(pk=response.data["action_id"])
    assert action.config["algorithm"] == "SPLIT_BY_PERCENTAGE"
    assert action.config["rows"] == payload["config"]["rows"]
    assert action.is_active is True


def test_split_by_percentage_rejects_percentages_not_summing_to_100(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    output_item = ItemNameModel.objects.create(name="PKO")
    rule.output_item = output_item
    rule.save(update_fields=("output_item",))

    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {
            "algorithm": "SPLIT_BY_PERCENTAGE",
            "rows": [
                {"id": "row-1", "output_code": "PKO", "percentage": "40.00"},
                {"id": "row-2", "output_code": "OLIVE_OIL", "percentage": "40.00"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 400
    assert "100" in str(response.data.get("config", ""))


def test_split_by_percentage_rejects_duplicate_input_codes(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel
    output_item = ItemNameModel.objects.create(name="PKO")
    rule.output_item = output_item
    rule.save(update_fields=("output_item",))

    client, _user = _client(company)
    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {
            "algorithm": "SPLIT_BY_PERCENTAGE",
            "rows": [
                {"id": "row-1", "output_code": "PKO", "percentage": "60.00"},
                {"id": "row-2", "output_code": "PKO", "percentage": "40.00"},
            ],
        },
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 400
    assert "Duplicate" in response.data.get("config", "")


def test_split_by_percentage_loads_from_master_rules_as_defaults(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    from apps.core.models import ItemNameModel

    output_item_1 = ItemNameModel.objects.create(name="PKO")
    output_item_2 = ItemNameModel.objects.create(name="OLIVE_OIL")
    rule.output_item = output_item_1
    rule.save(update_fields=("output_item",))

    master_rule_1 = SionPlanningRule.objects.create(
        sion=sion, name="PKO Cap", unit="kg", max_unit_price=Decimal("2.50"),
        priority=2, output_item=output_item_1, percentage_constraint=Decimal("50.00"),
        expression={},
    )
    master_rule_2 = SionPlanningRule.objects.create(
        sion=sion, name="Olive Cap", unit="kg", max_unit_price=Decimal("2.50"),
        priority=3, output_item=output_item_2, percentage_constraint=Decimal("50.00"),
        expression={},
    )

    client, _user = _client(company)

    payload = {
        "strategy": "SPLIT_BY_PERCENTAGE",
        "config": {"algorithm": "SPLIT_BY_PERCENTAGE", "rows": []},
    }
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/allocation-strategy/", payload, format="json",
    )
    assert response.status_code == 200
    action = SionPlanningAction.objects.get(pk=response.data["action_id"])
    assert action.config["algorithm"] == "SPLIT_BY_PERCENTAGE"
    assert len(action.config.get("rows", [])) == 2
    percentages = {row["output_code"]: row["percentage"] for row in action.config.get("rows", [])}
    assert percentages.get("PKO") == "50.00"
    assert percentages.get("OLIVE_OIL") == "50.00"


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


@pytest.mark.parametrize("endpoint", ("plan-sion", "preview-sion"))
@pytest.mark.parametrize("include_empty_license_ids", (False, True))
def test_sion_first_api_uses_eligible_company_licenses_when_filter_is_omitted_or_empty(
    rule_world, endpoint, include_empty_license_ids,
):
    """An empty license filter is the SION-first contract, not invalid input."""
    company, sion, license_obj, _item, _rule = rule_world
    client, _user = _client(company)
    payload = {"sion_id": sion.pk}
    if include_empty_license_ids:
        payload["license_ids"] = []

    response = client.post(
        f"/api/sion-planning-rules/{endpoint}/", payload, format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["sion_id"] == sion.pk
    assert len(response.data["licenses"]) == 1
    assert response.data["licenses"][0]["license_id"] == license_obj.pk
    assert response.data["licenses"][0]["license_number"] == license_obj.license_number


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


def test_versioned_edit_preserves_execution_mapping_identity(rule_world):
    company, _sion, _license_obj, _item, rule = rule_world
    rule.stable_key = "TEST:RULE:001"
    rule.save(update_fields=("stable_key",))
    client, _user = _client(company)
    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/",
        {"max_unit_price": "3.10"}, format="json",
    )
    assert response.status_code == 200, response.data
    assert SionPlanningRule.objects.get(pk=response.data["id"]).stable_key == rule.stable_key


def test_versioned_clear_expression_is_match_none_and_preserves_execution_output(rule_world):
    company, sion, _license_obj, _item, rule = rule_world
    rule.stable_key = "TEST:RULE:CLEAR"
    rule.execution_output = "OTHER CONFECTIONERY INGREDIENTS"
    rule.save(update_fields=("stable_key", "execution_output"))
    untouched = SionPlanningRule.objects.create(
        sion=sion, stable_key="TEST:RULE:OTHER", name="Other", version=1,
        unit="kg", max_unit_price=Decimal("9.00"), priority=2,
        execution_output="EGG ALBUMIN",
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "3502"},
    )
    client, _user = _client(company)

    response = client.patch(
        f"/api/sion-planning-rules/{rule.pk}/",
        {"expression": {"operator": "AND", "conditions": [
            {"operator": "OR", "conditions": []},
        ]}},
        format="json",
    )

    assert response.status_code == 200, response.data
    replacement = SionPlanningRule.objects.get(pk=response.data["id"])
    assert replacement.version == rule.version + 1
    assert replacement.expression == {"operator": "AND", "conditions": []}
    assert replacement.execution_output == "OTHER CONFECTIONERY INGREDIENTS"
    assert evaluate_expression(replacement.expression, {
        "hs_code": "08029900", "description": "Other Confectionery",
    }) is False
    for endpoint, mode in (
        ("preview-sion", "NEW"), ("plan-sion", "NEW"), ("plan-sion", "ALL"),
    ):
        execution = client.post(
            f"/api/sion-planning-rules/{endpoint}/",
            {"sion_id": sion.pk, "mode": mode}, format="json",
        )
        assert execution.status_code == 200, execution.data
        assert execution.data["licenses"] == [], (endpoint, mode, execution.data)
    assert not LicenseItemPlan.objects.filter(license=_license_obj).exists()
    rule.refresh_from_db()
    untouched.refresh_from_db()
    assert rule.is_active is False
    assert untouched.is_active is True
    assert untouched.expression == {
        "field": "HSN", "comparator": "CONTAINS", "value": "3502",
    }


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
