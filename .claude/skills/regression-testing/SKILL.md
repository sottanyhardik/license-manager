---
name: regression-testing
description: Choose and run the right regression tests after a change (targeted → area → full), separating pre-existing failures. Use before reporting a change as done.
metadata:
  origin: project
---
1. Changed files: `git diff --name-only` (+ untracked). Callers: `grep '^<path>' .claude/index/dependents.tsv`.
2. Run targeted tests for changed code and its direct callers first.
3. Then the area gate: `sh scripts/dev/quality-gate.sh backend|frontend|mds|mds-client` (mirrors CI).
4. A failure that looks unrelated → confirm on the base commit in a temporary worktree before calling it pre-existing; report it separately, never hide it.
5. Don't re-run checks that already passed unless code changed since.
6. Gates that could not run (no Postgres/toolchain) → report NOT RUN + reason (exit 3 ≠ pass).

**Output:** `Tests: <targeted> Pass/Fail · <gate> Pass/Fail/NOT RUN` + pre-existing failures listed separately.
