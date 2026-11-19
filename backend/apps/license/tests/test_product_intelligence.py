"""Product Intelligence Engine (owner spec 2026-11-19): our own database-trained matching layer.

Labels used here are test fixtures created in the test database — the production
pipeline only ever trains on human ``ProductMatchDecision`` rows and USER_SELECTED
BOE / allotment targets.
"""
import json
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.test import APIClient

from apps.core.models import ItemNameModel, SionNormClassModel
from apps.license.models import (
    LicenseImportItemsModel, ProductAlias, ProductIntelAuditEvent, ProductIntelModel, ProductMatchDecision,
)
from apps.license.services.item_pivot_intelligence import build_intelligence
from apps.license.services.item_pivot_selection import select_pivot_licenses
from apps.license.services.product_intelligence import knowledge, learn, lifecycle
from apps.license.services.product_intelligence.aliases import create_alias
from apps.license.services.product_intelligence.features import FEATURE_NAMES, FINANCIAL_TERMS, PairContext, TfidfIndex, pair_features
from apps.license.services.product_intelligence.resolver import resolve
from apps.license.services.product_matching import MatchValidationError, decide, matching_groups, suggest
from apps.license.services.product_matching_semantic import finalise
from apps.license.tests import test_item_pivot_intelligence as pivot_fixture


# ---- pure units ---------------------------------------------------------------------------------

def test_feature_set_never_contains_financial_fields():
    assert not [n for n in FEATURE_NAMES if any(term in n for term in FINANCIAL_TERMS)]
    x = pair_features("Aluminium foil", "ALUMINIUM FOIL", PairContext(hsn="76071994"))
    assert x.shape == (len(FEATURE_NAMES),) and x[FEATURE_NAMES.index("exact_normalised")] == 1.0


@pytest.mark.parametrize("query,expected", [("Aluminum Foil", "foil"), ("Alu foil 7607", "foil"), ("Poly Propylene granules", "pp"),
                                            ("Sun Flower Oil", "sunflower"), ("Paper & Paperboard", "paper")])
def test_tfidf_index_ranks_spelling_and_abbreviation_variants_first(query, expected):
    index = TfidfIndex({"foil": "ALUMINIUM FOIL", "pp": "POLYPROPYLENE", "sunflower": "SUNFLOWER OIL", "paper": "PAPER AND PAPER BOARD", "sugar": "SUGAR"})
    assert index.top_k(query, 1)[0][0] == expected


def test_tfidf_retrieval_only_scores_overlapping_documents():
    index = TfidfIndex({"a": "SUGAR", "b": "ZZZZ"})
    assert [k for k, _ in index.top_k("sugar", 5)] == ["a"]


def _separable(n=120, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.random((n, len(FEATURE_NAMES)))
    y = (X[:, 0] + X[:, 1] > 1.0).astype(float)
    return X, y


@pytest.mark.parametrize("algo", sorted(learn.ALGORITHMS))
def test_learners_are_reproducible_and_learn_a_separable_rule(algo):
    X, y = _separable()
    a, b = learn.ALGORITHMS[algo].fit(X, y), learn.ALGORITHMS[algo].fit(X, y)
    assert json.dumps(a.to_dict()) == json.dumps(b.to_dict())  # deterministic
    m = learn.metrics(y, a.predict_proba(X))
    assert m["precision"] >= 0.9 and m["recall"] >= 0.9
    restored = learn.load(json.loads(json.dumps(a.to_dict())))
    assert np.allclose(restored.predict_proba(X), a.predict_proba(X))


def test_group_split_is_deterministic_and_never_splits_a_group():
    groups = [f"g{i % 30}" for i in range(300)]
    first, second = learn.group_split(groups), learn.group_split(groups)
    assert (first == second).all()
    assert all(len({h for g2, h in zip(groups, first) if g2 == g}) == 1 for g in set(groups))


def test_metrics_report_false_merges_and_calibration_bins():
    y = np.array([1, 1, 0, 0], dtype=float)
    m = learn.metrics(y, np.array([0.9, 0.2, 0.8, 0.1]))
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 1)
    assert m["false_merge_rate"] == 0.5 and sum(b["n"] for b in m["calibration"]) == 4


