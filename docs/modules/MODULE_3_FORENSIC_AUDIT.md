# MODULE 3 FORENSIC AUDIT: Allocation/Allotment System

**Date:** 2026-08-10  
**Scope:** AllotmentAction, AllotmentItems, allocation flow, balance updates  
**Status:** Complete discovery phase (12 parallel auditors)  
**Token Usage:** 881K

---

## FORENSIC RESULTS SUMMARY

## ADVERSARIAL AUDIT: Module 3 — Allocation/Allotment System

### 1. ENTRY POINTS

**API Endpoint Chain (Primary):**
- `POST /api/allotment-actions/{id}/allocate-items/` → `AllotmentActionViewSet.allocate_items()` (views_actions.py:625)
  - Atomic transaction, transaction-scoped row locks via `select_for_update()`
  - Accepts batch of allocations in single request

- `GET /api/allotment-actions/{id}/available-licenses/` → `AllotmentActionViewSet.available_licenses()` (views_actions.py:42)
  - Two independent paths: Actual mode (line 82) vs Plan mode (line 376)
  - Returns filtered license items available for allocation

- `DELETE /api/allotment-actions/{id}/delete-item/{item_id}/` → `AllotmentActionViewSet.delete_allotment_item()` (views_actions.py:878)
  - Atomic, includes `select_for_update()` on import item

**Database Signals (Secondary):**
- `post_save` on AllotmentItems (models.py:342) → `update_stock()` → triggers `update_balance_values()` via `transaction.on_commit()`
- `post_delete` on AllotmentItems (models.py:360) → `delete_stock()` → same balance update
- `post_save` on AllotmentItems (signals.py:22) → `update_is_allotted_on_save()` → sets allotment.is_allotted = True
- `pre_delete` on AllotmentItems (signals.py:41) → `update_is_allotted_on_delete()` → risk area (line 56)

---

### 2. KEY FUNCTIONS/SERVICES

**AllocationService (backend/apps/allotment/services/allocation_service.py):**
- `calculate_max_allocation()` (line 29): Computes max qty/value with 4 constraints
  - balanced_quantity (allotment.required_quantity - allocated)
  - available_quantity on import item (live balance)
  - available CIF FC (live balance)
  - required_value_with_buffer on allotment
  - **RISK:** Returns computed max based on live balance snapshot; no lock held
- `calculate_allocation_value()` (line 94): qty × unit_price (no validation)
- `validate_allocation_amount()` (line 113): Validates qty/value against max_allocation
- `allocate_item()` (line 154): Creates AllotmentItems record (uses LicenseValidationService.validate_allocation())
- `deallocate_item()` (line 207): Deletes AllotmentItems if not converted to BOE
- `update_allocation()` (line 228): Updates qty/cif_fc on existing record

**AllotmentValidationService (backend/apps/allotment/services/validation_service.py):**
- `validate_allocation_within_limits()` (line 76): Sum of current + proposed qty/value vs allotment limits
  - Queries sum of AllotmentItems.qty / AllotmentItems.cif_fc
  - Compares to balanced_quantity / required_value_with_buffer
  - **RISK:** No transaction lock during aggregate calculation
- `check_allotment_fully_allocated()` (line 163): Current value >= required * 0.99
- `get_remaining_allocation_capacity()` (line 192): Remaining qty/value available

**View-Level Validation (views_actions.py:allocate_items):**
- Line 671: `select_for_update()` on import item (holds lock for duration of allocation)
- Line 694: Checks `available_quantity` stored column (not live computed value)
- Line 722: Checks `available_value_calculated` property (live Balance CIF computation)
- Line 733-741: Checks allotment remaining quantity (balance qty - allocated)
- Line 761-784: Plan enforcement via `plan_status_for()` — compares used + requested vs original planned qty/cif_fc

---

### 3. DATA FLOW

**Allocation Creation Flow:**
```
POST /allocate-items/ {allocations: [{item_id, qty, cif_fc, plan_line_id?}]}
  ↓
@transaction.atomic + loop through allocations:
  ├─ select_for_update() on LicenseImportItemsModel (line 671)
  ├─ validate license expiry (line 679)
  ├─ check available_quantity >= qty (line 694)
  ├─ check available_value_calculated >= cif_fc (line 722)
  ├─ check allotment.balanced_quantity >= qty (line 733)
  ├─ plan_status_for() group cap check (line 761)
  ├─ AllotmentItems.objects.filter(allotment, item).first() (line 788)
  │  ├─ if exists: qty += new_qty, cif_fc += new_cif (line 795-796)
  │  └─ if not: AllotmentItems.create() (line 802)
  ├─ [PLAN MODE] if plan_line_id: decrement LicenseItemPlan.remaining_quantity/cif_fc (line 832-844)
  └─ post_save signal triggers update_balance_values()
```

**Balance Update Flow:**
```
AllotmentItems.save() → post_save signal (models.py:342)
  ├─ transaction.on_commit(_update_balance_sync(item.id))
  └─ _update_balance_sync() calls update_balance_values(import_item)
    ├─ calculate_debited_quantity() — sum all AllotmentItems.qty for this item
    ├─ calculate_debited_value() — sum all AllotmentItems.cif_fc for this item
    ├─ calculate_available_quantity() = quantity - debited_qty
    └─ LicenseImportItemsModel.save(available_quantity, available_value)
```

**Deallocation Flow:**
```
DELETE /delete-item/{item_id}/ → AllotmentActionViewSet.delete_allotment_item()
  ├─ select_for_update() on import item (line 909)
  ├─ AllotmentItems.delete() (line 912)
  └─ post_delete signal (models.py:360) → update_balance_values()
```

---

### 4. CALCULATIONS & CONSTRAINTS

**Allotment-Level Constraints:**
- `balanced_quantity` (cached property, models.py:172): `required_quantity - SUM(allotment_details.qty)`
  - Never goes negative (clamped to 0 line 184)
  - **CRITICAL:** Cached property — may return stale value if AllotmentItems created mid-transaction

- `allotted_value` (cached property, models.py:198): `SUM(allotment_details.cif_fc)`

- `required_value_with_buffer` (views_actions.py:340): `required_value + 20`
  - Buffer is a hardcoded $20 to handle rounding issues

**License Item-Level Constraints:**
- `available_quantity`: Stored column, recomputed by update_balance_values() after each allotment change
- `available_value_calculated` (property): Live Balance CIF computation via condition_pool
  - Branches on `condition_type` (%, AU, open) for restriction pooling

**Plan Enforcement Constraints (Line Mode):**
- `LicenseItemPlan.remaining_quantity` / `remaining_cif_fc`: Independent per-line balances
  - Only decremented if `plan_line_id` provided in allocate_items request
  - **RISK:** Decrement logic does NOT validate against available_quantity — can exceed physical stock if plan line not properly initialized

