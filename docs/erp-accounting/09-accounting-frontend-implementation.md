# 09 — Accounting frontend implementation (2026-11-17)

Scope: make the accounting engine that already exists usable through one coherent workspace at `/accounting/*`.
The posting engine, report selectors, permissions and entity model are reused unchanged. **No tests were run in this
round** (owner methodology: feature-first, then one coordinated testing phase). Only the TypeScript typecheck
(`tsc --noEmit`, exit 0), ESLint on the changed files (0 errors, 6 fast-refresh warnings) and `py_compile` ran.

Statuses: **COMPLETED** = implemented, not tested · **IN PROGRESS** · **DEFERRED** · **BLOCKED**.

## 1. Backend functionality found (inspected in code)

- `apps/accounting/urls.py` has about 40 endpoints: entities and FY/periods, accounts, cost centres, parties (company
  master), vouchers (list, draft create, post, reverse, allocate, delete draft), invoices, payments, trade tracking,
  TDS/LDC, audit, banking (accounts, statement upload, lines, auto-match, candidates, manual match, unmatch, BRS,
  suspense), reports (TB, P&L, monthly P&L, BS, cash flow, GL, party ledger, ageing, registers, GST, TDS, trade
  profitability, suspense, loans, bank/cash book, dashboard, consolidated), loans and migration.
- Permissions: `AccountingPermission`. Viewer reads; `AccountingView` writes need the write level (manager);
  `ApproverView` writes need the approve level. Reads are allowed for every accounting role.
- Posted vouchers are immutable (Postgres triggers 0002/0004). Only manual drafts (JOURNAL/CONTRA/OPENING/ADJUSTMENT)
  are entered by hand. Payment, receipt, sales and purchase vouchers are created only by their documents.

## 2. Backend additions (needed by the screens; additive API)

| Change | Where | Status |
|---|---|---|
| Edit a manual draft: `PATCH accounting/vouchers/<id>/` (header + full line set). Refused for posted and document vouchers. The editor becomes the maker, so maker-checker still holds | `services/posting.py update_draft`, `api/views.py VoucherDetailView.patch` | COMPLETED |
| Party summary: `GET accounting/parties/summary/?entity&start&end[&search]`. Per party: GL ledger balance (from `balances_by_account`), open receivable/payable bills (from `ageing`), customer/supplier flags | `selectors/reports.py party_summary`, `api/views.py PartySummaryView`, `urls.py` | COMPLETED |
| Dashboard: additive `advances_paid` / `advances_received`. Same definition as `payments.unallocated` (party amount − active settlements) | `selectors/reports.py unallocated_advances` | COMPLETED |
| Statement-line search also matches `reference` (UTR / cheque no.) | `api/views_banking.py` | COMPLETED |
| Tests for the above | `tests/test_frontend_support_api.py` | COMPLETED (written, **not run**) |

No migrations. No change to posting rules, balances or permissions. No new calculation: the summary and advances
reuse existing selectors and the existing `unallocated` definition.

## 3. Navigation and routes

One source, `frontend/src/pages/accounting/sections.ts`, drives the workspace group tabs, each group's sub-navigation
and the breadcrumbs (longest-prefix match). The main sidebar (`components/navigation/navConfig.ts`) mirrors it in
five sections. Every entry is a real route; no placeholder screens.

| Group | Pages (route under `/accounting/`) |
|---|---|
| Dashboard | `dashboard` |
| Masters | `masters/accounts`, `masters/groups`, `masters/parties`, `masters/parties/:id` |
| Transactions | `vouchers`, `vouchers/{journal,payment,receipt,contra,sales,purchase}`, `vouchers/new[?type=]`, `vouchers/:id`, `vouchers/:id/edit`, `payments`, `trades` |
| Ledgers | `reports/general-ledger`, `party-ledger`, `ledgers/customers`, `ledgers/suppliers` |
| Banking | `banking`, `banking/transactions[/:bank]`, `banking/unmatched[/:bank]`, `banking/reconciliation[/:bank]`, `banking/suspense`, `banking/workbench[/:bank]` (kept) |
| Expenses & Income | `invoices` (bills & expenses), `reports/register/{expense,sales,purchase,commission,notes}`, `loans` |
| Reports | `reports/{trial-balance,profit-loss,balance-sheet,cash-flow,party-outstanding,receivables-ageing,payables-ageing,cash-book,bank-book,voucher-register,register,gst,tds,trade-profitability}` |
| Entity-wise | `entities`, `reports/consolidated` |
| Setup | `setup`, `migration` |

The old in-page tab bars (Reports, Banking) were removed; the workspace sub-navigation replaces them. The old URLs
keep working (`reports/register?kind=`, `banking/workbench`).

## 4. Entity and financial year

- The entity selector lists the active `EntityBooks` (pk = the existing company id; no second entity master).
  Switching entity remounts every page (the routes are keyed by entity), so drafts never leak between entities' books.
- New: a **From / To date range** inside the selected FY (clamped to the FY; "Whole FY" resets it; not persisted).
  `scope` now always sends `start`/`end` rather than `fy`. The API's `period_from()` prefers `?fy=` and needs the FY
  opened; with start/end, screens also work for an FY that hasn't been opened yet. All report, ledger, list and
  dashboard query keys include both dates.
