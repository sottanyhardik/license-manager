# Q2 trade and reconciliation operation packets

**Bounded individual-operation audit: 42 API IDs.** This document supplies
one row per selected trade, payment and reconciliation operation. It records
direct current-code and named-test evidence only; all rows are **Partial**.
It does not approve object/company scope (D1), balance/report semantics (D2),
general-ledger scope (D5), or audit durability (D6).

Common evidence: `TradePermission` requires `TRADE_MANAGER` for unsafe
methods and permits `TRADE_MANAGER`/`TRADE_VIEWER` reads
([permissions.py:66](../../../backend/apps/accounts/permissions.py#L66)).
`ReconciliationPermission` admits either domain read role for safe methods
and requires both `TRADE_MANAGER` and `BOE_MANAGER` for writes
([permissions.py:72](../../../backend/apps/accounts/permissions.py#L72)).
Neither class supplies object/company filtering; D1 remains required. The
OpenAPI request/response declarations below are the current schema evidence;
source-owned fields/actions may be more specific.

## Payments — API-270–276

`LicenseTradePaymentViewSet` is a factory-generated `MasterViewSet` with
`TradePermission`, `LicenseTradePaymentSerializer`, filtering by trade/date,
search by note and ordering by date/id (`trade/views.py:656+`). The generic
write path records creator/modifier and may use the MDS write gate; local
delete exposes model `ProtectedError` as validation error
([master_view.py:81](../../../backend/apps/core/views/master_view.py#L81)).
No payment-specific direct HTTP test was identified in this bounded review.

| API ID / method-path | Current request/response/effect evidence | Consumer/tests/error-recovery closure | Status |
| --- | --- | --- | --- |
| API-270 `GET /payments/` | No body; factory list/query/filter/pagination of payment serializer, schema `200`. | Frontend trade form/list consumer needs exact reconciliation; test list/filter/pagination and read role/D1 scope. | P2 Partial |
| API-271 `POST /payments/` | Schema accepts `LicenseTradePayment`; generic create returns `201`, stamps actor and may write through MDS. | Validate payment fields/trade ownership, MDS/local rollback and manager/viewer/anonymous responses. | P1 Partial |
| API-272 `GET /payments/{id}/` | Generic retrieve/payment serializer, schema `200`. | Test nonexistent/foreign object and D1-approved company behavior. | P2 Partial |
| API-273 `PUT /payments/{id}/` | Full serializer update, schema `200`; generic update stamps modifier/MDS path. | Freeze required-field semantics, financial-balance effect and stale/edit failure fixture. | P1 Partial |
| API-274 `PATCH /payments/{id}/` | Patched serializer update, schema `200`; same generic write path. | Test partial validation, permission/object denial and report/ledger recomputation or explicit no-effect. | P1 Partial |
| API-275 `DELETE /payments/{id}/` | Generic destroy, schema `204`; local referenced record may become validation error; MDS delete is authority-first. | Test accounting-history policy (D5), protected/foreign delete, MDS outage and audit/recovery. | P1 Partial |
| API-276 `GET /payments/export/` | Generic export action, schema `200`; filters/queryset authorization originate in factory. | Identify UI consumer/content type/filter provenance and denied/download failure behavior. | P2 Partial |

## Reconciliation reads and writes — API-278–291

All actions are `ReconciliationViewSet` methods
([views.py:64](../../../backend/apps/reconciliation/views.py#L64)). Detection
actions are read-only query delegates and use 50-row default/500-row maximum
pagination; writes are `transaction.atomic()` and create `ReconciliationLog`
in the same transaction ([views.py:1](../../../backend/apps/reconciliation/views.py#L1)).
`test_reconciliation.py` covers selected detection, summary, link, note and
merge scenarios; it does not close direct role/object/recovery packets.

| API ID / method-path | Current request/response/effect evidence | Consumer/tests/error-recovery closure | Status |
| --- | --- | --- | --- |
| API-278 `GET /reconciliation/audit-log/` | Optional `scope=today`; selects related audit rows, paginates and serializes before/after/user fields ([views.py:119](../../../backend/apps/reconciliation/views.py#L119)). | Test audit-log visibility/redaction, pagination/error and D6 retention; UI reconciliation consumer requires L/E/S/D evidence. | P2 Partial |
| API-279 `GET /reconciliation/cif-comparison/` | Delegates to `queries.cif_comparison()` and paginates ([views.py:100](../../../backend/apps/reconciliation/views.py#L100)). | Query test has tolerance scenarios; bind returned engine/precision to D2 and test filters/empty/role denial. | P2 Partial |
| API-280 `GET /reconciliation/duplicate-boes/` | Delegates to `queries.duplicate_boes()` with standard pagination. | `test_reconciliation.py` near-duplicate cases; require error/query-scale/object-scope and UI recovery evidence. | P2 Partial |
| API-281 `GET /reconciliation/duplicate-debits/` | Delegates to `queries.duplicate_debits()` with standard pagination. | Existing double-debit fixture is narrow; add denied/filter/empty and result-provenance tests. | P2 Partial |
| API-282 `POST /reconciliation/link/` | Requires `trade_id`,`boe_id`; atomically adds (does not replace) relation, stamps invoice and logs; `400` missing input, `200` IDs ([views.py:145](../../../backend/apps/reconciliation/views.py#L145)). | Link/log and hidden-BOE tests exist. Add anonymous/partial-role/D1, duplicate/race, stamp failure and UI recovery. | P1 Partial |
| API-283 `POST /reconciliation/merge-boe/` | Requires target/source IDs; atomically delegates merge/log; `ValueError` becomes `400`, schema `200` ([views.py:180](../../../backend/apps/reconciliation/views.py#L180)). | Protected-duplicate/external-link tests exist. Add wrong role/D1, concurrent merge, file rollback and operator diagnostics. | P1 Partial |
| API-284 `GET /reconciliation/missing-boe/` | Delegates to `queries.missing_boe()` and paginates. | Selected detection test exists; require read-role/D1, empty/error and query-budget/UI-state evidence. | P2 Partial |
| API-285 `GET /reconciliation/missing-invoice/` | Delegates to `queries.missing_invoice()` and paginates. | Selected detection test exists; require read-role/D1, empty/error and query-budget/UI-state evidence. | P2 Partial |
| API-286 `GET /reconciliation/multi-boe/` | Delegates to `queries.multi_boe_per_invoice()` and paginates. | Fixture test exists; require pagination/provenance, denial and UI recovery evidence. | P2 Partial |
| API-287 `GET /reconciliation/multi-invoice/` | Delegates to `queries.multi_invoice_per_boe()` and paginates. | Fixture test exists; require pagination/provenance, denial and UI recovery evidence. | P2 Partial |
| API-288 `POST /reconciliation/note/` | Requires `IGNORED`/`PENDING` and exactly one target; atomic upsert/full_clean/log; `400` invalid/multi-target, `200` note ([views.py:213](../../../backend/apps/reconciliation/views.py#L213)). | Note/multi-target tests exist. Add direct role/D1, competing note, log durability (D6) and UI retry. | P1 Partial |
| API-289 `GET /reconciliation/qty-comparison/` | Delegates to `queries.qty_comparison()` and paginates. | Tolerance/result-source, denial, filter/empty and page failure contract remain unlinked. | P2 Partial |
| API-290 `POST /reconciliation/recalculate/` | Queues all-license balance task and log atomically, returns `202` task status; supplied `license_ids` are currently ignored ([views.py:274](../../../backend/apps/reconciliation/views.py#L274)). | Add dual-role/D1, broker failure/idempotency/polling and either reject or implement scope-looking body; D2 labels required. | P1 Partial |
| API-291 `GET /reconciliation/summary/` | Returns `queries.summary()` without pagination ([views.py:81](../../../backend/apps/reconciliation/views.py#L81)). | `SummaryQueryTests` covers expected keys; add role/D1, empty/error, aggregate provenance and UI partial-failure tests. | P2 Partial |

## Trades — API-333–353

`EnhancedLicenseTradeViewSet` applies relation-aware `select_related`/
`prefetch_related` and forces list ordering by descending invoice date
([views.py:360](../../../backend/apps/trade/views.py#L360)). Standard CRUD
inherits the generated base view/serializer; custom endpoints are listed
below. Existing evidence includes `backend/tests/test_api_trade.py`,
`apps/trade/tests/test_trade_service.py`, paired-trade and document suites.
It remains insufficient for individual authorization/object/recovery closure.

| API ID / method-path | Current request/response/effect evidence | Consumer/tests/error-recovery closure | Status |
| --- | --- | --- | --- |
| API-333 `GET /trades/` | Filtered/prefetched list; forced invoice-date order; schema `200`. | `TestTradeAPI` covers list/filter/order. Add pagination/empty/D1 and frontend route UI-030 state/denial evidence. | P2 Partial |
| API-334 `POST /trades/` | `LicenseTrade` multipart/form/json schema, `201`; override only debug-logs request shape then inherited serializer create ([views.py:385](../../../backend/apps/trade/views.py#L385)). | Create test exists. Freeze nested lines/payments/docs validation, atomicity, wrong role/D1 and financial effect. | P1 Partial |
| API-335 `GET /trades/{id}/` | Prefetched serializer retrieve, `200`. | Retrieve test exists; test missing/foreign/D1, document availability and UI edit-load recovery. | P2 Partial |
| API-336 `PUT /trades/{id}/` | Full `LicenseTrade` serializer update, `200`; inherited update. | Add stale/nested correction/financial-balance/reversal and role/D1 fixtures. | P1 Partial |
| API-337 `PATCH /trades/{id}/` | Patched serializer update, `200`; inherited partial update. | Add partial nested/document/line validation, concurrent correction and UI error recovery. | P1 Partial |
| API-338 `DELETE /trades/{id}/` | Inherited destroy, `204`. | Pair/line/payment deletion behavior needs D5-approved lifecycle contract, direct denial and rollback/audit tests. | P1 Partial |
| API-339 `POST /trades/{id}/copy-to-purchase/` | Calls `copy_sale_to_purchase`; `404` missing sale, `400` invalid; returns counterpart payload `201` when created else `200` ([views.py:591](../../../backend/apps/trade/views.py#L591)). | Service idempotency/reciprocity tests exist. Add HTTP role/D1, duplicate race and UI success/error contract. | P1 Partial |
| API-340 `POST /trades/{id}/copy-to-sale/` | Symmetric purchase-to-sale call/status semantics ([views.py:601](../../../backend/apps/trade/views.py#L601)). | Service existing-pair test exists. Add HTTP role/D1, concurrent duplicate and financial/report parity. | P1 Partial |
| API-341 `GET /trades/{id}/counterpart/` | Returns counterpart payload or `404` when absent ([views.py:611](../../../backend/apps/trade/views.py#L611)). | Add paired-object D1, schema and UI missing-counterpart/error tests. | P2 Partial |
| API-342 `GET /trades/{id}/generate-bill-of-supply/` | SALE-only; optional `include_signature`; returns inline PDF or `400`/safe `500` ([views.py:403](../../../backend/apps/trade/views.py#L403)). | API PDF test exists. Add file content/disposition, D1, generator failure and blob UI recovery. | P2 Partial |
| API-343 `GET /trades/{id}/generate-purchase-invoice/` | PURCHASE-only; optional signature; returns inline PDF or `400`/safe `500` ([views.py:445](../../../backend/apps/trade/views.py#L445)). | Add purchase fixture/content/D1/generator-failure and browser download recovery tests. | P2 Partial |
| API-344 `POST /trades/{id}/generate-transfer-letter/` | Passes documented template/override/items/CIF payload to shared transfer-letter generator ([views.py:618](../../../backend/apps/trade/views.py#L618)); action uses transfer-letter permission override. | Freeze body/attachment/error DTO, wrong TL role/D1 and generated-file authorization/retry. | P1 Partial |
| API-345 `POST /trades/{id}/link-trade/` | `partner_id` sets/clears reciprocal link; maps `ValueError` to `400`, missing partner `404` ([views.py:555](../../../backend/apps/trade/views.py#L555)). | Link/unlink/self/missing service tests exist. Add HTTP D1/race/relink UI recovery and audit policy. | P1 Partial |
| API-346 `POST /trades/{id}/resolve-final-party/` | SALE-only; requires resolution note; validates canonical buyer, cleans/saves classification fields; `400` invalid ([views.py:306](../../../backend/apps/trade/views.py#L306)). | Add decision provenance/D5, role/D1, stale classification and audit/reversal fixtures. | P1 Partial |
| API-347 `POST /trades/{id}/sales-classification-review/` | Calls `apply_decision`; maps absent sale `404` and validation `400`, returns status/affected licences ([views.py:294](../../../backend/apps/trade/views.py#L294)). | Add input decision/provenance fixtures, D5/D1 role/object, replan/effect/retry and UI state tests. | P1 Partial |
| API-348 `GET /trades/{id}/summary/` | Calls `build_trade_summary`, returns computed payload ([views.py:549](../../../backend/apps/trade/views.py#L549)). | Summary service tests assert keys/values/string numerics. Add engine/provenance/D2-D5, D1 and empty/error UI tests. | P2 Partial |
| API-349 `GET /trades/export/` | Generated export action on prefetched/queryset view; schema `200`. | Trace actual content/filter/ACL/download errors and source field provenance. | P2 Partial |
| API-350 `GET /trades/prefill-invoice-number/` | Requires direction/company, optional strict ISO date; generates number or `400`/`404` ([views.py:487](../../../backend/apps/trade/views.py#L487)). | Service invalid/missing/sequence tests exist. Add HTTP role/D1, concurrent sequence and form recovery. | P2 Partial |
| API-351 `GET /trades/sales-classification-review/` | Returns explicit `review_rows()` results; unknowns are not inferred ([views.py:277](../../../backend/apps/trade/views.py#L277)). | Add schema/pagination/role/D1, large-result and UI empty/error evidence. | P2 Partial |
| API-352 `GET /trades/sales-classification-review/export/` | Streams CSV with fixed columns/content disposition from `review_rows()` ([views.py:283](../../../backend/apps/trade/views.py#L283)). | Test CSV data/ACL/filter/provenance/download failure; D5 governs commercial classification use. | P2 Partial |
| API-353 `POST /trades/sales-classification-review/import/` | Requires uploaded CSV; `import_rows` returns applied count; `ValueError`/decode error map `400` ([views.py:294](../../../backend/apps/trade/views.py#L294)). | Add CSV schema/idempotency/partial-write/role-D1/malicious-file/UX recovery tests. | P1 Partial |

## Completion guard

This audit increases individual source-level evidence for 42 API IDs only. It
does **not** increase the completed-operation numerator: every row still lacks
at least direct cross-role/object scope, concrete DTO fixture, consumer state,
or recovery proof required by the [contract-closure protocol](contract-closure-protocol.md).
