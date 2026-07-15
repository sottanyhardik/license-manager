# File Ownership Map

> **For every critical file: purpose, dependencies, safe/unsafe modifications.**  
> Use before making any change to understand impact.

---

## Backend — Services (Highest Risk)

### `backend/apps/license/services/balance_service.py`

| Property | Value |
|---|---|
| **Purpose** | Single authoritative source for license balance calculation |
| **Business rules** | LIC-002 through LIC-015 |
| **Depends on** | LicenseExportItemModel, RowDetails, AllotmentItems, LicenseTradeLine, LicenseBalance, LicenseFlags, LicenseImportItemsModel |
| **Depended on by** | `license/tasks.py` (calls recompute_license_balance), `boe/models.py` (via task dispatch), `allotment_service.py` (via task dispatch), `reports/services/balance_report.py` (re-implements, divergence risk) |
| **Safe to modify** | `_NULL_THRESHOLD` value, logging detail, `_update_item_level_balances` optimization |
| **Unsafe to modify** | The formula itself (credit-debit-allotment-trade), `select_for_update()` removal, `max(_DEC_0, raw)` floor removal, calling `_update_item_level_balances()` outside `transaction.atomic()` |
| **Tests required** | `tests/balance/test_balance_system.py` (all 21 tests), `tests/integration/test_license_workflows.py` |
| **Playbook** | `docs/playbooks/balance-module-playbook.md` |

---

### `backend/apps/allotment/services/allotment_service.py`

| Property | Value |
|---|---|
| **Purpose** | Allotment CRUD with planning validation and balance dispatch |
| **Business rules** | ALLOT-001 through ALLOT-007, PLAN-001 through PLAN-008 |
| **Depends on** | AllotmentModel, AllotmentItems, LicenseItemPlan, LicenseImportItemsModel (for license_id resolution), `recompute_license_balance_task` |
| **Depended on by** | `allotment/views.py` (only consumer) |
| **Safe to modify** | Logging detail, error message text |
| **Unsafe to modify** | `_dispatch` ID resolution logic (must use license_id not item_id), `select_for_update()` in `_validate_plan_availability`, `on_commit` dispatch (never inline), `_adjust_plan` F() expression removal |
| **Tests required** | `tests/allotment/test_allotment.py`, `tests/balance/test_balance_system.py` (tests 6-9) |

---

### `backend/apps/bill_of_entry/models.py` — signals section

| Property | Value |
|---|---|
| **Purpose** | Post-save/delete signals that dispatch balance recompute + BOE exchange rate recalculation |
| **Business rules** | BOE-003, BOE-004, BOE-005 |
| **Depends on** | `recompute_license_balance_task` (via lazy import), RowDetails, BillOfEntryModel |
| **Depended on by** | Fires whenever RowDetails is saved or deleted (all BOE row operations) |
| **Safe to modify** | Log messages |
| **Unsafe to modify** | Removing `_dispatch_balance_recompute()` from signals, changing from `on_commit` to inline dispatch, removing exchange rate recalculation |
| **Tests required** | `tests/bill_of_entry/test_boe.py::TestCreateBoeDispatchesBalanceTask`, `tests/balance/test_balance_system.py` tests 3-4 |

---

## Backend — Serializers (High Risk)

### `backend/apps/accounts/serializers.py` — `UserSerializer`

| Property | Value |
|---|---|
| **Purpose** | Login response and /me endpoint user object |
| **Critical field** | `is_superuser` — MUST be present. If removed, all superusers lose navigation |
| **Depended on by** | `LoginView`, `MeView`, `frontend/src/shared/auth/AuthContext.tsx` |
| **Safe to modify** | Add read-only fields |
| **Unsafe to modify** | Remove `is_superuser`, change `roles` field (used for RBAC) |
| **Tests required** | No regression test yet — add one (test gap AUTH-005) |

---

### `backend/apps/bill_of_entry/serializers.py` — BOE create/update

