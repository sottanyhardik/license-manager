# Product Intelligence — autonomous execution tracker

Owner specs: "Item Pivot — AI-assisted product consolidation" + "Build our own AI product intelligence engine"
(2026-11-19). Constraints: no Ollama, no hosted / paid inference, CPU-only, our own database-trained layer, no push,
no deploy. Summary checkpoint also in `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md` (`CHECKPOINT:product-intelligence`).

## Current phase

Independent review done and all 10 findings fixed (below); full gates → local commit.

## Independent review (code-reviewer, 2026-11-19) — all resolved

| # | Sev | Finding | Fix |
|---|---|---|---|
| 1 | HIGH | HSN features leaked the label (approval links the items whose HSN then defines the master profile) | `PairFeaturiser` excludes the decision's own import items (`exclude_import_ids`); test |
| 2 | HIGH | `alias_exact` leaked the label (approval creates the alias) | feature removed; aliases stay a 100 % suggestion path; test |
| 3 | MED | label groups differed by source; first label kept | group = normalised wording; latest human label wins; test |
| 4 | MED | model-only score could reach HIGH / bulk | capped below STRONG unless text score ≥ 80; test |
| 5 | MED | broken artifact silently disabled the model; promote didn't verify | `logger.exception`; promote / rollback load + checksum first; test |
| 6 | MED | admin GET scanned all labels; any viewer could force inventory refresh | label counts cached 60 s; refresh managers only |
| 7 | MED | gate on tiny holdouts | ≥ 10 per class in holdout + Wilson 95 % lower bound ≥ 80 %; tests |
| 8 | LOW | alias GET without report permission | `ReportPermission` check; test |
| 9 | LOW | `"false"` parsed as true; no run lock; broker error → 500 | strict parse, 30-min cache lock (409), broker error → 503; tests |
| 10 | LOW | NULL-SION aliases not unique | migration `0061` partial unique constraint |

## Part 15 — mapping changes drive Item Pivot + automatic re-planning (owner answers 2026-11-19)

- Decisions: both mappings (import-item master links; BOE / allotment debit targets), automatic re-planning, bulk
  consolidation follows Part 15, the E1 PP consolidation is applied by the owner via the UI (an agent apply run was
  rejected — no agent writes to `lmanagement`). Decision record §7.
- `MappingChange` (license/0063) = mapping version: kind, refs, affected import items / licences, `before` archive of every
  active plan line + canonical BOE / allotment / available CIF, `after` captured once published; status PROPAGATING →
  PUBLISHED / FAILED (retryable), NO_PLANNING_IMPACT for multi-product classification.
- Hooks: `decide()` (now `dispatch=True`), consolidation apply / revert, `decide_products` (Item Pivot only), new
  post_init / post_save signal for BOE / allotment **header** debit-target changes (these did not re-plan before).
- Re-planning = the existing pipeline (`LicenseReplanRequest`, licence source / applied revisions, `planning.replan_license`
  REPLACE + retry / coalescing). Status uses each licence's latest request (coalesced requests count); a stale licence
  with no active request is re-requested.
- Item Pivot: licence `planning_stale`, overview `planning_stale_licence_count` + `mapping_propagation`; UI banner +
  "Re-planning" badge; "Mapping changes" tab (versions, impact before / after per debit item, actuals separate, retry).
- Not done (owner decision needed): the engine still physically REPLACEs generated plan lines (history kept in the
  archive); there is no posted / frozen plan state; bulk target backfill commands create one version per changed header.

## Bulk canonical consolidation (E1 PP → "PP") — implemented, not applied

- `product_intelligence/consolidation.py` + API `matching/consolidation/` (preview), `/apply/`, `/revert/`; UI tab
  "Bulk consolidation". Eligible = one product, identity equal after packaging / grade qualifiers, HSN chapter of the
  target (≥ 10 % of its links), ≤ 1 current link; re-classified under row locks at apply (all-or-nothing); previous
  links audited (`ProductMatchDecision`, matcher bulk-consolidation-v1); aliases recorded; revert per batch restores
  only links unchanged since (locked, exact audit). Masters are never deleted.
