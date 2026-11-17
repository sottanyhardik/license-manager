# 00 — Executive Assessment (Phase Zero)

**Date:** 2026-11-15 · **Branch:** `feature/version5` · **Evidence:** docs 01–09 in this folder, local dev DB `lmanagement` (read-only), CI-equivalent gate runs.

## Verdict in five lines

1. The system is a working Django/DRF + React modular-monolith-in-waiting. It does **not** need a rewrite or microservices. It needs one authoritative balance layer, a green test baseline, and consolidated UI primitives.
2. **The single biggest risk is financial, not architectural.** There are **four licence-level balance engines and 25 duplicated business rules** (05). Twenty of them produce **different numbers today**.
3. **A live user-visible defect exists.** The Financial Ledger's "Current Balance" uses a trade-only running total (`license_balance_ledger_builder.py:666-672`, introduced 2026-08-10 in `7fd7104d`) instead of the financial engine. It is wrong for **2,036 of 2,185** dev licences: licence id 2603 shows 190,992.45 against the engine's 3,962.32 (verified independently). The screen, PDF and Excel all show it, and no test caught it.
4. **The test suite was silently not running.** One broken import (`SAMPLE_PDF_DATA`) aborted collection of ~2,700 app-level tests in CI from 2026-10-08. Fixtures were also never committed because of a global `*.csv` ignore. Both are now fixed (`5c509493`). 7 newly-visible failures are in triage.
5. **Prior "FROZEN / APPROVED / zero duplicates" documents from the 2026-08 autonomous run are not reliable.** The approval sign-offs are placeholders, and the "single source of truth restored" claim is contradicted by item 3. They are treated as leads only (ED-000).

## Health scorecard

| Area | State | Key evidence |
|---|---|---|
| Business-logic correctness | 🔴 | DUP-01 ledger balance wrong; floor-at-0 in 13 places hides 35 over-utilised licences (−6.96M total); ARO filter never matches (`calculate_balance.py:55`) |
| Tests / CI | 🟡 (was 🔴) | Gate now: lint, typecheck, vitest 544/544, build, backend `tests/` 237/237, MDS, mds-client pass. App-level: 2,700 pass, 7 fail (triage) |
| Architecture | 🟡 | App cycles hidden by local imports; signal-driven balance writes; fat views (allocation 497 LOC in a view) — 02 §12 |
| Database | 🟡 | ORM CASCADE reaches BOE/allotment history; no CHECK constraints on CIF/qty; 16 duplicate indexes; activity log 334k rows with no retention; MVs stale and unused — 03 |
| Performance | 🟡 | Active-licences report: 5.8 s / 7,034 queries. BOE list: 1,208 queries per page. Item report payload: 61 MB — 07 |
| Security | 🟡 | Env files tracked in git; USER_MANAGER can edit superusers; JWT in localStorage; no tenant boundary — 08 |
| Frontend | 🟡 | 9+ table implementations; financial maths duplicated client-side (4 rounding policies); `strict:false`; half-migrated data fetching — 09 |
| Dead code | 🟢 actionable | 20+ high-confidence removals listed (06 §A), awaiting batch approval |

## What happened in this session

- Completed Phase Zero docs 03, 04, 05, 07 (parallel read-only agents) plus 00, 10–13. Docs 01, 02, 06, 08 and 09 already existed and were kept.
- Captured a real baseline. Before: 5 gates failing. After: 1 gate failing (7 tests, triage in progress).
- Fixes, all test or tooling only, with no business-rule change (ED-002…ED-007): synthetic ledger fixtures, the broken test import/setup, a stale frontend expectation, eslint node-script config, a gate env leak, and the local MDS DB role.

## Decisions needed from the owner (ranked; asked one at a time)

| # | Decision | Why first |
|---|---|---|
| 1 | **OD-10** Financial Ledger "Current Balance": engine value vs trade-only running total (DUP-01) | Live wrong number on the most-used financial screen |
| 2 | **OD-01** Floor at 0 vs preserve negatives and flag over-utilisation | Hides 35 over-utilised licences |
| 3 | **OD-02** Which engine is canonical "Available CIF"; make "billed without BOE" an explicit term | Prerequisite for the master calculation engine |
| 4 | OD-11 Invoice PDF total and round-off rule (HALF_EVEN vs HALF_UP; ₹1,234.50 prints 1,234 vs stored 1,235) | Printed legal documents |
| 5 | OD-12 Outstanding-allotment definition (AR vs AT, netting) | Allotment module |
| 6+ | OD-03…OD-09, OD-13…OD-20 | See 12 |

## Recommended next three moves (no owner input needed)

1. Finish triage of the 7 hidden failures and get the gate fully green.
2. Add **characterization tests** that run `LicenseBalanceLedgerBuilder.build()` on licences that have BOEs and allotments. Today's numbers get pinned, and DUP-01 becomes visible to CI whichever way the owner decides.
3. Performance quick wins that cannot change numbers: BOE list/detail per-request balance memoisation (1,208 → ~O(licences) queries), the `active_licenses_report.py:225` prefetch, and `GZipMiddleware`. Each change carries a query-count regression test and an output-equality check against the 07 baseline.
