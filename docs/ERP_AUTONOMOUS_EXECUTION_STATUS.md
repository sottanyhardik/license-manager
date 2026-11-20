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

<!-- CHECKPOINT:planning-workspace:BEGIN -->
**/planning SION workspace — licence-style accordion + inline tabs — TESTED (2026-11-18)**
- Norm list = compact accordion rows (one open, `?sion=` push → refresh/back/forward); config-driven tabs Overview ·
  Rules · Split Configuration · Product Mapping · Validation · Version History (+ Simulation when a preview exists).
- **API (additive, read-only, LicensePermission):** `GET sion-planning-rules/norm-summary/`,
  `GET sion-planning-rules/norm-configuration/?sion=` (service `license/services/sion_planning_workspace.py`); rule
  serializer gains read-only `stable_key`. No engine/calculation change; E126 split read from registry + entitlement profile.
- Tests: new backend 6 passed + planning rule suites 61 passed; frontend gate exit 0 (vitest 971/971, lint, typecheck,
  build); Playwright `planning-workspace.visual.spec.ts` 7/7 (mocked API, real local data via `LM_PLANNING_FIXTURE`).
  Backend gate: tests/ 246 + apps 3672 passed, 1 xfailed; **ruff F401 FAIL pre-existing** in
  `accounting/selectors/licence_bank_ledger.py` (unused `Q`, commit 44911fd3) — not touched.
- Local data note: E126/A3627 are inactive with no DB rules locally; shown from the code registry (read-only).
<!-- CHECKPOINT:planning-workspace:END -->

<!-- CHECKPOINT:allotments-workspace:BEGIN -->
**/allotments — licence-style rows + inline workspace + allotted-licence management — TESTED (2026-11-18)**
- Compact register toolbar (filters closed by default), single-expand rows, three-stage summary (allotment →
  allocated to licences → BOE). Tabs: Overview · Allotted Licences · Allocation · Allocate Licence (existing
  allocation page embedded) · BOE · Documents · Edit (inline MasterForm) · History.
- Allocation/release reuse `allotment-actions/allocate-items` + `delete-item` (no new model). Per-licence outstanding
  + status from `licenses/<id>/overview-allotments/` (same records as the licence workspace).
- **API (additive, read-only):** allotment `balanced_value` (= allocate-items remaining-CIF ceiling);
  `bill-of-entries/?allotment=<id>` (BOE permission); `masters/activity-logs/?endpoint_prefix=` (user managers).
  Display fix: FC values (`required_value`/`allotted_value`) now shown as USD (were labelled ₹).
- Tests: backend gate tests/ 246 + apps 3678 passed, 1 xfailed (ruff F401 pre-existing, unrelated); frontend gate exit 0
  (vitest 972/972); Playwright `allotments-workspace.visual.spec.ts` 5/5 (real local data via `LM_ALLOTMENT_FIXTURE`).
  cif-balance-auditor: APPROVE, no business-rule change. No live allocation writes were made on the dev DB.
<!-- CHECKPOINT:allotments-workspace:END -->

<!-- CHECKPOINT:item-pivot-intelligence:BEGIN -->
**Item Pivot — utilization intelligence + canonical licence figures — TESTED (2026-11-18)**
- Owner decisions: docs/decisions/2026-11-18-planning-cif-budget-e126-split-item-pivot.md (canonical engine;
  ItemNameModel × SION identity). Audit + implementation notes: docs/reports/item-pivot-audit-2026-11-18.md.
- **BUSINESS-RULE / API (additive):** classic pivot licence rows now canonical (signed balance, `is_over_utilised`,
  billed, allocation netting; summary final balance signed). New read-only `item-pivot/intelligence/` and
  `item-pivot/recommendations/` (ReportPermission, Excel). UI: Intelligence (default) | Classic pivot; four views.
- Tests: backend gate tests/ 246 + apps 3714 passed, 1 xfailed (ruff F401 pre-existing, unrelated); frontend gate
  exit 0 (vitest 978/978); Playwright `item-pivot-intelligence.visual.spec.ts` (real E5/E126 dumps + built-in) pass.
  cif-balance-auditor findings addressed (item basis labelled; other-adjustments from engine maps; overdrawn signed).
- Next: AI-assisted product matching (owner: deterministic matcher + pluggable AI; approval links import items to
  the master item — affects Auto Plan classification; approver LICENSE_MANAGER).
