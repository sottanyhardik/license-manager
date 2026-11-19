"""Product matching (deterministic, owner decision 2026-11-18) — suggestions,
compatibility validation, audited approval that links import items to the master
item, reuse of prior decisions, and permissions."""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel, LicenseReplanRequest, ProductMatchDecision
from apps.license.services.item_pivot_intelligence import build_intelligence
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.services.product_matching import (
    MatchValidationError, decide, matching_groups, merge_ai, normalise, product_segments, suggest, text_score,
)
from apps.license.tests.test_item_pivot_intelligence import IntelligenceFixture


@pytest.mark.parametrize("raw,expected", [
    ("Poly Propylene", "polypropylene"), ("PP", "polypropylene"), ("Aluminum Foil", "aluminium foil"), ("Alu Foil", "aluminium foil"),
    ("Sun Flower Oil", "sunflower oil"), ("Natural Flavours", "natural flavour"), ("Natural Flavour", "natural flavour"),
    ("Paper & Paperboard", "paper paper board"), ("Paper and Paper Board", "paper paper board"), ("STARCHES", "starch"),
])
def test_normalisation_handles_spelling_abbreviations_and_plurals(raw, expected):
    assert normalise(raw) == expected


def test_exact_variants_score_100_and_multi_product_descriptions_split():
    assert text_score("Aluminum Foil", "ALUMINIUM FOIL")[0] == 100
    assert text_score("Alu Foil", "Aluminium Foil")[0] == 100
    assert product_segments("HDPE/PP/GRANULES FILM GRADE") == ["hdpe", "polypropylene", "granule film"]


