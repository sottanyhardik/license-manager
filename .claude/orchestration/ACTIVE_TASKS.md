# Active tasks

The machine-readable source of truth is `.claude/state/queue.json` (`orch.py status`). This page records
what the queue can't see: externally-managed worktrees/sessions and their file claims. Update it at
DISCOVER time (`git worktree list`, `ListAgents`).

## Queue (at setup, 2026-11-16)

No ERP tasks queued. Approved base: `feature/version5` @ `e6dfc9b7cd74e0cdd485e90bbaa4c87e73011a31`.

## Externally managed worktrees (NOT created by orch.py — do not modify, do not remove)

| Path | Branch | HEAD | Created | Origin | State at setup |
|---|---|---|---|---|---|
| `../license-manager-implementation` | `feature/erp-implementation` | `e6dfc9b7` | 2026-11-16 08:57 | another concurrent Claude session (PyCharm ACP agent / terminal) | clean |
| `../lm-impl-boe-perf` | `feature/erp-impl-boe-perf` | `e6dfc9b7` | 2026-11-16 08:58 | same | clean |
| `../lm-impl-od02-customs` | `feature/erp-impl-od02-customs` | `e6dfc9b7` | 2026-11-16 08:58 | same | clean |
| `../lm-impl-od21-labels` | `feature/erp-impl-od21-labels` | `e6dfc9b7` | 2026-11-16 08:58 | same | clean |
| `../lm-impl-od07-apiv1` | `feature/erp-impl-od07-apiv1` | `e6dfc9b7` | 2026-11-16 (after 09:00) | same | appeared later in setup |
| `../lm-impl-od08-deadcode` | `feature/erp-impl-od08-deadcode` | `e6dfc9b7` | 2026-11-16 (after 09:00) | same | appeared later in setup |

Their names suggest in-flight work on OD-02 (`customs_available_cif`), OD-07 (`/api/v1/`), OD-08 (dead-code
removal), OD-21 (UNPLANNED label) and BOE performance. Before queuing a task touching those areas, check those worktrees' diffs
(`git -C ../lm-impl-od02-customs diff --stat e6dfc9b7`) and coordinate with the owner — two sessions must
not edit the same files.

## Stale branches (leftovers from native subagent isolation, no worktree attached)

| Branch | Tip | Based on | Note |
|---|---|---|---|
| `worktree-agent-a19bdca551906c320` | `22024f76` | `02f15724` (feature/version5 history) | 1 commit not on HEAD — owner to review/delete |
| `worktree-agent-a72f3b374274863a8` | `1a9a62ec` | `0c28a897` (**develop**) | evidence of the default-branch worktree issue — owner to review/delete |
