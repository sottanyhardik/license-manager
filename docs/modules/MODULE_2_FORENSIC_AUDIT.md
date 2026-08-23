# MODULE 2 FORENSIC AUDIT: Planning System

**Date:** 2026-08-10  
**Audit Scope:** Query efficiency, N+1 detection, caching, large dataset behavior  
**Status:** Complete discovery phase

---

## 1. ENTRY POINTS

### 1.1 REST API Endpoints

All planning APIs are mounted under `/api/license-item-plans/` and `/api/` (backend/apps/license/views/item_plan.py).

| Endpoint | Method | Path | Handler | Purpose |
|----------|--------|------|---------|---------|
| List plans | GET | `/api/license-item-plans/?license=<id>` | `LicenseItemPlanViewSet` (line 99) | Fetch all plan lines for a license |
| Create plan | POST | `/api/license-item-plans/` | `perform_create()` (line 111) | Create single plan line with validation |
| Update plan | PATCH | `/api/license-item-plans/<id>/` | `perform_update()` (line 119) | Modify existing plan line |
| Delete plan | DELETE | `/api/license-item-plans/<id>/` | (ModelViewSet default) | Remove plan line |
| Norm prefill | GET | `/api/license-item-plans/norm-prefill?license=<id>` | `norm_prefill()` (line 128) | Pre-fill form with norm-computed values |
| Bulk upsert | POST | `/api/license-item-plans/bulk-upsert` | `bulk_upsert()` (line 152) | Full-replace: delete all, insert many (with validation) |
| E1 auto-plan | POST | `/api/license-item-plans/e1-auto-plan` | `e1_auto_plan()` (line 294) | Compute E1 (confectionery) plan, save atomically |
| Auto-plan unified | POST | `/api/license-item-plans/auto-plan` | `auto_plan()` (line 375) | Dispatch to E1/E5/E126/E132/A3627 planner by norm |
| Auto-plan all | POST | `/api/license-item-plans/auto-plan-all` | `auto_plan_all()` (line 456) | Batch: plan ALL eligible DFIA licenses |

**Filters:** DjangoFilterBackend on `license`, `import_item` (line 108-109).

---

### 1.2 Management Command

**File:** `backend/apps/license/management/commands/plan_norms.py`

```bash
python manage.py plan_norms E1 [--license <number>] [--all] [--force] [--dry-run]
```

- **Arguments:** Norm class (E1, E5, E126, E132, or registered custom)
- **Options:**
  - `--license`: Target one license number
  - `--all`: Re-plan even fully-planned (default: skip ≥99% planned)
  - `--force`: Override `--all` fallback (deprecated alias)
  - `--dry-run`: Compute but don't commit

**Flow:** Filters licenses by norm → Checks "fully planned" threshold → Calls `PlannerFactory.run()` → `save_plan_lines_for_license()` (line 68-69)

---

### 1.3 Celery / Background Jobs

**Current Status:** No dedicated Celery job discovered. Batch operations (`auto-plan-all`, `plan_norms`) execute synchronously within HTTP request or management command context.

---

### 1.4 Signals / Hooks

**LicenseItemPlan.save()** (line 1279-1283):
- Denormalizes `license_id` from `import_item.license_id` on create (one-time, not validated/re-checked on updates)

**Allotment signals** (apps/allotment/models.py):
- `update_stock` (on_commit hook): Refreshes `LicenseImportItemsModel.{allotted_quantity, allotted_value}` — denormalized cache
- Plan enforcement reads LIVE `AllotmentItems` aggregates, NOT these cached columns (see plan_enforcement.py line 24-27)

---

## 2. DATA FLOW

### 2.1 Input Sources

**Import Items** (backend/apps/license/models/core.py):
- Table: `LicenseImportItemsModel`
- Key columns: `available_quantity`, `available_value`, `quantity` (original import qty)
- Related: `hs_code` (HSN classification), `items` (M2M to `ItemNameModel`)

**License Context**:
- Table: `LicenseDetailsModel`
- Key columns: `license_expiry_date`, `balance_cif` (denormalized cache), `get_balance_cif` (live property, computed via `LicenseBalanceCalculator`)
- Related: `export_license__norm_class` (E1/E5/E126/E132/A3627 identifier)

