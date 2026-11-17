# 05 — Phased implementation plan

Each phase is independently testable and mergeable, and each needs its listed owner decisions first. Each phase also
runs the backend (and, where touched, frontend) quality gates and a `cif-balance-auditor` check that licence
balances are unchanged (prompt test 20).

| Phase | Scope | Needs | Exit tests (prompt §18 numbers) |
|---|---|---|---|
| **A1 Foundation** | `apps/accounting`: LegalEntity, FY, Period, AccountGroup, Account, VoucherType, VoucherSequence, Voucher, VoucherLine, AuditEvent. Services `create_draft`, `approve`, `post`, `reverse`, `lock_period`. Balanced-voucher DB trigger + immutability trigger. CoA seed command (per entity, from a CSV the CA supplies). Read APIs: accounts, vouchers, GL, trial balance. `AccountingPermission` + roles. **No trade integration.** | AD-01, AD-07, AD-08 | 1, 16, 23, 24, 25; idempotent seed; numbering gap-free under concurrency; architecture ratchets green |
| A2 Opening balances | OPN voucher import, BillReference for open items, cut-over reconciliation report | AD-02, production snapshot (OD-17) | no duplicate opening balance; Σ open bills = party OPN |
| **B1 Trade posting** | Trade selectors; PostingRule + outbox; "Post to books" action; posting for PURCHASE/SALE/COMMISSION_*; pair classification; posted-trade delete guard + drift report | AD-03, AD-05 (GST = 0 baseline), AD-06 | 2, 3, 7, 20, 21, 22 |
| B2 TDS + settlements | TDS config (sections, dated rates, thresholds, PAN, LDC); Payment/Receipt vouchers; bill-wise allocation; advances; statuses PAID/PARTIAL/UNPAID/OVERDUE/SETTLED; party ledger + statement + ageing APIs | AD-04, AD-05 | 4, 5, 6, 8 |
| C Banking | BankAccount (own), statement import (CSV/Excel first; PDF later), normalisation, duplicate detection, matching (UTR → reference → amount+party → narration), split match, suspense register + reclassification, BRS | — | 9, 10 |
| D1 Expenses & commission | Expense documents (independent or trade-linked), categories, cost centres, approval, GST/TDS, commission registers | GST rules for services (AD-05) | 11 |
| D2 Loans | Loan master, schedules, accrual engine (Celery beat), repayments, restructuring, closure | interest conventions (CA) | 12, 13, 14, 15 |
| E Reporting | P&L, Balance Sheet, Cash Flow (indirect), registers, ageing, trade profitability from the GL (allocation by value/qty/weight), consolidation with intercompany elimination; Excel/PDF on the server; drill-down | — | 16, 17, 18, 19 |
| F Controls | GST registers/returns prep, TDS returns prep, period close checklist, tax reconciliation | CA | statutory register tie-outs |
| G UI | Accounting/Banking/Tax/Reports menus in the nav-redesign `navConfig.ts`; voucher entry (keyboard-first), GL/party drill-down, reconciliation workbench, dashboards. Reuse DataTable/useListQuery/FilterPanel. Money stays Decimal strings | nav-redesign merged | Vitest + Playwright per screen |

## Proposed first increment (A1) — detail, for approval

- **Files (new only):**
  - `backend/apps/accounting/{apps.py, models/, services/, selectors/, domain/, api/, migrations/0001…, management/commands/seed_chart_of_accounts.py, tests/}`.
  - One `INSTALLED_APPS` entry and one `urls.py` include.
  - `AccountingPermission` in `accounts/permissions.py`.
  - A data migration that creates the 3 role groups (additive).
- **Not touched:** trade, license, BOE, allotment, reconciliation, MDS and frontend.
- **Migrations:** purely additive new tables and triggers. They are reversible (the triggers have a reverse SQL
  step). There is no data backfill.
- **Tests (pytest-django):**
  - an unbalanced post is rejected, both by the service and by the raw-SQL trigger;
  - a posted voucher is immutable, and reversal produces exact negating lines that link back to the original;
  - a locked period rejects posting;
  - concurrent posts get unique, consecutive numbers;
  - a non-approver gets 403 and maker = checker is refused;
  - the trial balance totals match;
  - seeding the CoA twice is idempotent;
  - plus a query-count test on the GL read endpoints (ARCHITECTURE_RULES 6).
- **Size estimate:** about 1.5–2.5k lines of backend code and tests (inferred).

**Start condition:** the owner answers AD-01, AD-07 and AD-08 (and accepts ADR-004). Until then this plan is a
proposal only.
