# Skill catalog

Skills are loaded **on demand**: only their one-line description sits in context until a skill is
used. Project skills are deliberately short and point to the ECC skill that holds the generic patterns,
so nothing is duplicated.

## Requested skills → implementation

| Requested | Skill(s) | Origin |
|---|---|---|
| repository-audit | `repository-audit` | project |
| architecture-review | `architecture-review` | project |
| django-development | `django-development` → ECC `django-patterns`, `django-celery` | project + ECC |
| react-development | `react-development` → ECC `react-patterns`, `react-performance`, `react-testing`, `frontend-a11y` | project + ECC |
| typescript-development | `typescript-development` | project |
| postgresql-development | `postgresql-development` → ECC `postgres-patterns` | project + ECC |
| api-development | `api-development` → ECC `api-design` | project + ECC |
| debugging | `debugging` (+ agent `debugging-specialist`) | project |
| test-driven-development | `test-driven-development` → ECC `tdd-workflow`, `django-tdd`, `python-testing`, `react-testing` | project + ECC |
| code-review | **built-in** `/code-review` + project `/review-diff` (parallel specialist review) | built-in + project |
| security-review | **built-in** `/security-review` + ECC `django-security` + agent `security-auditor` | built-in + ECC |
| performance-review | `performance-review` | project |
| git-workflow | `git-workflow` | project |
| documentation | `documentation` | project |
| migration-safety | `migration-safety` → ECC `database-migrations` | project + ECC |
| regression-testing | `regression-testing` → ECC `verification-loop` | project + ECC |

`code-review` and `security-review` were **not** created as project skills because Claude Code
already ships built-in skills with exactly those names. A same-name project skill would shadow
the built-in or collide with it.

## Other ECC skills available
`context-budget`, `strategic-compact` (context management) · `search-first` (check existing deps
before writing code) · `django-verification`, `verification-loop` (verification).

## Project commands (also invocable as `/name`)
| Command | Purpose |
|---|---|
| `/quality-gate [area]` | CI-equivalent gates (`scripts/dev/quality-gate.sh`) |
| `/review-diff` | Independent parallel review of the working diff |
| `/cif-audit` | Audit the diff against canonical CIF/balance rules |
| `/orchestrate` | Full multi-agent workflow, for substantial tasks only |
| `/report [full]` | Short report: Status · Changes · Tests · Remaining |
| `/remember`, `/session-summary` | Write durable facts and session summaries to `.claude/memory/` |
