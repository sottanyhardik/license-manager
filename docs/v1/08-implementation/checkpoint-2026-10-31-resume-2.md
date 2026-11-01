# Checkpoint — resume 2 (sticky geometry, accessibility, matrix, anonymous access)

Date: 2026-10-31 (IST). Predecessor: `checkpoint-2026-10-31-mission-phases-0-2.md`. Status: **in progress. Not production-ready.**

## Repository state at checkpoint

Branch `version-v1`, HEAD `d78c8b1d108368a9e48b26a05a50094dc930608d`, 3 stashes (unchanged). No commits. Tracked changes are listed under "Files changed". Untracked: `.claude/skills/`, `docs/v1/`, three new backend test files, one new Playwright spec, and two unattributed items (see "Open items").

## Verified results (exit codes and counts from logs)

| Check | Result |
| --- | --- |
| Sticky spec through isolated harness, `--repeat-each=3` | **3 passed**, exit 0 (before: 3/3 failed at the same assertion) |
| Shell and filter accessibility regression (new, guarded) | **1 passed**, exit 0 |
| Anonymous and role-less critical API tests (new) | **22 passed**, exit 0 |
| Item-pivot authorization (new) | 6 passed, exit 0 (earlier) |
| Item-pivot related backend (`-k pivot`) | 221 passed, exit 0 (earlier, before the latest frontend edits; backend code unchanged since) |
| Frontend lint / typecheck / unit (544) / build | exit 0 / exit 0 / exit 0 (544 passed, 78 files) / exit 0 |
| Full Playwright, **default mode** | **121 passed, 0 failed, 10 skipped**, exit 0 |
| Full Playwright, **isolated harness (all specs, guarded enabled)** | **124 passed, 4 failed**, exit 1 |

Default mode skips every guarded spec, so its exit code 0 is **not** evidence that the guarded tests pass. The harness run is the one that executes them.

## Defect register (this resume)

| ID | Severity | Status | Root cause and evidence |
| --- | --- | --- | --- |
| E2E-001 (sticky) | P1 → **resolved** | Fixed in the test | The layout is correct. The assertion measured the wrong box: the first tier's `<th>` is rowspan-ed across both tiers, so its height is the whole block. Measured tier-2 top 137.312 = first-tier top 109.312 + first-tier row height 28. The assertion now compares the tier-2 top with first.top + tier-one `<tr>` height. Tolerance unchanged (2 px). |
| E2E-001 negative control | Open | Not performed | The fixed assertion has not been shown to fail on a misaligned layout. Required before the fix is treated as proven. |
| HARNESS-002 | P1 → **fixed** | Default ports moved from 8000/41731 to 8011/41732 | Default port 8000 is the developer's backend; 41731 is Playwright's own webServer. Guard test: exit 2 when occupied. |
| A11Y-002 (shell) | P1 → **fixed** | Verified by the guarded regression | Quick-action labels and the brand text were `display:none` below 768/720/480 px, leaving icon-only controls without a name. Now visually hidden, so they keep their accessible name. |
| A11Y-003 (contrast, caption) | P2 → **fixed** | Verified | "License Manager" caption was `text-muted-foreground/40` at 1.85:1. Now full opacity. |
| A11Y-004 (contrast, filter tint) | P2 → **fixed** | Verified | Selected filter buttons were `#0066cc` on `#d9e8f7` at 4.46:1. Tint lightened to `/10`. |
| A11Y-005 (filter labels) | P1 → **fixed** | Verified by the guarded regression | `AdvancedFilter` rendered labels with no association to their controls, on every master list. Each control now has an id derived from its field name, and labels use `htmlFor`. Toggle and button groups use `role="group"`. `DebouncedAsyncSelect` gained an optional `inputId` prop. `DateRangeFilter` received ids from `AdvancedFilter`. |
| A11Y-006 (report filters) | P1 → **fixed** | Verified | Item-pivot company selects and item-report include/exclude selects had no name. Item-report editable row select now has an `aria-label`. |
| E2E-002 (download specs) | P2 → **partly fixed** | Test selector corrected; behaviour still fails | The UI label is "Include License Numbers"; the specs searched for "License Numbers". Corrected in three specs. They now fail later: the "Custom Ledger PDF" action is not present in the row for seeded licence 3411008090, so no download starts. **Unresolved product or fixture issue**, not diagnosed. |
| E2E-003 (PLAN queue) | P1, unresolved | Open | With the HEAD seed the test fails earlier (licence 3411009001 absent). With the corrected seed, it reaches the assertion that licence 3411009011 is hidden, and the page shows it. The expected queue size or ordering is not verified. **Not caused by the seed change**; the seed change is what makes the scenario reachable. |
| SEC-PIVOT-001 / AUTHZ-01 | P1, policy | Characterized | `ReportPermission` is role-only. Pinned by a test labelled as a characterization, not an approval. Needs D1. |
| VAL-02 | P2 | Open | A stale-schema request returned a raw database message in a 500 body. Not yet fixed or tested. |
| D2 | P0, semantics | Open | Unchanged. Characterization tests pin current values. |

