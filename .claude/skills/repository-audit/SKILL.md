---
name: repository-audit
description: Read-only audit of the repo or one area (structure, hotspots, dead code, test gaps, risks). Use when asked to audit/assess code health.
metadata:
  origin: project
---
1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges. Area shape: grep the section in `.claude/index/CODE_MAP.md`.
2. State: `git status`, `git log --oneline -15`; environment: `sh scripts/dev/doctor.sh`.
3. Hotspots: largest/most-imported files (`wc -l`, count in `dependents.tsv`); ad-hoc root scripts (`backend/verify_*.py`, `trace_*.py`).
4. Test gaps: modules with no matching tests in `backend/tests/`, `backend/apps/*/tests/`, `frontend/src/**/*.test.*`.
5. Risks: business-rule code paths (`.claude/rules/business-rules.md`), permissions, raw SQL, secrets handling.
6. Broad sweeps → one `Explore` agent (haiku); never re-scan what the index answers.

**Output:** table `severity · area/file:line · finding · recommendation`. Read-only — no fixes unless asked; write to `docs/audit/` only if asked.
