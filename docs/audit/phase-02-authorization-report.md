# Phase 2 Authorization Audit Report

Status: `COMPLETED`

Authentication was completed before this phase started. This report records the complete line-by-line Authorization pass across backend permission classes, endpoint gates, frontend route guards, navigation visibility, command visibility, role helper types, and authorization regression tests.

## Files Audited

| Module | File | Status | Lines | Lines Reviewed | Functions Reviewed | Classes Reviewed | Imports Reviewed | Issues Found | Issues Fixed | Verification | Risk |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| Backend Authorization | `backend/apps/accounts/permissions.py` | COMPLETED | 150 | 150 | 8 | 10 | 1 | No behavior bug found in the permission classes during this pass. Duplication remains across role checks and is queued for a later safe consolidation pass. | Verified superuser bypass, authenticated-user checks, read/write role splits, ledger roles, account-access roles, and transfer-letter roles. | Focused authorization tests, targeted Ruff | Low |
| Backend Authorization | `backend/apps/license/views_actions.py` | COMPLETED | 528 | 528 | 10 | 1 | 12 | License ownership/transfer actions used `IsAuthenticated`, allowing any logged-in user to reach write paths. | Replaced action-level `IsAuthenticated` overrides with `LicensePermission`; removed an unused import. | Focused authorization tests, targeted Ruff | Medium |
| Backend Authorization Tests | `backend/tests/test_authorization_permissions.py` | COMPLETED | 26 | 26 | 1 | 1 | 5 | Missing regression for license action role enforcement. | Added no-role authenticated-user regression expecting 403 on license transfer update. | Focused authorization tests | Low |
| Frontend Authorization | `frontend/src/routes/ProtectedRoute.tsx` | COMPLETED | 45 | 45 | 1 | 1 | 3 | No behavior bug found in this pass. | Verified unauthenticated redirect, superuser requirement, single-role and any-role checks, and 403 redirects. | Frontend typecheck, lint | Low |
| Frontend Authorization | `frontend/src/pages/Forbidden.tsx` | COMPLETED | 15 | 15 | 1 | 0 | 2 | No behavior bug found in this pass. | Verified 403 screen action and copy. | Frontend typecheck, lint | Low |

## Improvements

- Security fix: license ownership/transfer mutation endpoints now require `LICENSE_MANAGER` through `LicensePermission` instead of accepting any authenticated user.
- Regression coverage: added a focused authorization test that fails if unauthorised authenticated users reach the license transfer update view.
- Readability cleanup: removed unused `parse_datetime` import in `backend/apps/license/views_actions.py`.

## Verification

- `.venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_authentication_query_param.py backend/tests/test_api_license.py -q` -> 15 passed.
- `.venv/bin/ruff check backend/apps/accounts/permissions.py backend/apps/license/views_actions.py backend/tests/test_authorization_permissions.py --select F821,F811,E741,F841,F401` -> clean.
- `npm run typecheck` -> passed.
- `npm run lint` -> passed.

## Remaining Authorization Work

- Continue backend viewset/action permission audit outside license actions.
- Audit frontend `PermissionGate`, navigation visibility, dashboard role checks, and settings/admin gates.
- Add frontend route-gate regression tests where safe.
- Consolidate repeated backend role-check boilerplate only after all authorization call sites are mapped.

## Continuation Pass: Master Data Backend Gates and Frontend Navigation Guards

