# Agent roster, ownership and the shared contract

## ERP agents (queue-bound)

| Agent | Kind | Model (verified 2026-11-16) | Default scope (narrowed to exact `owned_files` per task) | Wraps protocol of |
|---|---|---|---|---|
| `erp-backend` | implementation | `sonnet` → claude-sonnet-5-5 | `backend/**` code + tests (no migrations unless owned) | `backend-engineer` |
| `erp-frontend` | implementation | `sonnet` | `frontend/src/**` | `frontend-engineer` |
| `erp-database` | implementation | `sonnet` | `backend/apps/*/migrations/**`, model/query files | `data-engineer` |
| `erp-security` | implementation | `sonnet` | auth/RBAC/settings hardening files | `security-auditor` (knowledge) |
| `erp-qa` | implementation (tests only) | `sonnet` | `**/tests/**`, `*.test.*`, fixtures | `qa-test-engineer` |
| `erp-performance` | implementation | `sonnet` | query/render hot paths | `performance-engineer` |
| `erp-architect` | **read-only** | `opus` → claude-opus-5-5 | none (plans only) | `solutions-/django-/react-architect` |
| `erp-reviewer` | **read-only** | `opus` | none (reviews) | `code-reviewer` |
| `erp-security-reviewer` | **read-only** | `opus` | none (reviews) | `security-auditor` |

Domain auditors usable as read-only queue reviewers: `cif-balance-auditor`, `boe-reconciliation-auditor`,
`invoice-auditor`, `dgft-dfia-rules-auditor`. Lookups/exploration: `code-explorer`/`Explore` on `haiku`.
Model aliases were verified by headless calls through the Central proxy (sonnet→claude-sonnet-5-5,
opus→claude-opus-5-5, haiku→claude-haiku-5-5). Fast mode is not assumed.

## Read-only enforcement (three layers — guard rails, not a sandbox)

1. `tools:` allowlist without Edit/Write/NotebookEdit, plus `disallowedTools`.
2. Agent-scoped `PreToolUse(Bash)` hook: `guard_bash.py --readonly` blocks redirection, `tee/touch/rm/mv/cp`,
   in-place `sed/perl`, git state changes (incl. `git -C`), migrations, installs, `orch.py add/transition/review/worktree create`,
   and `python -c` file writes. The guard also enters read-only mode if the hook payload carries
   `agent_type` ∈ {erp-reviewer, erp-security-reviewer, erp-architect}.
3. The orchestrator verifies after every review that the worktree diff did not change (`orch.py worktree verify`).
   A determined process could still write via an arbitrary script — Bash is not sandboxed.

## Shared contract (every implementation agent)

1. Work only in the task worktree `.claude/worktrees/T-NNN`; never in the parent checkout.
2. First and last command: `orch.py worktree verify T-NNN` (branch, base ancestry, nothing outside ownership).
3. Edit only `owned_files`. Need another file → stop and ask the orchestrator (it re-plans ownership).
4. Regression-first; targeted tests with `TEST_DB_NAME=<task test_database>` on local Postgres.
5. Decisions: read `.claude/state/decisions-snapshot.md`, then the canonical register rows. Open OD-11…OD-20
   → stop, `blocked-on: OD-NN`. Never invent financial rules.
6. No push/merge/rebase/reset/clean/stash-drop/worktree removal/dependency installs/non-local DB/secrets/
   deploy/customs-PDF deletion. Local commits on the task branch only if the brief says so.
7. Hand-off: files, tests, exact commands + output, assumptions, approvals needed.

## Ownership rules

- One owner per file at a time across all `running`/`review`/`integration` tasks (enforced).
- Directory claims (`path/`) and globs overlap with every file beneath them.
- A task that changes a symbol (signature, model field, serializer field) conflicts with tasks owning that
  symbol's dependents (`grep '^<file>' .claude/index/dependents.tsv`) → sequence with `depends_on`.
- One migrating task per Django app per round (`apps/<app>/migrations/` as an owned directory).
- Shared files that many tasks want (`urls.py`, `settings.py`, `package.json`, `components/ui/*`): give them
  to a single dedicated task or to the integrator.
- Parent-checkout uncommitted OD-06 files are owned by **nobody** until the owner commits them.
