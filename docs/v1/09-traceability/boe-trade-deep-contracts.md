# BOE and trade API deep contracts

**Bounded direct-source audit — 14 operations.** This document supplements the
registered [BOE contract rows](api-operation-contracts-license.md) and [trade
contract rows](api-operation-contracts-remaining.md). It is not a claim that
the BOE or trade API families are complete. Each row is **Partial** because
the direct request/effect evidence below does not yet include the full role,
object/company, error/recovery, consumer and browser suite required by the
[contract-closure protocol](contract-closure-protocol.md).

**Evidence labels:** **C** = verified by current source; **T** = named current
test; **R** = registered OpenAPI/route evidence; **P** = proposed V1 acceptance
work; **D** = owner decision required. Current role checks are role-based;
nothing here infers company/object isolation (D1). Trade invoices/payments are
commercial evidence, not a verified GL or bank-reconciliation capability (D5).

| API ID / method | Direct current contract | Principal data/transaction/effect evidence | Authorization, consumer/test evidence and closure gap | Status |
| --- | --- | --- | --- | --- |
| **API-036** `POST /api/bill-of-entries/` | **R** accepts the `BillOfEntry` schema and declares `201`. **C** the nested serializer creates BOE/row data (`serializers.py:267`). | BOE rows carry debit and allocation relationships; serializer/model behavior is not a substitute for a parse-to-save atomic contract. | **C** `BillOfEntryPermission` writes require `BOE_MANAGER` (`permissions.py:60`). **T** `test_create_boe_missing_required_fields_returns_400` and BOE API tests are discovered. **P** freeze valid/nested-invalid DTO fixtures, direct anonymous/viewer/object cases, row rollback and file-cleanup behavior. | P1 / Partial; D1 |
| **API-038/039** `PUT/PATCH /api/bill-of-entries/{id}/` | **R** full/patched `BillOfEntry` schemas declare `200`. **C** detail queryset prefetches rows, licences and allotments before serializer update (`views/boe.py:134`). | **C** nested update begins `serializers.py:299`; model/service lifecycle may schedule downstream recalculation. No single source reviewed here proves conflict semantics. | **T** `BillOfEntryNestedRowUpdateTests::test_update_ignores_header_planning_metadata_when_creating_row` is a narrow behavior test. **P** assert stale edit, frozen-row/correction, balance/reconciliation effects and failure rollback. | P0/P1 / Partial; D1/D2 |
| **API-041** `POST …/generate-transfer-letter/` | **C** resolves BOE with company and delegates template/file generation to `generate_transfer_letter_generic` (`views/boe.py:226`). | Document generation is an external/file-producing effect; its storage/error/retention contract is not fully traced. | **C** action overrides default role policy with `TransferLetterPermission` (`:123`). UI-029 names this endpoint. **P** test template/selected-data validation, blob failure, authorization matrix and audit/provenance. | P1 / Partial; D1/D4 |
| **API-042** `POST …/merge/` | **C** requires `source_boe_id`; missing/self/not-found/protected duplicates become `400`/`404` (`views/boe.py:247`, `boe_service.py:203`). | **C** one transaction moves nonduplicate rows, transfers allotments, deletes source, changes target port; protected duplicate reconciliation links abort before movement (`boe_service.py:242–292`). | **T** `test_merge_rejects_protected_duplicate_before_any_rows_move` proves one rejection path. **P** role/object policy, concurrent merges, row/allotment reconciliation and UI retry/diagnostics. | P0 / Partial; D1/D2 |
| **API-044** `POST …/update-invoice-no/` | **C** body `invoice_no` defaults blank and trims/saves exactly that field, responding ID/value/message (`views/boe.py:267`; `boe_service.py:321`). | A direct header mutation; it does not prove linked trade, hidden-BOE, audit or balance semantics. | **C** action overrides to `AccountAccessPermission` (`views/boe.py:124`), distinct from ordinary BOE manager writes. **P** test empty/duplicate/hidden/reconciliation behavior, direct wrong-role and object policy. | P1 / Partial; D1/D2 |
| **API-047** `GET /api/bill-of-entries/export/` | **C** grouped export is injected by `add_grouped_export_action` (`views/boe.py:276`); OpenAPI declares `200` without a response DTO. | Export may produce XLSX/PDF and must not be assumed equivalent to JSON list output. | **T** `test_export_rejects_invalid_format_before_work`, XLSX/PDF and missing-dependency `503` cases in `test_api_boe.py`. **P** fixture content/provenance, filter parity, denied download and generated-file failure/retry tests. | P1 / Partial; D1/D4 |
| **API-049** `POST /api/bill-of-entries/parse-pdf/` | **C** requires multipart `file`, optional `create_company`; parser failure is `400`, unsupported/no BOE number is `422` (`views/parse_pdf.py:203`). | **C** entire parse/match/prefill flow is atomic; it may match/create a company but returns prefill and does **not** persist a BOE. | **C** requires authenticated `BillOfEntryPermission`; parser-role tests identify BOE manager allowed and allotment manager denied. **P** validate PDF/size/malware policy, company-create rollback, malformed/duplicate prefill and UI retry. | P1 / Partial; D1 |
| **API-334** `POST /api/trades/` | **R** `LicenseTrade` request schema and `201`. **C** serializer transaction creates header, nested lines/incentive lines/payments, totals, BOE links/invoice stamps and optional paired trade (`serializers.py:401`). | **C** standalone sale without BOE locks import items and rejects cumulative quantity above current availability before writes (`:421–442`). | **C** `TradePermission` writes require `TRADE_MANAGER` (`permissions.py:66`). **T** `test_create_trade`, paired-CIF tests and trade form smoke test exist. **P** version DTO, payment validation, paired failure rollback, D1 direct cases and financial golden effects. | P0/P1 / Partial; D1/D2/D5 |
| **API-336/337** `PUT/PATCH /api/trades/{id}/` | **R** full/patched trade schemas declare `200`. **C** serializer update is atomic and synchronizes optional nested lines/payments/BOEs, totals and invoice stamps (`serializers.py:502`). | **C** removed BOEs are cleared only when still stamped with this trade invoice; counterpart synchronization failures are logged rather than rolling back the completed main update (`:570–617`). | **T** `test_serializer_update_call_site_does_not_unhide_boe` and trade service hidden-guard cases bound selected behavior. **P** make counterpart sync recovery observable; test stale edits, nested delete, correction/reversal and financial parity. | P0/P1 / Partial; D1/D2/D5 |
| **API-339/340** `POST …/copy-to-purchase|copy-to-sale/` | **C** delegates to directional counterpart services; returns `201` only when created, otherwise idempotent-looking `200`, and maps missing source to `404`/validation to `400` (`views.py:591–615`). | Pair creation/linking affects commercial records; exact service locking and compensation are not fully covered by this slice. | **T** `CounterpartCopyTests::test_sale_to_purchase_is_idempotent_and_reciprocal` and inverse reuse tests. UI-030 list actions consume trade operations. **P** direct role/object tests, duplicate concurrent copy, financial/replan effect and browser state recovery. | P1 / Partial; D1/D5 |
| **API-342/343** `GET …/generate-bill-of-supply|generate-purchase-invoice/` | **C** require respectively SALE/PURCHASE and optional `include_signature`; wrong direction is `400`, renderer failure `500`, success streams inline PDF (`views.py:393–493`). | Generated PDFs derive invoice/party amounts. Their storage/protected-download/caching policy is separate from the inline response. | **T** `TestTradeBillOfSupply::test_generate_bill_of_supply` and invoice-document service tests cover selected generation/version behavior. **P** wrong-role/object, signature/input, renderer failure and document provenance/retention tests. | P1 / Partial; D1/D4/D5 |
| **API-345** `POST …/link-trade/` | **C** accepts nullable `partner_id`, delegates bidirectional linking, returns serialized trade; invalid partner is `400`, absent partner `404` (`views.py:555–578`). | Linking mutates both records through the service; no reviewed source proves a transaction/race contract here. | **T** `LinkTradesTests` cover link/unlink/self/missing/relink behavior. **P** direct permission/object cases, concurrent re-link, counterpart balance/document implications and UI explanation. | P1 / Partial; D1/D5 |
| **API-346/347** `POST …/resolve-final-party|sales-classification-review/` | **C** resolution requires SALE plus a nonblank auditable note and either canonical buyer or an explicit UNKNOWN status; validates/saves classification fields (`views.py:318–351`). Classification decision delegates to service and maps not-found/value errors to `404`/`400` (`:306–316`). | Classification may affect provenance/reporting; source does not establish its financial or cross-company policy. | **C** default `TradePermission` write applies. **P** add request fixtures, audit/log retention, reviewer role/object cases, import/export reconciliation and correction/reversal tests. | P1 / Partial; D1/D5/D6 |

