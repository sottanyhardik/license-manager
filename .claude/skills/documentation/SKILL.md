---
name: documentation
description: When and how to document changes in docs/ (proportionate, accurate, index-backed). Use after significant changes or when asked for docs.
metadata:
  origin: project
---
Docs rules: `.claude/rules/documentation-mode.md` (auto-loaded in `docs/**`). Specialists: `technical-writer`, `architecture-documenter`.

- Trivial change → no docs. Behaviour/API/schema change → update the matching numbered doc (`docs/01…10-*.md`). Architectural decision → short record in `docs/decisions/`.
- Every claim backed by code: cite `file:line`. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
- Diagrams: Mermaid, in the doc that uses them.
- Durable project facts/decisions → `.claude/memory/` via `/remember` (one line, no duplicates).
- Keep it short: what changed, why, how to verify.
