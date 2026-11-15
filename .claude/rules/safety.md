# Safety & autonomy boundaries (always applies)

Enforced by `.claude/settings.json` permissions + `.claude/hooks/guard-bash.sh`; this file is the policy.

**Autonomous (no approval needed):** read/edit application code, tests, docs, config under `.claude/`;
run tests/linters/typecheck/builds/dev servers; local migrations against the local dev/test DB
(`DB_HOST` = localhost/127.0.0.1 only); create plans and reviews; create/remove temporary git worktrees;
`git status/diff/log/branch/add/commit/stash/worktree` on a feature branch.

**Requires explicit human approval in the current conversation:** `git push`, merge/rebase into
`develop`/`master`, `git reset --hard`, `git clean -f`, force-anything, branch deletion; any deploy
(`backend/deploy/**`, `scripts/deploy*`, ssh/scp/rsync to servers, systemctl/nginx); any command whose
DB target is not local; `pip install`/`npm install` of *new* dependencies; dropping/truncating tables,
bulk deletes, irreversible data migrations.

**Never:** print, copy, or commit secrets (`.env*`, `backend/.env_dgft`, keys, tokens); use
`--dangerously-skip-permissions` / `bypassPermissions` as a default; disable hooks to get past a block;
claim a gate passed without running it.
