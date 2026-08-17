# SION plan database migration report

Status: **GENERIC SCHEMA/ENGINE AND INACTIVE DB BACKFILL COMPLETE; RUNTIME CUTOVER GATED**

## Implemented expansion (2026-08-17)

- `SionPlanningProfile`, ordered `SionPlanningAction`,
  `SionPlanningOutputMapping`, and auditable `SionPlanningRun` models landed in
  migrations 0020/0021. Rules now have immutable stable migration keys.
- `DatabaseDrivenSionPlanner` executes the closed generic action vocabulary
  without SION-code dispatch: first-match predicates, grouping, mapped and
  structured pricing, CIF waterfalls, milk splits, ratio splits, quantity
  flooring, mop-up, value-gain rebalancing, rounding, and output mapping.
- Safe expression support now includes item-name context, word tokens and
  negative prefix matching. Formula configuration is whitelisted and never
  evaluated as source code.
- Deterministic E1, E5, E126, E132 and A3627 profiles/rules/actions/mappings
  were imported into the local database, inactive by design. Re-running the
  importer creates no duplicates.
- `compare_sion_planner` and `compare_all_sion_planners` compare ordered row
  identity, Decimal price/quantity/value, splits and remaining CIF.

Exact persisted-DB golden comparison result:

| SION | Cases | Differences | Result |
|---|---:|---:|---|
| E1 | 2 | 0 | PASS |
| E5 | 3 | 0 | PASS |
| E126 | 2 | 0 | PASS |
| E132 | 2 | 0 | PASS |
| A3627 | 2 | 0 | PASS |

Runtime callers have deliberately not been switched yet. The golden datasets
prove the generic numerical primitives, but the live auto-plan adapters also
carry physical-group anchoring and existing split-preservation behavior that
still requires read-only real-data shadow coverage before lossless cutover.

## Transitional legacy-mechanics bridge

`SionPlanningExecutionService` is now the single temporary adapter registry.
For E1 and E5 it loads active DB rules in persisted priority order, resolves
their profile-owned output categories, performs classification from those DB
expressions, and passes the resulting typed items into the unchanged
`plan_e1_items` / `plan_e5_items` waterfall functions. Focused old-versus-DB
tests compare the complete result objects exactly and pass for both engines.

The SION-first API explicitly accepts omitted or empty `license_ids`; both
forms resolve the eligible company-scoped DFIA universe. The frontend now
omits an empty filter for PLAN and Preview. Non-empty identifiers remain an
optional restriction with the existing tenant checks.

E126/E132/A3627 remain on their existing execution adapters until their
low-level self-classifiers can accept the same resolved DB configuration
without changing split, preservation, grouping or weighted-price mechanics.

### Canonical NEW / FORCE ALL execution (2026-08-17)

The REST endpoint and `plan_norms` command now invoke the same
`SionPlanningExecutionService` with mode `NEW` or `ALL`. Both reload active DB
rules for the selected SION in priority order; neither accepts browser rules.

- `NEW` is the backward-compatible default. It uses active licenses with
  positive live balance and skips licenses already planned to at least 99%.
- `ALL` preserves legacy `--all`: reprocess the full eligible universe for one
  selected SION. It never means every SION.
- Empty or omitted `license_ids` selects the normal eligible universe.
- `--dry-run` invokes the same service with persistence disabled.
- A SION row lock serializes API and command runs across rule reload,
  calculation, and persistence.

Supported forms include `plan_norms E1`, `plan_norms --sion E1 --new`, and
`plan_norms --sion E1 --all`. E1/E5 use DB classification plus proven legacy
mechanics. E126/E132/A3627 remain centralized transitional factory adapters
and are not claimed as DB-classifier cutovers.

### License-centric preview (2026-08-17)

The canonical dry-run response is grouped by `license_id`; duplicate top-level
licenses are rejected defensively. Each license contains ordered matched-item
children, matched rule counts/priorities, bulk-loaded existing and proposed
plan snapshots, and a backend-computed `NEW`, `CHANGE`, `NO_CHANGE`, `SHORTAGE`,
or `SKIPPED` status. Exact comparison uses canonical identifiers and Decimal
quantities/prices rather than rendered strings. Summary counts use the same
license objects.

The UI renders one compact license row, backend status badges, and item
expansion keyed by license id. **View Plan** reuses the established
`/licenses/:id/overview?tab=planning` route and its canonical plan-utilization
API instead of introducing another detail implementation. NEW and ALL preview
modes now flow through the API to the same execution service.

The grouping/current-plan comparison adds a fixed three-query bulk load,
covered by regression test. The preserved E1/E5 legacy compute adapter still
has its pre-existing per-license query behavior; changing that adapter is
deferred because this UX correction intentionally does not alter proven
planner mechanics.

### plan-sion 400 resolution

The exact local failure was reproduced: omitted and empty `license_ids` both
reached execution, then the simplified current-price path rejected three E1
items as `MISSING` because their master unit price was zero. It was not a
license-list validation failure.

E1/E5 plan and preview now select the transitional execution bridge whenever a
persisted profile exists. DB expressions classify items in priority order;
`execution_output` supplies the explicit legacy bucket; DB maximum prices
override the applicable fixed/WPC rate; and the existing auto-plan grouping,
waterfall, split, flooring and output construction remain unchanged. Migration
0023 backfills the two approved pre-existing E1 UI rules without priority-based
inference.

Local read-only verification for SION id 1 now returns the same successful
result for omitted and empty license filters: E1, 25 eligible licenses, two
matched legacy-engine lines, `can_plan=true`. Focused endpoint/bridge/E1/E5
regression: 49 passed.

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
- Generic-schema representability: **PASS for audited golden contracts**
- Inactive DB conversion/idempotency: **PASS**
- Persisted-DB golden equivalence: **PASS (11 cases)**
- Read-only current-data equivalence: **PENDING**
- Zero active hardcoded runtime rules: **FAIL**
- Freeze: **WITHHELD**
