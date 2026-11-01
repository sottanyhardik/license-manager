# API and integration inventory

**Verified by runtime URL resolution.** `backend/lmanagement/urls.py` mounts accounts, licence, allotment, BOE, trade, reconciliation, tasks, masters and sync APIs. At this worktree, Django resolves **476 API URL patterns**. Removing DRF format-suffix aliases and API-root entries produces **249 distinct registered API patterns backed by 75 view classes**. This is the authoritative endpoint-pattern baseline; it still does not prove every method/serializer/permission/consumer contract.

**Verified by OpenAPI generation.** `manage.py spectacular --validate` generated a schema with **246 paths and 354 HTTP operations**, completed with 0 errors and 22 warnings (6 unique warning classes). The three-pattern difference from the normalized resolver baseline is itself traceability evidence: framework/docs/media/catch-all paths need an explicit disposition rather than being silently omitted.

| OpenAPI family | Paths | Operations | Audit status |
| --- | ---: | ---: | --- |
| Licence / licence-prefixed resources | 69 | 81 | Partial |
| Master data | 49 | 105 | Partial |
| Root/other (health, dashboard, reports and miscellaneous) | 37 | 46 | Partial |
| Trade | 24 | 36 | Partial |
| Auth/users | 11 | 17 | Partial |
| Allotment | 11 | 15 | Partial |
| BOE | 11 | 15 | Partial |
| Reconciliation | 14 | 14 | Partial |
| Tasks | 7 | 12 | Partial |
| Reports | 7 | 7 | Partial |
| Sync | 6 | 6 | Partial |

The OpenAPI warnings concern inferred Ledger path-parameter types (`job_id`, `item_id`, `trade_id`, `request_id`) and colliding operation IDs for ledger download/readiness paths. They are P1 contract-quality work: consumers must not treat these generated schemas as fully unambiguous until annotations/operation IDs are corrected and contract-tested.

The supporting static registration inventory is **37 DRF router resources**, **33 app-level explicit paths**, **6 root direct API paths**, and **130 `@action` decorator occurrences**. Router CRUD verbs, multi-method actions, inherited/dynamic master viewsets and route-name expansion explain the difference from the runtime resolver total.

| Mounted prefix | Router resources | Explicit application paths | Custom action occurrences | Notes |
| --- | ---: | ---: | ---: | --- |
| `api/auth/` | 1 | 7 | 2 | Auth plus user management |
| `api/` licence | 13 | 13 | 78 | Licence, planning, ledger, reports and downloads; highest dynamic surface |
| `api/` allotment | 2 | 0 | 8 | Allocation actions and exports |
| `api/` BOE | 1 | 1 | 8 | BOE parsing, corrections and transfer actions |
| `api/` trade | 3 | 1 | 14 | Trade lines/payments/document actions |
| `api/` reconciliation | 1 | 0 | 14 | Read diagnostics plus link/merge/note/recalculate |
| `api/` tasks | 1 | 0 | 5 | Task lifecycle actions |
| `api/masters/` | 15 | 5 | 1+ | Generic master viewset can add inherited actions |
| `api/sync/` | — | 6 | — | Sync push/pull/status/media/conflicts |

| Family | Primary capability | Contract / V1 treatment |
| --- | --- | --- |
| Accounts | login, refresh, logout, profile, password, user management | Preserve JWT contracts; map roles and denial cases. |
| Licence | licence/item CRUD, balance/ledger/report operations, planning | Stabilize DTO and dual-balance provenance. |
| Allotment | availability, allocation/deallocation, plans, grouped exports | Protect live-CIF and plan-line isolation contracts. |
| BOE | import evidence, rows, parsing and visibility | Document file/row lifecycle and correction semantics. |
| Trade/reconciliation | trade documents, invoices/payments and BOE allocation | Do not imply bank/GL scope. |
| Masters/sync/tasks | reference data, sync, task/replan package lifecycle | Contract async recovery/idempotency. |

External/runtime integrations: Redis is broker/result backend for Celery; file/PDF/XLSX generation/parsing and master-data synchronization are present. Their credentials and live endpoints were not inspected. This is **Verified by code** for registration, **Requires owner approval** for external service policy.

### Contract-completion gate

For every one of the 354 OpenAPI operations (plus resolver-only patterns), record method, normalized path, owner/view/action, request/response serializer, authentication/permission, filters/pagination, side effect/transaction, frontend/external consumer, tests and disposition. The runtime resolver and schema commands used PyCharm's configured `.venv` Python 3.14.6 and did not mutate data. Endpoint-level contract extraction remains outstanding.

The operation register already records schema-declared request/response/security metadata for every operation. `jwtAuth`/`cookieAuth` in that export describes authentication schemes, not object-level authorization; `To reconcile` remains mandatory for permission class and company/object scope.

Runtime reconciliation resolved **354/354 OpenAPI operations** to a Django callback view class. This proves route ownership, not permission or serializer behavior; the remaining endpoint-contract work is now bounded to the unresolved fields in the operation register rather than unknown route registration.

### Action-family traceability increment

The [API action and workflow traceability map](../09-traceability/api-action-workflow-map.md) source-family maps **354/354 operations**, including high-consequence, auth/user, generic-master, peer-sync, dashboard/upload, report, specialised planning and protected-media families. It records known action-specific permission overrides, transaction/task boundaries, model/service imports and named tests without falsely promoting the generated operation rows to verified contracts. Every operation still retains an explicit individual contract-mapping requirement.

Static view metadata was also extracted for all 354 operations: 353 expose a declared permission class; the SimpleJWT refresh operation has no class-level declaration and requires framework/default-policy review. 104 operations have no direct `serializer_class` and 137 have no direct `queryset.model` (both may be deliberately dynamic). These dynamic cases are not defects by themselves; they are source-review targets for action-aware serializer/model/transaction mapping.

Static import reconciliation found a source file for 353/354 resolved callbacks and direct indexed imports for 349/354. These imports make model/service/report dependencies reviewable, but they are view-level—not proof that every DRF action invokes every import. Action-level dependency status remains Partial.