class MatchingTests(IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.foil, _ = ItemNameModel.objects.get_or_create(name="ALUMINIUM FOIL")
        self.foil.sion_norm_class = self.sion
        self.foil.is_active = True
        self.foil.save()
        self.foil.norms.add(self.sion)
        self.sugar.norms.add(self.sion)
        a, b = self.licences
        self.item(a, 9, "39206990", "Aluminium foil (existing)", "1", names=[self.foil])  # gives the master its HSN chapter 39
        self.alu = self.item(a, 1, "39206991", "Alu Foil", "100")
        self.alu_b = self.item(b, 1, "39206991", "alu  foil", "50")
        self.mixed = self.item(b, 2, "39206991", "Alu Foil / LDPE", "10")
        self.wrong_hsn = self.item(b, 3, "21069099", "Aluminum Foil", "5")
        # The import-item save signal auto-links masters; these rows model genuinely unlinked records.
        for row in (self.alu, self.alu_b, self.mixed, self.wrong_hsn):
            row.items.clear()
        self.user = get_user_model().objects.create_user(username="matcher")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])

    def suggestions(self):
        data = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))
        return {s["description"].lower().strip(): merge_ai(s, None) for s in suggest(matching_groups(data))}

    def test_bands_and_conflicts(self):
        sug = self.suggestions()
        alu = next(s for k, s in sug.items() if k.startswith("alu foil") and "ldpe" not in k)
        assert alu["band"] == "HIGH" and alu["suggestion"]["name"] == "ALUMINIUM FOIL" and alu["confidence"] == 100
        assert sorted(alu["import_item_ids"]) == sorted([self.alu.pk, self.alu_b.pk])  # exact duplicates grouped
        assert sug["alu foil / ldpe"]["band"] == "CONFLICT"
        assert sug["aluminum foil"]["band"] == "CONFLICT" and "HSN chapter 21" in sug["aluminum foil"]["conflicts"][0]

    def test_approval_links_items_audits_and_flags_replan_and_is_reused(self):
        alu = next(s for k, s in self.suggestions().items() if k.startswith("alu foil") and "ldpe" not in k)
        from apps.license.models import LicenseDetailsModel
        revisions = dict(LicenseDetailsModel.objects.filter(pk__in=[self.alu.license_id, self.alu_b.license_id]).values_list("pk", "planning_source_revision"))
        [row] = decide(suggestions=[alu], decision=ProductMatchDecision.APPROVED, user=self.user)
        assert list(self.alu.items.values_list("pk", flat=True)) == [self.foil.pk]
        assert row.previous_links == {str(self.alu.pk): [], str(self.alu_b.pk): []}
        assert row.new_links == {str(self.alu.pk): [self.foil.pk], str(self.alu_b.pk): [self.foil.pk]}
        assert row.decided_by == self.user and row.chosen_item == self.foil
        assert LicenseImportItemsModel.objects.get(pk=self.alu.pk).description == "Alu Foil"  # source untouched
        after = dict(LicenseDetailsModel.objects.filter(pk__in=revisions).values_list("pk", "planning_source_revision"))
        assert all(after[pk] > revisions[pk] for pk in revisions)  # each licence flagged for re-planning (not run)
        assert LicenseReplanRequest.objects.filter(license_id__in=revisions).exists()
        # Now mapped: the group leaves the matching queue.
        assert not any(k.startswith("alu foil") and "ldpe" not in k for k in self.suggestions())

    def test_conflicts_cannot_be_approved_and_rejections_are_not_resuggested(self):
        sug = self.suggestions()
        with pytest.raises(MatchValidationError):
            decide(suggestions=[sug["alu foil / ldpe"]], decision=ProductMatchDecision.APPROVED, user=self.user)
        assert not self.mixed.items.exists()
        decide(suggestions=[sug["aluminum foil"]], decision=ProductMatchDecision.REJECTED, user=self.user)
        again = self.suggestions()["aluminum foil"]
        assert again["suggestion"] is None or again["suggestion"]["name"] != "ALUMINIUM FOIL"
        assert again["history"][0]["decision"] == "REJECTED"

    def test_reviewer_choice_is_revalidated_with_full_rules(self):
        """Choosing another master than the suggestion re-runs HSN / multi-product checks for that master."""
        data = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))
        raw = {s["description"].lower().strip(): s for s in suggest(matching_groups(data))}
        row = raw["aluminum foil"]  # HSN chapter 21; ALUMINIUM FOIL's chapter is 39
        finalised = merge_ai(row, None)
        finalised["band"], finalised["conflicts"] = "REVIEW", []  # even if the suggestion itself looked clean
        finalised["suggestion"] = {"item_id": self.sugar.pk, "name": self.sugar.name}
        with pytest.raises(MatchValidationError, match="HSN chapter 21"):
            decide(suggestions=[finalised], decision=ProductMatchDecision.APPROVED, user=self.user, item_id=self.foil.pk,
                   evaluators={row["source_key"]: row["_evaluate"]})
        assert not self.wrong_hsn.items.exists()

    def test_bulk_approval_requires_strong_conflict_free_rows(self):
        sug = self.suggestions()
        alu = next(s for k, s in sug.items() if k.startswith("alu foil") and "ldpe" not in k)
        with pytest.raises(MatchValidationError):
            decide(suggestions=[alu, sug["alu foil / ldpe"]], decision=ProductMatchDecision.APPROVED, user=self.user, bulk=True)
        assert not self.alu.items.exists()  # atomic: nothing applied

    def test_totals_are_preserved_by_consolidation(self):
        def totals():
            data = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))
            return (sum(Decimal(p["entitlement_qty"]) for p in data["products"]), sum(p["source_record_count"] for p in data["products"]), len(data["products"]))
        qty_before, records_before, products_before = totals()
        alu = next(s for k, s in self.suggestions().items() if k.startswith("alu foil") and "ldpe" not in k)
        decide(suggestions=[alu], decision=ProductMatchDecision.APPROVED, user=self.user)
        qty_after, records_after, products_after = totals()
        assert (qty_after, records_after) == (qty_before, records_before)
        assert products_after == products_before - 1

    def test_consolidation_integrity_reproduces_source_totals_before_and_after_approval(self):
        def integrity():
            return build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))["overview"]["integrity"]
        before = integrity()
        assert before["preserved"] is True
        assert before["source_totals"] == before["consolidated_totals"]
        assert before["source_record_count"] == before["consolidated_source_record_count"]
        alu = next(s for k, s in self.suggestions().items() if k.startswith("alu foil") and "ldpe" not in k)
        decide(suggestions=[alu], decision=ProductMatchDecision.APPROVED, user=self.user)
        after = integrity()
        assert after["preserved"] is True
        assert after["source_totals"] == before["source_totals"]  # every financial total unchanged
        assert after["source_record_count"] == before["source_record_count"]
        assert after["consolidated_product_count"] == before["consolidated_product_count"] - 1
        assert after["pending_mapping_count"] == before["pending_mapping_count"] - 1

    def test_match_groups_carry_the_product_key_of_their_report_row(self):
        data = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))
        keys = {p["key"] for p in data["products"] if p["kind"] != "MAPPED"}
        assert {g["product_key"] for g in matching_groups(data)} == keys

    def test_api_permissions_and_server_side_revalidation(self):
        params = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}
        viewer = get_user_model().objects.create_user(username="viewer")
        viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        client = APIClient()
        client.force_authenticate(viewer)
        listing = client.get("/api/item-pivot/matching/", params)
        assert listing.status_code == 200 and listing.data["can_approve"] is False
        key = next(s["source_key"] for s in listing.data["suggestions"] if s["band"] == "CONFLICT")
        assert client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": params}, format="json").status_code == 403
        client.force_authenticate(self.user)
        refused = client.post("/api/item-pivot/matching/decide/", {"source_keys": [key], "decision": "APPROVED", "filters": params}, format="json")
        assert refused.status_code == 400
        assert ProductMatchDecision.objects.count() == 0

    def test_job_api_lifecycle_permissions_and_single_active_job(self):
        from unittest import mock

        from apps.license.models import ProductMatchingJob

        viewer = get_user_model().objects.create_user(username="viewer2")
        client = APIClient()
        client.force_authenticate(viewer)
        assert client.post("/api/item-pivot/matching/jobs/", {}, format="json").status_code == 403
        client.force_authenticate(self.user)
        with mock.patch("apps.license.tasks.run_product_matching_job.delay") as delay:
            started = client.post("/api/item-pivot/matching/jobs/", {"batch_size": 50, "filters": {"sion_norm": "PI1"}}, format="json")
            assert started.status_code == 202
            job = ProductMatchingJob.objects.get()
            assert job.batch_size == 8 and job.status == ProductMatchingJob.QUEUED and job.created_by == self.user
            assert client.post("/api/item-pivot/matching/jobs/", {}, format="json").status_code == 409
            assert client.post(f"/api/item-pivot/matching/jobs/{job.pk}/pause/").status_code == 200
            job.refresh_from_db()
            assert job.pause_requested is True
            assert client.post(f"/api/item-pivot/matching/jobs/{job.pk}/resume/").status_code == 200  # QUEUED: no-op
            ProductMatchingJob.objects.filter(pk=job.pk).update(status=ProductMatchingJob.PAUSED)
            resumed = client.post(f"/api/item-pivot/matching/jobs/{job.pk}/resume/")
            job.refresh_from_db()
            assert resumed.status_code == 200 and job.status == ProductMatchingJob.QUEUED and job.pause_requested is False
            assert [c.args for c in delay.call_args_list] == [(job.pk,), (job.pk,)]
            assert client.post("/api/item-pivot/matching/jobs/999999/pause/").status_code == 404