## Related BOE hide/restore behavior

The requested BOE hide/restore workflow is currently exposed through the
licence-balance actions rather than the fourteen BOE REST rows selected here.
**C** `hide_boe` preserves the previous invoice, writes a reconciliation log
and refreshes every touched licence; `restore_boe` is a hidden-only inverse
with a no-op path (`boe_service.py:487`, `:537`). Bulk siblings collect
per-ID failures and refresh each touched licence once (`:580`, `:636`).
**T** `test_hide_and_restore_both_recompute_every_touched_license`, idempotency
tests and hide-log tests in `test_boe_hide_service.py` establish narrow
current behavior. The remaining closure is the action-level role/D1 scope,
concurrent hide/restore, audit durability (D6), API fixture and browser
provenance contract; see BAC-01–06 and the P0 regression test contracts.

## V1 acceptance dependencies

1. Freeze D1 before adding company predicates or declaring their absence a
   defect; every selected mutation needs anonymous, wrong-role, approved-role
   and approved company/object-pair tests.
2. Preserve atomic BOE merge and trade serializer boundaries. Characterize the
   explicitly non-atomic counterpart-sync failure path before changing it.
3. Treat parse, PDF, transfer-letter and export behavior as file-lifecycle
   contracts: validation, access, storage/renderer failure, cleanup and user
   recovery must be tested independently from CRUD success.
4. Freeze D2-labelled balance effects and D5 commercial scope before changing
   trade/BOE accounting or report claims.

This 14-operation slice does not increase the global complete-operation,
frontend-contract or static-symbol numerator.
