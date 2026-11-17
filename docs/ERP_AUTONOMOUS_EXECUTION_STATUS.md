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
| I Reconciliation workbench | Implemented + Tested (API + UI: upload, auto/manual/split match, unmatch, suspense, BRS) | `api/views_banking.py`, `frontend/src/pages/accounting/Banking.tsx` |
| J Expenses/commission/loans | Implemented + Tested | `services/loans.py`, `services/invoices.py` |
| K Historical migration | Implemented + Tested on the test DB (dry run, execute, reconcile, idempotent). **Not run on any real DB.** | `services/migration.py`, Migration Center UI |
| L/M Reports + consolidation | Implemented + Tested | `selectors/reports.py`, Reports UI |
| N Licence protection | No licence code changed. Full `apps/` suite incl. licence/CIF regression green | see Tests |
| O Accountant workspace (UI) | Implemented + Tested (vitest smoke + money unit tests; tsc + build pass) | `frontend/src/pages/accounting/*` |
| API | Implemented + Tested (permissions, Decimal strings, HTTP workflow) | `apps/accounting/api/*`, `urls.py` |
| P Independent review | 5 high + 8 medium findings **fixed with regression tests** (`tests/test_review_regressions.py`) | see below |

## Independent review (2026-11-17) — outcomes

| Finding | Fix |
|---|---|
| H1 a reversed debit/credit note left its settlement active | `reverse_invoice` deactivates the note's settlements |
| H2 the generic voucher reverse bypassed the document lifecycle | `reverse_manual_voucher`: only MANUAL/BANK_OPENING vouchers; document vouchers are reversed from their document |
| H3 suspense reclassification could over-allocate or settle the wrong direction | Σ allocations ≤ suspense amount; direction + party-ledger checks |
| H4 a contra between own banks could be matched on only one side | matched amount computed per bank account |
| H5 resync kept the stale party/entity/kind | resync moves the bill to the corrected party/entity/kind (only when unsettled) |
| M1 a migration DB error aborted the run | per-record `DatabaseError` → FAILED with reason |
| M2 `trade_ids` did not scope payments | payments filtered by their trade |
| M3 identical same-day loan repayments merged | per-loan event sequence |
| M4 as-of ageing/BRS used later settlements/matches | as-of filters |
| M5 a reversed payment left its statement line MATCHED | line status refreshed |
| M6 cash flow pro-rata was inexact | exact direct method (each counter-line contributes −its net) |
| M7 TDS threshold fixed at draft time | TDS recomputed at posting under the invoice lock |
| M8 resync compared settled vs gross | compares vs the recomputed net (rolls back otherwise) |
| Low | zero-weight allocation → 400; period row lock vs posting race; reversal in a locked period → today; dashboard overdue = everything past due |
| Open (low) | resolved suspense can't be re-opened; no guard against booking customer TDS both on the bill and on the receipt; per-user entity scoping (any accounting role sees all entities, consistent with OD-04) |

## Tests (2026-11-17, local Postgres 18, isolated test DBs)

- Baseline before changes: `apps/trade apps/accounts` 87 passed, 1 xfailed.
- Full backend after the engine/API/UI commits: `pytest apps` **3065 passed, 1 xfailed** (incl. all licence/CIF suites);
  `pytest tests` **246 passed**.
- After the review fixes: `apps/accounting` **69 passed**, `tests/architecture` **9 passed**; flake8, ruff, `makemigrations --check`
  clean.
- Frontend: `vitest run` all suites pass (726 + 2 new accounting tests); `tsc --noEmit` clean; `eslint` 0 errors (3 fast-refresh
  warnings); `vite build` OK. Playwright not run (no live backend/browser session in this job).

## Known limits / approval blockers

- PDF statement import is not supported (refused with guidance). CSV and XLSX are supported.
- **Policy (CA):** GST treatment of licence trades (currently none, matching the Bill of Supply); which TDS sections and rates apply;
  perpetual vs periodic inventory costing.
- **Approval:** executing the historical migration on production (rehearse on the sanitised snapshot OD-17 first); merging into
  `feature/v5` / pushing; changed trade DELETE behaviour for trades with posted accounting (now refused with 400).