**Plan Enforcement Constraints (Group Cap):**
- `plan_status_for(import_item)`: Aggregates across all LicenseItemPlan rows with same `plan_group_key`
  - Returns: original_quantity, original_cif_fc, used_quantity (live SUM of AllotmentItems), remaining
  - Enforces: (used + requested) <= original
  - **RISK:** Computed live each time; can race with concurrent allocations modifying AllotmentItems

---

### 5. RISKS & UNKNOWNS

#### **A. RACE CONDITIONS & DOUBLE ALLOCATION**

**Risk A1: Concurrent allocations exceeding plan cap** (Line 761-784)
- **Scenario:** Two concurrent requests for same import_item, both pass `plan_status_for()` check mid-race
- **Sequence:**
  1. Request A reads: used=50, original=100, requests 40 → 50+40 ≤ 100 ✓
  2. Request B reads: used=50, original=100, requests 40 → 50+40 ≤ 100 ✓
  3. Request A creates AllotmentItems, commits (used now 90)
  4. Request B creates AllotmentItems, commits (used now 130 > 100) ✗
- **Current Mitigation:** `select_for_update()` on import item (line 671) inside transaction
  - **GAP:** Lock is acquired AFTER plan_status_for() read (line 761), not before
  - **WINDOW:** Between line 671 (lock) and line 761 (plan cap check), lock is held but another read at 761 can see intermediate state if it proceeds in parallel transaction
  - **ACTUAL SAFETY:** Depends on transaction isolation level; PostgreSQL READ_COMMITTED allows this race window
- **Impact:** Over-allocation against plan cap by N × request_qty where N = concurrent requests that slip through

**Risk A2: Cached balanced_quantity returning stale value**
- **Scenario:** 
  1. Allotment.balanced_quantity reads 100 (cached)
  2. Concurrent allocation A completes, AllotmentItems.save() commits
  3. Allocation B uses cached balanced_quantity = 100 instead of fresh value (99 or less)
- **Current Mitigation:** Views_actions.py line 734 reads `allotment.required_quantity` fresh, not alloted_quantity, then computes remaining inline
  - **CODE VERIFICATION:** Lines 733-735 recompute balance correctly; do NOT trust cached balanced_quantity property
- **Impact:** Low in views_actions.py (computes fresh), but HIGH risk in serializers or other views that may use cached property blindly

**Risk A3: Double-allocation to same (allotment, item) tuple**
- **Scenario:** Two concurrent requests for same item to same allotment
- **Current Code (lines 788-809):**
  ```python
  existing = AllotmentItems.objects.filter(allotment=allotment, item=license_item).first()
  if existing:
      existing.qty += qty  # += without lock on `existing`
      existing.cif_fc += cif_fc
      existing.save()
  else:
      AllotmentItems.objects.create(...)
  ```
- **Race Window:** Between `.first()` query (line 788) and `.save()` (line 798)
  - Two concurrent threads can both see "no existing", both create → IntegrityError (unique_together violation line 248 of models.py)
  - OR if database allows, read-modify-write on += loses update from concurrent thread
- **Current Mitigation:** `select_for_update()` is on import_item (line 671), NOT on AllotmentItems check
- **Impact:** Potential duplicate AllotmentItems or lost quantity increments; IntegrityError would abort transaction

#### **B. NEGATIVE ALLOCATIONS & DATA CORRUPTION**

**Risk B1: Negative plan-line remaining_quantity**
- **Scenario:** Plan line has remaining_qty=20, request allocates 30, clamped to 0 (line 842)
  - `new_remaining_qty = max(Decimal('0'), current_remaining - qty)` correctly clamps
  - BUT: Frontend may still allow over-allocation if balance is stale
- **Impact:** Over-allocation is silently permitted, leaving auditor unable to reconcile plan cap

**Risk B2: Delete signal cascade deleting is_allotted incorrectly**
- **Scenario:** AllotmentItems deleted, but multiple items still exist on allotment
- **Code (signals.py:54-56):**
  ```python
  has_details = instance.allotment.allotment_details.exists()
  if has_details:
      instance.allotment.allotment_details.delete()  # ⚠️ DELETES ALL, not just the one
  ```
- **Bug:** When deleting a single AllotmentItems, code checks if ANY details exist, then deletes ALL of them
- **Impact:** CRITICAL data corruption — deleting one item wipes entire allotment's items
- **Status:** Appears to be latent bug in models.py:56; unclear if this code path is actually reachable or if signals.py:41 pre_delete is called instead

#### **C. STALE BALANCE COLUMNS & COMPUTED PROPERTY MISMATCHES**

