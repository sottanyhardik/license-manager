# Specialist Agents

A team of senior (25-years-experience) subagents for developing the License
Manager. They are **built on top of the code index** (`.claude/index/`): every
agent is required to `grep` the index (`symbols.tsv`, `dependents.tsv`,
`imports.tsv`, `CODE_MAP.md`) **before** reading source — so they locate code and
size refactor blast radius cheaply instead of re-reading the tree.

## Roster

| Agent | Use it for | Edits code? |
|-------|-----------|:-----------:|
| `tech-lead` | Plan & coordinate multi-part work; decompose, size risk, delegate | plans, delegates |
| `backend-engineer` | Django/DRF/Postgres: models, viewsets, serializers, services, migrations | ✅ |
| `frontend-engineer` | React 19/TS/Tailwind/shadcn: components, pages, hooks, forms, tables | ✅ |
| `refactor-specialist` | Behavior-preserving restructuring driven by the dependency graph | ✅ |
| `qa-test-engineer` | Write/extend tests, reproduce bugs, characterization tests, verify | ✅ (tests) |
| `security-auditor` | RBAC/auth/access-control/data-exposure review | ❌ read-only |
| `code-reviewer` | Pre-merge diff review for correctness & missed callers | ❌ read-only |

## How to invoke

- **Directly:** ask for a specific agent — e.g. *"Use the refactor-specialist to
  decompose MasterForm.tsx"* — or the main assistant dispatches via the Agent tool
  with `subagent_type: "refactor-specialist"`.
- **Coordinated:** ask the `tech-lead` to own a larger task; it plans against the
  index and delegates focused briefs to the specialists, then runs a
  `code-reviewer` pass before declaring done.
- **In parallel:** independent specialists can run concurrently (e.g. backend +
  frontend on separate slices). The tech-lead sequences what must be serial.

A typical feature flow:

```
tech-lead (plan + impact map from the graph)
   ├─ backend-engineer   (API/model/service)      ┐ parallel where independent
   └─ frontend-engineer  (UI + data wiring)        ┘
qa-test-engineer   (tests / verify)
code-reviewer      (pre-merge diff + graph caller check)
```

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
