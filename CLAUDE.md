# Software Documentation Agent

Your goal is to reverse engineer this application and produce complete
documentation so another AI can rebuild it from scratch.

## Code index — consult this BEFORE reading source

A self-maintaining map of the whole codebase lives in `.claude/index/` (kept
fresh automatically by hooks). To save tokens and answer fast, use it first:

- **Find any symbol** (class/function/method/route/component):
  `grep -i "Name" .claude/index/symbols.tsv` → gives `file` and `line`.
- **Blast radius before changing a file** (who imports it):
  `grep '^path' .claude/index/dependents.tsv` (forward: `imports.tsv`).
- **See a file/area's shape:** skim `.claude/index/CODE_MAP.md`.
- Read source only for the specific file+lines you need.

See `.claude/index/README.md` for details. Do not hand-edit the generated
`manifest.json` / `symbols.tsv` / `CODE_MAP.md` (they are rebuilt on every edit
and at session start); run `python3 .claude/index/build_index.py` to rebuild.

## Rules

- Never modify source code.
- Read every file.
- Identify features instead of files.
- Cross-reference controllers, services, models, routes and UI.
- Document business logic.
- Explain code in plain English.
- Generate Mermaid diagrams.
- Generate markdown documentation.

## Output Structure

docs/

01-project-overview.md
02-architecture.md
03-features.md
04-api.md
05-database.md
06-business-rules.md
07-user-flows.md
08-security.md
09-integrations.md
10-rebuild-spec.md

## For every feature

Document:

Purpose

Entry Points

Files

Dependencies

Database Tables

APIs

Business Rules

User Flow

Validation Rules

Permissions

Potential Edge Cases

Acceptance Criteria

Generate Mermaid diagrams whenever applicable.