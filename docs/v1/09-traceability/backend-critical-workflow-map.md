# Backend critical-workflow traceability map

This is the backend companion to the generated 8,046-symbol register. It
does **not** claim that every static symbol has a runtime caller or a test. It
instead maps the twelve consequential workflow boundaries that can change
licence entitlement, financial presentation, documents, or replicated master
data. Source citations below identify the inspected boundary; an import or a
test filename is not treated as proof that every action in its viewset uses
that dependency.

## Coverage and status

| Population | Count | What this map proves | What it does not prove |
| --- | ---: | --- | --- |
| Critical backend workflow boundaries selected from registered routes, task registration, and models | 12 | Entry point, principal data owners, authorization class, key state/error/concurrency evidence, and available regression-test evidence for each boundary | Per-operation request/response contract or every branch/error result |
| Generated API operation register | 354 | Runtime callback ownership for every OpenAPI operation | Action-level service/data/test mapping; see `api-action-workflow-map.md` when completed |
| Static backend-symbol register | 8,046 | Stable symbol/file/line denominator | Call graph, side effects, auth, tests or live reachability of every symbol |
| Critical boundaries with direct transaction/concurrency evidence below | 7/12 | Specific `atomic`, row-lock, durable-job or idempotency mechanism | End-to-end race simulation for every endpoint |
| Critical boundaries with named source tests below | 12/12 | Relevant existing tests were located and the app-level suite passed | Test-to-operation completeness or production-policy approval |

**Audit status convention:** `Verified boundary` means the cited source and/or
test establishes the stated detail. `Partial` means the workflow exists but
has unresolved policy, operation, consumer, or recovery coverage. Every row
remains `Partial` until its linked API-operation and acceptance mappings are
complete.

## Cross-cutting authorization and source-of-truth evidence

**Verified by code:** `BaseRolePermission` in
`backend/apps/accounts/permissions.py:4` applies authentication plus role
sets, with superuser bypass. `LicensePermission`, `AllotmentPermission`,
`BillOfEntryPermission`, and `TradePermission` gate their respective CRUD
families (lines 31–69). `ReconciliationPermission` requires either trade or
BOE read role, but *both* TRADE_MANAGER and BOE_MANAGER for writes (lines
72–100). This is role authorization, not demonstrated object/company
isolation. `LicenseLedgerViewPermission` explicitly says ledger access is not
company-assignment dependent (line 132); that policy needs owner decision D1.

**Verified by code:** `LicenseBalanceLedgerPermission` denies unmapped writes
by default and has different role combinations for recalculation, warning
bookkeeping, BOE visibility, invoice/BOE allocation and BOE/allotment
allocation (`permissions.py:240+`). Thus a frontend role guard cannot be the
authorization evidence for a financially consequential action.

**Requires owner approval:** company/entity isolation, accounting scope, and
the canonical presentation of Customs versus Financial balance are recorded
as D1, D5 and D2 in
`../../00-executive-overview/decisions-required.md`. No code change is
recommended until those policies are approved.

## Workflow boundary register

