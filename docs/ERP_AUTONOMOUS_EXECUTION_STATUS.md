# ERP autonomous execution status — Trade → Accounting → Banking → Reporting

Branch `docs/erp-accounting-audit` (worktree `.claude/worktrees/erp-accounting-audit`), based on `feature/v5` @ `01223ea7`.
Owner rule: work lands on `feature/v5`; this worktree is cherry-picked into it (`--only` paths). **Nothing pushed or
deployed. No production data touched.** Design: `docs/erp-accounting/04-*` + ADR-004.

Status legend: **Implemented** (code), **Tested** (automated tests green), **Dry-run validated**, **Migrated**,
**Approved**, **Deployed**. Nothing below is Approved/Deployed/Migrated on production.

## Decisions taken (routine, reversible; recorded instead of asked)

| ID | Decision (implemented) | Why safe |
|---|---|---|
| AD-01 | `EntityBooks` uses the existing `core.CompanyModel` id as its **primary key**, so the entity ids are the Trade entity ids. Entities are discovered from Trade and books are **activated** explicitly. No company is seeded or invented. It holds book configuration only. | No second company master; IDs preserved; MDS-mirrored master untouched |
| AD-02 | Each entity has its own `books_start_date`. Trades before it are not posted (opening balances cover them). Historical posting goes through the Migration Center dry run → explicit `confirm=true` execution. | Nothing posts automatically; dry runs write no vouchers |
| AD-03 | Paired trades: `from_company` = seller and `to_company` = buyer on both legs (verified in `trade_service._copy_to_counterpart`). A SALE posts in the seller's books and a PURCHASE in the buyer's. A leg whose own side has no active books is not postable. If both sides have books, the pair is intercompany: each leg posts once in its own books to INTERCOMPANY_* accounts, and consolidation eliminates them. | No leg can post twice; no double settlement (each leg's copied payments belong to that leg's entity) |
| AD-04 | Existing `LicenseTradePayment` rows are **linked** (`Payment.trade_payment`, unique) and accounted once against a chosen bank account. New payments and receipts are accounting `Payment` documents. | Link, never recreate |
| AD-05 | **GST: none on trade-linked invoices**. This matches the existing Bill of Supply (HSN 4907) and the absence of tax fields on trades. Standalone bills (expenses, commission, notes) take the GST rate per line, split CGST/SGST or IGST from GSTIN state codes. **TDS: no rates seeded.** `TdsSection` is dated configuration with thresholds (FULL/EXCESS), PAN category and lower-deduction certificates. | Statutory treatment stays configurable. **Open for CA confirmation (policy):** GST on licence sales; which TDS sections apply |
| AD-06 | "Post to books" is an explicit confirm → post action. A trade edited after posting shows as drift (`EXCEPTION`). Re-sync **reverses and re-posts** and never rewrites. Trades or trade payments with posted entries cannot be deleted (`on_delete` guard). Draft links are removed with the trade. | Existing trade APIs unchanged except: deleting a trade with posted accounting now fails (**API behaviour change, flagged**) |
| AD-07 | Roles `ACCOUNTS_VIEWER` / `ACCOUNTS_MANAGER` / `ACCOUNTS_APPROVER` (Django groups, migration 0003). Optional maker-checker per entity. Entity is a book dimension, not an access boundary (OD-04 kept). | Reuses `BaseRolePermission` pattern |
| AD-08 | A default Indian trading chart is seeded per entity on activation (ledgers only). The accountant can rename it or add accounts. | Idempotent; no parties seeded |
| P-1 | Inventory: **periodic method**. Purchases go to P&L under COGS, and closing stock is a journal (Dr Closing Stock / Cr Change in Stock). Nothing unsold is auto-expensed beyond the purchase account. A perpetual licence-cost method needs a CA decision. | Standard Tally-style; no invented costing |
| P-2 | Loan interest uses actual/365 on each day's closing balance, posted monthly, idempotent per period. A repayment accrues to the day before. Accrual stops at maturity or closure. | Configurable rate; compound option |

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| A Audit | Done (`docs/erp-accounting/00–05`) | commit `f950d8c3` |
| B/C Trade + invoice engine | Implemented + Tested | `services/invoices.py`; `tests/test_trade_accounting.py` |
| D Central accounting engine | Implemented + Tested | `services/posting.py`, migration 0002 triggers; `tests/test_posting_engine.py` |
| E Automatic trade accounting (exactly once) | Implemented + Tested (explicit post action, idempotent) | same |
| F Party ledgers & settlement | Implemented + Tested (bill-wise, advances, multi-bill, notes, TDS) | `services/payments.py` |
| G Entity-wise P&L | Implemented + Tested (P&L agrees with ledger) | `selectors/reports.py` |
| H Banking | Implemented + Tested (CSV/XLSX, dedupe, UTR→amount match, split/partial, suspense, reclass, BRS = 0 diff) | `services/banking.py`; `tests/test_banking.py` |
| I Reconciliation workbench | Backend done; UI pending | — |
| J Expenses/commission/loans | Implemented + Tested | `services/loans.py` |
| K Historical migration | Implemented + Tested on test DB (dry run, execute, reconcile, idempotent). **Not run on any real DB.** | `services/migration.py` |
| L/M Reports + consolidation | Implemented + Tested (TB, P&L, BS, CF, ageing, registers, TDS/GST, profitability, consolidation) | `selectors/reports.py` |
| N Licence protection | Not touched; accounting never reads/writes licence CIF | licence suites to run in gate |
| O Accountant workspace (UI) | **Next** | — |
| API | **Next** | — |

## Tests

- 2026-11-17 baseline: `apps/trade apps/accounts` 87 passed, 1 xfailed.
- `apps/accounting` 52 passed; `tests/architecture` 9 passed (accounting added to governed apps; edges accounting→core/trade/accounts).

## Known limits / approval blockers

- PDF statement import is not supported (refused with guidance). CSV and XLSX are supported.
- GST on licence trades and the applicable TDS sections need CA confirmation (AD-05).
- Production migration execution needs owner approval plus a sanitised snapshot rehearsal (OD-17).
- Merging into `feature/v5` and any push need owner approval.

## Next exact action

Build the DRF API (`apps/accounting/api`, `/api/accounting/…`, `AccountingPermission`), then the frontend accountant
workspace (`/accounting/*`), then run the gates.
