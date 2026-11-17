# 10 — Trade-to-Finance ERP: gap matrix (read-only audit, 2026-11-17)

Baseline: `feature/v5` @ `1d37f29c`. No code changed. The licence balance engine is frozen; its conflicts are recorded,
not proposed for change. "Ledger" below means the **DGFT licence balance ledger** unless prefixed "financial".
Sources: code (file:line) plus backend-audit 02, 05, 07, 08 and `DECISION_REGISTER.md`. "inf" = inference.

Legend: **E** EXISTING · **I** INCOMPLETE · **M** MISSING · **R** NEEDS REFACTORING

## Matrix

| # | Area | Capability | Status | Evidence | Gap |
|---|---|---|---|---|---|
| 1 | Trade mgmt | Trade header, parties, licence link | E | `trade/models.py:138` `LicenseTrade`; party snapshot `:393`; `LicenseTradeLine.sr_number` FK `:525` | — |
| 1a | | Lifecycle / status (draft→confirmed→cancelled) | M | no status field; only `final_party_status` | deletion is the only void path |
| 1b | | File size / layering | R | `models.py` 817 L, `api/views.py` 719 L, permission assigned post-definition (`views.py:273,691,719`) | split like license/allotment `api/` layering |
| 2 | Purchase & sales | Direction, pairing, copy | E | `direction` `:140-152`; `counterpart`, `transaction_pair_uuid`, `TradePairAudit`; `copy_trade` `services/trade_service.py:216` | — |
| 2a | | Final-party classification | E | `services/final_party_classification.py`, `SaleClassificationDecision` `:476` | SALE only |
| 2b | | Duplicate-invoice guard | I | `uniq_purchase_supplier_invoice`, `uniq_sale_buyer_invoice_nonblank` | no constraint for COMMISSION_* (inf) |
| 3 | Direct invoices | Invoice independent of a licence trade | M | invoice = `LicenseTrade` row | needs Invoice model or trade refactor |
| 3a | | Invoice numbering | R | two generators: `get_next_invoice_number` `:74` and `LicenseTrade.next_invoice_number` `:431` | drift; concurrency unverified |
| 3b | | PDFs / secure links / versioning | E (R) | `bill_of_supply_pdf.py` 793 L, `purchase_invoice_pdf.py` 741 L, `TradeInvoiceDocument` `:693` | no PDF-content tests; large modules |
| 3c | | GST (CGST/SGST/IGST, rate, place of supply), e-invoice | M | only GSTIN snapshots + `hsn_code` default 49070000 | Bill of Supply = no-tax doc; owner must confirm tax treatment |
| 3d | | Credit / debit notes, cancellation | M | no matches in `backend/apps` | — |
| 4 | Item qty/CIF/FOB | Trade line fields (Decimal) | E | `qty_kg`, `rate_inr_per_kg`, `cif_fc`, `exc_rate`, `cif_inr`, `fob_inr`, `pct`, `amount_inr`, `mode` | — |
| 4a | | Server-side amount derivation | I | `LicenseTradeLine.save` `:567` computes only when `amount_inr` is 0; `cif_inr` never derived from `cif_fc × exc_rate` | totals can diverge from inputs |
| 4b | | Line validation | I | only "≥1 line" (`api/serializers.py:327`); no sign/consistency checks | — |
| 4c | | Totals recompute | I | `recompute_totals` `:365` per line save | N+1 on bulk saves (inf) |
| 4d | | Licence/allotment/BOE CIF FC vs INR | I | allotment header derives INR; `AllotmentItems.cif_inr` = 0 for UI rows (05 D7) | — |
| 4e | | Quantity semantics / units | I | 08: S1-S22 parallel computations; no unit conversion (07 §3) | blocked on OD-QTY-1..14 |
| 4f | | FOB | I | export side only (`license/models/items.py:57`, `header.py:238`); not in engine | — |
| 5 | Licence allocation & utilisation | Reserve via allotment items | E (R) | `allotment/views_actions.py:1072` `_allocate_items_atomic` (atomic, locked) | ~500 L business logic in view (02 #1); 05 D1-D12 |
| 5a | | Consume via BOE | E | `balance_calculator.py:459,512` | — |
| 5b | | Consume via trade (SALE) | I | `calculate_trade` `:1063`; qty check only for SALE without BOE (`trade/api/serializers.py:428-438`) | `_force_save`/paired/legacy bypass CIF check |
| 5c | | Utilisation reporting | I | overview services, item pivot | overview "Total Allotted" double counts (HIGH, escalated) |
| 5d | | Orphan allocation code | R | `AllocationService`, `AllotmentValidationService`, `calculate_available_value_for_allocation` (no prod caller) | decision O8 open |
| 6 | BOE matching | BOE↔allotment (M2M) | E (R) | `bill_of_entry/models.py:211`; serializer write not atomic (`serializers.py:296-375`) | cross-licence links possible (OD-MAP-2) |
| 6a | | BOE↔allotment-item fine allocation | I | `BOEAllotmentAllocation` `reconciliation/models.py:331` + atomic service | no production writer (05) |
| 6b | | Invoice↔BOE | E | `InvoiceBOEAllocation` `:226`, `boe_link_reconciler.py:47,71` (1:1 unambiguous only) | writes only via `backfill_boe_allocations --apply` |
| 6c | | Unmatched / ambiguous handling | I | reconciler skips ambiguous; warnings via `warning_service.py` | no UI resolution flow (inf) |
| 7 | Allotments | Model + items + constraints | E | `allotment/models/core.py:135-208,338-347` | `save()` rewrites `cif_fc` (D10) |
| 7a | | Lifecycle (release/reactivate, versioning) | I | fields + `AllocationVersion` exist, no writer (O7); copy not atomic/audited | — |
| 7b | | Allotment ↔ trade/invoice line link | M | no allotment FK on `LicenseTradeLine` | only chain: allotment→BOE→invoice |
| 8 | Balance engine (frozen) | Canonical engine | I | `LicenseBalanceCalculator` `:80`, `ItemBalanceCalculator` `:1714`; customs vs financial engines by design | parallel paths: stored cache (`core/scripts/calculate_balance.py`), MVs, ledger builder, canonical_ledger_service, R3/R5/overview/pivot |
| 8a | | Known rule/code conflicts | R (escalated) | 05 D1/D2/D3/D5/D6; ledger re-import CREDIT duplication `core/scripts/ledger.py:308` | owner decisions, not engine edits |
| 9 | Expenses & profitability | Trade expense / cost model | M | none | — |
| 9a | | Commission | I | COMMISSION_* directions + numbering only | no rate/amount/agent payable |
| 9b | | Margin per trade | M | none | — |
| 9c | | P&L report | I | `LicensePurchaseProfitReportView` (`license/urls.py:67`), `services/purchase_profit_report` | per licence, live-computed, no expenses/overheads |
| 10 | Accounting | Chart of accounts / journal / double entry | M | no model in backend or MDS; `COMMISSION_ACCOUNTING_GUIDE.md` describes an external system | new app needed |
| 10a | | Payments / receipts | I | `LicenseTradePayment` `trade/models.py:650` (date, amount, note); CASCADE on trade delete; no AuditModel | no mode/bank/UTR/TDS/advance/multi-invoice allocation |
| 10b | | Party outstanding / ageing / statements | I | per-invoice `due_amount` only (`:351-363`) | no party-level view |
| 10c | | Party master | I | `CompanyModel` `core/models.py:226` mirrored to MDS (`MDS_ENABLED` default False) | no role/credit terms/opening balance/account link |
| 10d | | Bank, TDS/TCS | M | bank fields on party only | — |
| 10e | | Fiscal period close / lock | M | FY used only for numbering | back-dated edits unblocked |
| 10f | | FX for finance | I | `ExchangeRateModel` `core/models.py:714` = DGFT customs rates | no realised/unrealised FX |
| 10g | | Financial audit trail | I | `AuditModel`, `ActivityLog`, `TradePairAudit`, `InvoiceDocumentAuditEvent` | no before/after history |
| 10h | | Tally / external accounting export | M | none | — |
| 10i | | Finance UI | M | `TopNav.tsx:20-53`: Licenses, Operations, Reports only | — |

## Prerequisites before coding (owner decisions)

1. **Tax treatment**: are licence sales exempt supplies (Bill of Supply) only, or must the ERP issue GST tax invoices?
2. **Accounting scope**: in-app double-entry general ledger vs. export to Tally (or another system) as the system of record.
3. **Invoice model**: new `Invoice` entity (direct invoices, credit/debit notes) vs. extending `LicenseTrade`.
4. **Lifecycle/cancellation policy**: replace hard delete with cancel + reversal for posted invoices.
5. **Amount authority**: should the server always derive `amount_inr`/`cif_inr`, or keep manual override (with a flag)?
6. Existing blockers still apply to quantity-based profitability: OD-QTY-1..14, OD-MAP-1..6, doc 05 O1-O10.

## Risks

- HIGH: no financial source of truth; invoice and payment data are mutable operational rows (recompute, cascade delete, no period lock).
- HIGH: overview "Total Allotted" double count (escalated, engine-adjacent). Any profitability built on overview numbers would inherit it.
- MEDIUM: manual `amount_inr` plus non-derived `cif_inr` lets invoice totals diverge from CIF/FOB.
- MEDIUM: trade CIF validation is bypassable (`_force_save`, paired, legacy mode).
- MEDIUM: two invoice-number generators.
- Naming: a new finance module must avoid "ledger" (use `gl_`/`acct_`) to avoid collision with the licence ledger.
- Coverage gaps: no tests for invoice numbering, line amount computation, PDF content, or the trade permission matrix.