| Module | File | Status | Lines | Lines Reviewed | Functions Reviewed | Classes Reviewed | Permission Checks Reviewed | Issues Found | Issues Fixed | Verification | Risk |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| Backend Authorization | `backend/apps/core/views/master_view.py` | COMPLETED | 838 | 838 | 14 | 4 | 1 | Generic master-data write APIs trusted frontend superuser guards and allowed any authenticated user to create/update/delete by direct API call. | Added `MasterDataPermission`: authenticated users may read; only superusers may write. Removed stale imports in the touched file. | Master-data authorization regressions, MDS cutover regressions, core API tests, targeted Ruff | Medium |
| Backend Authorization URLs | `backend/lmanagement/urls.py` | COMPLETED | 78 | 78 | 1 | 0 | 4 | None requiring code change. | Verified production schema/docs gating, protected media route, API includes, and JSON API fallback ordering. | URL review; related backend authorization tests | Low |
| Backend Authorization Tests | `backend/tests/test_authorization_permissions.py` | COMPLETED | 80 | 80 | 3 | 2 | 3 | Missing regression for direct master-data write authorization. | Added non-superuser master-data write denial and superuser create allowance tests. | Master-data authorization regressions | Low |
| Backend MDS Write Tests | `backend/apps/core/tests/test_mds_write_cutover.py` | COMPLETED | 294 | 294 | 13 | 5 | 11 | New master-data write gate would otherwise block tests intended to exercise MDS write plumbing. | Authenticated the MDS write-cutover fixture as superuser so tests keep validating MDS behavior. | MDS cutover regressions | Low |
| Backend Core API Tests | `backend/tests/test_api_core.py` | COMPLETED | 119 | 119 | 9 | 3 | 9 | None requiring code change. | Verified existing core master CRUD tests still pass under superuser fixture. | Core API tests | Low |
| Frontend Authorization | `frontend/src/components/PermissionGate.tsx` | COMPLETED | 29 | 29 | 1 | 0 | 2 | None requiring code change. | Verified role and any-role fallback behavior delegates to AuthContext helpers. | Frontend typecheck, lint | Low |
| Frontend Authorization Navigation | `frontend/src/components/TopNav.tsx` | COMPLETED | 287 | 287 | 3 | 2 | 5 | Reports menu duplicated route role logic and hid reports for roles that routes already allow, such as `LICENSE_VIEWER`. | Reused shared `REPORT_ROLES` constant for nav visibility. | TopNav regression, typecheck, lint | Low |
| Frontend Authorization Tests | `frontend/src/components/TopNav.test.tsx` | COMPLETED | 47 | 47 | 0 | 0 | 1 | Missing regression for report menu visibility parity. | Added `LICENSE_VIEWER` Reports navigation visibility regression. | TopNav regression | Low |
| Frontend Authorization Navigation | `frontend/src/layout/Sidebar.tsx` | COMPLETED | 155 | 155 | 5 | 0 | 1 | None requiring code change in this pass; sidebar is secondary/legacy navigation and user-management visibility already uses `canManageUsers`. | Verified user-management visibility and unrestricted master/report menu behavior against backend read/write gates. | Frontend typecheck, lint | Low |
| Frontend Authorization Routes | `frontend/src/routes/AppRoutes.tsx` | COMPLETED | 272 | 272 | 1 | 0 | 32 | Report route role list was duplicated with TopNav. | Moved report roles into shared `authorizationRoles.ts`. | TopNav regression, typecheck, lint | Low |
| Frontend Authorization Constants | `frontend/src/routes/authorizationRoles.ts` | COMPLETED | 10 | 10 | 0 | 0 | 1 | Shared constant did not exist. | Created `REPORT_ROLES` as the route/nav source of truth. | TopNav regression, typecheck, lint | Low |
| Frontend Role Display Constants | `frontend/src/utils/roleConstants.js` | COMPLETED | 62 | 62 | 2 | 0 | 0 | None requiring code change. | Verified role labels and badge helpers are display-only, not access-control decisions. | Frontend typecheck, lint | Low |

## Continuation Improvements

- Security fix: direct API writes to generic master-data endpoints now require a superuser, matching the existing frontend create/edit route gates.
- Authorization consistency: report route roles and report navigation visibility now share one constant, preventing route/nav drift.
- Regression coverage: added backend master-data write-denial/allowance tests and frontend report-menu visibility coverage.
- Dead code removed: unused imports in `backend/apps/core/views/master_view.py`.

## Continuation Verification

- `.venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/apps/core/tests/test_mds_write_cutover.py backend/tests/test_api_core.py -q` -> 23 passed.
- `.venv/bin/ruff check backend/apps/core/views/master_view.py backend/tests/test_authorization_permissions.py backend/apps/core/tests/test_mds_write_cutover.py --select F821,F811,E741,F841,F401` -> clean.
- `npm test -- --run src/components/TopNav.test.tsx` -> 1 passed.
- `npm run typecheck` -> passed.
- `npm run lint` -> passed.
- `npm audit --audit-level=high` -> 0 vulnerabilities.
- Python dependency audit: `pip-audit` is not installed in the local environment.

