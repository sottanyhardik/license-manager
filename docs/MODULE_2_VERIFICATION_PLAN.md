# Module 2 (Planning) — Comprehensive Verification Plan

**Document Type:** Pre-Implementation Verification Strategy  
**Target:** CanonicalPlanningService + Consumer Migration (Phase O-S)  
**Status:** Ready for Implementation Gate  
**Last Updated:** 2026-08-10  

---

## EXECUTIVE SUMMARY

Module 2 (Planning) implements a unified canonical planning service to replace fragmented logic across:
- 5 norm-specific auto-plan engines (E1, E5, E126, E132, A3627)
- Multiple allocation validation paths
- API endpoints, UI forms, and PDF/Excel exporters
- Celery background jobs

This verification plan ensures:
1. **Runtime correctness** via canonical scenario tests
2. **Perfect parity** (API = UI = PDF = Excel = Reports)
3. **Security isolation** (company, license, authorization)
4. **Performance baseline** (query count, latency, throughput)
5. **Adversarial resilience** (edge cases, rounding, double-allocation)

---

## SCOPE & DELIVERABLES

### In Scope
- CanonicalPlanningService (backend core)
- PlannerFactory planner dispatch (E1, E5, E126, E132, A3627)
- LicenseItemPlan data persistence
- API endpoints (plan CRUD + auto-plan triggers)
- UI allocation forms (plan mode, splits)
- PDF/Excel exporters (plan display)
- Celery async jobs
- Authorization (company isolation, license access)

### Out of Scope
- Individual norm algorithms (tested separately, not re-tested here)
- Legacy planner code (frozen after parity gate)
- Database migrations (handled by Phase O setup)
- Frontend React components (UX verified separately)

---

## 1. RUNTIME VERIFICATION

### 1.1 Unit Tests: CanonicalPlanningService

**Purpose:** Verify core service logic in isolation.

**Test Coverage:**

| Category | Test Count | Scenario | Pass Criteria |
|----------|-----------|----------|---------------|
| **Input Validation** | 4 | Invalid license, null plan data, malformed items | Validation error raised, no DB writes |
| **Plan Creation** | 6 | New plan with 1/3/10 items, empty plan, duplicate names | Row count matches input, IDs generated, timestamps set |
| **Plan Updates** | 5 | Modify quantity, item name, unit price; delete lines | State persisted, version incremented, audit trail created |
| **Plan Deletions** | 3 | Hard delete, soft delete, restore deleted plan | Correct cascade behavior, audit logging |
| **Quantity Calculation** | 8 | Integer, decimal, rounding per norm, large quantities | Matches golden scenarios, decimal precision ≤2 dp |
| **Authorization** | 6 | Company isolation, license ownership, role checks | Correct user can read/write, unauthorized blocked |

**Test Files:**
- `backend/apps/license/tests/test_canonical_planning_service.py` (NEW)
- Fixtures: `backend/apps/license/tests/fixtures/canonical_planning_fixtures.py` (NEW)

**Success Criteria:**
- ✅ 32/32 unit tests PASS
- ✅ Code coverage ≥ 95% on service file
- ✅ All validation paths exercised
- ✅ No database leaks (rollback verified)

---

### 1.2 Integration Tests: Service + Module 1 (Balance)

**Purpose:** Verify CanonicalPlanningService integrates correctly with existing balance calculation (Module 1).

**Test Scenarios:**

| # | Scenario | Setup | Expected Behavior | Verification |
|---|----------|-------|-------------------|--------------|
| 1 | Plan created from fresh import | E1 license + 100kg CIF | Plan auto-allocates available balance | Balance decremented correctly |
| 2 | Plan respects live balance | Updated CIF mid-planning | Plan quantity adjusted or rejected | No over-allocation occurs |
| 3 | Plan line balance tracking | 3-line plan with partial allocations | Each line's remaining tracked independently | Allocations don't cross-contaminate |
| 4 | Plan + allocation cascade | Create plan, then allocate items | Plan quantities decremented as items allocated | Consistent state, no drift |
| 5 | Decimal precision cascade | 1055.56 CIF, multi-item split | Totals match within ±0.01 | No rounding drift across lines |
| 6 | Company isolation (Module 1) | 2 companies with same license# | Plan query returns correct company only | IDOR impossible |

**Test Files:**
- `backend/apps/license/tests/test_canonical_planning_integration.py` (NEW)
- Uses existing fixtures: `TestLedgerBalance`, `TestBalanceCalculator`

**Success Criteria:**
- ✅ 6/6 integration tests PASS
- ✅ Balance queries remain ≤5ms (no slowdown from planning)
- ✅ No cross-company data leakage
- ✅ Decimal precision ±0.01 maintained end-to-end

---

### 1.3 Golden Scenario Tests

**Purpose:** Verify CanonicalPlanningService reproduces known-good outputs (backward compatibility).

**Golden Scenarios:** 14 scenarios from Module 1 baseline, extended with planning data.

