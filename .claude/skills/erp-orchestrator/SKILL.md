---
name: erp-orchestrator
description: Run an ERP change for the License Manager through the queued, worktree-isolated multi-agent lifecycle (DISCOVER → PLAN → DEPENDENCY ANALYSIS → APPROVAL CHECK → DELEGATE → IMPLEMENT → TARGETED TEST → REVIEW → INTEGRATE → FULL QUALITY GATE → OWNER APPROVAL). Use when the user invokes /erp-orchestrator or asks to orchestrate ERP feature/fix work with erp-* agents, file ownership and pinned worktrees.
argument-hint: <task description | "status" | "resume T-NNN">
metadata:
  origin: project
---

# /erp-orchestrator

## 1. Purpose
Deliver an owner-approved ERP change safely: every unit of work is a queue task with one agent,
explicit file ownership, a pinned base SHA, its own worktree and test DB, independent review, and a
single integrator. Policy docs: `.claude/orchestration/README.md` (start there).

## 2. Invocation criteria
- `/erp-orchestrator <request>` — substantial, multi-file or multi-agent ERP work.
- `/erp-orchestrator status` — run `orch.py status`, `orch.py validate`, `orch.py base-check`; report.
- `/erp-orchestrator resume T-NNN` — continue a queued task from its current state.
- Small tasks (a few tool calls, one file) → do directly; do not spin up the lifecycle.
- Not for: deploys, credential rotation, history rewrites, production data (owner-only).

## 3. Required context
`.claude/state/decisions-snapshot.md` (+ staleness check against the register) ·
`.claude/rules/business-rules.md` · `.claude/orchestration/{AGENT_OWNERSHIP,APPROVAL_POLICY,INTEGRATION_POLICY,ACTIVE_TASKS}.md` ·
`.claude/memory/README.md` · code index (`symbols.tsv`, `dependents.tsv` — grep only).

`ORCH="python3 .claude/orchestration/bin/orch.py"` (run from the main checkout).

## 4. Workflow
1. **DISCOVER** — restate the request + acceptance criteria. `$ORCH base-check`, `$ORCH status`,
   `git worktree list`. Read ACTIVE_TASKS.md for externally-managed worktrees/sessions and avoid their files.
   If business semantics are unclear → `licence-domain-expert` (read-only) or ask the owner.
2. **PLAN** — spawn `erp-architect` (read-only, opus) with the request and pointers. Get tasks with owned
   files, deps, agents, skills, decision refs, criteria.
3. **DEPENDENCY ANALYSIS** — `$ORCH add ...` each task (state `pending`), then `$ORCH validate`.
   For each pair intended to run in parallel: `$ORCH check-conflicts T-NNN`. Shared symbols (per
   `dependents.tsv`) ⇒ make them sequential with `--depends`.
4. **APPROVAL CHECK** — any task that touches an open decision (OD-11…OD-20), a business rule,
   API contract/permissions, migrations on large tables, dependencies, or anything in APPROVAL_POLICY.md
   → `transition blocked --note "needs owner: …"` and ask the owner **one question at a time**.
   Approved base SHA must be confirmed by the owner before the first DELEGATE of a session.
5. **DELEGATE** — for each `ready` task (`$ORCH transition T ready`): `$ORCH worktree create T`
   (pinned to the task base SHA — **never** use the Agent tool's `isolation: "worktree"`, which may branch
   from the default branch `develop`), then `$ORCH transition T running` (enforces deps, conflicts,
   ≤4 implementation agents, worktree verification).
   Spawn the agent (`subagent_type: erp-backend|erp-frontend|erp-database|erp-security|erp-qa|erp-performance`)
   with a brief: task ID, absolute worktree path, owned files, base SHA, test DB name, criteria,
   decision refs, relevant `file:line` pointers, skills to load. Launch independent tasks in one message.
6. **IMPLEMENT / TARGETED TEST** — agents work only in their worktree; on hand-off run
   `$ORCH worktree verify T` yourself (never trust the summary). Failure → back to the agent.
7. **REVIEW** — `$ORCH transition T review`; spawn `erp-reviewer` (+ `erp-security-reviewer` when
   security-relevant, + required domain auditor). Max 2 reviewers concurrently. Record verdicts with
   `$ORCH review T approved|changes-requested --reviewer <agent> --note "…"`. Changes → `transition T running`
   (max 3 rounds, then escalate).
8. **INTEGRATE** — `$ORCH transition T integration` (requires review approved). Follow
   INTEGRATION_POLICY.md: one task at a time onto the integration branch, never into the parent checkout's
   dirty tree, never into develop/master without owner approval.
9. **FULL QUALITY GATE** — once per integration batch, never concurrently:
   `sh scripts/dev/quality-gate.sh <areas>` (in the integration worktree). Report real output.
10. **OWNER APPROVAL** — `$ORCH transition T completed --note "<gate evidence>"` only after the gate; then
    produce the `/report`. Push/merge/deploy remain owner actions.

## 5. Restrictions
- No edits by the orchestrator to task-owned files while a task is active.
- Never: push, rebase, reset --hard, clean -f, history rewrite, remove worktrees, stash drop, deploy,
  non-local DB, print secrets, delete customs PDFs, bypass-permissions mode, invent business rules,
  decide OD-11…OD-20, touch the parent checkout's uncommitted OD-06 work.
- Concurrency: ≤4 implementation agents, ≤2 reviewers, 1 full gate, 1 migrating task per app.
- Text hooks are guard rails, not a sandbox — still review every diff.

## 6. Acceptance criteria
Every task `completed` has: worktree verify clean, targeted tests passing, reviewer APPROVE recorded,
gate evidence note, decision refs honoured; queue `validate` passes; no file edited outside ownership;
parent checkout's pre-existing changes untouched.

## 7. Verification commands
```
python3 .claude/orchestration/bin/orch.py validate
python3 .claude/orchestration/bin/orch.py base-check
python3 .claude/orchestration/bin/orch.py worktree verify T-NNN
python3 .claude/orchestration/bin/test_orch.py
python3 .claude/hooks/test_guard_bash.py
sh scripts/dev/quality-gate.sh backend|frontend|mds|mds-client|all
```

## 8. Documentation references
`.claude/orchestration/README.md` · `TASK_TEMPLATE.md` · `AGENT_OWNERSHIP.md` · `APPROVAL_POLICY.md` ·
`INTEGRATION_POLICY.md` · `CENTRAL_CLI.md` · `docs/claude/ORCHESTRATION.md` (general `/orchestrate`
flow — this skill is its queued, worktree-pinned ERP variant) · `docs/erp-transformation/12-decisions-register.md`.
