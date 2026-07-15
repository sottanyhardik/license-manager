# License Manager — Documentation Index

> **Complete Living System Specification** for the License Manager application.  
> Last updated: 2026-07-15 (feature/V1). **Update this file whenever documentation changes.**

This documentation is the **single source of truth** for understanding the system. Read this before any development task to avoid re-discovering architecture.

---

## 🚀 Start Here (Claude context files)

| Purpose | Document |
|---|---|
| Quick system briefing (5 min) | [claude/system-overview.md](claude/system-overview.md) |
| Before touching balance/allotment/BOE | [claude/balance-context.md](claude/balance-context.md) |
| Backend development patterns | [claude/backend-context.md](claude/backend-context.md) |
| Frontend development patterns | [claude/frontend-context.md](claude/frontend-context.md) |
| Recurring code patterns | [claude/common-patterns.md](claude/common-patterns.md) |
| How to run, test, lint, commit | [claude/development-guide.md](claude/development-guide.md) |

---

## Quick Links

| What you need | Where to find it |
|---|---|
| System overview + architecture diagrams | [knowledge-graphs/system-overview.md](knowledge-graphs/system-overview.md) |
| **Balance formula (critical)** | [business-rules/balance-calculations.md](business-rules/balance-calculations.md) |
| Planning / allotment rules | [business-rules/planning-rules.md](business-rules/planning-rules.md) |
| **All business rules indexed** | [business-rules/business-rule-index.md](business-rules/business-rule-index.md) |
| **All calculations with formulas** | [business-rules/calculation-engine.md](business-rules/calculation-engine.md) |
| Business decisions & rationale | [business-decisions.md](business-decisions.md) |
| Change impact maps | [knowledge-graphs/dependency-maps.md](knowledge-graphs/dependency-maps.md) |
| Test coverage gaps | [test-coverage-map.md](test-coverage-map.md) |
| Rule → Code traceability | [traceability.md](traceability.md) |
| Known issues & improvements | [improvements/improvement-register.md](improvements/improvement-register.md) |
| License module details | [modules/license.md](modules/license.md) |
| Allotment module | [modules/allotment.md](modules/allotment.md) |
| Bill of Entry module | [modules/bill-of-entry.md](modules/bill-of-entry.md) |
| Trade module | [modules/trade.md](modules/trade.md) |
| Reports module | [modules/reports.md](modules/reports.md) (partial) |
| Tasks module | [modules/tasks.md](modules/tasks.md) |
| Dashboard module | [modules/dashboard.md](modules/dashboard.md) |
| Authentication & RBAC | [modules/authentication.md](modules/authentication.md) |
| Masters (reference data) | [modules/masters.md](modules/masters.md) |
| Frontend architecture | [frontend/architecture.md](frontend/architecture.md) |
| Infrastructure & config | [infrastructure.md](infrastructure.md) |
| Database schema | [05-database.md](05-database.md) |
| API contract (legacy) | [api-contract/legacy-v1.yaml](api-contract/legacy-v1.yaml) |
| Security audit | [security-audit-phase1.md](security-audit-phase1.md) |
| Performance review | [performance-review-phase1.md](performance-review-phase1.md) |
| Architecture decisions | [adr/](adr/) |
| Knowledge graphs (living docs) | [knowledge-graph/](knowledge-graph/) |

---

## Module Status

| Module | Backend | Frontend | Tests | Docs |
|---|---|---|---|---|
| Authentication | ✅ done | ✅ done | ✅ | ✅ |
| Masters (23 models) | ✅ done | ✅ done | ✅ | ✅ |
| License | ✅ done | ✅ done | ✅ | ✅ |
| License Balance | ✅ done | ✅ done | ✅ 21 tests | ✅ |
| License Planning | ✅ done | ✅ done | ✅ | ✅ |
| Allotment | ✅ done | ✅ done | ✅ | ✅ |
| Bill of Entry | ✅ done | ✅ done | ✅ | ✅ |
| Trade | ✅ done | ✅ done | ✅ | ✅ |
| Tasks | ✅ done | ✅ done | ✅ | ✅ |
| Dashboard | ✅ done | ✅ done | ✅ | ✅ |
| Reports | ✅ done | ✅ done | ✅ | ✅ |
| Settings | ✅ done | ✅ done | — | partial |

---

## Critical Business Rules

> Always read these before modifying balance, allotment, or BOE code.

1. **Balance formula**: `balance_cif = max(0, credit − debit − allotment − trade)` — see [balance-calculations.md](business-rules/balance-calculations.md)
2. **No double-deduction**: Allotment exits formula when BOE is linked; BOE enters formula simultaneously
3. **Planning is optional**: If no `LicenseItemPlan` exists, allotment is unrestricted
4. **select_for_update**: Required in recompute_license_balance AND plan validation
5. **on_commit dispatch**: Balance recompute only enqueued AFTER transaction commits
6. **acks_late=True**: All financial Celery tasks re-queue on worker crash
7. **3dp precision**: `pct`/`rate_pct` in trade must use `Decimal(str(value))` NOT `q2(value)` before dividing by 100

---

## Architecture Decisions