class SemanticMatchingTests(MatchingTests):
    """Semantic layer with a fake embedder (no model files needed in CI)."""

    def fake_embed(self, texts, *, batch_size=4, before_batch=None):
        import numpy as np
        if before_batch:
            before_batch()
        self.embed_calls.append(len(texts))
        out = []
        for text in texts:
            low = text.lower()
            vec = np.zeros(384, dtype=np.float32)
            vec[0] = 1.0 if ("alu" in low or "foil" in low) else 0.0
            vec[1] = 1.0 if "sugar" in low else 0.0
            vec[2] = 1.0 if "milk" in low else 0.0
            vec[3] = 0.2
            out.append(vec / np.linalg.norm(vec))
        return np.stack(out)

    def setUp(self):
        super().setUp()
        from apps.license.services import product_embedding as pe
        self.embed_calls = []
        self._patches = [(pe, "embed", pe.embed), (pe, "model_version", pe.model_version), (pe, "available_memory_mb", pe.available_memory_mb)]
        pe.embed = self.fake_embed
        pe.model_version = lambda: "fake-minilm"
        pe.available_memory_mb = lambda: 4000.0
        self.job_filters = {"sion_norm": "PI1", "min_balance": -1000000000, "license_status": "all"}

    def tearDown(self):
        for module, name, value in self._patches:
            setattr(module, name, value)
        super().tearDown()

    def run_job(self):
        from apps.license.models import ProductMatchingJob
        from apps.license.services.product_matching_semantic import run_job
        return run_job(ProductMatchingJob.objects.create(filters=self.job_filters, batch_size=4))

    def test_job_persists_embeddings_once_and_records_semantic_candidates(self):
        from apps.license.models import ProductMatchSuggestion, ProductTextEmbedding
        job = self.run_job()
        assert job.status == "DONE" and job.processed == job.total > 0
        first = ProductTextEmbedding.objects.count()
        assert first > 0 and ProductMatchSuggestion.objects.filter(model_version="fake-minilm").exists()
        again = self.run_job()
        assert again.metrics["embedded_new"] == 0 and ProductTextEmbedding.objects.count() == first  # repeated run reuses vectors

    def test_semantic_pick_is_capped_to_review_and_never_clears_conflicts(self):
        from apps.license.services.product_matching_semantic import SEMANTIC_CAP, finalise
        self.run_job()
        data = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))
        rows = {r["description"].lower().strip(): r for r in finalise(suggest(matching_groups(data)))}
        assert rows["alu foil / ldpe"]["band"] == "CONFLICT"
        assert rows["aluminum foil"]["band"] == "CONFLICT"
        for row in rows.values():
            if row.get("matcher") == "fake-minilm":
                assert row["confidence"] <= SEMANTIC_CAP and row["band"] in {"REVIEW", "UNCLASSIFIED", "CONFLICT"}

    def test_memory_pressure_and_user_pause_stop_the_job(self):
        from apps.license.services import product_embedding as pe
        pe.available_memory_mb = lambda: 100.0
        job = self.run_job()
        assert job.status == "PAUSED" and "Memory pressure" in job.metrics["paused_reason"]
        pe.available_memory_mb = lambda: 4000.0
        from apps.license.models import ProductMatchingJob
        from apps.license.services.product_matching_semantic import run_job
        paused = ProductMatchingJob.objects.create(filters=self.job_filters, batch_size=4, pause_requested=True)
        assert run_job(paused).status == "PAUSED"

    def test_unavailable_model_fails_the_job_but_matching_still_works(self):
        from apps.license.services import product_embedding as pe

        def broken(*_a, **_k):
            raise pe.EmbeddingUnavailable("model files missing")
        pe.embed = broken
        assert self.run_job().status == "FAILED"
        alu = next(s for k, s in self.suggestions().items() if k.startswith("alu foil") and "ldpe" not in k)
        assert alu["band"] == "HIGH"  # deterministic matching unaffected

    def test_matching_never_touches_financial_records(self):
        from apps.allotment.models import AllotmentItems
        from apps.bill_of_entry.models import RowDetails
        from apps.license.models import LicenseItemPlan
        before = (LicenseItemPlan.objects.count(), RowDetails.objects.count(), AllotmentItems.objects.count(),
                  list(LicenseImportItemsModel.objects.order_by("pk").values_list("quantity", "cif_fc", "description", "hs_code_id")))
        self.run_job()
        alu = next(s for k, s in self.suggestions().items() if k.startswith("alu foil") and "ldpe" not in k)
        decide(suggestions=[alu], decision=ProductMatchDecision.APPROVED, user=self.user)
        after = (LicenseItemPlan.objects.count(), RowDetails.objects.count(), AllotmentItems.objects.count(),
                 list(LicenseImportItemsModel.objects.order_by("pk").values_list("quantity", "cif_fc", "description", "hs_code_id")))
        assert before == after


