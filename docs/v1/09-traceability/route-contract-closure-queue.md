# Route contract closure queue

**Proposed V1 audit work queue.** This partitions all 57 registered frontend
routes into reproducible closure batches. It does not promote any route from
`Partial`: the current complete route/API/state/browser/permission-contract
metric remains **0/57**. The denominator and cross-register identities are
verified by [route-register validation](route-register-validation.md).

## Exact, disjoint route partition

The batches below use stable UI IDs from
[the frontend route register](frontend-route-register.tsv). They are
deliberately grouped by user workflow and closure dependencies, not by the
current TSV `priority` field, which incorrectly labels all routes P1.

| Queue | Route IDs | Count | Primary closure dependencies |
| --- | --- | ---: | --- |
| U1 — access, shell and safe destinations | UI-012–017, UI-047, UI-049, UI-057 | 9 | D1/D4; credential/session behavior, protected media and direct-server denial |
| U2 — reports and export workspaces | UI-001–011 | 11 | D1/D2/D4/D5; report schema-gap reconciliation, precision/provenance and protected blob handling |
| U3 — financial trade workflows | UI-018–034, UI-045 | 18 | D1/D2/D3/D5/D6; live balance/allocation/reconciliation and correction/recovery contracts |
| U4 — incentive/ledger/document lifecycle | UI-035–044, UI-046 | 11 | D1/D2/D4/D6; package/job/storage/replan and redirect compatibility contracts |
| U5 — settings, masters and administration | UI-048, UI-050–056 | 8 | D1/D4/D6; dynamic-master allowlist/MDS, user privileges and activity-history durability |
| **Total** | UI-001–057 | **57** |  |

The exact P0/P1 subset is independently represented by the
[P0/P1 route/API register](p0-p1-route-api-contract-register.md): **49 IDs in
45 rows** after the four SION and two ledger-detail aliases are expanded.
The eight excluded IDs are UI-014, UI-016, UI-036, UI-037, UI-046, UI-049,
UI-056 and UI-057. Their exclusion from that initial priority subset does not
remove them from this closure queue.

## Per-route evidence packet

Each route exits `Partial` only when its packet contains direct evidence for
every applicable item. A shared page component or client guard is supporting
evidence, not a substitute for a route/action packet.

1. UI ID, route expression, page component, known client role gate and route
   alias/redirect disposition.
2. Explicit user task(s), rendered server/API dependencies and request/response
   fixture references; each source-only or OpenAPI gap must be reconciled or
   deprecated with compatibility evidence.
3. Browser/component evidence for loading, empty, success, error and denied
   states (`L/E/S/D`), plus keyboard, focus, labels, responsive dense-data and
   route recovery behavior that applies to the page.
4. Direct API evidence for anonymous, wrong-role and the D1-approved
   object/company result. Client-side hiding or redirect is never server
   authorization proof.
5. For a mutation, data-effect cleanup, destructive confirmation, stale/race
   or idempotency result, audit/provenance behavior and actionable recovery.
   For download/export, content type/name/provenance, authorization, blob
   error and credential-in-URL disposition are required.
6. Named focused component/browser and API test IDs, actual command/result,
   linked acceptance criterion and current evidence label/status.

## Queue-specific execution order

| Queue | First audit/implementation sequence | Exit evidence |
| --- | --- | --- |
| U1 | Freeze approved credential and company/object policy; test login/reset/session expiry/redirect sanitization, direct API denial, protected PDF viewer failure and NotFound/Unauthorized/Forbidden recovery. | Auth/media route state matrix plus matching direct-API negative tests; no token disclosure in UI/download flow. |
| U2 | Reconcile source-only report paths with OpenAPI, freeze financial report fixtures, then test filters/totals/empty/error/export/retry at desktop and narrow viewports. | Each report identifies source engine/as-of/filter provenance and protected-download outcome; schema gaps resolved or explicitly deprecated. |
| U3 | Start with UI-021/025/032/045 P0/P1 actions after D1–D3; then close CRUD/list/reconciliation route families. Run browser states only against fixtures that assert server-side cap, balance, reversal and role effects. | Golden financial/entitlement cases, direct role/object/race tests and full L/E/S/D browser contracts for each routed action. |
| U4 | Characterize package/upload/recovery state machines and protected file delivery before incentive CRUD/compatibility redirect polish. Use controlled storage/worker fixtures. | Job owner scope, retry/failed/ready/download recovery, file validation/cleanup and redirect behavior are proven. |
| U5 | Enumerate dynamic entity allowlist and privilege boundaries; close user lifecycle/settings/MDS unavailable/activity-history states. | Per-entity/API role matrix, admin destructive/self/privileged-target cases, MDS error recovery and D6-appropriate audit presentation. |

U1 and source characterization inside U2–U5 can run in parallel. A route
cannot become Verified merely because its shared `MasterList`, `MasterForm`,
or `ProtectedRoute` component has evidence elsewhere.

## Existing evidence to reuse, not duplicate

- [Frontend P0/P1 action contracts](frontend-p0-action-contracts.md) cover
  ten action surfaces across 14 UI IDs.
- [Admin/report/upload action contracts](frontend-admin-report-action-contracts.md)
  cover ten surfaces across 13 UI IDs.
- [Route-by-route redesign](../03-ui-ux/route-by-route-redesign.md) provides
  a proposal for every UI ID; it is not browser evidence.
- [Current-state audit](../03-ui-ux/current-state-audit.md) has only two
  read-only running observations: login and BOE list.
- [E2E baseline](../07-quality-and-operations/e2e-baseline.md) is currently
  failing (68 passed / 54 failed / 8 skipped) and cannot act as a green gate
  until its harness, fixture and contrast defects are repaired.

## Priority metadata control

The `frontend-route-register.tsv` `priority` column must not be used as a
decision source until M0/M1 reconciles it with the 49-ID P0/P1 subset. The
reconciliation must either assign approved P0–P3 values per UI ID or add a
separate, documented `implementation_priority` field. Alias expansion must
be machine-readable so the P0/P1 49-ID selection can be reproduced without
interpreting prose ranges.

## Reporting and stop rule

For each queue, report separate counts for: assigned UI IDs; known API
dependency disposition; component/browser L/E/S/D evidence; direct API
authorization/error evidence; accessibility/responsive evidence; and fully
closed route packets. Do not collapse any of those counts into route
completion. Before V1 handover, rerun the route register validation and the
repaired E2E/axe strata; a changed route population requires a new stable UI
ID/disposition before its evidence can be counted.
