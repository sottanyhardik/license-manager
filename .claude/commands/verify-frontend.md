---
description: Run the frontend quality gate (lint → typecheck → build) from frontend/
---

Run the frontend quality gate in order and report results. Stop at the first failure and
show the relevant output:

1. `cd frontend && npm run lint`
2. `cd frontend && npm run typecheck`
3. `cd frontend && npm run build`

This is the must-pass gate before declaring any frontend change done (see `.claude/rules.md`
and `.claude/checklists/pr.md`). Do not modify source to "fix" failures without explaining the
cause first. Summarize pass/fail per step at the end.
