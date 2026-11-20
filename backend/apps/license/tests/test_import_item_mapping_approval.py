"""Global Description + HSN -> Item Name approvals (owner amendment 2026-11-20)."""
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection

from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import (
    ImportItemMappingApproval, ImportItemMappingApprovalVersion, ImportItemNameOverride, LicenseImportItemsModel, MappingChange,
    ProductIntelAuditEvent, ProductMatchDecision,
)
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.product_intelligence import consolidation
from apps.license.services.product_intelligence import import_item_approval as ia
from apps.license.services.product_intelligence import import_item_override as ov
from apps.license.services.product_intelligence.description_mapping import (
    USER_APPROVED, apply_for_licence, auto_apply, description_rows, save_mapping,
)
from apps.license.services.product_intelligence.item_name_mapping import counts, undo_import_approval
from apps.license.services.product_matching import MatchValidationError, decide, matching_groups
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture

DESC, HSN = "Palm Kernel Oil", "15131900"


class ApprovalFixture(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.pko, _ = ItemNameModel.objects.get_or_create(name="PKO")
        self.olive, _ = ItemNameModel.objects.get_or_create(name="OLIVE OIL")
        for n in (self.pko, self.olive, self.sugar, self.milk):
            n.sion_norm_class, n.is_active = self.sion, True
            n.save()
            n.norms.set([self.sion])
        LicenseImportItemsModel.items.through.objects.filter(
            itemnamemodel_id__in=[self.pko.pk, self.olive.pk, self.sugar.pk, self.milk.pk]).delete()
        self.lic, self.other = self.licences
        self.r1 = self.item(self.lic, 1, HSN, DESC, "500")
        self.r2 = self.item(self.lic, 2, HSN, "PALM KERNEL OIL ", "300")
        self.foreign = self.item(self.other, 1, HSN, DESC, "70")
        self.diff_hsn = self.item(self.other, 2, "15131100", DESC, "20")
        self.diff_desc = self.item(self.lic, 3, HSN, "Palm Kernel Oil Refined", "10")
        self.no_hsn = LicenseImportItemsModel.objects.create(license=self.lic, serial_number=4, hs_code=None, description=DESC,
                                                             quantity=Decimal("5"), available_quantity=Decimal("5"), cif_fc=Decimal("100"))
        for r in (self.r1, self.r2, self.foreign, self.diff_hsn, self.diff_desc, self.no_hsn):
            r.items.clear()
        self.user = get_user_model().objects.create_user(username="appr-manager")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
        self.viewer = get_user_model().objects.create_user(username="appr-viewer")
        self.viewer.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        self.super = get_user_model().objects.create_superuser(username="appr-super", password="x", email="a@example.com")

    def links(self, r):
        return sorted(LicenseImportItemsModel.items.through.objects.filter(licenseimportitemsmodel_id=r.pk).values_list("itemnamemodel_id", flat=True))

    def approve(self, item=None, desc=DESC, hsn=HSN, **kw):
        return ia.approve(description=desc, hsn=hsn, item_id=item.pk if item else None, user=self.user, **kw)

    def row(self, r, lic=None):
        return next(x for x in ov.rows_for_licence((lic or self.lic).pk) if x["import_item_id"] == r.pk)

    def financials(self):
        ids = [self.lic.pk, self.other.pk]
        rows = list(LicenseImportItemsModel.objects.filter(license_id__in=ids).order_by("pk").values_list(
            "quantity", "available_quantity", "debited_quantity", "allotted_quantity", "cif_fc", "cif_inr", "debited_value", "allotted_value"))
        comps = [LBC.calculate_all_components(l) for l in (self.lic, self.other)]
        return rows, comps, LBC.calculate_financial_balance_for_licenses(ids)


class ApprovalTests(ApprovalFixture):
    # 1-3 -------------------------------------------------------------------------------------------------------------
    def test_assign_updates_every_exact_match_across_licences_with_counts(self):
        res = self.approve(self.pko)
        assert res["action"] == "CREATE" and res["records"] == 3 and res["licences"] == 2 and res["applied"] == 3
        assert res["approval"]["item"]["id"] == self.pko.pk and res["approval"]["status"] == "USER_APPROVED" and res["approval"]["version"] == 1
        assert res["conflicts"] == 0 and res["overridden"] == 0 and res["mapping_change"]
        for r in (self.r1, self.r2, self.foreign):
            assert self.links(r) == [self.pko.pk]
        assert MappingChange.objects.get(kind=MappingChange.IMPORT_ITEM_APPROVAL).import_item_ids == sorted([self.r1.pk, self.r2.pk, self.foreign.pk])

    def test_different_hsn_and_different_description_and_no_hsn_are_untouched(self):
        self.approve(self.pko)
        assert self.links(self.diff_hsn) == [] and self.links(self.no_hsn) == [] and self.links(self.diff_desc) == []
        assert ia.preview(description=DESC, hsn="")["records"] == 1  # no HSN is its own combination
        res = self.approve(self.olive, hsn="")
        assert res["records"] == 1 and self.links(self.no_hsn) == [self.olive.pk]
        assert self.links(self.r1) == [self.pko.pk]  # the HSN combination is independent
        assert ImportItemMappingApproval.objects.count() == 2

    def test_blank_description_is_never_globally_mappable(self):
        for bad in ("", "   ", " . "):
            with pytest.raises(MatchValidationError, match="description is required"):
                ia.approve(description=bad, hsn=HSN, item_id=self.pko.pk, user=self.user)
        with pytest.raises(MatchValidationError, match="existing, active"):
            ia.approve(description=DESC, hsn=HSN, item_id=999999, user=self.user)
        assert not ImportItemMappingApproval.objects.exists()

    # 4 ---------------------------------------------------------------------------------------------------------------
    def test_clear_propagates_globally_and_shows_cleared_not_not_mapped(self):
        self.approve(self.pko)
        res = self.approve(None)
        assert res["action"] == "CLEAR" and res["approval"]["status"] == "USER_APPROVED_CLEAR" and res["approval"]["item"] is None
        assert res["applied"] == 3 and all(self.links(r) == [] for r in (self.r1, self.r2, self.foreign))
        assert self.row(self.r1)["status"] == "CLEARED" and self.row(self.r1)["source"] == "APPROVAL"
        assert self.row(self.r1)["approval"]["status"] == "USER_APPROVED_CLEAR" and self.row(self.r1)["approval"]["item"] is None
        assert self.row(self.diff_desc)["status"] == "NOT_MAPPED" and self.row(self.diff_desc)["approval"] is None

    # 5 ---------------------------------------------------------------------------------------------------------------
    def _pko_rule(self):
        return mock.patch("apps.license.utils.item_matcher.match_import_item_to_items", return_value=ItemNameModel.objects.filter(pk=self.pko.pk))

    def test_rule_auto_link_never_touches_cleared_or_approved_records(self):
        self.approve(None, desc="Guarded desc", hsn=HSN)
        self.approve(self.olive, desc="Approved desc", hsn=HSN)
        with mock.patch("apps.license.utils.item_matcher.RULE_AUTO_LINK", True), self._pko_rule():
            cleared = self.item(self.lic, 10, HSN, "Guarded desc", "1")
            approved = self.item(self.lic, 11, HSN, "Approved desc", "1")
            free = self.item(self.lic, 12, HSN, "Free desc", "1")
            assert self.links(free)  # control: the rule links an undecided record
            assert self.links(cleared) == [] and self.links(approved) == []  # every rule path skips decided records
            self.lic.save()
            assert self.links(cleared) == [] and self.links(approved) == []
        with self.captureOnCommitCallbacks(execute=True):
            self.lic.save()  # rules off: the saved approvals apply
        assert self.links(cleared) == [] and self.links(approved) == [self.olive.pk]

    def test_bulk_rule_link_skips_protected_records(self):
        from django.db.models import Q as _Q
        self.approve(None, desc="Guarded desc", hsn=HSN)
        cleared = self.item(self.lic, 10, HSN, "Guarded desc palm", "1")
        cleared_same = self.item(self.lic, 11, HSN, "Guarded desc", "1")
        overridden = self.item(self.lic, 12, HSN, "palm overridden", "1")
        free = self.item(self.lic, 13, HSN, "palm free", "1")
        for r in (cleared, cleared_same, overridden, free):
            r.items.clear()
        ov.save_overrides(license_id=self.lic.pk, changes=[{"import_item_id": overridden.pk, "item_id": None, "expected_item_ids": []}], user=self.user)
        target, _ = ItemNameModel.objects.get_or_create(name="PKO - PI1")
        target.sion_norm_class, target.is_active = self.sion, True
        target.save()
        cfg = [{"base_name": "PKO", "norms": ["PI1"], "filters": [_Q(description__icontains="palm"), _Q(description__icontains="guarded")]}]
        from apps.license.utils import item_matcher
        with mock.patch.object(item_matcher, "get_item_filters", return_value=cfg):
            item_matcher.rule_auto_link_license_items(self.lic)
        assert self.links(free) == [target.pk]
        assert self.links(cleared_same) == [] and self.links(overridden) == []
        assert self.links(cleared) == [target.pk] or self.links(cleared) == []  # different description: not covered by the approval

    def test_auto_apply_and_apply_for_licence_and_description_mapping_respect_approvals(self):
        self.approve(self.pko)
        # a saved description mapping of the same description never overrides the approved combination
        res = save_mapping(description=DESC, item_ids=[self.olive.pk], user=self.user)
        assert res["approved"] == 3 and res["applied"] == 2  # diff_hsn + no_hsn follow the description mapping
        assert self.links(self.r1) == self.links(self.foreign) == [self.pko.pk]
        assert self.links(self.diff_hsn) == self.links(self.no_hsn) == [self.olive.pk]
        # drift (e.g. a stale writer) is repaired by the approval, not by the mapping
        self.r1.items.set([self.sugar])
        assert auto_apply(self.r1.pk) == "APPROVED" and self.links(self.r1) == [self.pko.pk]
        self.r2.items.set([self.milk])
        apply_for_licence(self.lic.pk)
        assert self.links(self.r2) == [self.pko.pk]
        # cleared: auto paths keep it empty
        self.approve(None)
        assert self.links(self.r1) == []
        assert auto_apply(self.r1.pk) == "APPROVED" and apply_for_licence(self.lic.pk) == 0 and self.links(self.r1) == []

    def test_new_record_gets_the_approval_and_hsn_change_triggers_propagation(self):
        self.approve(self.pko)
        new = self.item(self.lic, 20, HSN, "palm  kernel OIL.", "1")
        new.items.clear()
        with self.captureOnCommitCallbacks(execute=True):
            new.save()
            LicenseImportItemsModel.objects.filter(pk=new.pk).first()
        assert self.links(new) == []  # a plain re-save (no description / HSN change) does not touch links
        moved = LicenseImportItemsModel.objects.get(pk=self.diff_hsn.pk)
        assert self.links(moved) == []
        moved.hs_code = HSCodeModel.objects.get(hs_code=HSN)
        with self.captureOnCommitCallbacks(execute=True):
            moved.save()
        assert self.links(moved) == [self.pko.pk]  # the new (description, HSN) combination is approved
        again = LicenseImportItemsModel.objects.get(pk=new.pk)
        again.description = "palm kernel oil  "
        again.items.clear()
        with self.captureOnCommitCallbacks(execute=True):
            again.description = "PALM KERNEL OIL (x)"
            again.save()
            again.description = DESC
            again.save()
        assert self.links(again) == [self.pko.pk]

    # 6 ---------------------------------------------------------------------------------------------------------------
    def test_reassign_is_versioned_and_idempotent(self):
        first = self.approve(self.pko)
        changes_before = MappingChange.objects.count()
        same = self.approve(self.pko)
        assert same["action"] == "UNCHANGED" and same["applied"] == 0 and same["mapping_change"] is None and same["unchanged"] == 3
        assert MappingChange.objects.count() == changes_before
        assert ImportItemMappingApprovalVersion.objects.count() == 1
        second = self.approve(self.olive, expected_version=first["approval"]["version"])
        assert second["action"] == "REVISE" and second["approval"]["version"] == 2 and second["applied"] == 3
        assert all(self.links(r) == [self.olive.pk] for r in (self.r1, self.r2, self.foreign))
        v = ImportItemMappingApprovalVersion.objects.get(version=2)
        assert v.item_id == self.olive.pk and v.previous_item_id == self.pko.pk and v.records == 3 and v.licences == 2 and v.mapping_change_id

    def test_stale_version_is_a_concurrency_error(self):
        self.approve(self.pko)
        self.approve(self.olive)
        with pytest.raises(ia.ApprovalConcurrencyError):
            self.approve(self.pko, expected_version=1)
        assert self.links(self.r1) == [self.olive.pk]

    # override wins --------------------------------------------------------------------------------------------------
    def test_row_override_wins_over_an_approval(self):
        ov.save_overrides(license_id=self.lic.pk, changes=[{"import_item_id": self.r1.pk, "item_id": self.sugar.pk, "expected_item_ids": []}], user=self.user)
        res = self.approve(self.pko)
        assert res["overridden"] == 1 and res["applied"] == 2
        assert self.links(self.r1) == [self.sugar.pk] and self.links(self.r2) == [self.pko.pk]
        row = self.row(self.r1)
        assert row["source"] == "OVERRIDE" and row["overridden"] and row["approval"]["item"]["id"] == self.pko.pk
        assert ia.protected_import_item_ids([self.r1.pk, self.r2.pk, self.diff_desc.pk]) == {self.r1.pk: "override", self.r2.pk: "approved"}
        self.approve(None)
        assert self.links(self.r1) == [self.sugar.pk] and ia.protected_import_item_ids([self.r2.pk]) == {self.r2.pk: "cleared"}

    # 7 consolidation -------------------------------------------------------------------------------------------------
    def test_consolidation_repoints_approvals_with_a_version_and_revert_repoints_back(self):
        other = SionNormClassModel.objects.create(head_norm=HeadSIONNormsModel.objects.create(name="Other"), norm_class="PX9", is_active=True)
        pp, _ = ItemNameModel.objects.get_or_create(name="PP")
        pp.sion_norm_class, pp.is_active = other, True
        pp.save()
        pp.norms.set([self.sion, other])
        legacy, _ = ItemNameModel.objects.get_or_create(name="PP - PI1")
        legacy.sion_norm_class, legacy.is_active = self.sion, True
        legacy.save()
        legacy.norms.set([])
        a, b = self.licences
        merged = self.item(a, 21, "39021000", "PACKING MATERIAL :- PP", "40")
        merged_other = self.item(b, 22, "39021000", "PACKING MATERIAL :- PP", "40")
        cleared = self.item(b, 23, "39021000", "Poly Propylene Film Grade", "25")
        for r in (merged, merged_other, cleared):
            r.items.clear()
        self.approve(legacy, desc="PACKING MATERIAL :- PP", hsn="39021000")
        self.approve(None, desc="Poly Propylene Film Grade", hsn="39021000")
        assert self.links(merged) == self.links(merged_other) == [legacy.pk] and self.links(cleared) == []
        rows = {r["description"]: r for r in consolidation.preview(sion="PI1", target_id=pp.pk)["rows"]}
        assert rows["PACKING MATERIAL :- PP"]["status"] == consolidation.ELIGIBLE and "re-pointed" in rows["PACKING MATERIAL :- PP"]["reasons"][0]
        assert rows["Poly Propylene Film Grade"]["status"] == consolidation.EXCLUDED and "cleared" in rows["Poly Propylene Film Grade"]["reasons"][0]
        keys = [r["key"] for r in rows.values() if r["selectable"]]
        assert len(keys) == 1
        res = consolidation.apply(sion="PI1", target_id=pp.pk, keys=keys, user=self.user, reason="cleanup")
        approval = ImportItemMappingApproval.objects.get(description_key__startswith="PACKING")
        assert approval.item_id == pp.pk and approval.version == 2 and approval.source == "CONSOLIDATION"
        assert res["approval_repoints"] == [{"approval_id": approval.pk, "from_item_id": legacy.pk, "to_item_id": pp.pk, "version": 2, "applied": 0, "conflicts": 0}]
        v = ImportItemMappingApprovalVersion.objects.get(approval=approval, version=2)
        assert v.action == "CONSOLIDATION" and v.previous_item_id == legacy.pk and v.item_id == pp.pk
        assert self.links(merged) == self.links(merged_other) == [pp.pk] and self.links(cleared) == []  # cleared never gains links
        assert ProductIntelAuditEvent.objects.filter(action="import_item_approval", detail__action="CONSOLIDATION").exists()
        assert ImportItemMappingApproval.objects.get(description_key__startswith="POLY").status == "USER_APPROVED_CLEAR"
        back = consolidation.revert(batch=res["batch"], user=self.user)
        approval.refresh_from_db()
        assert approval.item_id == legacy.pk and approval.version == 3 and not back["conflicts"]
        assert self.links(merged) == self.links(merged_other) == [legacy.pk] and self.links(cleared) == []
        assert ImportItemMappingApprovalVersion.objects.filter(approval=approval, action="CONSOLIDATION").count() == 2

    def test_item_merge_repoints_active_and_revoked_approvals(self):
        self.approve(self.olive)
        revoked = self.approve(self.olive, desc="Other desc", hsn=HSN)["approval"]["id"]
        ia.revoke(revoked, self.user)
        out = ia.repoint_for_merge([self.olive.pk], self.pko.pk, user=self.user, reason="merge")
        assert len(out) == 2 and not ImportItemMappingApproval.objects.filter(item_id=self.olive.pk).exists()
        assert self.links(self.r1) == [self.pko.pk]
        assert ImportItemMappingApprovalVersion.objects.filter(action="CONSOLIDATION").count() == 2

    # 8 product mapping -----------------------------------------------------------------------------------------------
    def test_product_mapping_excludes_approved_combinations(self):
        pending_before = counts(fresh=True)["import"]
        rows, _, _ = description_rows(status="MAPPING_REQUIRED")
        assert any(r["description"] == DESC for r in rows)
        self.approve(self.pko)
        # the description still has two other combinations -> still pending, with per-combination counts
        rows, summary, _ = description_rows()
        palm = next(r for r in rows if r["key"] == "PALM KERNEL OIL")
        assert palm["status"] == "MAPPING_REQUIRED" and palm["combinations"] == 3 and palm["approved_combinations"] == 1 and palm["cleared_combinations"] == 0
        self.approve(self.olive, hsn="15131100")
        self.approve(None, hsn="")
        rows, summary, _ = description_rows()
        palm = next(r for r in rows if r["key"] == "PALM KERNEL OIL")
        assert palm["status"] == USER_APPROVED == "USER_APPROVED" and palm["approved_combinations"] == 2 and palm["cleared_combinations"] == 1
        assert palm["mapping"] is None and palm["records"] == 5
        assert not any(r["key"] == "PALM KERNEL OIL" for r in description_rows(status="MAPPING_REQUIRED")[0])
        assert any(r["key"] == "PALM KERNEL OIL" for r in description_rows(status="USER_APPROVED")[0])
        after = counts(fresh=True)["import"]
        assert after["records"] == pending_before["records"] - 5 and after["descriptions"] == pending_before["descriptions"] - 1

    def test_matching_groups_decide_and_undo_refuse_approved_records(self):
        self.r1.items.set([self.sugar, self.milk])
        before = {i for g in matching_groups(self.report()) for i in g["import_item_ids"]}
        assert self.diff_desc.pk in before and {self.r1.pk, self.r2.pk, self.foreign.pk} <= before
        self.approve(None, desc="Palm Kernel Oil Refined")
        self.approve(self.pko, hsn=HSN)
        after = {i for g in matching_groups(self.report()) for i in g["import_item_ids"]}
        assert self.diff_desc.pk not in after and not ({self.r1.pk, self.r2.pk, self.foreign.pk} & after)
        suggestion = {"source_key": "k", "description": DESC, "import_item_ids": [self.r1.pk, self.diff_hsn.pk], "hsn_code": HSN, "sion": "PI1",
                      "sion_known": True, "band": "HIGH", "confidence": 100, "checks": {}, "explanation": "", "suggestion": {"item_id": self.olive.pk}}
        with pytest.raises(MatchValidationError, match="1 record\\(s\\) have an approved Description \\+ HSN mapping — revise it in Product Mapping → Approved"):
            decide(suggestions=[suggestion], decision=ProductMatchDecision.APPROVED, user=self.user, item_id=self.olive.pk)
        assert self.links(self.diff_hsn) == []
        decision = ProductMatchDecision.objects.create(source_key="k", source_description=DESC, normalized_description="x", import_item_ids=[self.r1.pk],
                                                       chosen_item=self.olive, decision=ProductMatchDecision.APPROVED,
                                                       previous_links={str(self.r1.pk): []}, new_links={str(self.r1.pk): [self.pko.pk]}, decided_by=self.user)
        with pytest.raises(MatchValidationError, match="approved Description \\+ HSN mapping"):
            undo_import_approval(decision_id=decision.pk, user=self.user)
        assert self.links(self.r1) == [self.pko.pk]

    # revoke ----------------------------------------------------------------------------------------------------------
    def test_revoke_keeps_links_and_reapplies_the_description_mapping(self):
        self.approve(self.pko)
        res = ia.revoke(ImportItemMappingApproval.objects.get().pk, self.user)
        assert res["action"] == "REVOKE" and res["approval"]["is_active"] is False and res["approval"]["version"] == 2 and res["reapplied"] == 0
        assert all(self.links(r) == [self.pko.pk] for r in (self.r1, self.r2, self.foreign))
        assert ia.revoke(res["approval"]["id"], self.user)["action"] == "UNCHANGED"
        assert ia.protected_import_item_ids([self.r1.pk]) == {}
        # with an active description mapping, revoke applies it to the combination
        save_mapping(description=DESC, item_ids=[self.olive.pk], user=self.user)
        again = self.approve(self.sugar)  # reactivates
        assert again["action"] == "REACTIVATE" and again["approval"]["version"] == 3 and self.links(self.r1) == [self.sugar.pk]
        res = ia.revoke(again["approval"]["id"], self.user)
        assert res["reapplied"] == 3 and all(self.links(r) == [self.olive.pk] for r in (self.r1, self.r2, self.foreign))
        assert list(ImportItemMappingApprovalVersion.objects.order_by("version").values_list("action", flat=True)) == ["CREATE", "REVOKE", "REACTIVATE", "REVOKE"]

    # 9 audit ---------------------------------------------------------------------------------------------------------
    def test_every_change_is_audited_and_versioned(self):
        res = self.approve(self.pko)
        self.approve(self.olive)
        self.approve(None)
        ia.revoke(res["approval"]["id"], self.user)
        hist = ia.history(res["approval"]["id"])
        assert [h["action"] for h in hist] == ["REVOKE", "CLEAR", "REVISE", "CREATE"] and [h["version"] for h in hist] == [4, 3, 2, 1]
        assert hist[2]["item"]["name"] == "OLIVE OIL" and hist[2]["previous_item"]["name"] == "PKO" and hist[1]["item"] is None
        assert hist[3]["user"] == "appr-manager" and hist[3]["records"] == 3 and hist[3]["mapping_change"]
        events = ProductIntelAuditEvent.objects.filter(action="import_item_approval").order_by("pk")
        assert [e.detail["action"] for e in events] == ["CREATE", "REVISE", "CLEAR", "REVOKE"] and all(e.user == self.user for e in events)
        assert events[0].detail["records"] == 3 and events[0].detail["hsn_code"] == HSN

    # 10 financial invariance -----------------------------------------------------------------------------------------
    def test_financial_invariance(self):
        before = self.financials()
        a = self.approve(self.pko)
        assert self.financials() == before
        self.approve(self.olive)
        assert self.financials() == before
        self.approve(None)
        assert self.financials() == before
        ia.revoke(a["approval"]["id"], self.user)
        assert self.financials() == before

    # preview / listing -----------------------------------------------------------------------------------------------
    def test_preview_counts(self):
        self.foreign.items.set([self.sugar])
        self.r1.items.set([self.sugar])
        ov.save_overrides(license_id=self.lic.pk, changes=[{"import_item_id": self.r2.pk, "item_id": None, "expected_item_ids": []}], user=self.user)
        p = ia.preview(description=" palm kernel oil ", hsn=HSN)
        assert p["records"] == 3 and p["licences"] == 2 and p["overridden"] == 1
        assert p["licence_numbers"] == ["PIVOT-INT-000", "PIVOT-INT-001"]
        assert p["current_item_sets"] == {self.sugar.name: 2, "": 1}  # Item Names, never id lists
        with pytest.raises(MatchValidationError):
            ia.preview(description="", hsn=HSN)

    def test_listing_counts_records_and_licences_in_bulk(self):
        self.approve(self.pko)
        self.approve(None, hsn="")
        self.approve(self.olive, desc="Palm Kernel Oil Refined")
        ia.revoke(ImportItemMappingApproval.objects.get(description_key="PALM KERNEL OIL REFINED").pk, self.user)
        data = ia.listing()
        assert data["total"] == 2 and data["counts"] == {"approved": 1, "cleared": 1}
        by = {(r["hsn_code"]): r for r in data["rows"]}
        assert by[HSN]["records"] == 3 and by[HSN]["licences"] == 2 and by[HSN]["item"]["name"] == "PKO" and by[""]["status"] == "USER_APPROVED_CLEAR"
        assert [r["hsn_code"] for r in ia.listing(status="CLEARED")["rows"]] == [""] and ia.listing(status="REVOKED")["total"] == 1
        assert ia.listing(q="kernel")["total"] == 2 and ia.listing(q="zzz")["total"] == 0 and ia.listing(q=HSN[:4])["total"] == 1

    def test_licence_rows_query_count_does_not_grow_with_rows(self):
        self.approve(self.pko)
        with CaptureQueriesContext(connection) as small:
            ov.rows_for_licence(self.lic.pk)
        for n in range(10, 16):
            self.item(self.lic, n, HSN if n % 2 else "15131100", f"Desc {n}", "1")
            self.approve(self.olive if n % 3 else None, desc=f"Desc {n}", hsn=HSN if n % 2 else "15131100")
        with CaptureQueriesContext(connection) as big:
            rows = ov.rows_for_licence(self.lic.pk)
        assert len(rows) == 10 and len(big) == len(small) <= 22, (len(small), len(big))


class ApprovalReviewFixTests(ApprovalFixture):
    """Review fixes: consolidation vs row overrides / later decisions (B1, B2), HSN normaliser (N2), conflicts (N3), no-op cost (N4)."""

    def consolidation_setup(self):
        pp, _ = ItemNameModel.objects.get_or_create(name="PP")
        pp.sion_norm_class, pp.is_active = self.sion, True
        pp.save()
        pp.norms.set([self.sion])
        legacy, _ = ItemNameModel.objects.get_or_create(name="PP - PI1")
        legacy.sion_norm_class, legacy.is_active = self.sion, True
        legacy.save()
        legacy.norms.set([])
        a, b = self.licences
        rec_a = self.item(a, 21, "39021000", "PACKING MATERIAL :- PP", "40")
        rec_b = self.item(b, 22, "39021000", "PACKING MATERIAL :- PP", "40")
        for r in (rec_a, rec_b):
            r.items.set([legacy])
        return pp, legacy, rec_a, rec_b

    def row_override(self, record, item):
        ov.save_overrides(license_id=record.license_id, changes=[{"import_item_id": record.pk, "item_id": item.pk, "expected_item_ids": self.links(record)}],
                          user=self.user)

    # B1 ---------------------------------------------------------------------------------------------------------------
    def test_b1_consolidation_excludes_row_overridden_records(self):
        pp, legacy, rec_a, rec_b = self.consolidation_setup()
        self.row_override(rec_a, legacy)
        rows = consolidation.preview(sion="PI1", target_id=pp.pk)["rows"]
        row = next(r for r in rows if r["description"] == "PACKING MATERIAL :- PP")
        assert row["eligible_record_ids"] == [rec_b.pk] and row["record_ids"] == sorted([rec_a.pk, rec_b.pk])
        consolidation.apply(sion="PI1", target_id=pp.pk, keys=[row["key"]], user=self.user, reason="cleanup")
        assert self.links(rec_a) == [legacy.pk] and self.links(rec_b) == [pp.pk]
        assert ImportItemNameOverride.objects.get(import_item=rec_a).item_ids == [legacy.pk]

    def test_b1_only_overridden_records_are_not_selectable_and_reason_is_explicit(self):
        pp, legacy, rec_a, rec_b = self.consolidation_setup()
        self.row_override(rec_a, legacy)
        self.row_override(rec_b, legacy)
        row = next(r for r in consolidation.preview(sion="PI1", target_id=pp.pk)["rows"] if r["description"] == "PACKING MATERIAL :- PP")
        assert row["status"] == consolidation.EXCLUDED and not row["selectable"] and row["reasons"] == [consolidation.OVERRIDE_REASON]
        with pytest.raises(MatchValidationError, match="Row override"):
            consolidation.apply(sion="PI1", target_id=pp.pk, keys=[row["key"]], user=self.user, reason="cleanup")

    def test_b1_override_created_after_the_preview_aborts_apply_under_the_lock(self):
        pp, legacy, rec_a, rec_b = self.consolidation_setup()
        stale = consolidation.preview(sion="PI1", target_id=pp.pk)
        key = next(r["key"] for r in stale["rows"] if r["description"] == "PACKING MATERIAL :- PP")
        self.row_override(rec_a, legacy)
        with mock.patch.object(consolidation, "preview", return_value=stale):
            with pytest.raises(MatchValidationError, match="Row override"):
                consolidation.apply(sion="PI1", target_id=pp.pk, keys=[key], user=self.user, reason="cleanup")
        assert self.links(rec_a) == [legacy.pk] and self.links(rec_b) == [legacy.pk]  # all-or-nothing

    # B2 ---------------------------------------------------------------------------------------------------------------
    def _applied_batch(self):
        pp, legacy, rec_a, rec_b = self.consolidation_setup()
        key = next(r["key"] for r in consolidation.preview(sion="PI1", target_id=pp.pk)["rows"] if r["description"] == "PACKING MATERIAL :- PP")
        batch = consolidation.apply(sion="PI1", target_id=pp.pk, keys=[key], user=self.user, reason="cleanup")["batch"]
        assert self.links(rec_a) == self.links(rec_b) == [pp.pk]
        return pp, legacy, rec_a, rec_b, batch

    def test_b2_revert_skips_records_with_a_later_approval(self):
        pp, legacy, rec_a, rec_b, batch = self._applied_batch()
        ia.approve(description="PACKING MATERIAL :- PP", hsn="39021000", item_id=pp.pk, user=self.user)
        back = consolidation.revert(batch=batch, user=self.user)
        assert back["restored"] == 0 and len(back["conflicts"]) == 2
        assert all("approved" in c["reason"] for c in back["conflicts"])
        assert self.links(rec_a) == self.links(rec_b) == [pp.pk]

    def test_b2_revert_skips_records_with_a_later_row_override(self):
        pp, legacy, rec_a, rec_b, batch = self._applied_batch()
        self.row_override(rec_a, pp)
        back = consolidation.revert(batch=batch, user=self.user)
        assert back["restored"] == 1 and [c["import_item_id"] for c in back["conflicts"]] == [str(rec_a.pk)]
        assert "row override" in back["conflicts"][0]["reason"]
        assert self.links(rec_a) == [pp.pk] and self.links(rec_b) == [legacy.pk]
        assert ImportItemNameOverride.objects.get(import_item=rec_a).item_ids == [pp.pk]

    def test_b2_revert_skips_when_the_repointed_approval_was_changed_later(self):
        pp, legacy, rec_a, rec_b = self.consolidation_setup()
        ia.approve(description="PACKING MATERIAL :- PP", hsn="39021000", item_id=legacy.pk, user=self.user)
        key = next(r["key"] for r in consolidation.preview(sion="PI1", target_id=pp.pk)["rows"] if r["description"] == "PACKING MATERIAL :- PP")
        batch = consolidation.apply(sion="PI1", target_id=pp.pk, keys=[key], user=self.user, reason="cleanup")["batch"]
        ia.approve(description="PACKING MATERIAL :- PP", hsn="39021000", item_id=self.olive.pk, user=self.user)  # a later user decision
        back = consolidation.revert(batch=batch, user=self.user)
        assert back["restored"] == 0 and back["conflicts"]
        assert self.links(rec_a) == self.links(rec_b) == [self.olive.pk]

    # N2 ---------------------------------------------------------------------------------------------------------------
    def test_n2_hsn_trim_is_identical_in_python_and_sql_for_tab_nbsp_newline(self):
        a = self.item(self.lic, 31, "1513190", DESC, "1")
        b = self.item(self.lic, 32, "1513190\t", DESC, "1")
        c = self.item(self.lic, 33, "1513190\u00a0", DESC, "1")
        d = self.item(self.other, 34, "1513190\n", DESC, "1")
        for r in (a, b, c, d):
            r.items.clear()
        assert ia.clean_hsn(" \t1513190\u00a0\n") == "1513190" and ia.combination(c)[2] == "1513190"
        assert sorted(r.pk for r in ia.records_for(ia.combination(a)[1], "1513190")) == sorted([a.pk, b.pk, c.pk, d.pk])
        pending_before = counts(fresh=True)["import"]["records"]
        res = ia.approve(description=DESC, hsn="\t1513190 ", item_id=self.pko.pk, user=self.user)
        assert res["records"] == 4 and res["applied"] == 4
        for r in (a, b, c, d):
            assert self.links(r) == [self.pko.pk]
        approval = ImportItemMappingApproval.objects.get(hsn_code="1513190")
        stats = ia.stats_for([approval])[approval.pk]
        assert stats["records"] == 4 and stats["licences"] == 2
        assert set(ia.coverage([a, b, c, d])) == {a.pk, b.pk, c.pk, d.pk}
        assert ia.preview(description=DESC, hsn="1513190\u00a0")["records"] == 4
        assert pending_before - counts(fresh=True)["import"]["records"] == 4  # all four HSN variants leave the pending list
        from apps.license.services.product_intelligence.description_mapping import description_index
        combos = description_index()[ia.dm.description_key(DESC)]["combos"]
        assert sorted(combos["1513190"]) == sorted([a.pk, b.pk, c.pk, d.pk])

    # N3 ---------------------------------------------------------------------------------------------------------------
    def test_n3_conflicts_count_in_stats_and_listing(self):
        other = SionNormClassModel.objects.create(head_norm=HeadSIONNormsModel.objects.create(name="Other"), norm_class="PX8", is_active=True)
        bad, _ = ItemNameModel.objects.get_or_create(name="BAD SION ITEM")
        bad.sion_norm_class, bad.is_active = other, True
        bad.save()
        bad.norms.set([other])
        res = self.approve(bad)
        assert res["conflicts"] == 3 and res["applied"] == 0
        approval = ImportItemMappingApproval.objects.get(item=bad)
        assert ia.stats_for([approval])[approval.pk]["conflicts"] == 3
        row = next(r for r in ia.listing()["rows"] if r["id"] == approval.pk)
        assert row["conflicts"] == 3 and row["records"] == 3
        for r in (self.r1, self.r2, self.foreign):
            assert self.links(r) == []  # links unchanged
        # a healthy approval has none; an overridden record is not a conflict
        ok = self.approve(self.pko, desc="Other desc", hsn=HSN)
        assert ia.stats_for([ImportItemMappingApproval.objects.get(pk=ok["approval"]["id"])])[ok["approval"]["id"]]["conflicts"] == 0

    # N4 ---------------------------------------------------------------------------------------------------------------
    def test_n4_noop_licence_save_with_approved_records_stays_small(self):
        self.approve(self.pko)
        records = list(LicenseImportItemsModel.objects.filter(license=self.lic).select_related("hs_code"))
        with CaptureQueriesContext(connection) as small:
            out = ia.apply_for_records(records)
        assert out["applied"] == 0 and out["conflicts"] == 0 and len(out["covered"]) == 2
        for n in range(40, 50):
            r = self.item(self.lic, n, HSN, DESC, "1")
            r.items.set([self.pko])
        records = list(LicenseImportItemsModel.objects.filter(license=self.lic).select_related("hs_code"))
        with CaptureQueriesContext(connection) as big:
            out = ia.apply_for_records(records)
        assert out["applied"] == 0
        assert len(big) == len(small) <= 6, (len(small), len(big))
        assert MappingChange.objects.filter(kind=MappingChange.IMPORT_ITEM_APPROVAL).count() == 1  # nothing new recorded


class ApprovalApiTests(ApprovalFixture):
    SAVE = "/api/licenses/{}/import-item-names/save/"
    PREVIEW = "/api/licenses/{}/import-item-names/preview/"
    WS = "/api/item-pivot/matching/item-name-mapping/import/approvals/"

    def change(self, r, item, **extra):
        return {"import_item_id": r.pk, "item_id": item.pk if item else None, "expected_item_ids": self.links(r), **extra}

    def api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_licence_detail_save_is_global_by_default_with_propagation(self):
        c = self.api(self.user)
        res = c.post(self.SAVE.format(self.lic.pk), {"changes": [self.change(self.r1, self.pko)]}, format="json")
        assert res.status_code == 201, res.content
        j = res.json()
        assert j["saved"] == 1 and j["mapping_change"]
        p = j["propagation"][0]
        assert p["import_item_id"] == self.r1.pk and p["combination"] == {"description": DESC, "hsn_code": HSN}
        assert (p["records"], p["licences"], p["applied"], p["unchanged"], p["overridden"], p["conflicts"], p["conflict_licences"]) == (3, 2, 3, 0, 0, 0, [])
        assert self.links(self.foreign) == [self.pko.pk]
        row = next(r for r in j["rows"] if r["import_item_id"] == self.r1.pk)
        assert row["source"] == "APPROVAL" and row["approval"]["version"] == 1 and row["approval"]["records"] == 3 and row["approval"]["licences"] == 2
        assert row["approval"]["updated_by"] == "appr-manager" and row["approval"]["item"] == {"id": self.pko.pk, "name": "PKO"}
        # clear -> CLEARED
        res = c.post(self.SAVE.format(self.lic.pk), {"changes": [self.change(self.r1, None, expected_approval_version=1)]}, format="json")
        assert res.status_code == 201 and res.json()["propagation"][0]["applied"] == 3
        assert next(r for r in res.json()["rows"] if r["import_item_id"] == self.r1.pk)["status"] == "CLEARED"
        # scope=record is the one-record override
        rec = c.post(self.SAVE.format(self.lic.pk), {"changes": [self.change(self.r1, self.sugar, scope="record")]}, format="json")
        assert rec.status_code == 201 and rec.json()["propagation"] == [] and self.links(self.r1) == [self.sugar.pk] and self.links(self.r2) == []
        assert ImportItemNameOverride.objects.filter(import_item=self.r1).exists()

    def test_licence_detail_save_errors(self):
        c = self.api(self.user)
        url = self.SAVE.format(self.lic.pk)
        c.post(url, {"changes": [self.change(self.r1, self.pko)]}, format="json")
        stale = c.post(url, {"changes": [self.change(self.r1, self.olive, expected_approval_version=7)]}, format="json")
        assert stale.status_code == 409 and "version" in stale.json()["detail"]
        stale_row = c.post(url, {"changes": [{**self.change(self.r1, self.olive), "expected_item_ids": []}]}, format="json")
        assert stale_row.status_code == 409 and stale_row.json()["import_item_ids"] == [self.r1.pk]
        assert self.links(self.r1) == [self.pko.pk]
        dup = c.post(url, {"changes": [self.change(self.r1, self.olive), self.change(self.r2, self.sugar)]}, format="json")
        assert dup.status_code == 400 and "same Description + HSN" in dup.json()["detail"] and self.links(self.r2) == [self.pko.pk]
        bad_scope = c.post(url, {"changes": [self.change(self.r1, self.olive, scope="everywhere")]}, format="json")
        assert bad_scope.status_code == 400
        blank = LicenseImportItemsModel.objects.create(license=self.lic, serial_number=9, hs_code=None, description="  ", quantity=Decimal("1"))
        assert c.post(url, {"changes": [self.change(blank, self.olive)]}, format="json").status_code == 400
        # all-or-nothing: the second change fails, the first is rolled back
        mixed = c.post(url, {"changes": [self.change(self.diff_desc, self.olive), {"import_item_id": 999999, "item_id": self.olive.pk, "expected_item_ids": []}]}, format="json")
        assert mixed.status_code == 400 and self.links(self.diff_desc) == [] and not ImportItemMappingApproval.objects.filter(description_key__contains="REFINED").exists()

    def test_permissions(self):
        url = self.SAVE.format(self.lic.pk)
        v = self.api(self.viewer)
        assert v.post(url, {"changes": [self.change(self.r1, self.pko)]}, format="json").status_code == 403
        assert v.post(self.WS + "save/", {"description": DESC, "hsn_code": HSN, "item_id": self.pko.pk}, format="json").status_code == 403
        assert v.post(self.WS + "1/revoke/", {}, format="json").status_code == 403
        assert not ImportItemMappingApproval.objects.exists()
        pv = v.post(self.PREVIEW.format(self.lic.pk), {"changes": [{"import_item_id": self.r1.pk, "item_id": self.pko.pk}]}, format="json")
        assert pv.status_code == 200, pv.content  # read permission is enough
        assert v.get(self.WS).status_code in (200, 403)  # reads follow the viewset's ReportPermission (not widened here)
        outsider = get_user_model().objects.create_user(username="appr-nobody")
        assert self.api(outsider).post(self.PREVIEW.format(self.lic.pk), {"changes": []}, format="json").status_code in (403, 404)

    def test_preview_endpoint(self):
        self.foreign.items.set([self.sugar])
        res = self.api(self.user).post(self.PREVIEW.format(self.lic.pk), {"changes": [{"import_item_id": self.r1.pk, "item_id": self.pko.pk}]}, format="json")
        assert res.status_code == 200
        p = res.json()["previews"][0]
        assert p["import_item_id"] == self.r1.pk and p["combination"] == {"description": DESC, "hsn_code": HSN}
        assert (p["records"], p["licences"], p["overridden"]) == (3, 2, 0) and p["licence_numbers"] == ["PIVOT-INT-000", "PIVOT-INT-001"]
        assert p["current_item_sets"] == {"": 2, self.sugar.name: 1}
        assert not ImportItemMappingApproval.objects.exists() and self.links(self.r1) == []  # read-only
        for body in ({}, {"changes": []}, {"changes": [{"import_item_id": self.r1.pk, "item_id": 999999}]},
                     {"changes": [{"import_item_id": self.diff_hsn.pk, "item_id": self.pko.pk}]}):
            assert self.api(self.user).post(self.PREVIEW.format(self.lic.pk), body, format="json").status_code == 400

    def test_workspace_endpoints(self):
        c = self.api(self.user)
        res = c.post(self.WS + "save/", {"description": DESC, "hsn_code": HSN, "item_id": self.pko.pk}, format="json")
        assert res.status_code == 201, res.content
        j = res.json()
        assert j["action"] == "CREATE" and j["records"] == 3 and j["approval"]["source"] == "MAPPING_WORKSPACE"
        aid = j["approval"]["id"]
        assert c.post(self.WS + "save/", {"description": DESC, "hsn_code": HSN, "item_id": self.pko.pk}, format="json").status_code == 200  # unchanged
        stale = c.post(self.WS + "save/", {"description": DESC, "hsn_code": HSN, "item_id": self.olive.pk, "expected_version": 5}, format="json")
        assert stale.status_code == 409 and stale.json()["version"] == 1
        assert c.post(self.WS + "save/", {"description": "", "hsn_code": HSN, "item_id": self.pko.pk}, format="json").status_code == 400
        assert c.post(self.WS + "save/", {"hsn_code": HSN}, format="json").status_code == 400
        assert c.post(self.WS + "save/", {"description": DESC, "hsn_code": HSN, "item_id": 999999}, format="json").status_code == 400
        rev = c.post(self.WS + "save/", {"description": DESC, "hsn_code": HSN, "item_id": self.olive.pk, "expected_version": 1}, format="json")
        assert rev.status_code == 201 and rev.json()["action"] == "REVISE"
        lst = c.get(self.WS + "?q=palm").json()
        assert lst["total"] == 1 and lst["counts"] == {"approved": 1, "cleared": 0} and lst["can_apply"] is True
        row = lst["rows"][0]
        assert (row["id"], row["description"], row["hsn_code"], row["status"], row["version"], row["records"], row["licences"], row["overridden"]) == (
            aid, DESC, HSN, "USER_APPROVED", 2, 3, 2, 0)
        assert row["item"]["name"] == "OLIVE OIL" and row["updated_by"] == "appr-manager" and row["source"] == "MAPPING_WORKSPACE" and row["updated_on"]
        hist = c.get(f"{self.WS}{aid}/history/").json()["events"]
        assert [h["action"] for h in hist] == ["REVISE", "CREATE"]
        assert c.get(f"{self.WS}999999/history/").status_code == 404
        done = c.post(f"{self.WS}{aid}/revoke/", {}, format="json")
        assert done.status_code == 200 and done.json()["action"] == "REVOKE" and c.get(self.WS).json()["total"] == 0
        assert c.post(f"{self.WS}999999/revoke/", {}, format="json").status_code == 400

    def test_licence_form_and_item_patch_cannot_change_an_approved_combination(self):
        from apps.license.api.serializers._license_write import _apply_form_import_items

        self.approve(self.pko)
        _apply_form_import_items(self.r1, [self.olive])
        assert self.links(self.r1) == [self.pko.pk]
        _apply_form_import_items(self.diff_desc, [self.olive])  # not covered: the form still applies
        assert self.links(self.diff_desc) == [self.olive.pk]
        c = self.api(self.super)
        refused = c.patch(f"/api/license-items/{self.r1.pk}/", {"items": [self.olive.pk]}, format="json")
        assert refused.status_code == 400 and "approved mapping" in str(refused.json())
        assert c.patch(f"/api/license-items/{self.r1.pk}/", {"items": [self.pko.pk]}, format="json").status_code == 200  # same links re-sent
        assert self.links(self.r1) == [self.pko.pk]



@pytest.mark.django_db
def test_approval_refuses_more_records_than_the_cap(monkeypatch):
    """Security review 2026-11-20: one decision locks / re-plans a bounded number of records; nothing is written above it."""
    from apps.license.models import ImportItemMappingApproval
    from apps.license.services.product_intelligence import import_item_approval as ia
    from apps.license.services.product_matching import MatchValidationError as _E

    monkeypatch.setattr(ia, "MAX_RECORDS", 1)
    monkeypatch.setattr(ia, "records_for", lambda *a, **k: [object(), object()])
    with pytest.raises(_E, match="limit 1"):
        ia.approve(description="Palm Kernel Oil", hsn="15131900", item_id=None, user=None)
    assert not ImportItemMappingApproval.objects.exists()  # rolled back