- Navigation: one "Accounting" group was added to `TopNav.tsx`. The nav-redesign session must carry it into `navConfig.ts`.

## Next exact action

Owner: confirm the policy items above, then approve (a) cherry-picking this branch into `feature/v5` and (b) a migration dry run
on the sanitised snapshot. Engineering next: Playwright e2e for the purchase → bank reconciliation flow against a dev server;
resolve the open low-severity items.

## Integration into feature/v5 (2026-11-17)

Done. All five commits plus the follow-ups are on `feature/v5`. Report, tests and remaining decisions: `docs/erp-accounting/07-integration-report.md`.

---

# Workstream: BOE ERP modernization

Rules for every workstream in this file: `.claude/rules/autonomous-execution.md`. Each workstream keeps one
`CHECKPOINT:<name>` block below; `.claude/hooks/session_start.sh` prints every such block at session start.
The 2026-08-10 `docs/AUTONOMOUS_EXECUTION_STATUS.md` is a stale snapshot kept for history.

<!-- CHECKPOINT:accounting:BEGIN -->
**Accounting — last verified checkpoint (2026-11-17, second consolidation pass)**
- On `feature/v5`: engine, API, workspace and review fixes (`706af329` … `43131b80`), UI/navigation `644f800f`,
  trades ordering `f0344260`, t2f audit `f47b6337`, docs `a8073a21`. Second pass: T1–T4 pricing `89a2e030`
  (migration `trade/0012`), A-1 + M2M `7fad3583`, audit docs `6777aee4`, config `615c750e`, Tally status doc.
- Tally ERP: `docs/tally-erp/INTEGRATION_STATUS.md`. The in-app engine is the Tally replacement; there is NO Tally
  connector (DEFERRED). System of record and cut-over (D6/AD-02) are BLOCKED on the owner/CA.
- Inventory: `docs/erp-accounting/08-completion-inventory.md`. Report: `07-integration-report.md` §9.
- **No tests were run for either consolidation pass.** The last verified run is the UI round: vitest 817, Playwright 10/10.
- Next: run backend + frontend gates once on `feature/v5` (includes `trade/0012` on a local test DB). Then the deferred
  items: report exports, opening-balance import, accrual beat job, DataTable/sort, trade-screen accounting badge.
- IN PROGRESS, uncommitted in the shared checkout: A-2 (not approved) and the overview-transactions endpoint (unapproved,
  unwired). Backup: `~/lm_backups/wip-main-checkout-2026-11-17-consolidation/`.
- Blocked on CA: GST on licence trades, TDS sections/rates, inventory costing. Production historical posting needs approval.
- Left alone: ERP OD-program code (`feature/erp-implementation`), `feature/v5-throttle-retry`, other worktrees'
  uncommitted WIP. Local DB `test_lm_upgrade_9b79` is kept (owner).
<!-- CHECKPOINT:accounting:END -->

<!-- CHECKPOINT:accounting-frontend:BEGIN -->
**Accounting frontend round — TESTED (2026-11-17; licence data-bearing e2e fixed; 1 P3 open)** · details `docs/erp-accounting/09-accounting-frontend-implementation.md`
- Workspace IA (`pages/accounting/sections.ts`): Dashboard · Masters · Transactions · Ledgers · Banking · Expenses &
  Income · Reports · Entity-wise · Setup; sidebar mirrors it (`navConfig.ts` + test). Date range inside the FY.
- New screens: Chart of Accounts, Account Groups, Parties (+detail), Customer/Supplier ledgers, typed voucher books,
  draft edit, Bank Transactions / Unmatched / Reconciliation, Party Outstanding, Voucher Register, register/:kind,
  Entity-wise summary; dashboard advances + recent vouchers + activity.
- Backend (additive): `PATCH vouchers/<id>/` (manual drafts), `GET parties/summary/`, dashboard `advances_*`,
  statement search on reference. Tests written, not run (`test_frontend_support_api.py`).
