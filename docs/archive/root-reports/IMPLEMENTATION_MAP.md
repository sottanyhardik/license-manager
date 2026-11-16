# Implementation Map: Allocation & Planning Specification

**Date:** 2026-08-10  
**Status:** Pre-Implementation Reconnaissance Complete  
**Branch:** feature/V2

---

## EXECUTIVE SUMMARY

The specification (requirements 1-49) describes a comprehensive allocation/planning system with:
- Manual + automatic planning with fixed priority rules
- Company assignment (manual selection + automatic split)
- Shortfall handling with FIFO fulfillment
- Lifecycle states (CREATED/RELEASED/REACTIVATED/COMPLETED)
- Full audit trails (all changes tracked)
- BOE reconciliation (automatic allocation increases)
- Transaction atomicity (all-or-nothing saves)

**Existing state:** Partial infrastructure exists (LicenseItemPlan from Module 2, AllotmentModel). **Gap:** Lifecycle states, version history, company tracking on allocations, shortfall model, reactivation logic, combined audit events.

---

## CURRENT CODEBASE STATE

### Models Present
- **LicenseItemPlan** (backend/apps/license/models/core.py:1181) — Planning lines with qty/CIF caps, remaining balance tracking
- **AllotmentModel** (backend/apps/allotment/models.py:46) — Allotment containers, required_qty, unit_value
- **AllotmentItems** (backend/apps/allotment/models.py:209) — Allocation link (item ↔ allotment), qty/CIF
- **LicenseImportItemsModel** — Import items with available_quantity
- **AuditModel** — Base audit mixin (created_on, created_by, updated_on, updated_by)

### Services Present
- **CanonicalPlanningService** (backend/apps/license/services/canonical_planning_service.py) — Module 2 service, single source of truth for planning
- **AllocationService** (backend/apps/allotment/services/allocation_service.py) — **DEAD CODE** (not used by live endpoint)
- **AllocationService** (backend/apps/reconciliation/services/allocation_service.py) — Separate allocation service
- **plan_enforcement.py** — Plan cap validation, baseline snapshot
- **balance_calculator.py** — Live balance calculation
- Various legacy planners (e1, e5, e126, e132, a3627)

### APIs Present
- **ItemPlanViewSet** (backend/apps/license/views/item_plan.py) — Planning endpoints (bulk_upsert, auto_plan, auto_plan_all)
- **AllotmentActionViewSet** (backend/apps/allotment/views_actions.py) — **LIVE allocation endpoint** (lines 623-876, has defects F1-F10 from Module 3 audit)
- **AllotmentViewSet** (backend/apps/allotment/views.py) — CRUD endpoints

