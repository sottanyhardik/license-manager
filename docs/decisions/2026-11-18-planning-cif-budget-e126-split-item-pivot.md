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