| Property | Value |
|---|---|
| **Purpose** | BOE header CRUD with allotment M2M management |
| **Critical logic** | `boe.allotment.set(allotment_data)` in `create()` and `update()` — enables Scenario B balance math |
| **Safe to modify** | Add new fields, change validation messages |
| **Unsafe to modify** | Remove allotment M2M set calls — breaks Scenario B (silent double-deduction) |

---

## Backend — Models (Medium Risk)

### `backend/apps/license/models/license.py` — `LicenseImportItemsModel`

| Property | Value |
|---|---|
| **Critical fields** | `available_quantity`, `debited_quantity`, `allotted_quantity` — written by `_update_item_level_balances()` |
| **Safe to modify** | Add new non-balance fields |
| **Unsafe to modify** | Change field names (must match legacy DB exactly), make `managed=True` |

---

### `backend/apps/trade/models.py` — `LicenseTradeLine.compute_amount()`

| Property | Value |
|---|---|
| **Purpose** | Billing formula for 3 modes (CIF_INR, FOB_INR, QTY) |
| **Critical constraint** | `Decimal(str(self.pct))` not `q2(self.pct)` before dividing by 100 |
| **Tests required** | `tests/trade/test_trade.py` (all 10 precision tests) |

---

## Frontend (High Risk)

### `frontend/src/shared/api/client.ts`

| Property | Value |
|---|---|
| **Purpose** | Global axios instance with JWT attachment, 401 refresh queue, envelope unwrap, blob guard |
| **Depended on by** | All 9 feature modules, AuthContext.tsx |
| **Safe to modify** | Timeout values, retry logic |
| **Unsafe to modify** | Envelope unwrap logic (affects ALL response parsing), blob guard removal (breaks PDF downloads), API_HOST export (used by AuthContext), refresh queue logic (concurrent 401 handling) |
| **Tests required** | Manual test: login, navigate, trigger 401, verify refresh, download PDF |

---

### `frontend/src/app/globals.css` — `@theme inline` block

| Property | Value |
|---|---|
| **Purpose** | Maps shadcn CSS vars to Tailwind v4 `--color-*` namespace |
| **Critical** | WITHOUT this block, ALL `bg-primary`, `text-foreground`, `border-border` etc. render nothing (buttons invisible) |
| **Safe to modify** | Add new color mappings, adjust color values |
| **Unsafe to modify** | Remove the entire `@theme inline { }` block |

---

### `frontend/src/shared/auth/AuthContext.tsx`

| Property | Value |
|---|---|
| **Purpose** | JWT state management, token refresh (proactive + reactive), idle timeout, RBAC helpers |
| **Critical** | `hasAnyRole()` checks `user?.is_superuser` — requires backend to send `is_superuser: true` |
| **Safe to modify** | IDLE_TIMEOUT_MS, TOKEN_REFRESH_BUFFER_MS values |
| **Unsafe to modify** | Remove `is_superuser` check in `hasAnyRole` — hides all navigation for superusers; switch proactive refresh from `axios.post(${API_HOST}${ENDPOINTS.AUTH.REFRESH})` to `apiClient` — risk of recursive interceptor |

---

### `frontend/vite.config.ts` — proxy section

| Property | Value |
|---|---|
| **Critical constraint** | `/api/v1` MUST come BEFORE `/api/` in proxy configuration |
| **Unsafe modification** | Reversing order routes all `/api/v1/` requests to legacy backend |

---

## Infrastructure (Critical)

### `nginx-labdhi.conf` / `nginx-license-manager.conf` / `nginx-license-tractor.conf`

| Property | Value |
|---|---|
| **Critical ordering** | `location /api/v1/` MUST be before `location /api/` |
| **Critical timeouts** | `client_header_timeout 30s` (Slow Loris protection — do not increase) |
| **Safe to modify** | Cache durations for static assets, log formats |
| **Unsafe to modify** | Remove `internal` from `/protected-media/` (security), change to `proxy_set_header X-Forwarded-Proto https` (hardcoded, should be `$scheme`) |

---

### `backend/config/settings/base.py` — Redis config

| Property | Value |
|---|---|
| **Critical** | Cache=/1, Broker=/2, Results=/3 must remain separate |
| **Unsafe to modify** | Merging any two services onto same Redis DB number |
