# Route-to-API mapping method

57 frontend route expressions, 249 normalized runtime API patterns (75 view classes), and 354 OpenAPI operations are discovered; they are not yet a reliable one-to-one screen/API count. For each route family, M1 must record: component, user task, backend endpoint/action, method/request/response, backend permission, client role hint, loading/error/empty/denied state, tests, and acceptance criterion.

Initial mapping families: licences → licence/balance/ledger actions; allotments → availability/allocation actions; BOEs → import/row/parse actions; trade/reconciliation → trade/payment/BOE allocation actions; reports → report/export/download actions; masters/users → metadata CRUD/user management. This is **Inferred from static inspection** and not a complete endpoint contract.

| UI family | Direct backend family | Traceability status |
| --- | --- | --- |
| Licence, overview, planning, ledger, reports | licence routers, report paths, ledger/replan paths | Family mapped; individual action/serializer/consumer map incomplete |
| Allotment | allotments and allotment-actions routers | Family mapped; action contract incomplete |
| BOE | bill-of-entries router and parse path | Family mapped; file/row contract incomplete |
| Trade/reconciliation | trade/line/payment and reconciliation routers | Family mapped; payment/document contract incomplete |
| Masters/users | masters/user routers and auth paths | Family mapped; generic metadata permissions incomplete |

Coverage: **57/57 route expressions now have a static frontend component/gate/API-dependency disposition** in the [route workflow map](frontend-route-workflow-map.md). **0/57 route expressions have a completed endpoint-level V1 contract**: the static client calls are not proof of server authorization, action effects, response/error compatibility, or browser behavior. This distinction replaces false route/API certainty and bounds the remaining M1 work.

The [P0/P1 route-to-API contract register](p0-p1-route-api-contract-register.md) converts all 49 priority route IDs into executable state, negative-authorization, recovery, and acceptance gates. Its entries remain Partial until the named tests and server-operation reconciliation exist.

## Machine-generated baseline registers

- [Frontend route register](frontend-route-register.tsv) enumerates all 57 declared route expressions with a stable component ID, route, resolved page component, available client gate and explicit Partial status.
- [API operation register](api-operation-register.tsv) enumerates all 354 OpenAPI operations with a stable ID, method, path, operation ID, tags, declared request schema, response codes, declared security scheme, **runtime-resolved callback view class**, declared permission class, direct serializer class, direct queryset model, DRF action, direct static view imports and source line where indexed, plus explicit fields awaiting source reconciliation.
- [Runtime view-resolution register](api-runtime-view-register.tsv) is the raw 354/354 successful Django resolver mapping used to populate the operation register.

Both are mechanically derived from the current `AppRoutes.tsx` and validated OpenAPI export on 2026-10-31. They are intentionally not evidence of functional correctness: `To reconcile` means no claim has been made about the dependency, authorization, tests or edge cases. This makes the remaining completion scope countable.
