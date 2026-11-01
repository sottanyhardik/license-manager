# SION and planning function contracts

This is a bounded direct-source audit of **15** high-consequence planning,
restriction and plan-enforcement contracts. It supplements the 8,046-symbol
register; static file dependents are explicitly not a caller graph. **C** is
code evidence, **T** is named existing-test evidence, **S** is a static
import/dependent only, and **P** is a V1 proposal. Every row remains
**Partial**. D3 (SION/restriction pool semantics) is required before a
policy-affecting replacement or consolidation.

| ID / symbol | Verified current behavior | Effects, callers, tests and remaining closure | Status |
| --- | --- | --- | --- |
| SP-01 `plan_enforcement.live_allotted_qty` / `live_allotted_value` | **C** [`plan_enforcement.py:50`](../../../backend/apps/license/services/plan_enforcement.py#L50) aggregates non-BOE `AT` allotments live rather than using lagging denormalized item fields. | Query-only. **S** direct file dependents include allocation action, canonical planner, plan views and plan-cap tests. Need transaction-isolation/race/query-budget parity. | P0 / Partial |
| SP-02 `plan_line_status_for` / `plan_line_status_for_many` | **C** [`plan_enforcement.py:86`](../../../backend/apps/license/services/plan_enforcement.py#L86) treats source import-item group plus planning target as allocation identity; it derives residual from live plan-basis debits and not legacy `remaining_*` snapshots. | Read boundary shared by candidate grids and enforcement. **T** `test_allocate_items_plan_line_balance.py`, `test_plan_enforcement.py`, `test_plan_utilization.py`. Need direct action/API response and concurrent plan replacement/allocation evidence. | P0 / Partial |
| SP-03 `planned_totals_for` / `group_used_snapshot` | **C** [`plan_enforcement.py:169`](../../../backend/apps/license/services/plan_enforcement.py#L169) filters only current plan rows and derives original plan totals; [`:193`](../../../backend/apps/license/services/plan_enforcement.py#L193) snapshots live group use at plan creation. | Query-only helpers underpin plan residual presentation. Need D3-approved group semantics, deleted/cancelled/replan parity and bulk/per-row comparison. | P0 / Partial; D3 |
| SP-04 `save_plan_lines_for_license` | **C** atomic full-replace gateway at [`plan_enforcement.py:205`](../../../backend/apps/license/services/plan_enforcement.py#L205) locks licence and existing plan rows, stamps baseline use, consolidates same ceiling rows and replaces disposable projections. | Mutates plan projection; static consumers include item-plan views and canonical planner. **T** plan enforcement/grouping/canonical-planning suites. Need malformed multi-line rollback, concurrent allocate/replan and audit/operator recovery. | P0 / Partial |
| SP-05 `resolve_plan_sion` | **C** [`plan_lifecycle.py:22`](../../../backend/apps/license/services/plan_lifecycle.py#L22) resolves exactly one export norm; missing/multiple norms return explicit unresolved/ambiguous states rather than selecting an arbitrary first row. | Query-only lifecycle identity. **S** allocation action and item-plan view import the module. Need user-facing ambiguity contract and persisted mapping decision under D3. | P1 / Partial; D3 |
| SP-06 `get_current_allocation_plan` | **C** [`plan_lifecycle.py:42`](../../../backend/apps/license/services/plan_lifecycle.py#L42) accepts only one active/non-deleted/non-cancelled line for complete licence/import-item/SION/target identity; multiple candidates are explicit ambiguity. | Read guard for allocation. Need direct allocation status/error tests and race between lifecycle transition and allocation. | P0 / Partial |
| SP-07 `PlanLifecycleService.transition` | **C** [`plan_lifecycle.py:67`](../../../backend/apps/license/services/plan_lifecycle.py#L67) locks the plan, applies finite activate/deactivate/cancel/delete/supersede transitions, `full_clean`s then saves lifecycle fields. | Consequential mutation; caller supplies authorization. Need invalid transition matrix, transition audit, D1 object policy and concurrent state-change tests. | P1 / Partial; D1 |
| SP-08 `SionPercentageCapacity.get_percentage_cap_for_input` | **C** [`sion_percentage_capacity.py:45`](../../../backend/apps/license/services/sion_percentage_capacity.py#L45) computes export-norm eligible quantity × percentage / 100, `ROUND_HALF_UP` to 2 decimals. | Query-only capacity proposal; **T** `test_sion_percentage_feature.py`, `test_sion_generic_integration.py`. Need approved unit/pool/rounding policy and report/API parity. | P0 / Partial; D3 |
| SP-09 `SionPercentageCapacity.get_remaining_capacity_for_input` / `can_allocate_to_input` | **C** [`sion_percentage_capacity.py:164`](../../../backend/apps/license/services/sion_percentage_capacity.py#L164) subtracts planned, allotted and BOE-debited classified quantities; unmapped/nonpositive requests bypass this cap in `can_allocate_to_input`. | Existing code catches relationship exceptions in allotment/BOE aggregation and returns zero, so silent undercount is a specific risk needing characterization. Need locking, failure telemetry and D3 policy. | P0 / Partial; D3 |
| SP-10 `SionRuleResolver.resolve_canonical_input` | **C** [`sion_rule_resolver.py:33`](../../../backend/apps/license/services/sion_rule_resolver.py#L33) normalizes aliases and resolves output+SION, SION, global then `UNMAPPED` scope in order. | Query-only resolver. **T** generic-rule/integration suites. Need duplicate alias uniqueness/live data audit and explicit unmapped operator behavior. | P1 / Partial; D3 |
| SP-11 `SionRuleResolver.get_split_rules_for_output_item` | **C** [`sion_rule_resolver.py:132`](../../../backend/apps/license/services/sion_rule_resolver.py#L132) returns no split mapping unless active percentages total exactly 100. | Query-only configuration gate. Need Decimal/duplicate/empty group, persisted constraint and UI validation contracts. | P0 / Partial; D3 |
| SP-12 `normalize_expression` / `validate_expression` / `evaluate_expression` | **C** [`sion_rule_engine.py:45`](../../../backend/apps/license/services/sion_rule_engine.py#L45) constrains expression depth/nodes/operators/fields, rejects conflicting leaves and treats an empty root as match-none; no dynamic code execution is used. | Pure validation/evaluation. **T** `test_sion_generic_rule_engine.py`, `test_sion_rule_engine_qa.py`. Need serializer/API negative fixtures, rule migration validation and audit history. | P1 / Partial |
| SP-13 `SionRulePriorityService.normalize` / `reorder` | **C** [`sion_rule_engine.py:208`](../../../backend/apps/license/services/sion_rule_engine.py#L208) row-locks the SION and uses temporary priority values before bulk updates, respecting an active-rule unique priority constraint. | Transactional configuration mutation; caller authorization sits above it. Need concurrent reorder, failed second phase, API permission and D1 scope tests. | P1 / Partial; D1/D3 |
| SP-14 `validate_declarative_rules`, `source_unit_value`, `select_unit_value_row`, `solve_unit_value_mix` | **C** [`sion_planning_execution.py:31`](../../../backend/apps/license/services/sion_planning_execution.py#L31) validates strategy and exact 100% split rows; [`:72`](../../../backend/apps/license/services/sion_planning_execution.py#L72) derives source unit value; [`:86`](../../../backend/apps/license/services/sion_planning_execution.py#L86) has deterministic touching-band selection; [`:121`](../../../backend/apps/license/services/sion_planning_execution.py#L121) computes bounded Decimal mixes. | Pure planning calculation. **T** `test_e1_e5_db_config.py`, `test_planning_tolerances.py`, E1/E5 profile suites. Need D3-approved price-band and underfunding treatment/golden export parity. | P0 / Partial; D3 |
| SP-15 `DatabaseDrivenSionPlanner.execute` / split actions | **C** [`database_driven_sion_planner.py:127`](../../../backend/apps/license/services/database_driven_sion_planner.py#L127) validates known action types/unique priorities then executes deterministic action order; percentage split creates provenance and rejects non-100% configuration by leaving unmatched record unchanged. | In-memory plan result, not persistence authority. **T** `test_database_driven_sion_planner.py`, percentage/shortage suites and shadow comparison. Need end-to-end save parity, configuration drift/retry and policy approval. | P0 / Partial; D3 |

## Verified boundaries and V1 guardrails

- Live allotment sums and authoritative plan capacity are calculated at the
  enforcement/allocation boundary. Candidate-grid/snapshot values must not
  authorize a debit.
- Plan lines are replaceable projections while allocation entries form the
  debit record. A schema/UI simplification must preserve that distinction.
- SION configuration intentionally has deterministic resolution, ordering and
  expression safety mechanics, but those mechanics do not determine the
  business meaning of pooled restrictions, eligibility or financial caps.

## Required closure

1. Record the approved D3 policy in examples covering shared pool,
   restriction, percentage, AU/open, unit/rounding and cancellation/replan
   treatment.
2. Add direct API tests for malformed configurations, ambiguous SION/plan
   identities, wrong-role/object scope, stale plan/allocation and concurrent
   reorder/replace/debit conditions.
3. Freeze golden plans through UI/API/report exports, then run durable replan
   and broker-recovery tests before changing planner representation.

This document adds 15 bounded contracts only. It does not convert remaining
planning symbols, endpoint contracts or D3 into verified behavior.
