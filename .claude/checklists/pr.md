# Checklist — Pull Request

Run before opening/merging any PR. PRs target **`develop`** (feature branches → `develop`).

## Code

- [ ] Followed `CLAUDE.md` §3 routing — loaded the right rules/context before coding.
- [ ] Reused existing utilities/primitives/base classes; no duplicated component or logic.
- [ ] No dead code, no unused imports, no stray `console.log`/`print`.
- [ ] Business logic, API contracts, and authorization unchanged (or change flagged for review).

## Gates

- [ ] Frontend: `cd frontend && npm run lint` clean.
- [ ] Frontend: `npm run typecheck` clean (no new `any`).
- [ ] Frontend: `npm run build` succeeds.
- [ ] Backend: `pytest` (or `./run-tests.sh --fast`) green.
- [ ] New endpoint/bugfix has a test (`@pytest.mark.api` / regression test).

## Docs & hygiene

- [ ] Updated `docs/` and/or `.claude/context/*` if architecture/API/DB/business rules changed.
- [ ] Logged any non-obvious decision in `.claude/memory/decisions.md`.
- [ ] No secrets committed; no `.env*` tracked.
- [ ] Diff is focused — one concern per PR.

If auth, permissions, input handling, file upload, or secrets were touched → also run
`.claude/checklists/security.md`.
