# Test and gate results

Only evidence from the phase reports is recorded here. Items marked NOT RUN were not executed.

## Phase A (commit `f202cedb`)

| Gate | Result |
|---|---|
| Backend `scripts/dev/quality-gate.sh backend` | PASS: 3339 passed, 1 pre-existing xfail |
| Frontend `scripts/dev/quality-gate.sh frontend` | PASS: 814/814 unit tests, typecheck, lint, build |
| Playwright BOE mocked suite | 29/29 PASS |
| Read-only echo validation of local BOEs | 1044 BOEs checked, 0 false 400s |
| Local DB migrations | No pending migrations |
| Local data facts | 1015 of 1044 BOEs have frozen rows; 159 legacy OTH BOEs protected by D6 |
| Live/real Playwright specs (`*.live`, `*.real`) | NOT RUN (need seeded live backend) |

## Phase B (implemented, pending lead verification and final gate)

Per-workstream targeted runs only. No full gate was run, per the owner's testing policy.

| WS | Targeted tests | Result | Not run |
|---|---|---|---|
| B1 detail page | Vitest `src/pages/bill-of-entry` + `src/features/bill-of-entry`: 6 files, 59 tests; tsc clean; ESLint clean; Playwright `boe-workflow.spec.ts` 11/11 | PASS | Full suite, build, backend |
| B2 MasterForm guard | Vitest 5 files, 24 tests (6 new in `MasterForm.boe.test.tsx`); tsc clean; ESLint clean | PASS | Visual check at 390px, Playwright |
| B3 save service | `test_boe_save_service.py` 12 characterization then 15 total; focused run 147 passed (incl. architecture tests); py_compile OK | PASS (reported) | ruff, full gate. Reviewer did NOT reproduce the 147 run |
| B4 exporters | 20 golden tests before and after move; 86 related passed; 9 architecture passed; pyflakes clean | PASS (reported) | Full suite |

Note on the merge request: the request to merge into `feature/v5` without testing was not actioned by this documentation task. No merge, push or commit was made.

## Review verdicts

| Workstream | Reviewer verdict | Notes |
|---|---|---|
| B3 save service | approve (read-only, tests NOT run by reviewer) | 2 low findings; see final-audit |
| B1/B2/B4 | approve_with_fixes | 2 medium, 3 low; see final-audit |
