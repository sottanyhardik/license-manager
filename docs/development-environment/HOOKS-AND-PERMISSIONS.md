# Hooks and permissions

Source of truth: `.claude/settings.json` (committed) and `.claude/rules/safety.md` (policy).
All hooks are pure stdlib Python or POSIX sh. None of them deploy, delete or touch databases.

## Hooks

| Event | Script | What it does | Blocks? |
|---|---|---|---|
| SessionStart | `.claude/index/hook_session.sh` | Incremental code-index rebuild (output goes to a log, not to context) | no |
| SessionStart | `.claude/hooks/session_start.sh` | Injects 2 lines: branch, uncommitted count, scope rule | no |
| PreToolUse (Bash) | `.claude/hooks/guard_bash.py` | Blocks force push, `reset --hard`, `clean -f`, `branch -D`, discard-all, history rewrite, `rm -rf` of root/home/repo, permission bypass, ssh/scp/rsync, service control, deploy scripts, DROP/TRUNCATE, `manage.py flush`, secret-file reads, env dumps, `curl \| sh`, non-local `DB_HOST` | exit 2 |
| PreToolUse (Bash) | `.claude/hooks/pre_commit_check.py` | Only on `git commit`: blocks staged secret files, token/private-key material and Python syntax errors; reminds you to run gates and review when app files are committed | exit 2 |
| PostToolUse (Edit/Write) | `.claude/index/hook_postedit.sh` | Re-indexes the edited file | no |
| PostToolUse (Edit/Write) | `.claude/hooks/post_edit_validate.py` | Syntax-checks `.py` and `.json` files (JSONC tsconfig skipped). **Never reformats.** The repo has no formatter config, and silent rewrites could clobber user edits | reports error to Claude |
| Stop | `.claude/hooks/stop_verify_reminder.py` | Shows one reminder per distinct diff state when backend/frontend/MDS files changed: run `/quality-gate`, `/review-diff`, `/report` | never |
| SessionEnd | `.claude/hooks/session_end.sh` | Appends a one-line session record to `.claude/memory/session-log.md` (git-ignored) | no |

The full gate suite is **not** run inside a hook, because it needs Postgres and takes minutes.
Gates are enforced by policy (CLAUDE.md §4), the commit reminder and the Stop reminder.
There are no git-level hooks (`.git/hooks`); human commits from PyCharm are not intercepted.

Self-tests: `python3 .claude/hooks/test_guard_bash.py` (31 cases) and `python3 .claude/hooks/test_hooks.py` (14 cases).

## Permissions

`defaultMode: acceptEdits` (file edits apply without prompting). `disableBypassPermissionsMode: "disable"`
means bypass mode cannot be turned on for this project.

| Bucket | Examples |
|---|---|
| **allow** (no prompt; routine, reversible) | Read/Edit/Write; git status/diff/log/show/branch/switch/add/commit/worktree/fetch, `git stash list/show`; ls/grep/rg/find/cat/head/tail/mkdir/cp/mv/touch; pytest, `manage.py check/makemigrations/showmigrations` (also via `python3`, `.venv/bin/python`, `backend/.venv/bin/python`, MDS venv); `npm run …`, `npm ci`, vitest/tsc/eslint/playwright; quality-gate/doctor; read-only `gh pr/run` views; read-only PyCharm MCP tools |
| **ask** (prompts every time) | `git push/merge/rebase/reset/restore/checkout --/cherry-pick/tag`, branch delete, forced worktree removal; `gh pr create/merge/comment`, `gh issue create`, `gh api`, `gh release`; `pip/npm/brew install`, `npm uninstall/publish`; `docker`, `psql`, `dropdb/createdb/pg_restore`, `redis-cli`; `manage.py migrate/loaddata/shell/dbshell`; `rm`; PyCharm SQL execution, data import and run configurations |
| **deny** | force push (incl. `--force-with-lease`), `reset --hard`, `clean -f`, `filter-branch`, ssh/scp/rsync, `manage.py flush/reset_db`; reading `.env`, `.env.local`, `.env.production`, `.env_dgft`, `*.pem`, `*.key`, `~/.ssh/**` |

Unlisted Bash commands prompt under `acceptEdits`. The guard hook runs before any permission rule,
so a blocked pattern stays blocked even if it is allowed.

**Why `migrate` asks:** Claude cannot see which DB `backend/.env` points at without reading a secret.
Approve it only when you know the target is the local dev/test DB.

## Changes made 2026-11-16
- Added hooks: `pre_commit_check.py`, `post_edit_validate.py`, `session_start.sh`, `stop_verify_reminder.py`, plus `test_hooks.py`.
- Permissions:
  - added `disableBypassPermissionsMode`
  - `git stash` narrowed to list/show
  - `migrate` moved to ask
  - added ask rules for destructive file, DB and GitHub-write commands
  - added glob secret-read denies
  - added more routine allows to reduce prompts
