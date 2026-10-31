# Route and workflow inventory

Route authority is `frontend/src/routes/AppRoutes.tsx:60-335`. All entries below are **STATICALLY INSPECTED** unless noted; no route is claimed functionally verified. Client guards are in `routes/ProtectedRoute.tsx:22-44`; backend API enforcement is separately assessed.

| ID | Path(s) | Component/workflow | Access | Status / scope |
|---|---|---|---|---|
| R01 | `/login`, `/forgot-password`, `/401`, `/403` | Login, reset, auth error | Public | Login mock browser check PARTIAL; other routes static. |
| R02 | `/`, `/dashboard`, `/profile`, `/pdf-viewer` | Landing/dashboard/profile/PDF | Authenticated | Static; add error/empty/a11y E2E. |
| R03 | `/licenses`, `/licenses/create`, `/licenses/:id/edit`, `/licenses/:id/overview`, `/licenses/:id/balance` | Licence CRUD/overview; balance redirects | Licence roles | Static; characterise balance/edit and redirect. |
| R04 | `/planning` | SION licence planning | LICENSE_MANAGER | Static; restriction/concurrency E2E required. |
| R05 | `/allotments`, `/allotments/create`, `/allotments/:id/edit`, `/allotments/:id/allocate` | Allotment/allocate | Allotment roles | Static; allocation/plan-cap tests required. |
| R06 | `/bill-of-entries`, `/bill-of-entries/create`, `/bill-of-entries/:id/edit`, `/bill-of-entries/:id/generate-transfer-letter` | BOE and transfer letter | BOE/TL/account roles | Static; upload/validation/recovery E2E required. |
| R07 | `/trades`, `/trades/create`, `/trades/:id/edit` | Trade/invoice/payment | Trade roles | Static; posting and paired trade tests required. |
| R08 | `/reconciliation`, `/reconciliation-issues` | BOE/invoice exception triage | Reconciliation roles | Static; not bank reconciliation. |
| R09 | `/incentive-licenses`, `/create`, `/:id/edit` | Incentive licence CRUD | Incentive roles | Static. |
| R10 | `/ledger-upload`, `/license-ledger`, `/license-ledger/download-requests`, `/:requestId`, `/package-readiness/:jobId`, `/:licenseId`, `/:licenseId/:itemId` | Ledger package/upload/detail | Licence/trade/ledger roles | Static; job resilience/download security E2E required. |
| R11 | 11 `REPORT_ROUTES`: `/reports/parle/sion-e1`, `sion-e5`, `sion-e126`, `sion-e132`, `/expiring-licenses`, `/active-licenses`, `/download-license`, `/item-pivot`, `/item-report`, `/planned-report`, `/license-purchase-profit` | Reports/exports | REPORT_ROLES | Static; parity with canonical service required. |
| R12 | `/masters/:entity`, `/create`, `/:id/edit` (8 configured entities) | Master list/form | Authenticated / USER_MANAGER writes | Static; global/tenant policy required. |
| R13 | `/settings`, `/admin/users`, `/admin/users/create`, `/admin/users/:id/edit`, `/admin/activity-log`, `*` | Admin and 404 | Superuser/USER_MANAGER/public 404 | Static. |

API discovery: root composition is `backend/lmanagement/urls.py:31-79`; router groups exist for auth, licences/action/items/plans/SION rules/ledger/reports, allotments/actions, BOEs/PDF parse, trades/lines/payments/invoice document, BOE-invoice reconciliation, tasks, masters/sync and schema/docs. Every endpoint requires a separate API contract/permission execution matrix before release.

Workflow inventory: licence intake→items→plan→allotment→BOE/trade→reports; import PDF parsing; ledger upload/package jobs; master maintenance/sync; reconciliation triage; user/role administration. Preconditions, error/recovery and database effects are statically derivable from the named services, but execution status remains NOT TESTED outside the mock tests listed in the verification report.
