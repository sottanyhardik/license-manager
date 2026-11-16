# Safety & autonomy boundaries (always applies)

Enforced by `.claude/settings.json` permissions + `.claude/hooks/guard_bash.py` and
`.claude/hooks/pre_commit_check.py`; this file is the policy (details: `docs/development-environment/HOOKS-AND-PERMISSIONS.md`).

**Autonomous (no approval needed):** read/edit application code (only for explicitly requested changes),
tests, docs, config under `.claude/`; run tests/linters/typecheck/builds/dev servers; `makemigrations`;
create plans and reviews; create/remove temporary clean git worktrees;
`git status/diff/log/branch/add/commit/worktree`, `git stash list/show` on a feature branch.

**Prompts every time (settings `ask`):** `manage.py migrate` (local dev/test DB only — `DB_HOST` =
localhost/127.0.0.1; Claude cannot verify the target without reading secrets), `rm`, `git restore`/`checkout --`,
`git stash` push/pop/drop, `psql`/`redis-cli`/`docker`, `gh api`/PR/issue creation.

**Requires explicit human approval in the current conversation:** `git push`, merge/rebase into
`develop`/`master`, `git reset --hard`, `git clean -f`, force-anything, branch deletion; any deploy
(`backend/deploy/**`, `scripts/deploy*`, ssh/scp/rsync to servers, systemctl/nginx); any command whose
DB target is not local; `pip install`/`npm install` of *new* dependencies; dropping/truncating tables,
bulk deletes, irreversible data migrations.

**Never:** print, copy, or commit secrets (`.env*`, `backend/.env_dgft`, keys, tokens); use
`--dangerously-skip-permissions` / `bypassPermissions` as a default; disable hooks to get past a block;
claim a gate passed without running it.
