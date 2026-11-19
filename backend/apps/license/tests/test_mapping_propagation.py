"""Part 15 — mapping changes drive Item Pivot regeneration and automatic re-planning (owner decision 2026-11-19).

The planning engine is isolated exactly like the canonical replan suite (``test_replan_requests``): the real
``planning.replan_license`` task body runs, ``plan_sion`` is patched to REPLACE the licence's generated lines.
The engine's own SION / E126 / E132 rules are covered by the planner and veg-oil suites.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseItemPlan, LicenseReplanRequest, MappingChange
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.item_pivot_intelligence import build_intelligence
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.services.product_intelligence import propagation
from apps.license.services.product_matching import decide, matching_groups, suggest
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


class PropagationTests(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.foil, _ = ItemNameModel.objects.get_or_create(name="ALUMINIUM FOIL")
        self.foil.sion_norm_class, self.foil.is_active = self.sion, True
        self.foil.save()
        self.foil.norms.add(self.sion)
        a, b = self.licences
        self.item(a, 9, "76071994", "Aluminium foil (existing)", "1", names=[self.foil])
        self.alu = self.item(a, 1, "76071991", "Alu Foil", "100")
        self.sugar_b = self.item(b, 2, "17019990", "Sugar", "50", names=[self.sugar])
        self.alu.items.clear()
        self.old_line = LicenseItemPlan.objects.create(license=a, import_item=self.alu, item_name=self.milk, planned_quantity=Decimal("40"), planned_cif_fc=Decimal("80"))
        self.untouched = LicenseItemPlan.objects.create(license=b, import_item=self.sugar_b, item_name=self.sugar, planned_quantity=Decimal("10"), planned_cif_fc=Decimal("20"))
        self.user = get_user_model().objects.create_user(username="prop-manager")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
        # Start from a "published" state: no pending re-plans from fixture setup.
        LicenseReplanRequest.objects.all().update(status=LicenseReplanRequest.STATUS_SUCCEEDED)
        for lic in LicenseDetailsModel.objects.all():
            LicenseDetailsModel.objects.filter(pk=lic.pk).update(planning_applied_revision=lic.planning_source_revision)

    def report(self):
        return build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1", include_norm_links=True))

    def approve_alu(self):
        rows = [s for s in suggest(matching_groups(self.report())) if s["description"] == "Alu Foil"]
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), self.captureOnCommitCallbacks(execute=True):
            decide(suggestions=rows, decision="APPROVED", user=self.user)
        return MappingChange.objects.get(kind=MappingChange.MATCH_DECISION)

    def run_replans(self, *, fail=False):
        """Execute the real replan task body; the engine REPLACEs the licence's generated line (foil 30 qty)."""
        from apps.license.tasks import replan_license_task

        def plan_sion(*args, **kwargs):
            lic_id = self.licences[0].pk
            LicenseItemPlan.objects.filter(license_id=lic_id).delete()  # the engine's REPLACE semantics
            LicenseItemPlan.objects.create(license_id=lic_id, import_item=self.alu, item_name=self.foil, planned_quantity=Decimal("30"), planned_cif_fc=Decimal("60"))
            return {"write_results": [{"license_id": lic_id}], "rules_executed": [1]}

        for req in LicenseReplanRequest.objects.filter(status__in=[LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED]):
            LicenseReplanRequest.objects.filter(pk=req.pk).update(status=LicenseReplanRequest.STATUS_QUEUED)
            resolve = {"side_effect": RuntimeError("SION rule failed")} if fail else {"return_value": (None, [self.sion.pk])}
            with patch("apps.license.views.sion_planning_rule.SionPlanningRuleViewSet._resolve_sions_for_license", **resolve), \
                    patch("apps.license.services.sion_rule_engine.SionRulePlanningService.plan_sion", side_effect=plan_sion):
                replan_license_task.run(req.pk)

    # 1 / 4 / 18 ------------------------------------------------------------------------------------
    def test_approval_versions_the_change_archives_plans_and_marks_only_affected_licences_stale(self):
        change = self.approve_alu()
        a, b = self.licences
        assert change.license_ids == [a.pk]  # only the licence owning the re-mapped records
        archived = change.before["licences"][str(a.pk)]["plan_lines"]
        assert [line["id"] for line in archived] == [self.old_line.pk] and archived[0]["item_name"] == "PIVOT MILK"
        data = self.report()
        rows = {r["license_id"]: r for r in data["licences"]}
        assert rows[a.pk]["planning_stale"] and not rows[b.pk]["planning_stale"]  # stale planning is never shown as current
        assert data["overview"]["planning_stale_licence_count"] == 1
        assert any(p["item_name_id"] == self.foil.pk and p["source_record_count"] == 2 for p in data["products"])  # Item Pivot regenerated
        assert propagation.refresh(change).status == MappingChange.PROPAGATING
        assert LicenseReplanRequest.objects.filter(license=a, status=LicenseReplanRequest.STATUS_PENDING).exists()

    # 5 / 6 / 7 / 8 / 13 / 14 / 15 -------------------------------------------------------------------
    def test_replan_publishes_new_plan_supersedes_old_and_keeps_actuals(self):
        change = self.approve_alu()
        a, b = self.licences
        actual_before = (LBC.calculate_debit_for_licenses([a.pk]), LBC.calculate_allotment_for_licenses([a.pk]), LBC.calculate_financial_balance_for_licenses([a.pk]))
        self.run_replans()
        change = propagation.refresh(change)
        assert change.status == MappingChange.PUBLISHED and change.completed_on
        report = propagation.impact(change)
        lic = report["licences"][0]
        items = {i["item"]: i for i in lic["items"]}
        assert items["PIVOT MILK"]["before_qty"] == "40.000" and items["PIVOT MILK"]["after_qty"] == "0"  # superseded (archived, inactive)
        assert items["ALUMINIUM FOIL"]["after_qty"] == "30.000"  # new plan uses the new debit item
        assert lic["superseded_lines"] == 1 and lic["active_lines"] == 1 and not lic["stale"]
        assert not LicenseItemPlan.objects.filter(pk=self.old_line.pk).exists()  # no longer active utilisation …
        assert change.before["licences"][str(a.pk)]["plan_lines"][0]["planned_cif_fc"] == "80.00"  # … but preserved in the archive
        assert LicenseItemPlan.objects.filter(pk=self.untouched.pk).exists()  # unaffected licence's lines preserved
        for field in ("boe_cif", "allotment_cif", "available_cif"):
            assert lic["actual"][field]["before"] == lic["actual"][field]["after"]  # actual utilisation unchanged
        assert actual_before == (LBC.calculate_debit_for_licenses([a.pk]), LBC.calculate_allotment_for_licenses([a.pk]), LBC.calculate_financial_balance_for_licenses([a.pk]))
        assert report["totals"]["before_planned_cif"] == "80.00" and report["totals"]["after_planned_cif"] == "60.00"
        assert not report["provisional"]

    # 16 / 17 ---------------------------------------------------------------------------------------
    def test_failure_keeps_previous_results_flags_failed_and_retry_is_idempotent(self):
        change = self.approve_alu()
        self.run_replans(fail=True)
        change = propagation.refresh(change)
        assert change.status == MappingChange.FAILED and "SION rule failed" in change.error
        assert LicenseItemPlan.objects.filter(pk=self.old_line.pk).exists()  # previous valid plan still in place
        assert propagation.impact(change)["provisional"]
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), self.captureOnCommitCallbacks(execute=True):
            propagation.retry(change, user=self.user)
            propagation.retry(change, user=self.user)
        active = LicenseReplanRequest.objects.filter(license=self.licences[0], status__in=[LicenseReplanRequest.STATUS_PENDING, LicenseReplanRequest.STATUS_QUEUED])
        assert active.count() == 1  # retries coalesce — never duplicate plans
        self.run_replans()
        assert propagation.refresh(change).status == MappingChange.PUBLISHED
        assert LicenseItemPlan.objects.filter(license=self.licences[0]).count() == 1

    def test_coalesced_older_request_is_tracked_and_orphaned_stale_licences_are_requested(self):
        a = self.licences[0]
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), self.captureOnCommitCallbacks(execute=True):
            from apps.license.services.replan_requests import mark_license_replan_source_changed
            mark_license_replan_source_changed(license_id=a.pk, reason="earlier")  # a request already pending
        change = self.approve_alu()  # coalesced into the earlier request
        self.run_replans(fail=True)
        assert propagation.refresh(change).status == MappingChange.FAILED  # the older, coalesced request counts
        LicenseReplanRequest.objects.filter(license=a).delete()  # request purged while still stale
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), self.captureOnCommitCallbacks(execute=True):
            propagation.refresh(change)
        assert LicenseReplanRequest.objects.filter(license=a, reason="mapping_change_propagation").exists()

    # 3 ---------------------------------------------------------------------------------------------
    def test_multi_product_classification_affects_item_pivot_only(self):
        from apps.license.services.product_intelligence.multi_product import decide_products
        self.board = ItemNameModel.objects.create(name="PIVOT BOARD", sion_norm_class=self.sion, is_active=True)
        rec = self.item(self.licences[1], 7, "39201099", "Pivot Board / Pivot Sugar", "9")
        rec.items.clear()
        LicenseReplanRequest.objects.all().update(status=LicenseReplanRequest.STATUS_SUCCEEDED)
        row = next(s for s in suggest(matching_groups(self.report())) if s.get("segments"))
        before = LicenseReplanRequest.objects.count()
        decide_products(suggestion=row, selections=[{"index": 0, "item_id": self.board.pk}], user=self.user)
        change = MappingChange.objects.get(kind=MappingChange.MULTI_PRODUCT)
        assert change.status == MappingChange.NO_PLANNING_IMPACT and LicenseReplanRequest.objects.count() == before

    # BOE / allotment debit target ------------------------------------------------------------------
    def test_debit_target_change_is_versioned_and_replans_only_when_it_changes(self):
        allotment = AllotmentModel.objects.create(company=self.company, item_name="x", required_quantity=Decimal("10"))
        AllotmentItems.objects.create(allotment=allotment, item=self.sugar_b, qty=Decimal("5"), cif_fc=Decimal("10"), cif_inr=Decimal("1"))
        allotment = AllotmentModel.objects.get(pk=allotment.pk)
        assert not MappingChange.objects.filter(kind=MappingChange.ALLOTMENT_TARGET).exists()  # creation is not a mapping change
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), self.captureOnCommitCallbacks(execute=True):
            allotment.planning_target_item = self.sugar
            allotment.save()
            allotment.save()  # same target again → no second version
        changes = MappingChange.objects.filter(kind=MappingChange.ALLOTMENT_TARGET)
        assert changes.count() == 1 and changes[0].license_ids == [self.licences[1].pk]
        assert changes[0].detail == {"previous_target": None, "new_target": self.sugar.pk}
        assert LicenseReplanRequest.objects.filter(license=self.licences[1], reason="debit_target_changed").exists()

    def test_bulk_consolidation_is_a_mapping_change_that_replans(self):
        from apps.license.services.product_intelligence.consolidation import apply, preview
        rows = [r for r in preview(sion="PI1", target_id=self.foil.pk)["rows"] if r["selectable"]]
        with patch("apps.license.tasks.dispatch_replan_requests.delay"), self.captureOnCommitCallbacks(execute=True):
            result = apply(sion="PI1", target_id=self.foil.pk, keys=[r["key"] for r in rows], user=self.user, reason="test")
        change = MappingChange.objects.get(pk=result["mapping_change"])
        assert change.kind == MappingChange.CONSOLIDATION and change.license_ids == [self.licences[0].pk]
        assert LicenseReplanRequest.objects.filter(license=self.licences[0], status=LicenseReplanRequest.STATUS_PENDING).exists()

    def test_api_lists_reports_and_restricts_retry(self):
        from rest_framework.test import APIClient
        change = self.approve_alu()
        viewer = get_user_model().objects.create_user(username="prop-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(viewer)
        listing = client.get("/api/item-pivot/matching/mapping-changes/")
        assert listing.status_code == 200 and listing.json()["changes"][0]["version"] == change.pk and listing.json()["can_retry"] is False
        detail = client.get(f"/api/item-pivot/matching/mapping-changes/{change.pk}/")
        assert detail.status_code == 200 and detail.json()["provisional"] is True
        assert client.post(f"/api/item-pivot/matching/mapping-changes/{change.pk}/retry/").status_code == 403
        intel = client.get("/api/item-pivot/intelligence/", {"sion_norm": "PI1", "license_status": "all", "min_balance": "-1000000000"})
        assert intel.status_code == 200 and intel.json()["overview"]["mapping_propagation"]["propagating"] == 1