- **2026-11-20 — Total Summary ↔ detail, attribution, NOT ATTRIBUTED — VERIFIED (uncommitted, feature/v5).** Details +
  open owner decisions D1–D6: docs/decisions/2026-11-20-item-pivot-attribution-open-decisions.md. No business-rule change
  (licence CIF canonical). Fixes this session: TARGET MISSING summary rows carry `source_records` + provenance; Opus F1
  (split plan with NULL Item Name took rows mapped to another target); F3 rounding tolerance in `summary_check`.
  Evidence: backend gate exit 0 (tests/ 246; apps 4014 passed, 1 xfailed; ruff clean) `/private/tmp/gate_backend_pivot7.log`;
  frontend gate exit 0 (`gate_frontend_pivot2.log`); Playwright sticky 1/1 (`pw_pivot_harness4.log`); focused 45 passed.
  Real data (read-only) E1 active: 3 + 63 + 14 = 80 licences, 21 products, Total = Σ groups on 9 metrics, Excel = screen 0 diffs;
  all norms reconcile per licence. Opus cif-balance-auditor: APPROVED; /review-diff 5 reviewers: no blocking.
  Next: owner decisions D1–D6 + review follow-ups (decision doc); commit when the owner asks.
<!-- CHECKPOINT:item-pivot-intelligence:END -->

<!-- CHECKPOINT:import-item-name-override:BEGIN -->
**Licence Detail → Import Items: editable Item Name (row override) — VERIFIED (2026-11-20, uncommitted, feature/v5)**
- Owner decisions + design: docs/decisions/2026-11-20-import-item-name-row-override.md (row override; one Item Name per row;
  LICENSE_MANAGER writes). SCHEMA: migration `license/0066_import_item_name_override` (new table + MappingChange kind choice;
  additive; NOT yet applied to the local dev DB — `migrate` needs owner approval). No business-rule change.
- Overrides respected by: description mapping save / bulk / reapply / auto_apply / apply_for_licence, licence form,
  `PATCH license-items/:id/` (400), matcher decide + undo. Unguarded by design: consolidation, admin commands, RULE_AUTO_LINK (off).
- Evidence: backend gate exit 0 (apps 4027 passed, 1 xfailed) `/private/tmp/gate_backend_ovr2.log`; frontend gate exit 0
  (vitest 1028/1028, lint, typecheck, build) `/private/tmp/gate_frontend_ovr4.log`; override suite 13 passed.
  Reviews: cif-balance-auditor (Opus) APPROVED; code-reviewer APPROVE; security-auditor no Critical/High; findings fixed.
- Next: owner approves `migrate` on the local dev DB → browser check; commit when the owner asks.
<!-- CHECKPOINT:import-item-name-override:END -->

<!-- CHECKPOINT:item-report-planning-status:BEGIN -->
**Item Report — all items by default + Planning Status filter — FOCUSED-VERIFIED (2026-11-20, uncommitted, feature/v5)**
- Owner decision: Planned = valid plan (active, not deleted / cancelled) whose line is on the item OR lists it in
  `allocation_provenance.source_item_ids` (own licence only; Item Pivot `_plan_source_ids`). Real data: 3,233 = 723 + 2,510.
- API (additive): `reports/item-report/?planning_status=all|planned|unplanned` (400 otherwise); rows `is_planned`; response
  `planning_status`, `planning_counts`. Excel honours the filter. Planned Report unchanged (param never sent; query gate kept).
- UI: report loads without an item-name / search query; Planning Status select (counts) above the report; status empty states.
- Tests: backend item report 19 passed (exit 0); vitest src/pages/reports 104 passed (exit 0); eslint + ruff + tsc exit 0.
- Next: full backend + frontend gates in the same integration run as the Description + HSN approval work (in progress).
<!-- CHECKPOINT:item-report-planning-status:END -->

<!-- CHECKPOINT:import-item-mapping-approval:BEGIN -->
**Global Description + HSN import-item mapping approval — REVIEWED, gates pending (2026-11-20, uncommitted, feature/v5)**
- Owner decisions: docs/decisions/2026-11-20-import-item-name-row-override.md (Amendment): strict key + trimmed HSN ("no HSN"
  own key); precedence row override → approval (USER_APPROVED / USER_APPROVED_CLEAR) → description mapping → automatic writers.
