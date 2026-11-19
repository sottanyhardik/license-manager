"""Domain-specific pair classifiers in numpy (deterministic, CPU-only, no new dependency).

Two candidate algorithms are trained on the same human-verified pairs and the better
one on the held-out split is kept:

* ``logreg``  — L2-regularised logistic regression (full-batch gradient descent);
* ``stumps``  — gradient-boosted decision stumps (logistic loss).

Random forest / SVM are not offered: they would need scikit-learn, a new dependency
that has not been approved. Raw similarity is never treated as a probability; only
these models' outputs, evaluated for calibration on held-out human decisions, are.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


@dataclass
class LogReg:
    weights: np.ndarray
    bias: float
    mean: np.ndarray
    scale: np.ndarray
    algorithm: str = "logreg"

    @classmethod
    def fit(cls, X: np.ndarray, y: np.ndarray, *, l2: float = 0.1, lr: float = 0.5, epochs: int = 3000) -> "LogReg":
        mean = X.mean(axis=0)
        scale = X.std(axis=0)
        scale[scale == 0] = 1.0
        Z = (X - mean) / scale
        w = np.zeros(X.shape[1])
        b = 0.0
        n = len(y)
        for _ in range(epochs):
            p = _sigmoid(Z @ w + b)
            grad_w = Z.T @ (p - y) / n + l2 * w / n
            grad_b = float(np.mean(p - y))
            w -= lr * grad_w
            b -= lr * grad_b
        return cls(w, b, mean, scale)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return _sigmoid(((X - self.mean) / self.scale) @ self.weights + self.bias)

    def to_dict(self) -> dict:
        return {"algorithm": self.algorithm, "weights": self.weights.tolist(), "bias": self.bias,
                "mean": self.mean.tolist(), "scale": self.scale.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "LogReg":
        return cls(np.array(d["weights"]), float(d["bias"]), np.array(d["mean"]), np.array(d["scale"]))

    def explain(self, x: np.ndarray, names: tuple[str, ...]) -> list[tuple[str, float]]:
        contrib = ((x - self.mean) / self.scale) * self.weights
        order = np.argsort(-np.abs(contrib))
        return [(names[i], float(contrib[i])) for i in order[:4]]


@dataclass
class Stumps:
    base: float
    stumps: list[tuple[int, float, float, float]]  # (feature, threshold, left value, right value)
    rate: float
    algorithm: str = "stumps"

    @classmethod
    def fit(cls, X: np.ndarray, y: np.ndarray, *, rounds: int = 150, rate: float = 0.2, min_leaf: int = 3, l2: float = 1.0) -> "Stumps":
        prior = float(np.clip(y.mean(), 1e-3, 1 - 1e-3))
        base = float(np.log(prior / (1 - prior)))
        F = np.full(len(y), base)
        stumps = []
        thresholds = [np.unique(np.quantile(X[:, j], np.linspace(0.05, 0.95, 19))) for j in range(X.shape[1])]
        for _ in range(rounds):
            p = _sigmoid(F)
            g, h = y - p, np.maximum(p * (1 - p), 1e-6)
            best = None
            for j in range(X.shape[1]):
                for t in thresholds[j]:
                    left = X[:, j] <= t
                    nl, nr = int(left.sum()), int((~left).sum())
                    if nl < min_leaf or nr < min_leaf:
                        continue
                    gl, gr, hl, hr = g[left].sum(), g[~left].sum(), h[left].sum(), h[~left].sum()
                    # L2 on leaf values keeps pure leaves from saturating probabilities on small data.
                    gain = gl * gl / (hl + l2) + gr * gr / (hr + l2)
                    if best is None or gain > best[0]:
                        best = (gain, j, float(t), float(gl / (hl + l2)), float(gr / (hr + l2)))
            if best is None:
                break
            _, j, t, vl, vr = best
            F += rate * np.where(X[:, j] <= t, vl, vr)
            stumps.append((j, t, vl, vr))
        return cls(base, stumps, rate)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        F = np.full(len(X), self.base)
        for j, t, vl, vr in self.stumps:
            F += self.rate * np.where(X[:, j] <= t, vl, vr)
        return _sigmoid(F)

    def to_dict(self) -> dict:
        return {"algorithm": self.algorithm, "base": self.base, "rate": self.rate, "stumps": [list(s) for s in self.stumps]}

    @classmethod
    def from_dict(cls, d: dict) -> "Stumps":
        return cls(float(d["base"]), [(int(s[0]), float(s[1]), float(s[2]), float(s[3])) for s in d["stumps"]], float(d["rate"]))

    def explain(self, x: np.ndarray, names: tuple[str, ...]) -> list[tuple[str, float]]:
        contrib: dict[int, float] = {}
        for j, t, vl, vr in self.stumps:
            contrib[j] = contrib.get(j, 0.0) + self.rate * (vl if x[j] <= t else vr)
        return [(names[j], v) for j, v in sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:4]]


ALGORITHMS = {"logreg": LogReg, "stumps": Stumps}


def load(d: dict):
    return ALGORITHMS[d["algorithm"]].from_dict(d)


def _bucket(group: str, seed: str) -> float:
    return int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def group_split(groups: list[str], holdout: float = 0.25, seed: str = "pi-v1") -> np.ndarray:
    """Deterministic two-way split by source group (no wording in both train and holdout)."""
    return np.array([_bucket(g, seed) < holdout for g in groups])


def group_split3(groups: list[str], *, validation: float = 0.2, test: float = 0.2, seed: str = "pi-v1") -> np.ndarray:
    """Deterministic three-way split by group: 0 = train, 1 = validation (model selection), 2 = test (gate only)."""
    def part(g: str) -> int:
        b = _bucket(g, seed)
        return 2 if b < test else 1 if b < test + validation else 0
    return np.array([part(g) for g in groups])


def _wilson_lower(successes: int, n: int, z: float = 1.96) -> float:
    p = successes / n
    centre = p + z * z / (2 * n)
    margin = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return float((centre - margin) / (1 + z * z / n))


def metrics(y: np.ndarray, p: np.ndarray, *, threshold: float = 0.5) -> dict:
    """Precision / recall / false-merge rate at the threshold + calibration on the given split."""
    pred = p >= threshold
    tp, fp = int(np.sum(pred & (y == 1))), int(np.sum(pred & (y == 0)))
    fn, tn = int(np.sum(~pred & (y == 1))), int(np.sum(~pred & (y == 0)))
    bins = []
    index = np.minimum((np.round(p * 1000).astype(int)) // 100, 9)  # exact decile on 0.001 steps; 1.0 → last bin
    for b in range(10):
        m = index == b
        if m.any():
            bins.append({"from": b / 10, "n": int(m.sum()), "mean_p": round(float(p[m].mean()), 4), "observed": round(float(y[m].mean()), 4)})
    ece = sum(b["n"] * abs(b["mean_p"] - b["observed"]) for b in bins) / max(1, len(y))
    return {
        "n": int(len(y)), "positives": int(y.sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        # Wilson 95 % lower bound: what precision we can claim given how few holdout merges there are.
        "precision_lower_95": round(_wilson_lower(tp, tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        # Share of proposed merges that are wrong — the error the owner cares about most.
        "false_merge_rate": round(fp / (tp + fp), 4) if tp + fp else None,
        "brier": round(float(np.mean((p - y) ** 2)), 4), "ece": round(float(ece), 4), "calibration": bins,
    }
