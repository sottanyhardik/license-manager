# Autonomous execution workflow (always applies)

Owner rule, 2026-11-17. Complements `CLAUDE.md` §2a (scope) and `safety.md` (boundaries);
when they conflict, `safety.md` wins. Autonomy applies **inside an explicitly requested
task** — it never widens scope or invents features.

## Start of every task
1. Read `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md` (printed at SessionStart) and continue
   from its **Last verified checkpoint**. Do not redo work it records as verified.
2. Check for already-running work before launching anything: `ListAgents`, background
   tasks, and processes on the ports/DBs you need (e.g. `lsof -iTCP:41731`, the
   `TEST_DB_NAME` you intend to use). Never start a duplicate of a running gate/workflow —
   wait for its completion notification instead.

## Execution loop (no repeated prompts needed)
implement → focused test → fix → module regression (once) → document → checkpoint.
- Wait for running commands/gates to finish (background + notification; never poll-sleep).
- Capture exit codes and log files (job tmp dir); read the failing lines, fix routine
  failures (test pins, lint, types, imports) and rerun **only** the affected tests.
- Full gates (`scripts/dev/quality-gate.sh backend|frontend`) run **once** per integration,
  not after every change. Reuse passing results for unchanged code; rerun only what a
  change can invalidate. Docs-only changes never trigger test runs.
- Each concurrent pytest runner uses its own `TEST_DB_NAME=test_lmanagement_<purpose>`.
- Minimal prompts, minimal diffs, existing architecture and shared components; no new
  dependencies.

## Checkpointing
After each verified milestone update the tracker: task, phase, commits, files, test
evidence (real numbers + exit codes), open findings, blockers, next action. Record only
real figures (tokens/cost/test counts) — never estimates.

## Ask the owner only for
destructive or irreversible operations, production/deploy actions, `git push`, remote or
production databases, new dependencies, and business-policy decisions (anything touching
canonical CIF/balance rules, permissions semantics, or financial data). Everything else
that is routine and reversible within the requested task: proceed.

## Never
destroy data, reset/clean/force anything, discard or overwrite other sessions' or the
user's uncommitted work, push, deploy, or claim a gate passed without its exit code.