- SCHEMA: `license/0066` (override) is ALREADY APPLIED on local `lmanagement` (2026-11-20 04:40 UTC, not by this session;
  table empty); `license/0067` (approval + version tables) NOT applied — needs owner approval.
- Reviews: cif-balance-auditor (Opus) APPROVED after fixes B1/B2 (consolidation vs overrides / later decisions) + N1–N4;
  code review contract mismatches fixed (preview item names, history `time`, mapping invalidation); security no Critical/High
  (record cap MAX_RECORDS=5000). Tests: approval 37 + override 13 passed; apps/license 2559 passed (2 item-report Excel
  failures belong to the in-progress Item Report alignment).
- FOLLOW-UP (pre-existing, accepted by Opus): lock-order cycle `apply_for_licence`/`auto_apply` (records → mapping) vs
  `save_for_key` (mapping → records) — a deadlock rolls one transaction back; on-commit hooks only log; drift repair heals.
  Also N6 qty sums in matching groups, N7 licence form ignores edits silently, N8 PROTECT blocks Item Name deletion.
- Next: full gates with the Item Report alignment; owner approves `migrate` 0067; browser verification.
<!-- CHECKPOINT:import-item-mapping-approval:END -->


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
- Generic bulk actions (2026-11-18): `POST masters/<entity>/bulk/` (`core/services/master_bulk.py`), per-record
  transaction + audit, MDS-outage stop; UI select page/rows → activate/deactivate/delete with per-record results.
  Off for domain viewsets and CIF/planning masters (B9). **API CONTRACT (additive).** Tests: backend 60 + architecture 39;
  backend app-level 3572 passed, 1 xfailed (exit 0); tests/ 246 passed after the services move; frontend gate exit 0 (903/903); real-backend masters 5/5.
- Master rows rebuilt on the licence register anatomy (2026-11-18): `masterColumns.ts` per master, one header row
  (select-all + labels), expandable rows, IEC-led Companies. Frontend gate exit 0 (910/910); real-backend masters 5/5;
  licence regression 6/6. The user's dev server (main checkout) still runs `b099789c`: land with ff-merge to see it.
- One generic template for all 8 masters (2026-11-18, session "generic master template consolidation"): SION Classes
  moved off the legacy `AccordionTable` onto `GenericMasterCards`; child norms come from config only
  (`masterColumns.ts` `nested`: export/import items, notes, conditions → compact tables in the expanded row). Also landed
  the earlier WIP: Masters menu two-column stacking, record title = list identifier, exchange-rate row widths.
  One parameterized spec `e2e/masters-seven-pages.real.spec.ts` covers all 8 (now incl. SION nested expansion).
  Tests: vitest masters 115/115, nav/licence/routes 64/64; tsc exit 0; ESLint exit 0; build exit 0; real-backend
  eight-master spec 10/10 (exit 0); masters-workspace 6/6 (exit 0). Run the two specs in **separate** harness runs —
  together they trip the API throttle (429 on `auth/me` → sign-out). No backend change; no business-rule change. Not pushed.
- Transfer Letter DOCX viewer + generic record tabs/accordion (2026-11-18) `b06133f7`. **NEW DEPENDENCY** `docx-preview@0.4.1`.
- One page per master — records open and edit inline (2026-11-18): no standalone master detail or edit screens.
  `/masters/:entity/:id?` → `MasterList` (one route, no remount) with that record expanded in its row
  (`MasterRecordPanel` via License's `DetailTabs`): Overview · Details (accordion) · Edit (generic `MasterForm`,
  `embedded`; save/cancel in place; writers only) · Documents (files + DOCX preview) · Related records · History.
  `/masters/:entity/:id/edit` → same list, record on Edit (URL normalised). `?tab=` is reserved (never a list filter).
  Off-page records show pinned above the list. Row delete now surfaces DRF list/field refusals (`apiErrorMessage`).
  Tests: frontend gate exit 0 (lint, typecheck, 924/924 vitest, build); real-backend masters-detail 4/4,
  eight-master 10/10, masters-workspace 6/6 (each exit 0, separate runs). No backend change. Not pushed.
  Open: `/masters/:entity/create` is still a page; editing a code-keyed master's code leaves the open URL on the old code.
