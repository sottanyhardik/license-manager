---
description: Record a durable project fact or decision in .claude/memory/
argument-hint: <fact or decision>
---
Record: $ARGUMENTS
- Decision (a choice with rationale) → append to `.claude/memory/decisions.md` as `## YYYY-MM-DD — title` with Context / Decision / Why.
- Domain fact → `.claude/memory/domain.md`; frontend fact → `components.md`/`project.md`.
- Check for an existing entry first and update it instead of duplicating. Don't store things derivable from code or git history, and never store secrets.