## Phase 2 Status After This Pass

Phase 2 remains `IN_PROGRESS`. Remaining work includes broader backend domain ViewSet action gates, report/dashboard authorization checks, MDS scoped permission documentation in the Authorization report without modifying frozen Phase 1 files, and any additional frontend hidden-control gates discovered by the next Authorization query.

## Continuation Pass: Domain ViewSets, Operational Views, and RBAC Documentation

| Module | File | Status | Lines | Lines Reviewed | Functions Reviewed | Classes Reviewed | Permission Checks Reviewed | Issues Found | Issues Fixed | Verification | Risk |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| Allotment Authorization | `backend/apps/allotment/views.py` | COMPLETED | 330 | 330 | 5 | 0 | 1 | None requiring code change. | Verified `AllotmentPermission` on generated ViewSet, copy/delete mutation paths, grouped export permission preservation, and default queryset behavior. | Allotment API tests, targeted Ruff | Low |
| BOE Authorization | `backend/apps/bill_of_entry/views/boe.py` | COMPLETED | 448 | 448 | 9 | 1 | 3 | None requiring code change. | Verified `BillOfEntryPermission`, `TransferLetterPermission`, `AccountAccessPermission`, and all attached action fallbacks. | BOE API tests, targeted Ruff | Low |
| Master Authorization URLs | `backend/apps/core/urls.py` | COMPLETED | 46 | 46 | 0 | 0 | 6 | None requiring code change. | Verified master routers, activity-log router, and throttle-monitoring route registration. | Core API tests, targeted Ruff | Low |
| MDS Status Authorization | `backend/apps/core/views/mds_status.py` | COMPLETED | 114 | 114 | 2 | 1 | 1 | None requiring code change. | Verified read-only MDS status stays behind `UserManagementPermission` because it exposes operational config/sync details. | Targeted Ruff | Low |
| Protected Media Authorization | `backend/apps/core/views/media.py` | COMPLETED | 59 | 59 | 1 | 1 | 1 | None requiring code change. | Verified authenticated-only media access and path confinement. | Targeted Ruff | Low |
| Dashboard Authorization | `backend/apps/license/views/dashboard.py` | COMPLETED | 257 | 257 | 6 | 1 | 4 | Stale unused `ReportPermission` import. | Removed unused import; verified dashboard remains authenticated and role-filters response sections internally. | Targeted Ruff | Low |
| Task Authorization | `backend/apps/tasks/views.py` | COMPLETED | 133 | 133 | 10 | 1 | 8 | None requiring code change. | Verified object-level task visibility, creator/assignee update rules, creator-only delete, and action-level modify checks. | Targeted Ruff | Low |
| Authorization Documentation | `docs/architecture/NAVBAR_ROLE_MAPPING.md` | COMPLETED | 185 | 185 | 0 | 0 | 15 | Documented stale Sidebar/AuthContext API names, old report-role list, old master visibility, and old redirect semantics. | Updated documentation to match `TopNav`, `ProtectedRoute`, `REPORT_ROLES`, backend `MasterDataPermission`, `/api/auth/me`, and `/403`. | Documentation review | Low |

## Domain ViewSet Improvements

- Documentation consistency: navigation role mapping now reflects the actual primary navigation, route guards, and backend permission boundary.
- Dead code removed: stale dashboard authorization import removed.
- Authorization verification: task object-level authorization and protected media access were reviewed without behavior changes.

## Domain ViewSet Verification

- `.venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_allotment.py backend/tests/test_api_boe.py backend/tests/test_api_core.py -q` -> 26 passed.
- `.venv/bin/ruff check backend/apps/allotment/views.py backend/apps/bill_of_entry/views/boe.py backend/apps/core/urls.py backend/apps/tasks/views.py backend/apps/core/views/mds_status.py backend/apps/core/views/media.py backend/apps/license/views/dashboard.py --select F821,F811,E741,F841,F401` -> clean.
- Coverage artifacts generated by pytest were removed after verification.

## Phase 2 Status After Domain Pass

