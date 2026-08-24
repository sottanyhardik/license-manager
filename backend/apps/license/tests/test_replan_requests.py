from unittest.mock import patch

import pytest
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseReplanRequest
from apps.license.services.replan_requests import (
    mark_license_replan_source_changed,
    request_license_replan,
)
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


@pytest.mark.django_db
class TestLicenseReplanRequests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.license = LicenseDetailsModel.objects.create(license_number="ASYNC-REPLAN-1")
        self.client = APIClient()
        self.client.force_authenticate(user=self.make_superuser())

    @patch("apps.license.tasks.dispatch_replan_requests.delay")
    def test_request_is_durable_and_dispatched_only_after_commit(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            request = request_license_replan(license_id=self.license.pk, reason="boe_changed")

        request.refresh_from_db()
        assert request.status in (LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED)
        assert request.task_id == str(delay.return_value.id)
        delay.assert_called_once_with([request.pk])

    @patch("apps.license.tasks.dispatch_replan_requests.delay")
    def test_repeated_requests_coalesce_to_one_active_row(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            first = request_license_replan(license_id=self.license.pk, reason="boe_changed")
        with self.captureOnCommitCallbacks(execute=True):
            second = request_license_replan(license_id=self.license.pk, reason="allotment_changed")

        assert first.pk == second.pk
        assert LicenseReplanRequest.objects.filter(license=self.license).count() == 1
        delay.assert_called_once()

    def test_unique_constraint_fallback_leaves_calling_transaction_usable(self):
        """A raced active-request insert must not poison allocation's atomic block."""
        existing = LicenseReplanRequest.objects.create(
            license=self.license,
            reason="already-active",
            status=LicenseReplanRequest.STATUS_PENDING,
        )
        from apps.license.services.replan_requests import _coalesce_locked

        # Simulate the gap in which another producer commits the active row
        # after this worker's first lookup but before its insert.
        with transaction.atomic():
            with patch("django.db.models.query.QuerySet.first", return_value=None):
                resolved, created = _coalesce_locked(
                    license_obj=self.license,
                    reason="allotment_changed",
                    scope=LicenseReplanRequest.SCOPE_LICENSE,
                    sion_id=None,
                )
            assert resolved.pk == existing.pk
            assert created is False
            # This query is the regression assertion: it would raise
            # TransactionManagementError if IntegrityError were caught in the
            # same atomic block as the failed insert.
            assert LicenseReplanRequest.objects.filter(pk=existing.pk).exists()

    def test_worker_is_idempotent_after_success(self):
        request = LicenseReplanRequest.objects.create(
            license=self.license, reason="manual", status=LicenseReplanRequest.STATUS_SUCCEEDED,
        )
        from apps.license.tasks import run_license_replan

        result = run_license_replan.run(request.pk)
        assert result == {"status": "succeeded", "request_id": request.pk, "idempotent": True}

    @patch("apps.license.tasks.replan_license_task.run")
    def test_sion_batch_processes_requests_one_by_one_in_request_order(self, run):
        first = LicenseReplanRequest.objects.create(license=self.license, reason="manual")
        second_license = LicenseDetailsModel.objects.create(license_number="ASYNC-REPLAN-2")
        second = LicenseReplanRequest.objects.create(license=second_license, reason="manual")
        run.side_effect = [
            {"status": "succeeded", "request_id": first.pk},
            {"status": "succeeded", "request_id": second.pk},
        ]

        from apps.license.tasks import replan_sion_batch
        result = replan_sion_batch.run([first.pk, second.pk])

        assert result["processed"] == 2
        assert [call.args[0] for call in run.call_args_list] == [first.pk, second.pk]

    def test_status_endpoint_exposes_failed_worker_detail_and_retry_state(self):
        LicenseReplanRequest.objects.create(
            license=self.license,
            reason="manual",
            status=LicenseReplanRequest.STATUS_FAILED,
            last_error_code="INVALID_SION_RULE",
            last_error_message="A required SION mapping is missing.",
        )
        response = self.client.get(f"/api/licenses/{self.license.pk}/replan-status/")
        assert response.status_code == 200, response.data
        assert response.data["planning_state"] == "REPLAN_FAILED"
        assert response.data["replan_request"]["last_error_code"] == "INVALID_SION_RULE"
        assert response.data["replan_request"]["last_error_message"] == "A required SION mapping is missing."

    def test_status_endpoint_accepts_canonical_license_number_from_overview_route(self):
        self.license.license_number = "0311046297"
        self.license.save(update_fields=["license_number"])
        response = self.client.get("/api/licenses/0311046297/replan-status/")
        assert response.status_code == 200, response.data
        assert response.data["license_id"] == self.license.pk

    def test_worker_records_failure_instead_of_leaving_running(self):
        # Patch the imports at their source because the task imports lazily.
        request = LicenseReplanRequest.objects.create(
            license=self.license, reason="manual", status=LicenseReplanRequest.STATUS_QUEUED,
        )
        from apps.license.tasks import run_license_replan
        with patch("apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license", side_effect=RuntimeError("bad SION")):
            result = run_license_replan.run(request.pk)

        request.refresh_from_db()
        assert result["status"] == LicenseReplanRequest.STATUS_FAILED
        assert request.status == LicenseReplanRequest.STATUS_FAILED
        assert request.attempts == 1
        assert "bad SION" in request.last_error

    def test_license_api_reports_pending_then_current_revision_after_worker(self):
        """The request response is asynchronous; CURRENT is task-owned.

        This deliberately executes the Celery task body rather than asserting
        a final plan immediately after the source change.  The rule engine is
        isolated here because its detailed persistence contract is covered by
        the canonical planner suite; this verifies the durable boundary and
        API freshness contract end-to-end.
        """
        with patch("apps.license.tasks.dispatch_replan_requests.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                request = mark_license_replan_source_changed(
                    license_id=self.license.pk, reason="import_item_changed",
                )

        pending = self.client.get(f"/api/licenses/{self.license.pk}/")
        assert pending.status_code == 200, pending.data
        assert pending.data["planning_state"] == "REPLAN_PENDING"
        assert pending.data["planning_revision"] == {
            "source_revision": 1, "planned_revision": 0, "is_current": False,
        }
        request.refresh_from_db()
        assert request.status == LicenseReplanRequest.STATUS_PENDING
        assert request.task_id == str(delay.return_value.id)
        delay.assert_called_once_with([request.pk])

        from apps.license.tasks import replan_license_task
        LicenseReplanRequest.objects.filter(pk=request.pk).update(
            status=LicenseReplanRequest.STATUS_QUEUED,
        )
        with patch(
            "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
            return_value=(None, [101]),
        ), patch(
            "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
            return_value={"write_results": [{"license_id": self.license.pk}], "rules_executed": [101]},
        ):
            result = replan_license_task.run(request.pk)

        assert result["status"] == LicenseReplanRequest.STATUS_SUCCEEDED
        request.refresh_from_db()
        self.license.refresh_from_db()
        assert request.planned_revision == self.license.planning_source_revision == 1
        assert self.license.planning_applied_revision == 1

        current = self.client.get(f"/api/licenses/{self.license.pk}/")
        assert current.status_code == 200, current.data
        assert current.data["planning_state"] == "CURRENT"
        assert current.data["planning_revision"] == {
            "source_revision": 1, "planned_revision": 1, "is_current": True,
        }

    def test_import_item_update_queues_without_running_a_planner_inline(self):
        LicenseReplanRequest.objects.all().delete()
        with patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion") as planner:
            item = LicenseImportItemsModel.objects.create(license=self.license, serial_number=1)
            item.description = "Changed input description"
            item.save(update_fields=["description"])

        assert planner.call_count == 0
        request = LicenseReplanRequest.objects.get(license=self.license)
        assert request.status == LicenseReplanRequest.STATUS_PENDING
        assert request.reason == "import_item_changed"

    @patch("apps.license.tasks.dispatch_replan_requests.delay")
    def test_auto_plan_endpoint_runs_inline_without_queueing(self, delay):
        """Interactive Auto Plan is committed inline; durable routes stay async."""
        with patch(
            "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
            return_value=(self.license, [101]),
        ), patch(
            "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
            return_value={"write_results": [{"license_id": self.license.pk}], "rules_executed": [101]},
        ) as planner:
            response = self.client.post(
                f"/api/licenses/{self.license.pk}/auto-plan/", {"force": True}, format="json",
            )

        assert response.status_code == 200, response.data
        assert response.data == {
            "license_id": self.license.pk,
            "license_number": self.license.license_number,
            "planning_state": "COMPLETED",
            "force": True,
            "write_results": 1,
            "rules_executed": [101],
            "message": "Licence planning has completed.",
        }
        planner.assert_called_once_with(101, license_ids=[self.license.pk], mode="ALL", force_plan=True)
        assert not LicenseReplanRequest.objects.filter(
            license=self.license, reason="manual_auto_plan",
        ).exists()
        delay.assert_not_called()

    @patch("apps.license.tasks.dispatch_replan_requests.delay")
    def test_plan_license_endpoint_queues_without_running_auto_plan_inline(self, delay):
        with patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion") as planner:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/sion-planning-rules/plan-license/",
                    {"license_id": self.license.pk, "mode": "ALL"},
                    format="json",
                )

        assert response.status_code == 202, response.data
        assert response.data["planning_state"] == "REPLAN_PENDING"
        durable_request = LicenseReplanRequest.objects.get(pk=response.data["replan_request_id"])
        assert durable_request.license_id == self.license.pk
        assert durable_request.reason == "manual_plan_license"
        planner.assert_not_called()
        delay.assert_called_once_with([durable_request.pk])

    @patch("apps.license.tasks.replan_sion_batch.delay")
    def test_plan_sion_endpoint_queues_each_explicit_license_without_inline_planning(self, delay):
        other = LicenseDetailsModel.objects.create(license_number="ASYNC-REPLAN-3")
        sion = SionNormClassModel.objects.create(
            head_norm=HeadSIONNormsModel.objects.create(name="Async replan"),
            norm_class="ASYNC-RP",
            is_active=True,
        )
        with patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion") as planner:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/sion-planning-rules/plan-sion/",
                    {"sion_id": sion.pk, "license_ids": [self.license.pk, other.pk], "mode": "ALL"},
                    format="json",
                )

        assert response.status_code == 202, response.data
        assert response.data["planning_state"] == "REPLAN_PENDING"
        assert len(response.data["replan_request_ids"]) == 2
        assert set(LicenseReplanRequest.objects.filter(pk__in=response.data["replan_request_ids"]).values_list("license_id", flat=True)) == {self.license.pk, other.pk}
        planner.assert_not_called()
        delay.assert_called_once_with(response.data["replan_request_ids"])

    def test_import_item_reassignment_queues_both_licenses(self):
        other = LicenseDetailsModel.objects.create(license_number="ASYNC-REPLAN-2")
        item = LicenseImportItemsModel.objects.create(license=self.license, serial_number=1)
        LicenseReplanRequest.objects.all().delete()

        item.license = other
        item.save(update_fields=["license"])

        assert set(LicenseReplanRequest.objects.values_list("license_id", flat=True)) == {self.license.pk, other.pk}

    def test_rolled_back_change_does_not_leave_a_replan_request(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with transaction.atomic():
                LicenseImportItemsModel.objects.create(license=self.license, serial_number=99)
                raise RuntimeError("rollback")
        assert not LicenseImportItemsModel.objects.filter(license=self.license, serial_number=99).exists()
        assert not LicenseReplanRequest.objects.filter(license=self.license).exists()

    @patch("apps.license.tasks.replan_license_task.apply_async")
    def test_recovery_task_is_bounded_and_redispatches_pending_rows(self, apply_async):
        pending = LicenseReplanRequest.objects.create(license=self.license, reason="manual")
        apply_async.return_value.id = "recovered-task"
        from apps.license.tasks import dispatch_pending_license_replans

        result = dispatch_pending_license_replans.run(limit=1)
        pending.refresh_from_db()
        assert result == {"dispatched": 1}
        assert pending.task_id == "recovered-task"
        apply_async.assert_called_once_with(args=[pending.pk], queue="celery")

    def test_source_mutation_coalesces_latest_revision_before_worker_starts(self):
        request = LicenseReplanRequest.objects.create(
            license=self.license, reason="manual", source_revision=0,
            status=LicenseReplanRequest.STATUS_QUEUED,
        )
        from apps.license.services.replan_requests import mark_license_replan_source_changed
        with self.captureOnCommitCallbacks(execute=True):
            newer = mark_license_replan_source_changed(license_id=self.license.pk, reason="source_changed")

        request.refresh_from_db()
        self.license.refresh_from_db()
        assert newer.pk == request.pk
        assert request.status in (LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED)
        assert self.license.planning_source_revision == 1
        assert request.source_revision == 1

    def test_source_mutation_during_worker_supersedes_stale_plan(self):
        """A plan calculated for revision 0 must never acknowledge revision 1."""
        request = LicenseReplanRequest.objects.create(
            license=self.license, reason="manual", source_revision=0,
            status=LicenseReplanRequest.STATUS_QUEUED,
        )

        def plan_then_mutate(*args, **kwargs):
            mark_license_replan_source_changed(
                license_id=self.license.pk, reason="source_changed",
            )
            return {"write_results": [], "rules_executed": []}

        from apps.license.tasks import replan_license_task
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), \
             patch("apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license", return_value=(None, [1])), \
             patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion", side_effect=plan_then_mutate):
            result = replan_license_task.run(request.pk)

        request.refresh_from_db()
        self.license.refresh_from_db()
        assert result["status"] == LicenseReplanRequest.STATUS_SUPERSEDED
        assert request.status == LicenseReplanRequest.STATUS_SUPERSEDED
        assert request.planned_revision is None
        assert self.license.planning_source_revision == 1
        assert self.license.planning_applied_revision == 0
        replacement = LicenseReplanRequest.objects.exclude(pk=request.pk).get(license=self.license)
        assert replacement.status == LicenseReplanRequest.STATUS_PENDING
        assert replacement.source_revision == 1

    def test_worker_replans_each_sion_for_a_multi_sion_license(self):
        request = LicenseReplanRequest.objects.create(
            license=self.license, reason="manual", status=LicenseReplanRequest.STATUS_QUEUED,
        )
        from apps.license.tasks import replan_license_task
        with patch(
            "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
            return_value=(self.license, [11, 22]),
        ), patch(
            "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
            return_value={"write_results": [], "rules_executed": []},
        ) as planner:
            result = replan_license_task.run(request.pk)

        assert result["status"] == LicenseReplanRequest.STATUS_SUCCEEDED
        assert [call.args[0] for call in planner.call_args_list] == [11, 22]
        assert all(call.kwargs["mode"] == "ALL" and call.kwargs["force_plan"] is True for call in planner.call_args_list)

    def test_sion_scoped_worker_does_not_expand_to_other_license_sions(self):
        """A plan-sion batch must retain its selected norm in the worker."""
        request = LicenseReplanRequest.objects.create(
            license=self.license,
            reason="manual_plan_sion",
            scope=LicenseReplanRequest.SCOPE_SION,
            sion_id=17,
            source_model="sion_planning_rule.plan_sion",
            source_pk="17",
            status=LicenseReplanRequest.STATUS_QUEUED,
        )

        from apps.license.tasks import replan_license_task
        with patch(
            "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
            side_effect=AssertionError("SION-scoped requests must not be expanded"),
        ), patch(
            "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
            return_value={"write_results": [], "rules_executed": []},
        ) as planner:
            result = replan_license_task.run(request.pk)

        assert result["status"] == LicenseReplanRequest.STATUS_SUCCEEDED
        planner.assert_called_once_with(17, license_ids=[self.license.pk], mode="ALL", force_plan=True)

    def test_license_scope_continues_after_one_norm_fails(self):
        request = LicenseReplanRequest.objects.create(
            license=self.license, reason="manual", status=LicenseReplanRequest.STATUS_QUEUED,
            scope=LicenseReplanRequest.SCOPE_LICENSE,
        )
        from apps.license.tasks import replan_license_task
        with patch(
            "apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license",
            return_value=(self.license, [11, 22]),
        ), patch(
            "apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion",
            side_effect=[RuntimeError("invalid norm"), {"write_results": [], "rules_executed": []}],
        ) as planner:
            result = replan_license_task.run(request.pk)

        assert result["status"] == LicenseReplanRequest.STATUS_SUCCEEDED
        assert [call.args[0] for call in planner.call_args_list] == [11, 22]
        assert result["failures"] == [{"sion_id": 11, "error": "invalid norm", "error_code": "RuntimeError"}]

    def test_allotment_and_boe_changes_enqueue_without_inline_planning(self):
        from decimal import Decimal
        from apps.allotment.models import AllotmentItems, AllotmentModel
        from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
        from apps.core.models import CompanyModel

        item = LicenseImportItemsModel.objects.create(license=self.license, serial_number=1)
        LicenseReplanRequest.objects.all().delete()
        with patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion") as planner:
            allotment = AllotmentModel.objects.create(company=CompanyModel.objects.create(name="Async Replan Co"))
            AllotmentItems.objects.create(
                allotment=allotment, item=item, qty=Decimal("1"), cif_fc=Decimal("1"), cif_inr=Decimal("1"),
            )
            assert LicenseReplanRequest.objects.filter(license=self.license).exists()
            LicenseReplanRequest.objects.all().delete()
            RowDetails.objects.create(
                bill_of_entry=BillOfEntryModel.objects.create(), sr_number=item,
                qty=Decimal("1"), cif_fc=Decimal("1"), cif_inr=Decimal("1"),
            )

        assert planner.call_count == 0
        assert LicenseReplanRequest.objects.filter(license=self.license).exists()
