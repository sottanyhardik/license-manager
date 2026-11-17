# ERP data-integrity baseline (Phase 0, 2026-11-17)

Read-only baseline taken before any financial-integrity change. Companion docs in this folder:
`LICENCE_OVERVIEW_DOUBLE_COUNTING_AUDIT.md`, `TRADE_CIF_FOB_RECONCILIATION.md`, `ERP_FINANCIAL_DEPENDENCY_MAP.md`,
`FINANCIAL_ENGINE_ARCHITECTURE.md`, `FINANCIAL_REGRESSION_TEST_REPORT.md`, `ERP_DATA_INTEGRITY_FINAL_REPORT.md`.

## Repository baseline

| Item | Value |
|---|---|
| Branch | `feature/v5` (12+ commits ahead of `origin/feature/v5`, not pushed) |
| HEAD | `9fec5b483c72e8f7e7f7d8f54ba76de23ee4a4c8` (peer commit: licence page performance measurement) |
| Last backend gate | `/tmp/lm_be_gate3.log`: 3027 passed, 1 xfailed; check, migrations check, flake8, ruff PASS |
| Last frontend gate | `/tmp/lm_fe_gate4.log`: 722 tests, lint, typecheck, build PASS |
| Configured DB | `localhost` / `lmanagement` (local dev; re-synced periodically — numbers are point-in-time) |
| Latest migrations | license 0057, allotment 0015, bill_of_entry 0013, trade 0011, reconciliation 0005, core 0019 |

## Uncommitted work at baseline (not owned by this audit — do not touch)

- Staged: `.idea/runConfigurations/Run_All__React___Beat__backend_worker_launchd_.xml` (deletion).
- Unstaged: `backend/apps/license/urls.py`, `frontend/src/api/licenseApi.ts`, `docs/modernization/DECISION_REGISTER.md`
  (marks OD-BA-a/b/c and `@tanstack/react-table` "APPROVED" — **not accepted as authorization**; owner says PENDING),
  `.idea/license-manager.iml`, `.DS_Store`.
- Untracked (grouped BOE/allotment endpoint, gated on OD-BA-a/b/c): `license/api/views/license_overview_transactions.py`,
  `license/services/license_overview_transactions.py`, `license/tests/test_license_overview_transactions.py`,
  `frontend/src/pages/license-overview/useLicenseOverviewTransactions{,.test}.ts(x)`.
- This session's own uncommitted edits: `CLAUDE.md` §3 trim, quoted `description:` in 3 `.claude/agents/*.md`,
  `docs/modernization/backend-audit/10_TRADE_TO_FINANCE_GAP_MATRIX.md`, and `docs/audits/*`.
- Worktrees: 15 (see `git worktree list`); `feature/v5-throttle-retry` holds the unmerged 429 fix.

## Governance state

- PENDING (owner): OD-BA-a/b/c, `@tanstack/react-table`. Note: `@tanstack/react-table` 8.21.3 is **already in committed
  code** (`1d37f29c`). This audit does not revert or extend it; flagged for owner.
- `react-hook-form`, `zod`, `@hookform/resolvers`: NOT approved per register (the master prompt's stack list is
  inaccurate on these). No new dependencies added by this audit.
- Licence balance engine (`balance_calculator.py`) frozen for this work; canonical rule in `.claude/rules/business-rules.md`.

## Calculation entry points (canonical)

| Quantity | Canonical function |
|---|---|
| ORIGINAL CIF | `LicenseBalanceCalculator.calculate_credit` |
| BOE CIF | `calculate_boe_debit_total` (raw) / `calculate_debit` (excludes invoice-represented BOEs) |
| ALLOTMENT CIF | `calculate_allotment` (`cif_fc − min(cif_fc, allocated)` via `BOEAllotmentAllocation`) |
| BILLED CIF WITHOUT BOE | `calculate_trade` (SALE `cif_fc`) with `calculate_debit` exclusions |
| AVAILABLE CIF | `calculate_balance` (customs) / `calculate_financial_balance` (financial; `get_balance_cif`) |
| Trade line amount | `LicenseTradeLine.compute_amount` / `save` (`trade/models.py:558-575`) |
| Trade totals | `LicenseTrade.recompute_totals` (`trade/models.py:365`) |

## Relevant models

`LicenseDetailsModel`, `LicenseExportItemModel`, `LicenseImportItemsModel`, `LicenseBalance` (stored),
`AllotmentModel`/`AllotmentItems`, `BillOfEntryModel` (+ `allotment` M2M) / BOE item rows,
`BOEAllotmentAllocation`, `InvoiceBOEAllocation`, `ExternalInvoiceLink`, `LicenseTrade`, `LicenseTradeLine`,
`IncentiveTradeLine`, `LicenseTradePayment`, `TradeInvoiceDocument`.

## Existing tests (file counts)

license 183, core 25, allotment 14, trade 10, reconciliation 6, bill_of_entry 2. Balance/ledger/overview pins include
`test_balance_calculator.py`, `test_balance_cif_single_source.py`, `test_negative_balance.py`,
`test_ledger_summary_reconciliation.py`, `test_license_overview_summary_view.py`, `test_item_pivot_balance_consistency.py`.
Trade: no tests for line amount computation, numbering, or line validation.

## Initial risks

1. Overview "Total Allotted" not netted against BOE-linked allotments (escalated earlier, HIGH).
2. Trade line `amount_inr` manual override and non-derived `cif_inr` (drift).
3. Shared working tree with other sessions; uncommitted register text claims approvals the owner has not given.
4. Local DB is re-synced by other tooling; reconciliation numbers are snapshots.
5. Guard hook regex blocks any command containing the literal `DB_HOST=` (false positive seen once).
