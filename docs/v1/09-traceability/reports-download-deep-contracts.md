# Report, export and download deep contracts

This is a bounded direct-source review of **14 registered operations**. It
does not resolve every report endpoint, generated file consumer or dynamic
report DTO. All rows are **Partial**: the cited source and selected tests show
current behavior, but direct role/object policy, report provenance, all error
paths and browser/download recovery are not complete.

**Evidence labels:** C = verified by code; T = a named existing test; I =
static frontend/register evidence; P = proposed V1 closure. OpenAPI declares
no response DTO for every operation here, so code behavior is not a stabilized
external contract.

| API ID(s) | Method/path | Current role | Status |
| --- | --- | --- | --- |
| API-292 | `GET /api/reports/active-licenses/` | active licences JSON/XLSX report | P1 Partial |
| API-293, 051–053 | `GET /api/reports/expiring-licenses/`; legacy viewset list/export/summary | expiry report and legacy compatibility family | P1 Partial |
| API-068–071, 295 | item-pivot list/norms/task/update and direct report route | pivot report and balance-refresh task | P1 Partial |
| API-296, 072–073 | item report plus filter lookups | item report/filter capabilities | P1 Partial |
| API-297 | purchase/profit report | financial report JSON/XLSX/PDF | P1 Partial |
| API-298, 277 | planned report plus planned lookup | plan-centric report/filter capability | P1 Partial |
| API-116 | ledger export | canonical ledger PDF/XLSX download | P1 Partial |
| API-128, 131, 152 | balance XLSX/PDF and multi-licence XLSX | licence-specific financial/customs outputs | P0/P1 Partial |

## Direct contracts

### Active and expiring licence reports — API-292, API-293, API-051–053

