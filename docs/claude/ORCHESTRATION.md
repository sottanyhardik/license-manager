# Multi-agent orchestration — License Manager

Claude Code has no always-on agent daemon. "Autonomous" here means that within one task the main
chat (or `engineering-manager`) plans, delegates to subagents, runs them in parallel, integrates the
results and verifies them. Ordinary reversible edits and commands don't need approval: permissions are
set to `acceptEdits` plus an allowlist. The actions listed in `.claude/rules/safety.md` still need a human.

Entry point: `/orchestrate <task>`. For small tasks (a handful of tool calls), skip all of this and just do the work.

## Flow

```mermaid
flowchart TD
  A[Task] --> B{Substantial?}
  B -- no --> Z[Do it directly · run relevant gate · short report]
  B -- yes --> C[1 Requirements<br/>product-manager · licence-domain-expert]
  C --> D[2 Memory + index<br/>.claude/memory · symbols.tsv · dependents.tsv]
  D --> E[3 Plan<br/>tech-lead (+ django/react/solutions-architect)]
  E --> F[4 Work packages + file ownership<br/>engineering-manager]
  F --> G1[backend-engineer / api-engineer]
  F --> G2[frontend-engineer / product-designer]
  F --> G3[data-engineer / reconciliation-specialist]
  F --> G4[qa-test-engineer / test-automation-engineer]
  G1 & G2 & G3 & G4 --> H[5 Integrate locally]
  H --> I[6 Quality gates<br/>scripts/dev/quality-gate.sh]
  I -- fail --> F
  I --> J[7 Parallel read-only reviews]
  J --> J1[code-reviewer + ECC language reviewers]
  J --> J2[security-auditor]
  J --> J3[performance-engineer]
  J --> J4[domain auditors<br/>cif-balance · boe · invoice · dgft]
  J1 & J2 & J3 & J4 --> K{Blocking findings?}
  K -- yes, ≤3 rounds --> F
  K -- still blocked --> X[Escalate to human]
  K -- no --> L[8 Docs + memory<br/>technical-writer · architecture-documenter · decisions.md]
  L --> M[9 Final report /report]
```

## Preventing conflicting edits

1. Every work package lists the **files it owns**. No two packages running at the same time may own the same file.
2. Packages also conflict when one changes a symbol (signature, model field, serializer field) that
   the other's files import. Check with `grep '^<file>' .claude/index/dependents.tsv`. Conflicting
   packages run one after another.
3. When packages have to touch overlapping areas in parallel (e.g. two migration-heavy changes), give each
   `isolation: "worktree"`. The integrator then applies them one at a time, re-running gates after each.
   Worktrees live under `.claude/worktrees/` (git-ignored) and are removed with `git worktree remove` once merged locally.
4. Migrations: only one package per Django app creates migrations per round. This avoids conflicting `00NN_` numbers.

## Model routing

| Work | Model |
|---|---|
| Lookups, index greps, exploration (`code-explorer`, `Explore`) | haiku |
| Implementation, tests, language reviews, invoice audit | sonnet |
| Architecture, engineering-manager integration, CIF/BOE/DGFT auditing, domain expert | opus |
| Existing agents with `model: inherit` | the session model |

## Which reviewers to trigger

| Changed paths | Reviewer(s) |
|---|---|
| any | `code-reviewer` |
| `*.py` | `django-reviewer`, `python-reviewer` |
| `frontend/src/**` | `typescript-reviewer`, `react-reviewer`, `a11y-architect` (UI) |
| `apps/accounts/**`, `permissions.py`, views/serializers/urls, settings | `security-auditor` |
| querysets, services, `materialized_views.py`, list/report pages | `performance-engineer`, `database-reviewer` |
| balance/CIF paths (`.claude/rules/business-rules.md`) | `cif-balance-auditor` (required) |
| `apps/bill_of_entry`, `apps/reconciliation` | `boe-reconciliation-auditor` |
| `apps/trade` | `invoice-auditor` |
| SION/norm/plan/classifier services | `dgft-dfia-rules-auditor` |
| migrations | `database-reviewer`, `django-architect` |

## Escalation ladder

Specialist → `engineering-manager` → `tech-lead` / architect → human. Always escalate to the human for:
business-rule changes or contradictions, API contract or permission changes, anything in the
"ask first" list, three failed fix rounds, and gates that can't run.

## Reusable workflows

| Command | Purpose |
|---|---|
| `/orchestrate <task>` | full flow above |
| `/quality-gate [area]` | CI-equivalent gates |
| `/review-diff` | parallel independent review of the working diff |
| `/cif-audit [scope]` | domain audit of balance-affecting changes |
| `/report` | standard final report |
| `/remember <fact>` · `/session-summary` | project memory |

Skills (load automatically by description): `django-patterns`, `django-security`, `django-tdd`,
`django-verification`, `django-celery`, `postgres-patterns`, `database-migrations`, `python-testing`,
`api-design`, `react-patterns`, `react-testing`, `react-performance`, `frontend-a11y`, `tdd-workflow`,
`verification-loop`, `search-first`, `strategic-compact`, `context-budget`.
For large fan-outs (more than ~5 agents), the `Workflow` tool can script the pipeline; use it only when the human opts in.

## Token-efficiency rules

- Index-first: grep `symbols.tsv`/`dependents.tsv`, then read only line ranges. Never dump index tables.
- Rules are path-scoped (`paths:` frontmatter), so backend rules only load when you touch backend files.
- Subagent briefs carry the goal, the owned files and the relevant `file:line` pointers. Don't make agents rediscover them.
- Use `/session-summary` then `/compact` at phase boundaries (skill: `strategic-compact`).
