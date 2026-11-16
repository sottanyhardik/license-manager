# Task template

Create tasks with `orch.py add` (it fills base SHA, branch, worktree path and test DB). This template is
the brief the orchestrator hands to the agent, and the checklist for the queue record.

```yaml
id: T-NNN                       # unique, T- + ≥3 digits
title: <imperative, one line>
agent: erp-backend              # erp-backend|erp-frontend|erp-database|erp-security|erp-qa|erp-performance
                                # read-only: erp-architect|erp-reviewer|erp-security-reviewer|<domain auditor>
skills: [django-backend, regression-first]
owned_files:                    # exact paths or dir/ prefixes; disjoint from every concurrently active task
  - backend/apps/license/services/x.py
  - backend/apps/license/tests/test_x.py
depends_on: [T-MMM]             # must be completed first
decision_refs: [OD-02]          # approved decisions honoured; open ones => state blocked
base_sha: <40-char SHA>         # defaults to queue approved_base.sha (owner-approved)
target_branch: orch/T-NNN
worktree: .claude/worktrees/T-NNN
test_database: test_lm_t_nnn    # TEST_DB_NAME for targeted tests, local Postgres only
acceptance_criteria:
  - <observable, testable statement>
review:
  status: not-started           # not-started|in-review|changes-requested|approved
  required: [erp-reviewer]      # + erp-security-reviewer / cif-balance-auditor / … as applicable
state: pending
```

## Agent brief (paste into the Agent call)

```
Task T-NNN — <title>
Worktree (work ONLY here): /Users/drushahardiksottany/PycharmProjects/license-manager/.claude/worktrees/T-NNN
Branch: orch/T-NNN   Base: <sha>   Test DB: TEST_DB_NAME=test_lm_t_nnn
Owned files (edit nothing else): …
Acceptance criteria: …
Decisions: OD-xx (read the register row). Open decisions you must not decide: …
Pointers: <file:line> …
Skills: …
First command: python3 /Users/drushahardiksottany/PycharmProjects/license-manager/.claude/orchestration/bin/orch.py worktree verify T-NNN
Hand-off: files changed, tests + command output, assumptions, anything needing owner approval.
Do not push, merge, rebase, remove worktrees, add dependencies or touch non-local databases.
```
