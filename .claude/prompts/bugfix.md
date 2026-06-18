# Prompt — Bug Fix

Copy, fill the blanks, and run.

---

**Bug**: <observed behavior>
**Expected**: <correct behavior>
**Repro**: <steps / endpoint / page>
**Suspected area**: <file or app, if known>

Process:
1. **Reproduce first.** Confirm the failure before changing anything.
2. Read the rule for the touched layer (`.claude/rules/*`) and relevant `.claude/context/*`.
3. **Find root cause**, not the symptom. Trace data flow; cite `file:line`.
4. **Write a failing regression test** (`.claude/templates/test.md`) that captures the bug.
5. Apply the **minimal** fix that makes the test pass. No drive-by refactors.
6. Re-run the test + the surrounding suite.

Watch for domain traps:
- Materialised balances change via the signal/recalc path, not direct field edits.
- `frozen` BOE rows are immutable.
- JWT refresh/401 handling is centralized in `frontend/src/api/axios.js`.

Definition of done:
- [ ] Regression test fails before, passes after.
- [ ] Quality gate green.
- [ ] `.claude/checklists/pr.md` passed.
