# Release freeze — Auto Plan and source-row CIF

## Semantics

Only `individual_item_cif_override is True` selects an import row's persisted
source-row CIF ledger. `None`, `False`, and non-boolean truthy values retain
the legacy path. Source-row identity is the import-item primary key; HSN,
names, serial display values, and row position are never identity keys.

`POST /api/licenses/{id}/auto-plan/` accepts `{"force": true}`, executes the
canonical planner synchronously under its transaction/locking path, and returns
HTTP 200 only after commit. It does not enqueue a durable replan request; the
other replan entry points remain durable/async.

## Migration

`license.0050_licensedetails_individual_item_cif_override` adds the nullable
override. `makemigrations --check --dry-run`: no drift. Fresh isolated browser
database migration completed through 0050.

## Verification

- Combined remediation: 93 passed in 25.76s.
- Complete backend: 2,658 passed in 418.13s; exit 0;
  `/tmp/license_manager_backend_release_final_20260824.log`.
- Trade list: 15 queries before the final legacy-metadata boundary; 9 after,
  under the four-row budget (<=10) and nine-row budget (<=14).
- Frontend: 72 files / 469 tests passed; format, typecheck, zero-warning lint,
  and production build passed.
- Browser: mocked Playwright 15 passed / 5 opt-in skips; isolated seeded
  data-bearing harness 5 passed. Axe checks are included in the mock browser
  suites.
- `npm audit --omit=dev --audit-level=high`: 0 vulnerabilities.
- `git diff --check`: passed. Diff secret-pattern scan found no bearer token,
  private key, or credential addition.

## Evidence and limits

The full backend suite covers null/false parity, synchronous Auto Plan,
source-row identity, planning/accounting reconciliation, permissions and IDOR.
The browser seed covers real planning, PLAN/ACTUAL allotment, trade, BOE,
ledger, report, pivot and responsive routes against a fresh disposable DB.
No production system, credentials, or production data were used.
