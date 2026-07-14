# ADR-001 — Migration Strategy: Hybrid Parallel-Run

**Status:** Accepted
**Date:** 2026-07-14

## Context

The License Manager is a mature production application that has accumulated
significant technical debt. A clean rewrite is needed, but full rewrites carry
the highest delivery risk: they routinely ship late, break edge-case business
logic that only surfaces in production, and leave no safe fallback path.

An in-place refactor of the existing monolith avoids the big-bang risk but
produces an intermediate state that is neither fully clean nor fully legacy,
making it hard to reason about correctness at any point in the migration.

The business requires continuity of service throughout the migration period.
License operations (BOE, allotments, DGFT queries) cannot be interrupted.

## Decision

Adopt a **hybrid parallel-run** strategy:

1. The existing application is preserved verbatim under `legacy/` and treated
   as read-only reference code (see ADR-010).
2. The rebuilt application lives under `backend/` (Django) and `frontend/`
   (React), developed from scratch against the same PostgreSQL database.
3. A **single shared PostgreSQL instance** serves both apps simultaneously
   (see ADR-002). nginx routes requests to legacy (port 8000) or new app
   (port 8001) based on URL prefix (see ADR-005).
4. Migration proceeds **module by module** (e.g. licenses, then BOE, then
   allotments). Each module is migrated, tested, and accepted before the next
   begins.
5. Production traffic does not switch until **all 6 gate criteria are met
   simultaneously** (see ADR-009).
6. At final cutover, the nginx upstream flip is the only infrastructure change.
   No data migration is required because both apps share the same DB.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Full rewrite (greenfield, new DB) | Highest risk: business logic gaps only appear in prod; long period with no production-grade fallback; ETL required at cutover. |
| In-place refactor | Intermediate states are neither clean nor legacy; hard to gate quality; no safe rollback to a known-good reference. |
| Strangler-fig with separate DB | Dual-write or ETL complexity during transition; data consistency risk between two live databases. |

## Consequences

**Positive:**
- `legacy/` is the ground-truth reference for every business rule. Developers
  can read legacy code to understand intent before reimplementing.
- Rollback during transition requires only an nginx upstream change (seconds).
- Module-by-module delivery means partial value can be captured early (e.g.
  new API endpoints consumed by the new SPA while legacy handles other routes).
- Zero data migration risk at cutover: DB state is always authoritative.

**Negative:**
- Two codebases must be understood by developers during the transition period.
- Schema must remain backward-compatible throughout (additive-only migrations,
  see ADR-002).
- Any emergency fix to legacy business logic requires a 5-day backport window
  to the new app (see ADR-010).
- nginx routing configuration is slightly more complex during transition.

## Related ADRs

- ADR-002 — Database Strategy: Single Shared PostgreSQL
- ADR-005 — API Versioning: /api/v1/ prefix
- ADR-009 — Production Cutover Gate: 6 Simultaneous Criteria
- ADR-010 — Legacy Read-Only Rule
