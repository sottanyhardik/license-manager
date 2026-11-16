# Agent roster — License Manager engineering org

42 agents: 16 original project agents (kept as they were, except that `code-reviewer` and
`security-auditor` are now limited to read-only tools), 12 vendored ECC agents (each with a
project-context section appended), 12 added 2026-11-15, and 2 added 2026-11-16
(`database-architect` [opus, RO+docs], `debugging-specialist` [sonnet, RW]). Original README backed up at
`.claude/backups/2026-11-15-pre-ecc/agents/README.md`. Orchestration:
`docs/claude/ORCHESTRATION.md`.

**12 core roles (2026-11-16)** — each carries an `## Engagement contract` section (responsibility,
scope guard, protected areas, safety, review, short output) and an explicit `tools:` list:
Principal Architect `solutions-architect` · Engineering Orchestrator `engineering-manager` ·
Senior Backend `backend-engineer` · Senior Frontend `frontend-engineer` · Database Architect
`database-architect` (+ `data-engineer` implements, `database-reviewer` reviews) · Code Reviewer
`code-reviewer` · QA `qa-test-engineer` · Security `security-auditor` · Performance
`performance-engineer` · Documentation `technical-writer` · Debugging `debugging-specialist` ·
Test Automation `test-automation-engineer`. Full catalog: `docs/development-environment/AGENT-CATALOG.md`.

Legend: **RO** = read-only tools (Read/Grep/Glob/Bash) · **RW** = full tools · model in brackets.
Origin: P = project original, E = vendored ECC (MIT), N = new 2026-11-15.

## Leadership
| Role requested | Agent | Access | Origin |
|---|---|---|---|
| Principal Architect | `solutions-architect` [inherit] | RW (design/ADR) | P |
| Tech Lead | `tech-lead` [inherit] | RW | P |
| Engineering Manager / orchestrator | `engineering-manager` [opus] | RW | N |
| Product Manager | `product-manager` [inherit] | RW (specs) | P |

## Backend
| Django Architect | `django-architect` [opus] | RW (docs/design) | N |
|---|---|---|---|
| Django Backend Engineer | `backend-engineer` [inherit] | RW | P |
| Database Engineer | `data-engineer` [inherit] + `database-reviewer` [sonnet] | RW / RO | P / E |
| API Engineer | `api-engineer` [sonnet] | RW | N |
| Performance Engineer | `performance-engineer` [inherit] | RW | P |
| Build/migration fixer | `django-build-resolver` [sonnet] | RW | E |

## Frontend
| React Architect | `react-architect` [opus] | RW (docs/design) | N |
|---|---|---|---|
| React Engineer | `frontend-engineer` [inherit] | RW | P |
| UI/UX Designer | `product-designer` (visual) + `ux-researcher` (flows) [inherit] | RW | P |
| Accessibility Specialist | `a11y-architect` [sonnet] | RW | E |
| Build fixer | `react-build-resolver` [sonnet] | RW | E |

## Data
| Data Engineer | `data-engineer` [inherit] | RW | P |
|---|---|---|---|
| Analytics Engineer | `data-scientist` [inherit] (reporting correctness, pivots, exports) | RW | P |
| Reconciliation Specialist | `reconciliation-specialist` [sonnet] | RW | N |

## Quality
| QA Engineer | `qa-test-engineer` [inherit] | RW | P |
|---|---|---|---|
| Test Automation Engineer | `test-automation-engineer` [sonnet] (+ `tdd-guide`, `pr-test-analyzer`) | RW | N / E |
| Security Auditor | `security-auditor` [inherit] | **RO** | P |
| Code Reviewer | `code-reviewer` [inherit] + `django-reviewer`, `python-reviewer`, `typescript-reviewer`, `react-reviewer`, `silent-failure-hunter` [sonnet] | RO | P / E |
| DevOps/SRE | `devops-sre` [inherit] | RW (deploys still need approval) | P |
| Refactoring | `refactor-specialist` [inherit] | RW | P |
| Code exploration | `code-explorer` [sonnet] | RO | E |

## Business domain (all read-only auditors)
| Licence Domain Expert | `licence-domain-expert` [opus] | RO | N |
|---|---|---|---|
| CIF Balance Auditor | `cif-balance-auditor` [opus] | RO | N |
| BOE Reconciliation Auditor | `boe-reconciliation-auditor` [opus] | RO | N |
| Invoice Auditor | `invoice-auditor` [sonnet] | RO | N |
| DGFT/DFIA Business Rules Auditor | `dgft-dfia-rules-auditor` [opus] | RO | N |

## Documentation
| Technical Writer | `technical-writer` [inherit] | docs/ only | P |
|---|---|---|---|
| Architecture Documenter | `architecture-documenter` [sonnet] | docs/ only | N |

## Deliberately not created (would duplicate)
- ECC `architect`/`planner` → covered by `solutions-architect` + `tech-lead`
- ECC `code-reviewer`, `security-reviewer`, `performance-optimizer`, `refactor-cleaner`, `doc-updater` → project equivalents already exist
- Separate "Analytics Engineer" and "UI/UX Designer" files → mapped to existing agents above

## Contract every agent follows
Index-first context loading · edits only the files it owns in the brief · Output format defined
in its file · escalates business-rule, API contract, permission, and "ask first" safety items ·
reports gate results honestly. Domain paths changed → the matching domain auditor must review.
