# Codex Stateful Audit

This directory contains the persistent state for the repository-wide audit.

- `build_audit_state.py` rebuilds the audit layer from the current repository state and the existing `.claude/index` graph.
- `repository-knowledge-graph.json` records graph summaries and impact-analysis rules.
- `audit-database.json` records every tracked file with checksum, audit status, metrics, and quality scores.
- `work-queue.md` records prioritized engineering work.
- `dashboard.md` records the live progress dashboard.

Workflow:

1. Use `.claude/index` to find symbols and blast radius.
2. Audit only files marked `NOT_STARTED` or `REQUIRES_RECHECK`.
3. After an edit, re-run this generator and affected tests/lint/type checks.
4. Do not mark a file `COMPLETED` unless its relevant verification has passed.
