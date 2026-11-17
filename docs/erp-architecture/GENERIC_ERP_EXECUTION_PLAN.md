# Generic ERP execution plan

Loop: DISCOVER → ASSIGN → IMPLEMENT → INTEGRATE → TEST → REVIEW → FIX → RETEST → DOCUMENT
(`.claude/rules/autonomous-execution.md`; protocol `docs/claude/ORCHESTRATION.md`, `/orchestrate`).
Scope rule (CLAUDE.md §2a): code changes only for explicitly requested, approved items.

| # | Step | Status (2026-11-17) |
|---|---|---|
| 1 | Generic backend + frontend | **Exists** (see [architecture](GENERIC_ERP_ARCHITECTURE.md) §1) |
| 2 | Prove on Licence | **Done** — Licence/Allotment/BOE/Trade/Incentive on `MasterList` + `create_viewset` |
| 3 | Core masters on generic CRUD | **Done** — 14 routers in `core/urls.py` ([matrix](MODULE_MIGRATION_MATRIX.md)) |
| 4 | Verify integrated `feature/v5` | **Done** @ `b099789c` — backend app-level 3546 passed; 1 env failure (no `frontend/dist`) ([QA report](TEST_AND_QA_REPORT.md)) |
| 4a | Masters workspace: `/masters` hub, category nav, 5 unexposed masters registered, code-keyed records, permission-aware actions, list refresh after save | **Done + Tested** `331b9520` ([QA report](TEST_AND_QA_REPORT.md)) |
| 4b | Masters on the licence UI standard: register toolbar, licence-style rows, generic record page + real history | **Done + Tested** ([QA report](TEST_AND_QA_REPORT.md)) |
| 5 | Shared-component consolidation (DataTable, ConfirmDialog, EmptyState, StatCard pairs) | Deferred — cross-app; [registry §5](generic-component-registry.md) |
| 6 | Masters that do not exist (Customer, Supplier, Country, Currency, Category, Unit, Bank) | **Blocked — owner decision** ([blockers](CURRENT_BLOCKERS.md) B1) |
| 7 | Accounting deferred items (exports, opening balance import, accrual beat, trade badge) | Next, accounting workstream (`docs/erp-accounting/08-completion-inventory.md`) |
| 8 | BOE list perf (per-row available CIF) | Blocked — protected balance code ([blockers](CURRENT_BLOCKERS.md) B4) |

Gates per integration: `scripts/dev/quality-gate.sh backend|frontend` once; focused tests during work.

Next candidates (no owner decision needed): bulk actions on generic masters; step 5 consolidation. Accounting masters
stay on their own views (DR-GEN-2) unless the accounting owner agrees. Blocked items: [blockers](CURRENT_BLOCKERS.md).
