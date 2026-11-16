# Approval policy

Base policy: `.claude/rules/safety.md` (unchanged). This page adds the orchestration specifics and lists
what enforces what. **Text-pattern hooks are guard rails, not a security sandbox** — they stop the common
and accidental cases; diff review and owner approval remain the real controls.

## Owner approval required (in the current conversation, every time)

| Action | Enforcement |
|---|---|
| `git push` (any form) | `settings.json` deny `Bash(git push:*)` + `guard_bash.py` block |
| Merge into `develop`/`master`, rebase, cherry-pick, tag | `git rebase` denied + hook; merge/cherry-pick/tag = `ask` rules |
| `git reset --hard`, `git clean -f`, `checkout -- <path>`, `restore <path>`, `stash drop/clear` | deny + hook |
| History rewrite (`filter-branch/repo`, `commit --amend`, `rebase`, `reflog expire`, `update-ref -d`, `gc --prune`) | deny + hook |
| Removing worktrees (`git worktree remove/prune`) or deleting branches | deny + hook (`branch -D`), `branch -d` = ask |
| SSH/SCP/rsync/sftp, systemctl, deploy scripts | deny + hook |
| Any DB whose host isn't localhost/127.0.0.1 (`DB_HOST=`, `psql -h`) | hook |
| DROP/TRUNCATE, `flush`/`reset_db`, irreversible data migrations | deny + hook (SQL patterns) + review |
| Reading/printing secrets (`.env*`, `backend/.env_dgft`, keys, `tokens.enc`) | `Read` deny rules + hook |
| Credential cleanup (`central logout/uninstall/remove`, session export/import, running `force_password_reset` / `invalidate_all_sessions`) | deny + hook (central); management commands = policy + review |
| Deleting PDFs (customs documents) | hook (`rm/git rm … .pdf`) |
| New dependencies (`pip/npm/brew install`) | `ask` rules |
| Business-rule changes; deciding OD-11…OD-20; API contract/permission changes | policy + `erp-reviewer`/domain auditor + owner |
| Moving the approved base SHA | policy (orchestrator asks; `queue.json approved_base`) |

## Never

`--dangerously-skip-permissions` / bypass-permissions as a default (hook blocks the flag in commands) ·
disabling hooks to get past a block · using JetBrains Central (or any proxy/alternate auth) to bypass Claude
Code permissions · claiming a gate passed without running it.

**Note found at setup:** the setup session itself was running with bypass permissions active (not set by the
project: `settings.json` `defaultMode` is `acceptEdits`). In bypass mode `ask` rules are not prompted, which
is why push/rebase/worktree-removal were moved to **deny** rules + hook blocks. Start orchestration sessions
in the normal mode: `claude` (or `claude --permission-mode acceptEdits`).

## Autonomous (no approval)

Read/edit app code inside an assigned worktree's owned files; tests/lint/typecheck/builds; local test DB
migrations; `orch.py` queue operations; creating pinned worktrees; local commits on `orch/T-NNN` branches when
the owner asked for the work.

## Escalation

Agent → orchestrator → owner. Always escalate: open decisions, business-rule contradictions (never fix
unilaterally), API/permission changes, three failed review rounds, gates that cannot run, anything above.