**Risk C1: available_quantity stale after balance change**
- **Location:** Views_actions.py line 694 uses `license_item.available_quantity` (stored column)
- **Issue:** If balance changes between page load and allocation (e.g., another user's BOE transaction), stored column is stale
- **Current Mitigation:** Recalculated via update_balance_values() after each allocation (post_save signal)
- **Impact:** User can allocate against 100kg available but actual live balance is 50kg; allocation would succeed but asset gets over-debited
- **Safeguard:** Line 722 also checks `available_value_calculated` (live property) as secondary gate

**Risk C2: Unit price mismatch in allocation validation**
- **Scenario:** User sends qty=100, cif_fc=1000 (implies unit_price=10); stored unit_value_per_unit=12
- **Current Code:** No validation that calculated unit price matches allotment's stored unit price
- **Impact:** Allocation qty and value become misaligned; downstream financials report discrepancies

#### **D. PLAN ENFORCEMENT GAPS**

**Risk D1: Plan line without proper initialization**
- **Scenario:** Auto-plan fails to generate LicenseItemPlan for an import item, but allocate_items is called with plan_line_id pointing to non-existent line
- **Code (line 846):** Exception silently caught (`except LicenseItemPlan.DoesNotExist: pass`)
- **Impact:** Allocation succeeds, but plan-line balance not decremented; User can over-consume the plan

**Risk D2: Group cap re-aggregation races with member-line updates**
- **Scenario:** Plan has PKO+Cheese split on representative item; concurrent allocations from different plan lines
- **Code:** plan_status_for() (plan_enforcement.py) re-sums used_quantity across ALL plan lines in group every call
- **Race Window:** Between reading used_quantity aggregate and comparing to original_quantity
- **Impact:** Two allocations that individually pass cap check could together exceed it (less severe than A1 due to per-line tracking, but still possible)

#### **E. MISSING CONSTRAINTS & EDGE CASES**

**Risk E1: No validation on required_value_with_buffer initialization**
- **Code:** Line 340 hardcodes `$20` buffer
- **Issue:** What if required_value is zero or negative? No validation in AllotmentModel or views
- **Impact:** Could create negative or zero required_value_with_buffer, allowing unbounded allocation

**Risk E2: Expiry date validation only on allocate-items, not on subsequent updates**
- **Code:** Line 679 checks `license_expiry_date < today` to reject allocation
- **Gap:** update_allocation() (allocation_service.py:228) has no expiry check
- **Impact:** Can update an allocation on an already-expired license

**Risk E3: deleted AllotmentItems can still affect balance if delete signal fails**
- **Code:** delete_stock signal (models.py:360) wraps in try-except, swallows errors
- **Impact:** If update_balance_values() throws, import item's available_quantity never recomputes; subsequent allocations see stale balance

**Risk E4: AllotmentModel.required_value_with_buffer computed in view, not stored**
- **Code:** Line 340 of views_actions.py adds $20 on-the-fly
- **Gap:** If buffer value ever changes, existing serializations/reports use old value
- **Impact:** Inconsistent reporting; frontend and backend may use different buffer values

#### **F. UNKNOWNS & INSUFFICIENT INSTRUMENTATION**

**Unknown F1: Exact isolation level of database transactions**
- Assumption: PostgreSQL READ_COMMITTED (Django default)
- If SERIALIZABLE: All race windows close at cost of potential serialization failures
- If READ_UNCOMMITTED: Additional risk of dirty reads on plan_status_for()

**Unknown F2: Frequency of cached_property invalidation**
- Django cached_properties are tied to object instance lifetime
- If AllotmentModel instance is reused across requests, cached balanced_quantity could span transaction boundaries
- **Code Path:** Line 865 calls `allotment.refresh_from_db()` but does NOT reset cached_property decorator

**Unknown F3: Whether update_balance_values() is idempotent**
- Core logic in backend/apps/core/scripts/calculate_balance.py
- If called twice in rapid succession, does it produce correct result or accumulate errors?
- Test coverage does not explicitly verify idempotency

**Unknown F4: Delete cascade behavior on foreign keys**
- AllotmentItems.item has on_delete=CASCADE (models.py:212)
- AllotmentItems.allotment has on_delete=CASCADE (models.py:218)
- If a LicenseImportItemsModel is deleted, all AllotmentItems referencing it cascade-delete
- Unclear if pre_delete signals fire correctly during cascade

---

### 6. AUDIT EVIDENCE ARTIFACTS

**Test Coverage for Known Issues:**
- `test_allocate_items_plan_line_balance.py` (line 195-205): Documents stale plan_line_id gracefully ignored
- `test_allocate_items_group_plan_cap.py` (line 143-159): Verifies consolidated cap not doubled
- `test_allocate_items_cif_validation.py`: Tests stale balance rejection + live balance enforcement
- `test_allocate_items_expiry_check.py`: Tests license expiry gate on allocate-items

**Missing Test Coverage:**
- Concurrent allocations (no test for race condition A1, A3)
- Delete signal corrupting remaining items (no test for B2)
- Unit price mismatch validation (no test)
- Cached property staleness across transaction boundaries (no test)

---

### SUMMARY TABLE: Risk Severity & Remediation

| Risk ID | Category | Severity | Likelihood | Remediation | File:Line |
|---------|----------|----------|------------|-------------|-----------|
| A1 | Race condition | **CRITICAL** | Medium | Move plan_status_for() check BEFORE select_for_update() lock acquisition OR extend lock window | views_actions.py:761 |
| A3 | Double allocation | **HIGH** | Medium | Use select_for_update() on AllotmentItems.objects.select_for_update() before checking existence | views_actions.py:788 |
| B2 | Data corruption | **CRITICAL** | Low | Fix pre_delete signal: delete only the instance being deleted, not all details | signals.py:56 |
| D1 | Plan enforcement gap | **HIGH** | Low | Log DoesNotExist exception instead of silently passing; return error to user | views_actions.py:846 |
| E3 | Stale balance after delete | **MEDIUM** | Low | Re-raise exception in delete_stock signal if update_balance_values() fails | models.py:360 |
| E2 | Expiry validation gap | **MEDIUM** | Low | Add expiry check to update_allocation() method | allocation_service.py:228 |

**Concrete File Paths for Forensic Follow-Up:**
- `/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/views_actions.py` — Primary entry point; allocation logic
- `/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/models.py` — Data models; signals
- `/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/signals.py` — Post-save/delete hooks
- `/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/services/allocation_service.py` — Calculation logic
- `/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/services/validation_service.py` — Limit enforcement
- `/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/core/scripts/calculate_balance.py` — Balance recomputation
Based on my forensic analysis of the Module 3 Allocation/Allotment system, here is the security audit report:

---

## SECURITY AUDIT: Module 3 Allocation/Allotment System

### 1. ENTRY POINTS

**HTTP Endpoints:**
- `/api/allotments/` — AllotmentViewSet (CRUD via MasterViewSet)
- `/api/allotment-actions/` — AllotmentActionViewSet (bulk operations)
  - `GET .../available-licenses/` — fetch allocatable items
  - `POST .../allocate-items/` — allocate import items to allotment
  - `DELETE .../delete-item/{item_id}/` — deallocate single item
  - `GET .../generate-pdf/` — export allotment as PDF
  - `POST .../generate-transfer-letter/` — export transfer letter
  - `POST .../copy/` — duplicate allotment
  - `DELETE .../destroy/` — delete allotment

**Authentication:** JWT token (Bearer), checked via `AllotmentPermission` class

**Authorization Roles:**
- Read: `ALLOTMENT_MANAGER`, `ALLOTMENT_VIEWER`
- Write: `ALLOTMENT_MANAGER`

---

### 2. KEY FUNCTIONS / SERVICES

**Views:**
- `/backend/apps/allotment/views.py:45–331` — AllotmentViewSet (list/retrieve/create/update)
- `/backend/apps/allotment/views_actions.py:30–967` — AllotmentActionViewSet (allocation actions)

**Services:**
- `/backend/apps/allotment/services/allocation_service.py` — balance calculations (NOT called by allocate_items; see **Data Flow** below)
- `/backend/apps/allotment/services/validation_service.py` — unused

**Models:**
- `/backend/apps/allotment/models.py:46–207` — AllotmentModel (header: company, item_name, quantities, values)
- `/backend/apps/allotment/models.py:209–376` — AllotmentItems (line items: FK to license import item + allocated qty/value)

**Signals:**
- `/backend/apps/allotment/models.py:342–375` — post_save/post_delete on AllotmentItems → triggers `_update_balance_sync(item_id)` to recalculate license's available quantity

---

### 3. DATA FLOW

**Allocation Flow (POST `/api/allotment-actions/{pk}/allocate-items/`):**

```
Request body: {
  "allocations": [
    {
      "item_id": <LicenseImportItemsModel.id>,
      "qty": Decimal,
      "cif_fc": Decimal,
      "cif_inr": Decimal,
      "plan_line_id": <optional LicenseItemPlan.id>
    }
  ]
}
```

1. **Load allotment** (`views_actions.py:648`) — `get_object_or_404(AllotmentModel, pk=pk)`
   - ✓ Uses `get_object_or_404` (respects permission checks)

2. **Per-allocation validation loop** (`views_actions.py:660–851`):
   - Load license import item with `select_for_update()` (row-level DB lock for this transaction)
   - **Expiry check** (`views_actions.py:678–685`): reject if `license_expiry_date < today`
   - **Quantity sufficiency** (`views_actions.py:694–702`): compare against `license_item.available_quantity`
   - **CIF sufficiency** (`views_actions.py:722–729`): compare against `license_item.available_value_calculated` (live-computed property, not stale stored column)
   - **Allotment balance check** (`views_actions.py:731–742`): remaining = required_qty - already_allotted; reject if new qty > remaining
   - **Utilization-plan cap** (`views_actions.py:760–784`): if item has a plan, reject if (used_qty + new_qty) > original_planned_qty
   - **Create or amend** (`views_actions.py:787–809`): upsert AllotmentItems row; if exists, add to qty/cif_fc; if not, create
   - **Plan-line decrement** (`views_actions.py:832–852`): if `plan_line_id` sent (plan-mode allocation), decrement that LicenseItemPlan's own `remaining_quantity`/`remaining_cif_fc` with `select_for_update()` lock

3. **Signals** → balance recalculation triggered for the import item's license

4. **Response** returns counts of successful + failed allocations with error messages

**Deallocation Flow (DELETE `/api/allotment-actions/{pk}/delete-item/{item_id}/`):**

1. Load AllotmentItems row with `get_object_or_404(AllotmentItems, id=item_id, allotment_id=pk)` ✓
2. Lock the underlying import item with `select_for_update()` to prevent concurrent allocate_items race
3. Delete the row
4. Signals recalculate license balance

---

### 4. CALCULATIONS & CONSTRAINTS

**Available Quantity Calculation** (`LicenseImportItemsModel.available_quantity`):
- Stored column, synchronized on AllotmentItems save/delete via signal → `/backend/apps/core/scripts/calculate_balance.py:update_balance_values()`
- Formula: `original_quantity - SUM(AllotmentItems.qty WHERE item_id = this)`

**Available Value (CIF FC) Calculation** (`LicenseImportItemsModel.available_value_calculated`):
- **Live-computed property** (`license/models/...`), not stored (so never stale)
- Branches on `condition_type` (%, AU, open) via condition pooling to apply restriction percentages
- Returns: `balance_cif_fc - (restriction_pool_balance if condition_type != 'open' else 0)`

**Utilization-Plan Cap** (`plan_status_for()` in `/backend/apps/license/services/plan_enforcement.py`):
- Original = SUM(LicenseItemPlan.planned_qty WHERE import_item_id = this) — **immutable original target**
- Used = SUM(AllotmentItems.qty WHERE item_id = this) — **live from allocations**
- Remaining = Original - Used
- Enforcement at allocate time: `(Used + New) > Original` → reject with `plan_exceeded: true`

**Plan-Line Balance** (`LicenseItemPlan.remaining_quantity`/`remaining_cif_fc`):
- Separate from import item's available_quantity
- Decremented independently when `plan_line_id` is provided at allocation time
- Used only in Plan-mode available-licenses display; unrelated to Actual-mode allocations

---

### 5. RISKS & UNKNOWNS

#### **CRITICAL IDOR — destroy_allotment** 
**File:** `/backend/apps/allotment/views.py:309–330`

**Issue:**
```python
def destroy_allotment(self, request, pk=None):
    allotment = AllotmentModel.objects.get(pk=pk)  # ← NO permission checks!
    allotment.delete()
```

Uses **direct ORM query** instead of `self.get_object()`. Bypasses viewset's permission layer and any custom get_queryset filtering.

**Exploit:** User with ALLOTMENT_MANAGER role targeting another user's allotment:
```bash
DELETE /api/allotments/{arbitrary_pk}/destroy
```
Will delete ANY allotment in the system, not just those scoped to the caller.

**Impact:** Cross-user allotment deletion; data loss; audit trail circumvention.

**Fix:** Replace with `self.get_object()` to inherit permission checks.

---

#### **HIGH: No Company Isolation**

**Issue:** User model (`/backend/apps/accounts/models.py`) has NO `company` FK. Permission system is **role-only**, not multi-tenant company-scoped.

- User with ALLOTMENT_MANAGER role can read/write/delete allotments for ANY company
- No tenant boundary enforced at the ORM level
- FilterSet supports `?company=X` but is **opt-in UI filtering**, not backend enforcement

**Evidence:**
- `/backend/apps/allotment/views.py:163–228` — get_queryset applies default filters (is_boe, type, is_allotted) but **never scopes by company**
- `/backend/apps/allotment/views_export.py:59–75` — download_grouped_export calls `self.filter_queryset(self.get_queryset())` and exports **all companies in one report**, no company-level isolation
- `/backend/apps/allotment/views_actions.py:42–73` — available_licenses endpoint queries all import items with `available_quantity > 0` globally; no per-company filter

**Impact:** 
- User from Company A can see/allocate/export allotments for Companies B, C, D
- Bulk exports (PDF/XLSX) leak competitor/sensitive company data
- No audit separation between users of different organizations

**Mitigation Required:**
1. Add user.company FK (or user.company_set M2M for multi-company access)
2. Scope all querysets in AllotmentViewSet/AllotmentActionViewSet to `filter(company__in=user.companies)` at the ORM level
3. Audit all bulk operations (copy, destroy, export) to enforce company boundary

---

#### **HIGH: Bulk Allocation Race Condition Window (Mitigated but Document)**

**File:** `/backend/apps/allotment/views_actions.py:667–852`

**Context:** `@transaction.atomic` + `select_for_update()` on import item locks prevent the following race:
- Thread A reads plan cap as {used: 100, original: 150, remaining: 50}
- Thread B allocates 30 (new used: 130, remaining: 20)
- Thread A allocates 40 (would exceed, but A saw stale remaining: 50)

**Mitigation:** `select_for_update()` on `LicenseImportItemsModel` re-fetches at allocation time, so both threads serialize. ✓

**Unknown Risk:** What if `LicenseItemPlan` is concurrently regenerated (Auto-Plan re-runs) between page load and Confirm?
- `plan_line_id` becomes stale reference (`LicenseItemPlan.DoesNotExist` caught at line 846)
- Allocation still succeeds (line 849 comment: "the real allotment above already succeeded")
- Plan-line balance not decremented, but import item's overall available_qty **is** reduced
- **Next allocate-items call on a sibling plan line MAY exceed the (now-incorrect) cap**

**Example:**
- License item split into: PKO (50 units) + Cheese (50 units) — both plan lines
- User allocates 30 PKO (stale plan_line_id for Cheese after Auto-Plan regen)
- Cheese plan line still shows 50 available (plan not decremented), but import item only has 20 left
- Next allocation of 40 Cheese fails, but user sees "Plan cap 50" in error, suspects UI bug

**Fix:** Return `plan_line_id_stale: true` in error response; frontend should trigger a refetch of available-licenses.

---

#### **MEDIUM: `available_quantity` Staleness on Concurrent Allocations**

**File:** `/backend/apps/allotment/views_actions.py:694`

**Context:** Check uses `license_item.available_quantity` (stored column), which is updated via post_save signal. Between two rapid POST requests:
- Request A: reads available_qty = 100, passes check, queues update_balance_sync
- Request B: reads available_qty = 100 (signal hasn't fired yet), also passes check
- Both allocate 80, over-allocate by 60

**Mitigation:** `select_for_update()` re-fetches the row at the start of the loop, **but does NOT re-fetch available_quantity**. Signal-based update is asynchronous if using Celery, or synchronous if using `transaction.on_commit()` (line 354, current code).

**Current Code** (line 354): Uses `transaction.on_commit()` → synchronous, fires at end of transaction commit. ✓ Safe for same-request (but not same-transaction if two allocations in one POST body)

**Risk:** Two allocations in one POST body against the same import item:
```json
{
  "allocations": [
    {"item_id": 123, "qty": 80},
    {"item_id": 123, "qty": 80}
  ]
}
```
- First loop iteration: available_qty = 100, pass, creates AllotmentItems
- Second loop iteration: available_qty still = 100 (not re-fetched), pass, adds to same AllotmentItems
- Result: 160 allocated against 100 available (no signal fired until transaction ends)

**Fix:** Maintain in-memory `allocated_this_transaction` map per item_id; check against live `available_qty - allocated_this_transaction`.

---

#### **MEDIUM: Plan-Mode Serialization — import_item_id vs plan.id Mismatch**

**File:** `/backend/apps/allotment/views_actions.py:592–612`

**Context:** Plan-mode response overlays plan fields on import-item serializer:
```python
row['id'] = plan.id                    # Plan line ID (for React key)
row['import_item_id'] = plan.import_item_id  # Real import item
```

**Risk:** Frontend **must** send back `import_item_id` (not `id`) in allocate-items request. If it sends `id` (plan line ID), `allocate_items` treats it as `LicenseImportItemsModel.id` and queries the wrong row.

**Evidence:**
- `allocate_items` line 671: `license_item = LicenseImportItemsModel.objects.select_for_update().get(id=item_id)`
- No validation that `item_id` is **not** a LicenseItemPlan ID
- Could silently fetch a wrong import item, or 404 if plan ID > highest import item ID

**Fix:** Add comment in API docs clarifying `item_id` must be `LicenseImportItemsModel.id`, not plan line ID. Frontend already sends `import_item_id` correctly (line 605), so low practical risk if frontend doesn't deviate.

---

#### **LOW: available_value_calculated Property Not Cached**

**File:** `/backend/apps/allotment/views_actions.py:722`

**Context:** Bulk allocation loop checks `license_item.available_value_calculated` for each import item. Property is live-computed (not stored), so:
- 10 allocations on same item: property re-computed 10 times in the loop
- 100-item page with 30% overlap: 30+ redundant balance-CIF aggregations

**Mitigation:** Line 312-313 batches `available_value_bulk_map()` for the paginated list in available-licenses endpoint, but not in allocate_items loop.

**Fix:** Cache `available_cif` after first check; avoid re-computation if qty check already passed.

---

#### **UNKNOWN: CIF INR Precision in Exports**

**File:** `/backend/apps/allotment/views_export.py:257, 493`

**Risk:** CIF INR calculated in export loop:
```python
allot_cif_inr = allot['value'] * allot.get('exchange_rate', DEFAULT_EXCHANGE_RATE)
```
- No rounding applied (differs from model's `ROUND_HALF_UP`)
- Summed across many allotments (order-of-summation floating-point rounding)
- PDF/XLSX may show different totals than UI/DB

**Fix:** Match Decimal rounding to `AllotmentModel.save()` logic (ROUND_HALF_UP, 2 places).

---

#### **UNKNOWN: Null Item FK on AllotmentItems**

**File:** `/backend/apps/allotment/models.py:209–215`

**Context:**
```python
item = models.ForeignKey(
    "license.LicenseImportItemsModel",
    null=True, blank=True,  # ← Nullable!
)
```

**Risk:** AllotmentItems.item can be NULL (e.g., after cascade deletes, or manual nulling). Then:
- `/backend/apps/allotment/models.py:257–260` — _license property returns None
- Export loops (`views_export.py:671–681`) try to access `detail.item.license` → AttributeError if item is None
- Serializer may fail

**Question:** Why is item nullable? Should it be PROTECT or CASCADE?

---

#### **INFORMATIONAL: JSON Number Precision in API Responses**

**File:** `/backend/apps/allotment/views_actions.py:815–817`

**Context:** Allocation response returns Decimals as strings:
```python
'qty': str(qty),
'cif_fc': str(cif_fc),
```

**Best Practice:** ✓ Strings preserve Decimal precision in JSON (JSON number type loses precision for large Decimals).

---

### SUMMARY TABLE

| Risk | Severity | File | Line(s) | Category |
|------|----------|------|---------|----------|
| destroy_allotment uses .get() not .get_object() | CRITICAL | views.py | 315 | IDOR |
| No company-level isolation | HIGH | views*.py | Multiple | Authorization |
| Plan-line stale reference during Auto-Plan regen | HIGH | views_actions.py | 846 | Race Condition |
| Two allocations in one request: qty not re-fetched | MEDIUM | views_actions.py | 694 | Race Condition |
| Plan-mode: id vs import_item_id confusion | MEDIUM | views_actions.py | 671 | API Contract |
| available_value_calculated recomputed in loop | LOW | views_actions.py | 722 | Performance |
| CIF INR rounding in exports | LOW | views_export.py | 257, 493 | Precision |
| AllotmentItems.item nullable (cascades possible) | INFORMATIONAL | models.py | 210 | Data Integrity |

---

**Recommendation:** Fix CRITICAL IDOR immediately (1-line change). Prioritize company isolation design for multi-tenant deployments. Document plan-line staleness behavior for frontend teams.

/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/views.py (destroy IDOR)
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/views_actions.py (bulk allocation race, plan-line staleness)
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/models.py (data model, nullable item FK)
Now let me compile the comprehensive forensic discovery audit. I have enough information to provide a concrete analysis.

## QA Auditor Forensic Discovery: Module 3 Allocation/Allotment System

### 1. ENTRY POINTS

**Primary Endpoint:**
- **Route:** `/api/allotment-actions/{allotment_id}/allocate-items/`
- **File:** `/backend/apps/allotment/views_actions.py` (lines 623-876)
- **Method:** `AllotmentActionViewSet.allocate_items()`
- **HTTP:** POST
- **Auth:** `AllotmentPermission`
- **Request Body:**
  ```json
  {
    "allocations": [
      {
        "item_id": <int>,
        "qty": <decimal string>,
        "cif_fc": <decimal string>,
        "cif_inr": <decimal string>,
        "plan_line_id": <int optional>
      }
    ]
  }
  ```

**Related Endpoints:**
- `GET /api/allotment-actions/{allotment_id}/available-licenses/` — filters available items for allocation (lines 42-621)
- `DELETE /api/allotment-actions/{allotment_id}/delete-item/{item_id}/` — deallocate (lines 878-923)

---

### 2. KEY FUNCTIONS/SERVICES

#### A. **AllocationService** (`backend/apps/allotment/services/allocation_service.py`)

| Function | Line | Purpose | Returns |
|----------|------|---------|---------|
| `calculate_max_allocation()` | 29 | Compute qty/value limits considering 4 constraints | `{max_quantity, max_value}` |
| `calculate_allocation_value()` | 94 | qty × unit_price | Decimal |
| `validate_allocation_amount()` | 113 | Check qty/value within max limits | `(bool, str)` |
| `allocate_item()` | 154 | Create AllotmentItems row (atomic) | AllotmentItems |
| `deallocate_item()` | 207 | Delete AllotmentItems if not BOE | None |
| `update_allocation()` | 228 | Modify existing AllotmentItems | AllotmentItems |
| `get_allocation_summary()` | 278 | Aggregate stats for allotment | `{total_items, total_quantity, total_value, ...}` |

#### B. **AllotmentValidationService** (`backend/apps/allotment/services/validation_service.py`)

| Function | Line | Purpose | Returns |
|----------|------|---------|---------|
| `validate_allotment_complete()` | 20 | Check required fields present | `(bool, [missing_fields])` |
| `validate_can_allocate()` | 50 | Pre-allocation gate (not BOE, not negative balance) | `(bool, str)` |
| `validate_allocation_within_limits()` | 76 | Check qty/value don't exceed allotment balance | `(bool, str)` |
| `validate_unit_price_matches()` | 128 | Verify calculated unit price matches expected | `(bool, str)` |
| `check_allotment_fully_allocated()` | 163 | Check if ≥99% of required_value allocated | bool |
| `get_remaining_allocation_capacity()` | 192 | Compute remaining qty/value headroom | `{remaining_quantity, remaining_value, ...}` |

#### C. **LicenseValidationService** (called from allocation_service.py line 183)

- `validate_allocation()` — comprehensive multi-stage check: license active, sufficient balance/quantity, restriction limits

#### D. **Plan Enforcement** (`backend/apps/license/services/plan_enforcement.py`)

- `plan_status_for(item)` (line 243) — returns `{original_quantity, original_cif_fc, used_quantity, used_cif_fc, remaining_quantity, remaining_cif_fc}` or None if unconstrained
- Used by allocate_items (line 761) to enforce utilization cap

---

### 3. DATA FLOW

```
POST /allocate-items
  ↓
Request body validation (allocations array)
  ↓
For each allocation:
  ├─ Fetch LicenseImportItemsModel (select_for_update lock)
  │  
  ├─ VALIDATION CHAIN (sequential, first failure returns error):
  │  ├─1. License Expiry Check (line 679)
  │  │   • license_expiry_date < today() → REJECT
  │  │
  │  ├─2. Available Quantity Check (line 697)
  │  │   • actual_available_qty < qty → REJECT
  │  │
  │  ├─3. Available CIF FC Check (line 722)
  │  │   • available_value_calculated < cif_fc → REJECT (uses live computed balance, not cached)
  │  │
  │  ├─4. Allotment Balance Quantity Check (line 735)
  │  │   • (required_qty - current_allotted) < qty → REJECT
  │  │
  │  └─5. Utilization Plan Cap Check (line 761)
  │      • plan_status_for(item) → check if proposed (used + qty) exceeds original
  │      • If plan exists and exceeded → return plan_exceeded error
  │
  ├─ Check for duplicate AllotmentItems (line 788)
  │  ├─ Exists: Update qty/cif_fc/cif_inr += new amounts
  │  └─ New: Create AllotmentItems row
  │
  ├─ Plan-line balance decrement (line 832)
  │  • If plan_line_id provided (Plan mode):
  │    - Lock LicenseItemPlan row
  │    - Decrement remaining_quantity -= qty
  │    - Recalculate remaining_cif_fc = remaining_qty × unit_price
  │    - Handle stale plan_line_id gracefully (allocation succeeds anyway)
  │
  └─ Signal chain triggered on save:
     ├─ update_is_allotted_on_save (signals.py line 22)
     │  ├─ Set allotment.is_allotted = True
     │  └─ Call update_license_balance(item)
     │
     ├─ update_balance_values (calculate_balance.py)
     │  └─ Recompute available_quantity/available_value_calculated
     │
     └─ Materialized view refresh (signals_materialized_views.py)
        └─ refresh_license_related_views, etc.

Response: HTTP 201/400 with {success, created_items[], errors[]}
```

---

### 4. CALCULATIONS & CONSTRAINTS

#### A. **Constraint Stack (allocate_items, lines 679-784)**

| # | Constraint | Source | Enforced At | Severity |
|---|-----------|--------|-------------|----------|
| 1 | License not expired | `license_expiry_date < today()` | Line 680 | HARD FAIL |
| 2 | Available quantity sufficient | `LicenseImportItemsModel.available_quantity >= qty` | Line 697 | HARD FAIL |
| 3 | Available CIF FC sufficient | `available_value_calculated >= cif_fc` | Line 722 | HARD FAIL |
| 4 | Allotment balance not exceeded | `allotment.balanced_quantity >= qty` | Line 735 | HARD FAIL |
| 5 | Utilization plan cap (if plan exists) | `plan_status_for(item).used + qty ≤ original` | Line 763 | HARD FAIL (plan_exceeded flag) |
| 6 | Unit price tolerance match (validation_service only) | `|calculated_unit_price - expected| ≤ 0.01` | Line 154 | Not currently used in allocate_items |

#### B. **Max Allocation Calculation** (AllocationService.calculate_max_allocation, line 29-91)

```python
unit_price = allotment.unit_value_per_unit

constraints = [
    balanced_qty,                    # AllotmentModel.balanced_quantity
    available_qty,                   # ItemBalanceCalculator.calculate_available_quantity(import_item)
    balance_cif_fc / unit_price,     # ItemBalanceCalculator.calculate_item_balance(import_item) ÷ price
    balanced_value_with_buffer / unit_price  # (required_value_with_buffer - allotted_value) ÷ price
]

max_qty = min(constraints)
max_value = max_qty × unit_price
```

#### C. **Balanced Quantity** (AllotmentModel, line 172-184)

```python
balanced_quantity = required_quantity - SUM(allotment_details.qty)
# Never goes negative; returns 0 if fully allocated
```

#### D. **Allotted Value** (AllotmentModel, line 198-206)

```python
allotted_value = SUM(allotment_details.cif_fc)
# Tracks total financial value allocated
```

#### E. **Plan Status** (plan_enforcement.plan_status_for, line 243-275)

```
original_quantity = SUM(LicenseItemPlan.planned_quantity WHERE plan_group_key matches)
original_cif_fc = SUM(LicenseItemPlan.planned_cif_fc)

used_quantity = (current_all_time_allotted - baseline_snapshot) for group
used_cif_fc = (current_all_time_value - baseline_snapshot) for group

remaining_quantity = original - used
remaining_cif_fc = original - used

Returns None if no LicenseItemPlan rows exist (unconstrained)
```

---

### 5. RISKS & UNKNOWNS

#### **CRITICAL ISSUES (Production Defects Fixed)**

1. **Stale CIF Balance Bug** (test_allocate_items_cif_validation.py)
   - **Risk:** Old code trusted `available_value` (cached column) whenever non-zero, ignoring stale `is_restricted` flag
   - **Evidence:** License item 33740: is_restricted=True, available_value=7.43 (stale), but live available_value_calculated=154802.90
   - **Fix Applied:** Line 722 uses `available_value_calculated` (live, computed per condition_type), bypasses is_restricted branch entirely
   - **Status:** ✅ Fixed (line 704-721 comments document this)

2. **License Expiry Not Checked** (test_allocate_items_expiry_check.py)
   - **Risk:** No expiry gate before allocation; expired licenses with positive balance could still be allocated
   - **Evidence:** License with license_expiry_date in past but available_quantity/value still positive (balances not zeroed on expiry)
   - **Fix Applied:** Line 680 checks `license_expiry_date < today()` (same comparison used by license_status filters)
   - **Status:** ✅ Fixed

3. **Group Plan Cap Double-Counting** (test_allocate_items_group_plan_cap.py)
   - **Risk:** E126/E132 reserialized items (sibling rows with same product, different serial numbers) could have legacy split on original + independent split on new siblings; plan_status_for would sum BOTH, doubling the enforced cap
   - **Evidence:** Fixture: representative with PKO 40 / Cheese 60 split; siblings get fresh independent splits → total cap enforced = 2× intended
   - **Fix Applied:** Auto-plan now groups by `plan_group_key` (HSN + description), consolidates entire group's plan onto representative (lowest serial)
   - **Status:** ✅ Fixed (e126_auto_plan.py, e132_auto_plan.py now group-aware)

4. **E1 Group Bypass** (test_allocate_items_e1_group_plan_cap.py)
   - **Risk:** E1 auto-plan grouped only by description (narrower than HSN-aware plan_group_key); two items same description, different HS codes could pool in plan but not in enforcement → one member left unconstrained
   - **Evidence:** License 0311045101: two items "Other Confectionery Ingredients" with HSN 08021100 vs 08029000; old code pooled into one plan, enforcement found zero plan for second item
   - **Fix Applied:** E1 now uses canonical `plan_group_key` (plan_grouping.merge_items_for_classification)
   - **Status:** ✅ Fixed (e1_auto_plan.py now uses plan_grouping)

#### **OPERATIONAL RISKS (Still Live)**

5. **Concurrent Allocation Race Condition**
   - **Scope:** Two simultaneous allocate_items calls on same import item
   - **Mechanism:** Both calls read plan_status_for, both see remaining=100; both create allocations totaling 120 → exceeds cap
   - **Mitigation:** select_for_update() locks on import item (line 671), plan_line (line 836), prevents interleave
   - **Gap:** Lock covers the import item, but plan-cap check (line 761) reads LicenseItemPlan rows WITHOUT lock → two transactions can both read, both check, both pass (plan line not locked until line 836, only for decrement, not for read)
   - **Status:** ⚠️ PARTIAL—plan_status_for aggregates live (no stale reads), but aggregate itself isn't isolated from concurrent writes

6. **Stale Plan Line ID Handling** (test_allocate_items_plan_line_balance.py)
   - **Scenario:** Plan-mode grid sends plan_line_id; auto-plan regenerates lines between page load and submit; old plan_line_id no longer exists
   - **Current Behavior:** Allocation succeeds (line 846 catches DoesNotExist, passes silently); no plan line decrement happens
   - **Risk:** If allotments continue against stale plan IDs, remaining_quantity never decreases → may allow overcap allocations from next request
   - **Status:** ⚠️ ACCEPTED (documented line 847-850; allocation intentionally succeeds; frontend must refresh on auto-plan changes)

7. **Duplicate Allocation Upsert Logic** (line 788-799)
   - **Behavior:** If AllotmentItems already exists for (allotment, import_item), UPDATE by adding qty/cif_fc/cif_inr
   - **Risk:** unique_together constraint on (item, allotment) (models.py line 248) allows only ONE row per pair; subsequent allocations always upsert into same row
   - **Implication:** Cannot track separate allocation "events"; all history collapses into one row's cumulative totals
   - **Status:** 🟡 DESIGN—this is intentional (unique_together enforces it), but limits audit trail

8. **Materialized View Refresh Lag**
   - **Trigger:** Signal chain on AllotmentItems save (signals.py line 22) → update_license_balance → calculate_balance.py → refresh materialized views
   - **Risk:** Views (e.g., license_balance_ledger) may lag behind real allocation by milliseconds
   - **Mitigation:** Views are refreshed synchronously (not async Celery task per signals.py), but refresh happens AFTER transaction commit
   - **Status:** 🟡 ACCEPTABLE (synchronous, on-commit refresh)

9. **Available Value Calculation Complexity** (condition_pool.available_value_calculated)
   - **Mechanism:** Computed property branches on condition_type (%/AU/open) to apply restriction pooling
   - **Calls:** Line 722 in allocate_items, also used by "available licenses" filter, Item Plan UI
   - **Risk:** Multiple code paths read this; if pool logic is wrong, allocation + UI can diverge silently
   - **Status:** ⚠️ HIGH—condition_pool.py is CRITICAL PATH, no redundancy

10. **No Allocation Reversal on Validation Failure**
    - **Scenario:** Allocate call fails after plan_line decrement (if plan_line_id was valid)
    - **Current:** Line 832-851 decrements plan line AFTER AllotmentItems created (line 802-809); if decrement fails, AllotmentItems persists
    - **Risk:** AllotmentItems row exists but plan line not decremented → plan_status_for counts allocation against old plan line, next allocation sees wrong Remaining
    - **Status:** ⚠️ GAP—no try-catch around entire allocation; if plan line decrement throws, partial state committed

#### **TEST COVERAGE ASSESSMENT**

| Test File | Edge Cases Covered | Gaps |
|-----------|-------------------|------|
| test_allocate_items_cif_validation.py | Stale balance, is_restricted flag, boundary cases | Zero balance, negative balance |
| test_allocate_items_expiry_check.py | Expiry date boundaries (today, yesterday, tomorrow, null), condition types | Expiry during transaction window |
| test_allocate_items_group_plan_cap.py | Group consolidation, double-counting fix, sibling independence | Concurrent re-planning |
| test_allocate_items_e1_group_plan_cap.py | Different HS codes same description, independent caps | >2 siblings |
| test_allocate_items_plan_line_balance.py | Per-line balance decrement, stale plan_line_id, missing plan_line_id | Plan line value mismatch (unit_price change) |
| test_available_licenses_filters.py | Quantity/value filters, plan mode rows, split visibility | Filter combinations (e.g., qty + value simultaneously) |

#### **UNKNOWNS REQUIRING INVESTIGATION**

1. **Condition Type Pool Calculation** — condition_pool.available_value_calculated logic under %, AU, open conditions
2. **Exchange Rate Application** — cif_inr calculation (line 664) accepted but never validated against allotment exchange_rate
3. **Materialized View Freshness** — how often do license_balance_ledger views refresh? Any stale reads in parallel queries?
4. **Auto-Plan Trigger Timing** — when exactly does auto-plan regenerate? Can it fire between plan_status_for read (line 761) and AllotmentItems create (line 802)?
5. **Balance Signals Order** — post_save (line 22) calls update_license_balance; does this run BEFORE or AFTER subsequent queries in same transaction see the balance?

---

### 6. EXECUTION SUMMARY

**Entry Point:** POST `/api/allotment-actions/{allotment_id}/allocate-items/` (views_actions.py:623)
**Atomic Transaction:** Yes (@transaction.atomic, line 624)
**Lock Strategy:** select_for_update() on import item (line 671) + optional plan_line (line 836)
**Validation Gates:** 5 sequential hard-fail checks (expiry → qty → CIF → balance → plan cap)
**Success Rate:** HTTP 201 with partial success possible (some allocations succeed, others error per allocation)
**Signal Cascade:** AllotmentItems save → update_is_allotted → update_license_balance → condition_pool refresh → materialized view refresh

**Files Modified on Execution:**
- AllotmentItems (create/update)
- AllotmentModel.is_allotted (set to True)
- LicenseImportItemsModel.available_quantity (decremented by signal)
- LicenseItemPlan.remaining_quantity/remaining_cif_fc (if plan_line_id provided)

/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/views_actions.py
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/services/allocation_service.py
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/services/validation_service.py
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/models.py
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/allotment/signals.py
/Users/drushahardiksottany/PycharmProjects/license-manager/backend/apps/license/services/plan_enforcement.py
Based on my audit of the Module 3 Allocation/Allotment system, here are the concrete performance findings:

---

## Module 3 Allocation/Allotment System — Performance Audit

### 1. ENTRY POINTS

**Primary API endpoints:**
- `GET /allotments/{pk}/available-licenses` (line 42-374 in `views_actions.py`)
- `POST /allotments/{pk}/allocate-items` (line 623-876 in `views_actions.py`)  
- `DELETE /allotments/{pk}/delete-item/{item_id}` (line 878-923 in `views_actions.py`)
- `GET /allotments/{pk}/available-licenses?debit_based_on=plan` (line 376-621, plan-mode variant)

**Serializers:**
- `LicenseImportItemSerializer` with context-injected bulk maps (line 326-334)
- `AllotmentSerializer` (line 335, 588, 869)

---

### 2. KEY FUNCTIONS/SERVICES

**Allocation Logic:**
- `AllocationService.calculate_max_allocation()` (line 29-91, `allocation_service.py`) — calls into `ItemBalanceCalculator.calculate_item_balance()` & `calculate_available_quantity()`, which delegate to condition pools
- `AllocationService.allocate_item()` (line 154-203) — wraps `LicenseValidationService.validate_allocation()`
- `validate_can_allocate()` (line 50-73, `validation_service.py`)
- `get_remaining_allocation_capacity()` (line 192-231, `validation_service.py`)

**Query Optimization Functions (Critical — prevent N+1):**
- `available_value_bulk_map(candidates)` (line 279, 312, imported from `condition_pool.py`) — **ONE query per license group**, not per item
- `plan_status_for_items(paginated_items)` (line 354-365, `views_actions.py`) — **ONE query per license**, aggregates all groups, returns `{item_id: dict|None}` map
- `billed_no_boe_bulk_map(page_item_ids)` (line 323, imported from `item_usage.py`)
- `plan_map_for_import_items(page_item_ids)` (line 321, imported from `plan_reporting.py`)

**Plan Enforcement (concurrent-allocation protection):**
- `plan_status_for_items()` (line 278-385 in `plan_enforcement.py`) — 5-6 fixed queries for ANY page size:
  - 1 query: all siblings across all licenses on the page
  - 1 query: LicenseItemPlan rows for those siblings' groups
  - 1 query: AllotmentItems aggregates by item (with `_ALLOTTED_FILTER` for AT-type only)
  - Result reused in both "available-licenses" response AND allocate-time plan-cap check

**Condition Pool Calculation (for %-restrictions):**
- `compute_condition_pools(license_obj)` (line 46-128, `condition_pool.py`) — **~13 queries per license**: 1 distinct-conditions query + 3 SUM queries per group (BOE debit / Allotment / Trade)
- `compute_condition_pools_bulk(license_ids)` (line 131-238) — **batched for many licenses**: ~5 queries regardless of count (1 distinct-groups query + 4 aggregation queries over all licenses' items)
  - Used in Item Pivot Report (not in allocate flow, but same infrastructure)
- Called from `available_value_calculated` property via `_resolve_available_value()` → `available_value_bulk_map()` (line 250+, `condition_pool.py`)

---

### 3. DATA FLOW

**available_licenses (Actual Mode):**
```
GET /allotments/{pk}/available-licenses
├─ Load allotment (line 73-74)
├─ Build base queryset (line 109-122): select_related(license, exporter, hs_code) + prefetch_related(items, export_license)
├─ Apply 15+ optional filters in sequence (line 125-241)
│  └─ NOTE: many use .distinct() (line 151, 162, 246) after M2M/FK joins
├─ Paginate: slice queryset, then .count() (line 291-303)
├─ ONE CALL: available_value_bulk_map(paginated_items) — line 313
│  └─ Batches live available-value computation across all items' licenses
├─ ONE CALL: plan_map_for_import_items(page_item_ids) — line 321
│  └─ Batches plan status across all items' groups
├─ ONE CALL: billed_no_boe_bulk_map(page_item_ids) — line 323
│  └─ Batches trade-line usage lookup
├─ Serialize items with context={'available_value_map': ...} (line 326-334)
├─ ONE CALL: plan_status_for_items(paginated_items) — line 355
│  └─ Recomputed (already in plan_map, but needed to extract individual plan status for the row extra fields)
└─ Return paginated response (line 367-374)
```

**allocate_items (concurrent-allocation guard):**
```
POST /allotments/{pk}/allocate-items + @transaction.atomic
├─ For each allocation in request (line 660-852):
│  ├─ .select_for_update() on LicenseImportItemsModel — LOCK row (line 671)
│  ├─ Check license expiry (line 680)
│  ├─ Check available_quantity (stored field, line 694)
│  ├─ Check available CIF (live via available_value_calculated, line 722)
│  ├─ Check remaining balance quantity (line 737)
│  ├─ Check plan cap: plan_status_for(license_item) (line 761)
│  │  └─ 1 query per item (but within transaction atomic block)