| # | License Type | Setup | Expected Plan Output | Verification |
|---|--------------|-------|----------------------|--------------|
| 1 | E1 Single Company | 100kg CIF → plan 50/50 split | 2 lines: 50kg each | Lines match, sum=100kg |
| 2 | E1 Multi-Company | 2 companies × 100kg | Each gets isolated plan | 0% cross-contamination |
| 3 | E5 Milk Group | 4 SKUs in pool, 200kg available | Auto-consolidate to representative | 1 line on representative, others reference |
| 4 | E126 Aluminum Foil | 3 variants, same HS code, 500kg | Create 3 separate plan lines (no pooling) | Lines independent, each has cap |
| 5 | E132 Sugar | Dairy exemption + normal, 1000kg | 2-line plan respecting exemption rules | Exemption rules enforced, balance correct |
| 6 | A3627 Auto-Plan | Fixed-rate product, 50 units @ 1000 INR ea | Auto-allocate across categories | Categories honored, total = 50000 |
| 7 | Plan Expiry | License expires tomorrow, active plan | Plan still usable (not future-checked) | Plan saved, expiry not enforced on plan |
| 8 | Plan Inheritance | Resynced license after plan exists | Preserve existing plan lines, add new | No plan wipes, additive only |
| 9 | CIF Attribution | Complex CIF from multiple sources | Plan visible in all attribution views | Attribution drill-down shows plan |
| 10 | Balance Edge Case | CIF = 0 (insufficient), 0.01 remainder | Plan rejects or truncates cleanly | Clear error, state consistent |
| 11 | Allocation Spanning Plan | Allocate 30kg from 2-line plan (20kg + 15kg) | Allocate reduces both lines atomically | Transactional, no partial allocation |
| 12 | Plan Split on Reallocation | Item allocated to wrong line, corrected | Plan line balances reconcile | Reallocation works, totals match |
| 13 | Commission Handling | License with commission + plan | Commission not counted in plan CIF | Plan uses only import CIF, not commission |
| 14 | Legacy Interop | Old ledger + new planning view | Both show consistent balance | Legacy + canonical agree within ±0.01 |

**Test Files:**
- `backend/apps/license/tests/test_canonical_planning_golden_scenarios.py` (NEW)
- Data: `audit_evidence/golden_scenarios/planning/` (reference JSON)

**Success Criteria:**
- ✅ 14/14 golden scenarios execute at runtime
- ✅ Computed outputs ≥ 99.9% match reference values
- ✅ No tolerance for financial differences (±0.00 on money)
- ✅ All scenarios complete in < 500ms individually

---

### 1.4 Canonical Planner Tests (Per Norm)

**Purpose:** Verify each norm's auto-plan function behaves correctly in canonical context.

**Coverage:**

| Norm | Existing Tests | New Canonical Tests | Focus |
|------|---|---|---|
| **E1** | ✅ test_e1_auto_plan.py (12 cases) | +3 | Interaction with canonical service, decimal handling |
| **E5** | ✅ test_e5_auto_plan.py (15 cases) | +2 | Milk grouping with canonical dispatch, representative selection |
| **E126** | ✅ test_e126_auto_plan.py (10 cases) | +2 | Variant independence, cap per line |
| **E132** | ✅ test_e132_auto_plan.py (14 cases) | +3 | Exemption rules, dual-track logic |
| **A3627** | ✅ test_a3627_auto_plan.py (8 cases) | +2 | Fixed-rate, category matching |

**Test Files:**
- Each `test_<norm>_auto_plan.py` gains 2-3 new canonical-integration tests
- Existing norm tests remain, newly scoped to norm-only verification

**Success Criteria:**
- ✅ All existing norm tests PASS (no regression)
- ✅ +10 new canonical integration tests PASS
- ✅ Each norm correctly produces LicenseItemPlan rows
- ✅ Planner dispatch via PlannerFactory works per norm

---

## 2. PARITY VERIFICATION

### 2.1 API ↔ Internal Service Parity

**Purpose:** Verify API response matches internal canonical service output.

**Test Matrix:**

| Endpoint | Method | Scenario | Verification |
|----------|--------|----------|--------------|
| `/license/{id}/item-plans` | GET | Retrieve created plan | Response matches DB state exactly |
| `/license/{id}/item-plans` | POST | Create plan (manual) | DB row created, response ID matches |
| `/license/{id}/item-plans/{plan_id}` | PATCH | Update quantity | DB updated, response reflects change |
| `/license/{id}/item-plans/{plan_id}` | DELETE | Delete line | DB deleted, GET returns 404 |
| `/license/{id}/auto-plan` | POST + norm | Trigger E1/E5/E126/E132/A3627 | Response LicenseItemPlan count matches DB |
| `/license/{id}/item-plans/bulk-upsert` | POST | Upsert 10 lines atomically | All-or-nothing, response counts correct |
| `/license/{id}/allocate-from-plan` | POST | Allocate from plan line | Plan balance decremented, allotment created |

**Test Files:**
- `backend/apps/license/tests/test_api_planning_parity.py` (NEW)
- Uses DRF test client, compares serialized API response vs. DB state

**Success Criteria:**
- ✅ 7 endpoint tests PASS
- ✅ API response ≡ DB state (byte-for-byte JSON comparison)
- ✅ All decimal fields match (±0.00)
- ✅ Response times < 300ms per request

---

### 2.2 UI Forms ↔ API Parity

**Purpose:** Verify UI form submissions produce identical results to direct API calls.

**Test Scenarios:**

| Scenario | UI Action | API Equivalent | Verification |
|----------|-----------|---|---|
| **Create Plan** | Fill form, submit | POST `/item-plans` | DB state identical |
| **Edit Quantities** | Change qty in grid, save | PATCH `/item-plans/{id}` | Updated row matches |
| **Bulk Upload** | Drag-drop CSV, parse, confirm | POST `/bulk-upsert` | All lines created identically |
| **Auto-Plan Trigger** | Click "Auto-Plan E1", confirm | POST `/auto-plan` with E1 | Same lines, same quantities |
| **Delete Lines** | Select rows, delete | DELETE `/item-plans/{id}` | Deleted rows gone |

**Test Files:**
- `backend/apps/license/tests/test_ui_api_planning_parity.py` (NEW)
- Simulates form parsing + API calls, compares DB outcomes

**Success Criteria:**
- ✅ 5 UI scenarios create identical DB state as direct API
- ✅ Form validation errors match API validation
- ✅ No data loss in form → API → DB pipeline