**Norm Detection** (services/norm_plan.py, line 23-42):
```python
def detect_norm(license_obj) -> str:
    # Reads export_license.norm_class (first export record)
    # Returns 'E1' | 'E5' | 'E126' | 'E132' | 'A3627' | ''
```

---

### 2.2 Processing Layers

#### Layer 1: Classification (Per-Item)

Each auto-plan engine classifies import items into categories/buckets. Example: E1 (line 88-154 in e1_plan.py):

```python
def classify_e1_item(item_key, hs_code, description) -> str | None:
    # Returns one of: 'OTHER CONFECTIONERY INGREDIENTS', 'COCOA MASS', 
    # 'MILK PRODUCTS', 'EGG ALBUMIN', 'FRUIT JUICE', 'TARTARIC ACID', 
    # 'ALUMINIUM FOIL', 'POLYPROPYLENE', or None
```

**Evidence:** Services:
- `e1_plan.py:88-154` — E1 classification by HSN/description/item-names
- `e5_plan.py` — E5 classification
- `e132_plan.py` — E132 deterministic per-item (Nuts/Yeast/PKO/RBD/Cheese/Aluminium)
- `e126_plan.py` — E126 deterministic (Nuts/PKO/Olive Oil)
- `a3627_auto_plan.py:_matched_ids_by_category()` — A3627 via `item_matcher.get_item_filters()` re-use

#### Layer 2: Grouping (By Plan Group Key)

After classification, items are GROUPED by `(HSN, normalized_description)` — the canonical grouping used everywhere (plan_grouping.py, line 73-85):

```python
def plan_group_key(item) -> str:
    # Key = f"{HSN}|{description}" when description present
    # Key = f"{HSN}|N:{sorted_item_names}" when names present (no description)
    # Key = f"ID:{item_id}" fallback (never merge un-named items)
```

**Evidence:**
- **Grouping definition:** plan_grouping.py lines 1-29 (module docstring)
- **Key function:** line 73-85
- **Consumers:**
  - `plan_enforcement.py:group_ids_of()` — retrieves all item IDs in a group
  - `plan_utilization.py` — groups items for Planning Modal display
  - Auto-plan engines — save one plan line per group representative

#### Layer 3: Waterfall Calculation

Each norm applies a sequential "priority bucket" calculation, consuming the running balance CIF:

**E1 example** (services/e1_plan.py, line 12-33):
1. OTHER CONFECTIONERY INGREDIENTS @ 3.00
2. COCOA MASS @ 10.00
3. MILK PRODUCTS → delegated to `milk_planner.split_milk_0404()`
4. EGG ALBUMIN @ 25.00 (WPC price from MILK_CONFIG)
5. FRUIT JUICE @ 2.50
6. TARTARIC ACID @ 1.50
7. ALUMINIUM FOIL @ 4.50
8. POLYPROPYLENE @ 1.20

**Primitive:** `allocate_step()` (services/planning_allocation.py):
- Allocates max qty at fixed price from remaining balance
- If `remaining_balance < requested_qty × max_price`, rate drops to `remaining / qty`
- Next step gets remainder

**Evidence:**
- E1: `e1_plan.py:_generic_stage()` (line 187-200) calls `allocate_step()`
- E5: `e5_plan.py` — similar waterfall with fractional-residual optimization
- E126: `e126_plan.py:plan_e126_per_item()` — deterministic per-item
- E132: `e132_plan.py:plan_e132_per_item()` — deterministic per-item, 6-category split

#### Layer 4: Persistence

Auto-plan engines call `save_plan_lines_for_license()` (plan_enforcement.py, line 130-191):

```python
def save_plan_lines_for_license(license_obj, lines, *, delete_existing=True):
    # Full-replace semantics: DELETE all existing LicenseItemPlan rows
    # CREATE new rows from lines list
    # Each row: import_item, item_name, planned_quantity, unit_price, 
    #           planned_cif_fc, remaining_quantity, remaining_cif_fc, note
    # SNAPSHOT: baseline_used_quantity, baseline_used_cif_fc 
    #           = group_used_snapshot(item) at creation time
```

**Key:** Baseline snapshot is stamped at creation and NEVER updated. This enables correct "used since plan" calculation even when allotments are amended in-place.

