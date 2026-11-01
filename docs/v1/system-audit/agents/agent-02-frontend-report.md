# Agent 2 report — frontend route and API inventory

Agent: Explore, read-only, 2026-11-01 (task a97e610334b1d57fa, 63 tool uses). Inventory: `inventories/frontend-route-inventory.md`. Status: **agent output, partly verified by the lead**.

## Lead verification

| Finding | Check | Result |
|---|---|---|
| Key finding 1: expiring and active report exports call `license/reports/...`, which no route matches | grep of `frontend/src` (4 page or test files); `backend/lmanagement/urls.py:45` mounts license under `api/`; `backend/apps/license/urls.py:56-57` registers `reports/...` | VERIFIED (static). Runtime 404 not run. Recorded as ISS-017. |
| Key finding 2: readiness link uses `request_key`, lookup uses `job.key` | `LicenseDownloadRequestDetail.tsx:7`; `ledger.py:181` (request_key = first UUID segment); `ledger.py:61,225` (job.key = timestamp plus 8 hex); `ledger.py:367` (lookup by key) | VERIFIED (static). Link expected to 404. Runtime not run. Recorded as ISS-018. |
| Key finding 3: `/reconciliation-issues` unlinked | agent grep of nav registries and `navigate`/`Link` | Agent-verified; not re-checked by lead. |
| Key finding 4: dead modules (`Sidebar.tsx`, `GlobalErrorBoundary.tsx`, `ServerError.tsx`) | agent grep for importers | Agent-verified; not re-checked by lead. |
| Route count (57 entries, 49 under AdminLayout, guard breakdown) | agent read of `AppRoutes.tsx` | Not re-counted by lead. |

## Impact on the register

- A-04 (frontend audit): inventory complete. Still needs state, API-client and UI behaviour review, and a runtime check of the two defects.
- A-01 (product inventory): frontend inventory now saved. The report file `02-project-and-module-inventory.md` is not yet written.
- A-05 (API audit): the frontend-to-backend mismatch list here is a starting point for request-level verification.

## Not verified

- Dead-code claims beyond the lead's spot-checks.
- Duplicate-page labels D3, D4, D7, D9 (SUSPECTED).
- Whether the `/licenses/:id/balance` redirect target exists at runtime.
