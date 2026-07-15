# System Overview — Claude Context

> **The 5-minute briefing. Read this first, every session.**

---

## What Is This?

A **DGFT License Manager** for Indian exporters. Companies get advance authorisation licenses from the government allowing duty-free import of raw materials used in manufacturing exports. This system tracks those licenses, their remaining balance (how much more can be imported), and all the transactions against them.

---

## The Core Problem This Solves

1. Government issues a license: "You may import up to USD 50,000 of goods duty-free"
2. Company imports goods in batches over months
3. System must track: how much of the USD 50,000 has been consumed?
4. Operators plan ahead (allotments), then actual imports (BOEs) happen
5. Multiple operators work concurrently — no over-allotment or double-deduction allowed

---

## The Balance Formula (know this cold)

```
balance_cif = max(0, credit − debit − allotment − trade)
```

This is computed asynchronously by Celery. Never in-request.

---

## The 9 Backend Modules

| Module | Port 8001 prefix | Key table | Primary concern |
|---|---|---|---|
| accounts | /auth/ | accounts_user | JWT auth, 15 RBAC roles |
| core | /masters/ | core_* (23 tables) | Reference data: companies, ports, HS codes, SION |
| license | /licenses/ | license_licensedetailsmodel | The central license record + balance |
| allotment | /allotments/ | allotment_allotmentmodel | Pre-authorization reservations |
| bill_of_entry | /bill-of-entries/ | bill_of_entry_billofentrymodel | Actual import records |
| trade | /trades/ | trade_licensetrade | Purchase invoices + bills of supply |
| tasks | /tasks/ | tasks_task | Internal workflow |
| dashboard | /dashboard/ | reads license/boe/allotment | KPI aggregation |
| reports | /reports/ | writes CeleryTaskTracker | Async report generation |

---

## Technology Choices

| Layer | Tech | Why |
|---|---|---|
| Backend | Django 6.x + DRF | Production-grade, RBAC, admin |
| Database | PostgreSQL (shared with legacy) | Continuity; all models are managed=False |
| Task queue | Celery + Redis | Async balance recompute (never in-request) |
| Frontend | React 19 + TypeScript | Modern, type-safe |
| Styling | Tailwind v4 + shadcn/ui | Component library + CSS-first |
| State | TanStack Query v5 | Server state management |
| Auth | JWT HS256 (shared key) | Works on both backends during transition |

---

## The Parallel Run Architecture

This is a **rebuild** of the legacy app, running in parallel:

```
nginx (443)
  /api/v1/* → backend/ (NEW, port 8001) ← You work here
  /api/*    → legacy/backend/ (OLD, port 8000) ← READ-ONLY, never modify
  /         → frontend/dist (NEW React app)
```

Both backends share the same PostgreSQL database. The `managed=False` flag on all business models means the new Django app can read/write legacy tables without owning their DDL.

**Cutover criteria** (ADR-009): 6 checks including UAT with 3 business users.

---

## Critical Constraint: managed=False

Every business model has:
```python
class Meta:
    managed = False
    db_table = "exact_legacy_table_name"
```

This means:
- ✅ Django can read and write
- ❌ Django will NOT run CREATE TABLE / ALTER TABLE / DROP TABLE
- ❌ Never run `makemigrations` for these apps
- ✅ Fields must exactly match the legacy DB schema

---

## Where to Start for Any Task

| Task type | Start here |
|---|---|
| Balance bug | `docs/claude/balance-context.md` |
| New feature | `docs/README.md` → relevant module doc |
| Frontend change | `docs/claude/frontend-context.md` |
| Understanding a workflow | `docs/knowledge-graphs/system-overview.md` |
| Business rules | `docs/business-rules/business-rule-index.md` |
| Formulas | `docs/business-rules/calculation-engine.md` |
| "What calls this file?" | `docs/knowledge-graphs/dependency-maps.md` |
| Common code patterns | `docs/claude/common-patterns.md` |
| Known issues | `docs/improvements/improvement-register.md` |
| How to run/test | `docs/claude/development-guide.md` |