---

### 2.3 Database Writes (Persistence)

**Table:** `LicenseItemPlan` (backend/apps/license/models/core.py, line 1181-1286)

**Columns (Planned State):**
- `planned_quantity` (DecimalField, 15,3) — immutable original plan
- `unit_price` (DecimalField, 15,2)
- `planned_cif_fc` (DecimalField, 15,2)
- `planned_cif_inr` (DecimalField, 15,2, nullable)
- `note` (CharField, 500)

**Columns (Live Remaining Balance):**
- `remaining_quantity` (DecimalField, 15,3, nullable) — independently-draining per-line balance
- `remaining_cif_fc` (DecimalField, 15,2, nullable)

**Columns (Baseline Snapshot for "Used Since Plan" Calculation):**
- `baseline_used_quantity` (DecimalField, 15,3) — group's live-allotted qty at creation time
- `baseline_used_cif_fc` (DecimalField, 15,2)

**Foreign Keys:**
- `import_item` (ForeignKey to `LicenseImportItemsModel`, CASCADE)
- `license` (ForeignKey to `LicenseDetailsModel`, CASCADE, denormalized for fast per-license queries)
- `item_name` (ForeignKey to `ItemNameModel`, nullable, used to tag split item names, e.g., DWP vs SWP)

**Indexes:** `(license)`, `(import_item)` (line 1277)

**Write Paths:**
1. `bulk_upsert()` (views/item_plan.py, line 268) — DELETE all, INSERT many
2. `auto_plan()` / `e1_auto_plan()` (views/item_plan.py, line 352/434) — call `save_plan_lines_for_license()`
3. `plan_norms` command (management/commands/plan_norms.py, line 68-69)
4. Direct CRUD (CREATE/UPDATE/DELETE) via REST ViewSet

---

### 2.4 Enforcement During Allocation

**When:** User clicks "Allocate" in Allotment UI → POST `/api/allotments/<id>/allocate-items/`

**Handler:** `AllotmentActionViewSet.allocate_items()` (views_actions.py, line 625-876)

**Plan Cap Check** (line 744-785):
```python
plan_status = plan_status_for(license_item)  # per-group cap
if plan_status is not None:
    exceeds_qty = (plan_status["used_quantity"] + qty) > plan_status["original_quantity"]
    exceeds_val = (plan_status["used_cif_fc"] + cif_fc) > plan_status["original_cif_fc"]
    if exceeds_qty or exceeds_val:
        errors.append({'plan_exceeded': True, ...})
```

**Plan-Line Balance Decrement** (line 820-852):
- If `plan_line_id` provided (from Plan-mode grid), decrement that line's `remaining_quantity` and `remaining_cif_fc`
- If line was deleted (auto-replan between page load and confirm), silently skip (no error)

---

## 3. CALCULATIONS

### 3.1 Original Planned Quantity & CIF

**Immutable after creation.** Set by auto-plan or user input, never touched by allotment code.

**Precision:**
- Quantity: 3 decimal places (line 1220-1223, LicenseItemPlan model)
- CIF-FC: 2 decimal places (line 1228-1231)

**Rounding:** Each engine rounds at its own stage (e.g., E1 uses 4-dp quantization internally, rounds to user display precision at serialization).

---

### 3.2 Remaining Balance (Per Line)

**Independently-draining balance for Plan-mode grid** (line 1248-1251):

```python
remaining_quantity = (planned_quantity - qty_allocated_via_plan_line_id)
remaining_cif_fc = remaining_quantity * unit_price
```

**Lifecycle:**
1. Created = `planned_quantity` (plan_enforcement.py, line 176)
2. Decremented when allotment names `plan_line_id` (views_actions.py, line 842-845)
3. NOT auto-restored on allotment delete (by design — prevents "ripple credit" confusion)

**Critical:** This is SEPARATE from "Used Since Plan" aggregate calculation. Two different balance models coexist:
- **Per-line remaining:** Stored, explicit decrement, for Plan-mode grid display
- **Group-level used:** Live aggregate from `AllotmentItems`, for enforcement + Allocate screen display

---

### 3.3 Used Since Plan (Baseline Snapshot Pattern)