Phase 2 remains `IN_PROGRESS`. Remaining real Authorization work is concentrated in report/export endpoints and any route/report documentation still marked `REQUIRES_RECHECK`; false positives with “group” in data-processing names are documented and will be left for their later functional phases unless they become authorization-impacting.

## Continuation Pass: BOE Parser and License Report Authorization Surfaces

| Module | File | Status | Lines | Lines Reviewed | Functions Reviewed | Classes Reviewed | Permission Checks Reviewed | Issues Found | Issues Fixed | Verification | Risk |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| BOE Authorization | `backend/apps/bill_of_entry/views/parse_pdf.py` | COMPLETED | 272 | 272 | 8 | 1 | 1 | BOE PDF parser used `AllotmentPermission`, allowing allotment roles into a BOE-specific parser and blocking the intended BOE role boundary. | Replaced parser permission with `BillOfEntryPermission`; added BOE-manager allow and allotment-manager deny regressions. | BOE parser authorization tests, BOE API tests, targeted Ruff | Medium |
| License Authorization | `backend/apps/license/views/parse_pdf.py` | COMPLETED | 207 | 207 | 8 | 1 | 1 | None requiring code change. | Verified license PDF parser remains authenticated and `LicensePermission` protected. | License focused tests, targeted Ruff | Low |
| License Authorization | `backend/apps/license/views/item_plan.py` | COMPLETED | 178 | 178 | 2 | 1 | 1 | None requiring code change. | Verified item-plan read/write actions remain behind `LicensePermission`. | License focused tests, targeted Ruff | Low |
| Incentive License Authorization | `backend/apps/license/views_incentive.py` | COMPLETED | 170 | 170 | 1 | 2 | 1 | Unused import found in the touched authorization surface. | Removed unused import while preserving `IncentiveLicensePermission`. | License focused tests, targeted Ruff | Low |
| Report Authorization | `backend/apps/license/views/inventory_balance_viewset.py` | COMPLETED | 184 | 184 | 4 | 1 | 1 | Unused imports found in the touched authorization surface. | Removed unused imports while preserving `ReportPermission`. | License focused tests, targeted Ruff | Low |
| Operational Health | `backend/apps/core/views/health.py` | COMPLETED | 43 | 43 | 3 | 1 | 1 | None requiring code change. | Verified health endpoint intentionally remains `AllowAny` and does not expose sensitive details beyond dependency status. | Targeted Ruff | Low |
| Report Authorization URLs | `backend/apps/license/urls.py` | COMPLETED | 53 | 53 | 0 | 0 | 5 | Direct `/api/reports/*` class-based report routes bypassed the protected ViewSet `ReportPermission` gates. | Kept route shape unchanged and moved direct report views onto DRF `APIView` permission handling. | Direct report authorization regression, license focused tests, targeted Ruff | Medium |
| Report Authorization | `backend/apps/license/views/active_licenses_report.py` | COMPLETED | 635 | 635 | 8 | 2 | 2 | Direct report view lacked backend permission enforcement; stale docstring said `AllowAny`; unused imports were present. | Added `ReportPermission` to the direct `APIView`, corrected permission docstring, removed unused imports. | Direct report authorization regression, license focused tests, targeted Ruff | Medium |
| Report Authorization | `backend/apps/license/views/expiring_licenses_report.py` | COMPLETED | 671 | 671 | 9 | 2 | 2 | Direct report view lacked backend permission enforcement; stale docstring said `AllowAny`; unused imports were present. | Added `ReportPermission` to the direct `APIView`, corrected permission docstring, removed unused imports. | Direct report authorization regression, license focused tests, targeted Ruff | Medium |
| Report Authorization | `backend/apps/license/views/inventory_balance_report.py` | COMPLETED | 327 | 327 | 5 | 1 | 1 | Direct report view was `csrf_exempt` and had no backend report permission enforcement. | Converted to DRF `APIView`, removed CSRF exemption, added `ReportPermission`, and removed unused imports. | Direct report authorization regression, license focused tests, targeted Ruff | Medium |
| Report Authorization | `backend/apps/license/views/item_pivot_report.py` | COMPLETED | 1567 | 1567 | 12 | 2 | 2 | Direct report view lacked backend permission enforcement; report status filtering used `timedelta` without importing it. | Added `ReportPermission` to the direct `APIView`, corrected permission docstring, fixed `timedelta` import path, and removed unused imports/locals in the touched surface. | Direct report authorization regression, license focused tests, targeted Ruff | Medium |
| Report Authorization | `backend/apps/license/views/item_report.py` | COMPLETED | 480 | 480 | 5 | 2 | 2 | Direct report view lacked backend permission enforcement; unused imports were present. | Added `ReportPermission` to the direct `APIView` and removed unused imports/locals. | Direct report authorization regression, license focused tests, targeted Ruff | Medium |
| Backend Authorization Tests | `backend/tests/test_authorization_permissions.py` | COMPLETED | 168 | 168 | 8 | 4 | 10 | Missing regression coverage for BOE parser role mismatch and direct report route permission bypass. | Added BOE parser allow/deny coverage and direct report unauthenticated/no-role/REPORT_VIEWER boundary tests. | Direct report authorization regression, BOE parser authorization tests | Low |

