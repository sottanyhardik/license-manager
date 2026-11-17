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
