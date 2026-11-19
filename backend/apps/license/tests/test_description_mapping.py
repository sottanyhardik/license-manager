"""Automatic licence import description → Item Name(s) mapping (owner spec 2026-11-19).

Map each unique description once (one or several existing Item Names); it applies to every existing record with the
exact normalised description and automatically to future ones; new descriptions stay "Mapping Required"; similar but
different wordings never merge; HSN / SION conflicts are flagged; edits REPLACE; quantities / CIF never change.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import (
    ImportDescriptionMapping, ImportDescriptionMappingVersion, ImportItemDescriptionMapping, LicenseImportItemsModel, LicenseReplanRequest, MappingChange,
)
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.product_intelligence.description_mapping import auto_apply, description_key, descriptions, reapply, save_mapping
from apps.license.services.product_matching import MatchValidationError
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


def test_description_key_is_strict():
    assert description_key("  Palm   Kernel Oil ") == description_key("PALM KERNEL OIL") == description_key("palm kernel oil.")
    assert description_key("PALM KERNEL OIL , CRUDE") == description_key("PALM KERNEL OIL,CRUDE")
    assert description_key("Olive Oil – Refined") == description_key("OLIVE OIL - REFINED")
    # meaningful words are never dropped / merged
    assert description_key("CRUDE PALM KERNEL OIL") != description_key("PALM KERNEL OIL")
    assert description_key("RBD PALMOLEIN") != description_key("PALMOLEIN")
    assert description_key("PALM KERNEL OIL (CRUDE)") != description_key("PALM KERNEL OIL CRUDE")
    # punctuation never glues tokens or rewrites numbers
    assert description_key("RBD .PKO") != description_key("RBD.PKO")
    assert description_key("WT 0 .5%") != description_key("WT 0.5%")
    assert description_key("1,000 KG") == "1,000 KG" and description_key("12:30") == "12:30"
    assert description_key("PKO\u200b OIL") == description_key("PKO OIL")
    assert description_key("ITEM NO.") == description_key("ITEM NO")  # trailing full stop only (documented)


class DescriptionMappingTests(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.pko, _ = ItemNameModel.objects.get_or_create(name="PKO")
        self.olive, _ = ItemNameModel.objects.get_or_create(name="OLIVE OIL")
        for n in (self.pko, self.olive, self.sugar):
            n.sion_norm_class, n.is_active = self.sion, True
            n.save()
            n.norms.set([self.sion])
        # seeded masters may carry links; HSN chapters must come from this fixture only
        LicenseImportItemsModel.items.through.objects.filter(itemnamemodel_id__in=[self.pko.pk, self.olive.pk, self.sugar.pk]).delete()
        a, b = self.licences
        self.a1 = self.item(a, 1, "15131900", "Palm Kernel Oil", "500", names=[self.sugar])  # existing (wrong) auto-link
        self.b1 = self.item(b, 1, "15131900", "PALM  KERNEL OIL ", "300")
        self.crude = self.item(b, 2, "15131900", "CRUDE PALM KERNEL OIL", "200")  # similar, different → separate
        self.a1_before = sorted(self.a1.items.values_list("pk", flat=True))  # incl. any pre-existing rule auto-link
        self.user = get_user_model().objects.create_user(username="desc-manager")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    def links(self, *items):
        return [sorted(i.items.values_list("pk", flat=True)) for i in items]

    def financials(self):
        ids = [lic.pk for lic in self.licences]
        return (list(LicenseImportItemsModel.objects.filter(license_id__in=ids).order_by("pk").values_list("description", "quantity", "cif_fc", "cif_inr", "hs_code_id")),
                LBC.calculate_financial_balance_for_licenses(ids))

    def test_one_save_applies_several_item_names_to_every_existing_licence_with_the_same_description(self):
        before = self.financials()
        crude_before = self.links(self.crude)
        res = save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk, self.olive.pk], user=self.user)
        assert res["action"] == "CREATE" and res["applied"] == 2 and res["conflicts"] == 0
        both = sorted([self.pko.pk, self.olive.pk])
        assert self.links(self.a1, self.b1) == [both, both]  # REPLACE: the old auto-link is gone
        assert self.links(self.crude) == crude_before  # similar but different wording is untouched
        assert not ImportItemDescriptionMapping.objects.filter(import_item=self.crude).exists()
        assert self.financials() == before  # descriptions, qty, CIF, balances unchanged; no multiplication
        change = MappingChange.objects.get(kind=MappingChange.DESCRIPTION_MAPPING)
        assert sorted(change.license_ids) == sorted(lic.pk for lic in self.licences)
        assert LicenseReplanRequest.objects.filter(license_id__in=[lic.pk for lic in self.licences]).exists()  # planning re-runs
        statuses = set(ImportItemDescriptionMapping.objects.values_list("status", flat=True))
        assert statuses == {ImportItemDescriptionMapping.APPLIED}
        assert ImportItemDescriptionMapping.objects.get(import_item=self.a1).previous_item_ids == self.a1_before  # audit

    def test_idempotent_save_and_replace_with_version_history(self):
        save_mapping(description="palm kernel oil", item_ids=[self.pko.pk, self.olive.pk], user=self.user)
        again = save_mapping(description="PALM KERNEL OIL", item_ids=[self.olive.pk, self.pko.pk], user=self.user)
        assert again["action"] == "UNCHANGED" and again["applied"] == 0 and again["unchanged"] == 2
        assert MappingChange.objects.filter(kind=MappingChange.DESCRIPTION_MAPPING).count() == 1
        replaced = save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user, expected_version=1)
        assert replaced["action"] == "REPLACE" and replaced["mapping"]["version"] == 2
        assert self.links(self.a1, self.b1) == [[self.pko.pk], [self.pko.pk]]  # no stale Olive link
        v = ImportDescriptionMappingVersion.objects.filter(mapping__description_key="PALM KERNEL OIL").order_by("version")
        assert [(x.action, x.previous_item_ids, x.item_ids) for x in v] == [
            ("CREATE", [], sorted([self.pko.pk, self.olive.pk])), ("REPLACE", sorted([self.pko.pk, self.olive.pk]), [self.pko.pk])]
        with pytest.raises(MatchValidationError, match="changed by someone else"):
            save_mapping(description="PALM KERNEL OIL", item_ids=[self.olive.pk], user=self.user, expected_version=1)

    def test_future_record_is_mapped_automatically_and_new_description_stays_mapping_required(self):
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        with self.captureOnCommitCallbacks(execute=True):
            future = self.item(self.licences[1], 9, "15131900", "Palm kernel oil", "50", names=[self.sugar])
        assert self.links(future) == [[self.pko.pk]]
        assert ImportItemDescriptionMapping.objects.get(import_item=future).status == ImportItemDescriptionMapping.AUTO
        with self.captureOnCommitCallbacks(execute=True):
            new = self.item(self.licences[1], 10, "15131900", "RBD PALMOLEIN", "10")
        # no saved mapping → the description mapping assigns nothing (only the pre-existing rule auto-link may have run)
        pko_not_in = self.pko.pk not in self.links(new)[0]
        assert pko_not_in and not ImportItemDescriptionMapping.objects.filter(import_item=new).exists()
        rows = {r["key"]: r for r in descriptions(limit=100)["rows"]}
        assert rows["RBD PALMOLEIN"]["status"] == "MAPPING_REQUIRED" and rows["RBD PALMOLEIN"]["mapping"] is None
        assert rows["PALM KERNEL OIL"]["status"] == "APPLIED" and rows["PALM KERNEL OIL"]["counts"]["auto"] == 1
        assert rows["CRUDE PALM KERNEL OIL"]["status"] == "MAPPING_REQUIRED"

    def test_sion_and_hsn_conflicts_are_flagged_not_assigned(self):
        other = SionNormClassModel.objects.create(head_norm=self.sion.head_norm, norm_class="PI2", is_active=True)
        foreign = ItemNameModel.objects.create(name="FOREIGN ITEM", sion_norm_class=other, is_active=True)
        foreign.norms.add(other)
        res = save_mapping(description="PALM KERNEL OIL", item_ids=[foreign.pk], user=self.user)
        assert res["applied"] == 0 and res["conflicts"] == 2
        assert self.links(self.a1) == [self.a1_before]  # unchanged
        app = ImportItemDescriptionMapping.objects.get(import_item=self.a1)
        assert app.status == ImportItemDescriptionMapping.CONFLICT and "PI1" in app.detail
        # HSN: PKO already used under chapter 15; a chapter-17 record with the same wording is flagged
        self.item(self.licences[0], 5, "15131900", "PKO SEED", "1", names=[self.pko])
        sweet = self.item(self.licences[0], 6, "17019990", "Palm Kernel Oil", "1")
        sweet_before = self.links(sweet)
        res = save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        assert ImportItemDescriptionMapping.objects.get(import_item=sweet).status == ImportItemDescriptionMapping.CONFLICT
        assert self.links(sweet) == sweet_before and self.pko.pk not in sweet_before[0]
        rows = {r["key"]: r for r in descriptions(limit=100)["rows"]}
        assert rows["PALM KERNEL OIL"]["status"] == "CONFLICT" and rows["PALM KERNEL OIL"]["conflicts"]

    def test_failed_or_partial_propagation_is_retry_safe(self):
        res = save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        # simulate a record that missed propagation (e.g. created by a bulk import without signals)
        ImportItemDescriptionMapping.objects.filter(import_item=self.b1).delete()
        self.b1.items.set([self.sugar])
        row = next(r for r in descriptions(limit=100)["rows"] if r["key"] == "PALM KERNEL OIL")
        assert row["status"] == "PARTIAL" and row["counts"]["stale"] == 1
        first = reapply(res["mapping"]["id"], user=self.user)
        second = reapply(res["mapping"]["id"], user=self.user)
        assert (first["applied"], second["applied"], second["unchanged"]) == (1, 0, 2)
        assert self.links(self.b1) == [[self.pko.pk]]
        assert auto_apply(self.b1.pk) == ImportItemDescriptionMapping.AUTO  # idempotent hook

    def test_validation_and_api(self):
        with pytest.raises(MatchValidationError):
            save_mapping(description="PALM KERNEL OIL", item_ids=[], user=self.user)
        inactive = ItemNameModel.objects.create(name="OLD", sion_norm_class=self.sion, is_active=False)
        with pytest.raises(MatchValidationError, match="active"):
            save_mapping(description="PALM KERNEL OIL", item_ids=[inactive.pk], user=self.user)
        assert not ImportDescriptionMapping.objects.exists()
        viewer = get_user_model().objects.create_user(username="desc-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(viewer)
        url = "/api/item-pivot/matching/item-name-mapping/import/descriptions/"
        listing = client.get(url, {"status": "MAPPING_REQUIRED"})
        assert listing.status_code == 200 and listing.json()["can_apply"] is False
        assert {r["key"] for r in listing.json()["rows"]} >= {"PALM KERNEL OIL", "CRUDE PALM KERNEL OIL"}
        body = {"description": "PALM KERNEL OIL", "item_ids": [self.pko.pk]}
        assert client.post(url + "save/", body, format="json").status_code == 403
        client.force_authenticate(self.user)
        assert client.post(url + "save/", [1], format="json").status_code == 400
        assert client.post(url + "save/", {"description": "PALM KERNEL OIL", "item_ids": ["x"]}, format="json").status_code == 400
        ok = client.post(url + "save/", body, format="json")
        assert ok.status_code == 201 and ok.json()["applied"] == 2
        mid = ok.json()["mapping"]["id"]
        assert client.post(f"{url}{mid}/reapply/", {}, format="json").json()["unchanged"] == 2
        assert client.get("/api/item-pivot/matching/item-name-mapping/import/approved/").status_code == 200  # earlier APIs kept
        assert client.get("/api/item-pivot/matching/item-name-mapping/boe/").status_code == 200
        assert client.get("/api/item-pivot/matching/", {"sion_norm": "PI1", "license_status": "all", "min_balance": -1000000000}).status_code == 200

    def test_item_pivot_groups_by_the_applied_item_names(self):
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        rows = [p for p in self.report()["products"] if p["item_name_id"] == self.pko.pk]
        assert rows and {r["import_item_id"] for p in rows for r in p["source_records"]} >= {self.a1.pk, self.b1.pk}

    def test_hook_runs_only_for_new_or_redescribed_records_and_never_reverts_manual_links(self):
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        self.a1.items.set([self.olive])  # manual re-link after the mapping was applied
        a1 = LicenseImportItemsModel.objects.get(pk=self.a1.pk)
        with self.captureOnCommitCallbacks(execute=True):
            a1.quantity = Decimal("501")
            a1.save()
        assert self.links(self.a1) == [[self.olive.pk]]  # not reverted by an unrelated save
        row = next(r for r in descriptions(limit=100)["rows"] if r["key"] == "PALM KERNEL OIL")
        assert row["status"] == "PARTIAL"  # drift is visible; Retry re-applies
        crude = LicenseImportItemsModel.objects.get(pk=self.crude.pk)
        with self.captureOnCommitCallbacks(execute=True):
            crude.description = "palm kernel oil"  # re-described → now the exact mapped description
            crude.save()
        assert self.links(self.crude) == [[self.pko.pk]]
        assert ImportItemDescriptionMapping.objects.get(import_item=self.crude).status == ImportItemDescriptionMapping.AUTO

    def test_hook_failure_is_logged_not_raised(self):
        from unittest import mock
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        with mock.patch("apps.license.services.product_intelligence.description_mapping.auto_apply", side_effect=RuntimeError("boom")), \
                self.assertLogs("apps.license.signals", level="ERROR"), self.captureOnCommitCallbacks(execute=True):
            self.item(self.licences[0], 11, "15131900", "Palm Kernel Oil", "5")

    def test_api_requires_the_seen_version_to_edit_and_caps_description_length(self):
        client = APIClient()
        client.force_authenticate(self.user)
        url = "/api/item-pivot/matching/item-name-mapping/import/descriptions/save/"
        assert client.post(url, {"description": "PALM KERNEL OIL", "item_ids": [self.pko.pk]}, format="json").status_code == 201
        stale = client.post(url, {"description": "PALM KERNEL OIL", "item_ids": [self.olive.pk]}, format="json")
        assert stale.status_code == 400 and "already has a mapping" in stale.json()["detail"]
        ok = client.post(url, {"description": "PALM KERNEL OIL", "item_ids": [self.olive.pk], "expected_version": 1}, format="json")
        assert ok.status_code == 201 and ok.json()["action"] == "REPLACE"
        assert client.post(url, {"description": "X" * 2001, "item_ids": [self.pko.pk]}, format="json").status_code == 400

    def test_rule_auto_link_is_replaced_new_unmapped_items_stay_empty_and_bulk_saves_apply_mappings(self):
        """Owner decision 2026-11-19 ("replace"): no rule-based guess; only exact saved description mappings link."""
        from apps.core.models import HSCodeModel
        from apps.license.utils.item_matcher import RULE_AUTO_LINK, bulk_auto_link_license_items
        assert RULE_AUTO_LINK is False
        with self.captureOnCommitCallbacks(execute=True):
            unmapped = self.item(self.licences[0], 20, "15131900", "OLIVE OIL EXTRA VIRGIN", "5")
        assert self.links(unmapped) == [[]]  # stays empty → Mapping Required
        save_mapping(description="PALM KERNEL OIL", item_ids=[self.pko.pk], user=self.user)
        code = HSCodeModel.objects.get(hs_code="15131900")
        LicenseImportItemsModel.objects.bulk_create([  # bulk imports send no post_save
            LicenseImportItemsModel(license=self.licences[0], serial_number=21, hs_code=code, description="palm kernel oil", quantity=Decimal("1")),
            LicenseImportItemsModel(license=self.licences[0], serial_number=22, hs_code=code, description="SOMETHING NEW", quantity=Decimal("1")),
        ])
        assert bulk_auto_link_license_items(self.licences[0]) == 1
        bulk = {r.description: r for r in LicenseImportItemsModel.objects.filter(license=self.licences[0], serial_number__in=[21, 22])}
        assert self.links(bulk["palm kernel oil"]) == [[self.pko.pk]] and self.links(bulk["SOMETHING NEW"]) == [[]]
