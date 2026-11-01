# API contract closure queue

**Proposed V1 audit work queue.** This turns the complete registered API
denominator into reproducible closure batches. It does not change any
operation's `Partial` status: the current complete individual-contract metric
is **0/354**. The denominator and path/method integrity are verified by
[API register validation](api-register-validation.md); the required proof is
defined by the [contract-closure protocol](contract-closure-protocol.md).

## Derivation and reproducibility

Batch counts below are generated from the `tags` column of
[`api-operation-register.tsv`](api-operation-register.tsv), not inferred from
route names. The current tag populations total 354:

| Tag group | Operation tags included | Exact count |
| --- | --- | ---: |
| Identity/security | `auth` (17), `media`, `invoice-documents`, `health` | 20 |
| Financial/entitlement mutation | `allotment-actions`, `allotments`, `bill-of-entries`, `trades`, `payments`, `lines`, `reconciliation`, `license-actions`, `license-item-plans`, `license-items`, `sion-planning-rules` | 112 |
| Licence/ledger/document lifecycle | `licenses`, `license-ledger`, `upload-ledger`, `ledger-task-status` | 66 |
| Read/report/workspace | `active-licenses`, `expiring-licenses`, `reports`, `inventory-balance`, `item-pivot`, `item-report`, `planned-report`, `dashboard`, `import-item-suggestion` | 25 |
| Generic master/peer/task administration | `masters`, `sync`, `tasks`, `mds`, `incentive-licenses` | 131 |
| **Total** |  | **354** |

The register's current schema-derived priority column has 177 `P1` and 177
`P2` values; it is not the source of business priority. The queue assigns
closure order based on mutation/security risk and the owner decisions already
recorded in [decisions required](../00-executive-overview/decisions-required.md).

## Per-operation evidence packet

Each operation must receive one evidence packet before it can leave `Partial`.
This packet is the same for REST actions, direct API views and generated CRUD;
an inherited action cannot inherit an untested authorization/effect claim.

1. Stable `API-*`, method, path, callback and current OpenAPI schema/warning
   disposition.
2. Concrete valid, malformed and boundary request/response or file fixture,
   including response status/body/content type/disposition.
3. Effective action permission and anonymous/wrong-role result, plus D1
   object/company result when applicable.
4. Queryset/object lookup, service/model mutation, transaction/lock/task
   boundary, audit/provenance and rollback/compensation evidence.
5. Known SPA/external consumer or an explicit no-known-consumer disposition.
6. Named focused test IDs: positive, authorization-negative, validation/error
   recovery, and race/retry/idempotency where effects are consequential.
7. API/route/workflow/requirement/acceptance links and a current status.

The first four items are source/test characterisation; items five through
seven make the contract implementation-ready. An owner-policy-dependent
negative result remains `Partial`, even if code currently returns a response.

## Closure batches

| Queue | Population | Dependencies | Required fixture and negative/recovery focus | Exit evidence |
| --- | ---: | --- | --- | --- |
| Q0 — policy/golden prerequisites | 0 operations; controls Q1–Q4 | D1 company/object, D2 balance labels, D3 SION pools; D4 download/token; D5 accounting scope; D6 audit durability | Approved policy matrix or explicitly approved preserve-current limitation; golden financial/entitlement data | Decision log names approver/effective date/scope; affected API packets link the decision. |
| Q1 — identity and externally reachable access | 20 | D1, D4, D6 | Login/refresh/reset/revocation, protected media traversal/object access, invoice capability expiry/view cap, health disclosure; anonymous/invalid/revoked/wrong-role/error cases | Direct endpoint tests and frontend credential/download consumer disposition; deployed proxy/media check remains a separate operational gate. |
| Q2 — financial and entitlement mutations | 112 | Q0 D1–D3, plus D5/D6 for trade/reconciliation/audit rows | Allocation cap/release, BOE create/correct/hide/restore, trade/payment/line reversal, reconciliation immutable allocation/merge/note, plan/replan/rule transitions; wrong/partial role, stale/race, rollback and task-dispatch cases | Golden fixtures and direct API tests prove each mutation's authoritative effects, lock/transaction/recovery and approved scope. Browser states link for every routed action. |
| Q3 — licence, ledger and document lifecycle | 66 | Q0 D1–D4/D6; Q2 where balances/plans are changed | Licence nested CRUD/document parse, dual ledger/report outputs, package/download request/job states, upload parsing/storage cleanup; file/multipart/owner/worker/storage failure cases | Exact DTO/file fixtures, action policy, balance-engine provenance, idempotency/job recovery and protected-download evidence. |
| Q4 — read/report/workspace contracts | 25 | D1/D2/D4/D5; Q2/Q3 source-output parity | Filter/sort/page/empty/error cases, report totals/precision/as-of provenance, pivot async status, export content/type and access denial | Read schemas, report source engine, export authorization and frontend loading/empty/error/denied evidence linked per operation. |
| Q5 — generic masters, peer sync and task administration | 131 | D1, D6; peer provisioning/recovery operational policy | Per-entity allowlist/CRUD and delete protection, MDS outage/compensation, peer token/cursor/replay/media, task transitions/comments/remarks; operator role/dry-run/retry cases | Generated master families expanded to individual method/path/serializer/action packets; peer/task lifecycle, recovery and operator control tests. |

Q1 and non-conflicting characterisation inside Q2–Q5 may run in parallel.
No mutation changes behavior during this audit; any implementation begins only
after the relevant queue has an approved policy and a characterization gate.

## Exact source-register work allocation

The three source-contract registers provide a second, independent way to
split the work without duplicate IDs. Use it when a team is assigned by
backend owner rather than tag:

| Source-register partition | IDs | Count | Primary queues touched |
| --- | --- | ---: | --- |
| Identity/master/sync/task | 018–034, 163–171, 172–248, 249–253, 254–267, 268–269, 315–320, 321–332 | 142 | Q1, Q5 and protected-media portion of Q3 |
| Licence/allotment/BOE/planning/ledger | 003–017, 035–049, 068–074, 080–091, 092–118, 119–127, 128–155 | 113 | Q2, Q3, Q4 |
| Remaining reports/ownership/trade/reconciliation/SION/upload | 001–002, 050–067, 075–079, 156–162, 270–314, 333–354 | 99 | Q1–Q4 |
| **Total disjoint partition** | 001–354 | **354** |  |

The source partition was validated as complete and non-overlapping; it is not
a substitute for Q1–Q5 priority order.

## Already deep-characterised starting points

The queue should reuse, then complete, rather than duplicate bounded evidence:

- [P0/P1 API sample](p0-api-deep-contracts.md): 11 allocation, ledger and
  reconciliation operations;
- [BOE/trade sample](boe-trade-deep-contracts.md): 14 operations;
- [identity/master sample](identity-masters-deep-contracts.md): 12 groups;
- [report/download sample](reports-download-deep-contracts.md): 14 operations;
- [route/API acceptance register](p0-p1-route-api-contract-register.md): 49
  priority route IDs represented by 45 grouped rows.

These documents reduce rediscovery only. They do not raise the completed
contract numerator and must be linked to operation-level packets during Q1–Q5.

## Batch controls and reporting

For each queue, report four separate counts: assigned IDs, packets with
direct source/DTO evidence, packets with named focused tests, and fully
closed packets. Never use a family-level count as a fully closed count.

Before implementation handoff, rerun OpenAPI generation/validation and the
[API register validation](api-register-validation.md). If the operation
population changes, add/reconcile stable IDs before moving a queue's
denominator or acceptance result.