def test_promotion_gate_rejects_weak_or_worse_models():
    good = {"precision": 0.97, "precision_lower_95": 0.9, "false_merge_rate": 0.03, "recall": 0.8, "ece": 0.05, "n": 40, "positives": 20}
    assert lifecycle.gate_check(good, {})["passed"]
    assert not lifecycle.gate_check({**good, "false_merge_rate": 0.2}, {})["passed"]
    assert not lifecycle.gate_check(good, {"holdout": {"precision": 0.99}})["passed"]  # worse than the active model
    assert not lifecycle.gate_check({**good, "n": 15, "positives": 12}, {})["passed"]  # too few non-matches to trust precision


def test_wilson_lower_bound_penalises_tiny_holdouts():
    small = learn.metrics(np.ones(5), np.ones(5))
    large = learn.metrics(np.ones(200), np.ones(200))
    assert small["precision"] == large["precision"] == 1.0
    assert small["precision_lower_95"] < 0.6 < large["precision_lower_95"]


def test_aliases_are_not_a_model_feature():
    assert "alias_exact" not in FEATURE_NAMES  # approval creates the alias → it would leak the label


def lifecycle_band_strong():
    from apps.license.services.product_matching import STRONG
    return STRONG


# ---- database-backed ----------------------------------------------------------------------------

