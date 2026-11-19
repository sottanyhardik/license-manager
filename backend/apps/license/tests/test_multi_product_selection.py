"""Multi-product selection and final classification (owner spec 2026-11-19).

Only explicitly selected, individually validated products become a record's approved classification; the
record's single shared quantity / CIF is never attributed to the products, and master links are untouched.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseImportItemsModel, ProductIntelAuditEvent, ProductMatchSelection
from apps.license.services.item_pivot_intelligence import build_intelligence
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.services.product_intelligence.multi_product import (
    SelectionRejected, decide_products, detected_products, phrase_entitlement,
)
from apps.license.services.product_matching import MatchValidationError, matching_groups, source_key, normalise, suggest
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


def test_detected_products_follow_the_existing_multi_product_split():
    assert [n for _, n in detected_products("Polypropylene Board / LDPE film")] == ["polypropylene board", "ldpe film"]
    assert [d for d, _ in detected_products("PP/LDPE/HDPE")] == ["PP", "LDPE", "HDPE"]


@pytest.mark.parametrize("text,expected", [
    ("Olive oil, subject to FSSAI approval; Sunflower oil", ["olive oil", "sunflower oil"]),  # a clause ends at ";"
    ("Edible oil (Olive oil / Sunflower oil)", ["edible oil", "olive oil", "sunflower oil"]),  # a listing parenthetical stays reviewable
    ("Food Flavours (Edible grade)", ["food flavour"]), ("Soda Ash ( Dense / Light )", ["soda ash"]),
    ("Items (j) Citric acid (k) Malic acid", ["citric acid", "malic acid"]),  # "Items" is a category label
    ("Sugar / Liquid Glucose", ["sugar", "liquid glucose"]),  # "liquid" is not a modifier on its own
])
def test_review_round_three_phrase_extraction(text, expected):
    from apps.license.services.product_matching import product_segments
    assert product_segments(text) == expected


def test_phrase_entitlement_is_norm_scoped():
    assert phrase_entitlement("E126", "Sunflower oil", "15121100") == "OLIVE OIL"
    assert phrase_entitlement("E126", "PKO", "15099010") == "PALM KERNEL OIL"  # the phrase's own wording wins over the record HSN
    assert phrase_entitlement("E126", "Edible oil", "15131900") == "PALM KERNEL OIL"  # no wording → record HSN
    assert phrase_entitlement("E132", "Sunflower oil", "15121100") is None  # E126 rules never applied to E132


class MultiProductTests(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.board = self._master("POLYPROPYLENE BOARD")
        self.ldpe = self._master("LDPE FILM")
        a, b = self.licences
        self.item(a, 8, "39201010", "PP board (existing)", "1", names=[self.board])  # chapter 39 history
        self.item(a, 9, "39201020", "LDPE film (existing)", "1", names=[self.ldpe])
        self.record = self.item(b, 3, "39201099", "Polypropylene Board / LDPE film", "100")
        self.record.items.clear()
        self.manager = get_user_model().objects.create_user(username="multi-manager")
        self.manager.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    def _master(self, name, sion=None):
        item, _ = ItemNameModel.objects.get_or_create(name=name)
        item.sion_norm_class, item.is_active = sion or self.sion, True
        item.save()
        item.norms.add(sion or self.sion)
        return item

    def report(self):
        return build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))

    def row(self):
        rows = [r for r in suggest(matching_groups(self.report())) if r.get("segments")]
        assert len(rows) == 1
        return rows[0]

    def approve(self, selections, partial=False):
        return decide_products(suggestion=self.row(), selections=selections, user=self.manager, partial=partial)

    def approved(self):
        return sorted(ProductMatchSelection.objects.filter(status="APPROVED").values_list("detected_phrase", "item__name"))

    # suggestions -----------------------------------------------------------------------------------
    def test_each_detected_product_gets_its_own_validated_suggestion_and_nothing_is_preselected(self):
        row = self.row()
        assert row["band"] == "CONFLICT"  # one master can never cover the whole description (unchanged safeguard)
        segs = {s["phrase"]: s for s in row["segments"]}
        assert segs["Polypropylene Board"]["suggestion"]["name"] == "POLYPROPYLENE BOARD" and segs["Polypropylene Board"]["compatible"]
        assert segs["LDPE film"]["suggestion"]["name"] == "LDPE FILM"
        assert all(s["approved"] is None for s in row["segments"]) and not ProductMatchSelection.objects.exists()

    # 1 / 2 / 3 -------------------------------------------------------------------------------------
    def test_select_one_of_two_products(self):
        self.approve([{"index": 0, "item_id": self.board.pk}])
        assert self.approved() == [("Polypropylene Board", "POLYPROPYLENE BOARD")]
        assert self.row()["segments"][1]["approved"] is None  # the excluded product stays an unapproved candidate

    def test_select_both_products_are_approved_independently(self):
        self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}])
        assert self.approved() == [("LDPE film", "LDPE FILM"), ("Polypropylene Board", "POLYPROPYLENE BOARD")]

    def test_select_none_approves_nothing(self):
        with pytest.raises(MatchValidationError, match="nothing was approved"):
            self.approve([])
        assert not ProductMatchSelection.objects.exists()

    # 4 / 5 / 9 -------------------------------------------------------------------------------------
    def test_deselecting_revokes_and_resubmitting_is_idempotent(self):
        both = [{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}]
        self.approve(both)
        again = self.approve(both)
        assert again["created"] == [] and again["kept"] == 2 and ProductMatchSelection.objects.count() == 2  # no duplicate mapping
        result = self.approve([{"index": 0, "item_id": self.board.pk}])
        assert len(result["revoked"]) == 1 and self.approved() == [("Polypropylene Board", "POLYPROPYLENE BOARD")]
        revoked = ProductMatchSelection.objects.get(status="REVOKED")
        assert revoked.item_id == self.ldpe.pk and revoked.revoked_by == self.manager

    def test_changing_one_products_master(self):
        film = self._master("PLASTIC FILM")
        self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}])
        self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": film.pk}])
        assert self.approved() == [("LDPE film", "PLASTIC FILM"), ("Polypropylene Board", "POLYPROPYLENE BOARD")]
        latest = ProductMatchSelection.objects.get(status="APPROVED", item=film)
        assert latest.previous_mapping == sorted([self.board.pk, self.ldpe.pk]) and latest.new_mapping == sorted([self.board.pk, film.pk])

    # 6 / 7 / 8 -------------------------------------------------------------------------------------
    def test_conflicting_selection_is_never_approved_and_compatible_one_may_proceed_explicitly(self):
        other_sion = SionNormClassModel.objects.create(head_norm=HeadSIONNormsModel.objects.create(name="Other"), norm_class="PI9", is_active=True)
        foreign = self._master("FOREIGN BOARD", sion=other_sion)  # not legitimate for PI1
        selections = [{"index": 0, "item_id": foreign.pk}, {"index": 1, "item_id": self.ldpe.pk}]
        with pytest.raises(SelectionRejected) as err:
            self.approve(selections)
        results = {r.phrase: r for r in err.value.results}
        assert not results["Polypropylene Board"].ok and "not a legitimate item for PI1" in results["Polypropylene Board"].reasons[0]
        assert results["LDPE film"].ok
        assert not ProductMatchSelection.objects.exists()  # nothing approved silently
        self.approve(selections, partial=True)
        assert self.approved() == [("LDPE film", "LDPE FILM")]

    def test_duplicate_selections_are_rejected(self):
        with pytest.raises(SelectionRejected) as err:
            self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 0, "item_id": self.ldpe.pk}])
        assert any("selected twice" in r for res in err.value.results for r in res.reasons)
        with pytest.raises(SelectionRejected) as err:
            self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.board.pk}])
        assert any("already selected for another product" in r for res in err.value.results for r in res.reasons)

    def test_manually_added_product_is_validated_like_the_others(self):
        with pytest.raises(SelectionRejected):
            self.approve([{"phrase": "Board / film", "item_id": self.board.pk}])  # still several products
        self.approve([{"index": 0, "item_id": self.board.pk}, {"phrase": "Board lamination", "item_id": self.ldpe.pk}])
        assert ("Board lamination", "LDPE FILM") in self.approved()

    # 11 --------------------------------------------------------------------------------------------
    def test_every_individual_decision_is_audited_with_source_context(self):
        self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}])
        for sel in ProductMatchSelection.objects.all():
            assert sel.import_item_ids == [self.record.pk] and sel.source_description == "Polypropylene Board / LDPE film"
            assert sel.hsn_code == "39201099" and sel.sion == self.sion and sel.decided_by == self.manager and sel.decided_on
            assert sel.checks["sion"]["ok"] and sel.segment_index in {0, 1}
        event = ProductIntelAuditEvent.objects.get(action="products_classified")
        assert event.detail["new_mapping"] == sorted([self.board.pk, self.ldpe.pk]) and event.detail["previous_mapping"] == []

    # 12 / 13 / 14 ----------------------------------------------------------------------------------
    def test_only_approved_products_appear_and_shared_amounts_are_never_duplicated(self):
        before = self.report()
        record_rows = [p for p in before["products"] if any(r["import_item_id"] == self.record.pk for r in p["source_records"])]
        assert [p["kind"] for p in record_rows] == ["UNMAPPED"]
        links_before = list(self.record.items.values_list("pk", flat=True))
        self.approve([{"index": 0, "item_id": self.board.pk}])
        after = self.report()
        record_rows = [p for p in after["products"] if any(r["import_item_id"] == self.record.pk for r in p["source_records"])]
        assert len(record_rows) == 1  # counted once — never once per product
        row = record_rows[0]
        assert row["kind"] == "MULTI_PRODUCT" and row["product"] == "POLYPROPYLENE BOARD" and "LDPE" not in row["product"]
        assert row["entitlement_qty"] == "100.000"
        board_row = next(p for p in after["products"] if p["item_name_id"] == self.board.pk)
        assert board_row["entitlement_qty"] == "1.000"  # the shared 100 is NOT attributed to the board master
        assert after["overview"]["integrity"]["preserved"] and after["overview"]["integrity"]["source_totals"] == before["overview"]["integrity"]["source_totals"]
        assert all(c["status"] != "UNDERUTILIZED" for c in after["eligibility"] if c["product_key"] == row["key"])  # not plannable
        assert list(self.record.items.values_list("pk", flat=True)) == links_before  # master links (Auto Plan input) untouched
        assert LicenseImportItemsModel.objects.get(pk=self.record.pk).quantity == Decimal("100")
        assert after["overview"]["consolidation"]["multi_product"] == 1
        # BOE / allotment / billed / available CIF per licence: byte-identical — classification never touches debits.
        keys = ("original_cif", "boe_cif", "allotment_cif", "billed_cif", "available_cif", "planned_cif", "final_balance_cif")
        assert [{k: lic[k] for k in keys} for lic in after["licences"]] == [{k: lic[k] for k in keys} for lic in before["licences"]]
        for field in ("debited_qty", "allotted_qty", "billed_qty", "planned_qty", "planned_cif"):
            assert after["overview"]["integrity"]["source_totals"][field] == before["overview"]["integrity"]["source_totals"][field]
        # Selecting the second product too keeps the record counted once (no per-product duplication).
        self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}])
        again = self.report()
        rows = [p for p in again["products"] if any(r["import_item_id"] == self.record.pk for r in p["source_records"])]
        assert len(rows) == 1 and rows[0]["entitlement_qty"] == "100.000" and rows[0]["product"] == "LDPE FILM + POLYPROPYLENE BOARD"
        assert again["overview"]["integrity"]["source_totals"] == before["overview"]["integrity"]["source_totals"]

    # review round 3 ----------------------------------------------------------------------------
    def test_modifier_merged_phrase_stays_approved_and_resubmission_is_idempotent(self):
        rec = self.item(self.licences[1], 5, "39201099", "PP Board dense / light / LDPE film", "10")
        rec.items.clear()
        rows = [r for r in suggest(matching_groups(self.report())) if r.get("segments") and rec.pk in r["import_item_ids"]]
        row = rows[0]
        assert [s["phrase"] for s in row["segments"]] == ["PP Board dense / light", "LDPE film"]
        sel = [{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}]
        decide_products(suggestion=row, selections=sel, user=self.manager)
        row = [r for r in suggest(matching_groups(self.report())) if r.get("segments") and rec.pk in r["import_item_ids"]][0]
        assert row["segments"][0]["approved"]["item_id"] == self.board.pk  # found again under its segment key
        again = decide_products(suggestion=row, selections=sel, user=self.manager)
        assert again["created"] == [] and again["revoked"] == [] and again["kept"] == 2

    def test_clearing_requires_the_explicit_flag_and_revokes_everything(self):
        self.approve([{"index": 0, "item_id": self.board.pk}, {"index": 1, "item_id": self.ldpe.pk}])
        with pytest.raises(MatchValidationError, match="nothing was approved"):
            self.approve([])  # an empty selection alone never changes anything
        assert ProductMatchSelection.objects.filter(status="APPROVED").count() == 2
        result = decide_products(suggestion=self.row(), selections=[], user=self.manager, clear=True)
        assert len(result["revoked"]) == 2 and not ProductMatchSelection.objects.filter(status="APPROVED").exists()
        assert ProductIntelAuditEvent.objects.filter(action="products_classification_cleared").exists()

    def test_malformed_ids_are_rejected_not_a_server_error(self):
        with pytest.raises(SelectionRejected) as err:
            self.approve([{"index": True, "item_id": self.board.pk}, {"index": 1, "item_id": "²"}])
        reasons = [r for res in err.value.results for r in res.reasons]
        assert "Unknown detected product" in reasons and "Invalid master id" in reasons

    def test_every_hsn_of_a_merged_group_is_checked(self):
        row = self.row()
        row = {**row, "hsn_codes": ["39201099", "21069099"]}  # a merged group spanning a foreign chapter
        with pytest.raises(SelectionRejected) as err:
            decide_products(suggestion=row, selections=[{"index": 0, "item_id": self.board.pk}], user=self.manager)
        assert any("HSN chapter 21" in r for r in err.value.results[0].reasons)

    def test_manual_products_are_flagged_in_the_audit(self):
        self.approve([{"index": 0, "item_id": self.board.pk}, {"phrase": "Board lamination", "item_id": self.ldpe.pk}])
        approved = ProductIntelAuditEvent.objects.get(action="products_classified").detail["approved"]
        assert {a["phrase"]: a["manual"] for a in approved} == {"Polypropylene Board": False, "Board lamination": True}

    # API -------------------------------------------------------------------------------------------
    def test_api_permissions_validation_and_server_side_recompute(self):
        viewer = get_user_model().objects.create_user(username="multi-viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        key = self.row()["source_key"]
        body = {"source_key": key, "selections": [{"index": 0, "item_id": self.board.pk}], "filters": {"sion_norm": "PI1", "license_status": "all", "min_balance": "-1000000000"}}
        client = APIClient()
        client.force_authenticate(viewer)
        assert client.post("/api/item-pivot/matching/decide-products/", body, format="json").status_code == 403
        client.force_authenticate(self.manager)
        bad = client.post("/api/item-pivot/matching/decide-products/", {**body, "selections": [{"index": 0, "item_id": 999999}]}, format="json")
        assert bad.status_code == 400 and bad.json()["results"][0]["ok"] is False
        ok = client.post("/api/item-pivot/matching/decide-products/", body, format="json")
        assert ok.status_code == 201, ok.json()
        assert client.post("/api/item-pivot/matching/decide-products/", {**body, "source_key": "nope"}, format="json").status_code == 400
        masters = client.get("/api/item-pivot/matching/masters/", {"sion": "PI1", "q": "board"}).json()["masters"]
        assert [m["name"] for m in masters] == ["POLYPROPYLENE BOARD"]


class E126MultiProductTests(pivot_fixture.IntelligenceFixture):
    """E126: each oil is validated against its own entitlement; PKO is never accepted as Olive Oil (and vice versa)."""

    def test_entitlements_are_validated_per_product(self):
        e126, _ = SionNormClassModel.objects.get_or_create(norm_class="E126", defaults={"head_norm": self.sion.head_norm, "is_active": True})
        olive, pko = ItemNameModel.objects.get_or_create(name="OLIVE OIL")[0], ItemNameModel.objects.get_or_create(name="PALM KERNEL OIL")[0]
        for item in (olive, pko):
            item.is_active = True
            item.save()
            item.norms.add(e126)
        text = "Olive oil / Sunflower oil / PKO"
        group = {"source_key": source_key(normalise(text), "15099010", "E126"), "kind": "UNMAPPED", "description": text, "aliases": [text],
                 "hsn_code": "15099010", "hsn_codes": ["15099010"], "sion": "E126", "import_item_ids": [], "license_numbers": [], "source_records": []}
        row = suggest([group])[0]
        assert {s["phrase"]: s["entitlement"] for s in row["segments"]} == {"Olive oil": "OLIVE OIL", "Sunflower oil": "OLIVE OIL", "PKO": "PALM KERNEL OIL"}
        user = get_user_model().objects.create_user(username="e126-manager")
        with pytest.raises(SelectionRejected) as err:
            decide_products(suggestion=row, selections=[{"index": 1, "item_id": pko.pk}], user=user)
        reasons = {r.phrase: r.reasons for r in err.value.results}
        assert any("requires OLIVE OIL" in x for x in reasons["Sunflower oil"])  # Sunflower → Olive Oil entitlement only
        decide_products(suggestion=row, selections=[{"index": 1, "item_id": olive.pk}, {"index": 2, "item_id": pko.pk}], user=user)
        assert sorted(ProductMatchSelection.objects.values_list("detected_phrase", "item__name")) == [("PKO", "PALM KERNEL OIL"), ("Sunflower oil", "OLIVE OIL")]
