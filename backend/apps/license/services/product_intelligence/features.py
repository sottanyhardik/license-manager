"""Product Feature Extractor + character n-gram TF-IDF similarity (numpy, no new dependency).

Pair features describe *a source description against one candidate master item*.
Approved aliases are deliberately not a feature: approval creates the alias, so it would
leak the label (alias hits are handled as 100 % suggestions in ``suggest`` instead).
They are built from text, HSN and rule compatibility only. Financial fields
(quantity, CIF, debits, allotments, plans) are never inputs: ``FEATURE_NAMES`` is the
complete, test-pinned list.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from apps.license.services.product_matching import master_label, normalise, product_segments, text_score, tokens

FEATURE_NAMES = (
    "text_score",          # deterministic matcher score / 100
    "char_tfidf_cosine",   # char 3–5-gram TF-IDF cosine of normalised texts
    "token_jaccard",       # word-set Jaccard after normalisation
    "master_coverage",     # share of the master's words present in the description
    "description_coverage",  # share of the description explained by the master's words
    "exact_normalised",    # 1 if normalised texts are identical
    "hsn_chapter_match",   # 1 / 0, 0.5 when unknown (no HSN or master has no history)
    "hsn_heading_match",   # same for the 4-digit heading
    "multi_product",       # 1 if the description lists more than one product
    "semantic_similarity",  # local MiniLM cosine when persisted, else 0
    "semantic_missing",    # 1 when no semantic evidence is available
)
FINANCIAL_TERMS = ("qty", "quantity", "cif", "debit", "allot", "plan", "value", "amount", "price", "balance")
NGRAMS = (3, 4, 5)


def char_ngrams(text: str) -> Counter:
    padded = f" {text} "
    grams: Counter = Counter()
    for n in NGRAMS:
        grams.update(padded[i:i + n] for i in range(max(0, len(padded) - n + 1)))
    return grams


class TfidfIndex:
    """Char n-gram TF-IDF over a fixed corpus with an inverted index for top-k retrieval.

    Retrieval only touches documents sharing at least one n-gram with the query, so the
    search space grows with overlap, not with corpus size.
    """

    def __init__(self, documents: dict[str, str]):
        self.keys = list(documents)
        self.texts = {k: normalise(v) for k, v in documents.items()}
        grams = {k: char_ngrams(t) for k, t in self.texts.items()}
        df: Counter = Counter()
        for g in grams.values():
            df.update(g.keys())
        n = max(1, len(grams))
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1.0 for g, c in df.items()}
        self.default_idf = math.log(1 + n) + 1.0
        self.vectors = {k: self._weigh(g) for k, g in grams.items()}
        self.postings: dict[str, list[str]] = {}
        for k, vec in self.vectors.items():
            for g in vec:
                self.postings.setdefault(g, []).append(k)

    def _weigh(self, grams: Counter) -> dict[str, float]:
        vec = {g: (1 + math.log(c)) * self.idf.get(g, self.default_idf) for g, c in grams.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    def vector(self, text: str) -> dict[str, float]:
        return self._weigh(char_ngrams(normalise(text)))

    @staticmethod
    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return float(sum(v * b.get(g, 0.0) for g, v in a.items()))

    def similarity(self, text: str, key: str) -> float:
        return self.cosine(self.vector(text), self.vectors.get(key, {}))

    def top_k(self, text: str, k: int = 10, *, allowed: set[str] | None = None, min_score: float = 0.0) -> list[tuple[str, float]]:
        query = self.vector(text)
        scores: dict[str, float] = {}
        for g, w in query.items():
            for key in self.postings.get(g, ()):
                if allowed is None or key in allowed:
                    scores[key] = scores.get(key, 0.0) + w * self.vectors[key][g]
        ranked = sorted(((key, s) for key, s in scores.items() if s >= min_score), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:k]


@dataclass(frozen=True)
class PairContext:
    hsn: str = ""
    master_chapters: frozenset[str] = frozenset()
    master_headings: frozenset[str] = frozenset()
    semantic_similarity: float | None = None


def _hsn_match(code: str, known: frozenset[str], width: int) -> float:
    if not code or len(code) < width or not known:
        return 0.5
    return 1.0 if code[:width] in known else 0.0


def pair_features(description: str, master_name: str, ctx: PairContext, *, tfidf: float | None = None) -> np.ndarray:
    a, b = normalise(description), normalise(master_label(master_name))
    ta, tb = tokens(a), tokens(b)
    if tfidf is None:
        va, vb = char_ngrams(a), char_ngrams(b)
        num = sum(va[g] * vb.get(g, 0) for g in va)
        den = math.sqrt(sum(v * v for v in va.values())) * math.sqrt(sum(v * v for v in vb.values())) or 1.0
        tfidf = num / den
    values = {
        "text_score": text_score(description, master_name)[0] / 100.0,
        "char_tfidf_cosine": float(tfidf),
        "token_jaccard": len(ta & tb) / len(ta | tb) if ta | tb else 0.0,
        "master_coverage": len(ta & tb) / len(tb) if tb else 0.0,
        "description_coverage": len(ta & tb) / len(ta) if ta else 0.0,
        "exact_normalised": 1.0 if a and a == b else 0.0,
        "hsn_chapter_match": _hsn_match(ctx.hsn, ctx.master_chapters, 2),
        "hsn_heading_match": _hsn_match(ctx.hsn, ctx.master_headings, 4),
        "multi_product": 1.0 if len(product_segments(description)) > 1 else 0.0,
        "semantic_similarity": float(ctx.semantic_similarity or 0.0),
        "semantic_missing": 0.0 if ctx.semantic_similarity is not None else 1.0,
    }
    return np.array([values[name] for name in FEATURE_NAMES], dtype=np.float64)