## Report Authorization Improvements

- Security fix: direct `/api/reports/inventory-balance/`, `/api/reports/expiring-licenses/`, `/api/reports/active-licenses/`, `/api/reports/item-pivot/`, and `/api/reports/item-report/` now enforce `ReportPermission`, matching the router-backed report endpoints.
- Security fix: BOE PDF parser now uses `BillOfEntryPermission` instead of `AllotmentPermission`.
- Runtime fix: item-pivot report status filters now import `timedelta` before using it.
- Dead code removed: unused imports and stale permission docstrings were cleaned in the audited report files.

## Report Authorization Verification

- `.venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_boe.py -q` -> 12 passed.
- `.venv/bin/ruff check backend/apps/bill_of_entry/views/parse_pdf.py backend/tests/test_authorization_permissions.py --select F821,F811,E741,F841,F401` -> clean.
- `.venv/bin/python -m pytest backend/tests/test_api_license.py backend/apps/license/tests/test_license_group_data.py -q` -> 12 passed.
- `.venv/bin/ruff check backend/apps/license/views/parse_pdf.py backend/apps/license/views/item_plan.py backend/apps/license/views_incentive.py backend/apps/license/views/inventory_balance_viewset.py backend/apps/core/views/health.py --select F821,F811,E741,F841,F401` -> clean.
- `.venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_license.py backend/apps/license/tests/test_license_group_data.py -q` -> 20 passed.
- `.venv/bin/ruff check backend/apps/license/views/active_licenses_report.py backend/apps/license/views/expiring_licenses_report.py backend/apps/license/views/inventory_balance_report.py backend/apps/license/views/item_pivot_report.py backend/apps/license/views/item_report.py backend/tests/test_authorization_permissions.py --select F401,F821,F811,E741,F841` -> clean.

## Phase 2 Status After Report Pass

Phase 2 remains `IN_PROGRESS`. Remaining work is the final constrained permission scan, including Trade authorization-gate review only where required by Phase 2, without broad Trade refactoring before the global Trade phase.

## Continuation Pass: Constrained Trade Authorization Gate Review

| Module | File | Status | Lines | Lines Reviewed | Functions Reviewed | Classes Reviewed | Permission Checks Reviewed | Issues Found | Issues Fixed | Verification | Risk |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| Trade Authorization | `backend/apps/trade/views.py` | COMPLETED | 560 | 560 | 9 | 1 | 4 | Direct nested `lines` and `payments` routers inherited generic `MasterDataPermission`, allowing any authenticated user to read trade line/payment data and blocking normal trade managers from write paths. | Assigned `TradePermission` to `TradeLineViewSet` and `TradePaymentViewSet`, matching the parent `trades` endpoint. Broader Trade business logic remains deferred to Phase 20. | Trade authorization regressions, Trade API tests, targeted Ruff | Medium |
| Backend Authorization Tests | `backend/tests/test_authorization_permissions.py` | COMPLETED | 212 | 212 | 10 | 5 | 13 | Missing regression coverage for direct nested Trade endpoints. | Added no-role denial and `TRADE_VIEWER` read allowance tests for `/api/trades/`, `/api/lines/`, and `/api/payments/`. | Trade authorization regressions | Low |

