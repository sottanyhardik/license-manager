# Dependency Graph

> Living document. Update when a new cross-module dependency is introduced.
> Source: Phase 1 audit (`docs/PHASE_1_REVIEW.md` §2).

## Backend Cross-App Import Counts (legacy — reference)

| Importer | Imports From | Count | Risk |
|---|---|---|---|
| license | allotment, bill_of_entry, core, accounts | 82 | HIGH — hub |
| allotment | accounts, bill_of_entry, core, license | 23 | MEDIUM |
| bill_of_entry | accounts, allotment, core, license | 18 | MEDIUM |
| trade | accounts, bill_of_entry, core, license | 4 | LOW |
| tasks | core | 1 | LOW |
| accounts | core | 2 | LOW |
| core | (none) | 0 | clean leaf |

## New App Coupling Rules (backend/)

- **No direct model imports across apps.** Cross-app reads go through service functions.
- **No synchronous signals for cross-app side effects.** Use Celery tasks (ADR-008).
- **Shared utilities** live in `backend/shared/` — not in any app.
- Circular dependencies are **banned**.

## Frontend Module Dependencies

| Feature | Shared Dependencies | Cross-Feature |
|---|---|---|
| All features | shared/api/client.ts, shared/auth/AuthContext.tsx | none (features are isolated) |
| Reports | licenses (for license selector) | read-only data |
| Allotments | licenses (for license selector) | read-only data |
| Trade | licenses, bill_of_entry (BOE selector) | read-only data |

## Key Library Dependencies (backend/)

> Populated as requirements are pinned.

| Library | Version | Purpose |
|---|---|---|
| Django | 6.0.x | Web framework |
| djangorestframework | 3.x | API layer |
| djangorestframework-simplejwt | 5.x | JWT auth |
| drf-spectacular | 0.x | OpenAPI generation |
| django-filter | latest | Query filtering |
| celery | 5.x | Async tasks |
| psycopg | 3.x | PostgreSQL driver |
