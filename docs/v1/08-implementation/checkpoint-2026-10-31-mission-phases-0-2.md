# Checkpoint — V1 audit, hardening and verified upgrade (phases 0–2, partial)

Date: 2026-10-31 (IST). Status: **in progress. Not production-ready.** Phases 3–12 of the mission are not complete. This checkpoint lists what was verified, what was changed, and what still fails, so the next session can resume from here.

## Phase 0 — baseline (verified this session)

| Item | Value |
| --- | --- |
| Branch / HEAD | `version-v1` / `d78c8b1d108368a9e48b26a05a50094dc930608d` (unchanged) |
| Stashes | 3, unchanged |
| Python / Django / DRF | 3.14.6 (`.venv`) / 6.0.4 / 3.17.1 |
| Node / React | v24.19.0 / ^19.2.0 |
| Commits made | None. Nothing committed or pushed. |

Tracked changes (uncommitted): `CLAUDE.md` (scope amendment), `frontend/e2e/responsive.spec.ts`, `frontend/src/pages/masters/MasterList.tsx`, `frontend/src/pages/masters/TradesListView.css`, `backend/apps/license/management/commands/seed_browser_2509.py`, `backend/apps/license/tests/test_seed_browser_2509_command.py`, `frontend/e2e/item-pivot.sticky.spec.ts`, `scripts/test/run_data_bearing_browser_e2e.sh`.

Untracked (new): `.claude/skills/` (16 ECC skills), `backend/apps/license/tests/test_balance_semantics_d2_characterization.py`, `backend/apps/license/tests/test_item_pivot_authorization.py`, `docs/v1/`.

## Verified results this phase (exit codes read from logs)

| Check | Result |
| --- | --- |
| Frontend `lint`, `typecheck` (after the spec and harness edits) | exit 0 / exit 0 |
| Seed command tests (`test_seed_browser_2509_command.py`) | 3 passed, exit 0 |
| Item-pivot authorization (new) | 6 passed, exit 0 |
| Item-pivot related backend tests (selected by `-k pivot`) | 221 passed, exit 0 |
| Harness port-collision guard (default port 8000 occupied) | refuses, exit 2 |
| Sticky spec in default run (no harness) | skipped (guard), exit 0 |
| Sticky spec through isolated harness | **FAIL** — see E2E-001 |

Earlier-session results still stand (re-run dates in the test baseline): frontend 544 tests; canonical backend 237; licence/core 2714; full E2E 121 passed / 1 failed / 8 skipped (the one failure is E2E-001).

## Defects found and status

| ID | Severity | Status | Summary and evidence |
| --- | --- | --- | --- |
| HARNESS-001 | **P1** (data-safety) | **Fixed** | `run_data_bearing_browser_e2e.sh` defaults the backend to port 8000 and accepts any server answering its readiness probe. With a developer server on 8000, the browser suite would run against that server's database. Fix: refuse to start if either port is already listening; stop the readiness loop if the started backend exits. Verified: guard exits 2 on occupied port. |
| SEED-001 | P1 (fixture defect, hid a real query gap) | **Fixed** | `seed_browser_2509` created the `E2` purchase status but never assigned it to any licence. The Item Pivot base query requires a purchase status (`GE/MI/CO` by default), so the scenario returned zero rows. Fix: assign the status on create and update, for both primary and queue licences. Regression assertion added to the existing seed test. |
| E2E-001 | P1 | **Partially fixed; still failing** | Causes found: (1) seed purchase status (SEED-001); (2) the pivot opens on "Total Summary", and the per-notification sticky stack needs the `Notification 2509` tab (spec now selects it). Remaining failure: at middle scroll, the notification banner sits 3.375 px below the navigation bar, against a 2 px tolerance (`item-pivot.sticky.spec.ts:52`). Cause not isolated. The `ResizeObserver` already watches the navigation bar, so a stale height is not the explanation. **Tolerance not widened.** |
| E2E-001b | P2 (test policy) | **Open, decision needed** | The sticky spec is now guarded (`LM_REAL_E2E=1`), so default `npx playwright test` reports it as **skipped**, not failed. This follows the data-bearing spec's pattern, but it means the default suite no longer runs this assertion. Owner should confirm the policy, or require the harness run in CI. |
| A11Y-001 | P2 | **Open** | The five `MasterList.tsx` labels are fixed. The eight other `hidden sm:inline` files are not measured. |
| SEC-PIVOT-001 | P1 (D1, policy) | **Characterized, not changed** | `ReportPermission` is role-only. A `REPORT_VIEWER` receives licences from companies they were never assigned (`test_d1_current_behaviour_*`). Changing this needs owner decision D1. |
| D2 | P0 (semantics) | **Open, owner decision** | `calculate_balance` (non-hidden) vs `calculate_customs_balance` (includes hidden) vs financial; snapshot `customs_balance` uses the non-hidden formula. Characterization test pins current values. No formula changed. |

## Environment incident (not caused by a signal from this work)

- The development server that was listening on port 8000 at the start of the session (PID 55011, `manage.py runserver 127.0.0.1:8000`) **is no longer running**. No signal was sent to it by this work. Cause not verified. A plausible explanation is a restart by PyCharm's Django run configuration (`.idea/runConfigurations/Django__debug_runserver__8000_.xml`); this is an inference only.
- A different listener now holds port 8000 (PID 36405, parent PID 1, `runserver`). It was not started by this work. A second listener on `*:8000` (PID 36908) belongs to a different parent. Neither was touched.
- Disposable databases created by this work were dropped (`test_license_manager_browser_e2e_8edfc680`, `test_sticky_probe_20261031`, `test_sticky_probe2_20261031`). Other `test_*` databases on the server were not created by this work and were left alone.

## Artifacts

- `frontend/responsive-screenshots/*.png`: the 50 files written this session were removed. The directory is still not git-ignored. Recommendation: ignore it (tracked change, needs approval).

## Next actions, in order

1. Isolate the sticky geometry defect: measure `nav.top`, `nav.bottom`, banner and `.top-nav` computed styles at scroll 900, using a kept harness database. Fix the cause, or document it as a test-geometry issue, then decide on the skip policy (E2E-001b).
2. A11Y-001: measure the eight remaining files with axe, then fix only confirmed violations.
3. Phase 2 extreme-case matrix for the licence balance and pivot paths, using characterization tests first. Do not change formulas before D2 is decided.
4. Phase 4 security: negative tests for the remaining high-value routes (licence, allotment, BOE, trade, ledger, export) after the D1 decision. Until then, record them as blocked.
5. Phases 5–12 (backend and frontend hardening, deployment readiness, performance, final verification) not started.

## Owner decisions still required

D1 (company/object access), D2 (balance figure for `customs_balance` and `balance_difference`), E2E-001b (guard policy for the sticky spec), GIT-1 (commit and ignore decisions).
