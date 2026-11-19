# AGENTS.md — License Manager (tool-agnostic agent instructions)

This file is for non-Claude coding agents (Codex, Cursor, etc.). **`CLAUDE.md` is the source of
truth.** Read it first; everything below just points into it. The previous version referenced a
non-existent `.Codex/` directory. Backup: `.claude/backups/2026-11-15-pre-ecc/AGENTS.md`.

- **Index first:** `grep -i "Name" .claude/index/symbols.tsv`, `grep '^path' .claude/index/dependents.tsv`,
  sections of `.claude/index/CODE_MAP.md`. Rebuild: `python3 .claude/index/build_index.py`.
- **Rules:** `.claude/rules/*.md`. Business-rule protection is in `business-rules.md`, safety boundaries in
  `safety.md`. The vendored ECC rules in `.claude/reference/ecc/` have lower precedence.
- **Role briefs:** `.claude/agents/*.md` (roster: `.claude/agents/README.md`).
- **Quality gates (mirror CI `.github/workflows/ci.yml`):** `sh scripts/dev/quality-gate.sh [frontend|backend|mds|mds-client|all]`.
- **Never:** push, merge, deploy, touch production/remote databases, or expose secrets without explicit human approval.
- **Docs generation mode:** `.claude/rules/documentation-mode.md`.