- Checks run: `tsc --noEmit` exit 0; ESLint on changed files 0 errors / 6 warnings; `py_compile` OK. Nothing else.
- Next: coordinated testing phase (backend accounting tests + architecture, vitest, lint, build, e2e incl. 19 new routes).
- **Nav visibility fix (2026-11-17, later) — VERIFIED (focused):** root cause of "Accounting missing from the top nav" =
  the menu/route are gated by `ACCOUNTS_VIEWER/MANAGER/APPROVER`, but `ROLE_CODES` (`available-roles`, which feeds
  the user form + Settings) omitted them, so only superusers could ever see Accounting. Fix: roles added to
  `ROLE_CODES`; Accounting entries added to the Ctrl-K palette. Tests: `apps/accounts/tests` 21 passed (exit 0,
  `TEST_DB_NAME=test_lmanagement_acctnav`); vitest CommandPalette + navConfig 20/20 (exit 0); `tsc` exit 0; ESLint
  exit 0. Owner action: assign an `ACCOUNTS_*` role to each accounting user (Users & Roles). Full gates not run.
- **Testing phase (2026-11-17, evening) — accounting TESTED.** Fix `3e7cfed5`: `parties/summary/` 500 (`period_from`
  not imported) + BOE list query-budget repin (cb2abf5c adds a flat +3; caps 20/50 → 23/53).
  - Frontend gate (lint, typecheck, vitest **853/853**, build): exit 0.
  - Backend gate (on 7b106d8f, `TEST_DB_NAME=test_lmanagement_b5gate`): check, migrations check, `tests/`, ruff PASS;
    app-level 3500 passed / 3 failed, flake8 1 F821 → all 3 caused by the two issues fixed in `3e7cfed5`. After the fix:
    flake8 exit 0; `apps/accounting` + query-budget file 107 passed; c914288b (peer) tests 3 + CommandPalette 5 passed.
    Full app-level suite not re-run (only those files changed).
  - Real-backend accounting e2e (`seed_accounting_e2e`, isolated DB, backend :8011): **10/10 passed**, 0 HTTP 500s
    (47 routes, trade→books→receipt→statement→reconciliation, reports drill-down, viewer/non-accounting permissions,
    breadcrumbs, desktop/tablet/mobile overflow). Before the fix: 1 failed (4× 500 on parties/summary).
  - Default Playwright suite: 103 passed / 52 failed / 19 skipped. 51 = legacy `responsive.spec.ts` (hardcodes
    `localhost:5175`, unchanged since 2026-09-25; not in CI) — env, not a regression. 1 = item-pivot (needs harness).
  - Licence data-bearing e2e (failing at HEAD and c33f6a1a) → **TESTED after `69fe9b9b`**: root cause = stale seed,
    not product code (CIF rule intact, diagnosed + bisected): since `0da86766` the purchase line had `cif_fc=0` (balance
    0.00) and no licence had a `purchase_status`; queue fixture assumed a 10/page queue (25/page since `128417fd`);
    pivot spec re-toggled the norm off. Also harness cache isolation (`CACHE_KEY_PREFIX`, opt-in, default ""). Result:
    `data-bearing.real` **5/5 passed**, 0 HTTP 500s; seed command + architecture tests 12 passed; `manage.py check` OK.
  - **FAILED (P3, open):** `item-pivot.sticky` — sticky tier misaligned 3.375px vs 2px tolerance (spec line 44). Real
    layout check, tolerance not loosened. Not investigated.
  - Not fixed (env): legacy `responsive.spec.ts` (hardcoded :5175, not in CI) — needs rewrite or removal (owner call).
- Next: P3 pivot sticky alignment; then deferred items (report exports, opening-balance import, accrual beat job,
  DataTable/sort, trade-screen accounting badge).
<!-- CHECKPOINT:accounting-frontend:END -->


<!-- CHECKPOINT:accounting-banking-proposals:BEGIN -->
**Accounting banking — statement import + invoice proposals — TESTED (2026-11-17)** (session license-manager-b5)
- Owner decisions (2026-11-17, this session): proposals are **propose → approver confirms** (nothing auto-posts);
  allocation **oldest bills first**, excess = on-account advance; **learn narration → party aliases**.
