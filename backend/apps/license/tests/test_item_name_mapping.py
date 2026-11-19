"""Item Name mapping across all three sources (owner requirement 2026-11-19, §6 acceptance test).

Licence import item, BOE and allotment descriptions are mapped to the SAME existing ``ItemNameModel`` id ("PKO");
Item Pivot groups them under it; pending queues drop them; descriptions and every financial value are unchanged.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel, SionPlanningRule
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.item_pivot_intelligence import build_intelligence
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.services.product_intelligence.item_name_mapping import apply_entries, apply_target, counts, history, queue
from apps.license.services.product_matching import MatchValidationError, decide, matching_groups, suggest
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


class _MappingFixture(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.pko, _ = ItemNameModel.objects.get_or_create(name="PKO")
        self.pko.sion_norm_class, self.pko.is_active = self.sion, True
        self.pko.save()
        self.pko.norms.add(self.sion)
        self.sugar.norms.add(self.sion)
        # Active SION rule that owns HSN 1513 → PKO is the legitimate debit target for these import items.
        SionPlanningRule.objects.create(sion=self.sion, name="PKO", unit="kg", max_unit_price=Decimal("2"), priority=1, import_item=self.pko,
                                        expression={"operator": "AND", "conditions": [{"field": "HSN", "comparator": "STARTS_WITH", "value": "1513"}]})
        a, _ = self.licences
        self.import_item = self.item(a, 1, "15131900", "PALM KERNEL OIL", "500")
        self.import_item.items.clear()
        self.boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="987654321", bill_of_entry_date=a.license_date,
                                                   exchange_rate=Decimal("84.50"), product_name="CRUDE PALM KERNEL OIL")
        self.boe_row = RowDetails.objects.create(bill_of_entry=self.boe, sr_number=self.import_item, transaction_type=DEBIT,
                                                 cif_inr=Decimal("8450"), cif_fc=Decimal("100"), qty=Decimal("40"))
        self.allotment = AllotmentModel.objects.create(company=self.company, item_name="PALM KERNEL OIL (CRUDE)", required_quantity=Decimal("20"))
        self.allot_row = AllotmentItems.objects.create(allotment=self.allotment, item=self.import_item, qty=Decimal("20"), cif_fc=Decimal("50"), cif_inr=Decimal("4225"))
        for model, pk in ((BillOfEntryModel, self.boe.pk), (AllotmentModel, self.allotment.pk)):  # pending, as on real data
            model.objects.filter(pk=pk).update(planning_target_item=None, planning_mapping_status="UNMAPPED_AMBIGUOUS", planning_mapping_source="")
        self.manager = get_user_model().objects.create_user(username="itemname-manager")
        self.manager.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    def report(self):
        return build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1", include_norm_links=True))

    def group(self, kind, record_id):
        return next((g for g in queue(kind)["groups"] if record_id in g["record_ids"]), None)

    def financials(self):
        a = self.licences[0].pk
        return (list(LicenseImportItemsModel.objects.filter(pk=self.import_item.pk).values_list("description", "quantity", "cif_fc", "hs_code_id")),
                list(RowDetails.objects.filter(pk=self.boe_row.pk).values_list("qty", "cif_fc", "cif_inr", "transaction_type")),
                list(AllotmentItems.objects.filter(pk=self.allot_row.pk).values_list("qty", "cif_fc", "cif_inr")),
                BillOfEntryModel.objects.get(pk=self.boe.pk).product_name, AllotmentModel.objects.get(pk=self.allotment.pk).item_name,
                LBC.calculate_debit_for_licenses([a]), LBC.calculate_allotment_for_licenses([a]), LBC.calculate_financial_balance_for_licenses([a]))


class ItemNameMappingTests(_MappingFixture):
    def test_three_sources_resolve_to_the_same_item_name_and_item_pivot_groups_them(self):
        before = self.financials()
        # Pending queues offer PKO as the legitimate target for the BOE and the allotment.
        assert [x["name"] for x in self.group("boe", self.boe.pk)["legitimate"]] == ["PKO"]
        assert [x["name"] for x in self.group("allotment", self.allotment.pk)["legitimate"]] == ["PKO"]
        # 1. Licence import item → PKO (Product Matching approval, server-validated).
        row = next(s for s in suggest(matching_groups(self.report())) if self.import_item.pk in s["import_item_ids"])
        decide(suggestions=[row], decision="APPROVED", user=self.manager, item_id=self.pko.pk)
        # 2. BOE and 3. allotment → the same PKO id.
        apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        apply_target(kind="allotment", record_ids=[self.allotment.pk], item_id=self.pko.pk, user=self.manager)

        assert list(self.import_item.items.values_list("pk", flat=True)) == [self.pko.pk]
        assert BillOfEntryModel.objects.get(pk=self.boe.pk).planning_target_item_id == self.pko.pk
        assert AllotmentModel.objects.get(pk=self.allotment.pk).planning_target_item_id == self.pko.pk
        boe = BillOfEntryModel.objects.get(pk=self.boe.pk)
        assert (boe.planning_mapping_status, boe.planning_mapping_source) == ("MAPPED_EXPLICIT", "USER_SELECTED")

        data = self.report()
        pko_rows = [p for p in data["products"] if p["item_name_id"] == self.pko.pk]
        assert len(pko_rows) == 1 and pko_rows[0]["product"] == "PKO"
        assert any(r["import_item_id"] == self.import_item.pk and r["description"] == "PALM KERNEL OIL" for r in pko_rows[0]["source_records"])

        assert self.group("boe", self.boe.pk) is None and self.group("allotment", self.allotment.pk) is None  # left the pending queues
        assert not any(self.import_item.pk in s["import_item_ids"] for s in suggest(matching_groups(self.report())))
        assert self.financials() == before  # descriptions, qty, CIF, BOE debit rows, allotments and balances unchanged

    def test_validation_rejects_illegitimate_inactive_and_conflicting_targets(self):
        with pytest.raises(MatchValidationError, match="not a legitimate planning target"):
            apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.sugar.pk, user=self.manager)
        inactive = ItemNameModel.objects.create(name="PKO OLD", sion_norm_class=self.sion, is_active=False)
        with pytest.raises(MatchValidationError, match="existing, active Item Name"):
            apply_target(kind="allotment", record_ids=[self.allotment.pk], item_id=inactive.pk, user=self.manager)
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=self.sugar, planning_mapping_status="MAPPED_EXPLICIT")
        with pytest.raises(MatchValidationError, match="already mapped"):
            apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        assert BillOfEntryModel.objects.get(pk=self.boe.pk).planning_target_item_id == self.sugar.pk  # nothing changed

    def test_mapping_is_idempotent_and_versioned_for_replanning(self):
        from apps.license.models import MappingChange
        first = apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        again = apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        assert (first["mapped"], again["mapped"], again["unchanged"]) == (1, 0, 1)
        change = MappingChange.objects.get(kind=MappingChange.BOE_TARGET)  # exactly one version (the signal does not re-version it)
        assert change.license_ids == [self.licences[0].pk] and change.source_refs == [self.boe.pk]
        assert change.detail["records"] == [{"id": self.boe.pk, "previous_target": None, "previous_status": "UNMAPPED_AMBIGUOUS", "new_target": self.pko.pk}]
        assert first["mapping_versions"] == [change.pk] and again["mapping_versions"] == []

    def test_status_only_change_is_versioned_and_replanned(self):
        from apps.license.models import LicenseReplanRequest, MappingChange
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=self.pko, planning_mapping_status="INVALID_PERSISTED_TARGET")
        before = LicenseReplanRequest.objects.filter(license=self.licences[0]).count()
        apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        assert BillOfEntryModel.objects.get(pk=self.boe.pk).planning_mapping_status == "MAPPED_EXPLICIT"
        change = MappingChange.objects.get(kind=MappingChange.BOE_TARGET)
        assert change.detail["records"][0]["previous_status"] == "INVALID_PERSISTED_TARGET" and change.license_ids == [self.licences[0].pk]
        assert LicenseReplanRequest.objects.filter(license=self.licences[0]).count() >= before and LicenseReplanRequest.objects.filter(
            license=self.licences[0], reason="debit_target_changed").exists()

    def test_api_permissions_and_queue(self):
        viewer = get_user_model().objects.create_user(username="itemname-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(viewer)
        res = client.get("/api/item-pivot/matching/item-name-mapping/boe/")
        assert res.status_code == 200 and res.json()["can_apply"] is False
        body = {"record_ids": [self.boe.pk], "item_id": self.pko.pk}
        assert client.post("/api/item-pivot/matching/item-name-mapping/boe/apply/", body, format="json").status_code == 403
        client.force_authenticate(self.manager)
        assert client.post("/api/item-pivot/matching/item-name-mapping/boe/apply/", {"record_ids": ["x"], "item_id": self.pko.pk}, format="json").status_code == 400
        ok = client.post("/api/item-pivot/matching/item-name-mapping/boe/apply/", body, format="json")
        assert ok.status_code == 201 and ok.json()["item"] == "PKO"


class MappingWorkspaceTests(_MappingFixture):
    """Mapping workspace spec (2026-11-19): suggestions are not approvals, per-entry bulk, audit, history, counts."""

    def second_boe(self, description="PALM KERNEL OIL"):
        boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="111222333", bill_of_entry_date=self.licences[0].license_date,
                                              exchange_rate=Decimal("84.50"), product_name=description)
        RowDetails.objects.create(bill_of_entry=boe, sr_number=self.import_item, transaction_type=DEBIT, cif_inr=Decimal("845"), cif_fc=Decimal("10"), qty=Decimal("4"))
        BillOfEntryModel.objects.filter(pk=boe.pk).update(planning_target_item=None, planning_mapping_status="UNMAPPED_AMBIGUOUS", planning_mapping_source="")
        return boe

    def test_queue_row_carries_spec_columns_and_a_validated_suggestion(self):
        row = self.group("boe", self.boe.pk)
        assert row["boe_numbers"] == ["987654321"] and row["latest_boe_date"] == self.licences[0].license_date.isoformat()
        assert row["hsn_codes"] == ["15131900"] and row["sion"] == ["PI1"] and row["quantity"] == "40.000" and row["records"] == 1
        assert row["licence_numbers"] == [self.licences[0].license_number]
        assert row["suggestion"]["item_id"] == self.pko.pk and row["suggestion"]["explanation"]
        assert all(c["code"] != "SION" for c in row["conflicts"])
        allot = self.group("allotment", self.allotment.pk)
        assert allot["quantity"] == "20.000" and allot["suggestion"]["name"] == "PKO"

    def test_cross_source_approval_improves_suggestion_but_never_approves_another_source(self):
        self.allotment.item_name = "CRUDE PALM KERNEL OIL"
        self.allotment.save(update_fields=["item_name"])
        apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        row = self.group("allotment", self.allotment.pk)
        assert row is not None, "the allotment must stay pending — no automatic cross-source approval"
        assert row["suggestion"]["confidence"] == 100 and "another source" in row["suggestion"]["explanation"]
        assert AllotmentModel.objects.get(pk=self.allotment.pk).planning_target_item_id is None

    def test_bulk_requires_an_item_name_per_entry_and_is_all_or_nothing(self):
        boe2 = self.second_boe()
        with pytest.raises(MatchValidationError, match="its own selected Item Name"):
            apply_entries(kind="boe", entries=[{"record_ids": [self.boe.pk], "item_id": self.pko.pk}, {"record_ids": [boe2.pk]}], user=self.manager)
        with pytest.raises(MatchValidationError, match="nothing was mapped"):
            apply_entries(kind="boe", entries=[{"record_ids": [self.boe.pk], "item_id": self.pko.pk}, {"record_ids": [boe2.pk], "item_id": self.sugar.pk}], user=self.manager)
        assert not BillOfEntryModel.objects.filter(pk__in=[self.boe.pk, boe2.pk], planning_target_item__isnull=False).exists()  # failure → still pending
        with pytest.raises(MatchValidationError, match="more than one entry"):
            apply_entries(kind="boe", entries=[{"record_ids": [self.boe.pk], "item_id": self.pko.pk}, {"record_ids": [self.boe.pk], "item_id": self.pko.pk}], user=self.manager)
        res = apply_entries(kind="boe", entries=[{"record_ids": [self.boe.pk], "item_id": self.pko.pk}, {"record_ids": [boe2.pk], "item_id": self.pko.pk}], user=self.manager)
        assert res["mapped"] == 2 and len(res["mapping_versions"]) == 1  # one mapping version per approval

    def test_multi_product_description_is_flagged_and_refused_in_bulk(self):
        boe2 = self.second_boe("PALM KERNEL OIL, SUGAR")
        row = self.group("boe", boe2.pk)
        assert any(c["code"] == "MULTI_PRODUCT" for c in row["conflicts"])
        with pytest.raises(MatchValidationError, match="multi-product description"):
            apply_entries(kind="boe", entries=[{"record_ids": [self.boe.pk], "item_id": self.pko.pk}, {"record_ids": [boe2.pk], "item_id": self.pko.pk}], user=self.manager)

    def test_audit_history_and_counts(self):
        before = counts(fresh=True)
        assert before["boe"]["records"] >= 1 and before["allotment"]["records"] >= 1
        apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager, reason="ok")
        rows = history("boe")["rows"]
        assert rows[0]["id"] == self.boe.pk and rows[0]["item_id"] == self.pko.pk and rows[0]["by"] == "itemname-manager"
        assert rows[0]["previous"] is None and rows[0]["hsn_codes"] == ["15131900"] and rows[0]["mapping_version"]
        from apps.license.models import ProductIntelAuditEvent
        rec = ProductIntelAuditEvent.objects.get(action="boe_item_name_mapped").detail["records"][0]
        assert rec["validation"].startswith("PASSED") and rec["licence_ids"] == [self.licences[0].pk] and rec["previous_status"] == "UNMAPPED_AMBIGUOUS"
        assert counts(fresh=True)["boe"]["records"] == before["boe"]["records"]  # pending = names without a saved name mapping

    def test_api_bulk_history_counts_and_pagination(self):
        client = APIClient()
        client.force_authenticate(self.manager)
        assert client.get("/api/item-pivot/matching/item-name-mapping/counts/").status_code == 200
        page = client.get("/api/item-pivot/matching/item-name-mapping/boe/", {"limit": 1, "offset": 0}).json()
        assert page["limit"] == 1 and len(page["groups"]) <= 1
        bad = client.post("/api/item-pivot/matching/item-name-mapping/boe/apply/", {"entries": [{"record_ids": [self.boe.pk]}]}, format="json")
        assert bad.status_code == 400
        ok = client.post("/api/item-pivot/matching/item-name-mapping/boe/apply/", {"entries": [{"record_ids": [self.boe.pk], "item_id": self.pko.pk}]}, format="json")
        assert ok.status_code == 201 and ok.json()["mapped"] == 1
        hist = client.get("/api/item-pivot/matching/item-name-mapping/boe/history/").json()
        assert hist["rows"][0]["id"] == self.boe.pk
        assert client.get("/api/item-pivot/matching/item-name-mapping/import/history/").status_code == 200

    def test_import_item_api_approval_requires_an_explicit_item_name(self):
        """A suggestion is never an approval: the decide API refuses APPROVED without a selected Item Name id."""
        client = APIClient()
        client.force_authenticate(self.manager)
        params = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}
        key = next(s["source_key"] for s in client.get("/api/item-pivot/matching/", params).json()["suggestions"] if self.import_item.pk in s["import_item_ids"])
        refused = client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": params}, format="json")
        assert refused.status_code == 400 and "Select an Item Name" in refused.json()["detail"]
        assert list(self.import_item.items.all()) == []
        ok = client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": params, "item_ids": {key: self.pko.pk}}, format="json")
        assert ok.status_code == 201, ok.json()
        assert list(self.import_item.items.values_list("pk", flat=True)) == [self.pko.pk]

    def test_non_pending_targets_are_never_overwritten_and_money_fields_are_not_persisted(self):
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=self.sugar, planning_mapping_status="MAPPED_DETERMINISTIC")
        with pytest.raises(MatchValidationError, match="already mapped"):
            apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        assert BillOfEntryModel.objects.get(pk=self.boe.pk).planning_target_item_id == self.sugar.pk
        # Header money fields that save() recomputes in memory stay exactly as stored.
        AllotmentModel.objects.filter(pk=self.allotment.pk).update(cif_fc=Decimal("12345.67"), cif_inr=Decimal("1.00"), exchange_rate=Decimal("9.99"))
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=None, planning_mapping_status="UNMAPPED_AMBIGUOUS", exchange_rate=Decimal("77.77"))
        apply_target(kind="allotment", record_ids=[self.allotment.pk], item_id=self.pko.pk, user=self.manager)
        apply_target(kind="boe", record_ids=[self.boe.pk], item_id=self.pko.pk, user=self.manager)
        assert AllotmentModel.objects.filter(pk=self.allotment.pk).values_list("cif_fc", "cif_inr", "exchange_rate").get() == (Decimal("12345.67"), Decimal("1.00"), Decimal("9.99"))
        assert BillOfEntryModel.objects.get(pk=self.boe.pk).exchange_rate == Decimal("77.77")

    def test_import_item_bulk_needs_an_explicit_valid_item_name_per_row(self):
        """Bulk: suggestions never satisfy selection; every row is re-validated; failures leave everything pending."""
        second = self.item(self.licences[1], 2, "15131900", "PALM KERNEL OIL CRUDE", "100")
        second.items.clear()
        client = APIClient()
        client.force_authenticate(self.manager)
        params = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}
        rows = client.get("/api/item-pivot/matching/", params).json()["suggestions"]
        keys = [next(s["source_key"] for s in rows if item.pk in s["import_item_ids"]) for item in (self.import_item, second)]
        assert keys[0] != keys[1]
        post = lambda body: client.post("/api/item-pivot/matching/decide/", {"source_keys": keys, "decision": "APPROVED", "filters": params, **body}, format="json")  # noqa: E731
        assert post({}).status_code == 400  # suggestions only
        assert post({"item_ids": {keys[0]: self.pko.pk}}).status_code == 400  # one row without a selection
        assert post({"item_ids": {keys[0]: self.pko.pk, keys[1]: True}}).status_code == 400  # not an id
        assert post({"item_ids": {keys[0]: self.pko.pk, keys[1]: 999999}}).status_code == 400  # no such Item Name
        inactive = ItemNameModel.objects.create(name="PKO RETIRED", sion_norm_class=self.sion, is_active=False)
        inactive.norms.add(self.sion)
        assert post({"item_ids": {keys[0]: self.pko.pk, keys[1]: inactive.pk}}).status_code == 400
        assert not self.import_item.items.exists() and not second.items.exists()  # failed approvals stay pending
        ok = post({"item_ids": {keys[0]: self.pko.pk, keys[1]: self.pko.pk}})
        assert ok.status_code == 201, ok.json()
        assert list(self.import_item.items.values_list("pk", flat=True)) == [self.pko.pk] == list(second.items.values_list("pk", flat=True))
        pending = client.get("/api/item-pivot/matching/", params).json()["suggestions"]
        assert not any(set(s["import_item_ids"]) & {self.import_item.pk, second.pk} for s in pending)  # left pending
        hist = client.get("/api/item-pivot/matching/item-name-mapping/import/history/").json()["rows"]
        assert {r["item_id"] for r in hist[:2]} == {self.pko.pk}  # appear in approved history

    def test_malformed_bodies_are_400_not_500(self):
        client = APIClient()
        client.force_authenticate(self.manager)
        assert client.post("/api/item-pivot/matching/item-name-mapping/boe/apply/", [1, 2], format="json").status_code == 400
        assert client.post("/api/item-pivot/matching/decide/", [1], format="json").status_code == 400
        params = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}
        key = next(s["source_key"] for s in client.get("/api/item-pivot/matching/", params).json()["suggestions"] if self.import_item.pk in s["import_item_ids"])
        for bad in (True, "5", -1):
            res = client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": params, "item_id": bad}, format="json")
            assert res.status_code == 400, bad
        assert not self.import_item.items.exists()


class ImportItemUndoTests(_MappingFixture):
    """Licence Import Item mapping — two-table workflow (owner spec 2026-11-19): Approved Mappings with Undo."""

    params = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.manager)

    def pending(self):
        return [s for s in self.client.get("/api/item-pivot/matching/", self.params).json()["suggestions"]
                if self.import_item.pk in s["import_item_ids"] and s["band"] not in {"APPROVED", "CLASSIFIED"}]

    def approve(self):
        key = self.pending()[0]["source_key"]
        res = self.client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": self.params,
                                                                    "item_ids": {key: self.pko.pk}}, format="json")
        assert res.status_code == 201, res.json()
        return res.json()["recorded"][0]

    def approved(self, **params):
        return self.client.get("/api/item-pivot/matching/item-name-mapping/import/approved/", params).json()

    def undo(self, decision_id):
        return self.client.post(f"/api/item-pivot/matching/item-name-mapping/import/approved/{decision_id}/undo/", {}, format="json")

    def test_approve_moves_to_approved_and_undo_returns_to_pending_with_audit(self):
        from apps.license.models import MappingChange, ProductAlias, ProductIntelAuditEvent, ProductMatchDecision
        before = self.financials()
        assert self.pending() and self.approved()["total"] == 0
        decision_id = self.approve()
        assert not self.pending()  # left Pending
        data = self.approved()
        assert data["total"] == 1 and data["can_undo"] is True
        row = data["rows"][0]
        assert (row["id"], row["item_id"], row["item"], row["status"], row["sion"]) == (decision_id, self.pko.pk, "PKO", "APPROVED", "PI1")
        assert self.approved(q="palm")["total"] == 1 and self.approved(q="zzz")["total"] == 0
        assert ProductAlias.objects.filter(decision_id=decision_id, is_active=True).exists()

        res = self.undo(decision_id)
        assert res.status_code == 200 and res.json()["undone"] is True, res.json()
        assert list(self.import_item.items.all()) == []  # links restored to the pre-approval state
        assert self.approved()["total"] == 0
        back = self.pending()
        assert back and back[0]["band"] != "APPROVED"  # Pending again, the undone approval is not reused
        # Audit: the approval row is kept unchanged; the reversal records user + timestamp; one mapping version per action.
        assert ProductMatchDecision.objects.filter(pk=decision_id, decision="APPROVED", chosen_item=self.pko).exists()
        ev = ProductIntelAuditEvent.objects.get(action="import_item_mapping_undone")
        assert ev.user == self.manager and ev.created_on and ev.detail["decision_id"] == decision_id
        assert MappingChange.objects.filter(kind=MappingChange.MATCH_DECISION, detail__undo_of=decision_id).count() == 1
        assert not ProductAlias.objects.filter(decision_id=decision_id, is_active=True).exists()
        hist = self.client.get("/api/item-pivot/matching/item-name-mapping/import/history/").json()["rows"]
        assert any(h["id"] == decision_id and h["undone"] is True for h in hist)
        assert self.financials() == before  # mapping is classification — no financial value changed

    def test_repeated_undo_is_safe_and_reapproval_needs_a_fresh_selection(self):
        from apps.license.models import ProductIntelAuditEvent
        decision_id = self.approve()
        assert self.undo(decision_id).json()["undone"] is True
        again = self.undo(decision_id)
        assert again.status_code == 200 and again.json() == {"decision_id": decision_id, "undone": False, "already_undone": True, "restored": 0}
        assert ProductIntelAuditEvent.objects.filter(action="import_item_mapping_undone").count() == 1
        key = self.pending()[0]["source_key"]
        refused = self.client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": self.params}, format="json")
        assert refused.status_code == 400 and not self.import_item.items.exists()  # the undone Item Name is not re-applied
        second = self.approve()
        assert second != decision_id and self.approved()["rows"][0]["id"] == second

    def test_undo_refuses_changed_links_unknown_ids_and_viewers(self):
        decision_id = self.approve()
        self.import_item.items.set([self.sugar])  # links changed after the approval (another workflow)
        res = self.undo(decision_id)
        assert res.status_code == 400 and "changed since" in res.json()["detail"]
        assert list(self.import_item.items.values_list("pk", flat=True)) == [self.sugar.pk]  # nothing undone
        assert self.undo(999999).status_code == 400
        viewer = get_user_model().objects.create_user(username="undo-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        self.client.force_authenticate(viewer)
        assert self.undo(decision_id).status_code == 403
        assert self.approved()["can_undo"] is False

    def test_second_undo_after_reapproval_deactivates_the_reactivated_alias(self):
        from apps.license.models import ProductAlias
        first = self.approve()
        assert self.undo(first).json()["undone"] is True
        second = self.approve()  # create_alias reactivates the alias of the first approval (decision FK unchanged)
        assert ProductAlias.objects.filter(is_active=True, item=self.pko).exists()
        assert self.approved()["rows"][0]["id"] == second
        assert self.undo(second).json()["undone"] is True
        assert not ProductAlias.objects.filter(is_active=True, item=self.pko).exists()  # no 100 % suggestion is left behind
        assert self.pending()[0]["band"] != "APPROVED" and list(self.import_item.items.all()) == []
        assert self.approved()["total"] == 0

    def test_an_undone_later_approval_does_not_supersede_the_earlier_one(self):
        from apps.license.models import ProductMatchDecision
        first = self.approve()
        # A later approval of the same source (e.g. consolidation), then undone: the first one is active again.
        d1 = ProductMatchDecision.objects.get(pk=first)
        later = ProductMatchDecision.objects.create(source_key=d1.source_key, source_description=d1.source_description, import_item_ids=d1.import_item_ids,
                                                    chosen_item=self.pko, decision="APPROVED", previous_links=d1.new_links, new_links=d1.new_links, decided_by=self.manager)
        assert [r["id"] for r in self.approved()["rows"]] == [later.pk]
        assert self.undo(first).status_code == 400  # superseded
        assert self.undo(later.pk).json()["undone"] is True  # restores the first approval's links
        assert [r["id"] for r in self.approved()["rows"]] == [first]
        assert self.undo(first).json()["undone"] is True and list(self.import_item.items.all()) == []
