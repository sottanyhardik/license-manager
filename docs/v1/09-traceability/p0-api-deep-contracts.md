# P0/P1 API deep-contract sample

## Scope and evidence status

This is a bounded, direct-source audit of **11 consequential operations**. It
does not change the `354`-operation denominator or make any operation
complete. Each row is **Partial**: the source, selected DTO fields, principal
mutation/response, authorization class, transaction/recovery behaviour and
named test or consumer evidence are recorded, but no operation has the full
cross-role, object/company-scope, error/recovery and browser-contract suite
required for closure.

`Verified by code` refers to the cited source. `Verified by test` refers to a
named current test; it is not a claim that the test proves every policy.
`Requires owner approval` points to the company/object-isolation decision D1.

| API ID | Method/path | Capability | Audit status | Priority |
| --- | --- | --- | --- | --- |
| API-003 | `POST /api/allotment-actions/{id}/allocate-items/` | Commit an actual or plan-basis allotment debit | Partial | P1 |
| API-097 | `POST /api/license-ledger/download-package/` | Create a durable ledger-package job | Partial | P1 |
| API-102 | `POST …/purchase-trades/{trade_id}/recover-orphan/` | Recover a reviewed purchase document | Partial | P1 |
| API-103 | `POST …/purchase-trades/{trade_id}/upload/` | Upload a purchase document for a job-linked trade | Partial | P1 |
| API-106 | `POST …/download-package/{job_id}/retry/` | Requeue failed package items | Partial | P1 |
| API-108 | `POST /api/license-ledger/download-requests/` | Create newer persistent download request | Partial | P1 |
| API-112 | `GET …/download-requests/{request_id}/licenses/{item_id}/download/` | Owner-scoped, checksum-verified PDF retrieval | Partial | P2 (security-sensitive) |
| API-282 | `POST /api/reconciliation/link/` | Link a BOE to a trade and stamp invoice data | Partial | P1 |
| API-283 | `POST /api/reconciliation/merge-boe/` | Merge duplicate BOE records | Partial | P1 |
| API-288 | `POST /api/reconciliation/note/` | Mark exactly one reconciliation target pending/ignored | Partial | P1 |
| API-290 | `POST /api/reconciliation/recalculate/` | Queue all-license balance recalculation | Partial | P1 |

## Evidence register

### API-003 — allocation commit

