# Initial Audit — License Manager modernization

Date 2026-11-16 · branch `feature/v5` · Detail lives in the sibling docs. This is the index and summary.

## Environment (inspected, nothing upgraded)

| Item | Found |
|---|---|
| Backend | Django 6.0.4, DRF, Python 3.14 (`backend/.venv`), single `lmanagement/settings.py` (620 LOC) |
| DB | PostgreSQL 18.7 local (Homebrew); CI uses PG 16; docker-compose uses PG 16 + Redis 7 |
| Frontend | React 19, TS 5.9 (`strict:false`, `allowJs`), Vite (rolldown) + vitest + Playwright |
| ECC / Claude | Curated ECC v2.2.3 vendored in `.claude/` (agents, skills, path-scoped rules, hooks: bash guard, pre-commit secret check, index rebuild). Verified current on 2026-11-16 (`.claude/memory/decisions.md`). Not reinstalled; no config change needed |
| Code index | `.claude/index/` (symbols / imports / dependents), auto-rebuilt by hooks |

## What exists

- **Backend:** 8 apps (accounts, allotment, bill_of_entry, core, license, reconciliation, tasks, trade) and 82 models (+7 core sync). Cyclic app imports (core↔license). There is no selectors layer. About 24 files exceed 800 LOC. Root-level ad-hoc scripts have been archived to `scripts/adhoc/` (2026-11-16). Detail: [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), [BACKEND_STRUCTURE.md](BACKEND_STRUCTURE.md).
- **API:** `/api/` prefix, no versioning, JWT (+ query-param JWT). See [API_ARCHITECTURE.md](API_ARCHITECTURE.md).
- **Frontend:** 326 TS + 33 JS files, one axios instance (110 dependents), duplicated wrappers, components and role constants. See [FRONTEND_STRUCTURE.md](FRONTEND_STRUCTURE.md).
- **DB:** 119 tables, 253 FKs (all validated), 772 indexes, 3 matviews, migrations consistent. Legacy unowned tables (eScrap/ebrc/shipping_bill) must be kept. See [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md), [DATABASE_ER_DIAGRAM.md](DATABASE_ER_DIAGRAM.md), [MIGRATION_REGISTER.md](MIGRATION_REGISTER.md).
- **Celery:** schedule in `lmanagement/celery.py`; beat names may not match registered tasks (being verified).
- **Tests:** backend ≈3,000 tests with pre-existing failures (1 collection error, 5 fixture, 7 logic); frontend 549 tests (1 failure), lint 3 errors in an ad-hoc script. See [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md).
- **Repo hygiene:** 263 root reports and 35 ad-hoc scripts archived. 217 MB of licence PDFs remain tracked (`backend/DFIA_COPY`), pending owner decision.

## Database environment

The local `lmanagement` DB is **replaced by `scripts/database/db-tools.sh sync` runs** (10:45 and 15:32 on 2026-11-16, each from a different remote). Every dataset seen has been dumped, restore-verified and kept. See [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) and [DATA_INTEGRITY_REPORT.md](DATA_INTEGRITY_REPORT.md). Staging and production are not identified and have not been touched ([DATABASE_SAFETY.md](DATABASE_SAFETY.md)).

## Business-rule state

Negative licence balances were previously floored at 0. The owner decided on 2026-11-16 to show the signed value plus an `is_over_utilised` flag. This is implemented in commit `85370c94`, with caps clamped so allocation and planning are unchanged. See `.claude/rules/business-rules.md`.
