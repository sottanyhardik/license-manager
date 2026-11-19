# Product matching — local, free AI (Item Pivot) — 2026-11-18

Owner decisions (this session): no external AI and no generative LLM; free local embeddings with
`sentence-transformers/all-MiniLM-L6-v2` (quantized ONNX, ONNX Runtime CPU); approval links licence import items to
the master item (`ItemNameModel` M2M — this also feeds Auto Plan classification); approver role `LICENSE_MANAGER`.

## Pipeline (precision first)

1. Reuse a prior human decision for the same source key (description + HSN + SION): approved → reused, rejected /
   "different product" → that master is never suggested again.
2. Deterministic matcher (`services/product_matching.py`): normalisation (spelling variants, abbreviations PP →
   polypropylene, Alu → aluminium, plurals, `&`), text similarity + coverage, master names without norm suffix.
3. Semantic candidates (`services/product_matching_semantic.py`, Celery queue `matching` only): MiniLM embeddings of
   the full description (overlapping word chunks, first chunk weighted 1.5×; nothing truncated) with the abbreviation
   expansion appended; cosine against the SION's legitimate master items. Embeddings are persisted once per
   (model version, text hash).
4. Validation for every pick (deterministic or semantic): SION legitimacy (`ItemNameModel.norms`), HSN chapter vs the
   master's existing import items, entitlement-profile aliases (E126 Sunflower → Olive Oil only for E126),
   multi-product descriptions, active planning-rule coverage.
5. Bands (owner spec 2026-11-19): ≥95 HIGH (bulk review) · 90–94 STRONG · 80–89 REVIEW · <80 UNCLASSIFIED (kept
   separate) · any conflict → CONFLICT (never approvable). A semantic-only pick is capped at 89 (REVIEW): semantics discover, humans approve.

Approvals (`POST item-pivot/matching/decide/`, server re-validates) write an audited `ProductMatchDecision`
(previous/new links, user, time) and flag each affected licence for re-planning (not dispatched). No HSN, SION rule,
quantity, CIF, BOE, allotment or plan record is modified (pinned by `test_matching_never_touches_financial_records`).

## Measured accuracy (local DB, 2026-11-18)

`manage.py evaluate_product_matching --sample 300 --semantic` — ground truth = existing single master links
(**proxy**: includes rule-based auto-links, not human-verified). Proposal = HIGH/STRONG/REVIEW band.

| SION | mode | proposed | precision | recall | false merge | false split |
|---|---|---:|---:|---:|---:|---:|
| E1 | deterministic = hybrid | 122/300 | 96.7 % | 39.3 % | 3.3 % | 59.3 % |
| E5 | deterministic | 134/300 | 94.8 % | 42.3 % | 5.2 % | 55.3 % |
| E5 | hybrid | 142/300 | 95.1 % | 45.0 % | 4.9 % | 52.7 % |
| E126 | both | 5/178 | 100 % | 2.8 % | 0 % | 97.2 % |
| E132 | both | 1/300 | 100 % | 0.3 % | 0 % | 99.7 % |
| A3627 | both | 0/300 | — | 0 % | — | 100 % |

Low recall on E126 / E132 / A3627 is mostly multi-product licence wording (e.g. "PP/LDPE/HDPE", oil lists) that is
deliberately never mapped to one master. No accuracy claim beyond these measured figures; re-measure against human
decisions with `--truth decisions` once reviewers have approved / rejected suggestions.

## Install on the server (2 GB RAM, 2 vCPU)

```bash
pip install -r backend/requirements.txt        # adds onnxruntime==1.32.0, tokenizers==0.23.3 (no torch / transformers)
python manage.py migrate license               # 0058, 0059 (additive tables)
python manage.py product_matching_model --status      # arch, AVX2/AVX512/ARM variant, RAM, swap
python manage.py product_matching_model --download    # pinned revision 1110a243…, sha256-verified (~23 MB + 0.5 MB)
python manage.py product_matching_model --benchmark   # load time, ms/record at batch 4 and 8, peak RSS — record the output
celery -A lmanagement worker -Q matching -c 1 --max-memory-per-child=700000 -n matching@%h   # one worker, one task at a time
```

Model files live in `PRODUCT_MATCH_MODEL_DIR` (default `backend/var/models/`, git-ignored). Inference uses 1 thread,
sequential execution, CPU provider, batch 4 (max 8). Jobs pause automatically when `MemAvailable` drops below
`PRODUCT_MATCH_MIN_AVAILABLE_MB` (default 350 MB) and can be paused/resumed from the UI.

Local dev benchmark (Apple M5 Pro, arm64 — **not** the target server): load 0.16 s; 4.5 ms/record at batch 4;
peak RSS of the whole Django process 285 MB (benchmark) / 362–390 MB (full E5 job incl. report build); E5 job
1,175 groups in 6.2 s, re-run 3.5 s with 0 new embeddings. **The server benchmark has not been run from this session.**

## Consolidation integrity — before vs after (local DB, 2026-11-19)

`overview.integrity` (Item Pivot intelligence) compares the unconsolidated per-source-record totals with the
consolidated product rows; the Overview tab shows it. Filters: active licences, min balance 200. Measured with the
local DB on 2026-11-19 (band counts use thresholds 95/90/80; semantic evidence as persisted locally):

| SION | licences | source records | consolidated products | pending mapping | totals preserved | bands |
|---|---:|---:|---:|---:|---|---|
| E1 | 66 | 1,447 | 106 | 86 | yes (all 7 measures) | HIGH 3 · REVIEW 15 · CONFLICT 34 · <80 20 · none 14 |
| E5 | 54 | 888 | 156 | 149 | yes | HIGH 14 · STRONG 2 · REVIEW 41 · CONFLICT 38 · <80 25 · none 29 |
| E126 | 9 | 89 | 21 | 20 | yes | CONFLICT 15 · <80 3 · none 2 |
| E132 | 13 | 112 | 18 | 17 | yes | CONFLICT 17 |
| A3627 | 28 | 140 | 31 | 28 | yes | CONFLICT 26 · none 2 |

Measures compared exactly (Decimal equality): entitlement, allotted, debited (BOE), billed-without-BOE, available and
planned quantity, planned CIF — e.g. E5 entitlement 61,006,122.563 / allotted 1,226,854.000 / debited
15,040,130.050 / planned qty 2,335,375.497 / planned CIF 4,601,831.10 on both sides. Most E126 / E132 / A3627 records
are multi-product licence descriptions (e.g. "Olive Oil / Sunflower Oil / Cotton seed …", "PP / Aluminium Foil"),
which the validator deliberately refuses to merge into one master item (CONFLICT); they need master-data review.
