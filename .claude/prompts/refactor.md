# Prompt — Refactor (no behavior change)

Copy, fill the blanks, and run.

---

**Target**: <file / module / component to refactor>
**Goal**: <readability | dedupe | decomposition | perf — pick one>
**Out of scope**: behavior, API contracts, auth, data flow (must stay identical)

Rules:
1. Read `.claude/rules.md` and the layer rule(s) in `.claude/rules/*` before touching code.
2. **Preserve business logic.** No change to API calls, responses, auth, or rendered behavior.
   If a behavior change seems necessary, **stop and flag it** — don't bundle it in.
3. Reuse existing utilities/primitives; remove dead code and unused imports as you go.
4. Keep the diff focused — one refactor concern at a time.
5. Log any non-obvious decision in `.claude/memory/decisions.md`.

Verification (behavior parity):
- Frontend: `lint` → `typecheck` → `build` all green; UI visually unchanged.
- Backend: `pytest` green (existing tests are the parity guard; add one if coverage is thin).

Definition of done:
- [ ] No behavior change (or change explicitly flagged + approved).
- [ ] Quality gate green.
- [ ] `.claude/checklists/pr.md` passed.
