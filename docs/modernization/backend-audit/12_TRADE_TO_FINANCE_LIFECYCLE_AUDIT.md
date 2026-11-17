# 12 — Trade-to-Finance ERP: lifecycle & data-integrity audit (read-only, 2026-11-17)

Baseline: `feature/v5` @ `01223ea7` (committed HEAD). **Audit only — no code, formula, data or migration changed.**
Extends doc 10 (`10_TRADE_TO_FINANCE_GAP_MATRIX.md`, cited "GM#"). Paths relative to `backend/apps/trade/` unless stated.
CIF/FOB, Total Allotted and canonical balances are protected; conflicts touching them are recorded, not changed.
Uncommitted WIP from another session (`amount_override`, `services/line_pricing.py`, migration 0012) is **not** in
the baseline; where relevant its effect is noted. "(inf)" = inference.

Verified by hand at HEAD: F1 constraint keys (`models.py:309-319`), F4 rounding (`purchase_invoice_pdf.py:449`,
`bill_of_supply_pdf.py:468` vs `models.py:377`), F11 (`api/views.py:341`).

## A. Code findings

| # | Sev | Area | Finding | Evidence | Remediation (proposal only) |
|---|---|---|---|---|---|
| F1 | HIGH | Trade↔invoice | SALE numbers can duplicate: `get_next_invoice_number` takes no lock; `LicenseTrade.next_invoice_number` locks inside its own `atomic()` and releases before the caller saves. SALE unique constraint is keyed on **buyer** (`to_company`) while the series is keyed on **seller** prefix → same number to two buyers is accepted. Confirmed in data (B-1). | `models.py:~74-132, :431, :309-319` | Locked per-(issuer, direction, FY) counter row; unique (issuer, direction, invoice_number). |
| F2 | MED | Trade↔invoice | Two generators (GM3a); prefix derived from company name only (two companies abbreviating to "LM" share a series); `_copy_to_counterpart` numbers with `source.to_company.name` regardless of destination direction. | `services/trade_service.py:240-244`, `models.py:445` | One issuer-aware generator. |
| F3 | MED | Lifecycle | `invoice_number`/`invoice_date` editable after issue, payment or BOE link; update re-stamps BOE `invoice_no/date`; back-dating shifts FY numbering. | `api/views.py:~100`, `api/serializers.py:605-608` | Freeze after first payment / document / allocation. |
| F4 | HIGH | Reporting | Rounding divergence: header ROUND_HALF_UP to rupee; PDFs use Python `round()` (banker's). 1000.50 → header 1001, PDF 1000. | `models.py:377`; `purchase_invoice_pdf.py:449`; `bill_of_supply_pdf.py:468` (direct-download path) | One shared rounding helper (needs decision D1). |
| F5 | HIGH | Reporting | Three "bill" figures: header `total_amount` (rounded), licence ledger Σ`amount_inr` (unrounded), persisted sale PDF `canonical_total_inr` (unrounded) → `TradeInvoiceDocument.sale_bill_inr` ≠ figure `due_amount` is computed from. | `license/services/canonical_ledger_service.py:1258-1277`; `invoice_document_service.py:123` | Decide authoritative total (D1); apply consistently. Ledger side is protected — needs cif-balance-auditor. |
| F6 | MED | Reporting | Profit/ledger reports sum lines per licence; multi-licence or rounded trades won't tie to header; invoice tab returns subtotal and total side by side; frontend recomputes in JS floats (inf). | `license/services/license_profit.py:348,396`; `purchase_profit_report.py:380,531`; `license_overview_invoices.py:48-52`; `frontend/src/pages/tradeFormHelpers.ts:412-503` | Reconciliation test: header = Σlines + roundoff. WIP narrows this. |
| F7 | MED | Payments | No payment validation: negative amounts and overpayment accepted; `due_amount` can go negative and status shows "Paid"; no date ≥ invoice date check; no mode/bank/UTR/created_by; freely editable/deletable via generic viewset. | `models.py:~650`; `license_overview_invoices.py:32`; `api/views.py:~695` | Min-value validator, ≤ due unless "advance", AuditModel. |
| F8 | MED | Payments | Paid/due computed per read from current `total_amount`; editing lines after payment silently changes due; no history. | `models.py:357`; `api/serializers.py:23-37` | Block line edits on (part-)settled trades or record adjustments. |
| F9 | MED | Lifecycle/Payments | Paired copy clones payments to the counterpart (a SALE receipt becomes a PURCHASE payment); later sync never syncs payments and deletes/recreates counterpart lines. | `services/trade_service.py:289-293, 411-444` | Don't copy payments, or tag as mirror excluded from party balances (D2). |
| F10 | MED | Lifecycle | Errors swallowed in nested line sync and counterpart sync under an outer `atomic`; e.g. removing a line protected by `InvoiceBOEAllocation` (PROTECT) leaves header/lines/counterpart out of step. | `api/serializers.py:543, 555-585, 612-619`; `reconciliation/models.py:263` | Savepoints per step; surface warnings instead of swallowing. |
| F11 | MED | Lifecycle | **Bug:** `resolve_final_party` saves `update_fields=[..., 'updated_on']`; field is `modified_on` → `ValueError` / HTTP 500. No test covers it. | `api/views.py:341` | Use `modified_on` + test (separate approval; non-financial). |
| F12 | MED | Lifecycle/Trace | Trade DELETE hard-cascades lines, payments, invoice documents, tokens, document audit events; only paired deletes write `TradePairAudit`; standalone delete leaves only a method/path ActivityLog row. | `models.py:~693`; `core/middleware.py:59-135` | Block delete when payments/documents/allocations exist; soft-cancel (D3). |
| F13 | MED | Commission | No duplicate guard for `COMMISSION_*` (constraints conditioned on PURCHASE/SALE only); no rate, base trade or agent; only manual `linked_trade`. Balance engine excludes them, invoice ledger includes them. | `models.py:234, 311, 317`; `license/services/transaction_semantics.py:85-120`; `license_overview_invoices.py:19-20` | Per-direction unique constraint; `commission_base_trade` FK (D5). |
| F14 | LOW | Bank recon | Absent: no `utr`, `bank_statement`, `cheque`, `neft`, `rtgs`, `bank_ref` anywhere in `backend/apps` (GM10a, 10d). | grep | Depends on D6. |
| F15 | MED | Party ledgers | No customer/supplier aggregation — only per-licence slices; those include commission trades and inherit F4/F5. Lines and payments carry no actor. | `license_overview_invoices.py`; GM10b, 10g | Party statement service; audit fields on lines/payments. |
| F16 | MED | Trade↔invoice | Editing an issued trade creates a new PDF version; older versions and tokens remain valid and unflagged → two amounts for one invoice number. Unit/rate edits that don't change `amount_inr` produce no new version. PURCHASE PDF always live-rendered. | `invoice_document_service.py:78-114`; `api/views.py:~405, ~447` | Mark superseded versions, or freeze on issue. |
| F17 | LOW | Traceability | Chain licence→allotment→BOE→invoice→payment breaks at allotment↔line (no FK, GM7b); `LicenseTrade.boes` M2M carries no amounts; payments link to whole trade only. | GM7b; `backfill_boe_allocations` 1:1 only | Depends on OD-MAP decisions. |
| F18 | LOW | Dup detection | Detection = 2 unique constraints, `backfill_boe_allocations` dry-run, `check_allocation_health`, `missing_purchase_invoice_warning`, `sale_classification_review`. F1/F13 duplicates undetected. | — | Read-only integrity report command (proposal). |

WIP note: the uncommitted `amount_override` / server-side pricing work narrows F6 and GM4a; it does not address F1-F5, F7-F16.

## B. Measured data integrity (local dev DB, read-only ORM, 2026-11-17 04:47 UTC)

Host confirmed localhost. Base: 566 trades (323 SALE, 243 PURCHASE, 0 COMMISSION_*), 874 lines, **0 payments**,
2 `InvoiceBOEAllocation`. The local DB is re-synced periodically and appears to be a subset (no payments,
no commissions) — payment/commission results must be re-measured on a production clone.

| # | Check | Result | Example IDs | Assessment |
|---|---|---|---|---|
| B-1 | Duplicate SALE invoice numbers | 2 groups / 4 rows (1 within same year) | 64/262, 288/293 | **Defect** — consistent with F1 |
| B-2 | Same direction+parties+date+total | 2 groups | 16/17, 540/541 | Probable double entry |
| B-3 | Blank PURCHASE invoice number | 1 | 520 | Defect |
| B-4 | Header `total_amount` ≠ Σ line `amount_inr` (>0.01) | 188 | 1, 2, 3, 4, 8 | Defect or rounding/manual drift — cause not traced (F4-F6) |
| B-5 | Header `subtotal` ≠ Σ lines | 116 | 59, 81, 87 | Defect (header itself internally consistent: subtotal+roundoff=total) |
| B-6 | `amount_inr` ≠ mode formula (>1 INR) | 133 | 134-138 | Expected legacy manual amounts (GM4a) |
| B-7 | `cif_inr` ≠ `cif_fc × exc_rate` (>1 INR) | 48 | 100-104 | Protected CIF data — record only |
| B-8 | Non-incentive trade with zero lines; zero-amount line | 1; 1 | 362; line 470 | Defect |
| B-9 | Invoice-number FY ≠ Apr–Mar FY of `invoice_date` | 3 of 383 | 359, 262, 328 | Defect (F3 back-dating) |
| B-10 | SALE without `InvoiceBOEAllocation` | 322 of 323 | — | Not backfilled; not corruption |
| B-11 | Pairing (counterpart/UUID/direction/totals) | 0 issues (7 pairs) | — | OK |
| B-12 | Payments / commission checks | vacuous (0 rows) | — | Re-measure on prod clone |

## C. Data-integrity risks (ranked)

1. **No financial source of truth** — totals, payments and documents are mutable operational rows; delete cascades financial records (F8, F12, GM10e).
2. **Duplicate invoice numbers** already present and not prevented (F1, B-1).
3. **Three different invoice totals** (header / PDF / ledger) with different rounding (F4, F5, B-4/B-5); party dues computed against a figure that differs from the issued document.
4. **Paired trades** can diverge (payment copy + swallowed sync errors) (F9, F10).
5. **Commission** unguarded and unlinked (F13); invoice ledger and balance engine disagree on inclusion.
6. **Traceability gap** allotment↔invoice line and BOE↔invoice amounts (F17, B-10).
7. Overview "Total Allotted" double count (escalated earlier; protected) — anything built on overview numbers inherits it.

## D. Proposed remediation sequence (each item needs separate explicit approval)

| Phase | Items | Touches protected financial maths? |
|---|---|---|
| P0 bugfix | F11 `updated_on` → `modified_on` + test | No |
| P1 detection (read-only) | Management command / report for B-1..B-9 checks; reconciliation tests header = Σlines + roundoff | No |
| P2 guards | Numbering lock + unique (issuer, direction, number) (F1, F2); commission constraint (F13); payment validators (F7); savepoints instead of swallowing (F10) | No (constraint migrations need `migration-safety`; existing duplicates B-1 must be resolved first by owner) |
| P3 lifecycle | Status/lock after issue, cancel instead of delete, superseded PDF versions (F3, F8, F12, F16) | No, but API contract change |
| P4 totals | Single rounding policy and authoritative total (F4, F5, F6) | **Yes** — `cif-balance-auditor` review + separate approval |
| P5 finance | Party statements, payment mode/bank/UTR, bank reconciliation, accounting integration (F14, F15, GM10) | Depends on D6 |

No data corrections are proposed automatically; B-1/B-2/B-3/B-8/B-9 rows need owner review case by case.

## E. Business decisions required

- **D1** Invoice total: rounded to rupee or unrounded? Which figure is authoritative — header, PDF or ledger?
- **D2** May payments be mirrored onto the paired trade? Are advances / overpayments allowed?
- **D3** When is an invoice locked (first payment, PDF issued, BOE allocated)? Replace delete with cancel/reversal?
- **D4** Who owns the number series (issuer company × direction × FY)? Must it be gapless?
- **D5** Commission: link to a base trade, carry a rate/agent, include or exclude from party balances?
- **D6** System of record for payments and bank reconciliation (in-app vs Tally/other)?
- **D7** Duplicate rows B-1/B-2 and blank number B-3: which are genuine, and how should they be corrected (manual, audited)?
- Plus doc 10 prerequisites (tax treatment, accounting scope, invoice model, amount authority) and OD-QTY / OD-MAP.
