# Current state and evidence index

| ID | Status | Evidence | Use / limitation |
|---|---|---|---|
| EV-01 | CONFIRMED | Git `develop` at `d2cb2446`; `origin/HEAD` develops; master diverges. | Deployed revision unknown. |
| EV-02 | CONFIRMED | Local `/`, `/api/health/`, `/api/schema/` return HTTP 200. | Availability only. |
| EV-03 | CONFIRMED | Sample unauthenticated business APIs return HTTP 401. | Does not prove object/company access. |
| EV-04 | CONFIRMED | Authenticated local Dashboard/Licence/BOE/Reconciliation/Planning UI read-only observations. | No mutations/test transactions. |
| EV-05 | CONFIRMED | Frontend test: 543/544 passed; lint: 3 errors/9 warnings; typecheck passed. | No backend/integration PASS claim. |
| EV-06 | CONFIRMED static | Existing assessment cites condition pools, SION capacity, roles and invoices/payments. | `.Codex/index/` missing; dependency graph unavailable. |

Existing reports in `docs/assessment/` are retained as prior evidence. Earlier master-sync/UI notes were treated as context, not proof of current runtime behaviour.
