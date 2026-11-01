# Q2 allotment and BOE individual operation packets

**Population:** 30 registered Q2 operation IDs: API-003–017 (15) and
API-035–049 (15). This is an individual-operation source/test packet, not a
family-level summary. Every row remains **Partial**: none has the complete
DTO fixture, direct anonymous/wrong-role/D1 object result, consumer state,
error/recovery and acceptance-test evidence required by the
[closure protocol](contract-closure-protocol.md).

**Evidence labels:** C = current code; T = named current test; R = current
OpenAPI registration; S = static frontend consumer; P = V1 acceptance work;
D = owner decision. `AllotmentPermission` is manager/viewer role-based and
`BillOfEntryPermission` is BOE manager/viewer/account/TL role-based;
neither proves company/object scope (D1). Read/write role distinctions cited
below are [permission source evidence](../../../backend/apps/accounts/permissions.py#L38).

## Allotment action operations

| API / method/path | Direct request/response and effect evidence | Transaction, authorization, consumer/test evidence | Missing closure / status |
| --- | --- | --- | --- |
| **API-003** `POST /allotment-actions/{id}/allocate-items/` | **C** body requires non-empty `allocations[]`, each accepting item/qty/CIF and optional plan identity; success returns `success`, `created_items`, `errors`, refreshed allotment and `201`, otherwise `400` ([views_actions.py:1051](../../../backend/apps/allotment/views_actions.py#L1051)). | **C** atomic worker locks allotment and source items, validates live actual/plan capacity and marks replan source ([views_actions.py:1072](../../../backend/apps/allotment/views_actions.py#L1072)). **S** `AllotmentAction.tsx:570`; **T** allocation cap, plan-line and live-CIF suites. | Direct role/D1 matrix, multi-row partial-error fixture, real dispatch-loss/race and UI 4xx/409 recovery. **P1 Partial; D1/D3.** |
| **API-004** `GET /allotment-actions/{id}/allocation-initialization/` | **C** returns backend-chosen actual/plan default, target, SION, plan status/reason/message; ambiguous plans fail closed to actual mode ([views_actions.py:169](../../../backend/apps/allotment/views_actions.py#L169)). | Read role uses `AllotmentPermission`. **S** `AllotmentAction.tsx:329`; **T** `TestAllocationInitialization` covers active/noncurrent/ambiguous/exhausted cases. | Missing/not-found and wrong-role HTTP fixtures, D1 scope, frontend unavailable/error state and D3 semantics approval. **P1 Partial; D1/D3.** |
| **API-005** `GET /allotment-actions/{id}/available-licenses/` | **C** queries actual or plan candidate grid with filters, paging, live quantity/CIF positions; invalid debit basis raises validation error ([views_actions.py:230](../../../backend/apps/allotment/views_actions.py#L230)). | Read role; response is advisory—not mutation authority. **S** `AllotmentAction.tsx:441`; **T** available-filter/plan-mode query and range tests. | Exact response/filter DTO, auth/D1 test, bad range/status fixtures, stale candidate vs allocate race and empty/error UI. **P1 Partial; D1/D3.** |
| **API-006** `DELETE /allotment-actions/{id}/delete-item/{item_id}/` | **C** deletes only parent-matching allocation, returns message/deleted quantity or `400` ([views_actions.py:1572](../../../backend/apps/allotment/views_actions.py#L1572)). | **C** atomic path locks source item, deletes allocation, refreshes balance and runs durable replan. **S** `AllotmentAction.tsx:651`; **T** plan-line delete/replan and allocation-scenario tests. | Wrong-role/D1, converted-to-BOE/rejection, competing delete/allocate, rollback and user confirmation/retry evidence. **P1 Partial; D1/D3.** |
| **API-007** `GET /allotment-actions/{id}/generate-pdf/` | **C** loads related data, returns inline `application/pdf` with generated filename; unexpected renderer/data failure returns `500` ([views_actions.py:1640](../../../backend/apps/allotment/views_actions.py#L1640)). | Read role. **S** `AllotmentsTable.tsx:91`, `MasterList.tsx:1466`; response is blob/file, not declared DTO. | Content/provenance fixture, denied/object result, renderer/storage failure, blob error feedback and D4 download posture. **P2 Partial; D1/D4.** |
| **API-008** `POST /allotment-actions/{id}/generate-transfer-letter/` | **C** accepts optional address/template/CIF edit input through shared transfer-letter generator ([views_actions.py:1666](../../../backend/apps/allotment/views_actions.py#L1666)). | **C** action overrides to `TransferLetterPermission`; **S** `TransferLetterForm.tsx:164`. | Explicit request/file schema, template/CIF validation, generated-doc provenance/error/cleanup, direct role/D1 and D4 policy tests. **P1 Partial; D1/D4.** |

## Allotment master operations

The seven standard CRUD/export actions use `AllotmentModelViewSet`, generated
by `MasterViewSet`; their common inherited query/filter/pagination/MDS/delete
behavior is bounded in [generic CRUD contracts](generic-crud-serializer-contracts.md).
The shared implementation cannot close an action-specific mutation contract.

| API / method/path | Current action packet | Auth, consumer/test evidence | Missing closure / status |
| --- | --- | --- | --- |
| **API-009** `GET /allotments/` | **R** `AllotmentSerializer`, `AllotmentModel`, `200`; inherited list supplies filtered/paginated metadata. | Read roles; **S** UI-022 `MasterList`; list/performance and API tests exist. | Filter/sort/page/empty DTO, D1 visibility, export/action affordance and browser state. **P2 Partial; D1.** |
| **API-010** `POST /allotments/` | **R** `Allotment` multipart/form/json schema, `201`; inherited serializer create may use MDS write-through. | Manager write role; **S** UI-023 `MasterForm`; domain/API tests located. | Valid/invalid/dependent-FK fixture, MDS outage/compensation, D1, duplicate/retry and no-allocation-before-action proof. **P1 Partial; D1.** |
| **API-011** `GET /allotments/{id}/` | **R** serializer/model `200`; inherited retrieve. | Read roles; **S** UI-024/025. | Not-found/D1 object result, nested/detail metadata contract and consumer loading/error evidence. **P2 Partial; D1.** |
| **API-012** `PUT /allotments/{id}/` | **R** full schema `200`; inherited update/serializer/MDS path. | Manager write; UI-024 form. | Complete-request fixture, immutable/live-cap fields, stale concurrent edit, MDS failure/rollback and D1 tests. **P1 Partial; D1/D3.** |
| **API-013** `PATCH /allotments/{id}/` | **R** patched schema `200`; inherited partial update. | Manager write; UI-024 inline/form consumers. | Field-level validation, optimistic UI rollback, dependent plan/cap effect and D1/error fixtures. **P1 Partial; D1/D3.** |
| **API-014** `DELETE /allotments/{id}/` | **R** `204`; inherited destroy maps protected relations/MDS deletion through common boundary. | Manager write; list delete consumer is conditional. | Referenced/allocation lifecycle policy, DB/MDS rollback, D1 and destructive confirmation/audit acceptance. **P1 Partial; D1/D6.** |
| **API-015** `POST /allotments/{id}/copy/` | **R** Allotment request schema, `200`; custom generated-view action needs action-level source reconciliation. | Manager write; UI list copy evidence is static only. | Copy field/child semantics, duplicate/error/D1 behavior, replan/MDS effects and user recovery. **P1 Partial; D1/D3.** |
| **API-016** `GET /allotments/download/` | **R** `200`; generated download action's concrete file/content contract is not declared. | Read role; consumer unresolved in this slice. | File type/filter parity, object/company policy, content failure and D4 protected-download tests. **P2 Partial; D1/D4.** |
| **API-017** `GET /allotments/export/` | **C** inherited export applies filtered queryset and selects XLSX/PDF via query parameter ([master_view.py:674](../../../backend/apps/core/views/master_view.py#L674)). | Read role; UI-022/export surface. | Applied-filter/golden content, invalid format/renderer failure, D1/D4 and blob feedback tests. **P2 Partial; D1/D4.** |

## BOE master and action operations

`BillOfEntryViewSet` supplies selected/prefetched querysets and custom invoice
filtering; generic CRUD uses the nested `BillOfEntrySerializer`. The direct
sources below distinguish that shared inherited path from BOE-specific actions
([boe.py:110](../../../backend/apps/bill_of_entry/views/boe.py#L110)).

| API / method/path | Direct request/response/effect evidence | Authorization, consumer/test evidence | Missing closure / status |
| --- | --- | --- | --- |
| **API-035** `GET /bill-of-entries/` | **C** list prefetches item/allotment data and defaults `is_invoice=false`, with an explicit `all` option ([boe.py:134](../../../backend/apps/bill_of_entry/views/boe.py#L134)). | BOE read roles; **S/Observed** UI-026 list; API/list tests exist. | Full query/filter/pagination schema, D1 result, empty/error/denied and data-provenance acceptance. **P2 Partial; D1.** |
| **API-036** `POST /bill-of-entries/` | **R** multipart/form/json `BillOfEntry`, `201`; **C** nested serializer is the create boundary (existing deep packet). | BOE manager; UI-027 MasterForm; API/parser tests. | Nested valid/invalid fixture, parse-to-save/error cleanup, D1 and row/allotment/balance effects. **P1 Partial; D1/D2.** |
| **API-037** `GET /bill-of-entries/{id}/` | **C** retrieve adds current allotment IDs to form metadata, and detail queryset prefetches rows/licences/allotments ([boe.py:134](../../../backend/apps/bill_of_entry/views/boe.py#L134)). | BOE read; UI-028/029; API tests. | Missing/foreign object, detail metadata DTO, D1, loading/error/denied and query-budget evidence. **P2 Partial; D1.** |
| **API-038** `PUT /bill-of-entries/{id}/` | **R** full schema `200`; nested update is serializer-owned and may trigger row/balance lifecycle. | BOE manager; UI-028; narrow nested-row test. | Exact full DTO, frozen/correction/stale conflict, transaction rollback, D1/D2 and browser recovery. **P1 Partial; D1/D2.** |
| **API-039** `PATCH /bill-of-entries/{id}/` | **R** patched schema `200`; same nested update boundary as API-038. | BOE manager; UI-028 and list inline action paths. | Field-level/error response, optimistic/stale behavior, row recalculation/reconciliation effects and D1. **P1 Partial; D1/D2.** |
| **API-040** `DELETE /bill-of-entries/{id}/` | **R** `204`; inherited destroy/model relationship behavior is not action-characterized. | BOE manager; row delete control observed but not invoked. | Allocation/reconciliation/document cascade, protected-row rejection, audit/D6, D1 and destructive UI recovery. **P1 Partial; D1/D6.** |
| **API-041** `POST /bill-of-entries/{id}/generate-transfer-letter/` | **C** loads BOE company and delegates shared generator ([boe.py:226](../../../backend/apps/bill_of_entry/views/boe.py#L226)). | `TransferLetterPermission`; UI-029. | Template/request/file fixture, renderer error, D1/D4, audit/provenance and blob recovery. **P1 Partial; D1/D4.** |
| **API-042** `POST /bill-of-entries/{id}/merge/` | **C** requires source ID; service atomically protects linked rows before move/delete. | BOE manager; tests prove protected duplicate rejection. | Direct role/D1, race, file/row/allotment rollback and diagnostics/retry UI. **P0 Partial; D1/D2.** |
| **API-043** `POST /bill-of-entries/{id}/resolve-dispute/` | **C** resolves target then delegates all-row dispute clearing ([boe.py:240](../../../backend/apps/bill_of_entry/views/boe.py#L240)). | Default BOE manager; `MasterList.tsx:1037` static consumer. | Response/status/idempotency/audit fixture, D1, error recovery and reconciliation/balance effect proof. **P1 Partial; D1/D6.** |
| **API-044** `POST /bill-of-entries/{id}/update-invoice-no/` | **C** trims and saves only invoice field, returning id/value/message ([boe_service.py:321](../../../backend/apps/bill_of_entry/services/boe_service.py#L321)). | Overrides to `AccountAccessPermission`; UI list inline consumer. | Empty/duplicate/linked-trade behavior, D1, audit/D6, wrong-role and recovery tests. **P1 Partial; D1/D2/D6.** |
| **API-045** `POST /bill-of-entries/{id}/update-product-name/` | **C** derives product name from item details; no-item failure becomes `400` ([boe.py:232](../../../backend/apps/bill_of_entry/views/boe.py#L232)). | Default BOE manager; `MasterList.tsx:1055`. | Deterministic multi-item rule, retry/idempotency, D1 and UI feedback tests. **P1 Partial; D1.** |
| **API-046** `POST /bill-of-entries/bulk-update-product-names/` | **C** invokes unscoped service bulk operation ([boe.py:262](../../../backend/apps/bill_of_entry/views/boe.py#L262)). | Default BOE manager; `MasterList.tsx:861`. | Selection/scope/result DTO, transaction/partial failure/audit, D1 and destructive confirmation/recovery. **P1 Partial; D1/D6.** |
| **API-047** `GET /bill-of-entries/export/` | **C** grouped export action is injected after view declaration; files/formats are separate from list JSON. | BOE read; UI list export; invalid-format/missing-dependency tests. | File content/filter parity, denied object scope, renderer/storage failure and D4 download feedback. **P2 Partial; D1/D4.** |
| **API-048** `GET /bill-of-entries/fetch-allotment-details/` | **C** requires `allotment_id`, accepts optional current `boe_id`, delegates exclusion-aware service; unexpected failure is `500` ([boe.py:206](../../../backend/apps/bill_of_entry/views/boe.py#L206)). | BOE read; `useMasterFormCalculations.ts:77`. | Request/response fixture, absent/foreign allotment D1, error data leakage and create/edit form recovery. **P2 Partial; D1.** |
| **API-049** `POST /bill-of-entries/parse-pdf/` | **C** multipart file plus optional company creation; parse errors `400`, unrecognized number `422`; atomic flow returns prefill and does not persist BOE ([parse_pdf.py:203](../../../backend/apps/bill_of_entry/views/parse_pdf.py#L203)). | Authenticated BOE permission; parser role tests; UI-027. | MIME/size/malware policy, company-create rollback, malformed/duplicate prefill, D1 and UI retry. **P1 Partial; D1.** |

## Exact population and next evidence

The table has **30 rows**, one for every API-003–017 and API-035–049 ID in
the current operation TSV. Each ID was individually retained even where it
uses an inherited CRUD action. The direct deep evidence does **not** change
the global fully-complete API numerator, which remains `0/354`.

Next tests must add, per mutation, a direct anonymous/wrong-role/valid-role
and D1-approved object fixture; for financial actions add stale/race/rollback
and D2/D3-labelled golden outcome fixtures; for files add content,
authorization, storage/renderer failure and UI recovery. These 28 packets
link to UI-022–029 and are inputs to Q2, not approval to change behavior.
