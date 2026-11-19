# 2026-11-18 — Planning CIF budget, E126 fixed split, Item Pivot canonical figures

Owner decisions taken in session (Claude Code, 2026-11-18).

## 1. Auto Plan when licence CIF is insufficient — KEEP current behaviour

- The planner keeps each line's full quantity and lowers its effective unit rate so the total planned CIF fits the
  available budget (`partial_mode: REDUCE_EFFECTIVE_RATE`; `CanonicalPlanningService` consumes one licence-wide
  ceiling line by line).
- The ceiling is `min(live financial balance (tolerance-zeroed below 500), SION export CIF − actual BOE −
  unlinked-allotment CIF)` (`SionPlanningExecutionService.plan_sion`).
- Evidence: 1,201 real local Auto Plan previews (E1/E5, rolled back) — 0 over the ceiling, 0 negative remaining.
  Invariant tests: `backend/apps/license/tests/test_planning_cif_budget_invariants.py`.

## 2. E126 Vegetable Oil — fixed 50:50 split, no PKO → Olive shift (BUSINESS-RULE CHANGE)

- Removed `E126:ACTION:005:REBALANCE` (VALUE_GAIN_SHIFT) from the E126 registry definition
  (`sion_legacy_configurations.py`). PKO and Olive Oil (+ Sunflower → Olive entitlement) are independent;
  spare CIF stays unplanned instead of moving quantity between them.
- Golden case renamed `split_fixed_50_50_no_rebalance`: 100 qty, balance 400 → PKO 50 @ 1.80 = 90.00,
  Olive 50 @ 5.00 = 250.00, remaining 60.00 (was PKO 31.25 / Olive 68.75, remaining 0).
- E132 (`E132:ACTION:005:REBALANCE`) and all other norms are unchanged.
- Deployed DB planning profiles imported earlier from the registry are not altered by this change; re-import or
  edit them deliberately if a production E126 profile carries a REBALANCE action.

## 3. Item Pivot report — use the canonical balance engine

- The report's licence/item balances must come from `LicenseBalanceCalculator` (signed balance + `is_over_utilised`,
  billed-without-BOE term, `BOEAllotmentAllocation` netting), replacing its own formulas
  (audit: `docs/reports/item-pivot-audit-2026-11-18.md`). Figures will change for some licences; requires an
  independent financial-integrity review before commit.

## 4. Item Pivot product identity — master item (`ItemNameModel`) per SION

- One canonical product row per `ItemNameModel` × SION; the classifier category is kept as an attribute; import
  items without a master-item link stay separate as "Unmapped" and are never auto-merged.

## 5. Product matching — free local embeddings only (later the same day)

- No external AI provider and no generative LLM (an Anthropic integration was prototyped and removed before commit).
  Matching = deterministic rules + local `all-MiniLM-L6-v2` quantized ONNX (ONNX Runtime CPU, `tokenizers`), pinned
  revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, sha256-verified, run only in the Celery `matching` queue.
- Approval links import items to the chosen master item (`ItemNameModel` M2M), which also feeds Auto Plan
  classification; every decision is audited (`ProductMatchDecision`) and flags affected licences for re-planning.
- Approver role: `LICENSE_MANAGER`. Bulk approval only for HIGH conflict-free suggestions.
- **Superseded 2026-11-19 (owner spec "AI-assisted product consolidation"):** bands are ≥95 strong (suggested,
  bulk-eligible; never auto-approved) · 80–94 probable (user review; shown as 90–94 / 80–89) · <80 kept separate ·
  any SION / entitlement conflict blocks approval regardless of confidence. Semantic-only picks stay capped at 89.
- Details and measured accuracy: `docs/reports/product-matching-local-ai.md`.

## 6. Product Intelligence Engine — our own, database-trained (2026-11-19)

- Owner rule: no Ollama, no hosted or paid inference. The engine is deterministic rules + approved aliases + char
  n-gram TF-IDF + the existing local MiniLM ONNX embeddings + a numpy pair classifier trained **only** on human
  decisions (`ProductMatchDecision`, BOE / allotment `USER_SELECTED`). Rule-derived mappings (master auto-links,
  `APPROVED_ALIAS`) are proxy evaluation data, never labels. No new dependency (scikit-learn not approved → no RF / SVM).
- Lifecycle: versioned dataset → candidate → held-out evaluation (group split by wording) → explicit, audited promotion
  through a gate (precision ≥ 95 %, Wilson lower bound ≥ 80 %, false merges ≤ 5 %, recall ≥ 50 %, ECE ≤ 10 %, ≥ 10 per
  class in holdout, not worse than the active model) → rollback keeps the previous model. Nothing retrains or promotes
  automatically; no model approves a match; a model-only score without textual support is capped below STRONG.
- Aliases (`ProductAlias`) are matching-only; approval of a single-product wording records it. They never write the
  planning-rule `SionInputAliasConfig`.
- Tracker: `docs/PRODUCT_INTELLIGENCE_AUTONOMOUS_EXECUTION.md`.

## 7. Mapping changes drive Item Pivot + automatic re-planning (Part 15, owner answers 2026-11-19)

- **Scope: both mappings.** Product mapping (import item → master links from Product Matching approvals, bulk
  consolidation and its revert) *and* BOE / allotment debit targets (`planning_target_item`). Multi-product
  classifications (no links) change Item Pivot grouping only (`NO_PLANNING_IMPACT`).
- **Automatic re-planning** through the existing pipeline (`LicenseReplanRequest`, licence source / applied revisions,
  `planning.replan_license` REPLACE with retry + idempotency). Every change is versioned (`MappingChange`, license/0063)
  with the affected licences' plan lines and canonical CIF archived first; status PROPAGATING → PUBLISHED / FAILED
  (retryable); Item Pivot flags stale licences and shows a provisional banner until published.
- **Bulk consolidation follows Part 15** (overrides that spec's §7 "do not change planned quantities").
- BOE / allotment *header* debit-target changes did not re-plan before; a signal now versions and re-plans them.
- The engine still REPLACEs (deletes) generated plan lines; history is preserved in the change archive. Turning the
  engine into soft-supersede (and a posted / frozen plan state, which does not exist today) would change every plan
  consumer — not done; needs a separate owner decision.
- The E1 PP consolidation is applied by the owner through the UI (not by an agent).
