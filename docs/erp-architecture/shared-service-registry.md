# Shared service registry

Reuse these before writing new code. Refs at base `9fc44ad3`. Balance code is protected (`.claude/rules/business-rules.md`): call it, never re-derive it (ARCHITECTURE_RULES rule 4).

## Backend

| Service | Location | Purpose | Known consumers |
|---|---|---|---|
| `MasterViewSet.create_viewset` | `apps/core/views/master_view.py:218` | Builds CRUD viewsets with `metadata`/`filter_config`, advanced filters, atomic `perform_create/update/destroy` (`:148-216`, `ProtectedError` → 400 on delete). | BOE (`bill_of_entry/api/views.py:103`), other masters |
| `StandardPagination` | `apps/core/pagination.py:22` (settings default, `lmanagement/settings.py:284-285`) | 25/page, `page_size` max 200. **Duplicate class** at `master_view.py:36` (same values) used as `MasterViewSet.pagination_class` (`:98`). | all list endpoints |
| `generate_transfer_letter_generic` | `apps/core/utils/transfer_letter.py:356` | Transfer-letter generation for `instance_type` boe/allotment/trade. | BOE, allotment, trade |
| `api_error` | `apps/core/utils/exceptions.py:12` | Logs the exception, returns safe `{'error': message}`. | BOE `fetch-allotment-details` (`views.py:234`) and others |
| `CombinedFilterBackend` | `apps/core/filters.py:471` | django-filter + advanced filter backend. | BOE viewset |
| `BOEFilterSet` | `apps/core/filtersets.py:232` | BOE filter fields. | BOE viewset |
| `UploadRateThrottle` | `apps/core/throttling.py:155` | Upload rate limit. | `license/api/views/ledger_upload.py:35`. **Not** applied to BOE `parse-pdf`. |
| `annotate_and_exclude_hidden` / `genuinely_hidden_boe_ids` | `apps/bill_of_entry/models.py:57`, `:143` | Single definition of "hidden BOE" (OTH + HIDE log). | balance, ledger, BOE list |
| `hide_boe` / `restore_boe` / bulk | `apps/bill_of_entry/services/boe_service.py:487-667` | Hide/restore with `ReconciliationLog` + `_refresh_licenses`. | licence viewset actions |
| `LicenseBalanceCalculator` | `apps/license/services/balance_calculator.py:80` | The one balance engine. | licence, BOE refresh |
| `resolve_effective_cif_mode` / `effective_source_row_cif_available` | `apps/license/services/effective_cif_mode.py:18`, `:114` | Licence CIF mode and per-row available CIF. | serializers, ledger |
| `update_license_flags` | `apps/license/signals.py:280` | Recompute licence flags. | signals, services |
| `update_balance_values` | `apps/core/scripts/calculate_balance.py:165` | Per-item stored balance refresh. | `bill_of_entry/models.py` signals (`_update_balance_sync`) |
| `remaining_for_*` | `apps/reconciliation/services/allocation_service.py:68,97,147,173` | Remaining qty/CIF per trade line, BOE row (invoice/allotment side), allotment item. | reconciliation allocations |
| Allocation writes | `allocation_service.py:224-416` | **Backend write reference**: atomic + `select_for_update` + `ReconciliationLog`. | reconciliation API |
| `ReconciliationLog.ACTION_*` | `apps/reconciliation/models.py:106-119` | Audit vocabulary incl. `MERGE_BOE`, `HIDE_BOE`, `RESTORE_BOE`. | services, recon views |

## Frontend

| Module | Location | Notes |
|---|---|---|
| Workspace | `components/workspace/{ModuleWorkspace,DetailTabs,ModuleAccordion}.tsx` | See [generic-component-registry](generic-component-registry.md). |
| Shared UI | `components/shared/*` (barrel `index.ts`) | `FieldGrid` is **not** in the barrel; import `@/components/shared/FieldGrid`. |
| Confirm | `hooks/useConfirmDialog.tsx:112` `confirmDangerousAction` | Use this. `ConfirmProvider` (`components/shared/ConfirmDialog.tsx:91`) is **not mounted**, so `ActionMenu` `item.confirm` throws (`ActionMenu.tsx:45`). |
| Formatters | `pages/masters/masterDisplayFormatters` (`formatTruthyInr`, `formatTruthyIndianNumber`) | Reused by BOE `format.ts` (WS2). |
| Query keys | `lib/queryKeys.ts` `qk.*` | `qk.boes = resource("boes")` (`:31`); first detail consumer is WS3. |
| Display | `lib/display.ts` (`displayValue`, `OUTLINE_TOKENS`) | |
| Licence copy PDF | `utils/licenseCopyPdf.openLicenseCopyPdf` | Used by both DocumentsTabs. |