| ID | Entry point(s) and principal models/services | Verified state, transaction and failure evidence | Authorization / tests | V1 disposition and open traceability work |
| --- | --- | --- | --- | --- |
| BW-01 Authentication and role authorization | REST framework default authentication plus `accounts/permissions.py`; query-token compatibility is `apps/core/authentication.py:27` | Role checks distinguish safe/read vs write methods; unknown balance-ledger write actions deny by default. Query JWT is only intended for GET/HEAD download-like paths (see `backend/tests/test_authentication_query_param.py`). | Role classes above; auth/permission tests include `backend/tests/test_authorization_permissions.py` and query-token tests. | **P0 / Partial.** Produce endpoint-by-endpoint denial matrix and decide D4 (token/download posture); do not infer company scoping from roles. |
| BW-02 Licence master, item nesting and metadata CRUD | `LicenseDetailsViewSet` (`apps/license/views/license.py:213`), generated `MasterViewSet`, `LicenseDetailsModel`, `LicenseDetailsSerializer` | Default filters hide expired/null flags as configured; list serializer context batches live balances to avoid N+1. `individual-item-cif-override` locks the licence in `transaction.atomic`, accepts one typed field, and only then marks a durable replan source change (`license.py:250+`). | `LicensePermission`, except explicit balance-ledger/read-only actions. Relevant API tests: `backend/tests/test_api_license.py`, app tests under `apps/license/tests`. | **P1 / Partial.** Map generated CRUD methods, nested serializer mutations, document uploads and dynamic metadata to the 81 licence-family operations. Characterize concurrent master edits and file rollback. |
| BW-03 Customs and financial balance presentation | `LicenseBalanceCalculator` (`apps/license/services/balance_calculator.py:80`), overview/ledger builders and `LicenseDetailsModel` balance properties | The legacy calculation at `:1330+` is export credit − non-hidden BOE debit − outstanding allotment, quantized to 2dp and floored at zero. Source comments explicitly say it is not the financial business figure and direct callers to `calculate_financial_balance`; hidden BOE treatment differs by ledger. | `LicenseBalanceLedgerPermission` for workspace actions. Tests: `apps/license/tests/test_balance_calculator.py`, `test_balance_cif_single_source.py`, `test_financial_balance_memo.py`, `test_balance_ledger_views.py`, `test_ledger_reconciliation_smoking_gun.py`. | **P0 / Partial.** Preserve both engines pending D2; record every screen/report field’s engine, timing and hidden/reversal treatment. Never consolidate on naming alone. |
| BW-04 Allotment candidate, allocation, release and replan | `AllotmentActionViewSet` (`apps/allotment/views_actions.py:51`, `allocate-items` at `:1051`); `AllotmentModel`, `AllotmentItems`; allocation/availability and plan services | `_allocate_items_atomic` row-locks the allotment before summing commitments and validates non-empty batches, dual basis and remaining caps (`views_actions.py:1072+`). Service deallocation is atomic and rejects BOE-converted allocation (`services/allocation_service.py:206+`). Boundary catches unexpected exceptions and returns safe 500. | `AllotmentPermission`, with transfer-letter exception. Tests: `test_allocate_items_cif_validation.py`, `test_allocate_items_plan_line_balance.py`, `test_allocate_items_*plan_cap.py`, `test_module3_allocation_scenarios.py`. | **P0 / Partial.** Preserve locked live-balance validation, plan-line isolation and on-commit replan. Map every allocate/deallocate/correction action to exact status codes; load-test competing allocations and recovery after job dispatch loss. |
| BW-05 BOE/import evidence and visibility | `BillOfEntryViewSet` (`apps/bill_of_entry/views/boe.py:110`), `BillOfEntryModel`, `BillOfEntrySerializer`, `boe_service` | View selects/prefetches related rows by action and applies invoice/hidden filters. `available_for_trade` uses `annotate_and_exclude_hidden`; special actions call transfer-letter or invoice update paths. BOE hide/restore affects balance and reconciliation log according to tests. | `BillOfEntryPermission`; `generate_transfer_letter` uses `TransferLetterPermission`; `update_invoice_no` uses `AccountAccessPermission`. Tests: `apps/bill_of_entry/tests/test_boe_hide_service.py`, parser/API tests, `apps/core/tests/test_protected_media_view.py`. | **P0 / Partial.** Define correction/hide/restore source of truth, row lifecycle and file-parser retry contract; map serializer nested writes and all export/download permissions. |
| BW-06 Trade, invoices, payments and document evidence | Generated `LicenseTradeViewSet` (`apps/trade/views.py:14+`), `LicenseTrade`, `LicenseTradeLine`, `LicenseTradePayment`, `LicenseTradeSerializer`, `trade_service` | Config exposes direction/license type, counterparties, BOE attachment, nested lines and payments. Direct imports show document PDFs and sale-classification review; the transaction behavior of generated serializer CRUD requires action-level review. | `TradePermission`. Tests: `apps/trade/tests/test_trade_service.py`, balance/ledger trade tests listed in BW-03. | **P1 / Partial.** Separate evidenced trade/invoice/payment capability from unproven GL/bank reconciliation. Map line changes to financial balance, invoice document access, compensation/reversal and validation errors. |
| BW-07 BOE/invoice and BOE/allotment reconciliation | `ReconciliationViewSet` (`apps/reconciliation/views.py:54`); `InvoiceBOEAllocation`, `BOEAllotmentAllocation`, `ReconciliationLog`, allocation services | View docstring states every write is atomic and writes its audit row in the same transaction (`views.py:1–18`). `create_invoice_boe_allocation` locks trade line and BOE row, validates same licence/nonnegative/remaining/duplicate, creates allocation and log atomically (`services/allocation_service.py:224+`). Edits supersede rather than overwrite and reversal never deletes (`:311+`, `:387+`). | `ReconciliationPermission` (dual manager role for writes). Tests: `apps/reconciliation/tests/test_allocation_service.py`, `test_boe_link_reconciler.py`, `test_reconciliation.py`, `test_external_invoice_service.py`. | **P0 / Partial.** Characterize all link/merge/note/recalculate error paths and operator recovery. Preserve immutable/superseding allocation history; require race and cross-company policy tests before redesign. |
| BW-08 Ledger workspace, exports and durable package generation | `LicenseLedgerViewSet` (`apps/license/views/ledger.py:23`), `LicenseLedgerPackageJob/Item`, `LicenseLedgerPackageService`, Celery tasks | Package request normalizes IDs, validates authorized licences, locks idempotency key/job creation in a transaction and dispatches on commit (`ledger.py:33+`). Request lookup restricts package retrieval to `requested_by`; retry only requeues items whose readiness became READY. Worker tasks use late acknowledgement/reject-on-worker-lost and staged file promotion (`apps/license/tasks.py:1+`). | `LicenseLedgerViewPermission`; per-request owner lookup. Tests: `test_license_ledger_package.py`, `test_license_ledger_package_jobs.py`, `test_ledger_package_recovery.py`. | **P1 / Partial.** Test all storage/Celery failure/retry transitions and protected-download token migration. Confirm intentional role-wide ledger visibility against D1. |
| BW-09 Replan and materialized-balance work | `LicenseReplanRequest`, `apps/license/tasks.py`, balance/materialized-view helpers | `dispatch_replan_requests` locks each request, only progresses pending/retry states, and queues serializable IDs; worker configuration uses late ack/reject on worker lost. Materialized-view refresh functions exist but are a separate representation from live balance. | Licence/action permissions; tests in allocation plan-line suite assert one durable replan after committed changes. | **P1 / Partial.** Build state-transition table for pending/queued/running/retry/failed and reconcile cache/materialized/live output. Do not let stale projection authorize a debit. |
| BW-10 Master-data peer synchronization | `/api/sync/` endpoints in `apps/core/sync/urls.py`; `PeerSyncAPIView`, `SyncEvent`, `SyncInboxEvent`, `SyncCursor`, registry/service | Peer token auth authenticates private calls. Push rejects source-server mismatch; batch application topologically orders entries. Inbox `get_or_create` plus domain write/output event live in one atomic block, forming an idempotency boundary (`sync/service.py:537+`). Pull returns immutable outbox cursor, not wall time (`sync/views.py:136+`). | Peer-token rather than user-role auth. Tests: `apps/core/tests/test_sync_failures.py`, `test_sync_transport.py`, `test_three_server_runtime.py`, `test_master_sync.py`; isolated MDS suite now passed 25/25. | **P1 / Partial.** Unit environment gap is closed. Map peer provisioning/revocation, media checksum failures, partial batches and operational conflict resolution; establish restore/replay drill. |
| BW-11 Background media and file handling | Sync media helpers, BOE/licence parser/upload actions, ledger package storage promotion | Sync pushes create media tasks when registered media fields are present; package task stages then publishes output to avoid visible partial file (`license/tasks.py:25+`). File/upload validation and storage access are not fully traced here. | Protected media tests and view-specific roles; no approved retention policy. | **P1 / Partial.** Complete upload MIME/size/virus policy and external-storage lifecycle mapping before changing document infrastructure. |
| BW-12 Maintenance and reconciliation commands | `reconcile_masters`, `sync_database_schema`, reconciliation health/backfill commands | Commands expose potentially data-affecting repair/backfill surfaces, while `sync_database_schema` includes backup/fix paths. They are not ordinary API endpoints and cannot be omitted from change control. | Management-command access is an operator/deployment concern, not a DRF permission. Tests/production runbook linkage incomplete. | **P1 / Partial.** Inventory flags/dry-run behavior, input/output, required backups and rollout owner before a migration or scheduled job is approved. |

## Critical state and recovery requirements derived from evidence

1. **Balance outputs:** characterisation tests must name the engine, source
   rows, precision, visibility, allocation and reversal state. Existing tests
   are strong evidence of current behavior, not approval to simplify it.
2. **Allocation/reconciliation:** retain database locks and transactional
   audit logging; test exact-cap, duplicate, stale cache, concurrent submit,
   supersede and reverse cases against the public API.
3. **Jobs/files:** an accepted HTTP request is not completion. Tests must
   observe durable request/item state, idempotency key, on-commit enqueue,
   retry/recovery and safe download authorization.
4. **Sync:** preserve immutable cursor and inbox idempotency semantics;
   add an operational replay/conflict/peer-revocation exercise before calling
   the replication design production-ready.

## Explicit remaining links

This document advances the workflow-level denominator from unbounded prose to
12 named boundaries. It does not reduce the generated registers’ `Partial`
status. Completion requires: (a) each operation in
`api-operation-register.tsv` to reference a boundary or justified exclusion;
(b) each relevant test to be linked to an acceptance criterion; (c) confirmed
company/object policy; and (d) live schema, browser and MDS-environment
evidence. These conditions are tracked in `completion-audit.md`.
