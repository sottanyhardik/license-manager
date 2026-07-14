# ADR-005 — API Versioning: /api/v1/ prefix

**Status:** Accepted
**Date:** 2026-07-14

## Context

During the transition period, the legacy app and the new app are both live and
both serve API traffic from the same domain. nginx must be able to route each
request to the correct upstream without examining authentication tokens or
request bodies — routing must be deterministic from the URL path alone.

The legacy app's endpoints live under `/api/` (no version segment). The new app
needs a distinct prefix so nginx can route without ambiguity.

After production cutover, the new app will serve all traffic and the version
prefix will remain as a stable API contract signal for any external consumers.

## Decision

All new API endpoints use the prefix `/api/v1/`.

nginx routing rules during transition:
- `/api/v1/*` → new app (port 8001)
- `/api/*` → legacy app (port 8000) (catch-all for unversioned paths)

The health endpoint `/api/health/` is served by the new app on port 8001
(unversioned) and is additionally mapped directly for monitoring tools that
expect it at that path.

After cutover, the legacy catch-all rule is removed. Port 8000 stops serving
traffic. The new app handles both `/api/v1/*` and `/api/health/`.

URL namespace convention inside the new app:

```
/api/v1/licenses/         # LicenseViewSet
/api/v1/boe/             # BillOfEntryViewSet
/api/v1/allotments/      # AllotmentViewSet
/api/v1/accounts/        # User/auth endpoints
/api/v1/schema/          # drf-spectacular OpenAPI schema
/api/v1/docs/            # Swagger UI
/api/health/             # Health check (unversioned)
```

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Header-based versioning (e.g. `Accept: application/vnd.lm.v1+json`) | nginx cannot route on headers without complex Lua or njs modules; browser clients cannot easily set custom Accept headers in all contexts; breaks curl and simple tooling. |
| URL path with date (e.g. `/api/2026-07-14/`) | Verbose; clients must update the URL on every API revision; unclear to consumers when to bump the date. |
| Subdomain versioning (e.g. `v1.api.example.com`) | Requires TLS cert per subdomain; DNS changes for every new version; operationally heavier than a URL prefix. |
| No versioning | Impossible to distinguish legacy vs new traffic at the nginx layer without inspecting token claims or request bodies — both are expensive and fragile. |

## Consequences

**Positive:**
- nginx routing is a trivial prefix match — zero per-request overhead.
- External consumers can pin to `/api/v1/` and be unaffected by legacy
  endpoint churn during transition.
- The OpenAPI schema at `/api/v1/schema/` documents only the new API surface,
  not legacy endpoints.
- Health monitoring tools work unchanged through cutover (the health URL does
  not change).

**Negative:**
- External consumers that currently hit `/api/*` must update their URL base
  when migrating to the new API. This is an intentional breaking change,
  managed as part of the cutover communication plan.
- During transition, developers must be careful not to accidentally hit the
  legacy endpoint when testing from tools that don't enforce the `/v1/` prefix.
- The unversioned `/api/health/` on the new app creates one edge-case exception
  to the routing rule (handled by ordering the nginx location blocks correctly:
  exact match `/api/health/` before the prefix match `/api/`).

## Related ADRs

- ADR-001 — Migration Strategy: Hybrid Parallel-Run
- ADR-003 — Backend Tech Stack
- ADR-009 — Production Cutover Gate: 6 Simultaneous Criteria
