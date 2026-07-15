# Business Rule Traceability Matrix

> **Trace any rule from UI to database and back.**  
> Format: Rule → Model → Service → API → Frontend → Test

---

## Balance Calculation

| Layer | Artifact | Details |
|---|---|---|
| **Business Rule** | `balance_cif = max(0, credit − debit − allotment − trade)` | BD-001, BD-004 |
| **Database Model** | `LicenseBalance.balance_cif` | Table: `license_licensebalance` |
| **Computation** | `balance_service.recompute_license_balance(license_id)` | `backend/apps/license/services/balance_service.py` |
| **Trigger service** | `allotment_service._dispatch()` | After allotment CRUD |
| **Trigger signal** | `boe/models.update_stock()` | After RowDetails save/delete |
| **Task** | `recompute_license_balance_task` | `backend/apps/license/tasks.py` |
| **API** | `GET /api/v1/licenses/{id}/balance/` | Returns snapshot |
| **API recompute** | `POST /api/v1/licenses/{id}/recompute_balance/` | Dispatches task |
| **Serializer** | `LicenseBalanceSerializer` | Exposes `balance_cif`, `total_authorised`, `total_debited`, `total_allotted` |
| **Frontend component** | `LicenseBalancePanel.tsx` | Shows Balance CIF, Total Authorised, Debited, Allotted cards |
| **Frontend hook** | `useLicenseBalance` in `licenses/queries.ts` | Fetches from `/balance/` endpoint |
| **Test** | `test_balance_system.py::test_balance_formula_all_components` | Unit test |
| **Test** | `test_license_workflows.py::test_license_balance_after_boe_row_creation` | Integration test |

---

## Over-Allotment Prevention

| Layer | Artifact | Details |
|---|---|---|
| **Business Rule** | Cannot allot more than planned_quantity | PLAN-004 |
| **Database Model** | `LicenseItemPlan.planned_quantity` | Table: `license_licenseitemplan` |
| **Validation** | `allotment_service._validate_plan_availability()` | Raises `ValidationError` |
| **Concurrency guard** | `select_for_update()` on `LicenseItemPlan` | Prevents concurrent over-allotment |
| **API** | `POST /api/v1/allotments/` | Creates allotment |
| **API response** | 400 ValidationError | "Requested quantity X exceeds available plan Y" |
| **Frontend display** | `LicenseImportItems.tsx` planned column | Shows remaining planned_quantity |
| **Frontend** | Validation error shown in `AllotmentForm.tsx` | Toast + form error |
| **Test** | `test_balance_system.py::test_create_allotment_rejects_over_plan` | ✅ |
| **Test** | `test_balance_system.py::test_validate_plan_uses_select_for_update` | ✅ |

---

## Plan Decrement on Allotment

| Layer | Artifact | Details |
|---|---|---|
| **Business Rule** | Create allotment decrements LicenseItemPlan | PLAN-002 |
| **Database Model** | `LicenseItemPlan.planned_quantity` | Updated via F() expression |
| **Service** | `allotment_service._adjust_plan(import_item_id, qty_delta, ...)` | `qty_delta = -allot_qty` |
| **Called from** | `allotment_service.create_allotment()` | After AllotmentItems.save() |
| **Reverse** | `allotment_service.delete_allotment()` | `qty_delta = +allot_qty` |
| **API** | `POST /api/v1/allotments/` | Create |
| **API** | `DELETE /api/v1/allotments/{id}/` | Delete + restore |
| **Frontend** | `LicenseImportItems.tsx` planned column updates | After mutation invalidates queries |
| **Test** | `test_balance_system.py::test_create_allotment_decrements_plan` | ✅ |
| **Test** | `test_balance_system.py::test_delete_allotment_restores_plan` | ✅ |
| **Test** | `test_balance_system.py::test_delete_allotment_plan_restore_is_exact` | ✅ |

---

## 3dp Trade Billing Precision

| Layer | Artifact | Details |
|---|---|---|
| **Business Rule** | pct/rate_pct must use 3dp, Decimal(str()) not q2() | TRADE-001, BD-005 |
| **Database Model** | `LicenseTradeLine.pct DecimalField(9,3)` | Table: `trade_licensetradelline` |
| **Calculation** | `LicenseTradeLine.compute_amount()` | `Decimal(str(self.pct)) / 100` |
| **Called from** | `LicenseTradeLine.save()` | Unconditionally on every save |
| **API** | `POST /api/v1/trades/` | Creates trade with lines |
| **Frontend** | `TradeLineTable.tsx` pct input | `step="0.001"` for 3dp input |
| **Frontend** | `TradeForm.tsx` | Sends pct as string with 3dp |
| **Test** | `test_trade.py::test_pct_3dp_precision_cif` | Pins: 7.925 × 100,000 = 7925.00 ✅ |
| **Test** | `test_trade.py::test_rate_pct_3dp_precision` | Pins: 2.125 × 500,000 = 10625.00 ✅ |

---

## Frozen BOE Rows Cannot Be Edited

| Layer | Artifact | Details |
|---|---|---|
| **Business Rule** | Frozen rows cannot be edited from frontend | BOE-002 |
| **Database Model** | `RowDetails.is_frozen BooleanField` | Table: `bill_of_entry_rowdetails` |
| **Enforcement** | `RowDetails.save()` returns early if `is_frozen=True` | Silently blocked |
| **Service** | `boe_service.update_row_detail()` reads `is_frozen` then raises ValueError | Returns 403 |
| **API** | `PATCH /api/v1/bill-of-entries/{boe_id}/rows/{row_id}/` | Returns 403 if frozen |
| **Frontend** | `BOERowsTable.tsx` disables edit/delete for frozen rows | Visual indicator |
| **Test** | `test_boe.py::TestFrozenRowUpdateRejected` | ✅ |
| **Test** | `test_boe.py::TestFrozenRowDeleteRejected` | ✅ |
| **Test** | `test_license_workflows.py::test_frozen_boe_row_update_rejected` | ✅ |

---

## RBAC: Superuser Bypasses All Roles

| Layer | Artifact | Details |
|---|---|---|
| **Business Rule** | Superusers have full access | AUTH-001 |
| **Backend model** | `User.is_superuser` | Table: `accounts_user` |
| **Backend check** | `BaseRolePermission.has_permission()` | `if is_superuser: return True` |
| **API serializer** | `UserSerializer.is_superuser` field | Must be in response |
| **Frontend auth** | `AuthContext.hasAnyRole()` | `if user?.is_superuser: return true` |
| **Frontend nav** | `Sidebar.tsx` SidebarLink component | Items shown when `hasAnyRole` returns true |
| **Test** | `test_permissions.py::test_superuser_bypasses_all_role_checks` | ✅ |
| **Test (missing)** | is_superuser in UserSerializer response | ❌ No regression test |

---

## Living Documentation Guidance

When any of these rules changes, update ALL rows in the relevant section:

1. The business rule description (in `docs/business-rules/business-rule-index.md`)
2. The model field (if changed)
3. The service function (if logic changes)
4. The API behavior (if response changes)
5. The frontend component (if display changes)
6. The test (must verify the new behavior)
7. This traceability document
