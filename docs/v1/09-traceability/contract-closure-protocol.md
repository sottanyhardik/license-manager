# Contract-closure protocol

**Proposed for V1.** This protocol turns the discovery registers into a repeatable audit and implementation gate. It does not assert that an operation, route, or symbol is already complete. The current measurable baseline and remaining zero-complete counts are authoritative in [traceability coverage](traceability-coverage.md) and the [completion audit](completion-audit.md).

## Unit of closure

The unit is one registered API operation, one registered frontend route/action, or one named backend boundary. A family-level source review is useful supporting evidence but cannot close an individual unit.

| Required evidence | API operation | Frontend route/action | Backend boundary |
| --- | --- | --- | --- |
| Stable identity | `API-*`, method/path and callback | `UI-*`, path and triggering component | `BW-*` plus source symbol(s) |
| Inputs and outputs | Concrete valid, invalid and boundary fixture; status/body/file contract | Rendered controls plus request and displayed result | Authoritative inputs, return/output and side effects |
| Authorization | Anonymous, wrong-role, and owner-approved D1 object/company case | Client gate plus direct server result; client is never authority | Caller/worker identity and permission/check path |
| State/data effects | Created/changed/reversed records, transaction boundary and cleanup | Loading, empty, success, error and denied states; mutation freshness | Locking, transaction, retry/idempotency and recovery evidence |
| Regression proof | Named focused test(s), exact command and result | Named browser/component test plus linked API test | Named unit/integration/race/recovery test |
| Trace links | Consumer(s), service/model, decision and acceptance criterion | Endpoint(s), state evidence, user task and acceptance criterion | Entry points, API/command/task consumers and affected workflows |

`Verified` requires every applicable cell above. `Partial` means evidence exists but one or more cells have not been directly demonstrated. `Unverified` means no bounded source/test/runtime evidence. A policy-dependent negative case remains `Partial` until the owner approves the relevant decision; it must never be silently marked as passing.

## Closure sequence

Perform these batches in dependency order. Batches can be investigated in parallel, but an operation cannot be marked Verified merely because a neighbouring operation is verified.

1. **P0 policy freeze:** record D1, D2 and D3 approval or explicitly retain the approved limitation. Freeze golden datasets for customs balance, financial balance, allocation/release, plan restrictions and reconciliation reversals.
2. **P0 mutation boundaries:** close APIs and UI actions for allotment allocation/release, BOE correction/hide/restore, trade correction/reversal, reconciliation allocation/reversal, planning/replan and their reports. Require concurrency or stale-state tests wherever a live balance/cap is consumed.
3. **P0 evidence/access:** close protected media, document uploads, exports/PDFs and public/download-token paths. Require denied path traversal/object access, failed storage, malformed file and cleanup/retry evidence.
4. **P1 core lifecycle:** close licence, allotment, BOE, trade, ledger package and user lifecycle CRUD/actions, including direct-role denial and file/task recovery.
5. **P1 reporting and masters:** reconcile frontend-only/schema-gap paths; close reports, dynamic masters, dashboards, sync and maintenance entry points. An endpoint absent from OpenAPI needs an explicit registered compatibility disposition, not a guessed mapping.
6. **P2/P3 and residual static symbols:** work domain-by-domain from the 8,046-symbol register. Prioritize callers of verified P0/P1 boundaries, then background tasks, signals, commands and remaining utilities. Use dynamic registrations and runtime observations to find symbols static parsing misses.

## Evidence recording template

Create or update a bounded contract row using this structure. A row may cite a concise fixture file rather than reproduce sensitive or production data.

```text
ID and capability:
Evidence classification: Verified by code | Verified by test | Observed in running application | Inferred | Proposed | Requires owner approval
Entry point / consumer:
Authorization and D1 scope:
Request / response / file fixture:
Service, models and transaction boundary:
State transition / idempotency / concurrency:
Errors, recovery and operator action:
Existing test IDs and measured result:
Missing test / approval:
Recommended action, priority, dependency and risk:
Status: Verified | Partial | Unverified
```

## Required closure artefacts

For every completed batch, update all applicable records:

- one of the three API operation registers and `api-operation-register.tsv`;
- `frontend-route-workflow-map.md` and the P0/P1 register when a UI action is involved;
- `backend-critical-workflow-map.md` or a domain-specific boundary record;
- `requirements-to-code.md`, `requirements-to-tests.md` and the relevant acceptance/milestone row;
- `traceability-coverage.md`, recording a numerator only after all required evidence exists;
- `execution-log.md`, with command, non-secret environment assumptions and actual result.

## Quality gate for the next implementation milestone

No policy-affecting or data-migrating implementation may start until D1–D3 are approved or that milestone is explicitly designed to preserve the current behavior without selecting a new policy. No high-consequence mutation can move to implementation without a failing-or-passing characterization test for its current behavior, an authorized direct-API negative test, and a rollback/recovery assertion. Browser E2E cannot be used as a green gate until the existing harness failures in [the E2E failure analysis](../07-quality-and-operations/e2e-failure-analysis.md) are remediated and rerun.

## Auditable stopping rule

The audit may state completion only when the completion-audit table has no unapproved `Partial` row. If an external environment, owner policy or inaccessible integration prevents direct evidence, record the exact population, evidence attempted, accountable approver and expiry/review date; otherwise leave the population Partial.