def test_real_model_ranks_variants_when_installed():
    """Runs only where the verified model files are installed (dev / server); skipped in CI."""
    from apps.license.services import product_embedding as pe
    from apps.license.services.product_matching_semantic import embedding_text
    try:
        if not pe.files_status()["onnx"]["verified"]:
            pytest.skip("model not installed")
    except pe.EmbeddingUnavailable:
        pytest.skip("unsupported CPU")
    vecs = pe.embed([embedding_text(t) for t in ["PP", "Polypropylene granules", "Aluminium foil", "Alu foil", "Paper board"]])
    sims = vecs @ vecs.T
    assert sims[0, 1] > sims[0, 4] and sims[2, 3] > sims[2, 4]
    long = "Relevant fats and oils namely olive oil / sunflower oil / mustard oil " * 30
    assert pe.embed([long]).shape == (1, 384)  # >256 tokens handled by chunking, nothing dropped



def test_e126_entitlement_aliases_are_norm_scoped():
    from apps.license.services.product_matching import _entitlement_targets
    assert _entitlement_targets("E126", "Refined Sunflower oil") == {"Sunflower Oil": "OLIVE OIL"}
    assert _entitlement_targets("E126", "PKO crude") == {"PKO": "PALM KERNEL OIL"}
    assert set(_entitlement_targets("E126", "Olive oil / Sunflower oil / PKO").values()) == {"OLIVE OIL", "PALM KERNEL OIL"}
    assert _entitlement_targets("E132", "Refined Sunflower oil") == {}  # E126 mapping never applied to E132


