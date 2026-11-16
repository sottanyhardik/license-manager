---
name: git-workflow
description: Branching, commit and safety conventions for this repo. Use for any git operation, commits, worktrees or PR prep.
metadata:
  origin: project
---
- Integration branch `develop`; production `master`; work on `feature/*` (current pattern) branched from `develop`.
- Commit messages: conventional style seen in history — `feat(scope): …`, `fix(scope): …`, `chore(scope): …`, `docs(…)`. One logical change per commit; never commit unrelated files (e.g. `.DS_Store`).
- Commit only when the user asked for the work; the `pre_commit_check.py` hook blocks secrets/syntax errors and reminds about gates.
- **Ask first:** `git push`, merge/rebase into `develop`/`master`, reset, cherry-pick, tag, branch deletion, PR creation. **Never:** force push, `reset --hard`, `clean -f`, history rewrite (hook-blocked).
- Never stash, reset, checkout-over or discard the user's uncommitted changes.
- Parallel agents that could touch the same files → `isolation: "worktree"` (worktrees under `.claude/worktrees/`); remove only your own clean worktrees.
- PRs: `gh pr create --base develop` (asks first); body ends with the Claude Code attribution line.