- **ERP workspace modernization (2026-11-18)** — five workspaces on the Licence register pattern:
  - P1 Licence Edit `b2175d44`: Edit tab inside the expanded licence (embedded `MasterForm`, LICENSE_MANAGER only;
    menu Edit opens it). Real-backend `licence-edit` 1/1 (validation error in place, cancel, save persisted, list kept, audited).
  - P2 shared toolbar `5b6a9172`: `WorkspaceToolbar`/`WorkspaceTitle`; `AdvancedFilter` + `MasterList` render through it (DOM same).
  - P3–P6 (this commit): Ledger Upload (toolbar, format guide from real limits, inline rejection, progress, per-category
    results — only categories the API returns), Licence Ledger (one toolbar, filters collapsed, secondary actions in a menu,
    chips, shared states; no request/calculation change), Planning (toolbar, filters collapsed, duplicate actions → one menu),
    Incentive Licences (compact toolbar + generic rows + inline record Overview/Details/Edit/History; `/incentive-licenses/:id`
    and `/:id/edit` open inline; old card table removed). Test seed creates LICENSE_VIEWER / INCENTIVE_LICENSE_VIEWER groups.
  - Evidence: frontend gate exit 0 (934/934); `workspaces.real` 6/6 incl. viewer denied (no Edit, API 403, /403 route);
    visual: all titles at the Licence toolbar row (y≈93 @1440, was 129), no overflow @1440/390. No financial code touched.
  - Regression: licence-edit 1/1, masters-detail 4/4, eight-master 10/10, masters-workspace 6/6, licence data-bearing 5/5,
    visual 1/1 (all exit 0); backend financial/ledger/incentive 203/203 (balance calculator, CIF single source, canonical
    ledger, BOE/allotment CIF attribution, ledger exports/statement); seed + architecture 12/12. Global mobile 44px
    touch-target rule no longer distorts Radix switches/checkboxes (index.css).
  - One-page Licence Ledger (2026-11-18): Category → Company accordion → SION accordion → licence row → inline
    `LedgerLicenceWorkspace` (Overview / Ledger = former detail page via embedded `LicenseLedgerDetail`; BOE & Allotments,
    Invoices, History = licence register tabs; Documents = ledger PDF/Excel/customs PDF + licence copy; Edit = embedded form).
    `/license-ledger/:licenseId?/:itemId?` is the one route (old detail URLs open the licence inline; off-filter → pinned).
    Real record 2619/881 (0311054050, company LABDHI GLOBAL LLP) verified read-only via `ledger_detail` (200, 3 txns,
    current balance 137,653.62 USD). Tests: gate exit 0 (935/935); e2e one-page 1/1, workspaces 6/6, visual 1/1. No backend change.
  - Payment ledgers `7e53e3cc` + bank details `44911fd3` (2026-11-18): read-only APIs `licenses/<id>/overview-payment-ledgers/`
    (LicensePermission) and `accounting/licence-bank-ledger/<id>/` (AccountingPermission; structural links only — settlements /
    trade-payment link; `trades` = per-invoice posted bank settlement, bank side from the statement line). Backend 170 passed.
  - NO TABS (2026-11-18): the expanded licence is one continuous workspace — header, cards, company-wise table with inline bank
    details, Purchase invoices, Sale invoices, Bank payment ledger (accounting roles), BOE & Allotments (expandable),
    Documents & licence copy actions (+ inline Edit for writers), Ownership History (expandable). Gate exit 0 (951/951);
    e2e one-page 1/1 (asserts zero tabs), payment ledgers 3/3; screenshot confirms the tab bar is gone.
  - SUPERSEDED same day by the owner (explicit choice: persistent header + 8 tabs, single owner per datum): permanent licence
    header + 4 licence-level cards; tabs Ledger (company-wise transactions + reference links only) / Purchase Invoices / Sale
    Invoices (invoice-level totals) / Bank Payment Ledger (licence-linked bank totals; each bank txn once) / BOE & Allotments /
    Documents / Ownership History / Edit. Cross-references switch tab and focus the record (invoice no. / UTR). The separate
    bank-movement block and inline bank rows were removed (duplicates). Gate exit 0 (950/950); e2e one-page 1/1, payment 3/3.
- Next: apply the licence register pattern to the next module (owner-agnostic, non-financial lists first);
  owner decisions B1, B8, B9.