---

### 2.3 PDF Exporter ↔ Canonical Data Parity

**Purpose:** Verify PDF export displays correct planning data.

**Test Scenarios:**

| Data Element | Source | PDF Display | Verification |
|---|---|---|---|
| **Plan Lines** | LicenseItemPlan table | Table in PDF section | Line count matches, order correct |
| **Item Names** | LicenseItemPlan.item_name | PDF text | Matches DB exactly |
| **Planned Quantities** | LicenseItemPlan.planned_quantity | PDF table | Displayed value = DB value (±0.01) |
| **Unit Prices** | LicenseItemPlan.unit_price | PDF table | Matches DB |
| **Plan Balance** | Computed from allocations | "Remaining" column | Correct = planned - debited |
| **CIF Attribution** | From Module 1 balance service | "CIF Source" column | Shows import/opening/commission correctly |
| **Company Header** | License.company | PDF title/header | Matches license company, not other |

**Test Files:**
- `backend/apps/license/tests/test_pdf_exporter_planning_parity.py` (NEW)
- Uses PyPDF2 to extract text, compares vs. canonical data

**Success Criteria:**
- ✅ 7 data elements display correctly in PDF
- ✅ PDF text extraction finds all expected quantities (±0.01 tolerance)
- ✅ No exporter queries stale/cached data

---

### 2.4 Excel Exporter ↔ Canonical Data Parity

**Purpose:** Verify Excel export produces correct planning calculations.

**Test Scenarios:**

| Sheet | Column | Formula | Verification |
|---|---|---|---|
| **Summary** | Total Planned Qty | SUM(Details!B:B) | Matches service total |
| **Summary** | Total Allocated | SUM(Allocations!C:C) | Correct calculation |
| **Details** | Plan Line Items | Pulled from DB | Count matches, no dupes |
| **Details** | Remaining = Planned - Allocated | Formula | Correct per line |
| **Calc Sheet** | Revenue Impact | qty × unit_price | Matches golden scenarios |
| **Audit Trail** | Created By | From audit model | Correct user recorded |

**Test Files:**
- `backend/apps/license/tests/test_excel_exporter_planning_parity.py` (NEW)
- Uses openpyxl to read generated Excel, verifies formulas + values

**Success Criteria:**
- ✅ 6 Excel elements correct
- ✅ Formulas preserved (not static values)
- ✅ Excel file size < 5MB for large plans (100+ lines)
- ✅ Export completes in < 2 seconds

---

### 2.5 Report Views ↔ Canonical Data Parity

**Purpose:** Verify all planning report views (Item Pivot, Dashboard, Ledger Detail) show consistent planning data.

**Test Matrix:**

| Report | Planning Data | Consistency Check |
|---|---|---|
| **Item Pivot Report** | Plan quantities by item | Matches LicenseItemPlan totals exactly |
| **Dashboard Balance** | Available qty = CIF - allocated | Uses canonical balance, includes plan lines in "allocated" |
| **Ledger Detail View** | Plan attribution source | Shows correct attribution, plan lines visible |
| **Planned Report** | All planned quantities | Matches bulk export |

**Test Files:**
- `backend/apps/license/tests/test_report_views_planning_parity.py` (NEW)
- Compares report outputs vs. canonical service queries

**Success Criteria:**
- ✅ All 4 report views show consistent planning data
- ✅ No conflicting totals across reports
- ✅ Reports include both planned + actual allocations

---

## 3. SECURITY VERIFICATION

### 3.1 Company Isolation (IDOR Prevention)

**Purpose:** Prevent one company from accessing another's planning data.

**Test Matrix:**