- Real E1 preview (local DB, target PP #94): 1 eligible group = 2 records (`PP - E1` → `PP`); 120 records already PP;
  11 for review (HSN 08 / 48 / 76, typos, several links); 615 multi-product excluded.
- Item Pivot intelligence now also accepts masters legitimate via `ItemNameModel.norms` (opt-in `include_norm_links`;
  classic pivot unchanged — regression test) and labels a row with the licence's norm (canonical PP had FK A3627).

## Review round 4 (code-reviewer + DGFT domain auditor) — resolved

Domain HIGH: export-item norm filter accidentally moved under the new opt-in branch (classic pivot would have stopped
scoping export items) → restored + regression test. Code HIGH: apply now re-validates every record under lock; status
derivation sees coalesced requests. MEDIUM: orphaned stale licences re-requested; revert audit records only restored
links, locks the batch, keeps aliases on conflict; trailing category labels keep a description multi-product;
`P.P.` no longer matches "p.p.m". Remaining LOW (documented): condition clauses end at ";" / sentence end;
impact GET recomputes the live state while unpublished.

## Multi-product selection and final classification (owner spec 2026-11-19) — implemented

- **Model** `ProductMatchSelection` (migration `license/0062`): one row per selected product — source key, import-item ids
  (provenance), original description + HSN, detected phrase, segment index (null = added manually), canonical master,
  match score, SION, entitlement, checks, status APPROVED / REVOKED, previous + new mapping, user, timestamps. Partial
  unique constraint → an approved (source, phrase, master) exists once (idempotent).
- **Service** `product_intelligence/multi_product.py`: `segment_rows` (per-product candidates + checks, nothing
  pre-selected), `validate_selections` (master exists + active, SION legitimacy, HSN chapter, entitlement per phrase,
  single-product phrase, duplicate phrase / master), `decide_products` (submitted set = final classification; any
  rejected selection → nothing written unless the reviewer explicitly asks for `partial`; deselected → REVOKED;
  unchanged → kept; audited `products_classified`).
- **API** `POST item-pivot/matching/decide-products/` (LICENSE_MANAGER; server recomputes the detected products from data),
  `GET item-pivot/matching/masters/?sion=&q=` (searchable legitimate masters).
- **Financial safeguard (spec §6 / Part 4):** classification only — import-item master links (Auto Plan input), quantity
  and CIF are never touched. Item Pivot shows the record once as `MULTI_PRODUCT` ("allocation pending", not plannable);
  the shared quantity is never attributed to each product. Tests pin licence BOE / allotment / billed / available CIF
  byte-identical and the integrity totals unchanged after approving one and then both products.
- **UI** `MultiProductSelection.tsx` inside the review row: checkbox per detected product (unchecked by default),
  master selector (candidates + all legitimate masters), score, HSN, SION, entitlement, explanation, conflicts, per-row
  rejection reasons; Select all compatible · Clear · Add product · Search masters; summary detected / selected /
  compatible / excluded / requiring review; "Approve the N compatible only" after a rejection.
- **Phrase extraction (Part 7), root causes on real wording:** enumeration markers `(A)…(E)` were deleted with every
  parenthesis before splitting (5 products → 1 segment); a "namely" heading became a product ("modifier"); licence
  condition clauses ("With the condition … is not allowed … as per PC 13") became products; detached modifiers
  ("Dense / Light") became products. Fixed once in `product_matching.segment_pairs` (used by conflict detection and the
  selection UI); regression tests from the real wordings.
- **Labels:** approved selections are verified training labels (phrase → master).

## Local DB observation (2026-11-19 03:21–03:26 UTC) — for the owner

User `hardik` approved 9 matches and marked 1 "different" in the review UI (8 aliases auto-recorded). Each approval
flags licences for re-planning (`dispatch=False`), but the Celery beat + worker running in PyCharm processed those 64
requests: 25 licences re-planned, 87 `LicenseItemPlan` rows rewritten. Report totals for E1 / E5 / E126 / E132 / A3627
(active, min balance 200) were unchanged afterwards. **Owner decision:** should matching approvals trigger automatic
re-planning when the beat is running, or only flag?

## Review round 2 — `/review-diff` (9 reviewers) + DGFT domain auditor, 2026-11-19 — resolved

| Finding (source) | Fix |
|---|---|
| Sunflower → Olive clause also applied to **E5** (domain F1, code-review) — unapproved widening | clause moved to an E126-only `OLIVE OIL` entry in `get_item_filters()`; test. **E5: owner question** |
| E126 record without alias wording could be linked across PKO / Olive (domain F2) | `ENTITLEMENT_HSN_PREFIXES` (E126 only): 1513 → PKO, 1509 / 1510 → Olive; enforced by `_validate` / `evaluate`; test |
| `items.set([target])` silently dropped multi-links (domain F4) | `replace_links` required + UI confirmation; previous links audited; test |
| Holdout used for both selection and gate (python) | three-way split: select on validation, refit, gate on untouched test; test |
| Semantic job stuck RUNNING after any non-embedding error (django, silent-failure) | atomic claim, stale-RUNNING recovery (1 h), catch-all → FAILED with error; idempotent resume; test |
| Bulk approve included rows hidden by a filter (react) | only visible selected rows; selection cleared on filter change; vitest |
| N+1 on `decided_by` in suggest history (performance) | `select_related("decided_by")`; decide scores only requested groups |
| Model with another feature schema could be loaded (python) | `_load_artifact` checks `feature_names`; any malformed artifact → `LifecycleError`; test |
| Dataset artifacts not verified before training (python) | sha256 re-verified over both files; tamper → refused; test |
| Promote race / alias race → 500 (django) | promote re-checks under `select_for_update`, IntegrityError → `LifecycleError`; alias IntegrityError → `MatchValidationError` |
| Alias clash on approval swallowed silently (silent-failure) | logged + `alias_skipped` returned and shown |
| Job GET without report permission; unvalidated job filters; health broadcast per call (security) | `ReportPermission`; filter whitelist + type checks (400); health cached 30 s; audit trail managers-only |
| Stump leaves unregularised; float calibration bins; non-atomic artifact write (python) | L2 = 1 on leaves; integer deciles; tmp + `os.replace`, orphan cleanup |
| UI hid matching / recommendation errors; `"0.00"` shown as +$0; NaN sort; progressbar 0-division (ts, react) | explicit error states + retry; numeric zero check; null-last comparator; guarded progressbar + `aria-valuetext` |
| ORM writes in a view module (architecture gate) | train request moved to `lifecycle.request_training` |

Not changed (reported): `integrity.preserved` is a grouping check (records lost / duplicated / mis-keyed), not an
independent recomputation of the figures — labelled so in the UI; headline status order keeps BLOCKED last
(exhausted entitlement is not an error when other licences are correct); waterfall sign handling in the committed
Overview (`4c19d6d9`) is pre-existing and untouched.

## Architecture (reuses, does not duplicate)

| Spec service | Code |
|---|---|
| Description normalizer | `services/product_matching.py` `normalise`, `product_segments` (existing) |
| Feature extractor | `services/product_intelligence/features.py` `pair_features` — `FEATURE_NAMES` pinned, no financial field |
| Similarity engine | `features.TfidfIndex` (char 3–5-gram TF-IDF + inverted index), `text_score`, local MiniLM ONNX (existing, offline) |
| Historical knowledge repository | `product_intelligence/knowledge.py` (inventory, observations, versioned datasets) |
| Domain classifier | `product_intelligence/learn.py` — numpy logistic regression + boosted stumps |
| Canonical resolver | `product_intelligence/resolver.py` → `GET item-pivot/matching/resolve/` |
| Approved alias registry | `ProductAlias` + `product_intelligence/aliases.py` (matching only; never `SionInputAliasConfig`) |
| HSN / SION / entitlement validators | `product_matching.suggest` → `evaluate()`, `_validate()` (existing; E126 profile is norm-scoped) |
| Confidence evaluator | `product_matching._band` — 95 / 90 / 80; any conflict → CONFLICT |
| Human decision + audit | `product_matching.decide` (`ProductMatchDecision`) + `ProductIntelAuditEvent` |
| Aggregation / eligibility / planning | `services/item_pivot_intelligence.py` (`build_intelligence` + integrity check, `_status`, `recommend_for_licenses`) |
| Training / evaluation / version / rollback | `product_intelligence/lifecycle.py` (`ProductIntelModel`, one ACTIVE, audited) |
| Background processing | Celery queue `matching`: `license.run_product_matching_job`, `license.product_intel_build_and_train` |
| Admin workspace | Item Pivot → "Intelligence admin" tab (`ProductIntelligenceAdmin.tsx`) |

Not used: scikit-learn / scipy / rapidfuzz (not installed; adding them needs owner approval) — so no random forest /
SVM. Ollama models present on the Mac (`qwen3.5:4b`, `qwen3:8b`) are deliberately not used (owner rule).

## Data inventory (local DB `lmanagement`, 2026-11-19, `manage.py product_intelligence inventory`)

| Source | Records | Unique normalised | Duplicates | No description | No HSN | Label trust |
|---|---:|---:|---:|---:|---:|---|
| Licence import items | 26,818 | 1,612 | 21,851 | 3,355 | 3,368 | master links: none 7,306 · one 15,775 · several 3,737 — signal / rule auto-links → proxy only |
| SION import norms | 10,720 | 5,056 | 5,602 | 62 | 10,720 (no HSN in data) | reference vocabulary |
| Bills of entry (`product_name`) | 14,422 | 328 | 6,889 | 7,205 | — | **8 USER_SELECTED (verified)** · 4,140 APPROVED_ALIAS (rule) · 10,274 unmapped (2025-12-02 → 2026-11-18) |
| Allotments (`item_name`) | 6,526 | 343 | 6,183 | 0 | — | 0 verified · 3,911 APPROVED_ALIAS (rule) · 2,615 unmapped |
| Product match decisions | 0 | — | — | — | — | verified (none yet) |
| Product aliases | 0 | — | — | — | — | — |
| Item masters (active) | 98 | — | — | — | — | canonical |
| HSN dictionary | 13,701 | — | — | — | — | reference |

Financial columns (quantity, CIF, debits, allotments, plans) are never extracted.

## Model status

- Dataset `ds-20261119-031424-237953` (after review fixes): 58,486 observations, 7,041 unique normalised
  descriptions, 5 verified labels (8 BOE USER_SELECTED rows de-duplicated by wording), sha256 `f35e8676dcbdf8f0…`.
- Model `pm-20261119-031424-878856`: **INSUFFICIENT_LABELS** (5 positive / 0 negative; needs ≥ 60 with ≥ 20 per class).
  No model is active → deterministic + alias + local-semantic matching. **No accuracy figure is claimed** for a trained
  model; the previously measured deterministic proxy figures stay in `docs/reports/product-matching-local-ai.md`.
- Promotion gate: holdout precision ≥ 95 %, false-merge rate ≤ 5 %, recall ≥ 50 %, ECE ≤ 10 %, and no worse than the
  active model. Promotion and rollback are explicit, audited actions.

## Financial integrity — before vs after (`overview.integrity`, active licences, min balance 200)

Identical before and after the engine work for E1, E5, E126, E132, A3627 (records, entitlement, allotted, debited,
billed, available, planned qty, planned CIF — exact Decimal equality). Figures: `docs/reports/product-matching-local-ai.md`.

## Migrations

`license/0058`, `0059` (earlier session, additive), `0060_product_intelligence_registry` (additive: 4 tables),
`0061_product_alias_global_unique` (constraint). Round-trip test `test_product_matching_migrations.py` (0057 ↔ 0061).
Applied to the local dev DB only.

## Tests (latest real runs)

- Engine + matching + pivot + migration suites: 89 passed (`test_product_intelligence.py` 32 of them).
- vitest item-pivot 15/15; tsc, ESLint clean.
- Playwright `item-pivot-intelligence.visual.spec.ts` with real local data (E1, E5, E126, E132, A3627) + built-in: 3/3
  each (18/18), after the review fixes.
- Full gates: see the commit section below (updated after the final run).

## Known limitations / blockers

1. No trained model can be promoted until reviewers record ≥ 60 verified decisions (≥ 20 per class). Every approve /
   reject / "different" in the review workspace is a label.
2. Random forest / SVM need scikit-learn (dependency approval).
3. SION import norms carry no HSN in the local data.
4. Most E126 / E132 / A3627 unmapped records are multi-product licence wordings — CONFLICT by design (master-data review).
5. The server-side MiniLM benchmark (2 GB Ubuntu) has never been run (no server access from this session).

## Next action

Owner decision needed: should Sunflower Oil count as Olive Oil on **E5** licences (currently E126 only)?
Owner / reviewers: record decisions in Product Matching until ≥ 60 verified labels (≥ 20 per class), then
"Generate dataset + train candidate" and promote only if the gate passes.