- LICENCE LEDGER FOUR TABS (2026-11-18, owner request): the expanded licence workspace now shows exactly Ledger · Purchase Invoices ·
  Sale Invoices · Bank Payment Ledger. BOE & Allotments, Documents, Ownership History and Edit were removed from the workspace
  presentation only (components/endpoints untouched). Ledger PDF / Excel / Customs PDF remain on the page toolbar and licence row.
  Verified: vitest 27/27 (licence-ledger files); full frontend gate exit 0 (950/950 unit, lint, typecheck, build); real-backend
  `licence-ledger-onepage` 1/1 (exit 0, fresh test DB). Screenshot confirms four tabs. Committed locally, not pushed.
<!-- CHECKPOINT:generic-erp:END -->

<!-- CHECKPOINT:e126-entitlement:BEGIN -->
**E126 Vegetable Oil entitlement planning — VERIFIED (2026-11-18, session backend-9b)**
- Generic read-only planner: `services/entitlement_planning.py` (pure Decimal) + `entitlement_planning_service.py` (DB adapter;
  rules/percentage rows, `get_debit_rows`, `get_allotment_rows`, `calculate_credit`, `get_balance_cif`) + data profile
  `sion_planner_config/entitlement_profiles.py` (E126: Sunflower+Olive → OLIVE OIL, PKO separate, refs `E126:ACTION:002:SPLIT`).
  `GET /api/entitlement-plan/?license_number=&sion=[&export=xlsx]` (LicensePermission). UI: `/planning?license=…&sion=E126&view=simulation`.
- Auto Plan: `planning_usage_reconciliation` split-child theoretical = planned + provenance `actual_target_quantity`
  (SPLIT_BY_PERCENT only; everything else unchanged). Reviewed by cif-balance-auditor (APPROVE).
- Owner-approved LOCAL DB data change: 25 BOE + 2 allotment explicit targets for 3411008089 (`apply_entitlement_targets`,
  audited in ActivityLog), BOE 5051922 ↔ allotment 10106 linked (ReconciliationLog LINK); licence re-planned (request 19607).
  Backup: `~/lm_backups/lic2510-before-entitlement-targets-2026-11-18.json`. Production needs the same command run separately.
- Result 3411008089: PKO remaining 14,039.13 kg / 25,270.43; OLIVE OIL 1,69,077.49 kg; both PARTIALLY UTILIZED.
- Evidence: backend gate exit 1 only for pre-existing ruff F401 in `accounting/selectors/licence_bank_ledger.py` (44911fd3);
  app-level 3654 passed/1 xfailed, tests/ 246 passed; planning regression on final code 1283 passed; new tests 66 passed;
  frontend gate: lint/unit (956)/build PASS, typecheck fixed → exit 0; planning vitest 38 passed. Live browser spec
  `e2e/e126-entitlement.live.spec.ts` written; NOT RUN (no saved auth state).
- Open: Auto Plan Olive CIF 8,77,628.98 vs residual 8,80,668.89 (planner reserves PKO at rate; 3,046.18 not re-flowed) — owner decision.
<!-- CHECKPOINT:e126-entitlement:END -->

<!-- CHECKPOINT:reports-menu-audit:BEGIN -->
**Reports menu audit — VERIFIED (2026-11-20, uncommitted, not pushed)**
- No entries removed: all 12 Reports / Licence status / SION entries are distinct (route + backend endpoint inspected).
- Fixed: Expiring/Active export called `license/reports/…` (Django 404) → `reports/…`; License Downloads menu/palette
  entry now gated by its route's `LEDGER_READ_ROLES` (REPORT_VIEWER saw it and got 403); SION page shows the group of
  its own norm. URL filters via new `hooks/useUrlFilters.ts`: `?days` (Expiring/Active), `?status&days` (Download
  License), `?is_expired&is_null` (SION); defaults written with replace, no double fetch.