## Constrained Trade Authorization Improvements

- Security fix: nested Trade line and payment endpoints now use `TradePermission`, avoiding leakage of trade sub-records through generic master-data read permissions.
- Regression coverage: no-role users are denied across parent and nested Trade endpoints; `TRADE_VIEWER` can read each endpoint.
- Scope note: this was an authorization-only review required by Phase 2. Full Trade module design, model, serializer, PDF, and workflow audit remains reserved for Phase 20.

## Constrained Trade Authorization Verification

- `.venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_trade.py -q` -> 19 passed.
- `.venv/bin/ruff check backend/apps/trade/views.py backend/tests/test_authorization_permissions.py --select F401,F821,F811,E741,F841` -> clean.

## Phase 2 Status After Constrained Trade Pass

Phase 2 remains `IN_PROGRESS` until the final frontend/backend role-string scan and generated audit artifacts confirm no Authorization files remain `CHANGED` or `REQUIRES_RECHECK`.

## Continuation Pass: Frontend Command and Dashboard Role Visibility

| Module | File | Status | Lines | Lines Reviewed | Functions Reviewed | Classes Reviewed | Permission Checks Reviewed | Issues Found | Issues Fixed | Verification | Risk |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| Frontend Authorization | `frontend/src/components/CommandPalette.tsx` | COMPLETED | 175 | 175 | 2 | 0 | 13 | Command palette exposed role-protected navigation and quick-create destinations to users without matching roles. | Added role metadata to command entries, reused `REPORT_ROLES`, and filtered commands with `hasAnyRole`/superuser checks before display. | CommandPalette regression tests, typecheck, lint, npm audit | Medium |
| Frontend Authorization Tests | `frontend/src/components/CommandPalette.test.tsx` | COMPLETED | 72 | 72 | 2 | 0 | 3 | Missing regression coverage for command palette authorization visibility. | Added no-role, license-viewer, and superuser command visibility tests. | CommandPalette regression tests | Low |
| Frontend Authorization | `frontend/src/pages/Dashboard.tsx` | COMPLETED | 322 | 322 | 5 | 0 | 5 | Dashboard header displayed create actions to users who could read/report but could not create allotments or BOEs. | Added manager/superuser-only checks for `New Allotment` and `New BOE` actions while preserving dashboard read visibility. | Typecheck, lint | Medium |
| Frontend Authorization Types | `frontend/src/types/index.ts` | COMPLETED | 119 | 119 | 0 | 16 | 4 | None requiring code change. | Verified AuthContext role helper types match the authorization checks used by command palette, dashboard, route guards, and navigation. | Typecheck | Low |

## Frontend Role Visibility Improvements

- Authorization consistency: command palette navigation now mirrors protected route role requirements instead of showing destinations that immediately route to 403.
- Authorization consistency: report commands reuse the shared `REPORT_ROLES` constant already used by `TopNav` and `AppRoutes`.
- Hidden-control hardening: dashboard create buttons are shown only to users with the matching manager role or superuser access.

## Frontend Role Visibility Verification

- `npm test -- --run src/components/CommandPalette.test.tsx src/components/TopNav.test.tsx` -> 4 passed.
- `npm run typecheck` -> passed.
- `npm run lint` -> passed.
- `npm audit --audit-level=high` -> 0 vulnerabilities.

## Phase 2 Status After Frontend Visibility Pass

Phase 2 is `COMPLETED`. Final authorization scan covered 46 backend/frontend authorization surfaces and all are marked `COMPLETED` in the audit database.

## Phase 2 Completion Freeze

- Final authorization surface scan: 46 files matched backend permission markers or frontend role-guard markers.
- Non-completed authorization files after final scan: 0.
- Audit artifacts regenerated after completion: `audit-database.json`, `repository-knowledge-graph.json`, `dashboard.md`, and `work-queue.md`.
- Phase 2 is frozen. Authorization files should not be modified again unless a later phase changes a dependency and the Repository Knowledge Graph marks them `REQUIRES_RECHECK`.
- Next queued module: Phase 3 Users.
