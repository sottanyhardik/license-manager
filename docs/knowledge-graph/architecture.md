# Architecture

> Living document. Update only affected sections — never regenerate whole file.
> Last updated: Phase 0 scaffold.

## System Overview

Hybrid rebuild: `legacy/` is the read-only reference implementation.
`backend/` and `frontend/` are the new production codebase.
Both share a single PostgreSQL database with backward-compatible migrations.

## Deployment Topology

```
                    ┌─────────────────────────────────┐
                    │          nginx (HTTPS)           │
                    └────────────┬────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
        /api/v1/*          /api/*            /  (static)
              │                  │                  │
        ┌─────▼─────┐    ┌───────▼──────┐   ┌──────▼──────┐
        │ backend/  │    │   legacy/    │   │  frontend/  │
        │ (new)     │    │  backend/    │   │  (new)      │
        │ :8001     │    │  :8000       │   │  dist/      │
        └─────┬─────┘    └───────┬──────┘   └─────────────┘
              │                  │
              └──────────┬───────┘
                         │
                  ┌──────▼──────┐
                  │ PostgreSQL  │
                  │   Redis     │
                  └─────────────┘
```

## Key Architectural Decisions

- ADR-001: Hybrid migration strategy
- ADR-002: Single shared PostgreSQL database
- ADR-005: `/api/v1/` prefix on all new endpoints
- ADR-007: Service layer — views never touch ORM directly
- ADR-008: No synchronous cross-app signals in new app

## Modules

See `modules.md` for per-module detail.