- **C:** [`ActiveLicensesReportView.get`](../../../backend/apps/license/views/active_licenses_report.py#L43)
  accepts `days` (safe integer, default 30), `format` (`json`/`excel`) and
  optional `sion_norm`. It queries active GE/MI/IP/SM licences with eligible
  expiry, excludes balance below 100, and returns a period/summary/licences
  envelope; Excel is produced from the same generated data. Its direct route
  is API-292. A report-generation exception becomes JSON `500` with the
  exception text.
- **C:** [`ExpiringLicensesReportView.get`](../../../backend/apps/license/views/expiring_licenses_report.py#L39)
  accepts the analogous fields, selects active eligible licences between today
  and today + `days`, and returns the same broad envelope. It is exposed as
  direct API-293 and viewset API-051 (`list`), API-052 (`export`) and API-053
  (`summary`). The source parses `days` using raw `int`, so invalid input is
  not handled by the view's report-generation `try` block. Source inspection
  does not prove whether every legacy action is semantically identical to the
  direct callback.
- **C:** both views require `ReportPermission`; direct report routes return a
  Django JSON/HTTP response rather than a generated OpenAPI DTO. No company
  filter appears in the shown query, so object/company scope needs D1 rather
  than an inferred tenancy claim.
- **I:** UI-005 and UI-006 currently call paths marked **schema gap** in the
  [P0/P1 route register](p0-p1-route-api-contract-register.md); do not equate
  them with API-292/293 without a request/response capture and source-path
  reconciliation.
- **P closure:** test invalid/negative/large `days`, `format`, empty response,
  XLSX content/disposition, report-role denial and D1-approved scope; decide
  whether to normalize safe parsing and whether the viewset/direct routes are
  compatibility aliases or separately supported contracts.

### Item pivot data and task refresh — API-068–071, API-295

- **C:** [`ItemPivotViewSet.list`](../../../backend/apps/license/views/item_pivot_report.py#L2283)
  delegates to `ItemPivotReportView.get`; API-068 and direct API-295 therefore
  share the pivot builder only if the direct view's request behavior stays
  aligned. This is source ownership, not a proven response-parity assertion.
- **C:** [`available_norms`](../../../backend/apps/license/views/item_pivot_report.py#L2294)
  (API-069) returns active norm class/description rows ordered by norm.
  [`task_status`](../../../backend/apps/license/views/item_pivot_report.py#L2321)
  (API-070) reads an arbitrary Celery `AsyncResult` ID and returns a shape for
  PENDING, PROGRESS, SUCCESS or other states; the source does not establish
  ownership of the task ID. [`update_balance`](../../../backend/apps/license/views/item_pivot_report.py#L2370)
  (API-071) takes an unvalidated `license_status` defaulting to `all`, calls
  `update_all_license_balances.apply_async(..., priority=9)`, and returns
  `202` with task ID/status.
- **C:** all these actions declare `ReportPermission`, including the write
  action. A report reader's ability to trigger a global balance update is a
  policy/action-level question requiring direct role tests—not a frontend
  button decision.
- **T:** [`ItemPivotBalanceConsistencyTests`](../../../backend/apps/license/tests/test_item_pivot_balance_consistency.py#L29)
  provides selected data consistency evidence; it does not exercise task
  ownership, worker failure or endpoint roles. Frontend render/filter tests
  are indexed at `frontend/src/pages/reports/ItemPivotReport.render.test.tsx`
  and `ItemPivotFilters.test.tsx`, but they do not prove browser task polling
  or server authorization.
- **P closure:** define task ownership/TTL and terminal failure behavior; test
  malformed/foreign task ID, report-only/wrong-role/anonymous update attempts,
  queue failure, provenance of resulting balance state, and UI retry/poll
  cancellation. This is P1 with P0 financial consequences.

### Item/planned report lookups and direct reports — API-296, 072–073, 298, 277

- **C:** [`ItemReportViewSet.available_items`](../../../backend/apps/license/views/item_report.py#L748)
  (API-072) returns active item names attached to import rows whose stored
  `available_value` is positive. [`planned_item_names`](../../../backend/apps/license/views/item_report.py#L769)
  (API-073) returns active names used by at least one plan line. Both are
  `ReportPermission` reads and return bare lists of `{id,name}`.
- **C:** [`PlannedReportViewSet.available_items`](../../../backend/apps/license/views/planned_report.py#L488)
  (API-277) returns active plan target names whose import-item stored available
  value is positive and whose licence flag is active. It is a different
  semantic population than API-072; they must not be merged because labels
  look similar.
- **C/I:** API-296 and API-298 are direct report callbacks in `item_report.py`
  and `planned_report.py`; their OpenAPI response is unspecified. Existing
  source renders XLSX with fixed filenames (`item_report.xlsx`,
  `planned_report.xlsx`) under format branches. UI-009/010 describe report
  reads, filters and exports but need a direct consumer/API parity fixture.
- **P closure:** version filter response DTOs, distinguish live/stored
  availability and planned/import populations in the UI, test empty sets,
  stale stored values, permission denial, filter encoding and file-content
  provenance. Item inline PATCH mentioned by UI-009 remains a separate
  mutation/schema gap, not a report read authorization.

### Purchase/profit output — API-297

- **C:** [`LicensePurchaseProfitReportView.get`](../../../backend/apps/license/views/license_purchase_profit_report.py#L131)
  requires `from_date`/`to_date` in ISO date form; supports `norm`,
  `license_number`, comma-separated exclusions, integer `exporter_id`, and
  `format`/`_format` `json`/`excel`/`pdf`. Invalid mandatory dates or exporter
  ID return `400`; builder and renderer failures are logged and return `500`.
  The view passes one builder result unchanged to Excel/PDF renderers rather
  than recomputing totals.
- **C:** it requires `ReportPermission`; the report is commercial evidence,
  not a verified general ledger or bank reconciliation (D5). It exposes user
  display name in generated metadata via `_get_generated_by`, so export
  recipient/retention/log policy must be explicit.
- **I/T:** UI-011 and `LicensePurchaseProfitReport.test.tsx`/builder-path tests
  provide static client/test evidence; no cited test here proves end-to-end
  values, file metadata, role denial or D1 scope.
- **P closure:** golden purchase/sale/profit fixture across JSON/XLSX/PDF;
  date/filter boundary, report-role denial, file response and failed render
  recovery; D5-approved labelling and D1 object scope.

### Canonical ledger and licence balance downloads — API-116, 128, 131, 152

- **C:** [`LicenseLedgerViewSet.export`](../../../backend/apps/license/views/ledger.py#L644)
  requires `file_format` `pdf` or `xlsx` (else `400`), optional authorized
  licence reference, canonical ledger data and nonempty datasets (else `404`).
  It is protected by `LicenseLedgerViewPermission`, not `ReportPermission`.
- **T:** [`test_authenticated_export_endpoint_uses_one_route_for_both_formats`](../../../backend/apps/license/tests/test_license_ledger_export_parity.py#L243)
  asserts `200`, content type and content-disposition for an authenticated
  fixture. The companion [security tests](../../../backend/apps/license/tests/test_license_ledger_export_security.py#L11)
  prove selected anonymous, role-authorized company-filter and invalid-type
  cases; these narrow tests do not prove every export/object branch.
- **C:** [`balance_excel`](../../../backend/apps/license/views/license.py#L899)
  and [`balance_pdf`](../../../backend/apps/license/views/license.py#L862)
  resolve the licence through the viewset object path, accept `show_hidden`
  truthy values and pass it to their respective generators. API-152 delegates
  a posted multi-licence request to `build_bulk_balance_excel`; its generated
  OpenAPI body is the generic licence serializer rather than a documented
  selection DTO.
- **T:** [`BalancePdfEndpointTests`](../../../backend/apps/license/tests/test_balance_pdf_endpoint.py#L15)
  proves selected PDF bytes/disposition, unauthenticated denial and sanitized
  logged generation failure. `test_balance_excel_export.py` covers selected
  XLSX hierarchy/reconciliation structure. Neither proves D1 object scope,
  bulk selection validation, output equality for every balance engine or
  browser blob recovery.
- **P closure:** freeze Customs/Financial labels and hidden-row semantics (D2),
  publish the API-152 request DTO, test viewer/manager/wrong-object role
  behavior, malformed/duplicate selections, no-data/output error recovery,
  generated file provenance and download UI feedback. Do not route these
  downloads through query-token compatibility without D4 approval.

## Schema-gap disposition

The report routes are registered and OpenAPI-valid, but their operation rows
mostly declare no request/response schema. The frontend has additional paths
for active/expiring XLSX downloads that do not conclusively match a registered
operation. V1 must choose one of: (1) retain and document an exact compatible
endpoint/DTO; (2) add it as a versioned registered contract with compatibility
tests; or (3) formally deprecate it after consumer migration. This audit makes
no choice and records every path as Partial.

## Acceptance sequence

1. Establish D1/D2/D4/D5 policy entries relevant to each report.
2. Add positive, anonymous, wrong-role and D1-approved object/company fixtures
   for every listed read/download and API-071 mutation.
3. Assert one golden data fixture serializes consistently to JSON/XLSX/PDF
   where formats are offered; test filename/content type and errors.
4. Repair the E2E harness, then test filter preservation, loading/empty/success/
   error/denied states and protected blob failure without exposing report data.

This slice does not promote an API, route or test denominator to complete.
