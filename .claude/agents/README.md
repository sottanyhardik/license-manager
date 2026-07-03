# Specialist Agents

A team of senior (25-years-experience) subagents for developing the License
Manager. They are **built on top of the code index** (`.claude/index/`): every
agent is required to `grep` the index (`symbols.tsv`, `dependents.tsv`,
`imports.tsv`, `CODE_MAP.md`) **before** reading source — so they locate code and
size refactor blast radius cheaply instead of re-reading the tree.

## Roster (the org)

A full product org, the way a large software company staffs one. All 16 are
senior (25-yr) and index-first.

**Leadership & architecture**

| Agent | Use it for | Edits code? |
|-------|-----------|:-----------:|
| `tech-lead` | Plan & coordinate multi-part work; decompose, size risk, delegate | plans, delegates |
| `solutions-architect` | System design, boundaries, ADRs, trade-offs, scalability | ❌ designs/advises |
| `product-manager` | Requirements, user stories, acceptance criteria, scope, edge cases | ❌ specs only |

**Engineering**

| Agent | Use it for | Edits code? |
|-------|-----------|:-----------:|
| `backend-engineer` | Django/DRF/Postgres: models, viewsets, serializers, services, migrations | ✅ |
| `frontend-engineer` | React 19/TS/Tailwind/shadcn: components, pages, hooks, forms, tables | ✅ |
| `refactor-specialist` | Behavior-preserving restructuring driven by the dependency graph | ✅ |
| `performance-engineer` | Profile & fix slow queries/N+1, indexes, caching, renders, bundle | ✅ |
| `data-engineer` | DGFT/SION/rates pipelines, ETL, schema/index design, data migrations | ✅ |

**Data & design**

| Agent | Use it for | Edits code? |
|-------|-----------|:-----------:|
| `data-scientist` | Analytics, reporting/balance-math validation, anomalies, forecasting | ❌ analyses |
| `product-designer` | Visual design, design system, tokens, layout, dark mode, polish | ✅ (UI) |
| `ux-researcher` | User flows, usability, interaction, form/table UX, accessibility (AA) | ✅ (UX) |

**Quality, ops & docs**

| Agent | Use it for | Edits code? |
|-------|-----------|:-----------:|
| `qa-test-engineer` | Write/extend tests, reproduce bugs, characterization tests, verify | ✅ (tests) |
| `security-auditor` | RBAC/auth/access-control/data-exposure review | ❌ read-only |
| `code-reviewer` | Pre-merge diff review for correctness & missed callers | ❌ read-only |
| `devops-sre` | Deploy scripts, nginx/SSL, systemd, backups, health, rollback | ✅ (ops) |
| `technical-writer` | `docs/` (features/API/DB/flows), Mermaid diagrams, keep docs in sync | ✅ (docs only) |

## How to invoke

- **Directly:** ask for a specific agent — e.g. *"Use the refactor-specialist to
  decompose MasterForm.tsx"* — or the main assistant dispatches via the Agent tool
  with `subagent_type: "refactor-specialist"`.
- **Coordinated:** ask the `tech-lead` to own a larger task; it plans against the
  index and delegates focused briefs to the specialists, then runs a
  `code-reviewer` pass before declaring done.
- **In parallel:** independent specialists can run concurrently (e.g. backend +
  frontend on separate slices). The tech-lead sequences what must be serial.

A typical end-to-end feature flow:

```
product-manager      (problem → stories + acceptance criteria)
solutions-architect  (design + boundaries + staged plan)
tech-lead            (impact map from the graph → delegate)
   ├─ backend-engineer    (API/model/service)     ┐
   ├─ frontend-engineer   (UI + data wiring)       │ parallel where independent
   ├─ product-designer    (visual/design system)   │
   └─ ux-researcher       (flow/usability/a11y)    ┘
performance-engineer (measure & optimize hot paths, if relevant)
qa-test-engineer     (tests / verify)
security-auditor     (if auth/RBAC/data-exposure touched)
code-reviewer        (pre-merge diff + graph caller check)
technical-writer     (update docs/ + diagrams)
```

Data/ops tracks run similarly: `data-engineer` (pipelines/schema) with
`data-scientist` (validate the numbers); `devops-sre` (ship it, with rollback).
Pick only the agents a task needs — most tasks use two or three, not all sixteen.

## Shared rules every agent follows

1. **Index-first** — grep `.claude/index/*` before reading source (token-cheap).
2. **Preserve business logic** — no behavior/API/auth/data-flow change unless the
   task says so; flag any behavior change.
3. **Quality gates before "done"** — frontend `npm run lint && npm run typecheck &&
   npm run build`; backend `py_compile` + `./run-tests.sh`. Report results honestly.
4. **Conventions** — follow `.claude/rules.md` (lucide-only icons, sonner over
   react-toastify, design tokens over hex, reuse `ui/*`).
5. **No unattended outward actions** — agents do not commit/push/merge; the human
   confirms anything hard to reverse.

## Note on `CLAUDE.md`

The root `CLAUDE.md` was written for a **documentation** task and says "Never
modify source code." These development agents intentionally *can* modify source
(that is the point of active development/refactoring). Use the read-only agents
(`security-auditor`, `code-reviewer`) and the `tech-lead` planning mode when you
want analysis without edits; use the engineer/refactor agents when you want
changes. If you want the whole team kept strictly read-only, say so and the edit
capability can be removed from their tool lists.
