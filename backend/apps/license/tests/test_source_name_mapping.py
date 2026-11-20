"""BOE Product Name / Allotment Item Name → Planning Target Item saved mappings (owner spec 2026-11-19).

Map each unique source name once; it applies to every existing record with the exact normalised name and automatically
to future ones; new names stay "Mapping Required"; similar names never merge; BOE / allotment / import identities never
mix; illegitimate targets are conflicts (record unchanged); edits REPLACE; quantities / CIF / balances never change.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.models import ItemNameModel
from apps.license.models import (
    ImportDescriptionMapping, LicenseReplanRequest, MappingChange, ProductIntelAuditEvent, SourceNameMapping, SourceNameMappingRecord,
    SourceNameMappingVersion,
)
from apps.license.services.planning_usage_reconciliation import aggregate_license_usage
from apps.license.services.product_intelligence.item_name_mapping import counts
from apps.license.services.product_intelligence.description_mapping import description_key
from apps.license.services.product_intelligence.source_name_mapping import (
    auto_apply, bulk_execute, bulk_preview, names, reapply, save_mapping,
)
from apps.license.services.product_matching import MatchValidationError
from apps.core.constants import DEBIT
from apps.license.tests.test_item_name_mapping import _MappingFixture

BASE = "/api/item-pivot/matching/item-name-mapping/"


class SourceNameMappingTests(_MappingFixture):
    def setUp(self):
        super().setUp()
        a, _ = self.licences
        # A second BOE with the same Product Name in other spacing / case, and a similar-but-different name.
        self.boe2 = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="987654322", bill_of_entry_date=a.license_date,
                                                    exchange_rate=Decimal("84.50"), product_name="crude  palm kernel oil.")
        self.boe2_row = RowDetails.objects.create(bill_of_entry=self.boe2, sr_number=self.import_item, transaction_type=DEBIT,
                                                  cif_inr=Decimal("4225"), cif_fc=Decimal("50"), qty=Decimal("10"))
        self.boe_other = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="987654323", bill_of_entry_date=a.license_date,
                                                         exchange_rate=Decimal("84.50"), product_name="RBD PALM KERNEL OIL")
        BillOfEntryModel.objects.filter(pk__in=[self.boe2.pk, self.boe_other.pk]).update(
            planning_target_item=None, planning_mapping_status="UNMAPPED_AMBIGUOUS", planning_mapping_source="")

    def row(self, kind, name):
        return next((r for r in names(kind, limit=100)["rows"] if r["key"] == description_key(name)), None)

    def header(self, model, pk):
        return model.objects.values_list("planning_target_item_id", "planning_mapping_status", "planning_mapping_source").get(pk=pk)

    # 1, 2, 9, 10 — grouping, exact normalisation, similar names separate, separate identities per source
    def test_unique_name_grouping_per_source_and_strict_identity(self):
        boe_row = self.row("boe", "CRUDE PALM KERNEL OIL")
        assert boe_row["records"] == 2 and boe_row["wordings"] == 2 and boe_row["status"] == "MAPPING_REQUIRED" and boe_row["mapping"] is None
        assert self.row("boe", "RBD PALM KERNEL OIL")["records"] == 1  # similar wording → own row
        allot = self.row("allotment", "PALM KERNEL OIL (CRUDE)")
        assert allot["records"] == 1 and allot["status"] == "MAPPING_REQUIRED"
        # 14 — licence references: distinct licences of the debited import items
        assert boe_row["licence_count"] == 1 and names("boe", limit=100)["rows"]  # page rows carry refs
        page_row = next(r for r in names("boe", limit=100)["rows"] if r["key"] == boe_row["key"])
        assert page_row["licences"] == [{"id": self.licences[0].pk, "license_number": self.licences[0].license_number}]

    # 4, 5, 11, 15, 16, 17 — save, reopen, propagate, REPLACE, planning integration, sources + financials unchanged
    def test_save_propagates_to_every_matching_record_and_planning_uses_it(self):
        before = self.financials()
        res = save_mapping(kind="boe", name="Crude Palm Kernel Oil", target_id=self.pko.pk, user=self.manager)
        assert res["action"] == "CREATE" and res["applied"] == 2 and res["conflicts"] == 0 and res["unverified"] == 0
        for pk in (self.boe.pk, self.boe2.pk):
            assert self.header(BillOfEntryModel, pk) == (self.pko.pk, "MAPPED_EXPLICIT", "NAME_MAPPING")
        assert self.header(BillOfEntryModel, self.boe_other.pk) == (None, "UNMAPPED_AMBIGUOUS", "")  # different name untouched
        assert self.header(AllotmentModel, self.allotment.pk)[0] is None  # other source never touched
        assert not ImportDescriptionMapping.objects.exists()
        # reopen: saved mapping loads
        reopened = self.row("boe", "CRUDE PALM KERNEL OIL")
        assert reopened["status"] == "APPLIED" and reopened["mapping"]["target"] == {"item_id": self.pko.pk, "name": "PKO"}
        # planning: usage of the debited import item is reconciled against PKO
        usage = aggregate_license_usage(self.licences[0].pk)
        assert (self.import_item.pk, self.pko.pk) in usage["mapped"]
        assert usage["mapped"][(self.import_item.pk, self.pko.pk)]["boe_used_cif"] == Decimal("150")  # each debit once, never multiplied
        # versioning, re-plan and audit
        change = MappingChange.objects.get(kind=MappingChange.BOE_TARGET)
        assert change.license_ids == [self.licences[0].pk] and sorted(change.source_refs) == sorted([self.boe.pk, self.boe2.pk])
        assert LicenseReplanRequest.objects.filter(license=self.licences[0], reason="debit_target_changed").exists()
        assert SourceNameMappingVersion.objects.get().action == "CREATE"
        assert ProductIntelAuditEvent.objects.filter(action="boe_name_mapped").count() == 1
        app = SourceNameMappingRecord.objects.get(kind="BOE", record_id=self.boe.pk)
        assert (app.previous_target_id, app.previous_status, app.verified) == (None, "UNMAPPED_AMBIGUOUS", True)
        assert self.financials() == before  # names, qty, CIF, debit rows, allotments, balances unchanged

        # idempotent
        again = save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager,
                             expected_version=res["mapping"]["version"])
        assert again["action"] == "UNCHANGED" and again["applied"] == 0 and again["unchanged"] == 2
        assert MappingChange.objects.filter(kind=MappingChange.BOE_TARGET).count() == 1

        # REPLACE with an illegitimate target → conflict: this mapping's target is withdrawn, the record restored
        replaced = save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.sugar.pk, user=self.manager, expected_version=1)
        assert replaced["action"] == "REPLACE" and replaced["conflicts"] == 2 and replaced["applied"] == 0
        assert self.header(BillOfEntryModel, self.boe.pk) == (None, "UNMAPPED_AMBIGUOUS", "")
        assert "not a legitimate planning target" in replaced["conflict_details"][0]["reason"]
        assert replaced["conflict_licences"] == [{"id": self.licences[0].pk, "license_number": self.licences[0].license_number}]
        assert self.row("boe", "CRUDE PALM KERNEL OIL")["status"] == "CONFLICT"
        assert list(SourceNameMappingVersion.objects.order_by("pk").values_list("action", "target_id_value", "previous_target_id")) == [
            ("CREATE", self.pko.pk, None), ("REPLACE", self.sugar.pk, self.pko.pk)]
        with pytest.raises(MatchValidationError, match="changed by someone else"):
            save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager, expected_version=1)
        assert self.financials() == before

    # 6, 7, 8 — future records auto-map; new names stay Mapping Required
    def test_future_boe_and_allotment_records_are_mapped_automatically(self):
        save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager)
        save_mapping(kind="allotment", name="PALM KERNEL OIL (CRUDE)", target_id=self.pko.pk, user=self.manager)
        a = self.licences[0]
        with self.captureOnCommitCallbacks(execute=True):
            new_boe = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="987654399", bill_of_entry_date=a.license_date,
                                                      exchange_rate=Decimal("84.50"), product_name="CRUDE PALM KERNEL OIL")
            RowDetails.objects.create(bill_of_entry=new_boe, sr_number=self.import_item, transaction_type=DEBIT,
                                      cif_inr=Decimal("845"), cif_fc=Decimal("10"), qty=Decimal("2"))
        assert self.header(BillOfEntryModel, new_boe.pk) == (self.pko.pk, "MAPPED_EXPLICIT", "NAME_MAPPING")
        assert SourceNameMappingRecord.objects.get(kind="BOE", record_id=new_boe.pk).status == "AUTO"
        # an allotment is created before its debits: target stored but NOT verified (planning keeps it unmapped) …
        with self.captureOnCommitCallbacks(execute=True):
            new_allot = AllotmentModel.objects.create(company=self.company, item_name="palm kernel oil (crude)", required_quantity=Decimal("5"))
        assert self.header(AllotmentModel, new_allot.pk) == (self.pko.pk, "UNMAPPED_NO_TARGET", "NAME_MAPPING")
        app = SourceNameMappingRecord.objects.get(kind="ALLOTMENT", record_id=new_allot.pk)
        assert not app.verified and "no licence debit" in app.detail
        assert self.row("allotment", "PALM KERNEL OIL (CRUDE)")["counts"]["unverified"] == 1
        # … and verified as soon as a debit is recorded
        with self.captureOnCommitCallbacks(execute=True):
            AllotmentItems.objects.create(allotment=new_allot, item=self.import_item, qty=Decimal("5"), cif_fc=Decimal("5"), cif_inr=Decimal("422"))
        assert self.header(AllotmentModel, new_allot.pk) == (self.pko.pk, "MAPPED_EXPLICIT", "NAME_MAPPING")
        assert SourceNameMappingRecord.objects.get(kind="ALLOTMENT", record_id=new_allot.pk).verified
        # a new, unmapped name stays empty and Mapping Required
        with self.captureOnCommitCallbacks(execute=True):
            fresh = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="987654398", bill_of_entry_date=a.license_date,
                                                    exchange_rate=Decimal("84.50"), product_name="PALM KERNEL OIL REFINED")
        assert self.header(BillOfEntryModel, fresh.pk)[0] is None
        assert self.row("boe", "PALM KERNEL OIL REFINED")["status"] == "MAPPING_REQUIRED"
        assert auto_apply("boe", fresh.pk) is None
        # renaming a record to a mapped name maps it
        with self.captureOnCommitCallbacks(execute=True):
            fresh.product_name = "Crude Palm Kernel Oil"
            fresh.save(update_fields=["product_name"])
        assert self.header(BillOfEntryModel, fresh.pk)[0] == self.pko.pk
        # an unrelated save never touches the target
        BillOfEntryModel.objects.filter(pk=new_boe.pk).update(planning_target_item=self.sugar)
        with self.captureOnCommitCallbacks(execute=True):
            obj = BillOfEntryModel.objects.get(pk=new_boe.pk)
            obj.bill_of_entry_number = "987654397"
            obj.save(update_fields=["bill_of_entry_number"])
        assert self.header(BillOfEntryModel, new_boe.pk)[0] == self.sugar.pk
        assert self.row("boe", "CRUDE PALM KERNEL OIL")["status"] == "PARTIAL"  # target changed elsewhere → Retry
        res = reapply("boe", SourceNameMapping.objects.get(kind="BOE").pk, user=self.manager)
        assert res["applied"] == 1 and self.header(BillOfEntryModel, new_boe.pk)[0] == self.pko.pk

    def test_no_planning_rule_is_not_verified_and_an_existing_valid_target_is_never_overwritten(self):
        from apps.license.models import SionPlanningRule

        SionPlanningRule.objects.filter(sion=self.sion).update(is_active=False)  # no rule configured → cannot verify
        res = save_mapping(kind="allotment", name="PALM KERNEL OIL (CRUDE)", target_id=self.pko.pk, user=self.manager)
        assert res["applied"] == 1 and res["unverified"] == 1 and res["conflicts"] == 0
        assert self.header(AllotmentModel, self.allotment.pk) == (self.pko.pk, "UNMAPPED_NO_TARGET", "NAME_MAPPING")
        usage = aggregate_license_usage(self.licences[0].pk)
        assert not any(k[1] == self.pko.pk for k in usage["mapped"])  # an unverified target never feeds planning
        # a record that already holds a valid target keeps it when the new one cannot be verified
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=self.sugar, planning_mapping_status="MAPPED_EXPLICIT",
                                                               planning_mapping_source="USER_SELECTED")
        res = save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager)
        assert res["conflicts"] == 1 and self.header(BillOfEntryModel, self.boe.pk) == (self.sugar.pk, "MAPPED_EXPLICIT", "USER_SELECTED")

    def test_validation(self):
        inactive = ItemNameModel.objects.create(name="PKO OLD", is_active=False)
        for bad in (None, 0, True, "1", inactive.pk, 10**9):
            with pytest.raises(MatchValidationError):
                save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=bad, user=self.manager)
        for name in ("", "   ", "x" * 256):
            with pytest.raises(MatchValidationError):
                save_mapping(kind="boe", name=name, target_id=self.pko.pk, user=self.manager)
        assert not SourceNameMapping.objects.exists()

    # 12, 13 — bulk with nested filters: each name its own mapping; fingerprint guard
    def test_bulk_with_nested_filters_maps_each_name_separately(self):
        flt = {"operator": "AND", "conditions": [{"field": "description", "op": "contains", "value": "PALM KERNEL"},
                                                 {"operator": "OR", "conditions": [{"field": "description", "op": "starts_with", "value": "CRUDE"},
                                                                                   {"field": "description", "op": "starts_with", "value": "RBD"}]}]}
        pre = bulk_preview("boe", mode="filter", filters=flt)
        assert pre["descriptions"] == 2 and pre["records"] == 3 and pre["licence_count"] == 1 and not pre["too_many"]
        with pytest.raises(MatchValidationError, match="changed since"):
            bulk_execute("boe", mode="filter", filters=flt, target_id=self.pko.pk, user=self.manager, fingerprint="x")
        out = bulk_execute("boe", mode="filter", filters=flt, target_id=self.pko.pk, user=self.manager, fingerprint=pre["fingerprint"])
        assert len(out["succeeded"]) == 2 and not out["failed"]
        assert SourceNameMapping.objects.filter(kind="BOE").count() == 2  # one mapping per name — never merged by the filter
        assert self.header(BillOfEntryModel, self.boe.pk)[0] == self.pko.pk
        # the RBD BOE debits nothing → stored, not verified
        assert self.header(BillOfEntryModel, self.boe_other.pk) == (self.pko.pk, "UNMAPPED_NO_TARGET", "NAME_MAPPING")
        assert ProductIntelAuditEvent.objects.filter(action="boe_name_bulk").count() == 1
        neg = {"operator": "AND", "conditions": [{"field": "description", "op": "not_contains", "value": "CRUDE"}]}
        assert all("CRUDE" not in r["key"] for r in names("boe", filters=neg, limit=100)["rows"])

    def test_counts_track_saved_name_mappings(self):
        before = counts(fresh=True)
        save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager)
        after = counts(fresh=True)
        assert after["boe"]["descriptions"] == before["boe"]["descriptions"] - 1 and after["boe"]["records"] == before["boe"]["records"] - 2
        assert after["allotment"] == before["allotment"]

    def test_api_permissions_and_contract(self):
        client = APIClient()
        client.force_authenticate(self.manager)
        listing = client.get(f"{BASE}boe/names/", {"status": "MAPPING_REQUIRED"})
        assert listing.status_code == 200 and listing.data["can_apply"] and listing.data["total"] >= 2
        bad = client.get(f"{BASE}boe/names/", {"filters": "{"})
        assert bad.status_code == 400
        saved = client.post(f"{BASE}allotment/names/save/", {"name": "PALM KERNEL OIL (CRUDE)", "target_id": self.pko.pk}, format="json")
        assert saved.status_code == 201 and saved.data["applied"] == 1
        need_version = client.post(f"{BASE}allotment/names/save/", {"name": "PALM KERNEL OIL (CRUDE)", "target_id": self.pko.pk}, format="json")
        assert need_version.status_code == 400  # an existing mapping is edited with the version the user saw
        assert client.post(f"{BASE}allotment/names/{saved.data['mapping']['id']}/reapply/", {}, format="json").status_code == 200
        assert client.post(f"{BASE}boe/names/bulk/preview/", {"mode": "keys", "keys": ["CRUDE PALM KERNEL OIL"]}, format="json").data["records"] == 2
        assert client.post(f"{BASE}boe/names/save/", ["x"], format="json").status_code == 400
        from django.contrib.auth import get_user_model

        viewer = get_user_model().objects.create_user(username="names-viewer")
        client.force_authenticate(viewer)
        assert client.post(f"{BASE}boe/names/save/", {"name": "X", "target_id": self.pko.pk}, format="json").status_code == 403
        assert client.post(f"{BASE}boe/names/bulk/apply/", {"mode": "keys", "keys": ["X"]}, format="json").status_code == 403

    # review fixes: never downgrade / silently replace a valid target; debit re-point and delete re-check
    def test_unverifiable_mapping_never_downgrades_a_valid_target_even_the_same_one(self):
        from apps.license.models import SionPlanningRule

        SionPlanningRule.objects.filter(sion=self.sion).update(is_active=False)
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=self.pko, planning_mapping_status="MAPPED_EXPLICIT",
                                                               planning_mapping_source="USER_SELECTED")
        BillOfEntryModel.objects.filter(pk=self.boe_other.pk).update(planning_target_item=self.sugar, planning_mapping_status="MAPPED_EXPLICIT",
                                                                     planning_mapping_source="USER_SELECTED")  # no debits
        first = save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager)
        save_mapping(kind="boe", name="RBD PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager)
        assert first["kept"] == 1  # the kept record has its own count (not counted as newly unverified)
        assert self.header(BillOfEntryModel, self.boe.pk) == (self.pko.pk, "MAPPED_EXPLICIT", "USER_SELECTED")
        assert self.header(BillOfEntryModel, self.boe_other.pk) == (self.sugar.pk, "MAPPED_EXPLICIT", "USER_SELECTED")
        # same target already held → kept and shown "Not verified", not a conflict; another target → conflict
        kept = SourceNameMappingRecord.objects.get(kind="BOE", record_id=self.boe.pk)
        assert (kept.status, kept.verified) == ("APPLIED", False) and "kept as it is" in kept.detail
        assert SourceNameMappingRecord.objects.get(kind="BOE", record_id=self.boe_other.pk).status == "CONFLICT"

    def test_automatic_recheck_never_replaces_a_target_chosen_on_the_record(self):
        save_mapping(kind="boe", name="CRUDE PALM KERNEL OIL", target_id=self.pko.pk, user=self.manager)
        other, _ = ItemNameModel.objects.get_or_create(name="PKO SPLIT")
        BillOfEntryModel.objects.filter(pk=self.boe.pk).update(planning_target_item=other, planning_mapping_status="MAPPED_EXPLICIT",
                                                               planning_mapping_source="USER_SELECTED")
        second = self.item(self.licences[0], 2, "15131900", "PALM KERNEL OIL GRADE 2", "100")
        with self.captureOnCommitCallbacks(execute=True):
            RowDetails.objects.create(bill_of_entry=self.boe, sr_number=second, transaction_type=DEBIT,
                                      cif_inr=Decimal("845"), cif_fc=Decimal("10"), qty=Decimal("2"))
        assert self.header(BillOfEntryModel, self.boe.pk) == (other.pk, "MAPPED_EXPLICIT", "USER_SELECTED")
        assert self.row("boe", "CRUDE PALM KERNEL OIL")["status"] == "PARTIAL"  # visible; explicit Retry replaces it

    def test_debit_rows_queue_one_recheck_and_repoint_or_delete_rechecks(self):
        save_mapping(kind="allotment", name="PALM KERNEL OIL (CRUDE)", target_id=self.pko.pk, user=self.manager)
        assert self.header(AllotmentModel, self.allotment.pk)[1] == "MAPPED_EXPLICIT"
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            for n in range(3):
                extra = self.item(self.licences[0], 10 + n, "15131900", f"PALM KERNEL OIL LOT {n}", "100")
                AllotmentItems.objects.create(allotment=self.allotment, item=extra, qty=Decimal("1"), cif_fc=Decimal("1"), cif_inr=Decimal("84"))
        from django.db import transaction

        pending = [e for e in transaction.get_connection().run_on_commit if getattr(e[1], "_source_name_marker", None) == ("allotment", self.allotment.pk)]
        assert len(pending) == 1 and len(callbacks) >= 1  # one queued re-check for the header, not one per row
        pending[0][1]._source_name_marker = None  # TestCase never commits: retire the queued marker as a real commit would
        with self.captureOnCommitCallbacks(execute=True):
            AllotmentItems.objects.filter(allotment=self.allotment).delete()  # queryset delete sends post_delete per row
        assert self.header(AllotmentModel, self.allotment.pk) == (self.pko.pk, "UNMAPPED_NO_TARGET", "NAME_MAPPING")  # no debit → not verified
