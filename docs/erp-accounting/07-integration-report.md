# 07 — Accounting integration into `feature/v5`: final report (2026-11-17)

Verified results are marked **[V]** (a command ran and its output is quoted). Everything else is labelled.
Nothing has been pushed or deployed. No production database was touched.

## 1. Commits

| Source (`docs/erp-accounting-audit`) | On `feature/v5` | Content |
|---|---|---|
| `f950d8c3` | `706af329` | Phase Zero audit, design, ADR-004 (docs) |
| `a1b15bf6` | `411642b9` | Engine, trade posting, banking, loans, reports, migration center |
| `813be5eb` | `1e124b66` | REST API + `AccountingPermission` |
| `f051c9ad` | `7f6dfdaa` | Frontend workspace. The `TopNav.tsx` conflict was resolved in favour of the canonical nav: the Accounting group lives in `navigation/navConfig.ts` |
| `213a9669` | `acfde967` | Review round 1 fixes (H1–H5, M1–M8) |
| — | follow-ups (§3) | Review round 2 fixes, frontend fixes, real-backend E2E, docs |

Integration method: `cherry-pick --no-commit` + `git commit -C <sha> --only -- <paths>`. The accounting trees on
`feature/v5` are byte-identical to the source branch **[V]** (`git diff --quiet`). The peer's staged `.idea` entry and
all unstaged/untracked peer files were left untouched.

## 2. Reviews (four independent agents + one ERP auditor scenario run)

| Review | Critical | High | Medium | Low | Status |
|---|---|---|---|---|---|
| ERP/CA audit (32 own scenarios; 13 pass / 19 fail at start) | 2 | 4 | 9 | 5 | C1, H1–H4 and M1–M9 fixed. C2 mitigated (below). After the fixes the auditor's own scenarios give **29 pass / 3 fail [V]**; the 3 failures are explained below |
| Database / migrations | 0 | 0 | 3 | several | Fixed: voucher lock when matching; IntegrityError → clean error; 0004 freezes the audit columns of posted vouchers; N+1 removed (batch outstanding, pooled book side) |
| Frontend UI/UX | 0 | 5 | 5 | many | Fixed: dead banking links, entity-switch draft leakage, LineMatcher key, confirmations, double-submit, partial-failure refresh, Setup entity keying, pagination/FY, ARIA combobox, responsive tables |
| Security / permissions / audit | 0 | 0 | 2 | 6 | Fixed: maker-checker now covers bills and reversals; upload size/row/zip-bomb guards; no raw DB errors; audit of book-setting changes / FY open / disbursement; `as_int` on filters |

Remaining after the fixes (deliberate; reasons given):

- **C2 unrealised intercompany profit in closing stock.** It cannot be derived from periodic-method books. The
  consolidated report now **warns**, and it takes an accountant-entered **stock reserve** that reduces group GP and
  inventory. An automatic computation needs a perpetual costing policy (CA decision P-1). The auditor's scenario still
  fails because it expects automatic elimination.
- **Auditor "bounced cheque" scenario.** It asserts that a *fully matched* deposit line still has candidates. The
  behaviour is correct: the return line matches the reversal voucher and the BRS stays at 0 before and after; this
  is covered by `test_bounced_cheque_reconciles_and_past_brs_is_stable`.
- **Auditor "on-account suspense" scenario.** It expects a later bill to settle with no allocation step. Allocation is
  an explicit, audited action through the new `POST /vouchers/<id>/allocate/` / `allocate_on_account` service.
- **Deferred low items:** list pages still use the local `DataGrid` rather than the TanStack `DataTable` (a moderate
  refactor; not a defect); payment posting has no draft stage, so maker-checker does not apply to it (documented);
  viewers see full bank account numbers; opening-stock reversal in FY2 is manual (P-1); loan interest stops at
  maturity even if principal is overdue (P-2).

## 3. Files and migrations

- Backend: `backend/apps/accounting/**` (new app); `accounts/permissions.py` (+`AccountingPermission`);
  `lmanagement/settings.py` (+app); `lmanagement/urls.py` (+include); `tests/architecture/test_architecture.py`
  (governed app; edges accounting→core/trade/accounts/license; seed writes pinned).