- Tests: frontend gate exit 0 (lint, typecheck, vitest 147 files/1057, build); `e2e/reports-menu.spec.ts` 11/11 exit 0.
  `e2e/navigation.spec.ts` + `reports-menu.spec.ts` 19/19 exit 0 (after d3's `items?.length` null-guard, 2026-11-20).
- Item Report ↔ Item Pivot alignment: handed to license-manager-d3 (owner of that WIP); D1–D4 owner decisions in
  docs/decisions/2026-11-20-item-pivot-attribution-owner-decisions-d1-d4.md; d3 re-confirming D1–D3 with the owner.
- Next: owner review + commit authorisation.
<!-- CHECKPOINT:reports-menu-audit:END -->

<!-- CHECKPOINT:erp-formatting:BEGIN -->
**Global ERP formatting standardisation — VERIFIED, uncommitted (2026-11-20)** · audit `docs/erp-formatting/2026-11-20-formatting-standardisation-audit.md`
- Excel: shared `apps/core/exporters/excel/cell_formats.py`; numeric cells, DD-MM-YYYY date cells, text identifiers, live SUM/SUMIF totals (length-safe) across licence/allotment/BOE/master exporters. Financial Ledger workbook keeps canonical DTO totals (CIF audit B1: SUM would double count multi-company licences).
- Dates: API stays DD-MM-YYYY (owner, ISO switch deferred); PDFs → `%d-%m-%Y`; frontend ad-hoc formats → `utils/dateFormatter`. Native date inputs listed, not replaced (owner).
- Tests: backend gate pytest 4100 passed + 1 xfailed, 246 passed; makemigrations clean; ruff 1 F401 in peer file `test_import_item_mapping_approval.py` (gate EXIT 1 for that only). Post-fix targeted reruns 130 + 20 + 83 passed (exit 0). Frontend gate EXIT 0 (vitest 1057/147, build OK, eslint 0 errors).
- Deferred (peer WIP): `item_pivot_excel.py`, `item_pivot_helpers.py`, `item_report.py` Excel typing/SUM totals.
- Next: owner review + commit authorisation; ISO API migration and native date-input replacement are separate tasks.
<!-- CHECKPOINT:erp-formatting:END -->

<!-- CHECKPOINT:cross-surface-reconciliation:BEGIN -->
**Cross-surface reconciliation — Phase 8 (2026-11-20) — PARTIAL, waiting on peer gates + owner decisions** · report `docs/reports/cross-surface-reconciliation-2026-11-20.md` §8
- Audit complete: `/tmp/recon_full2.json` exit 0 — 2,182 licences / 26,818 items / 14,314 pivot cells / 4,831 discrepancies on 2,071 licences. The licence-level CIF reconciles on every surface; the item level does not (RC3, RC4a/b, RC13–RC15).
- Independent Opus cif-balance-auditor: ESCALATE-TO-OWNER. RC4a and RC16 are canonical-rule conflicts (D-A, D-C). RC3 and RC4b are PARTIAL (relabelled). New findings: N1 PDF item Balance CIF = RC4a value (HIGH); N2 PDF Total CIF = opening_balance; N3 dead "never exceeds balance" guard; N4 PDF unit-key split.
- No application code changed in Phase 8 (docs only).
- Targeted tests: 305 passed, exit 0 (`TEST_DB_NAME=test_lmanagement_p8_targeted`).
- Full gates, Playwright and /review-diff: NOT RUN. They wait for peer `license-manager-d3` to finish its in-flux pivot/Item Report work, after which that session runs quality-gate backend + frontend once.
- Owner decided D-A … D-F + approvals 2026-11-20: `docs/decisions/2026-11-20-cross-surface-owner-decisions-da-df.md` (BUSINESS-RULE CHANGE approved, not implemented).
- Next: peer gate results → /review-diff → implement decisions (coordinate peer-owned files: item_report.py, item_pivot_*) with characterisation tests + Opus cif-balance-auditor.
<!-- CHECKPOINT:cross-surface-reconciliation:END -->

<!-- CHECKPOINT:sat-cif-recon:BEGIN -->
**SAT P0 addendum — licence CIF / import item / planning reconciliation — DONE (audit only, 2026-11-20, session license-manager-2c)**
- Reports (docs/qa): SAT_IMPORT_ITEM_CIF_RECONCILIATION.md (§10 = consolidated exception table), SAT_PLANNING_BALANCE_AUDIT.md, SAT_INVOICE_BOE_QUANTITY_AUDIT.md, SAT_ZERO_BALANCE_VALIDATION.md, SAT_CIF_RECON_INDEPENDENT_REVIEW.md. Evidence: ~/lm_sat_evidence/cifrecon/.
- Independent SQL = engine: 26,818 items × 8 metrics, 0 diffs; 2,185 licences, 0 diffs. API live fields = engine (526 licences / 6,679 items). Independent reviewer: 0 figure disagreements (19 items, 3 licences).
- FAIL / open: API stored fields (RC3/RC13, decided D-D/D-F, not implemented); item CIF over-use unflagged (DEC-50); null-DFIA thresholds 100/200/500 (SAT-DEF-140); saved plans not capped by the live balance (DEC-11; SAT-DEF-100 reclassified as a business-rule question); Plan tab balance ignores the hidden-BOE rule (SAT-DEF-102); invoice qty rule 15 FAIL on the test DB (SAT-DEF-120…132); unlinked allotment + BOE double count (SAT-DEF-150, 420,407.75).
- Tests: throwaway characterisation tests on test DBs: qty 31 passed (exit 0), planning 21 passed + 114 existing planning tests passed (exit 0). No repo code changed; no gates run (audit only).
- Register rows handed to SAT controller license-manager-ac (owner of SAT_USER_DECISION_REGISTER / SAT_DEFECT_REGISTER). Numbering: DEC-11…14, 20…26, 50…52, 60; SAT-DEF-100…106, 120…132, 140…142, 150…151.
- Next: owner decisions; no fix without approval.
<!-- CHECKPOINT:sat-cif-recon:END -->

**CHECKPOINT:sat-decisions — 2026-11-20 (docs only, no code, no tests)**
- All SAT owner decisions recorded: `docs/qa/SAT_USER_DECISION_REGISTER.md` (decision closure section + question log).
- Gate report awaiting owner approval: `docs/qa/SAT_IMPLEMENTATION_APPROVAL_REPORT.md` (WS0–WS8, G1–G8, migrations, data repair, rollback).
- Next: owner approval → WS0 characterisation tests → WS1 engine (financial-integrity owner). Peer-dirty files in scope: license serializers/views, item_usage.py, signals.py.

<!-- CHECKPOINT:item-pivot-license-numbers:BEGIN -->
**Item Pivot — License Numbers filter — VERIFIED + COMMITTED (2026-11-20, feature/v5, not pushed)** (only these hunks; peers' WIP in the same files left uncommitted)
- Backend: `license_numbers` GET param (comma/newline/;/tab split, trim, dedupe, exact `IN`, AND-ed with all filters, max 5000 → 400)
  in `item_pivot_selection.py` (`parse_license_numbers`, `license_number_filter_summary`), threaded through `item_pivot_report.py`,
  `item_pivot_generate.py`, `item_pivot_excel.py`. Additive response key `license_number_filter` {requested, matched,
  excluded_by_filters[{license_number, sion_norms}], not_found}. Excel matrix sheet CIF/qty cells now written as numbers (were text).
- Frontend: textarea + count + Apply (Ctrl+Enter) + Clear in `ItemPivotFilters.tsx`; state/export/chips/notice in `ItemPivotReport.tsx`.
- Tests: pytest `-k pivot` 294 passed (exit 0) incl. new `test_item_pivot_license_numbers.py` (19); balance pins 144 passed (exit 0);
  vitest ItemPivot* 41 passed (exit 0); tsc 0; eslint 0; build 0; Playwright new spec 1/1 passed. Existing `item-pivot.sticky.spec.ts`
  fails: seeded norm "E2E2509" absent from the current local DB (pre-existing data dependency).
- Snapshot gate (`quality-gate.sh all`, detached worktree of the exact commit tree): all PASS except 2 pre-existing, unrelated:
  ruff F401 `apps/accounting/selectors/licence_bank_ledger.py:25` (present at HEAD; peer WIP fixes it) and mds-client in `all`
  mode (gate leaks `DJANGO_SETTINGS_MODULE=mds.settings`; standalone mds-client runtests exit 0). cif-balance-auditor: PASS.
  Playwright spec re-run against a backend+Vite started from the snapshot: 1/1 passed.
- Next: none for this feature. Open: other norm tabs are separate pivots (by design); GET URL length (~600 numbers at nginx 8 KB default).
<!-- CHECKPOINT:item-pivot-license-numbers:END -->

**CHECKPOINT:sat-ws1 — 2026-11-20 (uncommitted)**
- WS0 + WS1 implemented and verified: backend app-level 4,194 passed / 1 xfailed; `tests/` 246 passed after fixes; ruff/flake8/check/migrations clean. Evidence `~/lm_sat_evidence/ws1/`. Opus cif-balance-auditor APPROVE-WITH-FIXES (F1/F4/F6 fixed).
- Open: F2 (exception/over-use surfaces not exposed), F3, F5, F7, F9 legacy consumers (→ WS3/WS4). Next: commit approval, then WS2.
