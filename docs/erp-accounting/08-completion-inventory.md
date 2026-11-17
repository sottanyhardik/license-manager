# 08 — Completion inventory (consolidation into `feature/v5`, 2026-11-17)

How this was produced: each item below was checked against the code on `feature/v5` (apps, routes, services and
screens), not against earlier documents. **No tests were run for this consolidation**; the test evidence cited comes
from the earlier integration rounds, which `07-integration-report.md` records with commands and exit codes.

Legend:
- **COMPLETED**: implemented and wired end to end (model → service → API → screen).
- **DEFERRED — NOT YET IMPLEMENTED**: missing, or only partly built.
- **BLOCKED**: needs a business or owner decision.

## A. COMPLETED

### Existing modules (preserved, not rebuilt)
- **Licence management:** licences, items, balance engine, CIF ledger, planning, reports. The accounting work makes
  no change to licence or CIF code.
- **Trade management:** trades, lines, payments, invoice documents, pairing.
  - Accounting adds only `on_delete` guards on its own FKs, plus one consolidated trade fix (list ordering, below).
- **BOE modernization:** integrated by the BOE session (see its checkpoint in `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md`).

### Accounting backend (`backend/apps/accounting`)
- **Entities:** discovered from Trade (`selectors/entities.py`). Books are keyed on the existing company id (no
  second master). FY and monthly periods, with period locks.
- **Chart of accounts:** default Indian trading chart, per entity, ledgers only; the accountant can add and rename
  ledgers.
- **Posting engine:** one engine for everything, with balanced, idempotent, gap-free numbering, reversal, manual
  drafts and maker-checker. Postgres triggers (migrations 0002, 0004) make posted vouchers immutable.
- **Trade → invoice → voucher:** exactly once. A trade edited after posting is re-synced by reversal plus re-post. A
  trade or trade payment with posted entries cannot be deleted. Intercompany pairs post in each entity's own books.
- **Standalone documents:** bills, expenses, commission, and debit/credit notes. GST CGST/SGST/IGST split per line;
  dated TDS sections (FULL/EXCESS threshold, catch-up, lower-deduction certificate with limit); allocation of
  expenses across trades.
- **Payments and receipts:**
  - bill-wise allocation, advances, on-account allocation, customer TDS;
  - existing trade payments are linked, never duplicated (`possible_duplicate` guard).
- **Banking:**
  - bank accounts; CSV/XLSX import with dedupe;
  - UTR → exact-amount auto-match (never posts); manual, split and partial matching with history;
  - suspense and reclassification, resolve-by-match;
  - bounced-cheque handling; bank reconciliation statement (also as of a past date).
- **Loans:** given and taken; principal and interest in separate ledgers; daily-balance accrual; repayment with
  true-up; closure.
- **Reports from the ledger:** Trial Balance, P&L (and monthly), Balance Sheet, Cash Flow (direct), General Ledger,
  party ledger, receivables/payables ageing, registers, GST and TDS registers, trade profitability, bank and cash
  book, consolidation (intercompany elimination within the group; stock-reserve input with a warning).
- **Historical migration center:** dry run, confirmed execute, idempotent re-run, FY reconciliation.
- **REST API** `/api/accounting/…`, role-gated by `AccountingPermission`:
  - viewer: read;
  - manager: draft, confirm, match, upload;
  - approver: post, reverse, payments, suspense, loans, migration, setup.
- **E2E seed command** `seed_accounting_e2e` (refuses any non-`test_*` database).

### Accounting frontend (`frontend/src/pages/accounting`, route `/accounting/*`)
- **Navigation:**
  - an "Accounting" group in the main navigation (`navigation/navConfig.ts`): Books / Banking / Reports & setup
    sections, gated by `ACCOUNTING_ROLES`;
  - active-item highlighting; breadcrumbs reusing the shared `ModuleWorkspace` `Breadcrumbs`;
  - in-workspace section tabs.
- **Entity and financial-year selectors:** switching remounts every page, so drafts never leak across entities.
- **Screens:**
  - Dashboard, Trade → Invoice tracking, Bills & Expenses (list/detail/new), Payments (record + allocation), Vouchers
    (list/detail/new journal, reverse, on-account allocation), Party Ledger;
  - Banking: accounts, statement upload, workbench with candidates and split, suspense, BRS;
  - Reports: 14 tabs with drill-down to the general ledger and then the voucher;
  - Loans, Migration Center, Setup (books, periods, chart, TDS).
- **UX behaviour:**
  - confirmation dialogs (the existing `useConfirmDialog`) on every financial action;
  - role-gated buttons with read-only notes; loading, empty and error states with Retry;
  - an ARIA combobox for parties; responsive tables;
  - money kept as Decimal strings throughout.