def test_e126_validation_blocks_cross_entitlement_and_multi_entitlement_merges():
    from types import SimpleNamespace
    from apps.license.services.product_matching import _validate
    olive = SimpleNamespace(name="OLIVE OIL", norms=SimpleNamespace(all=lambda: [SimpleNamespace(norm_class="E126")]), sion_norm_class_id=None)
    pko = SimpleNamespace(name="PALM KERNEL OIL", norms=SimpleNamespace(all=lambda: [SimpleNamespace(norm_class="E126")]), sion_norm_class_id=None)
    sunflower = {"band": "REVIEW", "conflicts": [], "sion_known": True, "sion": "E126", "entitlement_hits": {"Sunflower Oil": "OLIVE OIL"}}
    _validate(sunflower, olive, allow_review=True)  # Sunflower → Olive Oil entitlement: allowed
    with pytest.raises(MatchValidationError, match="OLIVE OIL"):
        _validate(sunflower, pko, allow_review=True)  # never into PKO
    mixed = {**sunflower, "band": "CONFLICT", "conflicts": ["Description names products of different entitlements"]}
    with pytest.raises(MatchValidationError):
        _validate(mixed, olive, allow_review=True)


@pytest.mark.parametrize("confidence,band", [(100, "HIGH"), (95, "HIGH"), (94, "STRONG"), (90, "STRONG"), (89, "REVIEW"), (80, "REVIEW"), (79, "UNCLASSIFIED")])
def test_confidence_bands_follow_the_owner_spec(confidence, band):
    from apps.license.services.product_matching import _band
    assert _band({"confidence": confidence, "conflicts": [], "suggestion": {"item_id": 1}})["band"] == band


def test_conflicts_override_any_confidence():
    from apps.license.services.product_matching import _band
    assert _band({"confidence": 100, "conflicts": ["different entitlement"], "suggestion": {"item_id": 1}})["band"] == "CONFLICT"


