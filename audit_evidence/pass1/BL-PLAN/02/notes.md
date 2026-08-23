# BL-PLAN-02 — "PP" SION norm class has zero Auto-Plan / norm_plan coverage
(73 of 228 real licenses, 32%)

## Classification
Improvement (feature-coverage gap), NOT a defect — `detect_norm()`
(`backend/apps/license/services/norm_plan.py`) is an explicit whitelist
(`E132`, `E126`, `E5`, `A3627`, and the `"E1" in code` family); any other
`norm_class` code, including the real, active `PP` SION norm class, falls
through to `return ""`. `PlannerFactory` (`planner_factory.py`) mirrors this
— `PP` is simply never registered. This looks like a deliberate,
intentional scoping decision (the codebase is visibly mid-rollout of one
new norm at a time — `A3627` was added most recently, per the in-progress,
out-of-scope `a3627_auto_plan.py` in this same working tree) rather than a
broken calculation, so it is reported as an improvement, not fixed here.

## Evidence
`query.py` / `query_result.txt` (this directory) — real DB query against
all 228 licenses:
  * Export-item `norm_class` distribution: `E5: 76, PP: 73, None: 51, E1:
    25, E132: 2, A3627: 1`.
  * `detect_norm()` returns `''` (no norm recognised) for 124 of 228
    licenses — 73 of those are the active `PP` norm class, the other 51
    have no `norm_class` set at all (a separate, pre-existing data-quality
    gap, not a code defect).
  * `PlannerFactory.supported_norms()` = `['A3627', 'E1', 'E126', 'E132',
    'E5']` — `PP` is absent; `PlannerFactory.is_supported('PP')` is
    `False`.

## Effect
For every one of the 73 real `PP`-norm licenses (32% of the entire license
book — the single largest norm-class group after `E5`):
  * `/auto-plan/`, `/auto-plan-all/`, and `/e1-auto-plan/`
    (`views/item_plan.py`) all return "unknown norm" / skip the license
    entirely — no Auto-Plan is ever generated;
  * `norm_plan_for_license()` / `effective_plan_for_license()`
    (`norm_plan.py`) return an empty per-item plan map, so the Item Pivot
    Report / License Overview Planning tab / Balance Excel export show no
    pre-filled utilization figures for these licenses unless a MANUAL plan
    is entered by hand for every item.

## Suggested follow-up (not implemented — read-only pass; also an
improvement, never fixed in this pass per instructions)
Confirm with the business whether `PP` planning rules are simply not yet
specified (most likely, given the in-progress `A3627` precedent), and if
so, prioritize a `pp_auto_plan.py` engine analogous to the existing four,
registered the same way `A3627` was.

## Confidence
High — directly confirmed by source code (`detect_norm`,
`PlannerFactory._load_defaults`) and by live query against the real
228-license database.
