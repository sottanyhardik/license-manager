# Agent task ownership

One owner per file; parallel agents get disjoint files or `isolation: "worktree"` (CLAUDE.md §3).
Roster: `.claude/agents/README.md`. Model routing: haiku = lookups/indexing, sonnet = CRUD/UI/tests,
opus = CIF/balance, BOE ledger, accounting, migrations, security, final integration.

| Area | Owner agent | Files owned | Reviewer |
|---|---|---|---|
| Generic backend (`core/views/master_view.py`, `core/urls.py`, serializers) | backend-engineer (sonnet) | `backend/apps/core/views/`, `core/serializers/` | django-reviewer |
| Generic frontend (`pages/masters/*`, `components/{shared,workspace}`) | frontend-engineer (sonnet) | `frontend/src/pages/masters/`, `components/shared/`, `components/workspace/` | react-reviewer |
| Licence / allotment / balance | backend-engineer + **cif-balance-auditor (opus)** | `apps/license`, `apps/allotment` | cif-balance-auditor |
| BOE / reconciliation | reconciliation-specialist (opus) | `apps/bill_of_entry`, `apps/reconciliation` | boe-reconciliation-auditor |
| Trade / invoices | backend-engineer | `apps/trade` | invoice-auditor |
| Accounting | peer session "erp accounting integration audit" | `apps/accounting`, `pages/accounting*` | cif-balance-auditor / opus |
| QA / gates | test-automation-engineer | `scripts/dev/quality-gate.sh`, conftest, test config | — |
| Docs hub | technical-writer (haiku/sonnet) | `docs/erp-architecture/` | — |

Concurrent sessions on `feature/v5` (2026-11-17): accounting audit (busy), BOE modernization, license-manager-53.
Do not edit their files; land via path-scoped commits.
