# 02 — Financial calculation inventory, missing functionality, duplicates

## 5. Existing financial calculation inventory (money, not licence CIF)

The licence CIF/quantity engines are already inventoried in `docs/audits/ERP_FINANCIAL_DEPENDENCY_MAP.md` and
`.claude/rules/business-rules.md`. They are **out of scope and frozen** for accounting.

| # | Quantity | Where | Precision / rounding | Stored? | Notes |
|---|---|---|---|---|---|
| F1 | Line amount (QTY×rate, CIF_INR×pct, FOB_INR×pct) | `LicenseTradeLine.compute_amount` `trade/models.py:562`; server pricing `trade/services/line_pricing.py:50` (T1, uncommitted) | Decimal, ROUND_HALF_UP | `amount_inr` | `amount_override` + reason keeps the manual value. CIF-INR tolerance 1.00 |
| F2 | Incentive line amount | `IncentiveTradeLine.save` :644 | Decimal | `amount_inr` | |
| F3 | Trade subtotal / round-off / total | `LicenseTrade.recompute_totals` :365 | round-off to nearest ₹ | header fields | Written via `queryset.update()`, so it bypasses signals. Called from about 7 places |
| F4 | Paid / received | `LicenseTrade.paid_or_received` :350 | q2 | no | The meaning (paid vs received) depends on direction |
| F5 | Due amount | `LicenseTrade.due_amount` :356 | q2 | no | No credit terms, no due date, no TDS |
| F6 | Payment status | `license/services/license_overview_invoices.py:31-38` | — | no | Paid/Partial/Unpaid. No Overdue/Settled. `_gst_amount()` hardcoded None (:9-28) |
| F7 | Licence profit (realised margin) | `license/services/license_profit.py:26,108-121` | Decimal, then **float** in report output (`purchase_profit_report.py:474,604`) | no | Excludes trades with `linked_trade` set. **May not exclude new-style `counterpart` pairs** (inferred, verify) |
| F8 | Ledger profit/loss per licence | `canonical_ledger_service._build_summary` :770-828 | quantize 2dp | no | A different definition from F7, deliberately not reconciled (`license_profit.py:39-56`) |
| F9 | INR conversion | frontend `cif_fc × exc_rate` (`TradeForm.tsx:457-463`); server `line_pricing.py:75` | 2dp back-derivation | `cif_inr` | `ExchangeRateModel` (`core/models.py:714`) is the DGFT customs rate table, not a bank/forex rate |
| F10 | Financial year | `core/utils/date_utils.py:320 get_financial_year` (Apr–Mar); duplicate `trade/models.py:36 indian_fy_label` | — | — | Reuse the core helper |

There are no GST, TDS, interest, ageing, forex gain/loss or landed-cost calculations anywhere.

## 6. Missing accounting functionality (gap report)

| Area (prompt §) | Exists | Gap |
|---|---|---|
| Chart of accounts, groups (§4) | — | Everything |
| Vouchers, lines, numbering, posting, reversal, period lock (§4) | — | Everything. Invoice numbering exists for trades only |
| Financial years, periods (§4) | FY label helper | Period model, lock, close |
| Trade → posting integration (§3) | Trade header and lines are a good source doc | Lifecycle/post action, posting rules, idempotent source refs, adjustment on edit |
| Purchase fields (§3) | supplier, invoice no/date, lines, qty, rate, value, attachment, payments | GST breakup, TDS, net payable, payment terms, due date, per-trade currency |
| Sales fields (§3) | customer, invoice, value, receipts, Bill of Supply PDF | GST (if applicable), TDS receivable, terms, due date, profitability per trade |
| TDS engine (§5) | — | Sections, PAN status, thresholds, lower-deduction certificates, dated rates, register |
| GST (§6, §12) | GSTIN strings, fixed HSN | Rates, place of supply, CGST/SGST/IGST split, LUT/zero-rated, registers |
| Payments / receipts (§5–6) | `LicenseTradePayment` (date, amount, note) | Bank account, mode, UTR, bill-wise allocation, advances, on-account, status OVERDUE/SETTLED |
| Party ledger (§7) | `CompanyModel` as the party master | Party roles, opening balances, statements, ageing |
| Banking (§8) | one bank account field per company | Bank account master (own), statements, import, matching, suspense, BRS |
| Expenses / commission (§9) | COMMISSION_* trade directions | Independent expenses, categories, cost centres, approval, commission registers |
| Loans (§10) | — | Everything |
| Trade profitability (§11) | F7/F8 licence-level margin | Per-trade P&L from the GL incl. expense allocation, inventory/GIT |
| Reports (§12) | Licence ledger, purchase-profit report | All 22 accounting reports |
| Multi-entity (§13) | — | Legal entities, separate books/numbering/FY, intercompany, consolidation |
| Audit (§17) | `AuditModel`, request-level `ActivityLog`, append-only `TradePairAudit`, `ReconciliationLog` | Field-level history for postable documents, approval trail |

## 7. Duplicate functionality report

| ID | Duplicate | Risk for accounting | Proposed handling |
|---|---|---|---|
| DUP-A1 | Payments copied to the counterpart trade (`trade_service.py:288-294`), not synced afterwards | One settlement posted twice; drift between legs | AD-03/AD-04: post payments as vouchers once. Legacy rows read-only |
| DUP-A2 | Two invoice-number generators (`get_next_invoice_number` :74 unlocked, `next_invoice_number` :431 locked) | Number collisions | Out of scope for accounting (trade fix, ask first). Voucher numbers use their own locked sequence |
| DUP-A3 | Two profit definitions (F7 vs F8) | A third, GL-based profit would conflict | GL-based trade profitability becomes a new, labelled figure. F7/F8 unchanged (frozen contracts) |
| DUP-A4 | `linked_trade` (legacy) vs `counterpart` (new) pairing | Pair exclusion is inconsistent (F7) | AD-03 classification covers both |
| DUP-A5 | FY helpers (`indian_fy_label`, `get_financial_year`) | Inconsistent FY on vouchers | Accounting uses only `get_financial_year` + the `FinancialYear` model |
| DUP-A6 | `CompanyModel` (core) vs MDS `Company`; both carry bank fields | Own bank accounts would be overwritten by sync | Own bank accounts live in a new `accounting.BankAccount`, not in the company master |
| DUP-A7 | `quantize_2dp` ×2 + `q2` | Rounding drift | Accounting uses one money helper (reuse `q2` semantics, ROUND_HALF_UP) |
| DUP-A8 | Commission guide account codes (docs only) vs no CoA | Docs suggest a CoA exists | Replace with the AD-08 seeded CoA |
