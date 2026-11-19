"""Bulk canonical-product consolidation (owner request 2026-11-19: E1 Polypropylene → canonical "PP").

Classification only: import-item → master links change (audited, reversible); descriptions, HSN, quantities, CIF,
plans and debits are never touched and no licence is flagged for re-planning.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseImportItemsModel, LicenseItemPlan, LicenseReplanRequest, ProductAlias, ProductIntelAuditEvent, ProductMatchDecision
from apps.license.services.item_pivot_intelligence import build_intelligence
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.services.product_intelligence.consolidation import ALREADY, ELIGIBLE, EXCLUDED, REVIEW, apply, preview, revert
from apps.license.services.product_matching import MatchValidationError, normalise
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


@pytest.mark.parametrize("raw", ["PP", "P.P.", "Polypropylene", "Poly Propylene", "Poly-Propylene", "POLYPROPYLENE"])
def test_every_pp_spelling_normalises_to_one_identity(raw):
    assert normalise(raw) == "polypropylene"


@pytest.mark.parametrize("raw", ["BOPP", "Pipe", "PPE kit", "Paper"])
def test_lookalikes_are_not_polypropylene(raw):
    assert "polypropylene" not in normalise(raw)


class ConsolidationTests(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        other = SionNormClassModel.objects.create(head_norm=HeadSIONNormsModel.objects.create(name="Other"), norm_class="PX9", is_active=True)
        # Canonical PP: legacy FK points at another norm, legitimacy for PI1 comes from the norms M2M (as on the real "PP").
        self.pp = self._master("PP", other, [self.sion, other])
        self.legacy = self._master("PP - PI1", self.sion, [])
        self.hdpe = self._master("HDPE", self.sion, [self.sion])
        self.foil = self._master("ALUMINIUM FOIL", self.sion, [self.sion])
        a, b = self.licences
        self.history = self.item(a, 20, "39021000", "PP Granules", "1", names=[self.pp])           # PP chapter 39 history
        self.legacy_rec = self.item(a, 21, "39021000", "PACKING MATERIAL :- PP", "40", names=[self.legacy])
        self.unlinked = self.item(b, 22, "39021000", "Poly Propylene Film Grade", "25")
        self.unlinked.items.clear()
        self.multi = self.item(b, 23, "39021000", "PP / Aluminium Foil", "30", names=[self.foil])
        self.board = self.item(b, 24, "39209999", "Polypropylene Board", "5")
        self.board.items.clear()
        self.wrong_hsn = self.item(b, 25, "76071994", "Packing Material / PP", "7", names=[self.foil])
        self.two_links = self.item(b, 26, "39012000", "P.P.", "3", names=[self.pp, self.hdpe])
        self.unrelated = self.item(b, 27, "39172390", "PVC pipe fittings", "9")
        # The import-item save signal auto-links masters; set each record's links to the state under test.
        for rec, links in ((self.history, [self.pp]), (self.legacy_rec, [self.legacy]), (self.unlinked, []), (self.multi, [self.foil]),
                           (self.board, []), (self.wrong_hsn, [self.foil]), (self.two_links, [self.pp, self.hdpe]), (self.unrelated, [])):
            rec.items.set(links)
        self.manager = get_user_model().objects.create_user(username="pp-manager")
        self.manager.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    @staticmethod
    def _master(name, fk, norms):
        item, _ = ItemNameModel.objects.get_or_create(name=name)
        item.sion_norm_class, item.is_active = fk, True
        item.save()
        item.norms.set(norms)
        return item

    def rows(self):
        return {r["description"]: r for r in preview(sion="PI1", target_id=self.pp.pk)["rows"]}

    def report(self):
        return build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1", include_norm_links=True))

    def eligible_keys(self):
        return [r["key"] for r in self.rows().values() if r["selectable"]]

    def test_preview_classifies_every_candidate_with_reasons(self):
        rows = self.rows()
        assert rows["PACKING MATERIAL :- PP"]["status"] == ELIGIBLE and "Replaces PP - PI1" in rows["PACKING MATERIAL :- PP"]["reasons"][0]
        assert rows["Poly Propylene Film Grade"]["status"] == ELIGIBLE
        assert rows["PP Granules"]["status"] == ALREADY
        assert rows["PP / Aluminium Foil"]["status"] == EXCLUDED and "Multi-product" in rows["PP / Aluminium Foil"]["reasons"][0]
        assert rows["Polypropylene Board"]["status"] == REVIEW and "board" in rows["Polypropylene Board"]["reasons"][0]
        assert rows["Packing Material / PP"]["status"] == REVIEW and "HSN chapter 76" in rows["Packing Material / PP"]["reasons"][0]
        assert rows["P.P."]["status"] == REVIEW and "several masters" in rows["P.P."]["reasons"][0]
        assert "PVC pipe fittings" not in rows  # unrelated products are not candidates
        assert sum(r["selectable"] for r in rows.values()) == 2

    def test_apply_consolidates_only_selected_eligible_records_and_is_idempotent(self):
        before = self.report()["overview"]["integrity"]
        quantities = list(LicenseImportItemsModel.objects.order_by("pk").values_list("pk", "description", "hs_code_id", "quantity", "cif_fc"))
        plans = list(LicenseItemPlan.objects.order_by("pk").values_list("pk", "planned_quantity", "planned_cif_fc"))
        replans = LicenseReplanRequest.objects.count()
        result_keys = self.eligible_keys()
        result = apply(sion="PI1", target_id=self.pp.pk, keys=result_keys, user=self.manager, reason="E1 PP cleanup")
        assert result["records"] == 2
        assert list(self.legacy_rec.items.values_list("name", flat=True)) == ["PP"]
        assert list(self.unlinked.items.values_list("name", flat=True)) == ["PP"]
        assert list(self.multi.items.values_list("name", flat=True)) == ["ALUMINIUM FOIL"]  # excluded stays as it was
        assert set(self.two_links.items.values_list("name", flat=True)) == {"PP", "HDPE"}
        assert list(LicenseImportItemsModel.objects.order_by("pk").values_list("pk", "description", "hs_code_id", "quantity", "cif_fc")) == quantities
        assert list(LicenseItemPlan.objects.order_by("pk").values_list("pk", "planned_quantity", "planned_cif_fc")) == plans
        assert LicenseReplanRequest.objects.count() == replans  # consolidation never flags licences for re-planning
        decision = ProductMatchDecision.objects.get(import_item_ids=[self.legacy_rec.pk])
        assert decision.previous_links == {str(self.legacy_rec.pk): [self.legacy.pk]} and decision.new_links == {str(self.legacy_rec.pk): [self.pp.pk]}
        assert decision.decided_by == self.manager and "E1 PP cleanup" in decision.explanation
        assert ProductAlias.objects.filter(item=self.pp, sion=self.sion).count() == 2
        assert ItemNameModel.objects.filter(pk=self.legacy.pk).exists()  # masters are never deleted
        assert not self.eligible_keys()  # nothing left to consolidate
        with pytest.raises(MatchValidationError, match="not eligible"):  # re-applying the same keys changes nothing
            apply(sion="PI1", target_id=self.pp.pk, keys=result_keys, user=self.manager, reason="again")
        assert ProductMatchDecision.objects.count() == 2
        after = self.report()["overview"]["integrity"]
        assert after["preserved"] and after["source_totals"] == before["source_totals"] and after["source_record_count"] == before["source_record_count"]

    def test_item_pivot_shows_one_canonical_pp_row_under_the_licence_norm(self):
        apply(sion="PI1", target_id=self.pp.pk, keys=self.eligible_keys(), user=self.manager, reason="cleanup")
        data = self.report()
        pp_rows = [p for p in data["products"] if p["item_name_id"] == self.pp.pk]
        assert len(pp_rows) == 1 and pp_rows[0]["sion"] == "PI1" and pp_rows[0]["key"] == f"ITEM:{self.pp.pk}:PI1"
        assert pp_rows[0]["entitlement_qty"] == "66.000"  # 1 + 40 + 25: each record counted once
        assert not [p for p in data["products"] if p["item_name_id"] == self.legacy.pk]
        # The classic pivot path keeps the legacy FK filter (unchanged behaviour).
        classic = select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1")
        names = {n.name for lic in classic for it in lic.import_license.all() for n in it.items.all()}
        assert "PP" not in names

    def test_ineligible_selection_changes_nothing(self):
        board_key = self.rows()["Polypropylene Board"]["key"]
        with pytest.raises(MatchValidationError, match="not eligible — nothing was changed"):
            apply(sion="PI1", target_id=self.pp.pk, keys=[self.eligible_keys()[0], board_key], user=self.manager, reason="x")
        assert list(self.legacy_rec.items.values_list("name", flat=True)) == ["PP - PI1"]
        with pytest.raises(MatchValidationError, match="reason"):
            apply(sion="PI1", target_id=self.pp.pk, keys=self.eligible_keys(), user=self.manager, reason=" ")

    def test_revert_restores_previous_links_once(self):
        result = apply(sion="PI1", target_id=self.pp.pk, keys=self.eligible_keys(), user=self.manager, reason="cleanup")
        out = revert(batch=result["batch"], user=self.manager)
        assert out["restored"] == 2 and not out["conflicts"]
        assert list(self.legacy_rec.items.values_list("name", flat=True)) == ["PP - PI1"] and not self.unlinked.items.exists()
        assert not ProductAlias.objects.filter(pk__in=result["aliases"], is_active=True).exists()
        with pytest.raises(MatchValidationError, match="already reverted"):
            revert(batch=result["batch"], user=self.manager)
        assert ProductIntelAuditEvent.objects.filter(action="bulk_consolidation_reverted").count() == 1

    def test_apply_aborts_when_a_record_changed_after_the_preview(self):
        keys = self.eligible_keys()
        self.unlinked.items.set([self.hdpe, self.foil])  # gained several links between preview and apply → no longer eligible
        with pytest.raises(MatchValidationError, match="changed since the preview"):
            from unittest import mock
            with mock.patch("apps.license.services.product_intelligence.consolidation.preview", return_value=self._stale_preview(keys)):
                apply(sion="PI1", target_id=self.pp.pk, keys=keys, user=self.manager, reason="x")
        assert list(self.legacy_rec.items.values_list("name", flat=True)) == ["PP - PI1"]  # nothing written

    def _stale_preview(self, keys):
        rows = []
        for desc, rid in (("PACKING MATERIAL :- PP", self.legacy_rec.pk), ("Poly Propylene Film Grade", self.unlinked.pk)):
            key = next(k for k in keys if k.startswith(normalise(desc)))
            rows.append({"key": key, "description": desc, "hsn_code": "39021000", "status": ELIGIBLE, "selectable": True, "reasons": [],
                         "eligible_record_ids": [rid], "record_ids": [rid]})
        return {"rows": rows}

    def test_revert_records_only_restored_links_and_keeps_aliases_on_conflict(self):
        result = apply(sion="PI1", target_id=self.pp.pk, keys=self.eligible_keys(), user=self.manager, reason="cleanup")
        self.unlinked.items.set([self.hdpe])  # changed by someone else after the consolidation
        out = revert(batch=result["batch"], user=self.manager)
        assert out["restored"] == 1 and len(out["conflicts"]) == 1
        reverts = ProductMatchDecision.objects.filter(explanation__startswith="Revert of bulk consolidation")
        assert sorted(i for d in reverts for i in d.import_item_ids) == [self.legacy_rec.pk]
        assert list(self.unlinked.items.values_list("name", flat=True)) == ["HDPE"]  # left as is

    def test_a_trailing_category_label_keeps_the_description_multi_product(self):
        from apps.license.services.product_matching import product_segments
        assert product_segments("Packing Material / PP") == ["polypropylene"]
        assert product_segments("Polypropylene / Packing Material") == ["polypropylene", "packing material"]
        assert "polypropylene" not in normalise("2 p.p.m residue")

    def test_api_requires_license_manager_and_previews_for_viewers(self):
        viewer = get_user_model().objects.create_user(username="pp-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(viewer)
        res = client.get("/api/item-pivot/matching/consolidation/", {"sion": "PI1", "target_id": self.pp.pk})
        assert res.status_code == 200 and res.json()["can_apply"] is False and res.json()["batches"] == []
        body = {"sion": "PI1", "target_id": self.pp.pk, "keys": self.eligible_keys(), "reason": "cleanup"}
        assert client.post("/api/item-pivot/matching/consolidation/apply/", body, format="json").status_code == 403
        client.force_authenticate(self.manager)
        created = client.post("/api/item-pivot/matching/consolidation/apply/", body, format="json")
        assert created.status_code == 201 and created.json()["records"] == 2
        assert client.post("/api/item-pivot/matching/consolidation/revert/", {"batch": created.json()["batch"]}, format="json").status_code == 200
        assert LicenseImportItemsModel.objects.get(pk=self.board.pk).quantity == Decimal("5")


class ClassicPivotSelectionRegressionTests(pivot_fixture.IntelligenceFixture):
    """Domain audit 2026-11-19: the opt-in norm-link change must not alter the classic pivot's export-item filter."""

    def test_norm_filter_still_scopes_export_items_on_both_paths(self):
        from apps.license.models import LicenseExportItemModel
        other = SionNormClassModel.objects.create(head_norm=self.sion.head_norm, norm_class="PX8", is_active=True)
        LicenseExportItemModel.objects.create(license=self.licences[0], norm_class=other, cif_fc=Decimal("5"))
        for include in (False, True):
            licences = select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1", include_norm_links=include)
            norms = {e.norm_class.norm_class for lic in licences for e in lic.export_license.all()}
            assert norms == {"PI1"}, (include, norms)
