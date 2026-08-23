# Large Module Decomposition Plan

Generated from the stateful audit database and existing graph memory. This plan
closes the broad `P4-LARGE-MODULES` queue item by replacing it with smaller,
coverage-gated tasks.

## Current Hotspots

| Area | File | LOC | Current Coverage | Risk |
|---|---:|---:|---|---|
| Backend Excel export | `backend/apps/license/services/exporters/license_balance_excel.py` | 2123 | API-level balance/export coverage only | High: workbook formatting and queryset behavior |
| Frontend form shell | `frontend/src/pages/masters/MasterForm.tsx` | 1975 | Create/edit smoke test and API-base helper tests | High: shared create/edit workflow |
| Frontend list shell | `frontend/src/pages/masters/MasterList.tsx` | 1823 | Smoke tests for key entities and generic master-card extraction | Medium: list rendering and actions |
| Frontend trade form | `frontend/src/pages/TradeForm.tsx` | 1662 | Create/edit smoke test and payload helper tests | High: purchase/sale branching |
| Frontend reports | `frontend/src/pages/reports/ItemPivotReport.tsx` | 1442 | No focused report page test | Medium: filter/export workflow |
| Frontend modal | `frontend/src/components/LicenseBalanceModal.tsx` | 1117 | Indirect through list/form only | Medium: modal-specific balance display |

## Regression Gates Before Refactor

- Add workbook-shape tests for `balance-excel` and `bulk-balance-excel` before
  extracting workbook sections from `license_balance_excel.py`.
- Add `MasterForm` smoke coverage for create/edit routes before moving form
  sections or submit orchestration.
- Keep existing `MasterList` smoke tests green before extracting more table
  variants.
- Add one `TradeForm` create/edit smoke test before splitting purchase/sale
  sections.
- Add one `ItemPivotReport` smoke test before moving filters/export controls.

## Decomposition Order

1. `license_balance_excel.py`: extract style constants and sheet section writers
   into private helpers in the same module first. Move to submodules only after
   workbook tests prove parity.
2. `MasterForm.tsx`: extract pure API path/default-value helpers before UI
   components. Avoid moving submit side effects until smoke tests cover create
   and edit.
3. `MasterList.tsx`: continue table/action extraction by entity, one entity per
   change, guarded by existing smoke tests.
4. `TradeForm.tsx`: extract validation and payload builders into pure helpers,
   then split purchase/sale sections.
5. Report pages: extract filter state and export URL builders into tested pure
   helpers before moving render components.

## Follow-up Work Queue

| ID | Priority | Scope | Verification |
|---|---:|---|---|
| `P4A-BALANCE-EXCEL-GOLDEN` | 4 | DONE: workbook-shape regression tests added for license balance Excel exports. | `.venv/bin/python -m pytest backend/tests/test_api_license.py -q` -> 11 passed. |
| `P4B-MASTERFORM-SMOKE` | 4 | DONE: added `MasterForm` create/edit smoke coverage. | `npm test -- --run src/pages/masters/MasterForm.smoke.test.tsx` -> 2 passed. |
| `P4C-MASTERLIST-DECOMPOSE` | 4 | DONE: extracted generic master-card rendering from `MasterList`. | `npm test -- --run src/pages/masters/MasterList.smoke.test.tsx` -> 5 passed; frontend typecheck passed. |
| `P4D-MASTERFORM-API-HELPER` | 4 | DONE: extracted MasterForm API-base resolver into a pure helper. | `npm test -- --run src/pages/masters/masterFormHelpers.test.ts src/pages/masters/MasterForm.smoke.test.tsx` -> 10 passed. |
| `P4E-TRADEFORM-SMOKE` | 4 | DONE: added `TradeForm` create/edit smoke coverage before splitting purchase/sale sections. | `npm test -- --run src/pages/TradeForm.smoke.test.tsx` -> 2 passed; frontend typecheck passed. |
| `P4F-TRADEFORM-PAYLOAD-HELPER` | 4 | DONE: extracted TradeForm payload cleanup into pure helpers. | `npm test -- --run src/pages/tradeFormHelpers.test.ts src/pages/TradeForm.smoke.test.tsx` -> 7 passed; frontend typecheck passed. |
| `P4G-TRADEFORM-VALIDATION-HELPER` | 4 | Extract TradeForm validation schema helpers before section splitting. | Focused helper tests, TradeForm smoke tests, and frontend typecheck. |
