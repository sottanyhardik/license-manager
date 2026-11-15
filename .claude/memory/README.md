# Project memory index (`.claude/memory/`)

Read this index, then only the file you need. Keep entries short; update instead of duplicating.
(The harness also keeps per-user auto-memory under `~/.claude/projects/…/memory/` — that one is personal, this one is shared with the repo.)

| File | Contents |
|---|---|
| `decisions.md` | Dated decisions + open owner decisions (append-only log) |
| `domain.md` | Licence/CIF/BOE/allotment domain facts and where they live in code |
| `project.md` | Frontend stack + in-flight migrations |
| `components.md` | Frontend component inventory notes |
| `graph-state.md` | Frontend module map snapshot (2026-06-17) |
| `session-notes.md` | Human-readable session summaries (`/session-summary`) |
| `session-log.md` | One-line automatic log per session (SessionEnd hook; git-ignored) |