def test_headline_status_is_the_most_severe_cell_status():
    from apps.license.services.item_pivot_intelligence import _headline_status
    assert _headline_status({"CORRECT": 3, "UNDERUTILIZED": 1}) == "UNDERUTILIZED"
    assert _headline_status({"CORRECT": 1, "OVERPLANNED": 1, "WARNING": 2}) == "OVERPLANNED"
    assert _headline_status({"BLOCKED": 2}) == "BLOCKED"
    assert _headline_status({}) is None


@pytest.mark.parametrize("text,expected", [
    # Real licence wording behind "Description lists 2 products (modifier; magnesium oxide soda ash …); SODA ASH covers 1":
    # enumeration markers are separators and the "namely" heading is a label, not a product.
    ("MODIFIERS NAMELY, (A) MAGNESIUM OXIDE (B) SODA ASH (C) SODIUM NITRATE (D) POTASH (E) POTASSIUM NITRATE",
     ["magnesium oxide", "soda ash", "sodium nitrate", "potash", "potassium nitrate"]),
    ("Intermediates namely, (a) Aluminium Oxide 28182000 (b) Zinc oxide", ["aluminium oxide", "zinc oxide"]),
    # Licence condition clauses are restrictions, not products.
    ("Cane Sugar -With the condition the Import of Lactose /Mannitol / Sodium Saccharin and other Artificial Sweetening Agents, "
     "is not allowed as substitute inputs against this item as per PC 13/31.01.2011", ["cane sugar"]),
    # Modifiers and synonyms describe one product.
    ("SODA ASH DENSE / LIGHT", ["soda ash dense"]), ("Soda Ash ( Dense / Light )", ["soda ash"]), ("PP / Polypropylene", ["polypropylene"]),
    # Genuine product lists still split.
    ("Polypropylene Board / LDPE film", ["polypropylene board", "ldpe film"]), ("Alu Foil / LDPE", ["aluminium foil", "ldpe"]),
    ("Relevant fats and oils namely Olive Oil / Sunflower Oil / PKO", ["olive oil", "sunflower oil", "palm kernel oil"]),
])
def test_product_phrase_extraction_on_real_licence_wording(text, expected):
    assert product_segments(text) == expected


def test_single_product_with_modifiers_is_no_longer_a_multi_product_conflict():
    from apps.license.services.product_intelligence.multi_product import detected_products
    assert [d for d, _ in detected_products("SODA ASH DENSE / LIGHT")] == ["SODA ASH DENSE / LIGHT"]


def test_report_rows_with_the_same_normalised_wording_become_one_review_group():
    row = lambda key, desc, ids: {"key": key, "kind": "UNMAPPED", "product": desc, "aliases": [desc], "hsn_codes": ["76071994"], "sion": "E126",
                                  "entitlement_qty": "10.000", "balance_qty": "4.000",
                                  "source_records": [{"import_item_id": i, "license_number": f"L{i}"} for i in ids]}
    groups = matching_groups({"products": [row("U:a", "PACKING MATERIAL - Paper and Paper board / Aluminum Foil", [1, 2]),
                                           row("U:b", "PACKING MATERIAL - Paper and Paper board / Aluminium Foil ", [3])]})
    assert len(groups) == 1
    g = groups[0]
    assert g["import_item_ids"] == [1, 2, 3] and g["product_keys"] == ["U:a", "U:b"] and g["entitlement_qty"] == "20.000"


def test_merged_group_kind_follows_precedence_not_row_order():
    row = lambda key, kind, ids: {"key": key, "kind": kind, "product": "Alu foil / LDPE", "aliases": ["Alu foil / LDPE"], "hsn_codes": ["7607"],
                                  "sion": "E5", "entitlement_qty": "1", "balance_qty": "1",
                                  "source_records": [{"import_item_id": i, "license_number": "L"} for i in ids]}
    groups = matching_groups({"products": [row("M", "MULTI_PRODUCT", [1]), row("U", "UNMAPPED", [2])]})
    assert [g["kind"] for g in groups] == ["UNMAPPED"]
