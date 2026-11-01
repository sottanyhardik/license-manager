# V1 acceptance criteria

These are implementation gates, not assertions that the current application
already satisfies them. A feature can be accepted only with evidence at the
appropriate boundary: a client role gate cannot prove a server permission, a
unit test cannot prove file storage or a worker, and a passing narrow fixture
cannot establish a business policy. The current inventory has **354** API
operations, **57** registered frontend routes, and **8,046** indexed backend
symbols; completion posture and denominators are maintained in
[traceability coverage](../09-traceability/traceability-coverage.md).

## Evidence and status rules

| Status | Evidence required before use | Meaning for acceptance |
| --- | --- | --- |
| Verified | Direct code/runtime/test evidence covers the stated criterion and its scope. | May satisfy a narrow acceptance gate only. |
| Partial | A source/test/route is located, but one or more contract, policy, error, recovery or live-runtime facts are missing. | Cannot be accepted; create the named missing test or obtain the decision. |
| Failing | Measured result contradicts the expected criterion. | Blocks affected release scope until repaired, rerun and evidenced. |
| Requires owner approval | The criterion selects a business, security or retention policy not proven by source. | Cannot be implemented by assumption; record the approved option and migration consequence. |

An API/route/action is complete only when it meets the individual closure rule
in the [P0/P1 route-to-API contract register](../09-traceability/p0-p1-route-api-contract-register.md): a concrete request/response/error fixture, anonymous and wrong-role direct API outcome, browser/component coverage of all listed states, asserted/cleaned-up mutation effect, and links back to the operation/route/test records.

## Universal feature gate

Every V1 feature must provide all applicable evidence below.

| Dimension | Measurable acceptance criterion |
| --- | --- |
| Identity and scope | Stable requirement, workflow, API and UI IDs; named owner; explicit inclusion/exclusion and compatibility impact. |
| Authorization | Anonymous, wrong-role and approved-role direct API cases; object/company cases match approved D1 policy. UI concealment/redirect is defense in depth only. |
| Contract and validation | Versioned request/response/file fixtures include valid, malformed, boundary, missing-reference and duplicate input; response status/body/download headers are asserted. Schema gaps are reconciled or explicitly deprecated. |
| Data and transactions | A mutation asserts created/changed/reversed records, audit/provenance and transaction rollback/forward recovery. Consequential concurrent/stale/idempotent actions receive a race/retry case. |
| User experience | Browser/component evidence covers loading, empty, success, server validation, retryable failure, denied and destructive-confirmation states. Keyboard/accessibility and responsive criteria apply to the rendered workflow, not source intent. |
| Observability and recovery | Failure is actionable to an operator/user without exposing secrets; task/export/file flows record an inspectable terminal/retry state. Backup/migration work has validation and forward recovery. |
| Regression evidence | Exact test IDs, command and actual result are recorded. A test only closes the stated operation/route/state; discovered or skipped E2E tests are not green evidence. |

## P0/P1 workflow gates

| Workflow / scope | Acceptance evidence | Decision/dependency |
| --- | --- | --- |
| Authentication, users and protected media (WF-01) | Login/reset avoids enumeration; refresh/revocation/logout contract is tested; direct protected-media checks reject anonymous, wrong-role, traversal and unapproved object access; no unintended credential is placed in URLs/logs. | D1 object/company policy; D4 token/download posture; [security paths](../09-traceability/security-critical-paths.md). |
| Licence, Customs/Financial balances and ledgers (WF-02/03) | Every card/report/export labels source engine and as-of meaning; approved golden data proves rounding, zero floor, hide/restore, trade and allocation effects; no metadata action silently changes a balance. | D2; [balance/allocation contracts](../09-traceability/balance-allocation-function-contracts.md). |
| Planning, SION and replan (WF-04) | Golden plan/restriction cases assert allowed/rejected result; durable request transitions and retry/supersession are tested; stale plan cannot silently overwrite current data. | D3; worker/broker recovery evidence. |
| Allotment allocation/release (WF-05) | Server locks/checks live capacity; decimal/cap/plan isolation, release/reversal, stale UI and competing allocation outcomes are asserted; each data effect has traceable replan behavior. | D1/D3; API-003 and related actions in the route/API register. |
| BOE/import evidence (WF-06) | Parse-to-save failure leaves no unapproved partial business record; correction/hide/restore is idempotent, auditable and recalculates affected ledgers; upload/download authorization and retry/cleanup are exercised. | D1/D2; storage lifecycle. |
| Trade, invoices, payments and reconciliation (WF-07/08) | Create/correct/reverse/link/merge/note actions preserve financial provenance and protected records; invalid references, duplicate/racing requests and dual-role denial are asserted. No feature is labelled GL/bank reconciliation without approved scope. | D1/D2; D5; reconciliation acceptance paths API-282–290. |
| Reports, exports and ledger packages (WF-09/10) | Filters/boundaries/empty data and totals have fixture evidence; blob/PDF headers, content, authorization and failure recovery are tested; package/request ownership, idempotency, checksum and worker/storage retry are proven. | D1/D4; operational recovery. |
| Masters, sync, administration and maintenance (WF-11/12/14) | Dynamic entity allowlist and per-entity permission/validation are asserted; sync duplicate/out-of-order/replay behavior is proven in its supported topology; commands have explicit operator, input, dry-run, backup and recovery procedures. | Peer provisioning/deployment drill; [command contracts](../09-traceability/maintenance-command-contracts.md). |
| Audit history, data lifecycle and operations (WF-13) | Required assurance level, retention/access policy and failure behavior are approved; critical business changes retain the required durable history; proposed data migrations have live-schema, backfill, reconciliation, restore and forward-recovery proof. | D6; [entity lifecycles](../06-data-and-migrations/high-risk-entity-lifecycle-contracts.md). |

## Current non-green gates

- The measured local Playwright/axe baseline is **68 passed, 54 failed, 8 skipped**. It is not an acceptance gate until the harness, fixtures and verified contrast defect are remediated and rerun; see [E2E failure analysis](../07-quality-and-operations/e2e-failure-analysis.md).
- D1–D6 remain **Requires owner approval**. Their recommended defaults and impact are recorded in [decisions required](../00-executive-overview/decisions-required.md); no criterion above selects a policy on their behalf.
- Live schema/data reconciliation, backup/restore, deployed proxy/media posture, worker/broker recovery and peer-sync deployment remain Partial. Source-level model/task evidence cannot close these operational criteria.

## Release-scope exit rule

A release candidate must demonstrate that every included P0/P1 route/action has
an accepted individual contract or an owner-approved, time-bounded exclusion;
all P0 failures are closed or formally accepted by the accountable owner; the
relevant migration/rollback and operational drills pass; and the measured
commands/results are linked in the execution log. A passing unit suite alone
does not satisfy this gate.
