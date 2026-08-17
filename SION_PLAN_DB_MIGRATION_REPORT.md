# SION plan database migration report

Status: **BLOCKED BEFORE CONVERSION — exact equivalence is not representable by the current schema**

## Inventory and classification

| Source | SION | Rule / execution order | Price (USD/unit) | Runtime caller | Classification | DB representable |
|---|---|---|---:|---|---|---|
| `services/e1_plan.py` | E1 | Other confectionery; cocoa; milk; egg; juice; tartaric; aluminium; PP | 3; 10; dynamic 6.50/4.40/1.50; 25; 2.50; 1.50; 4.50; 1.20 | auto-plan, norm fallback, Item Pivot | Active | No |
| `services/e5_plan.py` | E5 | Fibre; conditional milk/oil order; WPC; wheat mop-up | 3; dynamic milk; 25; 1.80/1.20/5; dynamic | auto-plan, norm fallback, Item Pivot | Active | No |
| `services/e126_plan.py` | E126 | Nuts; PKO; olive; 50/50 split and rebalance | 3; 1.80; 5 | auto-plan, norm fallback | Active | No |
| `services/e132_plan.py` | E132 | Nuts; yeast; PKO; RBD; cheese; aluminium; 40/60 split and rebalance | 3; 5; 1.80; 1.20; 5.50; 4.50 | auto-plan, norm fallback, Item Pivot | Active | No |
| `services/a3627_auto_plan.py` | A3627 | Rutile; titanium; soda ash; PP | dynamic 2.50/3.50; 2; .70; 1.20 | PlannerFactory writes | Active | No |
| `services/planner_factory.py` | all five | hardcoded dispatch registry | n/a | command and compatibility service | Active dispatcher | No |
| `services/norm_plan.py` | E1/E5/E126/E132 | manual-first merge, norm fallback, allotment subtraction | derived | Item Report, Balance Excel | Active duplicate | No |
| `views/item_pivot_report.py` | E1/E5/E132 | direct legacy calculations | derived | live reports | Active duplicate | No |
| `services/milk_planner.py` | E1/E5 | balance-dependent DWP/SWP split | 6.50/4.40/1.50; WPC 25 | E1/E5 engines | Active shared | No |
| `services/item_matcher.py` | A3627/other reports | hardcoded ORM predicates | n/a | A3627 and reports | Mixed active configuration | Not wholesale-migratable |

No `PP_PLAN` implementation was found; PP is an output category inside E1/A3627. Frontend `reports/Sion*` pages are report shells, not duplicate Module 06 editors. Tests are golden behavior evidence, scripts are tooling, and historical migrations must remain.

## Exact semantics and evidence

- E1 classifier/exclusions: `e1_plan.py:88-155`; eight-step shared-CIF waterfall: `e1_plan.py:225-318`. Auto planning groups physical items with minimum quantity 50. Milk may emit multiple balance-dependent lines.
- E5 classifier: `e5_plan.py:95-148`; waterfall: `e5_plan.py:233-366`. It has a global milk feasibility branch, oil ordering, flooring, minimum quantity 50, and wheat CIF mop-up.
- E126 split/rebalance: `e126_plan.py:119-376`. One record may split 50/50 between PKO and olive and then shift quantity using remaining CIF.
- E132 split/rebalance: `e132_plan.py:125-436`. One record may split 40/60 between PKO and cheese and then rebalance in stable order.
- A3627: `a3627_auto_plan.py:129-290`. Rutile price depends on original weighted import price and quantities are floored.

Legacy prices are assigned/capped allocation rates, often reduced to exhaust shared CIF. They are not current-price eligibility ceilings.

## Active callers

- `management/commands/plan_norms.py:33,115-225` dispatches `PlannerFactory` and writes plan rows outside dry-run.
- `canonical_planning_service.py:356-500` retains a callable legacy candidate/write service.
- `norm_plan.py:117-255` is called by `views/item_report.py:303-320` and `exporters/license_balance_excel.py:1399-1414`.
- `item_pivot_report.py:1261-1490` executes E1/E5/E132 on live report routes.
- `core/management/commands/seed_e132_plan_items.py` imports legacy E132 order.
- Current Module 06 endpoints use only `SionRulePlanningService`.

## Schema and equivalence gap

The current model stores a predicate, one Decimal ceiling, unit, priority, active flag, and version. The executor checks a current master price against the ceiling, requests full available quantity, and writes at that current price.

Exact conversion additionally needs generic DB primitives for stable migration identity/provenance, item-name and token predicates, first-match output categories, physical grouping/minimum quantity, fixed/aggregate/floor/mop-up allocation strategies, multi-output ratios, global conditions, milk formulas, post-waterfall rebalance/preservation, and weighted-price selectors.

Without them, seeded rows change matches, prices, quantities, line identities and CIF consumption. Therefore no rule was inserted and no legacy caller was removed.

## Result

The local DB currently has zero `SionPlanningRule` rows, so old/new real-data equivalence cannot yet be run. An idempotent importer must follow the generic action-schema implementation and golden suite.

- Inventory/classification: **PASS**
- Caller tracing: **PASS**
- Semantic extraction: **PASS**
- Current-schema representability: **FAIL**
- DB conversion/equivalence: **NOT RUN — would be lossy**
- Zero active hardcoded runtime rules: **FAIL**
- Freeze: **WITHHELD**
