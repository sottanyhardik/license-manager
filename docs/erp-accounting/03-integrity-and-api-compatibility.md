# 03 — Data integrity risks and API compatibility

## 8. Data integrity risk report (accounting lens)

Severity reflects the risk **once trades feed a GL**. Several are harmless today.

| ID | Risk | Evidence | Severity | Mitigation in the design |
|---|---|---|---|---|
| R1 | Trades are hard-deleted with cascade to lines, payments and documents | `trade/models.py:513,657,700` CASCADE; no soft delete | Critical | Accounting registers a `pre_delete` guard on `LicenseTrade` that blocks deletion of any trade with a posted voucher (accounting imports trade, so no cycle) |
| R2 | Header and lines are editable forever; totals rewritten by `queryset.update()` | `recompute_totals` :365; serializer `update` | Critical | Posting stores an immutable snapshot (`posted_total`, `source_version_hash`). A post-edit check detects drift and requires a reversal + re-post (AD-06) |
| R3 | Paired trades double settlements and possibly revenue | DUP-A1, `_copy_to_counterpart` | Critical | AD-03 pair classification. Posting refuses unclassified pairs |
| R4 | Nested sync errors are swallowed for paired trades (`force_save` forced True when a counterpart exists) | `api/serializers.py:565-567,583,602,616,648-652` | High | Posting re-reads lines from the DB and validates Σ lines = header total before posting. Fixing the trade itself is a separate approved task |
| R5 | Invoice-number race | `get_next_invoice_number` :74 | Medium | The DB unique constraint guards PURCHASE/SALE. Voucher numbering uses a row-locked `VoucherSequence` |
| R6 | No uniqueness for COMMISSION_* invoice numbers | constraints :302-327 | Medium | The posting idempotency key is (entity, source type, source id, event, version), independent of the invoice number |
| R7 | Party FK SET_NULL; snapshot lacks the party name | :190-214 | Medium | Voucher lines reference `party` with PROTECT, plus a name snapshot |
| R8 | Float money in API/report output | `api/serializers.py:196`, `purchase_profit_report.py:474,604` | Medium | Accounting APIs serialise Decimals as strings only |
| R9 | `LicenseTradePayment` has no direction, bank, UTR or user | :657 | High for reconciliation | New Payment/Receipt vouchers (AD-04) |
| R10 | Request-level audit only; no field history for payments | `ActivityLog` | High | Accounting writes an append-only `AccountingAuditEvent` in the same transaction |
| R11 | MDS sync may overwrite company rows keyed by IEC (inferred) | `MasterSyncMixin` | Medium | No accounting state stored on `CompanyModel`. LegalEntity/BankAccount live in accounting |
| R12 | The dev DB has 0 trades (OD-17), so migration and reconciliation cannot be rehearsed locally | erp-transformation 12 | High for cut-over | Requires a sanitised production snapshot before any opening-balance work (Phase B gate) |
| R13 | Historical trades: unknown which are already accounted in Tally | — | Critical | AD-02 cut-over: only trades dated ≥ cut-over post. Older ones are covered by opening balances. A reconciliation report proves there is no overlap |

## 9. Existing API compatibility report

Rule (ARCHITECTURE_RULES 7): existing contracts are frozen, and changes are additive only.

| Existing surface | Used by | Accounting impact | Compatibility plan |
|---|---|---|---|
| `GET/POST/PATCH/DELETE /api/trades/` (+ actions copy-to-*, unpair-and-delete, counterpart, link-trade, generate-*, prefill-invoice-number, summary) | `TradeForm.tsx`, `TradesListView.tsx` | DELETE and some edits become refused for posted trades | Additive read-only fields `accounting_status`, `voucher_refs` via a separate endpoint first (`/api/accounting/sources/trade/<id>/`). The DELETE refusal returns the existing 400 error shape. **API CONTRACT CHANGE for DELETE and PATCH semantics on posted trades — needs explicit approval (AD-06)** |
| `/api/payments/` (`LicenseTradePayment`) | `NestedFieldArray` payments | Becomes legacy | Unchanged shape. After cut-over, writes for posted trades are refused (approval with AD-04) |
| `/api/lines/` | Trade form | Same as trades | Same guard |
| `paid_or_received`, `due_amount` in the trade response | Trade list/form, licence invoice ledger | The accounting outstanding differs once TDS and vouchers exist | Keep the existing fields unchanged. Add `accounting_outstanding` as a new, separately labelled field |
| `licenses/<id>/overview-invoice-ledger/`, balance ledger, license-ledger, purchase-profit | Licence pages | None — licence CIF/profit stays independent | No change (frozen) |
| `/api/auth/me/` `roles` | `AuthContext.tsx` | New role codes appear | Additive |
| New `/api/accounting/...` namespace | new screens | — | Mounted before the `^api/` catch-all in `lmanagement/urls.py`. Versioned with OD-07 when that lands |