**Formula** (plan_enforcement.py, line 228-239):
```python
original_qty = sum(LicenseItemPlan.planned_quantity for group)
used_qty = max(0, current_live_allotted_qty - baseline_used_quantity)
remaining_qty = original_qty - used_qty

# CIF equivalents use _value instead of _quantity
```

**Why Baseline, Not Timestamp Filter?**

Allotment amendment: When a user re-allocates the same item to the same allotment, `allocate_items()` updates the existing `AllotmentItems` row in-place (line 795-798):
```python
existing.qty += qty
existing.cif_fc += cif_fc
existing.save()
```

The row's `created_on` never advances. A `created_on > plan_created_at` filter would miss this amendment and undercount "used".

**Baseline snapshot** fixes this: capture the group's live-allotted total AT plan creation time, then "used since" = (current total - baseline). No timestamp logic needed.

---

### 3.4 Calculations Across All Engines

| Norm | Classification | Waterfall Type | Price Model | Validation |
|------|---|---|---|---|
| **E1** | By HSN + item-name tags (e1_plan.py:88) | 8-step priority | Fixed per step + avg milk DWP/SWP (milk_planner.py) | Fresh plan lines only (no price ceiling) |
| **E5** | By HSN + item-name tags (e5_plan.py) | 7-step priority | Fixed per step + avg milk DWP/SWP | Fresh plan lines only (no price ceiling) |
| **E126** | Deterministic (e126_plan.py:plan_e126_per_item) | Per-item direct | Fixed: Nuts/PKO/Olive Oil @ known prices | Group price ceiling check (line 30 e126_auto_plan.py) |
| **E132** | Deterministic (e132_plan.py:plan_e132_per_item) | Per-item direct, 6-category split | Fixed per category or TBD (Milk/Yeast) | Group price ceiling check (line 29 e132_auto_plan.py) |
| **A3627** | Via item_matcher.get_item_filters() (a3627_auto_plan.py:55) | 4-step priority (RUTILE > TiO2 > Soda Ash > PP) | RUTILE: avg import price → 2.50 or 3.50; others fixed | Group price ceiling check (line 25 a3627_auto_plan.py) |

**Shared Primitives:**
- `allocate_step()` (planning_allocation.py) — allocates qty at rate from balance
- `milk_planner.split_milk_0404()` (milk_planner.py) — DWP/SWP split (shared by E1/E5)
- `plan_grouping.merge_items_for_classification()` — groups by HSN + normalized description
- `plan_grouping.validate_fresh_plan_lines()` — safety check (non-negative, qty ≤ available)
- `plan_grouping.validate_group_plan_lines()` — stricter price-ceiling check (E126/E132/A3627)

---

## 4. BUSINESS RULES

### 4.1 Plan Constraints (Enforced)

