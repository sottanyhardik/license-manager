# License Manager — Claude Code project instructions

Django 6 / DRF / Python 3.14  / Postgres (CI: 16, local dev: 18) / Redis / Celery backend (`backend/`),
React 19 + TypeScript 5.9 + Vite + Tailwind v4 + shadcn SPA (`frontend/`),
Django master-data service (`master-data-service/`) and its Python client
(`mds-client/`). Domain: Indian DGFT import/export licences (DFIA/Advance),
SION norms, allotments, bills of entry (BOE), trades/invoices, CIF balances.

## 1. Index first — MANDATORY before reading/editing source (every chat + every subagent)

`.claude/index/` is rebuilt automatically (SessionStart + PostToolUse hooks, zero chat tokens).
Never read the tables whole — grep them:

- Symbol → file:line: `grep -i "Name" .claude/index/symbols.tsv`
- Blast radius (who imports X): `grep '^path' .claude/index/dependents.tsv` (forward: `imports.tsv`)
- Area shape: grep the relevant section of `.claude/index/CODE_MAP.md`
- Rebuild manually: `python3 .claude/index/build_index.py`

Then read only the file+line ranges you need. Do not re-scan the repo.

## 2. Business logic is critical infrastructure

CIF/balance math, allotment/BOE/invoice reconciliation, API response shapes and
permissions must never change silently. Canonical rule and code map:
`.claude/rules/business-rules.md` (auto-loads for backend balance code). Any
change touching them → `cif-balance-auditor` review + tests, and an explicit
"BUSINESS-RULE CHANGE" note in the final report. Unresolved conflicts between the
stated rule and the code are escalated to the human, never "fixed" unilaterally.

## 2a. Operating mode — scope, speed, reporting (permanent)

**Scope:** change application code only when the user explicitly requests that change.
Never invent requirements, choose new ERP features, refactor unrelated code, add
dependencies (reuse existing ones), or overwrite user changes. Preserve architecture,
API contracts and historical data unless explicitly authorised. No destructive DB
operations without authorisation. Significant architectural decisions → `docs/decisions/`.

**Fast path (default):** SHORT PROMPT → UNDERSTAND (index + only relevant files) →
IMPLEMENT the minimum change → TEST (targeted first, then the area gate) → fix introduced
failures → REPORT. Infer routine details from the repo; don't ask about things this file or
`.claude/memory/` already answer; don't ask before routine reversible actions. Ask only when an
ambiguity materially affects architecture, data safety or behaviour. No long plans for clear,
small tasks; no agents for trivial tasks; parallel agents only for independent work.
Don't re-run passing checks unless code changed. Load only relevant skills.

**Never traded for speed:** necessary tests, security, existing behaviour, safe DB changes,
honest failure reporting (skills `regression-testing`, `migration-safety`).

**Report format (every task):** `Status: Completed/Blocked` · `Changes:` files + one line each ·
`Tests: Pass/Fail` (NOT RUN + reason if a gate couldn't run) · `Remaining:` genuine items only.
Add `BUSINESS-RULE / API CONTRACT / SCHEMA CHANGE` flags when applicable. No long prose.
Workflow detail + agent/skill catalogs: `docs/development-environment/`.

## 3. Orchestration protocol (substantial / multi-area tasks only)

Run `/orchestrate` (full protocol: `docs/claude/ORCHESTRATION.md`). Parallel agents
need **file ownership** (one owner per file; disjoint files or `isolation: "worktree"`).
Small tasks (a few tool calls): just do them — don't spawn agents.

Model routing: `haiku` for lookups/exploration, `sonnet` for implementation and
reviews, `opus` for architecture, domain auditing and the final integration.

## 4. Quality gates (authoritative spec: `.github/workflows/ci.yml`)

`scripts/dev/quality-gate.sh [frontend|backend|mds|mds-client|all]` runs the same
commands as CI. A task is not done until the relevant gates ran; report the real
output — if a gate could not run (missing toolchain/DB), say so explicitly.

## 5. Autonomy and safety boundaries

Allowed without asking: read/edit app code, write tests, run dev/test/lint/build
commands, `makemigrations` (file generation), plans, reviews, temporary worktrees,
local commits on a feature branch when the user asked for the work.
`migrate` prompts each time (settings `ask`): Claude cannot verify the DB target without
reading secrets — approve only for the local dev/test DB.

Always ask first: `git push`, merges into `develop`/`master`, rebases/resets/force
operations, deleting branches, anything under `backend/deploy`/`scripts/deploy*`
or touching servers, production/remote databases, dependency additions, data
deletion/irreversible data operations. Never print or commit secrets (`.env*`,
`backend/.env_dgft`, keys). Details: `.claude/rules/safety.md`.

## 6. Where things are

- Agents: `.claude/agents/` (roster: `.claude/agents/README.md`)
- Rules: `.claude/rules/` (project) + `.claude/rules/ecc/` (vendored ECC, lower precedence)
- Skills: `.claude/skills/` · Commands: `.claude/commands/` (`/orchestrate`, `/quality-gate`, `/cif-audit`, `/review-diff`, `/report`, `/remember`, `/session-summary`)
- Project memory: `.claude/memory/` (index: `.claude/memory/README.md`)
- Setup/troubleshooting: `docs/claude/INSTALLATION.md`, `docs/claude/TROUBLESHOOTING.md`

## 7. Autonomous execution (permanent, owner rule 2026-11-17)

Before any task: read `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md` (its `CHECKPOINT:<workstream>` blocks are
printed at SessionStart) and continue from the last verified checkpoint. Within an explicitly requested task,
run implement → focused test → fix → verify → document without waiting for repeated prompts; wait for running
commands/gates instead of duplicating them; capture exit codes and logs; rerun only affected tests; full gates
once per integration. Update the tracker after each verified milestone. Ask only for destructive, irreversible,
production, push/deploy, new-dependency or business-policy decisions. Full rules:
`.claude/rules/autonomous-execution.md` (subordinate to `.claude/rules/safety.md`).