def _word(i: int) -> str:
    """Distinct alphabetic token (normalisation drops digits, so labels must differ in words)."""
    return "batch" + chr(97 + i % 26) + chr(97 + i // 26 % 26)


class IntelligenceDBTests(pivot_fixture.IntelligenceFixture):
    def setUp(self):
        super().setUp()
        self.foil, _ = ItemNameModel.objects.get_or_create(name="ALUMINIUM FOIL")
        self.foil.sion_norm_class, self.foil.is_active = self.sion, True
        self.foil.save()
        self.foil.norms.add(self.sion)
        self.sugar.norms.add(self.sion)
        a, b = self.licences
        self.item(a, 9, "76071994", "Aluminium foil (existing)", "1", names=[self.foil])
        self.alu = self.item(a, 1, "76071991", "Alu Foil", "100")
        self.alu.items.clear()
        self.user = get_user_model().objects.create_user(username="intel-manager")
        self.user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
        self.viewer = get_user_model().objects.create_user(username="intel-viewer")
        self.viewer.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.enterContext(override_settings(PRODUCT_INTEL_DIR=str(self.tmp)))
        lifecycle._load_artifact.cache_clear()

    def suggestions(self):
        data = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))
        return {s["description"].lower().strip(): s for s in finalise(suggest(matching_groups(data)))}, data

    def _labels(self, n_pos=130, n_neg=130):
        """Test-only human decisions: positives = foil wordings → foil; negatives = unrelated wording → foil."""
        for i in range(n_pos):
            ProductMatchDecision.objects.create(source_key=f"pos{i}|76|PI1", source_description=f"aluminium foil {_word(i)}", hsn_code="76071994",
                                                sion=self.sion, chosen_item=self.foil, suggested_item=self.foil, decision="APPROVED", decided_by=self.user)
        for i in range(n_neg):
            ProductMatchDecision.objects.create(source_key=f"neg{i}|17|PI1", source_description=f"refined cane sugar {_word(i)}", hsn_code="17019990",
                                                sion=self.sion, suggested_item=self.foil, decision="REJECTED", decided_by=self.user)

    # knowledge -----------------------------------------------------------------------------------
    def test_observations_preserve_provenance_and_exclude_financial_fields(self):
        obs = [o for o in knowledge.observations() if o["source"] == "licence_import_item"]
        assert {o["source_id"] for o in obs} >= {self.alu.pk}
        keys = set().union(*(o.keys() for o in obs))
        assert not [k for k in keys if any(t in k for t in FINANCIAL_TERMS)]
        before = list(LicenseImportItemsModel.objects.order_by("pk").values_list("description", "quantity", "cif_fc"))
        knowledge.build_dataset()
        assert before == list(LicenseImportItemsModel.objects.order_by("pk").values_list("description", "quantity", "cif_fc"))

    def test_only_verified_decisions_become_labels(self):
        assert knowledge.verified_labels() == []  # master links / rule aliases are not labels
        self._labels(2, 1)
        labels = knowledge.verified_labels()
        assert sorted(x["label"] for x in labels) == [0, 1, 1]
        assert all(x["provenance"].startswith("ProductMatchDecision#") for x in labels)

    def test_latest_human_label_wins_and_groups_ignore_hsn(self):
        ProductMatchDecision.objects.create(source_key="a|1|PI1", source_description="Alu foil", hsn_code="7607", sion=self.sion,
                                            suggested_item=self.foil, decision="REJECTED", decided_by=self.user)
        ProductMatchDecision.objects.create(source_key="a|2|PI1", source_description="ALU FOIL", hsn_code="3920", sion=self.sion,
                                            suggested_item=self.foil, chosen_item=self.foil, decision="APPROVED", decided_by=self.user)
        labels = knowledge.verified_labels()
        assert len(labels) == 1 and labels[0]["label"] == 1 and labels[0]["group"] == "aluminium foil"

    def test_hsn_evidence_created_by_the_decision_itself_is_excluded(self):
        from apps.license.services.product_intelligence.lifecycle import PairFeaturiser
        linked = self.item(self.licences[1], 7, "39201010", "plastic sheet", "1", names=[self.foil])
        featuriser = PairFeaturiser({self.foil.pk})
        col = FEATURE_NAMES.index("hsn_heading_match")
        with_link = featuriser([{"description": "plastic sheet", "hsn": "39201010", "item_id": self.foil.pk}])[0, col]
        without = featuriser([{"description": "plastic sheet", "hsn": "39201010", "item_id": self.foil.pk, "exclude_import_ids": [linked.pk]}])[0, col]
        assert with_link == 1.0 and without == 0.0

    def test_dataset_content_hash_is_reproducible(self):
        self._labels(3, 3)
        first, second = knowledge.build_dataset(), knowledge.build_dataset()
        assert first.sha256 == second.sha256 and first.label_count == 6

    # lifecycle -----------------------------------------------------------------------------------
    def test_insufficient_labels_never_produce_a_model(self):
        self._labels(5, 2)
        model = lifecycle.train(knowledge.build_dataset(), user=self.user)
        assert model.status == ProductIntelModel.INSUFFICIENT and not model.artifact_path
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle.promote(model, user=self.user)

    def test_train_evaluate_promote_score_and_rollback(self):
        self._labels()
        first = lifecycle.train(knowledge.build_dataset(), user=self.user)
        assert first.status == ProductIntelModel.CANDIDATE
        hold = first.metrics["holdout"]
        assert hold["n"] >= lifecycle.MIN_HOLDOUT and first.metrics["gate"]["passed"], first.metrics
        assert lifecycle.active_classifier() == (None, None)  # nothing is active until promoted explicitly
        lifecycle.promote(first, user=self.user)
        sug, _ = self.suggestions()
        alu = sug["alu foil"]
        assert alu["model"]["version"] == first.version and 0 <= alu["model"]["probability"] <= 1
        assert alu["band"] != "APPROVED"  # the model never approves
        second = lifecycle.train(knowledge.build_dataset(), user=self.user)
        assert second.comparison["version"] == first.version  # compared with the active model
        lifecycle.promote(second, user=self.user)
        first.refresh_from_db()
        assert first.status == ProductIntelModel.RETIRED
        assert lifecycle.rollback(user=self.user).version == first.version
        assert ProductIntelModel.objects.get(pk=second.pk).status == ProductIntelModel.REJECTED
        assert list(ProductIntelAuditEvent.objects.filter(action__in=["promote", "rollback"]).values_list("action", flat=True))[:1] == ["rollback"]

    def test_model_alone_never_reaches_bulk_bands_without_text_support(self):
        self._labels()
        lifecycle.promote(lifecycle.train(knowledge.build_dataset(), user=self.user), user=self.user)
        odd = self.item(self.licences[1], 8, "76071991", "Zeta Kappa Material", "2")
        odd.items.clear()
        sug, _ = self.suggestions()
        row = sug["zeta kappa material"]
        assert row["confidence"] < lifecycle_band_strong() and row["band"] not in {"HIGH", "STRONG"}

    def test_promote_refuses_an_unloadable_artifact_and_keeps_the_active_model(self):
        self._labels()
        first = lifecycle.train(knowledge.build_dataset(), user=self.user)
        lifecycle.promote(first, user=self.user)
        second = lifecycle.train(knowledge.build_dataset(), user=self.user)
        Path(second.artifact_path).write_text("not json")
        lifecycle._load_artifact.cache_clear()
        with pytest.raises(lifecycle.LifecycleError):
            lifecycle.promote(second, user=self.user)
        first.refresh_from_db()
        assert first.status == ProductIntelModel.ACTIVE

    def test_corrupted_model_artifact_falls_back_to_deterministic_matching(self):
        self._labels()
        model = lifecycle.train(knowledge.build_dataset(), user=self.user)
        lifecycle.promote(model, user=self.user)
        Path(model.artifact_path).write_text("{}")
        lifecycle._load_artifact.cache_clear()
        assert lifecycle.active_classifier() == (None, None)
        sug, _ = self.suggestions()
        assert sug["alu foil"]["model"] is None and sug["alu foil"]["suggestion"]["name"] == "ALUMINIUM FOIL"

    # aliases -------------------------------------------------------------------------------------
    def test_approval_creates_an_alias_reused_for_new_records_without_auto_merge(self):
        sug, _ = self.suggestions()
        decide(suggestions=[sug["alu foil"]], decision="APPROVED", user=self.user)
        alias = ProductAlias.objects.get(normalized_alias="aluminium foil", item=self.foil)
        assert alias.source == ProductAlias.DECISION and alias.decision_id
        new = self.item(self.licences[1], 5, "76071999", "ALU-FOIL", "7")  # different HSN → different source key
        new.items.clear()
        sug, _ = self.suggestions()
        row = sug["alu-foil"]
        assert row["alias_match"] and row["confidence"] == 100 and row["band"] == "HIGH"
        assert not new.items.exists()  # still only a suggestion until approved

    def test_alias_validation_blocks_illegitimate_multi_product_and_clashing_aliases(self):
        other_sion = SionNormClassModel.objects.create(head_norm=self.sion.head_norm, norm_class="PI2", is_active=True)
        with pytest.raises(MatchValidationError, match="not a legitimate"):
            create_alias(text="alu foil", item_id=self.foil.pk, sion=other_sion.norm_class, user=self.user)
        with pytest.raises(MatchValidationError, match="several"):
            create_alias(text="Alu foil / LDPE", item_id=self.foil.pk, sion="PI1", user=self.user)
        create_alias(text="silver foil", item_id=self.foil.pk, sion="PI1", user=self.user)
        with pytest.raises(MatchValidationError, match="already an alias"):
            create_alias(text="Silver Foil", item_id=self.sugar.pk, sion="PI1", user=self.user)
        assert ProductIntelAuditEvent.objects.filter(action="alias_create").count() == 1

    def test_rejected_and_conflicting_mappings_stay_separate_with_a_model_active(self):
        self._labels()
        lifecycle.promote(lifecycle.train(knowledge.build_dataset(), user=self.user), user=self.user)
        mixed = self.item(self.licences[1], 6, "76071991", "Alu Foil / LDPE", "3")
        mixed.items.clear()
        sug, _ = self.suggestions()
        assert sug["alu foil / ldpe"]["band"] == "CONFLICT"
        with pytest.raises(MatchValidationError):
            decide(suggestions=[sug["alu foil / ldpe"]], decision="APPROVED", user=self.user)
        decide(suggestions=[sug["alu foil"]], decision="REJECTED", user=self.user)
        sug, _ = self.suggestions()
        assert (sug["alu foil"]["suggestion"] or {}).get("item_id") != self.foil.pk

    def test_consolidation_totals_are_unchanged_by_model_and_alias_activity(self):
        before = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))["overview"]["integrity"]
        self._labels()
        lifecycle.promote(lifecycle.train(knowledge.build_dataset(), user=self.user), user=self.user)
        create_alias(text="silver foil", item_id=self.foil.pk, sion="PI1", user=self.user)
        after = build_intelligence(select_pivot_licenses(min_balance=-10**9, license_status="all", sion_norm="PI1"))["overview"]["integrity"]
        assert after == before  # suggestions alone never change aggregation; only approvals do

    # review fixes -----------------------------------------------------------------------------
    def test_approving_a_multi_link_record_requires_explicit_replacement(self):
        amb = self.item(self.licences[1], 4, "76071991", "Alu Foil wrap", "4")
        amb.items.set([self.foil, self.sugar])
        # (Ambiguous report groups are named by their joined masters and are CONFLICT in the UI; decide() guards anyway.)
        row = {"source_key": "aluminium foil wrap|76071991|PI1", "description": "Alu Foil wrap", "hsn_code": "76071991", "sion": "PI1",
               "sion_known": True, "band": "REVIEW", "conflicts": [], "entitlement_hits": {}, "import_item_ids": [amb.pk],
               "suggestion": {"item_id": self.foil.pk, "name": self.foil.name}, "confidence": 85, "explanation": "test", "checks": {}}
        with pytest.raises(MatchValidationError, match="confirm replacing"):
            decide(suggestions=[row], decision="APPROVED", user=self.user, item_id=self.foil.pk)
        assert set(amb.items.values_list("pk", flat=True)) == {self.foil.pk, self.sugar.pk}
        decide(suggestions=[row], decision="APPROVED", user=self.user, item_id=self.foil.pk, replace_links=True)
        assert list(amb.items.values_list("pk", flat=True)) == [self.foil.pk]
        assert ProductMatchDecision.objects.get(import_item_ids=[amb.pk]).previous_links == {str(amb.pk): sorted([self.foil.pk, self.sugar.pk])}

    def test_model_with_a_different_feature_set_is_never_used(self):
        self._labels()
        model = lifecycle.train(knowledge.build_dataset(), user=self.user)
        payload = json.loads(Path(model.artifact_path).read_text())
        payload["feature_names"] = payload["feature_names"][:-1]
        raw = json.dumps(payload, sort_keys=True).encode()
        Path(model.artifact_path).write_bytes(raw)
        model.sha256 = __import__("hashlib").sha256(raw).hexdigest()
        model.save(update_fields=["sha256"])
        lifecycle._load_artifact.cache_clear()
        with pytest.raises(lifecycle.LifecycleError, match="feature set"):
            lifecycle.promote(model, user=self.user)

    def test_tampered_dataset_is_refused_for_training(self):
        self._labels()
        ds = knowledge.build_dataset()
        with open(Path(ds.artifact_path) / "labels.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"description": "forged", "item_id": self.foil.pk, "label": 1, "group": "forged"}) + "\n")
        with pytest.raises(lifecycle.LifecycleError, match="sha256"):
            lifecycle.train(ds, user=self.user)

    def test_training_reports_separate_validation_and_test_splits(self):
        self._labels()
        model = lifecycle.train(knowledge.build_dataset(), user=self.user)
        splits = model.metrics["splits"]
        assert min(splits.values()) >= lifecycle.MIN_HOLDOUT and sum(splits.values()) == model.metrics["labels"]
        assert set(model.metrics["validation"]) == set(learn.ALGORITHMS)  # selection evidence kept separately from the gate

    def test_semantic_job_failures_are_recorded_and_live_jobs_not_double_claimed(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.license.models import ProductMatchingJob
        from apps.license.services import product_matching_semantic as sem
        job = ProductMatchingJob.objects.create(filters={"sion_norm": "PI1"}, batch_size=4)
        with mock.patch.object(sem.pe, "model_version", return_value="test-model"), \
                mock.patch("apps.license.services.item_pivot_intelligence.build_intelligence", side_effect=RuntimeError("boom")):
            sem.run_job(job)
        job.refresh_from_db()
        assert job.status == ProductMatchingJob.FAILED and "boom" in job.error
        ProductMatchingJob.objects.filter(pk=job.pk).update(status=ProductMatchingJob.RUNNING, started_on=timezone.now())
        with mock.patch.object(sem.pe, "model_version", return_value="test-model") as version:
            sem.run_job(job)
            version.assert_not_called()  # a live RUNNING job is left alone
        ProductMatchingJob.objects.filter(pk=job.pk).update(started_on=timezone.now() - timedelta(hours=2))
        with mock.patch.object(sem.pe, "model_version", side_effect=sem.pe.EmbeddingUnavailable("no model")):
            sem.run_job(job)
        job.refresh_from_db()
        assert job.status == ProductMatchingJob.FAILED and job.error == "no model"  # a stale RUNNING job is recovered

    # resolver + API ------------------------------------------------------------------------------
    def test_resolver_is_read_only_and_reusable(self):
        row = resolve("Aluminum foil", hsn="76071994", sion="PI1")
        assert row["suggestion"]["name"] == "ALUMINIUM FOIL" and row["band"] == "HIGH"
        assert not ProductMatchDecision.objects.exists() and not ProductAlias.objects.exists()

    def test_admin_api_permissions_and_actions_are_audited(self):
        viewer, manager = APIClient(), APIClient()
        viewer.force_authenticate(self.viewer)
        manager.force_authenticate(self.user)
        assert viewer.post("/api/item-pivot/matching/admin/train/", {}, format="json").status_code == 403
        assert viewer.post("/api/item-pivot/matching/aliases/", {"text": "x", "item_id": self.foil.pk}, format="json").status_code == 403
        from django.core.cache import cache
        cache.delete(knowledge.inventory_cache_key() + ":train-lock")
        with mock.patch("apps.license.tasks.product_intel_build_and_train.delay", return_value=mock.Mock(id="t-1")) as delay:
            assert manager.post("/api/item-pivot/matching/admin/train/", {"train": "false"}, format="json").status_code == 202
            delay.assert_called_once_with(self.user.pk, False)  # training runs in Celery, never in the request; "false" parsed
            assert manager.post("/api/item-pivot/matching/admin/train/", {"train": True}, format="json").status_code == 409  # one run at a time
        cache.delete(knowledge.inventory_cache_key() + ":train-lock")
        outsider = APIClient()
        outsider.force_authenticate(get_user_model().objects.create_user(username="intel-outsider"))
        assert outsider.get("/api/item-pivot/matching/aliases/").status_code == 403
        res = manager.get("/api/item-pivot/matching/admin/")
        assert res.status_code == 200 and res.json()["labels"]["required"]["total"] == lifecycle.MIN_LABELS
        assert {r["source"] for r in res.json()["inventory"]} >= {"licence_import_item", "product_match_decision"}
        created = manager.post("/api/item-pivot/matching/aliases/", {"text": "Silver foil", "item_id": self.foil.pk, "sion": "PI1"}, format="json")
        assert created.status_code == 201
        assert manager.post(f"/api/item-pivot/matching/aliases/{created.json()['id']}/deactivate/").status_code == 200
        assert manager.post("/api/item-pivot/matching/admin/rollback/").status_code == 400  # no active model
        assert set(ProductIntelAuditEvent.objects.values_list("action", flat=True)) >= {"dataset_requested", "alias_create", "alias_deactivate"}
        resolved = viewer.get("/api/item-pivot/matching/resolve/", {"description": "Alu foil", "sion": "PI1"})
        assert resolved.status_code == 200 and resolved.json()["suggestion"]["name"] == "ALUMINIUM FOIL"


def test_e126_hsn_implies_the_entitlement_even_without_alias_wording():
    from types import SimpleNamespace
    from apps.license.services.product_matching import _entitlement_targets, _validate
    assert _entitlement_targets("E126", "Edible oil", "15131900") == {"HSN 1513": "PALM KERNEL OIL"}
    assert _entitlement_targets("E126", "Edible oil", "15099010") == {"HSN 1509": "OLIVE OIL"}
    assert _entitlement_targets("E132", "Edible oil", "15131900") == {}  # E126 rules never applied to E132
    olive = SimpleNamespace(name="OLIVE OIL", norms=SimpleNamespace(all=lambda: [SimpleNamespace(norm_class="E126")]), sion_norm_class_id=None)
    row = {"band": "REVIEW", "conflicts": [], "sion_known": True, "sion": "E126", "entitlement_hits": _entitlement_targets("E126", "Edible oil", "15131900")}
    with pytest.raises(MatchValidationError, match="PALM KERNEL OIL"):
        _validate(row, olive, allow_review=True)  # an alias-less PKO-HSN record can't be linked to Olive Oil


def test_sunflower_to_olive_classification_is_scoped_to_e126_only():
    from apps.license.utils.item_matcher import get_item_filters
    olive = [c for c in get_item_filters() if c["base_name"] == "OLIVE OIL"]
    sunflower = [c for c in olive if any("sunflower" in str(f).lower() for f in c["filters"])]
    assert sunflower and all(c["norms"] == ["E126"] for c in sunflower)
    assert not any("sunflower" in str(f).lower() for c in olive if "E5" in c["norms"] for f in c["filters"])


def test_e132_never_receives_e126_entitlement_aliases():
    from apps.license.services.product_matching import _entitlement_targets
    assert _entitlement_targets("E126", "Sunflower oil") == {"Sunflower Oil": "OLIVE OIL"}
    assert _entitlement_targets("E132", "Sunflower oil") == {}

