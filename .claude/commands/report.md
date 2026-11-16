---
description: Produce the final task report (short format by default; `full` for orchestrated/multi-agent work)
argument-hint: "[full]"
---
Use only facts verified in this session. Default (short) format — nothing else:

- **Status:** Completed / Blocked (one line; if Blocked, the blocker)
- **Changes:** files changed + one line each on what changed
- **Tests:** gates/tests actually run → Pass / Fail / NOT RUN + reason (never imply a skipped gate passed)
- **Remaining:** only genuine outstanding items (omit the line if none)

Mandatory flags, added as extra lines only when they apply: `BUSINESS-RULE CHANGE: …`,
`API CONTRACT CHANGE: …`, `SCHEMA/MIGRATION: …`, `PERMISSION CHANGE: …`.

If `$ARGUMENTS` is `full` (substantial/orchestrated work), additionally include: reviews
(reviewer → verdict → blocking findings resolved), quality-gate table, risks/escalations,
and git commands the human may want to run (never run push/merge yourself).
