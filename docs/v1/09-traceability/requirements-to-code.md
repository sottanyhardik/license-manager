# Requirements-to-code traceability

This is the requirement-level bridge between the 16-workflow inventory and
the endpoint, route, boundary and test registers. A listed file or boundary is
evidence of ownership, not proof that every nested function or generated DRF
action is complete. Every row remains **Partial** unless the linked individual
contract says otherwise.

| Requirement / workflow | Current code-owned boundary | API / UI traceability | Existing verification and remaining closure | Status / V1 disposition |
| --- | --- | --- | --- | --- |
| RQ-01 / WF-01 Authentication and user lifecycle | `apps.accounts.urls`, account auth/password/user views; `accounts/permissions.py`; `core/authentication.py` | API-019/024 and the identity rows in [auth/master operation contracts](api-operation-contracts-auth-masters.md); UI-012–015, UI-048, UI-053–055 | Canonical auth/permission and frontend login/auth-hook tests are named in [workflow test map](critical-workflow-test-map.md). Close refresh/revocation, per-operation role denial and D4 transport policy. | Partial / KEEP, IMPROVE |
| RQ-02 / WF-02 Licence master, items and documents | `LicenseDetailsViewSet`, nested serializers, licence item/document services | API-119–155; UI-018–021, UI-045; route/action register | Licence API/app and MasterForm/List tests exist. Close nested-write, parser/upload rollback, direct action policy and object-scope evidence. | Partial / IMPROVE |
| RQ-03 / WF-03 Customs and financial balances/ledgers | `LicenseBalanceCalculator`, licence properties, ledger view/package services | Balance/ledger API-092–118, API-123/131/141–149; UI-039–045 | Characterization tests are named in WF-03. Map every displayed/report output to a named engine/as-of input; D2 approval required before consolidation. | Partial / IMPROVE, no merge |
| RQ-04 / WF-04 Planning and SION restrictions | SION/plan services, replan request/task boundaries | API-121/122/127 and API-242/299–314; UI-021 | Planning/replan suites establish bounded current behavior. Close state/retry contract and D3 pool/restriction policy. | Partial / IMPROVE |
| RQ-05 / WF-05 Allotment allocation and release | `AllotmentActionViewSet`, allocation services/models | API-003–017; UI-022–025 | P0/API deep trace and allocation suites cover selected caps/effects. Close concurrent public submission, release/reversal and action-level direct-role/object tests. | Partial / IMPROVE |
| RQ-06 / WF-06 BOE/import evidence | `BillOfEntryViewSet`, parser and BOE services | API-035–049; UI-026–029 | Parser/API/hide tests are named in WF-06. Close correction/hide/restore/error matrix, file retry/cleanup and missing BOE UI test evidence. | Partial / IMPROVE |
| RQ-07 / WF-07 Trade, invoice and payment evidence | `LicenseTradeViewSet`, trade lines/payments and invoice-document service | API-333–350 and invoice capability rows; UI-030–032 | Trade/service/document tests exist. Close payment lifecycle, correction/reversal, financial output and D5 scope. | Partial / IMPROVE |
| RQ-08 / WF-08 Reconciliation | `ReconciliationViewSet`, allocation/BOE services and immutable log models | API-278–291; UI-033–034 | API-282/283/288/290 direct effects traced. Close exact HTTP error/role/company/race cases and operator recovery. | Partial / IMPROVE |
| RQ-09 / WF-09 Reports and protected exports | report viewsets/direct report paths, balance PDF/Excel services | Report API rows and UI-001–011, UI-047 | Selected export/auth tests named in WF-09. Reconcile schema gaps, generated-file provenance, role denial and browser blob recovery. | Partial / IMPROVE |
| RQ-10 / WF-10 Ledger package/download jobs | ledger viewset, job/item models and Celery tasks | API-097–115; UI-038–044 | Deep trace covers APIs 097/102/103/106/108/112. Close worker/storage failure, owner scope, idempotency and D4 download posture. | Partial / IMPROVE |
| RQ-11 / WF-11 Master data and peer sync | master generic views, `core.sync` service/events; MDS and MDS-client | API-165–268 plus sync endpoints; UI-050–052 | Isolated MDS/MDS-client suites passed. Close dynamic entity/action DTOs, peer provisioning and restore/replay drill. | Partial / IMPROVE |
| RQ-12 / WF-12 Task management | task models/views and background state transitions | task API contract rows; no located registered task UI page | Task-model evidence exists but action tests are not individually linked. Close role/status/comment/recovery paths. | Partial / KEEP, IMPROVE |
| RQ-13 / WF-13 Activity and audit history | activity middleware/models, reconciliation/BOE logs and command/task paths | activity-log API/UI disposition; BW-07/BW-12 | Connection/log-effect tests exist. D6 determines whether best-effort history or durable audit is required; close retention/retry/access proof. | Partial / IMPROVE |
| RQ-14 / WF-14 Administration and configuration | users, companies, masters, rates and maintenance commands | UI-048, UI-050–055; master/user API rows | Master authorization/delete-protection and account command evidence exists. Close command flags/dry-run/backup/operator policy and privilege escalation tests. | Partial / IMPROVE |
| RQ-15 / WF-15 Accounting/GL/bank reconciliation | Trade/reconciliation-adjacent commercial evidence only | No verified bank/GL API or route contract | Existing tests do not establish a general ledger or bank reconciliation domain. D5 must approve scope before requirements are created. | UNDECIDED / no fabricated capability |
| RQ-16 / WF-16 Company/tenant isolation | cross-domain querysets, role permission classes and protected media | Every company/object-bearing API/route; security contracts SCP-03/04/07 | Current tests demonstrate selected role-scoped multi-company behavior, not a universal tenancy policy. D1 must define required exceptions and denial cases. | Partial / UNDECIDED |

The canonical workflow source map is [workflow-register.md](workflow-register.md); exact API and UI identifiers are maintained by [the operation register](api-operation-register.tsv), [route register](frontend-route-register.tsv), and [P0/P1 route/API register](p0-p1-route-api-contract-register.md). The P0 evidence slices are [deep API contracts](p0-api-deep-contracts.md), [frontend actions](frontend-p0-action-contracts.md), and [security paths](security-critical-paths.md).

Counts are static-map counts, not runtime coverage. Full function-to-caller coverage remains incomplete because the index does not enumerate dynamic registration reliably.

## Audit-status semantics

| Status | Meaning |
| --- | --- |
| Verified | Source/runtime/test evidence proves the required trace fields for the component. |
| Partial | Component is located and classified, but one or more callers, effects, authorization, contract or tests are not reconciled. |
| Failing | A current test/runtime check disproves its expected behavior. |
| Unverified | Discovered but not yet reviewed with adequate evidence. |

At this stage, endpoint patterns are **Partial** (registered at runtime but contracts incomplete); frontend routes are **Partial** (declared and role-hinted but API/state/browser mapping incomplete); the 8,046 indexed backend symbols are **Partial at domain level**, not individually verified.

The operation and route registers establish the current measurable denominator: 354 API operations and 57 route expressions. Completion requires each record to replace all `To reconcile` fields with concrete evidence or a documented exclusion.

[Backend symbol register](backend-symbol-register.tsv) establishes the callable/source denominator: **8,046 symbols** under `backend/`, including every indexed function, method, class, model, serializer, view, route and test. It is machine-derived from the current static index and explicitly marks every record Partial; an indexed symbol is not treated as a working, callable, reachable or tested business function without further evidence.