### Known Defects (From Module 3 Forensic Audit)
- **F1:** Concurrent over-allocation (select_for_update doesn't protect)
- **F2:** Intra-request over-allocation (stale @cached_property)
- **F3:** Inconsistent response (refresh doesn't clear cache)
- **F4:** Broken exception handling (bare except in @transaction.atomic)
- **F5:** Partial commit reported as success
- **F6:** No authorization scoping
- **F7:** No lower-bound validation
- **F8:** Client-supplied CIF unvalidated
- **F9:** Plan-line drawdown loses real CIF
- **F10:** Float arithmetic, silent failures

---

## CRITICAL DECISIONS FROM SPECIFICATION

### D1: Company Boundary (Blocking)
**Current state:** No company scope on allocation, no user company scope  
**Required:** Company isolation for allocation validation  
**Action:** Implement company scope on AllotmentItems, validate caller's company

### D2: CIF Validation (Blocking)
**Current state:** Client sends CIF, no validation  
**Required:** Define if CIF is authoritative input or derived  
**Spec rule:** If authoritative, validate tolerance; if derived, ignore client input  
**Action:** Implement as **derived** (qty × unit_price) to prevent F8

### D3: Allotment Approval Gate (Blocking)
**Current state:** is_approved field exists but unused  
**Required:** Should allocation check is_approved?  
**Action:** Implement as **optional gate** (can disable)

### D4: Decimal Precision (Blocking)
**Current state:** qty 3-dp, CIF 2-dp, mixed rounding  
**Required:** Align precision for ceiling/allocation  
**Action:** Standardize to ROUND_DOWN for ceilings (prevents overcommit)

---

## GAP ANALYSIS

### Missing Model Fields

**AllotmentItems needs:**
- `company` (FK to Company) — Which company receives this allocation (Req 5)
- `status` (choices: CREATED, RELEASED, COMPLETED, REACTIVATED) — Lifecycle state (Req 7)
- `released_quantity` (DecimalField) — How much has been released (Req 8)
- `release_date` (DateTimeField, null) — When released (Req 8)
- `reactivated_quantity` (DecimalField, null) — If reactivated, how much (Req 9)
- `reactivated_date` (DateTimeField, null) — When reactivated (Req 10)
- `previous_version` (FK to self, null) — Link to prior version (Req 7)
- `release_reason` (CharField, null) — User-provided reason for release (Req 7)

**AuditEvent (new) needs:**
- Detailed audit trail for combined events (Req 38, 39)
- Fields: actor, action, resource_type, resource_id, details (JSON), created_on

**Shortfall (new) needs:**
- Model to track saved shortfalls (Req 18, 20)
- Fields: allocation (FK), required_qty, allocated_qty, shortfall_qty, status, created_on

### Missing Services

1. **EligibilityService** (new)
   - Check license eligibility (expiry cutoff, license number, issue date)
   - Rule: expiry >= allowed_expiry_date is INCLUSIVE (Req 11)

2. **AutomaticPriorityService** (new)
   - Automatic license priority: expiry → issue_date → license_number (Req 22)
   - FIFO for shortfalls (Req 21)

3. **ManualAllocationService** (new)
   - Manual allocation with company selection (Req 5)
   - Live availability check at Save (Req 34)
   - Automatic reduction if availability changed (Req 31)

4. **AutomaticPlanningService** (new, extend CanonicalPlanningService)
   - Automatic planning respecting manual allocations (Req 4)
   - Shortfall creation (Req 18)

5. **ShortfallFulfillmentService** (new)
   - Auto-fulfill shortfalls from new balance (Req 20)
   - FIFO ordering (Req 21)

6. **BOEReconciliationService** (refactor)
   - Correct allocation to match BOE usage (Req 16)
   - Automatic allocation increase (Req 16)
   - Audit the correction (Req 16)

7. **ReleaseService** (refactor/new)
   - Partial releases (Req 8)
   - Reversals (Req 42)
   - Version history preservation (Req 7)
   - Reactivation (Req 9)

8. **ConcurrencyService** (new)
   - Save-time revalidation (Req 34)
   - Automatic reduction on conflict (Req 31)
   - Combined audit event (Req 38)

### Missing APIs

1. **Manual allocation endpoint** (new or refactor allocate_items)
   - Input: allotment_id, lines (item_id, qty, company)
   - Output: allocated_items, warnings, shortfall
   - Rules: live revalidation, automatic caps (Req 36)

2. **Automatic planning endpoint** (extend auto_plan)
   - Input: license_id, allowed_expiry_date (Req 11)
   - Output: suggested_allocations, shortfalls
   - Rules: manual allocation priority, automatic priority (Req 4, 22)

3. **Shortfall endpoint** (new)
   - GET: list saved shortfalls
   - Shortfalls auto-reduce as balance increases (Req 20)

4. **Release/reactivation endpoint** (new)
   - POST release: item_id, qty, reason
   - POST reactivate: previous_item_id, new_qty, new_company, reason
   - Rules: protection, version history, audit (Req 7-10, 42)

5. **Company change endpoint** (new)
   - Change allocation's company
   - Automatic cap at receiving company's limit (Req 6)
   - Audit old → new (Req 6)

### Missing Frontend Elements

- Allowed Expiry Date input (default today, editable, triggers recalc)  (Req 11-12)
- Manual company selection per allocation (Req 5)
- Suggested split display + user edit (Req 29-30)
- Automatic cap warnings (Req 3)
- Shortfall display (Req 17)
- Automatic adjustment summaries (Req 37)
- Release/reactivation forms (Req 8-10)
- Audit/history visibility (Req 43)

---

## IMPLEMENTATION PHASES

### Phase A: Domain / Backend (Models + Services)

**1. Data Model**
- Add missing fields to AllotmentItems (company, status, released_qty, etc.) — MIGRATION REQUIRED
- Create AuditEvent model (detailed event trail)
- Create Shortfall model (saved shortfalls)
- Create AllocationVersion model (version history)

**2. Services (in order)**
- EligibilityService (check license eligibility)
- AutomaticPriorityService (fixed priority + FIFO)
- ManualAllocationService (manual with company, live revalidation)
- AutomaticPlanningService (extend CanonicalPlanningService)
- ShortfallFulfillmentService (FIFO auto-fulfill)
- BOEReconciliationService (reconcile allocation to BOE usage)
- ReleaseService (release, reversal, reactivation)
- ConcurrencyService (save-time revalidation, automatic caps)

**3. Atomic Transaction Boundaries**
- Each allocation/release/reactivation must be fully atomic (Req 41)
- All balance mutations recalculated and validated before commit (Req 41)

### Phase B: API (Endpoints + Serializers)

1. **Refactor/extend allocate_items** (manual allocation)
   - Input: company selection, suggested split editable
   - Rules: F1-F10 fixes, atomicity, auto-cap, auto-reduction

2. **Extend auto_plan** (automatic planning)
   - Input: allowed_expiry_date
   - Rules: manual priority, automatic priority, shortfall creation

3. **New release endpoint**
   - Partial release, reversal, reactivation

4. **New shortfall endpoint**
   - List shortfalls, auto-fulfill as balance increases

5. **New company-change endpoint**
   - Change allocation company, auto-cap

6. **Error handling**
   - Map service exceptions to REST responses
   - Preserve error codes (backward compatible)

### Phase C: Frontend

1. Allowed Expiry Date field + recalc trigger (Req 11-12)
2. Manual company selector per line (Req 5)
3. Suggested split display + edit (Req 29-30)
4. Live availability + cap warnings (Req 3, 36)
5. Shortfall display + notifications (Req 17, 40)
6. Automatic adjustment summaries (Req 37)
7. Release/reactivation forms (Req 8-10)
8. Audit/history panel (Req 43)

---

## TEST REQUIREMENTS (Req 46)

**Unit tests:** EligibilityService, AutomaticPriorityService, ManualAllocationService  
**Integration tests:** Eligibility, manual allocation, automatic planning, BOE, lifecycle, concurrency, audit  
**Concurrency tests:** Two-user, three-user conflicts, save-time revalidation  
**Atomicity tests:** TransactionTestCase, prove no partial commits  

---

## RISK AREAS

1. **F1-F10 Fixes:** Must be implemented atomically to prevent concurrent over-allocation
2. **Concurrency:** Multiple users on same license must not corrupt balance
3. **BOE Protection:** Final BOEs must never be auto-deleted; only unused qty releases
4. **Shortfall FIFO:** Must maintain order; new balance must apply to oldest shortfall first
5. **Decimal Precision:** Consistent rounding to prevent balance creep
6. **Audit Trail:** Every change must be recorded; no silent failures
7. **Backward Compatibility:** API contracts must remain unchanged (error formats, response keys)

---

## MIGRATION STRATEGY

1. **Create migration for new fields** (company, status, released_qty, etc.)
2. **Backfill existing AllotmentItems** with company = allotment.company (preserve existing behavior)
3. **Backfill status** with CREATED (for existing rows)
4. **Test migration against production-like data**
5. **Run all tests before deploying**

---

## FILES AFFECTED

### New Files
- `backend/apps/allotment/services/eligibility_service.py`
- `backend/apps/allotment/services/automatic_priority_service.py`
- `backend/apps/allotment/services/manual_allocation_service.py`
- `backend/apps/allotment/services/shortfall_fulfillment_service.py`
- `backend/apps/allotment/services/boe_reconciliation_service.py`
- `backend/apps/allotment/services/release_service.py`
- `backend/apps/allotment/services/concurrency_service.py`
- `backend/apps/allotment/models/allocation_version.py`
- `backend/apps/allotment/models/audit_event.py`
- `backend/apps/allotment/models/shortfall.py`

### Modified Files
- `backend/apps/allotment/models.py` — Add fields to AllotmentItems
- `backend/apps/allotment/views_actions.py` — Refactor allocate_items, fix F1-F10
- `backend/apps/allotment/serializers.py` — Add company, status, versioning
- `backend/apps/license/services/canonical_planning_service.py` — Extend for automatic planning
- `backend/apps/license/views/item_plan.py` — Extend auto_plan with allowed_expiry_date
- Database migrations (new)
- Frontend (TBD — new forms, inputs, panels)

---

## KNOWN CONSTRAINTS

1. **PROTECT relationships:** Port, Company FKs use PROTECT (Req 8, 47)
2. **Nullable fields:** Some existing fields are nullable; must preserve behavior
3. **Backward compatibility:** API response formats cannot change (error codes must match)
4. **Atomicity requirement:** All balance mutations must be atomic (Req 41)
5. **No silent failures:** All balance refresh failures must be surfaced (F10 fix)

---

## CRITICAL SUCCESS FACTORS

1. ✅ Verify all tests pass before claiming completion (Req 48)
2. ✅ Show evidence (test output), not claims (Req 49)
3. ✅ Preserve Phase 4D behavior (existing correct functionality)
4. ✅ Fix F1-F10 defects atomically
5. ✅ Implement full audit trail (Req 43)
6. ✅ No silent changes to balance semantics (Req 44)

---

**Ready for Phase A implementation (domain/backend) after approval.**