| Scenario | Setup | Attack | Expected Outcome |
|---|---|---|---|
| **Read IDOR** | User A (Company X), tries GET license of Company Y | Request `/license/Y/item-plans` | 403 Forbidden |
| **Write IDOR** | User B (Company Y), tries PATCH plan of Company X | Request PATCH `/license/X/item-plans/1` | 403 Forbidden |
| **Bulk IDOR** | User C (Company Z), tries bulk-upsert Company A data | POST `/bulk-upsert` with Company A license | 403 Forbidden |
| **Auto-Plan IDOR** | User D (Company W), triggers auto-plan on Company V license | POST `/auto-plan` for Company V | 403 Forbidden |
| **Report IDOR** | User E views reports, filters by unauthorized company | Query `/reports/item-pivot?company=Z` (not user's) | Report filtered to user's company only |

**Test Files:**
- `backend/apps/license/tests/test_planning_idor.py` (NEW)
- Uses multiple users/companies, confirms all isolation

**Authorization Checks:**
- ✅ License ownership verified before plan access
- ✅ Company from license checked against user's company role
- ✅ No "superuser" bypass for plan queries (always check)
- ✅ Bulk operations iterate licenses, verifying each

**Success Criteria:**
- ✅ 5/5 IDOR attacks blocked with 403
- ✅ Authorized users can still access own plans
- ✅ No data leakage in error messages

---

### 3.2 License Authorization (Role-Based Access)

**Purpose:** Enforce role-based access to planning features.

**Test Matrix:**

| Role | Action | Expected |
|---|---|---|
| **LICENSE_VIEWER** (read-only) | GET `/item-plans` | ✅ Allowed |
| **LICENSE_VIEWER** | POST `/item-plans` (create) | ❌ 403 Forbidden |
| **LICENSE_VIEWER** | POST `/auto-plan` | ❌ 403 Forbidden |
| **LICENSE_EDITOR** | GET, POST, PATCH | ✅ All allowed |
| **LICENSE_EDITOR** | DELETE | ✅ Allowed (can soft-delete) |
| **ALLOTMENT_ADMIN** | Access planning features | ❌ No access (wrong module) |
| **SUPERUSER** | Any action | ✅ All allowed |
| **Anonymous** | Any action | ❌ 401 Unauthorized |

**Test Files:**
- `backend/apps/license/tests/test_planning_authorization.py` (NEW)
- Uses DRF test utilities + role factory

**Success Criteria:**
- ✅ 8/8 authorization scenarios correct
- ✅ No privilege escalation bugs
- ✅ Superuser still works (not accidentally locked out)

---

### 3.3 Bulk Operations Authorization

**Purpose:** Verify bulk operations (import CSV, auto-plan batch) respect authorization.

**Test Scenarios:**

| Scenario | Setup | Verification |
|---|---|---|
| **Bulk Upsert Auth** | User with LICENSE_EDITOR role | Can bulk-upsert own company licenses; blocked on foreign |
| **Batch Auto-Plan** | Background job triggered on multiple licenses | Job processes only licenses user can access |
| **Audit Trail Auth** | Non-admin user views audit log | Only sees own actions, not others' |
| **Partial Failure** | Bulk upsert: 5 licenses (3 authorized, 2 not) | Processes 3, rejects 2 with clear error per license |

**Test Files:**
- `backend/apps/license/tests/test_bulk_planning_authorization.py` (NEW)

**Success Criteria:**
- ✅ Bulk operations enforce per-item authorization
- ✅ Partial failures don't corrupt state
- ✅ Clear error messages identify unauthorized items

---

## 4. PERFORMANCE VERIFICATION

### 4.1 Query Count Baseline

**Purpose:** Establish performance baseline to prevent N+1 queries and regressions.

**Test Scenarios:**

| Operation | Data Size | Expected Queries | Actual | Status |
|---|---|---|---|---|
| **GET /item-plans** | 100-line plan | ≤5 queries | TBD | ⏳ |
| **GET /item-plans** | 1000-line plan | ≤6 queries | TBD | ⏳ |
| **POST /item-plans** (create 10) | 10 new lines | ≤2 queries | TBD | ⏳ |
| **PATCH /item-plans/{id}** | Single line update | ≤3 queries | TBD | ⏳ |
| **POST /auto-plan** | Trigger E1 | ≤8 queries | TBD | ⏳ |
| **POST /bulk-upsert** | Upsert 50 lines | ≤4 queries | TBD | ⏳ |
| **GET /reports/item-pivot** | Report with plan data | ≤10 queries | TBD | ⏳ |

**Test Files:**
- `backend/apps/license/tests/test_planning_performance_queries.py` (NEW)
- Uses Django's `assertNumQueries()` context manager

**Query Optimization:**
- ✅ Use `select_related()` for license, company FKs
- ✅ Use `prefetch_related()` for item-plans list
- ✅ Avoid looping in Python (use batch queries)
- ✅ Cache balanced quantities (from Module 1)

**Success Criteria:**
- ✅ No query regression vs. baseline
- ✅ Bulk operations use batch queries (not per-item loops)
- ✅ Report queries optimized (< 10 for 100+ lines)

---

### 4.2 Latency Baseline

**Purpose:** Establish end-to-end latency expectations.

**Test Scenarios:**

| Operation | Data Size | Baseline SLA | Measured | Status |
|---|---|---|---|---|
| **GET /item-plans** | 100 lines | 200ms | TBD | ⏳ |
| **GET /item-plans** | 1000 lines | 300ms | TBD | ⏳ |
| **POST /item-plans** (create 1) | Single line | 100ms | TBD | ⏳ |
| **POST /item-plans** (create 10) | Bulk create | 200ms | TBD | ⏳ |
| **POST /auto-plan** | Single license | 150ms | TBD | ⏳ |
| **POST /auto-plan** | 10 licenses (parallel) | 500ms | TBD | ⏳ |
| **PDF Export** | 100-line plan | 800ms | TBD | ⏳ |
| **Excel Export** | 100-line plan | 500ms | TBD | ⏳ |

**Test Files:**
- `backend/apps/license/tests/test_planning_latency.py` (NEW)
- Uses timeit or pytest-benchmark

**Optimization Targets:**
- Auto-plan: ≤150ms (pre-computed categorization)
- Bulk upsert: ≤200ms (batch insert, not per-row)
- Exports: ≤1s (async in production, but test sync)

**Success Criteria:**
- ✅ All operations within SLA
- ✅ Sub-100ms for single-line creates
- ✅ Bulk operations scale linearly (not exponential)

---

### 4.3 Throughput & Concurrency

**Purpose:** Verify system handles concurrent planning operations.

**Test Scenarios:**

| Scenario | Concurrency | Duration | Success Rate |
|---|---|---|---|
| **Concurrent Plan Creates** | 10 users, 10 licenses each | 30 sec | ✅ 100% success |
| **Concurrent Auto-Plans** | 5 licenses auto-planned in parallel | 20 sec | ✅ 100% success (no conflicts) |
| **Concurrent Bulk Upserts** | 3 users bulk-upsert different licenses | 15 sec | ✅ 100% success |
| **Concurrent Allocations** | 20 users allocate from same plan | 10 sec | ✅ Plan line balance decremented atomically |

**Test Files:**
- `backend/apps/license/tests/test_planning_concurrency.py` (NEW)
- Uses threading or pytest-xdist for concurrency

**Database Constraints:**
- ✅ Row-level locking on LicenseItemPlan updates
- ✅ Atomic balance decrements (no race conditions)
- ✅ No deadlocks observed

**Success Criteria:**
- ✅ All concurrent operations succeed
- ✅ No orphaned transactions
- ✅ Final state consistent across all threads

---

### 4.4 Large Dataset Performance

**Purpose:** Verify scalability with large plans.

**Test Scenarios:**

| Test | Plan Size | Operation | SLA | Status |
|---|---|---|---|---|
| **Large Plan Display** | 1000 lines | GET `/item-plans` | ≤300ms | ⏳ |
| **Large Plan Export** | 1000 lines | PDF export | ≤1s | ⏳ |
| **Large Bulk Upsert** | 500 lines | POST `/bulk-upsert` | ≤500ms | ⏳ |
| **Large Report** | 1000 lines across 5 licenses | Item Pivot report | ≤1s | ⏳ |

**Test Files:**
- `backend/apps/license/tests/test_planning_large_datasets.py` (NEW)
- Uses factories to generate test data

**Pagination/Streaming:**
- ✅ API paginates plan results (50 per page default)
- ✅ Exports stream to disk (no full load in memory)
- ✅ Reports use cursors (not full dataset fetch)

**Success Criteria:**
- ✅ No memory bloat (< 100MB for 1000-line plan)
- ✅ All operations stay within SLA
- ✅ Database query plans use indexes (EXPLAIN analyzed)

---

## 5. ADVERSARIAL VERIFICATION

### 5.1 Rounding & Decimal Precision

**Purpose:** Detect rounding drift that accumulates across calculations.

**Test Scenarios:**

| Scenario | Input | Calculation | Verified Against |
|---|---|---|---|
| **Decimal Cascade** | CIF = 1055.56, split 3 ways | 351.85 + 351.85 + 351.86 | Sum = 1055.56 ±0.00 |
| **Unit Price × Qty** | Qty = 33.33kg, Price = 1234.56/kg | Revenue = 41120.93 | Golden scenario exact match |
| **Allocation Precision** | Allocate 12.34kg from plan, 5 times | Total 61.7kg | Remaining balance = planned - allocated ±0.00 |
| **Average Calc** | 3 imports: 100.1, 100.2, 100.15 | Average = 100.15 | Matches golden, no drift |
| **Rounding Modes** | Quantity 9.995 rounded to 2dp | Result = 10.00 | Consistent with financial rounding rules |

**Test Files:**
- `backend/apps/license/tests/test_planning_decimal_precision.py` (NEW)
- Explicit Decimal type, no float arithmetic

**Success Criteria:**
- ✅ All sums balance to ±0.00 (zero tolerance on money)
- ✅ All calculations match golden scenarios exactly
- ✅ No silent truncation (all decimals preserved to 2dp)

---

### 5.2 Double-Allocation Detection

**Purpose:** Prevent allocating same plan line quantity twice.

**Test Scenarios:**

| Scenario | Setup | Attack | Prevention | Status |
|---|---|---|---|---|
| **Duplicate Allocate (Same Item)** | Plan: 100kg, allocate 50kg twice | Allocate same item twice | DB constraint or application logic prevents 2nd | ✅ |
| **Concurrent Allocate (Race)** | Plan: 100kg, 2 allocations in parallel for 60kg each | Race condition on balance decrement | Row-level lock ensures only one succeeds | ✅ |
| **Cascade Allocate** | Allocate 50kg, then DELETE plan line, re-create, allocate again | Allocate from "ghost" line | Deleted line_id doesn't re-allocate | ✅ |
| **Bulk Allocate Duplicate** | Bulk import 10 allocations, 2 reference same plan line | Duplicate in CSV upload | Validation rejects or atomically applies all | ⏳ |

**Test Files:**
- `backend/apps/license/tests/test_planning_no_double_allocation.py` (NEW)

**Database Constraints:**
- ✅ Foreign key on allocations → plan lines (referential integrity)
- ✅ Unique constraint on (plan_line_id, allocation_id) if needed
- ✅ No orphaned allocations (plan line deleted → allocations cleaned)

**Success Criteria:**
- ✅ 4/4 double-allocation scenarios prevented
- ✅ Clear error message if user attempts duplicate
- ✅ No silent data loss

---

### 5.3 Negative/Invalid Quantities

**Purpose:** Prevent invalid quantity states (negative, zero, null).

**Test Scenarios:**

| Scenario | Input | Validation | Status |
|---|---|---|---|
| **Negative Quantity** | Create plan with qty = -10 | Rejected (validation error) | ✅ |
| **Zero Quantity** | Create plan with qty = 0 | Allowed (placeholder, not allocated) | ⏳ |
| **Null Quantity** | POST without qty field | Rejected (required field) | ✅ |
| **Non-Numeric Quantity** | qty = "abc" | Rejected (type error) | ✅ |
| **Allocation > Plan** | Plan 100kg, allocate 101kg | Rejected (balance check) | ✅ |
| **Negative Allocation** | Allocate -50kg from plan | Rejected (validation) | ✅ |

**Test Files:**
- `backend/apps/license/tests/test_planning_invalid_quantities.py` (NEW)

**Validation Rules:**
- ✅ Quantity must be > 0 (or allow 0 for placeholder)
- ✅ Allocation must be > 0, ≤ remaining balance
- ✅ Unit price must be ≥ 0 (allow 0 for internal transfers)

**Success Criteria:**
- ✅ All invalid scenarios rejected
- ✅ Error messages clear (e.g., "Quantity must be positive")
- ✅ No DB constraint violations (validation prevents upstream)

---

### 5.4 Wrong Scope / Cross-Contamination

**Purpose:** Detect data bleeding across licenses, companies, or norms.

**Test Scenarios:**

| Scenario | Setup | Attack | Expected | Status |
|---|---|---|---|---|
| **License Scope** | License A + B, same company | Get plan for A, check B's missing | Plan A isolated from B | ✅ |
| **Company Scope** | Company X, Y with License A (X), License B (Y) | User from Y queries License A | 403 Forbidden | ✅ |
| **Norm Mixing** | E1 license with A3627 auto-plan trigger | Trigger wrong norm | Rejected (schema mismatch) or uses norm from license | ✅ |
| **Planner Registry** | Register incorrect planner for norm | Norm "E9" → E5 planner | Returns E9 items (not E5) | ⏳ |
| **Allocation Scope** | Item A from License 1 allocated to plan from License 2 | Allocate across license boundary | Rejected (FK validation) | ✅ |

**Test Files:**
- `backend/apps/license/tests/test_planning_scope_isolation.py` (NEW)

**Architectural Checks:**
- ✅ License PK on plan lines (no orphan lines)
- ✅ Company derived from license (not stored separately)
- ✅ Planner factory uses license.scheme to select norm

**Success Criteria:**
- ✅ 5/5 scope attacks prevented
- ✅ No silent cross-contamination
- ✅ Clear error if user attempts cross-scope operation

---

### 5.5 Allocation Consistency Under Rebalancing

**Purpose:** Verify plan lines remain consistent when underlying CIF changes.

**Test Scenarios:**

| Scenario | Setup | Change | Expected Behavior | Status |
|---|---|---|---|---|
| **CIF Decrease** | Plan: 100kg CIF, plan created 80kg | CIF drops to 50kg | Plan still shows 80kg (not retroactive) | ✅ |
| **CIF Increase** | Plan: 100kg CIF, plan created 80kg | CIF increases to 150kg | Plan still shows 80kg (not auto-expanded) | ✅ |
| **Allocation After Replan** | Plan A: 100kg, allocate 30kg; then create Plan B from same CIF | Allocate from B: 50kg | Both plans show correct remaining (A: 70kg, B: 50kg) | ⏳ |
| **Manual Reallocation** | Allocate 40kg from Plan A line 1, move to line 2 | Reallocate atomically | Both lines updated, no orphans | ✅ |

**Test Files:**
- `backend/apps/license/tests/test_planning_rebalance_consistency.py` (NEW)

**Design Pattern:**
- ✅ Plan quantities are independent snapshots (CIF captured at plan creation)
- ✅ Allocations reference plan lines, not CIF directly
- ✅ If CIF changes, new plan created (not retroactive)

**Success Criteria:**
- ✅ 4/4 rebalancing scenarios handle correctly
- ✅ No orphaned allocations
- ✅ User visible/warned if CIF drops below active allocations

---

### 5.6 Edge Case Combinations

**Purpose:** Test unusual but valid combinations.

**Test Scenarios:**

| Scenario | Setup | Operation | Status |
|---|---|---|---|
| **Plan on Empty License** | License with 0 CIF, 0 items | Create empty plan | ✅ Allowed (placeholder) |
| **Plan Expiry Edge** | License expires today, create plan | Can plan expire-today license? | ✅ Allow (expiry not checked on plan create) |
| **Multi-Sourced CIF** | Import + Opening + Commission all present | Auto-plan uses which? | ✅ Only import (not opening/commission) |
| **Scheme Change** | E1 license, then change scheme to E5 | Existing plan valid? | ⏳ Plan becomes stale; user warned |
| **Plan Without Items** | Create plan with 0 line items | Save plan (no lines) | ✅ Allowed (can add lines later) |
| **Allocation Without Plan** | No plan created, try to allocate | Manual allocation (no plan) | ✅ Allowed (plan optional for allocation) |

**Test Files:**
- `backend/apps/license/tests/test_planning_edge_cases.py` (NEW)

**Success Criteria:**
- ✅ All edge cases handled without crashes
- ✅ User-friendly errors or warnings
- ✅ State remains consistent

---

## 6. VERIFICATION EXECUTION PLAN

### 6.1 Phase Order & Dependencies

```
Phase 1: Unit Tests (Runtime Verification)
  ├─ CanonicalPlanningService tests (4.1)
  ├─ Planner integration tests (1.4)
  └─ [Gate: 32/32 unit tests PASS]

Phase 2: Integration Tests (Runtime Verification)
  ├─ Module 1 balance integration (1.2)
  ├─ Golden scenario tests (1.3)
  └─ [Gate: 6 integration + 14 golden PASS]

Phase 3: Parity Tests (Verification 2.x)
  ├─ API ↔ Service parity (2.1)
  ├─ UI ↔ API parity (2.2)
  ├─ PDF parity (2.3)
  ├─ Excel parity (2.4)
  ├─ Report parity (2.5)
  └─ [Gate: 100% parity verified]

Phase 4: Security Tests (Verification 3.x)
  ├─ IDOR prevention (3.1)
  ├─ Authorization (3.2)
  ├─ Bulk operations (3.3)
  └─ [Gate: All security tests PASS]

Phase 5: Performance Tests (Verification 4.x)
  ├─ Query count baseline (4.1)
  ├─ Latency baseline (4.2)
  ├─ Concurrency (4.3)
  ├─ Large datasets (4.4)
  └─ [Gate: All performance SLAs met]

Phase 6: Adversarial Tests (Verification 5.x)
  ├─ Decimal precision (5.1)
  ├─ Double-allocation (5.2)
  ├─ Invalid quantities (5.3)
  ├─ Scope isolation (5.4)
  ├─ Rebalancing consistency (5.5)
  ├─ Edge cases (5.6)
  └─ [Gate: All adversarial scenarios blocked]

Phase 7: Regression & Full Suite
  ├─ All existing Module 1 tests still PASS
  ├─ All existing norm tests still PASS
  ├─ New test suite integrated into CI/CD
  └─ [Gate: Zero regressions]
```

### 6.2 Success Criteria by Phase

| Phase | Criteria | Evidence | Status |
|---|---|---|---|
| **1: Unit** | 32/32 PASS, ≥95% coverage | pytest report | ⏳ |
| **2: Integration** | 20/20 PASS (6 + 14), <500ms each | pytest report | ⏳ |
| **3: Parity** | 100% data match (API, UI, PDF, Excel, Reports) | Comparison reports | ⏳ |
| **4: Security** | 5 IDOR + 8 auth + 4 bulk = 17/17 PASS | Security audit log | ⏳ |
| **5: Performance** | All SLAs met, no regression vs. baseline | Performance report | ⏳ |
| **6: Adversarial** | All attacks blocked, ±0.00 precision, no double-allocation | Adversarial test report | ⏳ |
| **7: Regression** | All existing tests PASS, new tests integrated | CI/CD result | ⏳ |

### 6.3 Verification Gate Closure

**Hard Gates (Must PASS to proceed):**

```
┌─────────────────────────────────────────────────────────────┐
│ All Verification Phases Complete                            │
│                                                             │
│ ✅ Unit Tests: 32/32 PASS                                   │
│ ✅ Integration: 20/20 PASS                                  │
│ ✅ Parity: 100% match (API, UI, PDF, Excel, Reports)       │
│ ✅ Security: 17/17 PASS (IDOR, Auth, Isolation)            │
│ ✅ Performance: All SLAs met                                │
│ ✅ Adversarial: All attacks prevented                       │
│ ✅ Regression: All existing tests PASS                      │
│                                                             │
│ Total: 129/129 tests PASS                                   │
│ Coverage: ≥95% on canonical service                        │
│ Precision: ±0.00 (no rounding drift)                       │
│ Security: Zero IDOR/auth bugs detected                     │
│                                                             │
│ GATE: ✅ PASS — Proceed to Implementation                  │
└─────────────────────────────────────────────────────────────┘
```

**Blocker Conditions (Halt verification if detected):**

- ❌ Any financial calculation differs by > ±0.01
- ❌ Any IDOR/authorization bypass discovered
- ❌ Double-allocation possible
- ❌ Data loss or orphaned records
- ❌ Performance regression > 20% vs. baseline
- ❌ Existing tests regress to FAIL
- ❌ Company isolation compromised

---

## 7. IMPLEMENTATION & RUNNING TESTS

### 7.1 Test Infrastructure Setup

**New Test Files to Create:**

```
backend/apps/license/tests/
├─ test_canonical_planning_service.py                [NEW] 1.1
├─ test_canonical_planning_integration.py            [NEW] 1.2
├─ test_canonical_planning_golden_scenarios.py       [NEW] 1.3
├─ test_api_planning_parity.py                       [NEW] 2.1
├─ test_ui_api_planning_parity.py                    [NEW] 2.2
├─ test_pdf_exporter_planning_parity.py              [NEW] 2.3
├─ test_excel_exporter_planning_parity.py            [NEW] 2.4
├─ test_report_views_planning_parity.py              [NEW] 2.5
├─ test_planning_idor.py                             [NEW] 3.1
├─ test_planning_authorization.py                    [NEW] 3.2
├─ test_bulk_planning_authorization.py               [NEW] 3.3
├─ test_planning_performance_queries.py              [NEW] 4.1
├─ test_planning_latency.py                          [NEW] 4.2
├─ test_planning_concurrency.py                      [NEW] 4.3
├─ test_planning_large_datasets.py                   [NEW] 4.4
├─ test_planning_decimal_precision.py                [NEW] 5.1
├─ test_planning_no_double_allocation.py             [NEW] 5.2
├─ test_planning_invalid_quantities.py               [NEW] 5.3
├─ test_planning_scope_isolation.py                  [NEW] 5.4
├─ test_planning_rebalance_consistency.py            [NEW] 5.5
├─ test_planning_edge_cases.py                       [NEW] 5.6
└─ fixtures/
   └─ canonical_planning_fixtures.py                 [NEW]
```

### 7.2 Running Tests

**Command to run all verification tests:**

```bash
# Unit + Integration tests
pytest backend/apps/license/tests/test_canonical_planning_*.py -v

# Parity tests
pytest backend/apps/license/tests/test_*_planning_parity.py -v

# Security tests
pytest backend/apps/license/tests/test_planning_{idor,authorization,bulk_planning_authorization}.py -v

# Performance tests
pytest backend/apps/license/tests/test_planning_{performance_queries,latency,concurrency,large_datasets}.py -v

# Adversarial tests
pytest backend/apps/license/tests/test_planning_{decimal_precision,no_double_allocation,invalid_quantities,scope_isolation,rebalance_consistency,edge_cases}.py -v

# All verification tests together
pytest backend/apps/license/tests/test_*planning*.py -v --cov=backend/apps/license/services/canonical_planning --cov-report=html

# Existing tests (regression check)
pytest backend/apps/license/tests/test_{e1,e5,e126,e132,a3627}_auto_plan.py -v
```

### 7.3 Test Execution Timeline

| Phase | Test Files | Count | Estimated Duration |
|---|---|---|---|
| **1: Unit** | test_canonical_planning_service.py | 32 | 5 min |
| **2: Integration** | test_canonical_planning_integration.py + test_canonical_planning_golden_scenarios.py | 20 | 10 min |
| **3: Parity** | test_*_planning_parity.py | 28 | 15 min |
| **4: Security** | test_planning_idor.py + test_planning_authorization.py + test_bulk_planning_authorization.py | 17 | 8 min |
| **5: Performance** | test_planning_performance_*.py | 20 | 30 min (includes benchmark) |
| **6: Adversarial** | test_planning_{decimal,no_double,invalid,scope,rebalance,edge}.py | 32 | 12 min |
| **7: Regression** | Existing norm tests | 59 | 10 min |
| **Total** | 21 test files | **178 tests** | **~90 minutes** |

---

## 8. SIGN-OFF & GATE CLOSURE

### 8.1 Verification Report Format

**Verification Report Template:**

```
# Module 2 (Planning) — Verification Report
Date: [DATE]
Executed By: [AGENT/ROLE]

## Summary
- Total Tests: 178
- Passed: __/178
- Failed: __/178
- Skipped: __/178
- Coverage: __% (target ≥95%)

## Phase Results
- [ ] Phase 1: Unit Tests (32 tests) — PASS/FAIL
- [ ] Phase 2: Integration (20 tests) — PASS/FAIL
- [ ] Phase 3: Parity (28 tests) — PASS/FAIL
- [ ] Phase 4: Security (17 tests) — PASS/FAIL
- [ ] Phase 5: Performance (20 tests) — PASS/FAIL
- [ ] Phase 6: Adversarial (32 tests) — PASS/FAIL
- [ ] Phase 7: Regression (59 tests) — PASS/FAIL

## Findings
- Blockers: __
- Warnings: __
- Observations: __

## Gate Recommendation
- [ ] PASS — Proceed to Implementation
- [ ] BLOCKED — Issues found (list above)
- [ ] CONDITIONAL — Pass with monitoring (list conditions)

## Sign-Off
Verified By: [NAME]
Date: [DATE]
Confidence: [HIGH/MEDIUM/LOW]
```

### 8.2 Gate Closure Decision

**Automatic PASS if:**
- ✅ 178/178 tests PASS
- ✅ ≥95% code coverage
- ✅ All golden scenarios match ±0.00
- ✅ All security tests PASS
- ✅ All performance SLAs met
- ✅ Zero regressions
- ✅ No financial calculation differences > ±0.01

**Escalate if:**
- ⚠️ 1-5 tests FAIL (investigate root cause)
- ⚠️ Coverage 90-95% (document trade-off)
- ⚠️ Performance SLA missed by <20% (review and optimize)
- ⚠️ Any security warning (investigate, may be false positive)

**HARD BLOCK if:**
- ❌ > 5 tests FAIL
- ❌ Financial difference > ±0.01
- ❌ Any IDOR bypass confirmed
- ❌ Company isolation compromised
- ⛔ Existing tests regress to FAIL

---

## 9. HANDOFF TO NEXT PHASE

### 9.1 Verification Complete → Implementation Start

When all gates PASS:

1. **Commit verification plan**: docs/MODULE_2_VERIFICATION_PLAN.md (this file)
2. **Create verification report**: docs/MODULE_2_VERIFICATION_REPORT.md
3. **Lock Module 2 for implementation**: Set feature branch write lock
4. **Hand off to Phase O (Implementation)**: Backend engineer implements CanonicalPlanningService
5. **Auto-continue**: After implementation, run full verification suite again

### 9.2 Verification Data Artifacts

**Preserved as evidence:**

- Test results (pytest.xml with full output)
- Coverage report (coverage.xml + HTML)
- Query analysis (actual query counts per operation)
- Performance baselines (latency, throughput measurements)
- Security audit log (all authorization checks)
- Golden scenario outputs (reference values)

**Location:** `/audit_evidence/verification/module_2/`

---

## APPENDIX A: Quick Reference

### Success Metrics at a Glance

| Metric | Target | Evidence |
|---|---|---|
| **Test Pass Rate** | 100% (178/178) | pytest report |
| **Code Coverage** | ≥95% | coverage.xml |
| **Golden Scenario Match** | ±0.00 (financial) | verification report |
| **Query Count** | No regression | performance report |
| **Latency SLA** | All met | latency report |
| **IDOR Attacks Prevented** | 5/5 | security audit log |
| **Authorization Correct** | 8/8 | security audit log |
| **Decimal Precision** | ±0.00 | precision audit |
| **Double-Allocation** | 0 prevented | audit log |
| **Regression** | 0 existing tests broken | pytest report |

### Verification Command Cheat Sheet

```bash
# Run all verification phases
pytest backend/apps/license/tests/test_*planning*.py -v --cov=... --tb=short

# Run by phase
pytest backend/apps/license/tests/test_canonical_planning_*.py -v            # Phase 1-2
pytest backend/apps/license/tests/test_*_planning_parity.py -v               # Phase 3
pytest backend/apps/license/tests/test_planning_{idor,authorization}.py -v   # Phase 4
pytest backend/apps/license/tests/test_planning_performance_*.py -v           # Phase 5
pytest backend/apps/license/tests/test_planning_{decimal,double,invalid,scope,rebalance,edge}.py -v  # Phase 6

# Check regression
pytest backend/apps/license/tests/test_{e1,e5,e126,e132,a3627}_auto_plan.py -v  # Phase 7

# Generate coverage report
coverage run -m pytest backend/apps/license/tests/test_*planning*.py
coverage report --precision=2
coverage html
```

---

## APPENDIX B: Blockers & Risk Mitigation

| Risk | Detection | Mitigation | Owner |
|---|---|---|---|
| **Financial discrepancy > ±0.01** | Golden scenario tests fail | Audit decimal handling, verify against legacy | QA |
| **IDOR vulnerability** | IDOR tests expose auth bypass | Review authorization code, add constraint | Security |
| **Double-allocation** | Concurrent test exposes race condition | Implement row-level locking | Backend |
| **Performance regression** | Latency test > SLA | Profile queries, optimize with caching/indexes | DBA |
| **Scope leakage** | Scope isolation tests fail | Audit query scoping, check FKs | Backend |

---

**Document Status:** ✅ READY FOR VERIFICATION PHASE

**Next Action:** Launch Phase 1 (Unit Tests) when implementation begins

**Approval Required:** ✅ (Automatic on gate PASS)