- `05c62ad2` importer: header scan 25→60 rows, `Withdrawl Amt` alias, one-sided debit/credit mapping rejected.
- `d4320df6` + `5ba25fff` backend: `services/bank_proposals.py` (confirm → `payments.record_payment` + BankMatch
  `PROPOSAL`); guards: UTR book candidate, used UTR, unaccounted Trade payment, own account. API: `bank-accounts/<id>/
  proposals/` (+`confirm/`, approver), `statement-lines/<id>/proposal/?party_id=`, `narration-aliases/` (delete approver,
  audited). **SCHEMA (additive):** `accounting/0005_narration_alias` — applied to local `lmanagement` only.
- `3d96d090` UI: `/accounting/banking/proposals` (Invoice Proposals) + nav; read-only for viewers.
- Tests: backend `apps/accounting` + architecture **116 passed**; flake8 0; makemigrations --check clean; frontend gate
  exit 0 (**vitest 859/859**, lint, typecheck, build); real accounting e2e **10/10**, 0 HTTP 500s.
- Local data (dev DB only): LABDHI bank `BANK 400000070225` (id 2) created; `2025.xlsx` imported (318 lines, reconciles
  to closing ₹10,73,152.07). A second import `2026.xlsx` (341 lines) was added to the same account by someone else.
  Read-only proposal run on 659 lines: high 232 · medium 30 · low 13 · none 384; 11 queries. **Nothing confirmed.**
- `98b74efc` + `47866635` Record payment / receipt: tick invoices (settle in full), **Against invoices / On account** toggle,
  **Pick bank transaction** (party-ranked unmatched lines; `POST payments/` + optional `statement_line_id` posts and
  matches once, partial allowed). Tests: backend 120 passed; vitest 863 + Payments 4; typecheck/lint/build pass; real
  accounting e2e 10/10, 0 HTTP 500s.
- Later (same day, owner requests): saves on pick, no select/confirm (`10474eaa`); 10 s Undo via reversal (`5a4a81ab`,
  `ef2c1330`); **BU bulk-upload split** — one line → one payment per supplier, all matched to the line, all-or-none,
  undo reverses all (`946f486a`, `9fbb10ea`; no schema change). Tests: backend 126 passed; vitest 867; frontend gate
  exit 0; accounting e2e 10/10. Final integrated backend gate: run by session "accounting nav integration".
- Open: bank name/IFSC for account id 2 (owner); no e2e that confirms a proposal on seeded data yet.
- Next: owner reviews proposals in the UI and confirms; add an e2e confirm flow to `seed_accounting_e2e`.
<!-- CHECKPOINT:accounting-banking-proposals:END -->

<!-- CHECKPOINT:boe:BEGIN -->
**BOE — last verified checkpoint (2026-11-17, integration sweep)**
- Branch `feature/v5` (local only; 17 commits ahead of origin, 0 behind; push needs owner approval).
- All completed BOE work is integrated: `3ece31f0` (iteration 1), `f202cedb` (Phase A, D1–D15), `d47041f5` (autonomous
  workflow), `9f012089` (Phase B), `48e7207b` (Licence + BOE UI), `66feb25f` (tracker), `cb2abf5c` (authoritative
  `invoice_status`). Integration sweep (owner request): branches/worktrees checked by patch equivalence; no further
  completed BOE work found. **No tests were run for the sweep.**
- Preserved, NOT integrated (in progress / other owners / stale base): `lm-impl-boe-perf` and
  `license-manager-implementation` uncommitted BOE perf edits (2026-11-16, old `bill_of_entry/serializers.py` paths, now
  shims); `T-022` untracked `pages/boe-workspace/` prototype (superseded); `boe-erp` worktree deferred perf + low-item
  WIP (stopped, untested) — backup patch `~/lm_backups/boe-erp-wip-deferred-perf-2026-11-17.patch`.
- Non-BOE branches with unapplied commits (other workstreams, left alone): `feature/version5`, `orch/T-*`,
  `feature/erp-*` (OD track incl. protected balance code), `master` (session log), `fix/trades-list-ordering`,
  `feature/v5-throttle-retry`, `docs/t2f-lifecycle-audit`, `worktree-agent-*`, `docs/erp-accounting-audit`
  (accounting UI already integrated under a different hash).
- Deferred: (1) BOE list perf — ~818 queries / 3.3 s per 100 rows from per-row available-CIF (protected balance code;
  separate authorization); (2) Invoice Status filter single-select vs multi-value API; (3) nginx `nosniff` ops reload.