- Migrations (accounting only; **no other app's schema changed**):
  - `0001_initial`
  - `0002_ledger_integrity_triggers`
  - `0003_accounting_roles`
  - `0004_freeze_posted_voucher_audit_fields`
- Frontend:
  - `src/pages/accounting/**`, `src/api/accountingApi.ts`
  - `navigation/navConfig.ts` (+test), `routes/AppRoutes.tsx`, `routes/authorizationRoles.ts` (+test),
    `utils/roleConstants.ts`
  - `e2e/accounting.real.spec.ts`
- Scripts: `scripts/test/run_data_bearing_browser_e2e.sh`, which gains an optional `LM_E2E_SEED` (the default
  behaviour is unchanged).

## 4. Tests run (commands and actual results)

| Stage | Command (summary) | Result |
|---|---|---|
| Baseline `feature/v5` with peer working tree | `pytest apps tests` (TEST_DB_NAME isolated) | **3330 passed, 5 skipped, 1 xfailed [V]** |
| Focused, after each fix | `pytest apps/accounting/tests/<file>` | green before moving on [V] |
| Accounting feature | `pytest apps/accounting tests/architecture` | **99 passed [V]** (90 accounting + 9 architecture) |
| Full backend on the landing tree (feature/v5 @ `3ece31f0` + fixes) | `pytest apps tests --create-db` | **3419 passed, 1 xfailed, exit 0 [V]** — includes all licence/CIF, BOE, trade and reconciliation suites |
| Frontend | `tsc --noEmit`, `eslint .`, `vitest run`, `vite build` | **exit 0 / 0 errors (17 warnings) / 808 passed / built [V]** |
| Playwright — accounting, real backend, fresh `test_*` DB | `LM_E2E_SEED=seed_accounting_e2e run_data_bearing_browser_e2e.sh e2e/accounting.real.spec.ts` | **6/6 passed [V]** |
| Playwright — existing suite | `CI=1 playwright test` with accounting vs the pre-accounting snapshot `9fc44ad3` | **76 passed / 54 failed / 15 skipped vs 76 / 54 / 9 [V]**: the failures are identical and pre-existing (responsive screenshots, colour contrast); the +6 skipped are the opt-in real-backend specs |
| Lint (backend) | `ruff check`, `flake8`, `makemigrations --check` | clean [V] |

## 5. Database migration and historical data (local only)

The test ran on **`test_lm_upgrade_9b79`, a disposable copy** of the local dev DB (`pg_dump lmanagement | psql`). The
dev DB itself was only read.

- **Upgrade.** All 4 accounting migrations applied on top of existing data **[V]**.
- **Rollback.** `migrate accounting zero` removed every accounting table and trigger function (0 / 0 left); re-applying
  gave 4/4 OK **[V]**. The role groups are kept by design.
- **History.** 566 trades (Feb 2025 – Nov 2026), 0 trade payments.
  - Entities discovered from Trade: LABDHI MERCANTILE LLP (299 own-side documents) and LABDHI GLOBAL LLP (183). Books
    were started on 01-04-2024 for both.
  - Dry run: 482 READY / 0 needing review.
  - Execute: 482 migrated, 0 failed.
  - Re-execute: 482 skipped, voucher count unchanged (299 / 183); 0 duplicate trade invoices **[V]**.
  - Reconciliation: source = accounted in every FY for both entities, difference **0.00 [V]**.
  - Trial Balance, Balance Sheet and P&L agree with the ledger for every FY and entity **[V]**.
  - The other 84 trades are copied legs whose own side is a counterparty (e.g. Purplehub), so they are correctly not
    in the group's books.
- **Observations needing a CA decision.**
  - Global's 2024-25 / 2025-26 gross profit is negative because purchased stock is unsold and no closing-stock journal
    exists (periodic method, P-1).
  - The local data has no trade payments, so the payment migration path is proven by tests only.
  - **The copy database `test_lm_upgrade_9b79` still exists** (the owner declined its deletion). Drop it when it is
    no longer needed.

## 6. Outstanding owner/CA decisions

- **GST** on licence trades. Currently none, matching the Bill of Supply.
- **TDS:** which sections and rates apply; no rates are seeded.
- **Inventory costing:** periodic or perpetual (this decides automatic unrealised-profit elimination and FY2
  opening-stock handling).
- **Production:** historical posting on production, which first needs a sanitised snapshot rehearsal.
- **Release:** push/merge approval.

## 7. Release readiness

The work is locally integrated, tested and committed on `feature/v5`. It is **not release-ready for production
posting** until the CA decisions above are taken and a production-snapshot rehearsal is approved. The code is ready
for review and push approval.

## 8. UI/navigation readiness round and consolidation (2026-11-17, later)

**UI round** (`b5f0d3f8` on `feature/v5`):
- Actions are gated by role, mirroring `AccountingPermission`, so viewers and managers never see a button the API
  refuses.
- Breadcrumbs reuse the shared `ModuleWorkspace` `Breadcrumbs`. An "All Reports" menu item makes every report page
  highlight in the menu.
- **Bug fixed:** the workspace section, report and banking tabs used relative links that resolved under the splat
  route (for example `/accounting/reports/cash-flow/reports`). All workspace links are now absolute.
- Errors offer a Retry button. P&L detail rows now carry their line's sign.

Checks run **before** the owner's "no testing for now" instruction [V]:
- vitest 817 passed; tsc, eslint (0 errors) and build clean;
- real-backend Playwright 10/10, which includes desktop 1440, tablet 768 and mobile 390 layouts with no horizontal
  overflow on 8 major screens, viewer and trade-only access, breadcrumbs and active menu;
- existing navigation and shell specs 10/10.

Screenshots: `docs/erp-accounting/screenshots/` (24 files: desktop/tablet/mobile × dashboard, trades, payments,
banking workbench, trial balance, P&L, balance sheet, vouchers).

**Consolidation:** see `08-completion-inventory.md`. **No tests were run for the consolidation step itself.**
