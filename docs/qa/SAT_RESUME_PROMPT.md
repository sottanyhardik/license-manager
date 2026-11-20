# SAT resume prompt (paste into a fresh Claude Code session)

Resume the License Manager System Acceptance Test (SAT). This is test, investigate and document only: no commits, push,
migrations (except inside the disposable DB of `scripts/test/run_data_bearing_browser_e2e.sh`, owner-approved),
stash/reset/restore, fixes or business-rule changes, and no writes to `lmanagement`.

1. `git branch --show-current` must print `feature/v5`. `git diff | shasum | cut -c1-12` was `6f1712e03000` during the
   SAT. If it differs, peers changed code: record the new hash and note which results may be stale. Preserve the 178
   peer paths and never edit them. SAT-owned files: `docs/qa/SAT_*.md` and `frontend/e2e/sat-*.spec.ts` only.
2. Read `docs/qa/SAT_EXECUTION_STATE.md`. It is the source of truth. Do not redo any ID with status PASS, PASS-EXC or
   FAIL that has evidence. Evidence lives in **`~/lm_sat_evidence/<phase>/`**. `/tmp/sat/` was wiped once; never use it again.
3. Check what is still running first: `ps aux | grep -E "pytest|playwright|vite|runserver"`,
   `lsof -iTCP:8000 -iTCP:41731 -sTCP:LISTEN`, and the `ListAgents` tool. Never start a second copy.
4. For each workstream in the state file without a finished report (`SAT_API_DATABASE_AUDIT.md`,
   `SAT_SECURITY_PERFORMANCE.md`, `SAT_UI_UX_AUDIT.md`, `SAT_INDEPENDENT_REVIEW.md`), relaunch only that one with the
   same brief: ownership, read-only `lmanagement`, `TEST_DB_NAME=test_lmanagement_sat_<api|sec|rev>`, evidence under
   `~/lm_sat_evidence/`.
5. Merge new findings into `SAT_DEFECT_REGISTER.md` (SAT-DEF-nnn) and `SAT_USER_DECISION_REGISTER.md` (DEC-nn). Run the
   Phase 9 independent review (fresh Opus agent, given the evidence rather than the conclusions). Then write
   `SAT_FINAL_ACCEPTANCE_REPORT.md`.
6. **Status at 2026-11-20 ~19:45 IST:**
   - All 9 phases are assessed and `SAT_FINAL_ACCEPTANCE_REPORT.md` is written (PARTIALLY COMPLETE).
   - Remaining executable items, all on the browser harness only (`PYTHON_BIN=backend/.venv/bin/python LM_REAL_E2E=1 scripts/test/run_data_bearing_browser_e2e.sh <spec> --workers=1`):
     - SAT-INT-002 licence form writes;
     - SAT-INT-008 and INT-011 write paths;
     - SAT-INT-009 transfer;
     - SAT-INT-010 BOE PDF upload;
     - E2E sort, delete-confirm and dialog focus trap;
     - SAT-INT-004 in the browser, after adding a pending (non-BOE) allotment through the API in the spec.
   - Extend `frontend/e2e/sat-int-boe.spec.ts` or add new `sat-*.spec.ts` files. Then update the registers and §9 of the final report.
   - Trade verification on real data needs a production-shaped read-only copy (owner).
7. Never claim a test passed without its log and exit code. Mark blocked tests BLOCKED, with the reason and the
   alternative check that was run.