**1. Group Capacity (Per Item's Description Group)**

```
Σ planned_quantity (all splits of an item's group) ≤ 
    (live_allotted_qty for group + available_quantity sum for group)
```

**Evidence:**
- Definition: views/item_plan.py, line 223-240 (bulk_upsert)
- Enforcement: plan_enforcement.py, line 70-78 (live_allotted_qty_for)
- Per-item API: _validate_plan_line_cap() line 59-96

**2. License CIF Pool (Shared Across All Plan Lines)**

```
Σ planned_cif_fc (all lines for license) ≤ license.get_balance_cif (live)
```

**Evidence:**
- Definition: views/item_plan.py, line 242-252 (bulk_upsert)
- Enforcement: line 89-96 (_validate_plan_line_cap)

**3. Allotment Cap (At Allocation Time)**

```
(used_quantity + new_qty) ≤ original_quantity (from plan)
(used_cif_fc + new_cif) ≤ original_cif_fc (from plan)
```

**Evidence:** views_actions.py, line 763-784

**4. Expiry Gate**

No allocation against expired license (line 679-685 views_actions.py).

### 4.2 Auto-Plan Thresholds

**"Already Planned" Threshold (plan_norms.py, line 45; auto_plan_all view, line 520):**
```python
existing_cif >= live_balance * 0.99
```

When true, license is skipped (unless `--force`).

### 4.3 Item Eligibility for Planning

**Min Planned Quantity (e1_auto_plan.py, line 42):**
```python
MIN_PLAN_QTY = Decimal('50')
```

Items < 50 units are excluded from E1 auto-plan (same threshold used by E126, E132, A3627 via shared services).

**Norm-Supported Norms:** E1, E5, E126, E132, A3627 (others: no plan generated).

### 4.4 Plan Line Lifecycle

**Create:**
- Snapshot baseline: `baseline_used_qty = group_used_snapshot(import_item)`
- Snapshot balance: `baseline_used_cif_fc = group_used_snapshot(import_item)[1]`
- Initialize remaining: `remaining_qty = planned_qty`, `remaining_cif = planned_cif`

**Update (via bulk_upsert):**
- Full-replace semantics: existing rows are ALL deleted, new rows created fresh
- Baseline re-snapshotted at create time (so Used resets to 0, Remaining resets to Original)

**Delete (manual or auto-replan):**
- No "credit" step — Used is computed live from AllotmentItems aggregate, so deletion automatically restores Remaining on next read

---

## 5. DEPENDENCIES

### 5.1 Module 1: Balance & Ledger

**Dependency:** `license_obj.get_balance_cif` property (models/core.py).

**Flow:**
- Auto-plan endpoints call `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()` (views/item_plan.py, line 496)
- Each planning engine reads `balance_cif` as the max amount to allocate
- CIF pool constraint (line 242-252 bulk_upsert) compares against `license_obj.get_balance_cif`

**Evidence:**
- E1 auto-plan (e1_auto_plan.py:110-113): reads `license_obj.get_balance_cif`, falls back to `license_obj.balance_cif` (stale cache)
- `auto_plan_all` (views/item_plan.py:496): batches `calculate_financial_balance_for_licenses()`

**Risk (BL-LEDGER-02 noted in code):** The cached `balance_cif` column on `LicenseBalance` can lag reconciliation-allocation changes. Auto-plan now uses live balance via LicenseBalanceCalculator.

### 5.2 Module 3: Allocation

**Bidirectional Coupling:**

1. **Allocation → Plan Enforcement** (allocate_items checks plan cap before accepting allotment)
2. **Allocation → Plan Line Decrement** (allocate_items decrements `remaining_quantity` if `plan_line_id` provided)
3. **Plan Enforcement Reads AllotmentItems** (plan_status_for aggregates from AllotmentItems, not cached columns)

**Evidence:**
- views_actions.py, line 760-784 (plan cap check, live_allotted_qty_for aggregates)
- line 832-852 (plan-line balance decrement)
- plan_enforcement.py, line 48-89 (live_allotted_qty, live_allotted_value helpers)

### 5.3 Module 4: Bill of Entry

**Indirect Dependency:** BOE reconciliation updates `AllotmentItems.bill_of_entry` FK. Plan enforcement filters them out:

```python
_ALLOTTED_FILTER = Q(
    allotment__bill_of_entry__isnull=True,
    allotment__type="AT",
)
```

**Evidence:** plan_enforcement.py, line 24-27.

**Rationale:** BOE rows represent DGFT-approved allocations; they're not available for re-planning. Only "Actual Transfer" (AT) rows count toward plan caps.

---

## 6. UNKNOWNS & AMBIGUITIES

### 6.1 Missing Specifications

1. **A3627 Norm Routing:** Is A3627 norm detected/dispatched correctly?
   - `detect_norm()` (norm_plan.py:23-42) returns "A3627" when export_license.norm_class matches
   - But no explicit test evidence found; E1/E5/E126/E132 tested in test_* files, A3627 untested
   - **Action:** Search for A3627 test coverage or verify via manual test

2. **Milk DWP/SWP Pricing Derivation:** How are DWP vs SWP rates calculated?
   - `milk_planner.split_milk_0404()` (milk_planner.py) delegates to MILK_CONFIG constants
   - But these constants are set statically; no per-license or per-import-item variation observed
   - **Action:** Verify MILK_CONFIG is truly fixed or if there's hidden per-license logic

3. **E132 Vegetable Oil Split Preservation:** The code mentions "preserve once generated" (e132_auto_plan.py docstring)
   - `remaining_quantity` / `remaining_cif_fc` are passed as kwargs to avoid re-zeroing already-decremented balances
   - But no test case verifies this across a re-plan cycle
   - **Action:** Audit e132_auto_plan.py line 105-120 (Vegetable Oil special case)

### 6.2 Query Efficiency Unknowns

1. **plan_status_for_items() Batching:** The new batched function (line 278-385 plan_enforcement.py) claims ~315 queries → ~5 for 100 items
   - But no integration test measures this in production scale (>1000 licenses with >5k import items)
   - **Action:** Run query_count test on realistic data

2. **Prefetch Coverage:** `auto_plan_all` prefetches (line 486-491 views/item_plan.py):
   ```python
   .prefetch_related(
       'export_license__norm_class',
       'import_license__items',
       'import_license__hs_code',
   )
   ```
   But no validation that this covers all access patterns in compute_*_auto_plan functions
   - **Action:** Profile with django-debug-toolbar

3. **Norm Detection Query:** `detect_norm()` (line 26-29 norm_plan.py) calls `license_obj.export_license.first()`
   - If export_license is not prefetched, this triggers a query
   - Code assumes prefetch in bulk paths but doesn't enforce it
   - **Action:** Audit all callers of detect_norm()

### 6.3 Baseline Snapshot Correctness

1. **What if baseline is taken mid-amendment?** Thread A starts an allotment amendment on item X, mid-way thread B triggers an auto-replan
   - Thread B's baseline snapshot includes partial-state of thread A's amendment
   - Is this acceptable? Code has no comments on this race condition
   - **Evidence:** No locking around snapshot (plan_enforcement.py, line 116-127 group_used_snapshot)
   - **Action:** Verify transaction isolation level or add explicit locking

2. **Stale baseline_used_quantity on old rows:** Rows created months ago have an OLD baseline; if a license gets heavily allotted then planned, the new baseline resets "Used" to 0
   - Is this the intended semantics? Docs say "Used since THIS plan was saved" but implications for long-lived licenses unclear
   - **Action:** Clarify business intent: is "Used" ever meant to be cumulative, or always relative to latest plan?

---

## 7. RISKS & DATA INTEGRITY ISSUES

### 7.1 Race Conditions

**1. Concurrent bulk_upsert + allocate_items on same license**

Both operations run under `transaction.atomic()` + `select_for_update()` on license + items (views/item_plan.py:196-206, views_actions.py:667-671).

**Risk Level:** LOW — locking serializes concurrent requests.

**Caveat:** If a third operation (e.g., balance change signal) runs outside this atomic block, it could see intermediate state.

**Evidence:** Code explicitly addresses this (line 191-195 item_plan.py comment).

---

**2. plan_line_id stale reference during re-plan**

User allocates against plan_line_id X, but between page load and confirm, auto-plan deletes X and creates Y.

**Risk Level:** MEDIUM

**Current Handling:** allocate_items silently ignores stale plan_line_id (line 846-851 views_actions.py):
```python
except LicenseItemPlan.DoesNotExist:
    # Stale reference (e.g. Auto-Plan regenerated this line...)
    pass
```

**Risk:** Allocation succeeds but plan-line balance never decremented. User sees inconsistent "Remaining" on next refresh.

**Mitigation:** Frontend should refresh plan state before confirming allocation (not verified in code).

---

### 7.2 Data Loss Scenarios

**1. Delete allotment → plan-line not re-credited**

`remaining_quantity` is never auto-incremented on AllotmentItems.delete(). By design — "Used" is computed live from aggregate, not stored.

**Risk Level:** NONE — correct by design. Deleting an allotment immediately restores remaining on next read (since Used recalculates).

---

**2. Bulk_upsert deletes old plan before new lines are created**

(line 268 item_plan.py):
```python
LicenseItemPlan.objects.filter(license_id=license_id).delete()
for ln in lines:
    # ... create new rows
```

**Risk Level:** LOW — inside one transaction. If create fails, DELETE is rolled back.

**Caveat:** No foreign-key constraint on AllotmentItems → LicenseItemPlan. If an allotment names a now-deleted plan_line_id, the FK is simply stale (treated gracefully in allocate_items).

---

**3. Denormalized license field out of sync**

LicenseItemPlan.save() (line 1281-1282) only syncs license_id on create, never on update.

**Risk Level:** MEDIUM

**Scenario:** If an import item is reassigned to a different license (unlikely but possible via admin), its plan rows won't track this.

**Evidence:** No audit trail; no signal on import_item change.

**Recommendation:** Add a signal to LicenseImportItemsModel that updates any orphaned plan rows.

---

### 7.3 Concurrency Under High Load

**1. N+1 on plan_status_for_items() if not used**

The new batched function (line 278) exists but is NOT called by allocate_items (line 760 views_actions.py still calls `plan_status_for()` per-item in a loop).

**Risk Level:** MEDIUM (for paginated Allocate screens with >50 items)

**Evidence:**
- New function introduced but no integration point in allocate_items
- Allocate screen uses available_licenses grid which could benefit from batching
- Test exists (test_planned_report_query_count_stays_flat) but only for report view, not allocate

---

**2. Baseline snapshot without explicit lock**

`group_used_snapshot()` (line 116-127 plan_enforcement.py) reads live AllotmentItems aggregate but does NOT lock the source rows.

**Risk Level:** LOW (aggregate is eventually consistent, not atomic per-row)

**However:** If a concurrent delete_allotment_item is mid-transaction, snapshot could see a partially-committed state (depends on DB isolation level).

---

### 7.4 Large Dataset Behavior

**Test Coverage:**
- test_planned_report_query_count_stays_flat (test_planned_report_view.py) — 5 → 15 licenses, query count must stay < +3

**Scale:** Only tested up to ~15 licenses. Behavior on >1000 licenses + >50k import items unknown.

**Potential Issues:**
1. `plan_status_for_items()` batches queries but still one query per item in outer loop (line 304-326)
2. `auto_plan_all` calculates balance for ALL licenses upfront (line 496) — could OOM on very large tenants
3. Prefetch_related on nested relations (export_license__norm_class) could load large joined sets

---

## 8. DUPLICATE CALCULATIONS

### 8.1 Are There Multiple Planning Engines?

**YES — Five distinct engines exist:**

| Engine | File | Purpose | Dispatch |
|--------|------|---------|----------|
| **E1** | e1_auto_plan.py + e1_plan.py | Confectionery (8-step waterfall) | detect_norm() → "E1" |
| **E5** | e5_auto_plan.py + e5_plan.py | Sugar (7-step waterfall) | detect_norm() → "E5" |
| **E126** | e126_auto_plan.py + e126_plan.py | Nuts/PKO/Olive Oil (deterministic) | detect_norm() → "E126" |
| **E132** | e132_auto_plan.py + e132_plan.py | Vegetable Oil (6-category split) | detect_norm() → "E132" |
| **A3627** | a3627_auto_plan.py | Glass & Ceramic (4-step priority) | detect_norm() → "A3627" |

---

### 8.2 Are Calculations Duplicated?

**SHORT ANSWER:** Mostly NO — shared at the primitive level, but each engine has its own implementation.

**Shared Primitives:**
1. **`allocate_step()`** (planning_allocation.py) — Used by E1, E5, A3627 waterfalls
2. **`milk_planner.split_milk_0404()`** — Used by E1 and E5 for DWP/SWP split
3. **`plan_grouping.merge_items_for_classification()`** — Used by ALL engines to group by HSN + description
4. **`plan_grouping.{validate_fresh_plan_lines, validate_group_plan_lines}`** — Shared validation

**Per-Engine Implementations:**
1. **E1 classification** (e1_plan.py:88-154) — HSN + item-name rules, 8 buckets
2. **E5 classification** (e5_plan.py) — Similar to E1, 7 buckets
3. **E126 classification** (e126_plan.py) — Deterministic per-item (Nuts/PKO/Olive Oil)
4. **E132 classification** (e132_plan.py) — Deterministic per-item (Nuts/Yeast/PKO/RBD/Cheese/Aluminium)
5. **A3627 classification** (a3627_auto_plan.py) — Via item_matcher.get_item_filters() (RUTILE/TiO2/SodaAsh/PP)

---

### 8.3 Authoritative Planning Engine

**Per-Norm Authority:**

| Norm | Authoritative Source | Read-Only Consumers |
|------|---|---|
| E1 | e1_plan.plan_e1_items() | e1_auto_plan.py, norm_plan.py, item_pivot_report.py |
| E5 | e5_plan.plan_e5_items() | e5_auto_plan.py, norm_plan.py, item_pivot_report.py |
| E126 | e126_plan.plan_e126_per_item() | e126_auto_plan.py, norm_plan.py, item_pivot_report.py |
| E132 | e132_plan.plan_e132_per_item() | e132_auto_plan.py, norm_plan.py, item_pivot_report.py |
| A3627 | a3627_auto_plan.py (self-contained) | (no other known consumer) |

**Verification:** Every consumer delegates to the same shared engine. No re-implementation observed.

---

### 8.4 Discrepancies Between Pre-Fill (norm_prefill) and Auto-Plan (auto_plan)

**norm_prefill** (views/item_plan.py:128-150):
- Returns per-import-item planned values for manual form pre-fill
- Calls `norm_plan_for_license()` (norm_plan.py:117)

**auto_plan** (views/item_plan.py:375-454):
- Computes full plan lines and persists them
- Calls the full engine (compute_e1_auto_plan, etc.)

**Potential Divergence:**
1. norm_prefill returns per-ITEM values (one row per import item)
2. auto_plan groups by (HSN, description) and returns per-GROUP lines

**Risk:** User sees different grouping/pricing between prefill (per-item) and saved plan (per-group).

**Evidence:**
- norm_plan.py:166-172 (E1 per-item aggregation)
- e1_auto_plan.py:149-178 (E1 per-group aggregation)

**Recommendation:** Document this divergence or align the outputs.

---

## 9. SUMMARY: CRITICAL FINDINGS

| Finding | Severity | Status | Evidence |
|---------|----------|--------|----------|
| **Stale plan_line_id handling** | MEDIUM | By Design | views_actions.py:846-851 (silent pass) |
| **No plan-line credit on delete** | LOW | Correct | Used is live-computed, by design |
| **N+1 on allocate screen** | MEDIUM | Unfixed | plan_status_for per-item loop; plan_status_for_items exists but unused |
| **Denormalized license FK sync** | MEDIUM | Risk | LicenseItemPlan.save() only syncs on create (line 1281) |
| **Baseline snapshot race** | LOW | Acceptable | Snapshot taken outside transaction, but aggregate is eventual-consistent anyway |
| **Norm prefill vs auto-plan divergence** | LOW | Undocumented | Per-item vs per-group grouping difference |
| **A3627 test coverage** | MEDIUM | Unknown | No test files found; code present but untested |
| **Large dataset scale** | MEDIUM | Untested | Query count test only on ~15 licenses |
| **Milk pricing flexibility** | UNKNOWN | Static | MILK_CONFIG constants, no per-license override observed |
| **Duplicate import items** | MEDIUM | Possible | No unique constraint on (license, serial_number) found |

---

## 10. RECOMMENDATIONS

### Immediate (High Priority)

1. **Integrate plan_status_for_items() into allocate_items:**
   - Replace per-item loop (line 760 views_actions.py) with batched call
   - Measure improvement on paginated allocate screens

2. **Add signal to LicenseImportItemsModel:**
   - Sync orphaned LicenseItemPlan.license_id if import_item.license changes
   - Prevents data drift from admin reassignment

3. **Document plan_line_id stale reference handling:**
   - Clarify frontend responsibility to refresh plan state pre-confirm
   - Add integration test verifying silent failure + user-visible reconciliation

### Medium Priority

4. **Test A3627 Norm:**
   - Add auto_plan and detect_norm tests for A3627 licenses
   - Verify routing and calculation correctness

5. **Scale Test:**
   - Run query_count test on >1000 licenses, >50k import items
   - Profile prefetch_related depth (export_license__norm_class)

6. **Clarify norm_prefill vs auto_plan divergence:**
   - Document per-item vs per-group grouping difference
   - Either align outputs or add UI warning

### Low Priority

7. **Explicit Lock on Baseline Snapshot:**
   - If DB isolation < SERIALIZABLE, add select_for_update() around baseline calculation
   - Verify isolation level in settings

8. **Unique Constraint on Import Items:**
   - Add (license, serial_number) unique constraint to prevent duplicates
   - Or audit existing deduplication logic

---

**Audit Complete**  
**Next Steps:** Module 3 (Allocation) forensic review
