# ADR-003 — Backend Tech Stack

**Status:** Accepted
**Date:** 2026-07-14

## Context

The new backend must be compatible with the legacy codebase (same Django major
version, same DB driver family) to share a database safely (ADR-002) and allow
token interoperability during transition (ADR-006). Tooling choices affect
developer velocity, CI speed, and long-term maintainability.

The legacy backend runs Django 6.0.4 in production (confirmed in
`legacy/backend/requirements.txt`). Python 3.13 is the current stable release
with the highest performance gains from the free-threading and JIT work.

## Decision

The new backend uses the following stack:

**Runtime and framework:**
- Python 3.13
- Django 6.0.x (matching the legacy major version for DB and ORM compatibility)
- Django REST Framework (DRF) — serializers, viewsets, routers
- drf-spectacular — OpenAPI 3.1 schema generation and Swagger UI
- django-filter — queryset filtering via URL params
- django-cors-headers — CORS for the React SPA
- django-health-check — `/api/health/` endpoint (ADR-005)
- django-simple-history — row-level audit log on all business models

**Auth:**
- djangorestframework-simplejwt (SimpleJWT) — see ADR-006

**Async and background tasks:**
- Celery 5 with Redis as broker and result backend — see ADR-008
- redis-py / django-redis for cache

**Database:**
- PostgreSQL (shared instance per ADR-002)
- psycopg3 (not psycopg2) — native async support, binary protocol

**Package management and linting:**
- uv — package manager and virtual-env manager (replaces pip + pip-tools)
- Ruff — linter (line-length = 120, replaces flake8 + isort + pyupgrade)
- Black — formatter (line-length = 120)

**Testing:**
- pytest + pytest-django
- factory-boy + Faker — test data factories
- pytest-cov — coverage reporting

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Poetry | Slower dependency resolution than uv; uv is now the de facto standard for new Python projects. |
| flake8 + isort | Ruff subsumes both plus pyupgrade and pep8-naming in a single Rust binary; 10-100x faster in CI. |
| psycopg2 | Older C extension; no native async; psycopg3 is the current maintainer-recommended version. |
| FastAPI instead of Django | Legacy is Django; sharing DB safely and matching ORM behaviour requires staying in Django. FastAPI would need its own migration tooling, separate auth, and separate admin. |
| Django 5.x or 4.x | Legacy is already on Django 6.0.4. Using a different major version for the new app risks ORM and migration incompatibilities on the shared DB. |

## Consequences

**Positive:**
- Version parity with legacy (Django 6.0.x) eliminates ORM edge-case
  differences when both apps read/write the same tables.
- drf-spectacular produces a live OpenAPI spec that serves as ground-truth API
  documentation, reducing docs drift.
- uv + Ruff reduce CI time and eliminate the "works on my machine" dependency
  problem.
- psycopg3 binary protocol reduces query round-trip latency vs psycopg2.
- factory-boy makes test isolation reliable without fixture files.

**Negative:**
- Python 3.13 is very recent; some third-party packages may not yet publish
  3.13-compatible wheels. Monitor package compatibility at each dependency
  update.
- django-simple-history adds one INSERT per audited model save; high-volume
  bulk operations must use `skip_history=True` or `bulk_create` with explicit
  audit records.
- Celery 5 + Redis requires two additional production services (worker process,
  Redis instance) beyond the Django app server.

## Related ADRs

- ADR-002 — Database Strategy: Single Shared PostgreSQL
- ADR-006 — Authentication: SimpleJWT with shared signing key
- ADR-008 — Signal Strategy: Celery Replaces Cross-App Signals