| ADR | Title |
|---|---|
| ADR-001 | Hybrid parallel-run migration strategy |
| ADR-002 | Single shared PostgreSQL database |
| ADR-003 | Django 6.x / Python 3.13 backend stack |
| ADR-004 | React 19 / TypeScript / Vite / TanStack Query v5 |
| ADR-005 | `/api/v1/` prefix for new API |
| ADR-006 | JWT HS256 shared SECRET_KEY during transition |
| ADR-007 | Views → Services → ORM (never views → ORM directly) |
| ADR-008 | Celery replaces cross-app signals |
| ADR-009 | 6-criteria production cutover gate |
| ADR-010 | `legacy/` is read-only |

---

## Test Coverage Summary

| Test file | Tests | Coverage focus |
|---|---|---|
| `tests/balance/test_balance_system.py` | **21** | Balance formula, BOE scenarios, planning, dispatch |
| `tests/integration/test_license_workflows.py` | ~50 | All business rules BR-01 to BR-08 |
| `tests/integration/test_permissions.py` | ~35 | All RBAC roles |
| `tests/accounts/test_auth.py` | 13 | Login/logout/refresh/roles |
| `tests/allotment/test_allotment.py` | 4 | Dispatch, type choices |
| `tests/bill_of_entry/test_boe.py` | 7 | Frozen rows, dispute, signals, ledger |
| `tests/trade/test_trade.py` | 10 | 3dp precision all modes |
| `tests/license/test_license.py` | 8 | License CRUD, balance dispatch, permissions |
| `tests/reports/test_reports.py` | 4 | Task dispatch, tracker, polling |
| `tests/tasks/test_tasks.py` | 6 | State machine, remarks |
| `tests/core/test_masters.py` | 10 | Master CRUD, pagination, search |
| `tests/dashboard/test_dashboard.py` | 9 | Stats, charts, expiring |
| **Total** | **~161** | |

---

## Known Technical Debt

| Issue | Severity | Module | Details |
|---|---|---|---|
| Trade PDF generation synchronous | MED | trade | PDF generators block gunicorn workers; `generate_trade_pdf_task` stub exists but not connected |
| Report services diverge from balance formula | MED | reports | `balance_report.py` re-implements aggregations instead of calling `balance_service._compute_*` |
| ImportItemSerializer N+1 | LOW | license | `get_planned_quantity` queries LicenseItemPlan per import item |
| LicenseBalanceSerializer N+1 | LOW | license | `get_total_authorised/debited/allotted` each make a DB query on detail view |
| Single plan per item not enforced | LOW | license | API allows multiple LicenseItemPlan rows; serializer reads only first |
| Missing focus trap on mobile sidebar | LOW | frontend | WCAG 2.1 compliance — keyboard users can Tab outside open drawer |
| settings page incomplete | LOW | frontend | `pages/settings` exists but `features/settings` not in `features/` |
| Trade PDFs use window.open (fixed) | DONE | frontend | Fixed: now use apiClient with responseType: 'blob' |
| BOE balance recompute was broken | DONE | balance | Fixed: signals now dispatch correct license_id (not item_id) |
| _dispatch passed wrong IDs | DONE | allotment | Fixed: now resolves license_id from import item ID |

---

## End-to-End Workflows

| Workflow | Document |
|---|---|
| License creation → allotment → BOE → closure | [workflows/license-lifecycle.md](workflows/license-lifecycle.md) |

## State Machines

| Document | Entities covered |
|---|---|
| [state-machines/entities.md](state-machines/entities.md) | License, Allotment, BOE RowDetails, Task, CeleryTask, IncentiveLicense |

## Data Flows (Sequence Diagrams)

| Document | Flows covered |
|---|---|
| [data-flows/balance-recompute-flow.md](data-flows/balance-recompute-flow.md) | After allotment, after BOE row, full recompute detail, report generation |

## Change Playbooks

| Module | Playbook |
|---|---|
| Balance & Planning | [playbooks/balance-module-playbook.md](playbooks/balance-module-playbook.md) |

---

## 📋 Living Documentation Maintenance Protocol

**Every time code changes, update the relevant documentation:**

### If you change business logic:
1. Update `docs/business-rules/business-rule-index.md` (add/modify rule)
2. Update `docs/business-rules/calculation-engine.md` (if formula changes)
3. Update `docs/traceability.md` (trace from UI to DB)
4. Update the affected module doc (`docs/modules/{module}.md`)
5. Update `docs/test-coverage-map.md` if tests added/removed

### If you change architecture:
1. Write or update an ADR in `docs/adr/`
2. Update `docs/knowledge-graphs/system-overview.md`
3. Update `docs/knowledge-graphs/dependency-maps.md`
4. Update `docs/infrastructure.md` if infra changes

### If you fix a bug:
1. Add to `docs/business-decisions.md` if it reveals a hidden assumption
2. Update `docs/claude/{relevant-context}.md` "Known Pitfalls" section
3. Remove from `docs/improvements/improvement-register.md` if it was listed

### If you add a feature:
1. Create/update the module doc
2. Add business rules to the index
3. Add to test coverage map
4. Update workflows if user flow changes

---

## Document Count

| Category | Count | Lines |
|---|---|---|
| Claude context files | 6 | ~1,050 |
| Business rules | 4 | ~1,160 |
| Module docs | 8 | ~4,000 |
| Knowledge graphs | 3 | ~480 |
| Workflows | 1 | ~340 |
| State machines | 1 | ~180 |
| Data flows | 1 | ~190 |
| Playbooks | 1 | ~180 |
| Improvements | 1 | ~130 |
| Infrastructure | 1 | ~260 |
| ADRs | 10 | ~860 |
| Other | 5 | ~2,200 |
| **Total** | **~47** | **~11,000+** |