- Consolidated reporting stays a separate screen. The Entity-wise page shows each entity's own books side by side and
  never adds them together.

## 5. Screens

| Screen | API | Status |
|---|---|---|
| Dashboard: income, purchases, gross/net profit, bank, cash, receivables/payables (+overdue), **advances paid/received**, draft vouchers, unposted bills, unmatched bank lines, suspense, GST/TDS, loans; **recent vouchers**; **recent activity** (audit); link to entity-wise. All cards drill down | `reports/dashboard/`, `vouchers/`, `audit/` | COMPLETED |
| Chart of Accounts: search; group, kind and status filters; classification; opening/closing balance for the period (from TB); add ledger (General/Tax), rename, activate/deactivate (system ledgers protected) with confirmation; "Enter opening balances" opens an OPENING voucher | `accounts/`, `accounts/<id>/`, `reports/trial-balance/` | COMPLETED |
| Account Groups: code, nature, report head, ledger count (links to the filtered chart) | `accounts/` | COMPLETED (read-only: no group API) |
| Parties: search; customer/supplier filter; "only with a balance"; ledger balance Dr/Cr, receivable, payable, open bills; server totals | `parties/summary/` | COMPLETED |
| Party detail: summary, full ledger with running balance, bill-wise outstanding | `parties/summary/`, `reports/party-ledger/` | COMPLETED |
| Customer / Supplier ledgers: party list fixed to one side, opening each party's ledger | `parties/summary/` | COMPLETED |
| Vouchers: all + typed books (journal, payment, receipt, contra, sales, purchase); search, status filter, pagination; detail with Dr/Cr totals, audit, post, reverse, delete draft, **edit draft**; manual form with live balance/difference and validation messages | `vouchers/…` | COMPLETED |
| Ledgers: General ledger (any account; opening, running and closing balance), party ledger | `reports/general-ledger/`, `reports/party-ledger/` | COMPLETED (existing, now date-range aware) |
| Banking: accounts; **transactions** (upload, all lines, UTR/reference search, date window); **unmatched** (needs-attention queue, every open line regardless of date); **reconciliation** (BRS as of a date); suspense; the combined workbench is kept | `bank-accounts/…`, `statement-lines/…`, `suspense/…` | COMPLETED |
| Expenses & Income: bills & expenses; expense, sales (income), purchase, commission and notes registers; loans | `invoices/`, `reports/register/` | COMPLETED |
| Reports: TB, P&L, BS, cash flow, **party outstanding**, ageing, cash/bank book, **voucher register**, registers, GST, TDS, trade profitability; drill-down to GL → voucher | `reports/<name>/`, `parties/summary/`, `vouchers/` | COMPLETED |
| Entity-wise summary (per-entity dashboard figures) | `reports/dashboard/` × entities | COMPLETED |
| Setup: the chart editor was moved to Masters (Setup links to it; no duplicate editor) | — | COMPLETED |

Money stays as Decimal strings. The client only formats values and sums the form's own lines (BigInt paise), as
before; no accounting figure is computed in JavaScript.

## 6. Incomplete / deferred

| Item | Why | Status |
|---|---|---|
| Account group create/regroup | No API (`masters` service has none) | DEFERRED |
| Voucher attachments | `Voucher.attachment` exists; there is no upload endpoint | DEFERRED |
| Tally connector | Not implemented (see `docs/tally-erp/INTEGRATION_STATUS.md`); no screen is shown for it | DEFERRED |
| Report export (Excel/PDF) and column sort | As in inventory 08 §B | DEFERRED |
| Party detail by URL in `party-ledger` (`?party=`) | Party detail under Masters covers it | DEFERRED |
| GST/TDS return formats | Registers only | DEFERRED |

## 7. Known issues (not yet verified by tests)

1. `parties/summary/` lists only parties that already have a ledger account (created when a document posts). A
   company with no posted document does not appear (by design; the PartyPicker still finds it).
2. The entity-wise page sends one dashboard request per entity (fine for a handful of entities; there is no batch API).
3. Group-tab and sub-tab both carry `aria-current="page"` (in separate, labelled nav landmarks).
4. Unmatched / workbench queues ignore the date window on purpose (old open lines must stay visible); Bank
   Transactions applies it.
5. `test_frontend_support_api.py` and the extended e2e route list have never been executed.

## 8. Deferred testing (for the coordinated testing phase)

- Backend: `apps/accounting/tests` (incl. the new file) + the architecture ratchet + `scripts/dev/quality-gate.sh backend`.
- Frontend: vitest (`AccountingWorkspace.test.tsx`, `navConfig.test.ts` updated for the new IA), `npm run lint`,
  `npm run build`, then `e2e/accounting.real.spec.ts` (19 more routes) at 1440/768/390.
- Manual: draft edit under maker-checker, entity switch with a narrowed date range, party summary totals against TB.

## 9. Next implementation tasks

1. Voucher attachment upload (endpoint + detail panel).
2. Report exports (XLSX) reusing the existing exporter pattern.
3. Account group API + UI, if the CA wants custom groups.
4. Shared `DataTable` with column sort on the long lists.
