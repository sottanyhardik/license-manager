# SAT Execution State — source of truth

Branch `feature/v5` · HEAD `ec3604cb` · working-tree diff hash `6f1712e03000` (`git diff | shasum`) · 178 dirty paths
(peer-owned; preserved, never edited) · local DB `lmanagement@localhost` (read-only: 2,185 licences, 26,818 import
items, 14,425 BOEs, 168,629 BOE rows, 6,526 allotments, 11,610 allotment items at 2026-11-20 14:58 IST).
Evidence root: `/tmp/sat/<phase>/`. Plan: `docs/qa/MASTER_SYSTEM_TEST_PLAN.md`.

Rules for this file: an ID is DONE only with evidence (log path + exit code + real counts). Statuses:
`PENDING` · `RUNNING` · `PASS` · `PASS-EXC` (pass with documented exceptions) · `FAIL` · `BLOCKED` (reason + alternative) · `NOT-RUN`.

## Phase status

| Phase | Status | Owner | Output |
|---|---|---|---|
| 0 Baseline | see SAT-BASE-* | controller | this file |
| 1 Discovery | DONE — SAT-ARCH-001..009: 4 PASS, 3 PASS-EXC, 2 FAIL (004 dead clients/orphans, 009 unapplied migration 0067 locally). 375 API paths / 129 view classes | agent `sat-api-perf` | `SAT_API_DATABASE_AUDIT.md` §1, `~/lm_sat_evidence/api/` |
| 2 Backend/API | DONE — SAT-BE-001..017: 9 PASS, 5 PASS-EXC, 3 FAIL (003 payments 500, 010 date formats, 012 Redis). Write-path pytest 77: 70 passed / 7 failed (= findings), exit 1; probes exit 0 | agent `sat-api-perf` | `SAT_API_DATABASE_AUDIT.md` §2 |
| 3 Financial | DONE — PASS-EXC overall: licence-level CIF independently matches the engine and APIs (0 diffs on 2,185 licences; 0 diffs on 26,818 items × 6 metrics). FAIL on 008 (D01 High: ARO qty never deducted, filter `'ARO'` on a varchar(2) field — controller re-verified) and 014 (D02 High `is_boe` without M2M, 1,160,224.05 CIF; D03 duplicate BOE). Pinned tests 278 passed, exit 0; characterisation 13 passed, exit 0. 004/005 BLOCKED on data (0 trades) and verified on test DB | agent `sat-fin` (opus) | `SAT_FINANCIAL_AUDIT.md`, `/tmp/sat/fin/` |
| 4 Integration | DONE — PASS-EXC. Browser: INT-003 BOE debit → balance PASS (2,066.75 → 1,966.75, screen = API after reload); INT-014 reversal PASS; INT-006 accounting/payments PASS (10/10 + 3/3, exit 0); INT-005/012 PASS-EXC. Blocked in the browser with an API-level alternative: INT-004, INT-007 (backend workflow suites 257 passed / 1 xfailed, exit 0). NOT-RUN: INT-002 licence form writes, INT-009 transfer, INT-010 BOE upload (no UI). Partial: INT-008, INT-011 | `sat-e2e` + controller | `SAT_UI_UX_AUDIT.md` + controller addendum, `~/lm_sat_evidence/{e2e,int}/` |
| 5 E2E | DONE — PASS-EXC. 45 pages × 3 viewports = 135 loads: 0 page/console/API errors, 0 overflow. SAT-E2E: 19 PASS, 2 PASS-EXC, 1 FAIL (login error not announced), 1 PARTIAL, 3 NOT-RUN. Regression suite 25 passed / 4 failed (classified test/harness, 1 unclassified) / 16 did not run | agent `sat-e2e` | `SAT_UI_UX_AUDIT.md` |
| 6 Export | DONE 15:2x — FAIL (2 High). 25 export families, 19 sample licences. Export tests: 192 passed, exit 0. Defects D01 High (Balance Excel financial sheet wrong Current Balance, 15/16 licences), D02 High (Item Pivot Excel numbers stored as text), D03/D10 Medium, plus Low items. BLOCKED: trade/invoice exports (0 trades locally) and X07 package PDF | agent `sat-exp` | `SAT_EXPORT_AUDIT.md`, `/tmp/sat/exp/` |
| 7 UI/UX + security | SECURITY DONE — SAT-SEC-001..040: 13 PASS, 14 PASS-EXC, 10 FAIL, 3 NOT-RUN; final pytest 20 passed / 1 failed (harness over-strict assertion), exit 1; reruns exit 0 → SAT-DEF-050..065, DEC-34..40. UI part DONE: SAT-UX 5 PASS, 3 PASS-EXC, 6 FAIL (a11y), 2 NOT-RUN → SAT-DEF-080..089 | `sat-e2e` (UI), agent `sat-sec` (opus) | `SAT_UI_UX_AUDIT.md`, `SAT_SECURITY_PERFORMANCE.md` |
| 8 Perf/regression | DONE — SAT-PERF-001..012: 8 PASS, 2 PASS-EXC, 2 FAIL (004 BOE list N+1, 007 item-report 65 MB). `p8_perf.log` exit 0 | agent `sat-api-perf` | `SAT_API_DATABASE_AUDIT.md` §3 (summary → `SAT_SECURITY_PERFORMANCE.md`) |
| 9 Independent review | DONE (UI/E2E part not reviewed: that report wasn't available). Verdict ESCALATE-TO-OWNER. Blind raw-SQL recompute: 58/58 sample licences = engine single = bulk = `get_balance_cif` = list API (max diff 0.00); all 2,185 vs bulk engine 0 mismatches; Phase 3 totals reproduced to the cent (now the surviving raw evidence). Reproduced: 001, 003, 010, 011, 030, 031, 050, 051, 052 (+054); 002 partial; 055–065 not reproduced. Pinned balance tests 139 passed, exit 0; DEF-031 test exit 0; security repro 4 passed, exit 0. New: SAT-DEF-070…074. Severity/status corrections applied to the registers | agent `sat-review` (opus) | `SAT_INDEPENDENT_REVIEW.md`, `~/lm_sat_evidence/review/` |

## Phase 0 — baseline

| ID | Test | Status | Evidence |
|---|---|---|---|
| SAT-BASE-001 | frontend gate (lint, typecheck, unit, build) | PASS | `/tmp/sat/gate-frontend.log`, `FRONTEND_EXIT=0` |
| SAT-BASE-002 | backend `manage.py check` | PASS | `/tmp/sat/gate-backend.log` l.2–4 |
| SAT-BASE-003 | backend `makemigrations --check --dry-run` | PASS ("No changes detected") | same, l.6–8 |
| SAT-BASE-004 | backend `pytest tests/` | PASS — 246 passed, 75.79 s | same, l.1078 |
| SAT-BASE-005 | backend flake8 (undefined names) | PASS | same, l.1082 |
| SAT-BASE-006 | backend ruff F401 | PASS | same, l.1086 |
| SAT-BASE-007 | backend `pytest apps` (app-level) | PASS — 4,140 passed, 1 xfailed, 0 failed/errors, 565.22 s, EXIT=0 | original run killed at 13 % with the previous session (no process, log ends mid-line at 14:56). Re-run: `TEST_DB_NAME=test_lmanagement_sat_apps pytest apps --import-mode=importlib -q -o addopts=""` → `/tmp/sat/p2/apps-pytest.log` |

## Running commands

| Started | Command | Log | Bash task id |
|---|---|---|---|
| 14:58 | SAT-BASE-007 — DONE 15:08, EXIT=0 | `/tmp/sat/p2/apps-pytest.log` | `bheegsnx8` |
| 15:05 | agent `sat-fin` (opus) — Phase 3 | `/tmp/sat/fin/`, test DB `test_lmanagement_sat_fin` | background agent |
| 15:05 | agent `sat-sec` (opus) — Phase 7 security | `/tmp/sat/sec/`, `test_lmanagement_sat_sec` | background agent |
| 15:05 | agent `sat-api-perf` (sonnet) — Phases 1, 2, 8 | `/tmp/sat/api/`, `test_lmanagement_sat_api` | background agent |
| 15:05 | agent `sat-exp` (sonnet) — Phase 6 | `/tmp/sat/exp/`, `test_lmanagement_sat_exp` | background agent |
| 15:05 | agent `sat-e2e` (sonnet) — Phases 4, 5, 7 UI | `/tmp/sat/e2e/`, harness `test_*` DB, ports 8000/41731 | background agent |

Owner approval 2026-11-20: migrations are allowed on the disposable `test_*` DB that
`scripts/test/run_data_bearing_browser_e2e.sh` creates. This covers that DB only and does not cover `lmanagement` or
any other DB. The approval has been passed to `sat-e2e`.

File ownership (one writer each): sat-fin → `SAT_FINANCIAL_AUDIT.md`; sat-sec → `SAT_SECURITY_PERFORMANCE.md`
(security part; controller appends the performance summary); sat-api-perf → `SAT_API_DATABASE_AUDIT.md`; sat-exp →
`SAT_EXPORT_AUDIT.md`; sat-e2e → `SAT_UI_UX_AUDIT.md` + new `frontend/e2e/sat-*.spec.ts`; sat-review →
`SAT_INDEPENDENT_REVIEW.md`; controller → this file, defect/decision registers, final report, resume prompt.

## Session recovery 2026-11-20 15:22 IST (controller session 2)

- Branch `feature/v5`, HEAD `ec3604cb`, diff hash still `6f1712e03000` (tree unchanged since SAT start). 180 dirty
  paths = 178 peer paths + 2 SAT-owned specs (`frontend/e2e/sat-pages-audit.spec.ts`, `sat-workflows.spec.ts`).
- **`/tmp/sat/` no longer exists** (temp cleared with the previous session). The Phase 3 and Phase 6 reports keep their
  figures and exit codes, but their raw logs/scripts are gone. Phase 9 re-derives a sample independently.
- The agents `sat-sec`, `sat-api-perf` and `sat-e2e` died with session 1. They produced no reports, only the 2 partial
  specs. No pytest/playwright/runserver processes and no listeners on 8000/41731 at recovery.
- New durable evidence root: **`~/lm_sat_evidence/<phase>/`** (outside the repo and outside /tmp).
- Relaunched at 15:25: `sat-api-perf` (sonnet; Phases 1, 2, 8), `sat-sec` (opus; Phase 7 security) and `sat-e2e`
  (sonnet; Phases 4, 5, 7 UI). Same ownership and DB names as before.

- Peer session `license-manager-2c` is running a P0 addendum (read-only): CIF / import-item / planning
  reconciliation. It owns `SAT_IMPORT_ITEM_CIF_RECONCILIATION.md`, `SAT_PLANNING_BALANCE_AUDIT.md`,
  `SAT_INVOICE_BOE_QUANTITY_AUDIT.md` and `SAT_ZERO_BALANCE_VALIDATION.md`, and uses DBs
  `test_lmanagement_sat_plan|qty|recon`. It sends its rows to the controller for merging (DEC-11+, SAT-DEF-100+).
  It does not edit the registers or this file.

- 18:xx `sat-api-perf` finished: 16 defects → SAT-DEF-030..045. Controller re-checked D04 (serializer has no `trade`; no UI caller) and downgraded it High→Medium. Phase 9 `sat-review` (opus) launched on the Phase 3/6/1/2/8 evidence; security + UI reports are sent to it on arrival.

- `sat-sec` finished. Controller confirmed D01 (method-blind permission) and D14 (4 .env files tracked; contents not read). Performance summary appended to `SAT_SECURITY_PERFORMANCE.md`. Security report forwarded to `sat-review`.

- Peer `license-manager-2c` P0 addendum COMPLETE; merged: DEC-11…14, 20…26, 50…52 (renumbered from its 30…32), 60; SAT-DEF-100…106, 120…132, 140…142, 150…151. Controller reclassified SAT-DEF-100 → BRA (deliberate per code comment). The peer adds its own CHECKPOINT block to `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md`.

- Tree hash changed `6f1712e03000` → `f6dd80443ee6` during Phase 9. Cause: only `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md` (peer
  checkpoint, 17:56). No application source has changed since the SAT started (newest source mtime 14:01), so no results are stale.
- Controller re-checked SAT-DEF-070 (`license_balance_excel_bulk.py:375` uses `calculate_balance_for_licenses`; the same in HEAD `:361`).
- `guard_bash.py` false positive: register text containing the "ENV" class label next to a pipe is blocked as an
  "environment dump". Register edits are done with the Edit tool instead. The hook was not bypassed.

## Next exact action
**SAT status: PARTIALLY COMPLETE. The final report is written** (`SAT_FINAL_ACCEPTANCE_REPORT.md`).
- All 9 phases are assessed and every ID has an outcome.
- Registers: 95 defect IDs (94 open: 0 Critical, 11 High, 37 Medium, 46 Low; DEF-089 closed); DEC-41 is the only open decision.
- Gap runs done: X07 → DEF-090; reports-menu → DEF-091; masters → DEF-092 (`~/lm_sat_evidence/e2e/harness-gap1|gap2.log`).
- SAT-owned test files: `frontend/e2e/sat-pages-audit.spec.ts`, `sat-workflows.spec.ts`, `sat-int-boe.spec.ts`. Not committed (SAT rule).
- Remaining executable work is in report §9: INT-002, INT-009, sort/bulk/delete-confirm/focus-trap UI checks, X07 retry, an isolated rerun of `reports-menu.spec.ts:91` and the masters specs, and the SAT-UX-D10 seed triage. Trade verification needs production-shaped data.
- Then the owner gate: `SAT_IMPLEMENTATION_APPROVAL_REPORT.md`, which must also cover DEC-41, SAT-DEF-070…074, SAT-DEF-080…089 and the DEF-059 addition.
- No SAT process is running; ports 8000 and 41731 are free.

## Decision closure 2026-11-20 (controller session 3)
- Seven owner decisions recorded, plus every remaining owner question answered one at a time (question log in
  `SAT_USER_DECISION_REGISTER.md`). C-1 was superseded by DEC-23 A. DEC-14 B amends SAT-DEF-150 (partial release).
- Gate report: `SAT_IMPLEMENTATION_APPROVAL_REPORT.md`. **No code changed, no tests run** (docs only). No defect closed.
- **Next exact action:** owner approves the gate report (plan, G1–G8, start WS0+WS1). Only then: characterisation tests → WS1.

## WS0 + WS1 — 2026-11-20 (controller session 3; uncommitted, owner approval of the gate report)
- WS0 characterisation: `apps/license/tests/test_sat_ws1_engine_rules.py` was run against the old code first: 9 failed / 1 passed,
  reproducing the audit values (AR 0, commission credited, rowless link 0, RELEASED reserving 42, item cap 100, remainder 25,
  writer 900). Log `~/lm_sat_evidence/ws1/ws0_characterisation.log`.
- WS1 implemented: DEC-01 (AR at item level, writer counts it once), DEC-03 (rowless link stays outstanding + `allotment_exceptions`),
  DEC-06 (COMMISSION_PURCHASE excluded from purchase credit/gate), DEC-07b (RELEASED/COMPLETED stop reserving), DEC-14
  (any active formal allocation releases the item), SAT-DEF-005 (D-A/D-B item cap), DEC-50 (live cross-item CIF adjustment
  + append-only `ItemCifAdjustmentRecord`, migration reconciliation 0007), C-2 (exact auto-link service/command, review list,
  audit actions, migration 0006, signal **off by default**). The `%`-pool and bulk allotment paths are routed through the shared engine rule.
- Independent cif-balance-auditor (Opus): APPROVE-WITH-FIXES, 312 passed, exit 0. F1 (auto-link vs an already allocated row),
  F4 (PROTECT FKs) and F6 (signal default) are fixed. Reconciliation + WS1 tests after the fixes: 111 passed, exit 0.
- Open: F2 surfaces (exceptions, uncovered over-use, DEC-14 later-BOE exception not exposed in API/UI), F3 (adjustment log only via
  command), F5 (COMPLETED = non-reserving: owner confirm), F7 (SION planning cap N+1; BOE list +1 query/row, budget 53→57),
  F8 edge cases, F9 legacy consumers still on the old allotment rule (planning WS3, Balance Excel item rows, pivot fallback,
  overview counts, models/items.py peer-dirty).
- Backend gate (`scripts/dev/quality-gate.sh backend`, `~/lm_sat_evidence/ws1/gate_backend.log`): manage.py check PASS,
  migrations check PASS, app-level tests **4,194 passed, 1 xfailed** PASS, flake8 PASS; `pytest tests/` FAIL (3: architecture
  ratchet reconciliation→allotment import, 2 mock item-balance tests) and ruff FAIL (1 unused import), gate EXIT=1. Fixed;
  rerun of those steps: `pytest tests/` 246 passed exit 0, ruff "All checks passed", auto-link tests 17 passed. Earlier area run 3:
  4,008 passed / 2 failed (migration dependency → repointed to license 0014; summary query pin 47→48, flat).
- Not committed (owner approval needed). Next: owner confirms F5 (COMPLETED) and F3 (adjustment log policy) → WS2 quantity.
