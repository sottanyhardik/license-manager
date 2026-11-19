---
name: ecc-guidelines
description: Generic ECC language guidelines (Python, TypeScript, React, web, common) — load ONLY when a task needs style/pattern/security/testing guidance beyond the project rules. Project rules in .claude/rules/ always win.
---

# ECC guidelines (on demand)

The vendored Everything-Claude-Code rules live in `.claude/reference/ecc/` and are **not auto-loaded** (they cost
~15 K tokens per session when they were path-scoped rules — owner decision 2026-11-19). Read only the file you need:

| Need | File |
|---|---|
| Python style / patterns / security / pytest | `.claude/reference/ecc/python/{coding-style,patterns,security,testing}.md` |
| TypeScript | `.claude/reference/ecc/typescript/{coding-style,patterns,security,testing}.md` |
| React components / hooks / tests / security | `.claude/reference/ecc/react/{coding-style,patterns,testing,security}.md` |
| CSS / HTML / web perf / design quality | `.claude/reference/ecc/web/*.md` |
| Cross-language review, perf, security checklists | `.claude/reference/ecc/common/*.md` |

Precedence: `CLAUDE.md` and `.claude/rules/*.md` (business rules, safety, backend, frontend) > ADRs > these files.
