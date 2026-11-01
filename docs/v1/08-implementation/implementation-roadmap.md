# Dependency-aware implementation roadmap

| Milestone | Scope / prerequisite | Exit condition | Priority |
| --- | --- | --- | --- |
| M0 | Approve D1–D6; preserve branch/baseline | Signed decision log, golden datasets selected | P0 |
| M1 | Contract inventory: routers/actions, routes, models, jobs | Endpoint/route/permission map with exclusions | P1 |
| M2 | Financial and entitlement characterization | Customs/financial/restriction output suites pass | P0 |
| M3 | Authorization/object scope and protected media | Negative scope/download/export tests pass | P0/P1 |
| M4 | Additive data/migration preparation | Backup, graph, backfill and recovery rehearsal pass | P1 |
| M5 | Service/API boundaries and durable job contracts | Transaction/idempotency/recovery tests pass | P1 |
| M6 | Design system, route registry, critical workflows | Route state and accessibility acceptance checks pass | P1 |
| M7 | Reporting, integrations, operational gates | Export provenance, observability and E2E gates pass | P1 |
| M8 | Performance, UAT, release handover | Measured budgets and deployment-readiness evidence | P2 |

Parallelizable after M0: M1 frontend route mapping, test/CI work and schema inventory. M2 and M3 block correctness-sensitive workflow redesign. Effort estimates intentionally omitted until owner decisions and endpoint inventory establish scope.

## Milestone execution cards

### M0 — policy and preservation gate

Scope: obtain decisions D1–D6; retain legacy/data/worktree evidence; select representative golden datasets. Excludes implementation changes. Exit: decision log identifies approving owner, effective policy and non-goals for each decision. Recovery: no source/data change exists to roll back.

### M1 — contract and traceability completion

Scope: replace each API/route register `To reconcile` field with action-level evidence or a documented exclusion; map dynamic serializers/models and consumers; map tests to workflow requirements. Expected modules: viewsets, serializers, frontend page/service modules and tests, but this stage is documentation/characterization only. Exit: every 354 API operation and 57 route records has a disposition, permission/consumer/test evidence and acceptance criterion. Risk: generated metadata can hide dynamic behavior; mitigate with source and runtime reconciliation.

### M2 — financial/entitlement characterization

Scope: freeze dual-balance, allocation, SION/restriction, rounding, correction and report contracts with input/output golden cases. Excludes formula consolidation. Prerequisite: D2/D3 approval or an explicit approved “preserve current” policy. Exit: replayable comparison suites and a signed source-of-truth map. Recovery: retain old engine/output during any later migration.

### M3 — security and access-policy implementation plan

Scope: convert D1/D4 into endpoint/download/export/job policy tests; complete protected-media compatibility assessment. Excludes changing access behavior before policy approval. Exit: role/object/company matrix and negative tests match approved policy. Risk: changing multi-company semantics can break legitimate internal workflows; migrate behind explicit compatibility boundaries.

### M4 — additive data/migration readiness

Scope: live-schema reconciliation, constraint/duplicate audit, backup/restore drill and backfill design. Excludes destructive migration. Exit: each proposed schema change has affected data, validation query, rollout order and forward-recovery procedure. MDS CI-equivalent database provisioning is a prerequisite.

### M5–M7 — incremental implementation and workflow UX

Scope: service/API contracts, durable job behavior, shared frontend foundations, then critical licence/allotment/BOE/trade/report workflows. Each task must name its API register IDs, route IDs, migration impact, test additions and user-facing states. Exit: parity tests, action-level authorization tests, browser/axe critical-path tests and operational signals pass. Rollback: compatibility route/API/data reads remain until reconciliation is accepted.

### M8 — release gate and handover

Scope: measured performance budgets, UAT, backup/restore, deploy/worker/observability drills and documentation handover. Exit: all P0/P1 risks closed or formally accepted by owner; no unresolved policy is hidden in code. This milestone cannot be substituted by green unit tests alone.
