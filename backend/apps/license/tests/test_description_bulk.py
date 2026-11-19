"""Bulk update of licence import description mappings via filters / selected keys (owner spec 2026-11-19).

Filters select descriptions; each selected description gets its OWN mapping (strict key) applied to all its exact records.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import ImportDescriptionMapping, ImportItemDescriptionMapping, LicenseImportItemsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.product_intelligence import description_bulk as bulk
from apps.license.services.product_intelligence.description_mapping import descriptions, key_hash
from apps.license.services.product_matching import MatchValidationError
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture

URL = "/api/item-pivot/matching/item-name-mapping/import/descriptions/"


class DescriptionBulkTests(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.pko, _ = ItemNameModel.objects.get_or_create(name="PKO")
        self.olive, _ = ItemNameModel.objects.get_or_create(name="OLIVE OIL")
        for n in (self.pko, self.olive):
            n.sion_norm_class, n.is_active = self.sion, True
            n.save()
            n.norms.set([self.sion])
        LicenseImportItemsModel.items.through.objects.filter(itemnamemodel_id__in=[self.pko.pk, self.olive.pk]).delete()
        a, b = self.licences
        self.palm_a = self.item(a, 1, "15131900", "PALM KERNEL OIL", "500")
        self.palm_b = self.item(b, 1, "15131900", "palm  kernel oil", "300")  # same strict key, other wording
        self.crude = self.item(b, 2, "15131900", "CRUDE PALM KERNEL OIL", "200")
        self.nuts = self.item(a, 2, "08021100", "DIETARY NUTS ALMONDS", "10")
        self.user = get_user_model().objects.create_user(username="bulk-manager")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    def links(self, item):
        return sorted(item.items.values_list("pk", flat=True))

    def run_bulk(self, mode, item_ids, **kw):
        p = bulk.preview(mode=mode, **kw)
        return p, bulk.execute(mode=mode, item_ids=item_ids, user=self.user, fingerprint=p["fingerprint"], **kw)

    def test_filter_selects_descriptions_but_each_gets_its_own_mapping(self):
        before = (list(LicenseImportItemsModel.objects.order_by("pk").values_list("description", "quantity", "cif_fc")),
                  LBC.calculate_financial_balance_for_licenses([lic.pk for lic in self.licences]))
        filters = {"logic": "all", "conditions": [{"field": "description", "op": "contains", "value": "palm"}]}
        p, res = self.run_bulk("filter", [self.pko.pk, self.olive.pk], filters=filters)
        assert p["descriptions"] == 2 and p["records"] == 3  # PALM KERNEL OIL (2 wordings, 2 records) + CRUDE … (1)
        assert len(res["succeeded"]) == 2 and not res["failed"]
        assert ImportDescriptionMapping.objects.count() == 2  # two identities — the filter never merges descriptions
        assert set(ImportDescriptionMapping.objects.values_list("description_key", flat=True)) == {"PALM KERNEL OIL", "CRUDE PALM KERNEL OIL"}
        both = sorted([self.pko.pk, self.olive.pk])
        assert self.links(self.palm_a) == self.links(self.palm_b) == self.links(self.crude) == both  # all exact records
        assert self.links(self.nuts) == []  # not selected
        after = (list(LicenseImportItemsModel.objects.order_by("pk").values_list("description", "quantity", "cif_fc")),
                 LBC.calculate_financial_balance_for_licenses([lic.pk for lic in self.licences]))
        assert after == before  # classification only

    def test_negative_filter_and_listing_consistency(self):
        filters = {"logic": "all", "conditions": [{"field": "description", "op": "contains", "value": "OIL"},
                                                   {"field": "description", "op": "not_contains", "value": "CRUDE"},
                                                   {"field": "hsn", "op": "not_starts_with", "value": "0802"}]}
        from apps.license.services.product_intelligence.description_filters import clean_filters
        listed = {r["key"] for r in descriptions(limit=100, filters=clean_filters(filters))["rows"]}
        targets, _ = bulk.resolve_targets(mode="filter", filters=filters)
        assert listed == set(targets) == {"PALM KERNEL OIL"}  # what the user sees is exactly what is updated

    def test_selected_keys_twenty_descriptions_twenty_mappings_and_duplicates_once(self):
        lic = self.licences[0]
        for n in range(20):
            self.item(lic, 100 + n, "15131900", f"OIL GRADE {n:02d}", "1")
        keys = [f"OIL GRADE {n:02d}" for n in range(20)] + ["OIL GRADE 00"]  # duplicate key in the request
        p, res = self.run_bulk("keys", [self.pko.pk], keys=keys)
        assert p["descriptions"] == 20 and len(res["succeeded"]) == 20
        assert ImportDescriptionMapping.objects.filter(description_key__startswith="OIL GRADE").count() == 20

    def test_fingerprint_guards_against_a_changed_target_set(self):
        filters = {"logic": "any", "conditions": [{"field": "description", "op": "contains", "value": "PALM"}]}
        p = bulk.preview(mode="filter", filters=filters)
        self.item(self.licences[0], 9, "15131900", "PALM OLEIN NEW", "1")  # new data matches the filter after review
        with pytest.raises(MatchValidationError, match="changed since you reviewed"):
            bulk.execute(mode="filter", filters=filters, item_ids=[self.pko.pk], user=self.user, fingerprint=p["fingerprint"])
        assert not ImportDescriptionMapping.objects.exists()

    def test_replace_conflicts_and_retry(self):
        self.run_bulk("keys", [self.pko.pk, self.olive.pk], keys=["PALM KERNEL OIL"])
        _, res = self.run_bulk("keys", [self.olive.pk], keys=["PALM KERNEL OIL"])
        assert res["succeeded"][0]["action"] == "REPLACE" and self.links(self.palm_a) == [self.olive.pk]  # stale PKO gone
        _, again = self.run_bulk("keys", [self.olive.pk], keys=["PALM KERNEL OIL"])
        assert again["skipped"] and again["skipped"][0]["action"] == "UNCHANGED"  # retry-safe
        other = SionNormClassModel.objects.create(head_norm=self.sion.head_norm, norm_class="PB2", is_active=True)
        foreign = ItemNameModel.objects.create(name="BULK FOREIGN", sion_norm_class=other, is_active=True)
        foreign.norms.add(other)
        _, res = self.run_bulk("keys", [foreign.pk], keys=["DIETARY NUTS ALMONDS"])
        assert res["succeeded"][0]["conflicts"] == 1 and self.links(self.nuts) == []  # flagged, not assigned
        assert ImportItemDescriptionMapping.objects.get(import_item=self.nuts).status == ImportItemDescriptionMapping.CONFLICT
        with pytest.raises(MatchValidationError):
            bulk.execute(mode="keys", keys=["PALM KERNEL OIL"], item_ids=[], user=self.user, fingerprint="x")

    def test_unique_identity_under_concurrency(self):
        bulk.execute(mode="keys", keys=["PALM KERNEL OIL"], item_ids=[self.pko.pk], user=self.user,
                     fingerprint=bulk.preview(mode="keys", keys=["PALM KERNEL OIL"])["fingerprint"])
        with pytest.raises(IntegrityError), transaction.atomic():
            ImportDescriptionMapping.objects.create(key_hash=key_hash("PALM KERNEL OIL"), description_key="PALM KERNEL OIL", description="x")

    def test_api(self):
        viewer = get_user_model().objects.create_user(username="bulk-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(viewer)
        filters = {"logic": "all", "conditions": [{"field": "hsn", "op": "starts_with", "value": "0802"}]}
        listing = client.get(URL, {"filters": json.dumps(filters), "status": ""}).json()
        assert [r["key"] for r in listing["rows"]] == ["DIETARY NUTS ALMONDS"] and listing["total_records"] == 1
        assert client.get(URL, {"filters": "{bad"}).status_code == 400
        assert client.post(URL + "bulk/preview/", {"mode": "filter", "filters": filters}, format="json").status_code == 403
        client.force_authenticate(self.user)
        assert client.post(URL + "bulk/preview/", {"mode": "filter", "filters": {"conditions": []}}, format="json").status_code == 400  # no "update everything"
        p = client.post(URL + "bulk/preview/", {"mode": "filter", "filters": filters}, format="json").json()
        assert p["descriptions"] == 1 and p["records"] == 1
        bad = client.post(URL + "bulk/apply/", {"mode": "filter", "filters": filters, "item_ids": [self.pko.pk], "fingerprint": "nope"}, format="json")
        assert bad.status_code == 400
        ok = client.post(URL + "bulk/apply/", {"mode": "filter", "filters": filters, "item_ids": [self.pko.pk], "fingerprint": p["fingerprint"]}, format="json")
        assert ok.status_code == 201 and len(ok.json()["succeeded"]) == 1
        assert self.links(self.nuts) == [self.pko.pk]

    def test_select_all_matching_uses_the_tables_status_and_search_too(self):
        self.run_bulk("keys", [self.pko.pk], keys=["PALM KERNEL OIL"])  # now APPLIED
        filters = {"logic": "all", "conditions": [{"field": "description", "op": "contains", "value": "PALM"}]}
        targets, _ = bulk.resolve_targets(mode="filter", filters=filters, status="MAPPING_REQUIRED")
        assert targets == ["CRUDE PALM KERNEL OIL"]  # the applied one is not on the table → not updated
        targets, _ = bulk.resolve_targets(mode="filter", filters=None, q="nuts")
        assert targets == ["DIETARY NUTS ALMONDS"]
        with pytest.raises(MatchValidationError, match="Apply a filter"):
            bulk.resolve_targets(mode="filter", filters=None)


    def test_every_selected_item_name_is_hsn_checked_and_unverifiable_context_is_noted(self):
        sugar_rec = self.item(self.licences[0], 30, "17019990", "REFINED SUGAR", "1", names=[self.sugar])  # sugar → chapter 17
        self.item(self.licences[0], 31, "15131900", "PKO REF", "1", names=[self.pko])                        # PKO → chapter 15
        _, res = self.run_bulk("keys", [self.pko.pk, self.sugar.pk], keys=["DIETARY NUTS ALMONDS"])          # HSN 0802 → both wrong
        assert res["succeeded"][0]["conflicts"] == 1 and res["succeeded"][0]["conflict_details"]
        assert "PKO" in res["succeeded"][0]["conflict_details"][0]["reason"]
        mixed = self.item(self.licences[0], 32, "17019990", "SUGAR PALM MIX", "1")
        _, res = self.run_bulk("keys", [self.pko.pk, self.sugar.pk], keys=["SUGAR PALM MIX"])  # chapter 17 fits sugar, not PKO → conflict
        assert res["succeeded"][0]["conflicts"] == 1 and self.links(mixed) == []
        fresh = ItemNameModel.objects.create(name="BRAND NEW MASTER", sion_norm_class=self.sion, is_active=True)
        fresh.norms.add(self.sion)
        _, res = self.run_bulk("keys", [fresh.pk], keys=["REFINED SUGAR"])  # no HSN history → applied, noted
        assert res["succeeded"][0]["applied"] == 1 and self.links(sugar_rec) == [fresh.pk]
        assert ImportItemDescriptionMapping.objects.get(import_item=sugar_rec).detail.startswith("Not verified: no HSN history")
        row = next(r for r in descriptions(limit=100, status="")["rows"] if r["key"] == "REFINED SUGAR")
        assert row["counts"]["unverified"] == 1

    def test_one_bulk_at_a_time_batch_audit_and_status_codes(self):
        from django.core.cache import cache

        from apps.license.models import ProductIntelAuditEvent
        p = bulk.preview(mode="keys", keys=["PALM KERNEL OIL"])
        cache.add(bulk.LOCK_KEY, "someone-else", timeout=60)
        try:
            with pytest.raises(MatchValidationError, match="Another bulk update is running"):
                bulk.execute(mode="keys", keys=["PALM KERNEL OIL"], item_ids=[self.pko.pk], user=self.user, fingerprint=p["fingerprint"])
        finally:
            cache.delete(bulk.LOCK_KEY)
        res = bulk.execute(mode="keys", keys=["PALM KERNEL OIL"], item_ids=[self.pko.pk], user=self.user, fingerprint=p["fingerprint"])
        summary = ProductIntelAuditEvent.objects.get(action="import_description_bulk")
        assert summary.detail["batch"] == res["batch"] and summary.detail["succeeded"] == 1 and summary.detail["fingerprint"] == p["fingerprint"]
        assert ProductIntelAuditEvent.objects.filter(action="import_description_mapped", detail__batch=res["batch"]).count() == 1
        client = APIClient()
        client.force_authenticate(self.user)
        again = client.post(URL + "bulk/apply/", {"mode": "keys", "keys": ["PALM KERNEL OIL"], "item_ids": [self.pko.pk], "fingerprint": p["fingerprint"]}, format="json")
        assert again.status_code == 200 and again.json()["skipped"]  # nothing written → 200, not 201
        assert client.get(URL, {"filters": json.dumps({"conditions": [{"field": "hsn", "op": ["x"], "value": "1"}]})}).status_code == 400
        assert client.get(URL, {"filters": "[" * 5000}).status_code == 400

    def test_licence_references_counts_and_nested_filter_bulk(self):
        a, b = self.licences
        self.item(a, 40, "15119020", "REFINED PALMOLEIN OIL", "1")
        self.item(b, 41, "15119020", "refined  palmolein oil", "1")
        self.item(b, 42, "15119020", "REFINED PALMOLEIN OIL", "1")  # second record on the same licence
        row = next(r for r in descriptions(limit=100, status="")["rows"] if r["key"] == "REFINED PALMOLEIN OIL")
        assert row["records"] == 3 and row["licence_count"] == 2
        assert row["licences"] == sorted([{"id": a.pk, "license_number": a.license_number}, {"id": b.pk, "license_number": b.license_number}],
                                         key=lambda x: x["license_number"])  # each licence once, real ids
        nested = {"operator": "AND", "conditions": [{"field": "description", "op": "contains", "value": "OIL"},
                                                    {"operator": "OR", "conditions": [{"field": "hsn", "op": "starts_with", "value": "1511"},
                                                                                      {"field": "description", "op": "starts_with", "value": "CRUDE"}]}]}
        p = bulk.preview(mode="filter", filters=nested)
        assert p["descriptions"] == 2 and p["records"] == 4 and p["licence_count"] == 2  # REFINED PALMOLEIN (3) + CRUDE PALM KERNEL (1)
        assert {x["license_number"] for x in p["licences"]} == {a.license_number, b.license_number}
        res = bulk.execute(mode="filter", filters=nested, item_ids=[self.olive.pk], user=self.user, fingerprint=p["fingerprint"])
        assert len(res["succeeded"]) == 2
        assert set(ImportDescriptionMapping.objects.values_list("description_key", flat=True)) == {"REFINED PALMOLEIN OIL", "CRUDE PALM KERNEL OIL"}
        assert self.links(self.crude) == [self.olive.pk] and self.links(self.palm_a) == []  # PALM KERNEL OIL (HSN 1513) not selected
        with self.captureOnCommitCallbacks(execute=True):
            future = self.item(a, 43, "15119020", "Refined Palmolein Oil", "1")
        assert self.links(future) == [self.olive.pk]  # future exact match auto-maps
        row = next(r for r in descriptions(limit=100, status="")["rows"] if r["key"] == "REFINED PALMOLEIN OIL")
        assert row["records"] == 4 and row["licence_count"] == 2  # references refreshed

    def test_bulk_hsn_reference_is_order_independent_and_conflict_licences_are_complete(self):
        fresh = ItemNameModel.objects.create(name="ORDER TEST MASTER", sion_norm_class=self.sion, is_active=True)
        fresh.norms.add(self.sion)
        a_rec = self.item(self.licences[0], 50, "27101990", "A MINERAL OIL", "1")   # processed first (sorted keys)
        b_rec = self.item(self.licences[1], 51, "15091000", "B OLIVE OIL", "1")
        p = bulk.preview(mode="keys", keys=["A MINERAL OIL", "B OLIVE OIL"])
        res = bulk.execute(mode="keys", keys=["A MINERAL OIL", "B OLIVE OIL"], item_ids=[fresh.pk], user=self.user, fingerprint=p["fingerprint"])
        # neither record vouches for the other: both applied with a "Not verified" note, no order-dependent conflict
        assert [e["conflicts"] for e in res["succeeded"]] == [0, 0]
        assert self.links(a_rec) == self.links(b_rec) == [fresh.pk]
        other = SionNormClassModel.objects.create(head_norm=self.sion.head_norm, norm_class="PB3", is_active=True)
        foreign = ItemNameModel.objects.create(name="CONFLICT LICENCES", sion_norm_class=other, is_active=True)
        foreign.norms.add(other)
        p = bulk.preview(mode="keys", keys=["PALM KERNEL OIL"])
        res = bulk.execute(mode="keys", keys=["PALM KERNEL OIL"], item_ids=[foreign.pk], user=self.user, fingerprint=p["fingerprint"])
        assert {x["license_number"] for x in res["succeeded"][0]["conflict_licences"]} == {lic.license_number for lic in self.licences}

    def test_verification_note_is_refreshed_when_context_appears(self):
        fresh = ItemNameModel.objects.create(name="NOTE TEST MASTER", sion_norm_class=self.sion, is_active=True)
        fresh.norms.add(self.sion)
        rec = self.item(self.licences[0], 60, "15119020", "NOTE OIL", "1")
        save = lambda: bulk.execute(mode="keys", keys=["NOTE OIL"], item_ids=[fresh.pk], user=self.user,  # noqa: E731
                                    fingerprint=bulk.preview(mode="keys", keys=["NOTE OIL"])["fingerprint"])
        save()
        assert "no HSN history" in ImportItemDescriptionMapping.objects.get(import_item=rec).detail
        self.item(self.licences[1], 61, "15119090", "OTHER NOTE OIL", "1", names=[fresh])  # now fresh has chapter-15 history
        save()
        assert ImportItemDescriptionMapping.objects.get(import_item=rec).detail == ""