- **Verified by code — request/response:** the internal boundary documents
  `allocations[]` entries with `item_id`, `qty`, `cif_fc`, `cif_inr`, and
  optional legacy `plan_line_id`; actual request handling additionally reads
  `search_mode`/`debit_based_on`, `allocation_basis`, `actual_item_id`, and
  `planning_target_item_id` ([views_actions.py:1051](../../../backend/apps/allotment/views_actions.py#L1051),
  [views_actions.py:1072](../../../backend/apps/allotment/views_actions.py#L1072)). Success returns
  `success`, `created_items`, `errors`, and refreshed `allotment`, with `201`
  when at least one row was created; invalid input/zero success returns `400`.
  The OpenAPI declaration contains no request DTO, so this source contract is
  the current evidence, not a stabilized public schema.
- **Verified by code — effect and integrity:** `@transaction.atomic` locks the
  parent allotment and each import item (`select_for_update`), calculates
  committed quantity/CIF and validates non-empty allocations, remaining
  requirement, debit-basis consistency and target identity before creation.
  It then marks each touched licence for replan and invokes the task inline
  before responding ([views_actions.py:1072](../../../backend/apps/allotment/views_actions.py#L1072)).
  The outer public boundary logs an unexpected exception and returns a safe
  `500`, preventing an internal DB error from being returned directly
  ([views_actions.py:1051](../../../backend/apps/allotment/views_actions.py#L1051)).
- **Verified by code — authorization:** class permission is
  `AllotmentPermission`; writes require `ALLOTMENT_MANAGER`, while no object
  or company filtering is implemented in that permission
  ([permissions.py:38](../../../backend/apps/accounts/permissions.py#L38)).
  Whether role authorization must also constrain company/object access is D1,
  **requires owner approval**.
- **Verified by test:** plan residual/cap, stale cache and safe-500 cases are
  exercised in
  [test_allocate_items_plan_line_balance.py:1](../../../backend/apps/allotment/tests/test_allocate_items_plan_line_balance.py#L1)
  and the adjacent allocation suites listed in the route-family register.
- **Missing closure:** executable manager/viewer/anonymous and cross-company
  denial expectations; a versioned request/response fixture; validation of
  partial multi-row errors and task failure rollback/recovery; a UI consumer
  action/error-state contract.

### Ledger package jobs — APIs 097, 102, 103, 106, 108 and 112

All six endpoints use `LicenseLedgerViewPermission`, which is role-based for
`TRADE_VIEWER`, `TRADE_MANAGER`, `LICENSE_MANAGER`, or `LEDGER_MANAGER`; it is
explicitly independent of a user-company assignment
([permissions.py:126](../../../backend/apps/accounts/permissions.py#L126)). Job
retrieval is then owner-filtered (`requested_by=request.user`) for the durable
request and older package surfaces ([ledger.py:143](../../../backend/apps/license/views/ledger.py#L143),
[ledger.py:370](../../../backend/apps/license/views/ledger.py#L370)). That is
verified owner isolation, not a proven company-isolation policy; D1 remains
unresolved.

| API | Verified request / response and data effect | Transaction, recovery and existing evidence | Remaining closure |
| --- | --- | --- | --- |
| 097 | `license_ids` must be a de-duplicated non-empty list, max configured limit, and each resolved record must be DFIA. Optional idempotency key and `client_job_key` are accepted. A job plus one item per resolved licence is created and `202` returns a job payload ([ledger.py:186](../../../backend/apps/license/views/ledger.py#L186)). | Creation is atomic and task dispatch is `on_commit`; same-owner nonfailed idempotency key returns its existing job. Test proves duplicate IDs create one item and same key yields one job ([test_license_ledger_package_jobs.py:17](../../../backend/apps/license/tests/test_license_ledger_package_jobs.py#L17), [test_license_ledger_package_jobs.py:41](../../../backend/apps/license/tests/test_license_ledger_package_jobs.py#L41)). | Direct role matrix; unknown/non-DFIA ID fixture; worker-dispatch outage semantics; client payload compatibility; D1 scope. |
| 102 | Body must include existing storage `source_storage_key` and dictionary `evidence`; target is a PURCHASE trade linked to a licence item of the owner’s job. It reads storage and calls `link_unique_orphan`, then returns `{trade_id,status:'recovered'}` ([ledger.py:343](../../../backend/apps/license/views/ledger.py#L343)). | Invalid key/evidence or absent file becomes validation error; a service `ValueError` is mapped to validation error. | No direct HTTP test found for ownership, falsified evidence, competing recovery or storage read failure; no declared OpenAPI DTO. |
| 103 | Multipart `file` is mandatory; target is likewise a PURCHASE trade linked to a licence item of the owner’s job. Bytes and original name pass to `upload_purchase_document`; success returns `{trade_id,status:'uploaded'}` ([ledger.py:323](../../../backend/apps/license/views/ledger.py#L323)). | Missing file and service validation failures become validation errors; unrelated job/trade is `404`. | File size/type/malware policy, atomic storage/DB failure and retry test are absent from this bounded evidence. |
| 106 | No body required. Owner job only; all `failed` items become `queued`, error/timestamps reset, job changes to queued and worker dispatch happens `on_commit`; returns `202` job payload ([ledger.py:263](../../../backend/apps/license/views/ledger.py#L263)). | A no-failed-item retry is a `202` no-op. | Concurrency/idempotency and dispatch-failure test; user feedback for no-op/partial retry. |
| 108 | Newer durable request accepts de-duplicated `license_ids` and optional header/body idempotency key; it creates request, items and an audit event, returning `202` ([ledger.py:41](../../../backend/apps/license/views/ledger.py#L41)). | Atomic creation uses row locking for an existing owner/key; dispatch is on-commit and dispatcher failure changes job state to `dispatch_failed` ([ledger.py:150](../../../backend/apps/license/views/ledger.py#L150)). Frontend consumer sends the same idempotency value in body and header ([licenseDownloadRequests.ts:9](../../../frontend/src/services/licenseDownloadRequests.ts#L9)). | Direct DTO/test fixture for this newer surface, duplicate-key race and dispatcher-failure response/polling coverage. |
| 112 | Owner-scoped request and server-ready item are required. Storage object is read, and both size and SHA-256 must match recorded metadata before an attachment response; all failed ownership/state/integrity checks are `404` ([ledger.py:93](../../../backend/apps/license/views/ledger.py#L93)). | The caller can obtain this URL only via the owner payload; frontend deliberately fetches through authenticated Axios rather than a bare link ([licenseDownloadRequests.ts:14](../../../frontend/src/services/licenseDownloadRequests.ts#L14)). | Direct HTTP test for cross-owner, absent/tampered storage, expired job and content-disposition; no conclusion about URL token policy beyond D4. |

The older package surface has an owner-scope regression test:
[test_license_ledger_package_jobs.py:29](../../../backend/apps/license/tests/test_license_ledger_package_jobs.py#L29).
It is useful evidence for the shared ownership pattern but does **not** prove
the newer `download-requests` surface, so each remains Partial.

### Reconciliation writes — APIs 282, 283, 288 and 290

- **Verified by code — authorization:** all use `ReconciliationPermission`.
  A write requires both `TRADE_MANAGER` and `BOE_MANAGER` (or superuser),
  whereas safe reads accept either data-domain role
  ([permissions.py:72](../../../backend/apps/accounts/permissions.py#L72)). The
  view uses raw PK lookup with no company predicate; whether cross-company
  access is permitted is D1, **requires owner approval**.
- **API-282 / link:** requires `trade_id` and `boe_id` (else `400`), appends
  rather than replaces the M2M, stamps invoice fields through the shared
  helper, and creates a before/after `ReconciliationLog` in one atomic block;
  it returns IDs and linked IDs ([views.py:145](../../../backend/apps/reconciliation/views.py#L145)).
  Tests prove link/log and preservation of a genuinely hidden BOE's balance
  semantics ([test_reconciliation.py:358](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L358),
  [test_reconciliation.py:383](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L383)).
- **API-283 / merge BOE:** requires target/source IDs (else `400`), calls the
  dedicated merge service inside an atomic block, and logs only after service
  success ([views.py:180](../../../backend/apps/reconciliation/views.py#L180)).
  The service moves nonduplicate rows/allotments, deletes the source and
  restamps port atomically, but rejects protected duplicate rows before any
  mutation ([boe_service.py:203](../../../backend/apps/bill_of_entry/services/boe_service.py#L203)).
  Tests cover service delegation/log, atomic protected-duplicate rejection
  and external-invoice protection
  ([test_reconciliation.py:465](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L465),
  [test_reconciliation.py:493](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L493),
  [test_reconciliation.py:573](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L573)).
- **API-288 / note:** `status` must be `IGNORED`/`PENDING`, precisely one of
  `trade_id`, `bill_of_entry_id`, `license_item_id` must be supplied; it
  upserts `ReconciliationNote`, calls `full_clean`, and logs it atomically,
  responding with ID/status/reason ([views.py:213](../../../backend/apps/reconciliation/views.py#L213)).
  Creation and multi-target rejection are tested
  ([test_reconciliation.py:431](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L431),
  [test_reconciliation.py:451](../../../backend/apps/reconciliation/tests/test_reconciliation.py#L451)).
- **API-290 / recalculate:** request `license_ids`, if supplied, is explicitly
  ignored; it always queues `update_all_license_balances('all')`, logs task ID
  in the same atomic block, and returns `202 PENDING` with the task ID
  ([views.py:274](../../../backend/apps/reconciliation/views.py#L274)). This is a
  verified consequential behaviour and a P1 contract-quality risk: callers
  can send scope-looking input that has no effect.

**Shared missing closure:** no bounded evidence of action-level negative-role
HTTP tests, object/company scope tests, request/response fixtures, queue
failure behaviour for API-290, or frontend error/recovery state mapping. The
existing `test_reconciliation.py` evidence is feature-level and does not close
these gaps.

## Recommended implementation dependency / acceptance gates

1. Obtain D1 before adding company predicates or declaring their absence a
   defect. Add role, owner and company/object tests for every listed mutation.
2. Publish explicit OpenAPI DTOs for the source-only bodies, then freeze
   success and validation fixtures (especially API-003, 102, 103, 282–290).
3. Preserve atomic boundaries and add concurrency/retry simulations: racing
   allotment cap, package/recovery job ownership, protected BOE merge, and
   balance-task dispatch failure.
4. Make API-290 scope honest: either reject `license_ids` until implemented
   or obtain approval and add scoped task semantics plus audit fields. This is
   a proposed V1 correction, not a policy change made by this audit.
5. Exercise the frontend consumers with loading, empty, success, error and
   permission-denied states before promoting a row from Partial.
