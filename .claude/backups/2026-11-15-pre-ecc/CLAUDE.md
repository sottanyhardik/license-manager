# Software Documentation Agent

Your goal is to reverse engineer this application and produce complete
documentation so another AI can rebuild it from scratch.

## Code index — MANDATORY: consult BEFORE reading or editing any source

A self-maintaining map of the whole codebase lives in `.claude/index/`. It is
rebuilt automatically at **zero chat-token cost**: the `SessionStart` hook
re-scans changed source at the start of every chat, and the `PostToolUse` hook
refreshes it after every edit. The index is therefore always current, but it is
**not** dumped into context (that would waste ~7k tokens/session) — you read it
on demand with `grep`, paying only for the few lines you actually look up.

**Rule for every chat AND every subagent:** before you read or edit any source
file — and before you answer a question about the code — orient yourself from the
index first (grep it), then open source only for the specific file+lines you
actually need. Never dive straight into source without checking the index. This
applies to all specialist agents, not just the main chat.

How to use it (the tables are for `grep`, never read them whole):

- **Find any symbol** (class/function/method/route/component):
  `grep -i "Name" .claude/index/symbols.tsv` → gives `file` and `line`.
- **Blast radius before changing a file** (who imports it):
  `grep '^path' .claude/index/dependents.tsv` (forward: `imports.tsv`).
- **See a file/area's shape:** skim `.claude/index/CODE_MAP.md` (grep or read the
  relevant section only — don't read the whole file unless you need to).
- Read source only for the specific file+lines you need.

See `.claude/index/README.md` for details. Do not hand-edit the generated
`manifest.json` / `symbols.tsv` / `CODE_MAP.md` (they are rebuilt on every edit
and at session start); run `python3 .claude/index/build_index.py` to rebuild.

## Specialist agents

A full senior (25-yr) product org lives in `.claude/agents/` — leadership &
architecture (`tech-lead`, `solutions-architect`, `product-manager`), engineering
(`backend-engineer`, `frontend-engineer`, `refactor-specialist`,
`performance-engineer`, `data-engineer`), data & design (`data-scientist`,
`product-designer`, `ux-researcher`), and quality/ops/docs (`qa-test-engineer`,
`security-auditor`, `code-reviewer`, `devops-sre`, `technical-writer`). They all
consult the code index first and follow the quality gates in `.claude/rules.md`.
See `.claude/agents/README.md`. Note: the engineer/refactor/design/ops agents *do*
modify source for active development, which is intentional and supersedes the
doc-only rule above for development tasks; `technical-writer` edits only `docs/`.

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