# Generic ERP architecture (hub)

Central spec for the ECC-driven generic ERP work. **This file links; it does not restate.** Precedence is
in [README](README.md) (project rules > ADR-003 > vendored ECC). Verified against `feature/v5` @ `b099789c`.

## 1. The generic layer already exists — reuse, do not rebuild

| Layer | Generic implementation (file:line) | Driven by |
|---|---|---|
| Backend CRUD | `MasterViewSet` `backend/apps/core/views/master_view.py:81`; factory `create_viewset(model, serializer, config)` `:218` | per-module `config` (search, filters, ordering, nested) |
| Pagination / permission / search | `StandardPagination`, `MasterDataPermission`, `CaseInsensitiveSearchFilter` (same file) | [api-contract-standards.md](api-contract-standards.md) |
| MDS write-through | `backend/apps/core/mds_write.py` (`save_through_mds`, `delete_through_mds`) + sync registry `core/sync/registry.py` | ADR-001 |
| Frontend list/form | `frontend/src/pages/masters/MasterList.tsx`, `MasterForm.tsx`, `masterListConfig.ts`, `entitySections.ts`, `NestedFieldArray.tsx` | route `/masters/:entity` (`routes/AppRoutes.tsx:334`) |
| Workspace / shared UI | `components/workspace/*`, `components/shared/*` | [generic-component-registry.md](generic-component-registry.md), [shared-ui-standards.md](shared-ui-standards.md) |
| Backend services | [shared-service-registry.md](shared-service-registry.md) | ADR-003 layering |

`create_viewset` consumers: 17 in `core/views/views.py` (masters), plus licence, allotment, BOE, 3× trade, incentive.
So "build generic once, prove on Licence" is **already true**: Licence, Allotment, BOE, Trade and Incentive
routes render through `MasterList`.

## 2. What stays out of the generic layer (domain-isolated)

CIF/balance math, allotment/BOE/invoice reconciliation, the BOE frozen ledger and accounting posting
remain in their services (`.claude/rules/business-rules.md`, ADR-004). Generic CRUD must never replace them.

## 3. Related hubs

[GENERIC_ERP_EXECUTION_PLAN](GENERIC_ERP_EXECUTION_PLAN.md) · [MODULE_MIGRATION_MATRIX](MODULE_MIGRATION_MATRIX.md) ·
[AGENT_TASK_OWNERSHIP](AGENT_TASK_OWNERSHIP.md) · [API_CONTRACTS](API_CONTRACTS.md) ·
[ARCHITECTURE_DECISIONS](ARCHITECTURE_DECISIONS.md) · [TEST_AND_QA_REPORT](TEST_AND_QA_REPORT.md) ·
[CURRENT_BLOCKERS](CURRENT_BLOCKERS.md). Workstream checkpoints: `docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md`.

## 4. Licence UI as the standard — mapping to generic Masters (2026-11-17)

Masters reuse the licence/BOE presentation; no new components or CSS were introduced.

| Licence pattern (reference) | Shared piece | Masters usage |
|---|---|---|
| Register toolbar: inline breadcrumb + h1 + count + search + Filters popover + Excel/PDF + Add New | `MasterList` `COMPACT_REGISTER` branch → `AdvancedFilter` `toolbarStart/End` | Every `masterEntities` entry opts in; breadcrumb parent "Masters" (`/masters`) |
| Register rows (`features/licenses/LicenceCard`): bordered compact row, mono identifier, muted meta, status badge, one action menu | `ActionMenu`, `StatusBadge`, `LoadingState`, `EmptyState` | `tables/GenericMasterCards` (columns from `list_display`; `is_active` → badge) |
| Record workspace (`BoeDetailPage`, licence overview): breadcrumbs, meta badges, primary + secondary actions, tabs | `ModuleWorkspace`, `WorkspaceSection`, `FieldGrid`, `ActivityTimeline` | `pages/masters/MasterDetail` (`/masters/:entity/:id`): Details (fields + audit timestamps), History (real `ActivityLog`, USER_MANAGER) |
| Confirmed destructive actions | `ActionMenu` `confirm` → `ConfirmProvider` | Delete on the row menu (existing `confirmDelete`) and on the record page |
| Forms | `MasterForm` (labels, required marks, inline validation, sticky bars where enabled) | unchanged |

History = the audit log of successful writes to the record's own URL. Creation is a POST to the list URL, so it cannot be
attributed to a record and is not shown. "Created by"/"Updated by" appear only when the API sends a name, not a raw id.

## 5. Generic bulk actions (2026-11-18)

`POST /api/masters/<entity>/bulk/` — `apps/core/services/master_bulk.py`, wired once in `MasterViewSet.create_viewset`.
Per record: the viewset's own `perform_update` / `perform_destroy` (validation, delete protection, MDS write-through
unchanged) inside its own transaction together with its audit row (written first), so one refusal never rolls back the
others and nothing changes unaudited. An MDS outage stops the batch and reports the rest as not attempted. Max 200 keys.
Enabled for `core` masters except the CIF/planning masters (head norms, SION classes, SION export/import, exchange rates).
Domain viewsets (licences, BOEs, trades, allotments, incentive) never get it. The UI reads `bulk_actions` from list
metadata; `BulkSelectionSummary` is shared with `DataTable`.

Live licence UI reference (measured 2026-11-18 on `localhost:5173/licenses`, read-only): rows 50 px, 10 px radius,
slate-300 border, ~5 px gap, Inter 13.5 px; identifier 13.5/600 monospace `rgb(0,102,204)`; soft status badges; 26/600
h1 and 36 px inline search in one toolbar; no overflow at 390 px. `masters-workspace.real` asserts master rows match the
licence register's radius, border colour and font (height within 6 px).

## 6. Master rows = licence register rows (2026-11-18)

Per-master column configuration: `frontend/src/pages/masters/masterColumns.ts` (`MASTER_COLUMNS`, one entry per
registered master; fields verified against real API rows). First column = identifier (monospace link to the record,
like the licence number); then the master's columns on one CSS grid; `details` appear only when the row expands
(non-empty values only, plus audit timestamps). One header row carries select-all and the column labels (bulk actions
replace the labels while rows are selected), so labels are not repeated per row on desktop. Rows: expand chevron,
click-anywhere-to-expand (controls excluded), status badge + ActionMenu in a fixed trailing slot — the `LicenceCard`
anatomy. Toolbar and filters are the licence `COMPACT_REGISTER` toolbar (filters closed until opened; no Filters control
on masters without filters). Masters without an entry use `defaultMasterColumns` (skips ids, MDS sync, audit, status).