- Uncommitted by design: root `CLAUDE.md` §7 pointer (file also holds another session's edits).
<!-- CHECKPOINT:boe:END -->

| Date | BOE milestone | Commit | Evidence |
|---|---|---|---|
| 2026-11-17 | Iteration 1 | `3ece31f0` | BE 3152 passed/1 pre-existing xfail; FE 807/807; Playwright 29/29 mocked |
| 2026-11-17 | Authoritative invoice_status | `cb2abf5c` | backend suite 552 passed; FE 836/836; Playwright 16/16 mocked; live read-only API check 1044 BOEs |
| 2026-11-17 | Integration sweep (no tests run) | this commit | patch-equivalence check of all branches/worktrees |
| 2026-11-17 | Licence + BOE UI modernization | `48e7207b` | FE 833/833 + typecheck + lint + build; Playwright 38/38 mocked |
| 2026-11-17 | Phase B | `9f012089` | BE gate exit 0, 3395 passed/1 pre-existing xfail; FE 836/836; Playwright 21/21 mocked |
| 2026-11-17 | Iteration 2 Phase A (D1–D15) | `f202cedb` | BE gate exit 0, 3339 passed/1 pre-existing xfail; FE 814/814; Playwright 29/29 mocked; 1044 local BOEs echo-validated, 0 false 400s |

Detail: `docs/erp-architecture/boe-modernization-progress.md`, `docs/boe-modernization/owner-decisions.md`,
`docs/erp-architecture/claude-usage-log.md`.

<!-- CHECKPOINT:generic-erp:BEGIN -->
**Generic ERP + Masters workspace — TESTED (2026-11-17, session "license manager erp modernization")** · hub `docs/erp-architecture/GENERIC_ERP_ARCHITECTURE.md`, results `docs/erp-architecture/TEST_AND_QA_REPORT.md`
- Generic layer = existing `MasterViewSet.create_viewset` + metadata-driven `MasterList`/`MasterForm` (DR-GEN-1); no second framework.
- Backend gate on `b099789c`: app-level 3546 passed / 1 xfailed; `tests/` 245 passed + 1 env failure (no `frontend/dist`; 17/17 after build).
- `31061856` P3 item-pivot sticky: spec assertion wrong (tiers differ in height, abut exactly); real backend 1 passed. **Closes the P3.**
- `331b9520` Masters workspace: `/masters` hub (category nav, live counts, search), 5 API-only masters now in the UI, code-keyed
  record URLs, permission-aware card actions, list refresh after save. **API CONTRACT (additive):** slash-coded notification
  numbers (9/10 local codes) were 404 on detail/edit/delete — now resolve. Tests: backend 38 passed; vitest 127 passed;
  frontend gate lint/typecheck/build PASS; real-backend Playwright 4/4. Independent review: approve-with-nits, nits fixed.
- No business-rule change (no CIF/balance/BOE/accounting code touched). Not pushed.
- Blocked on owner (B1): Customer/Supplier/Country/Currency/Category/UoM/Bank masters have no models — not invented.
- Masters on the licence UI standard (2026-11-17, later): registered masters use the licence register toolbar
  (`COMPACT_REGISTER`), licence-style rows (`GenericMasterCards` → `ActionMenu`/`StatusBadge`), and a generic record page
  `/masters/:entity/:id` (`ModuleWorkspace`; Details + audit timestamps; History = real `ActivityLog` writes, USER_MANAGER).
  **API CONTRACT (additive):** `activity-logs/?changes_only=1&endpoint=…`. Tests: backend 21 passed; frontend gate exit 0
  (vitest 895/895 → 99/99 masters after review fixes); real-backend masters 4/4; licence data-bearing 6/6 (+1 live-only skip).
  Review (Sonnet): approve-with-nits; fixed 404 flash after delete + DRF error messages. Endpoint index deferred (B8, 31 ms).
- No business-rule change. Not pushed. `feature/v5` still at `b099789c` — land with `git merge --ff-only` (owner).
- Next: bulk actions on generic masters; owner decisions B1 (missing master models), B8 (optional index).
<!-- CHECKPOINT:generic-erp:END -->