## Files changed in this resume

- `frontend/e2e/item-pivot.sticky.spec.ts`: corrected the tier-alignment assertion. Tolerance unchanged.
- `frontend/e2e/shell-and-filter.accessibility.spec.ts` (new, guarded).
- `frontend/e2e/financial-ledger-invoices.spec.ts`, `package-download.spec.ts`, `custom-ledger-download.spec.ts`: label text corrected.
- `frontend/src/components/AdvancedFilter.tsx`: ids and label association, role groups, tint, and date-range ids.
- `frontend/src/components/DebouncedAsyncSelect.tsx`: optional `inputId`.
- `frontend/src/pages/reports/ItemPivotFilters.tsx`: company labels associated.
- `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`, `ItemReportTable.tsx`: labels and an aria-label.
- `frontend/src/styles/tailwind.css`, `frontend/src/theme/tabler.css`: visually hidden instead of `display:none` in three rules.
- `frontend/src/layout/AdminLayout.tsx`: caption contrast.
- `frontend/package.json`: added `test:e2e:isolated`.
- `scripts/test/run_data_bearing_browser_e2e.sh`: default ports 8011 and 41732.
- `backend/apps/license/tests/test_critical_api_anonymous_access.py` (new, 22 tests).
- `docs/v1/07-quality-and-operations/extreme-case-matrix.md` (new).

## Open items

1. **Negative control for the sticky assertion.** Show that the fixed assertion fails on a misaligned layout. Do this before treating E2E-001 as proven.
2. **E2E-002 and E2E-003.** Diagnose the "Custom Ledger PDF" action absence and the queue-size expectation. Both affect business workflows (downloads, allocation queue). Each needs data or product confirmation.
3. **Guard policy.** The sticky and shell-accessibility specs are skipped in default `npx playwright test`. They run only through `npm run test:e2e:isolated`, which needs CI or an owner decision to run.
4. **Unattributed untracked file:** `frontend/e2e/tsconfig.json`, created 21:40 during this session. Nothing references it. Left in place. Owner should confirm whether to keep it.
5. **Artifacts.** `frontend/responsive-screenshots/` is still not git-ignored. The PNGs this session generated were removed.
6. **Not started:** backend and frontend hardening beyond the fixes above, the financial concurrency tests (BAL-05, BAL-06 in the matrix), deployment and backup verification, performance measurement, and the full final verification report.

## Decisions required

- D1: company and object access policy.
- D2: balance figure for snapshot `customs_balance` and `balance_difference`.
- Guard policy for guarded specs (run in CI, or accept skipping by default).
- Whether to keep `frontend/e2e/tsconfig.json`, and whether to git-ignore `responsive-screenshots/`.

## Rollback

All changes are uncommitted. To revert one area, restore its file from `HEAD` after reviewing the diff. Do not use `git checkout -- .` or `git stash drop`: the three existing stashes and `docs/v1/` are user work.
