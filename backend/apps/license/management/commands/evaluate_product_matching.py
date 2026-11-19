"""Measure product-matching accuracy (read-only; writes nothing).

Ground truth:
  * ``--truth links`` (default): import items already linked to exactly ONE master item that is legitimate for the
    licence's SION. These links include rule-based auto-links, so this is a PROXY, not human-verified truth.
  * ``--truth decisions``: human ProductMatchDecision rows (APPROVED = positive, REJECTED/DIFFERENT = negative).

For each record the matcher sees only description + HSN + SION (its own link hidden) and is scored:
  precision      = correct proposals / proposals (proposal = HIGH, STRONG or REVIEW band)
  recall         = correct proposals / records
  false merge    = wrong proposals / proposals        (the costly error)
  false split    = records with no proposal / records
  hsn_compatible = share of correct proposals whose HSN check passed

    manage.py evaluate_product_matching --sion E5 --sample 300 [--semantic]
"""
import random
from collections import defaultdict

import numpy as np
from django.core.management.base import BaseCommand

from apps.core.models import ItemNameModel
from apps.license.models import LicenseImportItemsModel, ProductMatchDecision
from apps.license.services.product_matching import REVIEW, master_label, merge_ai, normalise, source_key, suggest

PROPOSED = {"HIGH", "STRONG", "REVIEW"}


class Command(BaseCommand):
    help = "Read-only precision / recall / false-merge evaluation of product matching."

    def add_arguments(self, parser):
        parser.add_argument("--sion", action="append", default=[], help="SION code(s); repeatable")
        parser.add_argument("--sample", type=int, default=300)
        parser.add_argument("--seed", type=int, default=20261118)
        parser.add_argument("--semantic", action="store_true", help="also score the hybrid (deterministic + MiniLM) mode")
        parser.add_argument("--truth", choices=["links", "decisions"], default="links")

    def _records(self, sion: str, sample: int, seed: int) -> list[dict]:
        rows = []
        items = (LicenseImportItemsModel.objects.filter(license__export_license__norm_class__norm_class=sion)
                 .select_related("hs_code").prefetch_related("items__norms").distinct().order_by("pk"))
        for item in items.iterator(chunk_size=500):
            names = list(item.items.all())
            if len(names) != 1 or not item.description:
                continue
            legit = {n.norm_class for n in names[0].norms.all()} or ({names[0].sion_norm_class.norm_class} if names[0].sion_norm_class_id else set())
            if sion not in legit:
                continue
            hsn = item.hs_code.hs_code if item.hs_code_id else ""
            rows.append({"truth": names[0].pk, "description": item.description, "hsn_code": hsn, "sion": sion,
                         "source_key": source_key(normalise(item.description), hsn, sion) + f"|eval{item.pk}", "import_item_ids": [item.pk],
                         "kind": "EVAL"})
        random.Random(seed).shuffle(rows)
        return rows[:sample]

    def _decision_records(self, sion: str) -> list[dict]:
        out = []
        for d in ProductMatchDecision.objects.filter(sion__norm_class=sion).select_related("chosen_item", "suggested_item"):
            truth = d.chosen_item_id if d.decision == ProductMatchDecision.APPROVED else None
            out.append({"truth": truth, "negative": d.suggested_item_id if truth is None else None, "description": d.source_description,
                        "hsn_code": d.hsn_code, "sion": sion, "source_key": f"{d.source_key}|eval{d.pk}", "import_item_ids": d.import_item_ids, "kind": "EVAL"})
        return out

    def _semantic(self, rows: list[dict], suggestions: list[dict]) -> list[dict]:
        from apps.license.services import product_embedding as pe
        from apps.license.services.product_matching_semantic import SEMANTIC_CAP, SEMANTIC_MIN, _legit_masters, embedding_text

        masters = _legit_masters({r["sion"] for r in rows})
        out = []
        cache: dict[str, np.ndarray] = {}
        for sion, pool in masters.items():
            vecs = pe.embed([embedding_text(master_label(m.name)) for m in pool], batch_size=8)
            cache.update({f"{sion}:{m.pk}": v for m, v in zip(pool, vecs, strict=True)})
        source_vecs = pe.embed([embedding_text(r["description"]) for r in rows], batch_size=8)
        for row, sug, vec in zip(rows, suggestions, source_vecs, strict=True):
            pool = masters.get(row["sion"], [])
            merged = merge_ai(sug, None)
            if pool and (merged["suggestion"] is None or merged["confidence"] < REVIEW):
                sims = np.array([cache[f"{row['sion']}:{m.pk}"] @ vec for m in pool])
                best = int(np.argmax(sims))
                if sims[best] >= SEMANTIC_MIN:
                    conflicts, checks = sug["_evaluate"](pool[best].pk)
                    merged.update({"suggestion": {"item_id": pool[best].pk, "name": pool[best].name}, "conflicts": conflicts, "checks": checks,
                                   "confidence": min(SEMANTIC_CAP, round(float(sims[best]) * 100))})
                    from apps.license.services.product_matching import _band
                    merged.update(_band(merged))
            out.append(merged)
        return out

    def _score(self, rows: list[dict], results: list[dict]) -> dict:
        stats = defaultdict(int)
        for row, res in zip(rows, results, strict=True):
            stats["records"] += 1
            pick = (res.get("suggestion") or {}).get("item_id")
            proposed = res["band"] in PROPOSED and pick is not None
            if row.get("truth") is None:  # human negative example
                stats["negatives"] += 1
                if proposed and pick == row.get("negative"):
                    stats["repeated_rejected"] += 1
                continue
            if not proposed:
                stats["no_proposal"] += 1
                continue
            stats["proposed"] += 1
            if pick == row["truth"]:
                stats["correct"] += 1
                stats["hsn_ok"] += bool((res.get("checks") or {}).get("hsn", {}).get("ok", True))
            else:
                stats["wrong"] += 1
        positives = stats["records"] - stats["negatives"]
        pct = lambda a, b: round(100 * a / b, 1) if b else None  # noqa: E731
        return {"records": stats["records"], "proposed": stats["proposed"], "precision_%": pct(stats["correct"], stats["proposed"]),
                "recall_%": pct(stats["correct"], positives), "false_merge_%": pct(stats["wrong"], stats["proposed"]),
                "false_split_%": pct(stats["no_proposal"], positives), "hsn_compatible_%": pct(stats["hsn_ok"], stats["correct"]),
                "repeated_rejected": stats["repeated_rejected"]}

    def handle(self, *args, **options):
        sions = options["sion"] or ["E1", "E5", "E126", "E132", "A3627"]
        self.stdout.write(f"truth={options['truth']} (links = existing single master links incl. rule-based auto-links: PROXY, not human-verified)")
        for sion in sions:
            rows = self._decision_records(sion) if options["truth"] == "decisions" else self._records(sion, options["sample"], options["seed"])
            if not rows:
                self.stdout.write(f"{sion}: no labelled records")
                continue
            # Hide each record's own link from the matcher: rejected history is empty for eval keys.
            suggestions = suggest(rows)
            det = [merge_ai(s, None) for s in suggestions]
            self.stdout.write(f"{sion} deterministic: {self._score(rows, det)}")
            if options["semantic"]:
                self.stdout.write(f"{sion} hybrid:        {self._score(rows, self._semantic(rows, suggestions))}")
        self.stdout.write(f"master items available: {ItemNameModel.objects.filter(is_active=True).count()}")
