"""Model Training, Evaluation, Version and Rollback services.

Lifecycle (owner spec): collect verified decisions → versioned dataset → train a
candidate → evaluate on held-out human-reviewed groups → compare with the ACTIVE model
→ promote only through an explicit, audited action that passes the quality gate →
previous model kept for rollback. Nothing retrains or promotes automatically, and
no model ever approves a match.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel, ProductIntelAuditEvent, ProductIntelDataset, ProductIntelModel
from apps.license.services.product_intelligence import learn
from apps.license.services.product_intelligence.features import FEATURE_NAMES, PairContext, pair_features
from apps.license.services.product_intelligence.knowledge import artifact_root, load_labels

logger = logging.getLogger(__name__)

MIN_LABELS, MIN_PER_CLASS, MIN_HOLDOUT = 60, 20, 15
# Holdout must contain enough of each class for the precision figure to mean something.
MIN_HOLDOUT_PER_CLASS = 10
PROMOTION_GATE = {"precision": 0.95, "precision_lower_95": 0.80, "false_merge_rate": 0.05, "recall": 0.50, "ece": 0.10}


class LifecycleError(ValueError):
    pass


def master_hsn_links(item_ids: set[int]) -> dict[int, dict[int, str]]:
    """{master id: {import item id: HSN}} — the HSN codes already imported under each master."""
    links: dict[int, dict[int, str]] = defaultdict(dict)
    through = LicenseImportItemsModel.items.through
    for name_id, import_id, hsn in through.objects.filter(itemnamemodel_id__in=list(item_ids)).values_list(
        "itemnamemodel_id", "licenseimportitemsmodel_id", "licenseimportitemsmodel__hs_code__hs_code"):
        if hsn:
            links[name_id][import_id] = str(hsn)
    return links


class PairFeaturiser:
    """Preloads master names and HSN links once, then featurises many pairs without queries.

    Leakage guard (independent review 2026-11-19): a training row may carry ``exclude_import_ids`` — the import
    items its own decision linked to the master. Those links are left out of the master's HSN profile, so a
    label never sees evidence that the label itself created.
    """

    def __init__(self, item_ids: set[int]):
        self.names = dict(ItemNameModel.objects.filter(pk__in=item_ids).values_list("pk", "name"))
        self.links = master_hsn_links(set(item_ids))

    def _profile(self, item_id: int, exclude: frozenset[int]) -> tuple[frozenset[str], frozenset[str]]:
        codes = [h for imp, h in self.links.get(item_id, {}).items() if imp not in exclude]
        return frozenset(h[:2] for h in codes), frozenset(h[:4] for h in codes)

    def __call__(self, rows: list[dict]) -> np.ndarray:
        out = []
        for r in rows:
            chapters, headings = self._profile(r["item_id"], frozenset(r.get("exclude_import_ids") or ()))
            ctx = PairContext(hsn=str(r.get("hsn") or ""), master_chapters=chapters, master_headings=headings)
            out.append(pair_features(r["description"], self.names.get(r["item_id"], ""), ctx))
        return np.vstack(out) if out else np.zeros((0, len(FEATURE_NAMES)))


def featurise(rows: list[dict]) -> np.ndarray:
    """rows: [{description, hsn, item_id}] → feature matrix (semantic evidence intentionally omitted in v1)."""
    return PairFeaturiser({r["item_id"] for r in rows})(rows)


def _audit(action: str, user, **detail) -> None:
    ProductIntelAuditEvent.objects.create(action=action, user=user, detail=detail)


def _active() -> ProductIntelModel | None:
    return ProductIntelModel.objects.filter(status=ProductIntelModel.ACTIVE).select_related("dataset").first()


@lru_cache(maxsize=4)
def _load_artifact(path: str, sha256: str):
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise LifecycleError(f"Model artifact unreadable: {path}") from exc
    if hashlib.sha256(data).hexdigest() != sha256:
        raise LifecycleError(f"Model artifact checksum mismatch: {path}")
    try:
        payload = json.loads(data)
        if payload.get("feature_names") != list(FEATURE_NAMES):
            raise LifecycleError("Model was trained on a different feature set — retrain it")
        return learn.load(payload)
    except LifecycleError:
        raise
    except Exception as exc:  # noqa: BLE001 — any malformed artifact is a lifecycle error, never a 500
        raise LifecycleError(f"Model artifact invalid: {exc}") from exc


def active_classifier():
    """(ProductIntelModel, classifier) or (None, None). Never raises — matching must keep working."""
    try:
        record = _active()
        if record is None:
            return None, None
        return record, _load_artifact(record.artifact_path, record.sha256)
    except Exception:  # noqa: BLE001 — a broken artifact disables the model, deterministic matching continues
        logger.exception("Active product-matching model could not be loaded; falling back to deterministic matching")
        return None, None


def train(dataset: ProductIntelDataset, *, user=None) -> ProductIntelModel:
    from apps.license.services.product_intelligence.knowledge import DatasetIntegrityError

    try:
        labels = load_labels(dataset)
    except (OSError, DatasetIntegrityError) as exc:
        raise LifecycleError(str(exc)) from exc
    positives = sum(1 for x in labels if x["label"] == 1)
    negatives = len(labels) - positives
    version = timezone.now().strftime("pm-%Y%m%d-%H%M%S-%f")
    if len(labels) < MIN_LABELS or positives < MIN_PER_CLASS or negatives < MIN_PER_CLASS:
        model = ProductIntelModel.objects.create(
            version=version, dataset=dataset, status=ProductIntelModel.INSUFFICIENT, feature_names=list(FEATURE_NAMES), trained_by=user,
            metrics={"labels": len(labels), "positives": positives, "negatives": negatives},
            notes=f"Needs ≥{MIN_LABELS} verified labels with ≥{MIN_PER_CLASS} per class; has {positives} positive / {negatives} negative. "
                  "Keep reviewing suggestions — every decision becomes a label.")
        _audit("train", user, model=version, dataset=dataset.version, status=model.status, labels=len(labels))
        return model
    X = featurise(labels)
    y = np.array([x["label"] for x in labels], dtype=np.float64)
    # Three-way split by wording (review 2026-11-19): select the algorithm on VALIDATION, refit the winner on
    # train + validation, and judge it once on the untouched TEST split — the gate never sees a split used for selection.
    part = learn.group_split3([x["group"] for x in labels])
    train_m, val_m, test_m = part == 0, part == 1, part == 2
    for name, mask in (("train", train_m), ("validation", val_m), ("test", test_m)):
        if mask.sum() < MIN_HOLDOUT or len(set(y[mask])) < 2:
            raise LifecycleError(f"The {name} split has too few or one-class labels ({int(mask.sum())}) — collect more decisions")
    results = {}
    for name, algo in learn.ALGORITHMS.items():
        clf = algo.fit(X[train_m], y[train_m])
        results[name] = learn.metrics(y[val_m], clf.predict_proba(X[val_m]))
    # Selection: fewest false merges first, then recall, then calibration.
    best = min(results, key=lambda n: (results[n]["false_merge_rate"] if results[n]["false_merge_rate"] is not None else 1.0,
                                       -(results[n]["recall"] or 0.0), results[n]["ece"]))
    fit_m = train_m | val_m
    clf = learn.ALGORITHMS[best].fit(X[fit_m], y[fit_m])
    hold_metrics = learn.metrics(y[test_m], clf.predict_proba(X[test_m]))
    train_metrics = learn.metrics(y[fit_m], clf.predict_proba(X[fit_m]))
    payload = json.dumps({**clf.to_dict(), "feature_names": list(FEATURE_NAMES), "version": version}, sort_keys=True).encode()
    folder = artifact_root() / "models"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{version}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written artifact
    comparison = {}
    current = _active()
    if current is not None:
        try:
            old = _load_artifact(current.artifact_path, current.sha256)
            comparison = {"version": current.version, "holdout": learn.metrics(y[test_m], old.predict_proba(X[test_m]))}
        except LifecycleError as exc:
            comparison = {"version": current.version, "error": str(exc)}
    try:
        model = ProductIntelModel.objects.create(
            version=version, dataset=dataset, algorithm=best, status=ProductIntelModel.CANDIDATE, artifact_path=str(path),
            sha256=hashlib.sha256(payload).hexdigest(), feature_names=list(FEATURE_NAMES), trained_by=user, comparison=comparison,
            metrics={"holdout": hold_metrics, "train": train_metrics, "validation": results, "labels": len(labels), "positives": positives,
                     "negatives": negatives, "splits": {"train": int(train_m.sum()), "validation": int(val_m.sum()), "test": int(test_m.sum())},
                     "holdout_groups": int(len({x["group"] for x, t in zip(labels, test_m) if t})), "gate": gate_check(hold_metrics, comparison)},
        )
    except Exception:
        path.unlink(missing_ok=True)  # no orphan artifact without a registry row
        raise
    _audit("train", user, model=version, dataset=dataset.version, status=model.status, algorithm=best, holdout=hold_metrics)
    return model


def gate_check(holdout: dict, comparison: dict) -> dict:
    failures = []
    for key, limit in PROMOTION_GATE.items():
        value = holdout.get(key)
        if value is None:
            failures.append(f"{key} unavailable")
        elif key in {"false_merge_rate", "ece"} and value > limit:
            failures.append(f"{key} {value} > {limit}")
        elif key not in {"false_merge_rate", "ece"} and value < limit:
            failures.append(f"{key} {value} < {limit}")
    if (holdout.get("positives") or 0) < MIN_HOLDOUT_PER_CLASS or (holdout.get("n", 0) - (holdout.get("positives") or 0)) < MIN_HOLDOUT_PER_CLASS:
        failures.append(f"holdout needs ≥{MIN_HOLDOUT_PER_CLASS} matches and ≥{MIN_HOLDOUT_PER_CLASS} non-matches")
    old = (comparison or {}).get("holdout") or {}
    if old.get("precision") is not None and (holdout.get("precision") or 0) < old["precision"]:
        failures.append(f"precision {holdout.get('precision')} below active model {old['precision']}")
    return {"passed": not failures, "failures": failures, "thresholds": PROMOTION_GATE}


def promote(model: ProductIntelModel, *, user) -> ProductIntelModel:
    if model.status != ProductIntelModel.CANDIDATE:
        raise LifecycleError(f"Only a CANDIDATE can be promoted (this one is {model.status})")
    gate = (model.metrics or {}).get("gate") or {}
    if not gate.get("passed"):
        raise LifecycleError("Quality gate not passed: " + "; ".join(gate.get("failures") or ["no evaluation"]))
    _load_artifact(model.artifact_path, model.sha256)  # never retire the working model for an unloadable artifact
    try:
        with transaction.atomic():
            # Re-check under lock: a concurrent reject / promote must not be overridden.
            model = ProductIntelModel.objects.select_for_update().get(pk=model.pk)
            if model.status != ProductIntelModel.CANDIDATE:
                raise LifecycleError(f"Model is now {model.status}")
            _promote_locked(model, user)
    except IntegrityError as exc:
        raise LifecycleError("Another model was promoted at the same time — reload") from exc
    return model


def _promote_locked(model: ProductIntelModel, user) -> None:
    """Retire the current ACTIVE model (if any) and activate ``model``; caller holds the transaction."""
    previous = ProductIntelModel.objects.select_for_update().filter(status=ProductIntelModel.ACTIVE).first()
    if previous:
        previous.status, previous.retired_on = ProductIntelModel.RETIRED, timezone.now()
        previous.save(update_fields=["status", "retired_on"])
    model.status, model.promoted_on = ProductIntelModel.ACTIVE, timezone.now()
    model.save(update_fields=["status", "promoted_on"])
    _audit("promote", user, model=model.version, previous=getattr(previous, "version", None))


def rollback(*, user) -> ProductIntelModel | None:
    """Retire the ACTIVE model and re-activate the most recently retired one (or none → deterministic only)."""
    with transaction.atomic():
        current = ProductIntelModel.objects.select_for_update().filter(status=ProductIntelModel.ACTIVE).first()
        if current is None:
            raise LifecycleError("No active model to roll back")
        target = ProductIntelModel.objects.filter(status=ProductIntelModel.RETIRED).exclude(pk=current.pk).order_by("-retired_on", "-pk").first()
        current.status, current.retired_on = ProductIntelModel.REJECTED, timezone.now()
        current.save(update_fields=["status", "retired_on"])
        if target:
            try:
                _load_artifact(target.artifact_path, target.sha256)
            except LifecycleError as exc:
                raise LifecycleError(f"Previous model {target.version} cannot be loaded: {exc}") from exc
            target.status, target.promoted_on, target.retired_on = ProductIntelModel.ACTIVE, timezone.now(), None
            target.save(update_fields=["status", "promoted_on", "retired_on"])
        _audit("rollback", user, from_model=current.version, to_model=getattr(target, "version", None))
    return target


def reject(model: ProductIntelModel, *, user) -> ProductIntelModel:
    if model.status != ProductIntelModel.CANDIDATE:
        raise LifecycleError("Only a CANDIDATE can be rejected")
    model.status = ProductIntelModel.REJECTED
    model.save(update_fields=["status"])
    _audit("reject_candidate", user, model=model.version)
    return model


class ModelScorer:
    """ACTIVE model + preloaded features for one matching run (``None`` from ``build`` when no model)."""

    def __init__(self, record: ProductIntelModel, clf, featuriser: PairFeaturiser):
        self.record, self.clf, self.featuriser = record, clf, featuriser

    @classmethod
    def build(cls, item_ids: set[int]) -> "ModelScorer | None":
        record, clf = active_classifier()
        return cls(record, clf, PairFeaturiser(item_ids)) if clf is not None else None

    def score(self, description: str, hsn: str, item_ids: list[int]) -> dict[int, dict]:
        if not item_ids:
            return {}
        X = self.featuriser([{"description": description, "hsn": hsn, "item_id": i} for i in item_ids])
        probs = self.clf.predict_proba(X)
        return {i: {"probability": round(float(p), 4), "top_features": [(n, round(v, 3)) for n, v in self.clf.explain(x, FEATURE_NAMES)]}
                for i, p, x in zip(item_ids, probs, X)}


class TrainingRequestError(LifecycleError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def request_training(*, user, train: bool) -> str:
    """Queue dataset generation (+ candidate training) on the ``matching`` worker. One run at a time; audited."""
    from django.core.cache import cache
    from kombu.exceptions import OperationalError

    from apps.license.services.product_intelligence.knowledge import inventory_cache_key
    from apps.license.tasks import product_intel_build_and_train

    lock = inventory_cache_key() + ":train-lock"
    if not cache.add(lock, user.pk, 1800):
        raise TrainingRequestError("A dataset / training run is already queued or running.", 409)
    event = ProductIntelAuditEvent.objects.create(action="dataset_requested", user=user, detail={"train": train})
    try:
        result = product_intel_build_and_train.delay(user.pk, train)
    except Exception as exc:  # noqa: BLE001 — never leave the run lock held when nothing was queued
        cache.delete(lock)
        event.detail = {**event.detail, "error": type(exc).__name__}
        event.save(update_fields=["detail"])
        if isinstance(exc, OperationalError):
            raise TrainingRequestError("Background worker broker unavailable — try again later.", 503) from exc
        raise
    event.detail = {**event.detail, "task_id": str(result.id)}
    event.save(update_fields=["detail"])
    return str(result.id)
