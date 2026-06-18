# Context — Architecture

Orientation only. Authoritative detail lives in `docs/` — links below.

## One-paragraph map

React 19 SPA (TypeScript, Tailwind v4, shadcn/ui) talks to a Django 6 + DRF backend over
`/api/*` with JWT auth. The backend is 7 apps — `accounts core license bill_of_entry allotment
trade tasks` — where `core` holds shared base classes (`MasterViewSet`, `AuditModel`) and master
data. PostgreSQL (psycopg 3) is the store; Redis + Celery run async ledger processing; balances
are materialised via signals. Django (WhiteNoise) serves the built frontend (`frontend/dist`).
Three servers run the app; `license-manager` is canonical and syncs master data one-way to
`labdhi` and `tractor`.

## Deep dives

| Topic | File |
|---|---|
| Full architecture + Mermaid diagrams | `docs/02-architecture.md` |
| Project overview / domain / topology | `docs/01-project-overview.md` |
| Code splitting / lazy routes | `docs/architecture/CODE_SPLITTING_GUIDE.md` |
| Materialized views / balances | `docs/architecture/MATERIALIZED_VIEWS_GUIDE.md` |
| Redis caching | `docs/architecture/REDIS_CACHING_GUIDE.md` |
| Modularization plan | `docs/architecture/MODULARIZATION_MASTER_PLAN.md` |
| Frontend stack rules + gates | `.claude/rules.md` |
| Frontend project notes | `.claude/memory/project.md` |

## Quick facts an AI usually needs

- ViewSet base: `backend/apps/core/views/master_view.py:69` (`MasterViewSet`).
- Audit base: `backend/apps/core/models.py:40` (`AuditModel`).
- Frontend API instance: `frontend/src/api/axios.js` (GET dedup + JWT refresh queue).
- No global state store; contexts: `AuthContext`, `ThemeContext`, `ToastContext`.
