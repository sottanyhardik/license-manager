# Integration policy

1. **Single integrator** — the main orchestrator session (opus). Implementation agents never merge.
2. **Integration branch in its own pinned worktree** — never integrate into the parent checkout while it
   holds uncommitted owner work (OD-06 at setup time):
   ```
   git worktree add -b orch/integration-<YYYYMMDD> .claude/worktrees/integration-<YYYYMMDD> <approved_base_sha>
   ```
3. **Preconditions per task** — `review.status == approved`, `orch.py worktree verify T` clean, targeted tests
   passed, then `orch.py transition T integration`.
4. **One task at a time**, in dependency order: `git -C <integration-wt> merge --no-ff orch/T-NNN`
   (merge is an `ask` rule → owner sees each one). Conflict → stop; never resolve a conflict in a file that
   another task owns without re-review; re-run that task's targeted tests after each merge.
5. **Migrations** — after each merge run `python manage.py makemigrations --check --dry-run`; numbering
   conflicts are fixed by the owning `erp-database` task, not by hand-editing.
6. **Full quality gate** — once per batch, not concurrently with any other gate/build:
   `sh scripts/dev/quality-gate.sh <areas>` in the integration worktree. Record real output.
   Exit 3 means a gate could not run — report it as NOT RUN, not as passed.
7. **Close out** — `orch.py transition T completed --note "<gate result, commit>"`; `/report`.
8. **Owner actions only** — merging the integration branch into `feature/*`/`develop`/`master`, pushing,
   opening PRs, deploying, removing worktrees and deleting `orch/*` branches.
9. **Failure** — `orch.py transition T failed --note …`; the task branch and worktree are kept for diagnosis.
