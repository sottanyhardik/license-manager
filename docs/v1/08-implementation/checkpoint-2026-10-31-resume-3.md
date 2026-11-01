# Checkpoint — resume 3 (E2E-002 / E2E-003, harness isolation)

Date: 2026-10-31 (IST). Predecessor: `checkpoint-2026-10-31-resume-2.md`. Status: **in progress. Not production-ready.** Full isolated harness: 129 passed, 1 failed (exit 1).

## Repository state
Branch `version-v1`, HEAD `d78c8b1d`, 3 stashes unchanged. No commits. Tracked `artifacts/` unchanged. Untracked and preserved: `.claude/skills/`, `docs/v1/`, `frontend/e2e/tsconfig.json` (origin unattributed; no config references it), new backend tests, `frontend/e2e/shell-and-filter.accessibility.spec.ts`.

## Verified results (exit codes from logs)
| Check | Result |
| --- | --- |
| Full isolated harness (all specs, guarded enabled) | **129 passed, 1 failed**, exit 1 |
| Failed test | `data-bearing.real.spec.ts:124` persisted routes: licence 3411008090 not visible on `/licences` (page shows "11 records"). Open. |
| PLAN queue (`data-bearing` PLAN test) | 1 passed, exit 0 |
| Custom ledger PDF | 1 passed, exit 0 (PDF `%PDF-` verified, in git-ignored output) |
| Ledger Excel export (replaces merged-PDF check) | 1 passed, exit 0 |
| Package workflow, blocked-path contract | 1 passed, exit 0 (positive PDF not verified) |
| Backend available-licenses plan-mode + filters | 25 passed, exit 0 |
| Frontend `AllotmentAction.test.tsx` | 14 passed, exit 0 |
| Orphan harness workers after run | 0 |

## Root causes and dispositions
- **E2E-003 PLAN queue:** stale test assumption. Product page size 25 is deliberate (commit `128417fd`). Corrected spec. Product unchanged.
- **E2E-002 custom ledger:** stale locator name and stale filename. Product's per-row button given an explicit aria-label. Endpoint filename contract `{license_number}.pdf` kept.
- **E2E-002 merged PDF (obsolete):** the control was replaced by the Download Package workflow in commit `79a08ac2`. Two specs replaced: Excel export (passes), and package blocked-path (passes).
- **Package blocked by readiness gate (product working as designed):** the seeded licence lacks purchase documents and final-party invoices. Making a positive PDF test requires a complete fixture; not built, and not a seed change made to satisfy a test.
- **Harness defect (fixed):** test jobs were routed to the developer's Redis db 0 with no worker. Harness now uses a dedicated Redis index (default 7), a harness-owned Celery worker, and clears only the verified-empty index. Orphan-worker cleanup defect (subshell PID) fixed.

## Open items
1. Persisted routes failure (`data-bearing.real.spec.ts:124`): diagnose pagination / default filter / seed state for licence 3411008090 on `/licences`.
2. Positive package PDF path: needs a seeded licence with complete documents (fixture design needs owner input on what counts as complete).
3. Developer broker db 0 key count rose across the session (2082 → 2376); attribution not established. Harness no longer writes to db 0.
4. Sticky-header negative control, extreme-case matrix updates, and D1/D2 implementation (Phases 3–4 of the master plan) not started in this resume.
5. Unattributed `frontend/e2e/tsconfig.json` kept pending owner decision.

## Next highest-priority task
Diagnose open item 1 (one data-bearing test failing; the only remaining red test in the isolated suite), then proceed to D1 authorization tests.
