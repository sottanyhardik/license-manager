"""Row-level Item Name override on Licence Detail -> Import Items (owner decision 2026-11-20)."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import (
    ImportDescriptionMapping, ImportItemDescriptionMapping, ImportItemNameOverride, LicenseImportItemsModel, LicenseReplanRequest, MappingChange,
    ProductIntelAuditEvent,
)
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.product_intelligence import import_item_override as svc
from apps.license.services.product_intelligence.description_mapping import (
    apply_for_licence, auto_apply, description_rows, reapply, save_mapping,
)
from apps.license.services.product_matching import MatchValidationError, decide
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


class OverrideTests(pivot_fixture.IntelligenceFixture):
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
        self.r1 = self.item(self.lic, 1, "15131900", "Palm Kernel Oil", "500")
        self.r2 = self.item(self.lic, 2, "15131900", "PALM KERNEL OIL ", "300")
        self.r3 = self.item(self.lic, 3, "15131900", "Olive thing", "100", names=[self.sugar, self.milk])
        self.foreign = self.item(self.other, 1, "15131900", "Palm Kernel Oil", "70")
        self.user = get_user_model().objects.create_user(username="ovr-manager")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
        self.super = get_user_model().objects.create_superuser(username="ovr-super", password="x", email="s@example.com")

    def links(self, r):
        return sorted(r.items.values_list("pk", flat=True))

    def row(self, r):
        return next(x for x in svc.rows_for_licence(self.lic.pk) if x["import_item_id"] == r.pk)

    def change(self, r, item, expected=None):
        return {"import_item_id": r.pk, "item_id": item.pk if item else None, "expected_item_ids": self.links(r) if expected is None else expected,
                "scope": "record"}  # API default is global (2026-11-20 amendment); this suite covers the one-record override

    def save(self, *changes, **kw):
        return svc.save_overrides(license_id=self.lic.pk, changes=list(changes), user=self.user, **kw)

    def financials(self):
        ids = [self.lic.pk, self.other.pk]
        rows = list(LicenseImportItemsModel.objects.filter(license_id__in=ids).order_by("pk").values_list(
            "quantity", "available_quantity", "debited_quantity", "allotted_quantity", "cif_fc", "cif_inr", "debited_value", "allotted_value"))
        comps = [LBC.calculate_all_components(l) for l in (self.lic, self.other)]
        return rows, comps, LBC.calculate_financial_balance_for_licenses(ids)

    # --- display -----------------------------------------------------------------------------------------------
    def test_display_mapped_unmapped_multiple_and_conflict(self):
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        r1 = self.row(self.r1)
        assert r1["status"] == "MAPPED" and r1["source"] == "DESCRIPTION_MAPPING" and not r1["overridden"]
        assert r1["items"] == [{"id": self.pko.pk, "name": "PKO"}] and r1["description_mapping"]["version"] == 1
        assert r1["sion"] == ["PI1"] and r1["hs_code"] == "15131900" and r1["override"] is None
        unmapped = self.item(self.lic, 4, "15131900", "Nothing mapped", "1")
        u = self.row(unmapped)
        assert u["status"] == "NOT_MAPPED" and u["source"] is None and u["items"] == [] and u["description_mapping"] is None
        m = self.row(self.r3)
        assert m["status"] == "MULTIPLE" and m["source"] == "OTHER" and len(m["items"]) == 2
        # description-mapping CONFLICT: an Item Name with another SION
        head = HeadSIONNormsModel.objects.create(name="Other")
        other_sion = SionNormClassModel.objects.create(head_norm=head, norm_class="ZZ9", is_active=True)
        bad = ItemNameModel.objects.create(name="WRONG SION ITEM", sion_norm_class=other_sion)
        bad.norms.set([other_sion])
        save_mapping(description="Olive thing", item_ids=[bad.pk], user=self.user)
        c = self.row(self.r3)
        assert c["status"] == "CONFLICT" and "not legitimate" in c["note"] and c["source"] == "DESCRIPTION_MAPPING"
        # linked name invalid for the licence SION
        self.r1.items.set([bad])
        assert self.row(self.r1)["status"] == "CONFLICT"

    # --- save / change / clear / idempotent --------------------------------------------------------------------
    def test_save_change_clear_and_idempotent_resave(self):
        before = self.financials()
        res = self.save(self.change(self.r3, self.pko), reason="wrong name")
        assert res["saved"] == 1 and res["unchanged"] == 0 and res["mapping_change"]
        assert self.links(self.r3) == [self.pko.pk]  # several links replaced by one
        ov = ImportItemNameOverride.objects.get(import_item=self.r3)
        assert ov.item_ids == [self.pko.pk] and sorted(ov.previous_item_ids) == sorted([self.sugar.pk, self.milk.pk])
        row = self.row(self.r3)
        assert row["status"] == "MAPPED" and row["source"] == "OVERRIDE" and row["overridden"] and row["override"]["reason"] == "wrong name"
        assert row["override"]["updated_by"] == "ovr-manager"
        again = self.save(self.change(self.r3, self.pko))
        assert again["saved"] == 0 and again["unchanged"] == 1 and again["mapping_change"] is None
        assert MappingChange.objects.filter(kind=MappingChange.IMPORT_ITEM_OVERRIDE).count() == 1
        changed = self.save(self.change(self.r3, self.olive))
        assert changed["saved"] == 1 and self.links(self.r3) == [self.olive.pk]
        assert ImportItemNameOverride.objects.get(import_item=self.r3).previous_item_ids == sorted([self.sugar.pk, self.milk.pk])  # first-ever
        cleared = self.save(self.change(self.r3, None))
        assert cleared["saved"] == 1 and self.links(self.r3) == []
        assert ImportItemNameOverride.objects.get(import_item=self.r3).item_ids == []
        r = self.row(self.r3)
        assert r["status"] == "NOT_MAPPED" and r["overridden"]
        assert self.save(self.change(self.r3, None))["unchanged"] == 1
        assert self.financials() == before

    def test_concurrency_other_licence_inactive_and_validation(self):
        with pytest.raises(svc.OverrideConcurrencyError) as exc:
            self.save(self.change(self.r1, self.pko, expected=[self.sugar.pk]), self.change(self.r2, self.pko))
        assert exc.value.import_item_ids == [self.r1.pk]
        assert self.links(self.r2) == [] and not ImportItemNameOverride.objects.exists()
        with pytest.raises(MatchValidationError, match="do not belong"):
            self.save(self.change(self.r1, self.pko), self.change(self.foreign, self.pko))
        assert not ImportItemNameOverride.objects.exists() and self.links(self.r1) == []
        inactive = ItemNameModel.objects.create(name="OLD", sion_norm_class=self.sion, is_active=False)
        with pytest.raises(MatchValidationError, match="active"):
            self.save(self.change(self.r1, inactive))
        with pytest.raises(MatchValidationError):
            self.save()
        with pytest.raises(MatchValidationError, match="At most"):
            self.save(*[self.change(self.r1, self.pko)] * 201)
        with pytest.raises(MatchValidationError, match="more than once"):
            self.save(self.change(self.r1, self.pko), self.change(self.r1, self.pko))

    def test_blocking_conflict_refuses_everything_and_not_verified_note_is_saved(self):
        head = HeadSIONNormsModel.objects.create(name="Other")
        other_sion = SionNormClassModel.objects.create(head_norm=head, norm_class="ZZ9", is_active=True)
        bad = ItemNameModel.objects.create(name="WRONG SION ITEM", sion_norm_class=other_sion)
        bad.norms.set([other_sion])
        with pytest.raises(MatchValidationError, match="Nothing was saved"):
            self.save(self.change(self.r1, self.pko), self.change(self.r2, bad))
        assert self.links(self.r1) == [] and not ImportItemNameOverride.objects.exists()
        assert not MappingChange.objects.filter(kind=MappingChange.IMPORT_ITEM_OVERRIDE).exists()
        # HSN chapter conflict: PKO is known only under chapter 17
        self.item(self.other, 5, "17019990", "Sugar", "1", names=[self.olive])
        with pytest.raises(MatchValidationError, match="HSN"):
            self.save(self.change(self.r1, self.olive))
        # "Not verified" (no HSN history for PKO) is saved and shown
        self.save(self.change(self.r1, self.pko))
        ev = ProductIntelAuditEvent.objects.get(action="import_item_name_override")
        assert "Not verified" in ev.detail["records"][0]["note"]
        assert "Not verified" in self.row(self.r1)["note"]

    # --- API ---------------------------------------------------------------------------------------------------
    def test_api_permissions_status_codes_and_history(self):
        viewer = get_user_model().objects.create_user(username="ovr-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
        client = APIClient()
        base = f"/api/licenses/{self.lic.pk}/import-item-names/"
        body = {"changes": [self.change(self.r1, self.pko)]}
        client.force_authenticate(viewer)
        got = client.get(base)
        assert got.status_code == 200 and got.json()["can_edit"] is False and len(got.json()["rows"]) == 3
        assert client.post(base + "save/", body, format="json").status_code == 403
        assert client.post(base + "revert/", {"import_item_ids": [self.r1.pk]}, format="json").status_code == 403
        assert not ImportItemNameOverride.objects.exists()
        client.force_authenticate(self.super)
        assert client.get(base).json()["can_edit"] is True
        ok = client.post(base + "save/", {**body, "reason": "fix"}, format="json")
        assert ok.status_code == 201, ok.content
        j = ok.json()
        assert j["saved"] == 1 and j["unchanged"] == 0 and j["mapping_change"] and len(j["rows"]) == 3
        assert client.post(base + "save/", {"changes": [self.change(self.r1, self.pko, expected=[])]}, format="json").status_code == 409
        stale = client.post(base + "save/", {"changes": [self.change(self.r1, self.olive, expected=[])]}, format="json")
        assert stale.status_code == 409 and stale.json()["import_item_ids"] == [self.r1.pk] and stale.json()["detail"]
        bad = client.post(base + "save/", {"changes": [self.change(self.foreign, self.pko)]}, format="json")
        assert bad.status_code == 400 and bad.json()["detail"]
        assert client.post(base + "save/", {}, format="json").status_code == 400
        hist = client.get(f"{base}{self.r1.pk}/history/").json()["events"]
        assert len(hist) == 1 and hist[0]["action"] == "import_item_name_override" and hist[0]["previous_item_ids"] == []
        assert hist[0]["new_items"] == [{"id": self.pko.pk, "name": "PKO"}] and hist[0]["user"] == "ovr-super" and hist[0]["time"]
        assert client.get(f"{base}{self.foreign.pk}/history/").status_code == 404
        rv = client.post(base + "revert/", {"import_item_ids": [self.r1.pk]}, format="json")
        assert rv.status_code == 200 and rv.json()["reverted"] == 1 and len(rv.json()["rows"]) == 3
        assert client.post(base + "revert/", {"import_item_ids": "x"}, format="json").status_code == 400
        acts = [e["action"] for e in client.get(f"{base}{self.r1.pk}/history/").json()["events"]]
        assert acts == ["import_item_name_override_reverted", "import_item_name_override"]

    def test_audit_mapping_change_and_replan(self):
        self.save(self.change(self.r3, self.pko), reason="why")
        ev = ProductIntelAuditEvent.objects.get(action="import_item_name_override")
        rec = ev.detail["records"][0]
        assert rec["previous_item_ids"] == sorted([self.sugar.pk, self.milk.pk]) and rec["new_item_ids"] == [self.pko.pk]
        assert rec["source"] == "licence_detail" and ev.detail["license_id"] == self.lic.pk and ev.user == self.user
        change = MappingChange.objects.get(kind=MappingChange.IMPORT_ITEM_OVERRIDE)
        assert ev.detail["mapping_version"] == change.pk and change.license_ids == [self.lic.pk] and change.import_item_ids == [self.r3.pk]
        assert LicenseReplanRequest.objects.filter(license_id=self.lic.pk).exists()
        h = svc.history(self.r3.pk)
        assert h[0]["previous_items"] and h[0]["new_items"][0]["name"] == "PKO"

    # --- overrides survive every automatic re-apply ------------------------------------------------------------
    def test_override_survives_every_description_mapping_path(self):
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        assert self.links(self.r1) == self.links(self.r2) == [self.pko.pk]
        self.save(self.change(self.r1, self.olive))
        mapped = ImportDescriptionMapping.objects.get()
        res = save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk, self.olive.pk], user=self.user)
        assert res["overridden"] == 1
        assert self.links(self.r1) == [self.olive.pk] and self.links(self.r2) == sorted([self.pko.pk, self.olive.pk])
        assert reapply(mapped.pk, user=self.user)["overridden"] == 1 and self.links(self.r1) == [self.olive.pk]
        with self.captureOnCommitCallbacks(execute=True):
            self.r1.description = "PALM KERNEL OIL  "  # same key
            self.r1.save()
        assert auto_apply(self.r1.pk) is None and self.links(self.r1) == [self.olive.pk]
        apply_for_licence(self.lic.pk)
        assert self.links(self.r1) == [self.olive.pk]
        with self.captureOnCommitCallbacks(execute=True):
            self.lic.save()  # licence save → apply_for_licence after commit
        assert self.links(self.r1) == [self.olive.pk]
        # clear is also protected
        self.save(self.change(self.r2, None))
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        reapply(mapped.pk, user=self.user)
        apply_for_licence(self.lic.pk)
        assert self.links(self.r2) == [] and self.links(self.r1) == [self.olive.pk]
        assert self.links(self.foreign) == [self.pko.pk]
        rows = {r["key"]: r for r in description_rows()[0]}
        assert rows["PALM KERNEL OIL"]["overridden"] == 2 and rows["PALM KERNEL OIL"]["status"] != "PARTIAL"

    def test_licence_form_save_never_overwrites_an_override(self):
        """The licence form re-sends every line's items on each save — a stale form must not revert an override."""
        from apps.license.api.serializers._license_write import _apply_form_import_items

        self.save(self.change(self.r1, self.olive))
        _apply_form_import_items(self.r1, [self.pko])  # stale form value
        assert self.links(self.r1) == [self.olive.pk]
        _apply_form_import_items(self.r2, [self.pko])  # non-overridden lines keep the existing form behaviour
        assert self.links(self.r2) == [self.pko.pk]

    def test_revert_reapplies_description_mapping(self):
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        self.save(self.change(self.r1, self.olive), self.change(self.r3, self.olive))
        before = self.financials()
        out = svc.revert_overrides(license_id=self.lic.pk, import_item_ids=[self.r1.pk, self.r3.pk, self.r2.pk], user=self.user)
        assert out["reverted"] == 2 and out["import_item_ids"] == sorted([self.r1.pk, self.r3.pk])
        assert self.links(self.r1) == [self.pko.pk]  # saved mapping re-applied (REPLACE)
        assert self.links(self.r3) == [self.olive.pk]  # no mapping for this description → links stay
        assert not ImportItemNameOverride.objects.exists()
        assert ImportItemDescriptionMapping.objects.get(import_item=self.r1).applied_version == 1
        assert MappingChange.objects.filter(kind=MappingChange.DESCRIPTION_MAPPING).count() >= 2
        ev = ProductIntelAuditEvent.objects.get(action="import_item_name_override_reverted")
        recs = {r["import_item_id"]: r for r in ev.detail["records"]}
        assert recs[self.r1.pk]["previous_item_ids"] == [self.olive.pk] and recs[self.r1.pk]["new_item_ids"] == [self.pko.pk]
        assert self.financials() == before
        assert svc.revert_overrides(license_id=self.lic.pk, import_item_ids=[self.r1.pk], user=self.user)["reverted"] == 0

    def test_decide_refuses_overridden_record(self):
        self.save(self.change(self.r1, self.olive))
        suggestion = {"source_key": "palm kernel oil", "description": "Palm Kernel Oil", "import_item_ids": [self.r1.pk, self.r2.pk],
                      "hsn_code": "15131900", "sion": "PI1", "sion_known": True, "band": "HIGH", "confidence": 100, "checks": {}, "explanation": "",
                      "suggestion": {"item_id": self.pko.pk}}
        from apps.license.models import ProductMatchDecision
        with pytest.raises(MatchValidationError, match="licence-level Item Name override"):
            decide(suggestions=[suggestion], decision=ProductMatchDecision.APPROVED, user=self.user, item_id=self.pko.pk)
        assert self.links(self.r1) == [self.olive.pk] and self.links(self.r2) == []
        assert not MappingChange.objects.filter(kind=MappingChange.MATCH_DECISION).exists()  # rolled back

    def test_review_round_guards(self):
        """Review findings 2026-11-20 (Opus N1/N2/N3/N5, security, code review)."""
        from apps.license.models import ProductMatchDecision
        from apps.license.services.product_intelligence.item_name_mapping import undo_import_approval

        client = APIClient()
        client.force_authenticate(self.super)
        # N1: the licence item chip editor (PATCH license-items/:id/) may re-send an override's links but never change them
        self.save(self.change(self.r1, self.olive))
        refused = client.patch(f"/api/license-items/{self.r1.pk}/", {"items": [self.pko.pk]}, format="json")
        assert refused.status_code == 400 and "override" in str(refused.json()).lower()
        assert self.links(self.r1) == [self.olive.pk]
        assert client.patch(f"/api/license-items/{self.r1.pk}/", {"items": [self.olive.pk]}, format="json").status_code == 200
        assert client.patch(f"/api/license-items/{self.r2.pk}/", {"items": [self.pko.pk]}, format="json").status_code == 200  # not overridden
        # N2: undoing an earlier matcher approval never reverts a pinned record
        decision = ProductMatchDecision.objects.create(source_key="k", source_description="Palm Kernel Oil", normalized_description="palm kernel oil",
                                                       import_item_ids=[self.r1.pk], chosen_item=self.olive, decision=ProductMatchDecision.APPROVED,
                                                       previous_links={str(self.r1.pk): []}, new_links={str(self.r1.pk): [self.olive.pk]}, decided_by=self.user)
        with pytest.raises(MatchValidationError, match="licence-level Item Name override"):
            undo_import_approval(decision_id=decision.pk, user=self.user)
        assert self.links(self.r1) == [self.olive.pk]
        # stale rows are reported (409) before an invalid target (400)
        self.pko.is_active = False
        self.pko.save()
        stale = client.post(f"/api/licenses/{self.lic.pk}/import-item-names/save/", {"changes": [self.change(self.r1, self.pko, expected=[])]}, format="json")
        assert stale.status_code == 409
        # security: malformed revert ids are a 400, never a 500; oversized expected lists are refused
        base = f"/api/licenses/{self.lic.pk}/import-item-names/"
        for ids in ([{"a": 1}], [1, "x"], [[1]]):
            assert client.post(base + "revert/", {"import_item_ids": ids}, format="json").status_code == 400, ids
        huge = {"changes": [{"import_item_id": self.r2.pk, "item_id": self.olive.pk, "expected_item_ids": list(range(1, 60))}]}
        assert client.post(base + "save/", huge, format="json").status_code == 400
        # N3: history reads only this licence's events; N5: the revert event links its mapping version
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.olive.pk], user=self.user)
        svc.save_overrides(license_id=self.other.pk, changes=[self.change(self.foreign, self.olive)], user=self.user)
        assert {e["action"] for e in svc.history(self.r1.pk, license_id=self.lic.pk)} == {"import_item_name_override"}
        assert svc.history(self.r1.pk, license_id=self.other.pk) == []
        svc.save_overrides(license_id=self.lic.pk, changes=[self.change(self.r1, None)], user=self.user)
        out = client.post(base + "revert/", {"import_item_ids": [self.r1.pk]}, format="json").json()
        assert out["reverted"] == 1 and out["reapplied"] == 1 and self.links(self.r1) == [self.olive.pk]
        ev = ProductIntelAuditEvent.objects.filter(action="import_item_name_override_reverted").latest("pk")
        assert ev.detail["mapping_version"] and MappingChange.objects.filter(pk=ev.detail["mapping_version"]).exists()

    # --- invariants --------------------------------------------------------------------------------------------
    def test_financial_invariance_across_save_clear_revert(self):
        from apps.allotment.models import AllotmentItems, AllotmentModel
        allotment = AllotmentModel.objects.create(company=self.company, item_name="x", required_quantity=1)
        AllotmentItems.objects.create(allotment=allotment, item=self.r1, qty=1, cif_fc=30, cif_inr=1)
        before = self.financials()
        self.save(self.change(self.r1, self.pko), self.change(self.r3, self.olive))
        assert self.financials() == before
        self.save(self.change(self.r1, None))
        assert self.financials() == before
        svc.revert_overrides(license_id=self.lic.pk, import_item_ids=[self.r1.pk, self.r3.pk], user=self.user)
        assert self.financials() == before

    def test_get_query_count_is_bounded(self):
        for n in range(20):
            self.item(self.lic, 10 + n, "15131900", f"Bulk {n}", "1", names=[self.sugar])
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        self.save(self.change(self.r1, self.olive))
        with CaptureQueriesContext(connection) as small:
            svc.rows_for_licence(self.other.pk)
        with CaptureQueriesContext(connection) as big:
            rows = svc.rows_for_licence(self.lic.pk)
        assert len(rows) == 23 and len(big) <= 12 and len(big) - len(small) <= 3, (len(big), len(small))
