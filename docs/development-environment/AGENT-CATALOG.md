# Agent catalog

42 agents live in `.claude/agents/`. Full roster with origins: `.claude/agents/README.md`.
Agents are **briefed, not autonomous**. Each acts only on an explicitly requested change, and
trivial tasks use no agents at all.

## The 12 core roles

| # | Role | Agent | Tools | Model | Reviewed by |
|---|---|---|---|---|---|
| 1 | Principal Architect | `solutions-architect` | Read/Grep/Glob/Bash/Write/Edit (design + ADRs in `docs/decisions/`) | inherit | human, for architecture/API/schema changes |
| 2 | Engineering Orchestrator | `engineering-manager` | all (incl. Agent) | opus | never self-approves: `code-reviewer` + gates |
| 3 | Senior Backend Engineer | `backend-engineer` | Read/Grep/Glob/Bash/Edit/Write | inherit | `code-reviewer`, `django-reviewer`/`python-reviewer`, domain auditor |
| 4 | Senior Frontend Engineer | `frontend-engineer` | Read/Grep/Glob/Bash/Edit/Write | inherit | `code-reviewer`, `react-reviewer`/`typescript-reviewer`, `a11y-architect` |
| 5 | Database Architect | `database-architect` (new) | read-only + docs Write/Edit | opus | `database-reviewer`, `django-reviewer`; human for irreversible ops |
| 6 | Code Reviewer | `code-reviewer` | read-only | inherit | independent; never reviews its own work |
| 7 | QA Engineer | `qa-test-engineer` | Read/Grep/Glob/Bash/Edit/Write | inherit | `code-reviewer` / `pr-test-analyzer` |
| 8 | Security Auditor | `security-auditor` | read-only | inherit | Critical/High findings go to the human |
| 9 | Performance Engineer | `performance-engineer` | Read/Grep/Glob/Bash/Edit/Write | inherit | before/after numbers; `cif-balance-auditor` for balance queries |
| 10 | Documentation Engineer | `technical-writer` | docs only | inherit | spot-check against code |
| 11 | Debugging Specialist | `debugging-specialist` (new) | Read/Grep/Glob/Bash/Edit/Write | sonnet | `code-reviewer`; domain auditor |
| 12 | Test Automation Engineer | `test-automation-engineer` | Read/Grep/Glob/Bash/Edit/Write | sonnet | `code-reviewer` |

Every core-role file ends with an **`## Engagement contract`** section. It covers:
- responsibility
- scope guard: no unrequested features, refactors or dependencies
- protected areas: API, permissions, schema, CIF/BOE/invoice logic
- safety (`.claude/rules/safety.md`)
- review requirement
- short output format: Status · Changes · Tests · Remaining

Specialists no longer carry the `Agent` tool, so they cannot fan out into nested agents. This is
cheaper in tokens and more predictable. Only `engineering-manager` (and the main session) orchestrate.

## Supporting agents (selected)

| Need | Agent |
|---|---|
| Planning / decomposition | `tech-lead`, `product-manager` (vague requests) |
| Design | `django-architect`, `react-architect` |
| Implementation helpers | `api-engineer`, `data-engineer`, `refactor-specialist`, `reconciliation-specialist`, `devops-sre` (deploys still need approval) |
| Build fixes | `django-build-resolver`, `react-build-resolver` |
| Language reviewers (ECC) | `django-reviewer`, `python-reviewer`, `typescript-reviewer`, `react-reviewer`, `database-reviewer`, `silent-failure-hunter`, `pr-test-analyzer` |
| TDD | `tdd-guide` |
| Exploration | `code-explorer`, built-in `Explore` (use haiku) |
| Domain auditors (read-only, mandatory for their paths) | `cif-balance-auditor`, `boe-reconciliation-auditor`, `invoice-auditor`, `dgft-dfia-rules-auditor`, `licence-domain-expert` |
| UX / design | `ux-researcher`, `product-designer`, `a11y-architect` |
| Docs | `architecture-documenter` |

## Model routing
haiku for lookups and exploration, sonnet for implementation and reviews, opus for architecture,
domain audits and final integration.
