"""
Tests for planning bulk operations, batch status/retry, dashboard KPIs and rule
version history.

Defects covered:
1. Coalescing a second request into a pending one overwrote its scope, so a
   pending SION-A request was silently dropped when SION-B was requested.
2. Bulk batch results had no honest aggregate: a batch with failed records
   could not be distinguished from success, and failed records could not be
   retried as a batch.
3. The workbench had no operational KPIs (rule counts, validation errors, job
   state), and rules had no traceable version chain: API-created rules never
   received a stable key, so history broke on the first edit.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseReplanRequest,
    SionPlanningPercentageRow,
    SionPlanningRule,
)
from apps.license.services.planning_operations import (
    failed_request_licences,
    planning_dashboard,
    replan_batch_status,
    rule_version_chain,
)
from apps.license.services.replan_requests import request_license_replan

pytestmark = pytest.mark.django_db
User = get_user_model()
RULES_URL = "/api/sion-planning-rules/"


@pytest.fixture
def operator(db):
    user = User.objects.create_user(username="planning-operator", email="planning-operator@example.com", password="x")
    user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
    return user


@pytest.fixture
def client(operator):
    api = APIClient()
    api.force_authenticate(operator)
    return api


@pytest.fixture
def world(db):
    from apps.core.models import CompanyModel as Company

    company = Company.objects.create(iec="PLANOPS001", name="Planning Ops Co")
    head = HeadSIONNormsModel.objects.create(name="Planning Ops Head")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E126", is_active=True, description="E126 ops")
    other = SionNormClassModel.objects.create(head_norm=head, norm_class="E132", is_active=True, description="E132 ops")
    pko = ItemNameModel.objects.create(name="PKO-OPS", sion_norm_class=sion, is_active=True)
    olive = ItemNameModel.objects.create(name="OLIVE-OPS", sion_norm_class=sion, is_active=True)
    licenses = []
    for index in range(3):
        lic = LicenseDetailsModel.objects.create(
            license_number=f"OPS-LIC-{index}",
            license_date=date.today() - timedelta(days=30),
            license_expiry_date=date.today() + timedelta(days=90),
            exporter=company,
        )
        # Creating a licence fires source-change signals that queue their own
        # replan requests; this file controls the ledger explicitly.
        LicenseReplanRequest.objects.filter(license=lic).delete()
        licenses.append(lic)
    return {"company": company, "sion": sion, "other": other, "pko": pko, "olive": olive, "licenses": licenses}


def _request(license_obj, status, *, scope=LicenseReplanRequest.SCOPE_LICENSE, sion_id=None, result=None, error_code="", error_message="", attempts=1):
    now = timezone.now()
    return LicenseReplanRequest.objects.create(
        license=license_obj, reason="test", scope=scope, sion_id=sion_id, status=status,
        result=result or {}, last_error_code=error_code, last_error_message=error_message,
        attempts=attempts, started_at=now, completed_at=now if status in (
            LicenseReplanRequest.STATUS_SUCCEEDED, LicenseReplanRequest.STATUS_FAILED) else None,
    )


class TestCoalescingNeverDropsWork:
    def test_second_sion_request_widens_pending_sion_request_to_licence_scope(self, world):
        lic = world["licenses"][0]
        pending = _request(lic, LicenseReplanRequest.STATUS_PENDING, scope=LicenseReplanRequest.SCOPE_SION, sion_id=world["sion"].pk)

        merged = request_license_replan(
            license_id=lic.pk, reason="second", scope=LicenseReplanRequest.SCOPE_SION,
            sion_id=world["other"].pk, dispatch=False,
        )

        assert merged.pk == pending.pk
        merged.refresh_from_db()
        assert merged.scope == LicenseReplanRequest.SCOPE_LICENSE
        assert merged.sion_id is None
        assert merged.trigger_count == 2

    def test_same_sion_request_keeps_sion_scope(self, world):
        lic = world["licenses"][0]
        _request(lic, LicenseReplanRequest.STATUS_QUEUED, scope=LicenseReplanRequest.SCOPE_SION, sion_id=world["sion"].pk)

        merged = request_license_replan(
            license_id=lic.pk, reason="again", scope=LicenseReplanRequest.SCOPE_SION,
            sion_id=world["sion"].pk, dispatch=False,
        )

        assert merged.scope == LicenseReplanRequest.SCOPE_SION
        assert merged.sion_id == world["sion"].pk

    def test_licence_scope_request_is_never_narrowed_by_a_sion_request(self, world):
        lic = world["licenses"][0]
        _request(lic, LicenseReplanRequest.STATUS_PENDING, scope=LicenseReplanRequest.SCOPE_LICENSE)

        merged = request_license_replan(
            license_id=lic.pk, reason="sion", scope=LicenseReplanRequest.SCOPE_SION,
            sion_id=world["sion"].pk, dispatch=False,
        )

        assert merged.scope == LicenseReplanRequest.SCOPE_LICENSE
        assert merged.sion_id is None

    def test_batch_identity_is_recorded_on_new_request(self, world, operator):
        lic = world["licenses"][0]
        created = request_license_replan(
            license_id=lic.pk, reason="batch", scope=LicenseReplanRequest.SCOPE_SION,
            sion_id=world["sion"].pk, dispatch=False, batch_id="batch-1", initiated_by=operator,
        )

        assert created.batch_id == "batch-1"
        assert created.initiated_by_id == operator.pk


class TestBatchStatusIsHonest:
    def test_mixed_batch_is_partial_failure_never_success(self, world):
        a, b, c = world["licenses"]
        rows = [
            _request(a, LicenseReplanRequest.STATUS_SUCCEEDED, result={"failures": []}),
            _request(b, LicenseReplanRequest.STATUS_FAILED, error_code="OperationalError", error_message="deadlock"),
            _request(c, LicenseReplanRequest.STATUS_SUCCEEDED, result={"failures": [
                {"sion_id": 7, "error": "no rule", "error_code": "PlanningError"},
            ]}),
        ]

        status = replan_batch_status([row.pk for row in rows])

        assert status["state"] == "PARTIAL_FAILURE"
        assert status["succeeded"] == 1
        assert status["failed"] == 2
        assert status["partial_failures"] == 1
        assert status["completed_at"] is not None
        codes = sorted(error["error_code"] for error in status["errors"])
        assert codes == ["OperationalError", "PlanningError"]
        assert {error["license_number"] for error in status["errors"]} == {b.license_number, c.license_number}

    def test_all_failed_batch_is_failed(self, world):
        rows = [_request(lic, LicenseReplanRequest.STATUS_FAILED) for lic in world["licenses"][:2]]

        status = replan_batch_status([row.pk for row in rows])

        assert status["state"] == "FAILED"
        assert status["succeeded"] == 0

    def test_clean_batch_succeeds(self, world):
        rows = [_request(lic, LicenseReplanRequest.STATUS_SUCCEEDED) for lic in world["licenses"]]

        status = replan_batch_status([row.pk for row in rows])

        assert status["state"] == "SUCCEEDED"
        assert status["failed"] == 0 and status["succeeded"] == 3

    def test_active_rows_mean_running_even_with_failures(self, world):
        a, b, _c = world["licenses"]
        running = _request(a, LicenseReplanRequest.STATUS_RUNNING)
        failed = _request(b, LicenseReplanRequest.STATUS_FAILED)

        status = replan_batch_status([running.pk, failed.pk])

        assert status["state"] == "RUNNING"
        assert status["completed_at"] is None

    def test_unknown_request_id_is_never_reported_as_success(self, world):
        row = _request(world["licenses"][0], LicenseReplanRequest.STATUS_SUCCEEDED)

        status = replan_batch_status([row.pk, 999999])

        assert status["state"] != "SUCCEEDED"
        assert status["unknown_request_ids"] == [999999]
        assert status["failed"] == 1

    def test_superseded_rows_are_skipped_not_failed(self, world):
        a, b = world["licenses"][:2]
        ok = _request(a, LicenseReplanRequest.STATUS_SUCCEEDED)
        skipped = _request(b, LicenseReplanRequest.STATUS_SUPERSEDED)

        status = replan_batch_status([ok.pk, skipped.pk])

        assert status["skipped"] == 1
        assert status["failed"] == 0
        assert status["state"] == "SUCCEEDED"


class TestBatchRetry:
    def test_retry_requeues_only_failed_licences_as_one_new_batch(self, client, world):
        a, b, c = world["licenses"]
        ok = _request(a, LicenseReplanRequest.STATUS_SUCCEEDED)
        failed = _request(b, LicenseReplanRequest.STATUS_FAILED, scope=LicenseReplanRequest.SCOPE_SION, sion_id=world["sion"].pk)
        partial = _request(c, LicenseReplanRequest.STATUS_SUCCEEDED, result={"failures": [{"sion_id": 1, "error": "x", "error_code": "E"}]})

        response = client.post(
            f"{RULES_URL}plan-batch-retry/",
            {"request_ids": [ok.pk, failed.pk, partial.pk]},
            format="json",
        )

        assert response.status_code == 202, response.data
        retry_ids = response.data["retry_request_ids"]
        assert len(retry_ids) == 2
        assert ok.pk not in retry_ids
        new_rows = LicenseReplanRequest.objects.filter(pk__in=retry_ids)
        assert set(new_rows.values_list("batch_id", flat=True)) == {response.data["batch_id"]}
        assert {row.license_id for row in new_rows} == {b.pk, c.pk}
        assert new_rows.get(license_id=b.pk).scope == LicenseReplanRequest.SCOPE_SION
        assert [item["request_id"] for item in response.data["skipped"]] == [ok.pk]

    def test_retry_is_idempotent_while_the_retry_is_active(self, client, world):
        b = world["licenses"][1]
        failed = _request(b, LicenseReplanRequest.STATUS_FAILED)

        first = client.post(f"{RULES_URL}plan-batch-retry/", {"request_ids": [failed.pk]}, format="json")
        second = client.post(f"{RULES_URL}plan-batch-retry/", {"request_ids": [failed.pk]}, format="json")

        assert first.data["retry_request_ids"] == second.data["retry_request_ids"]
        assert LicenseReplanRequest.objects.filter(license=b, status__in=["pending", "queued", "running", "retry_pending"]).count() == 1

    def test_retry_with_nothing_failed_queues_nothing(self, client, world):
        ok = _request(world["licenses"][0], LicenseReplanRequest.STATUS_SUCCEEDED)

        response = client.post(f"{RULES_URL}plan-batch-retry/", {"request_ids": [ok.pk]}, format="json")

        assert response.status_code == 200
        assert response.data["planning_state"] == "NOTHING_TO_RETRY"
        assert response.data["retry_request_ids"] == []

    def test_status_endpoint_rejects_malformed_ids(self, client):
        response = client.get(f"{RULES_URL}plan-batch-status/", {"request_ids": "abc"})

        assert response.status_code == 400
        assert response.data["code"] == "INVALID_REQUEST_IDS"

    def test_status_endpoint_reports_batch(self, client, world):
        row = _request(world["licenses"][0], LicenseReplanRequest.STATUS_SUCCEEDED)

        response = client.get(f"{RULES_URL}plan-batch-status/", {"request_ids": str(row.pk)})

        assert response.status_code == 200
        assert response.data["state"] == "SUCCEEDED"


def _rule(world, name, **overrides):
    values = dict(
        sion=world["sion"], name=name, unit="kg", max_unit_price=Decimal("10.00"),
        priority=1, strategy="STANDARD", import_item=world["pko"],
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "1507"}, is_active=True,
    )
    values.update(overrides)
    return SionPlanningRule.objects.create(**values)


class TestDashboard:
    def test_kpis_count_rules_validation_and_jobs(self, world):
        _rule(world, "Valid rule")
        _rule(world, "Inactive rule", is_active=False, priority=2)
        # Active split rule whose percentages total 60: a canonical validation error.
        split = _rule(world, "Broken split", strategy="SPLIT_BY_PERCENT", import_item=None, priority=3)
        SionPlanningPercentageRow.objects.create(
            rule=split, import_item=world["pko"], percentage=Decimal("60.00"),
            unit_price=Decimal("2.00"), priority=1,
        )
        # Empty expression matches everything: a warning, not an error.
        _rule(world, "Catch all", expression={"operator": "AND", "conditions": []}, priority=4)
        _request(world["licenses"][0], LicenseReplanRequest.STATUS_FAILED)
        _request(world["licenses"][1], LicenseReplanRequest.STATUS_PENDING)

        data = planning_dashboard(validator=lambda rule: _validate(rule))

        totals = data["totals"]
        assert totals["norms"] == 2
        assert totals["active_rules"] == 3
        assert totals["inactive_rules"] == 1
        assert totals["draft_rules"] is None
        assert totals["validation_errors"] >= 1
        assert totals["warnings"] == 1
        assert data["jobs"]["failed"] == 1
        assert data["jobs"]["pending"] == 1
        assert data["last_rule_change"]["modified_on"] is not None
        by_norm = {entry["norm_class"]: entry for entry in data["norms"]}
        assert by_norm["E126"]["active_rules"] == 3
        assert by_norm["E132"]["active_rules"] == 0


def _validate(rule):
    from apps.license.views.sion_planning_rule import SionPlanningRuleViewSet
    return SionPlanningRuleViewSet._rule_validation_errors(rule)


class TestRuleVersionHistory:
    def test_api_created_rule_gets_stable_key_and_history_tracks_renames(self, client, world):
        create = client.post(RULES_URL, {
            "sion": world["sion"].pk, "name": "Pko rule", "strategy": "STANDARD",
            "import_item": world["pko"].pk, "unit": "kg", "max_unit_price": "10.00",
            "expression": {"field": "HSN", "comparator": "CONTAINS", "value": "1507"},
            "is_active": True,
        }, format="json")
        assert create.status_code == 201, create.data
        rule = SionPlanningRule.objects.get(pk=create.data["id"])
        assert rule.stable_key

        patch = client.patch(f"{RULES_URL}{rule.pk}/", {"name": "Pko rule renamed"}, format="json")
        assert patch.status_code == 200, patch.data

        history = client.get(f"{RULES_URL}{rule.pk}/versions/")
        assert history.status_code == 200
        assert history.data["history_scope"] == "STABLE_KEY"
        versions = history.data["versions"]
        assert [v["version"] for v in versions] == [1, 2]
        assert versions[0]["changed_fields"] == []
        assert versions[1]["changed_fields"] == ["name"]
        assert versions[0]["is_active"] is False and versions[1]["is_active"] is True

    def test_child_row_edits_are_reported_as_changed_fields(self, world):
        rule = _rule(world, "Split", strategy="SPLIT_BY_PERCENT", import_item=None)
        SionPlanningPercentageRow.objects.create(rule=rule, import_item=world["pko"], percentage=Decimal("100.00"), unit_price=Decimal("1.00"), priority=1)
        # A second version whose only difference is the percentage child row.
        rule.stable_key = "chain-1"
        rule.save(update_fields=["stable_key"])
        newer = SionPlanningRule.objects.create(
            sion=world["sion"], name="Split", strategy="SPLIT_BY_PERCENT", unit="kg",
            max_unit_price=Decimal("10.00"), priority=2, version=2, stable_key="chain-1",
            expression={"operator": "AND", "conditions": []}, is_active=True,
        )
        SionPlanningPercentageRow.objects.create(rule=newer, import_item=world["pko"], percentage=Decimal("100.00"), unit_price=Decimal("2.00"), priority=1)

        chain = rule_version_chain(rule)

        assert [v["version"] for v in chain] == [1, 2]
        assert "percentage_rows" in chain[1]["changed_fields"]

    def test_legacy_rule_without_stable_key_is_chained_by_name(self, world):
        legacy = _rule(world, "Legacy", stable_key=None)

        history = rule_version_chain(legacy)

        assert len(history) == 1
        assert history[0]["changed_fields"] == []


def test_failed_request_licences_deduplicates_and_skips_active(world):
    lic, other = world["licenses"][0], world["licenses"][1]
    first = _request(lic, LicenseReplanRequest.STATUS_FAILED)
    second_failure_same_licence = _request(lic, LicenseReplanRequest.STATUS_FAILED)
    running = _request(other, LicenseReplanRequest.STATUS_RUNNING)

    plan = failed_request_licences([first.pk, second_failure_same_licence.pk, running.pk])

    assert [item["request_id"] for item in plan["retry"]] == [first.pk]
    reasons = {item["request_id"]: item["reason"] for item in plan["skipped"]}
    assert reasons[second_failure_same_licence.pk] == "duplicate licence in this retry"
    assert reasons[running.pk] == "already in progress"


class TestOperationalEndpoints:
    def test_dashboard_endpoint_returns_canonical_shape(self, client, world):
        _rule(world, "Endpoint rule")

        response = client.get(f"{RULES_URL}dashboard/")

        assert response.status_code == 200, response.data
        assert set(response.data) == {"totals", "last_rule_change", "jobs", "norms"}
        assert response.data["totals"]["active_rules"] == 1
        assert response.data["totals"]["draft_rules"] is None

    def test_versions_endpoint_is_404_for_unknown_rule(self, client):
        response = client.get(f"{RULES_URL}999999/versions/")

        assert response.status_code == 404