### Consolidated in this pass
| Source | New commit | What |
|---|---|---|
| `acct-ui` worktree `862755a7` | `b5f0d3f8` | Accounting UI/navigation readiness: role gating, breadcrumbs, absolute links (fixes broken section tabs on deep pages), Retry, P&L detail sign, viewport e2e + screenshots |
| `fix/trades-list-ordering` `bdf613ee` | `1efb04bf` | Deterministic nulls-last trades list ordering + regression test file (complete, small, no API change) |
| `docs/t2f-lifecycle-audit` `d5ca8fa1` | `18f62820` | Trade-to-finance lifecycle audit (docs) |
| `feature/erp-implementation` docs (`e6dfc9b7` tree) | this commit | `docs/erp-transformation/*` and `docs/security/OD-06-exposure-assessment.md`, docs only, with a provenance note |

Earlier accounting commits already on `feature/v5`:
`706af329`, `411642b9`, `1e124b66`, `7f6dfdaa`, `acfde967`, `fc8049ba`, `121a9653`, `73ecb37b`, `43131b80`.

## B. INCOMPLETE — DEFERRED — NOT YET IMPLEMENTED

| Item | State in code | Next step |
|---|---|---|
| Excel/PDF export of accounting reports | No export endpoint or button (the licence modules have server-side exports) | Add server-side XLSX export per report, reusing the existing exporter pattern |
| PDF bank statement import | Refused with guidance; CSV/XLSX only | Add a bank-specific PDF parser per bank format |
| Opening-balance import (trial balance + open bills) | Only a manual OPENING journal; no bulk import screen | Add an upload of the CA trial balance and open bills, posted through `post_voucher` |
| Scheduled monthly interest accrual | `loans.accrue_month_end()` exists; no Celery beat entry | Add a beat schedule entry |
| EMI repayment schedule | Only the `emi_amount()` helper; no schedule table or screen | Add schedule generation + screen |
| Cost-centre and trade filters on P&L/TB | Cost centres are stored on lines; reports don't filter by them | Add `cost_centre`/`trade` query params to the report selectors and UI |
| GST/TDS return preparation (GSTR-1/3B, 26Q/27Q) | Registers only | Build return-format exports |
| Accounting status inside the Trade screens | Status shown only in the accounting workspace | Add a read-only badge on the trade form/list (additive API field) |
| Main app dashboard financial overview | Not added (accounting has its own dashboard) | Add accounting KPI cards to `pages/Dashboard.tsx` for accounting roles |
| Command-palette entries for accounting screens | Not added | Add the accounting routes to `routes/config.ts` |
| Table sorting / shared `DataTable` on accounting lists | Local `DataGrid`, no column sort | Migrate list pages to `components/data-table/DataTable` + `useListQuery` |
| Maker-checker for payments | Payments post directly (no draft) | Add a draft → approve flow when the flag is on |
| Masking bank account numbers for viewers | Full numbers shown | Mask in `present.bank_dict` for non-approvers |
| ERP OD-program code (`feature/erp-implementation`, Nov 15–16): OD-10 `trade_running_balance`, OD-09 CI gates (drf-spectacular, pip-audit), OD-21 pivot fix, 5 stale licence-test fixes | **Not consolidated.** It forked from an older base and rewrites protected licence-balance code; `feature/v5` already has its own OD-01 signed-balance implementation | Reviewed port, commit by commit, with a `cif-balance-auditor` review (CLAUDE.md §2) |
| `feature/v5-throttle-retry` (`9ddc85cb`, status-aware 429 retry) | **Not consolidated.** It competes with `feature/v5`'s own 429 policy in `api/queryClient.ts` (would replace it) | Owner/frontend decision on which retry policy to keep, then merge one |
| Uncommitted WIP in other worktrees (`lm-impl-*`, `license-manager-implementation`, `T-009/013/022`, `boe-erp`, `/private/tmp/lm_a1_wt`) and in the shared checkout | Left untouched (other sessions' unreviewed work) | Each owning session reviews, commits or discards |

## C. BLOCKED — NEEDS BUSINESS DECISION

| Decision | Impact |
|---|---|
| GST treatment of licence (HSN 4907) trades; currently none (Bill of Supply) | Output/input GST on trade invoices |
| Which TDS sections and rates apply (none seeded) | TDS on purchases, commission, expenses |
| Inventory costing: periodic (current) vs perpetual | Closing-stock automation, FY2 opening stock, automatic elimination of unrealised intercompany profit (today: warning + manual reserve) |
| Historical posting on production | Needs a sanitised-snapshot rehearsal and approval (rehearsed locally on a copy: 482 trades, 0 differences) |
| Per-user entity access control | OD-04 keeps the system single-tenant; any accounting role sees all entities |

## Testing deliberately deferred for this consolidation
Not run: unit, integration, API, frontend, Playwright and quality gates. The three consolidated commits were tested in
their own sessions (UI round: vitest 817, tsc/eslint/build, real-backend Playwright 10/10, nav specs 10/10; trades
ordering fix: regression test file included). The next step is to run the backend and frontend gates once on
`feature/v5`.
