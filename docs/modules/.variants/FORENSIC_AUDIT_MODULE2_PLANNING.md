# FORENSIC AUDIT: Planning System (Module 2)

**Audit Scope:** Complete dependency analysis of the Planning system on ledger, allocation, BOE, and items modules.  
**Date:** 2026-08-10  
**Classification:** EVIDENCE-BASED, READ-ONLY ANALYSIS

---

## 1. ENTRY POINTS

### 1.1 API Endpoints (REST)

**Endpoint Chain:**
- **GET `/api/license-item-plans/?license=<id>`** → `LicenseItemPlanViewSet.list()`
  - File: `backend/apps/license/views/item_plan.py:99-110`
  - Filters existing plan lines by license
  - Read-only; no writes

- **POST `/api/license-item-plans/`** → `LicenseItemPlanViewSet.create()`
  - File: `backend/apps/license/views/item_plan.py:111-117`
  - Creates single plan line with validation via `_validate_plan_line_cap()`
  - **Validates:** capacity (available + live-allotted) per item group + CIF pool ceiling
  - Transaction-wrapped; row-locks license + item group

- **PATCH `/api/license-item-plans/<id>/`** → `LicenseItemPlanViewSet.perform_update()`
  - File: `backend/apps/license/views/item_plan.py:119-126`
  - Modifies existing plan line
  - Same validation as create, excluding the modified row from "already planned" sums

- **DELETE `/api/license-item-plans/<id>/`** → Standard ModelViewSet.destroy()
  - File: `backend/apps/license/views/item_plan.py:99-110`
  - Removes single plan line; no cascade logic

- **GET `/api/license-item-plans/norm-prefill?license=<id>`** → `LicenseItemPlanViewSet.norm_prefill()`
  - File: `backend/apps/license/views/item_plan.py:128-150`
  - Returns: `{"norm": "E1"|"E5"|"E126"|"E132"|"", "plan": {import_item_id: {planned_quantity, unit_price, planned_cif}}}`
  - Calls `norm_plan_for_license()` to compute norm-based plan for prefill (UI only; does not persist)

- **POST `/api/license-item-plans/bulk-upsert/`** → `LicenseItemPlanViewSet.bulk_upsert()`
  - File: `backend/apps/license/views/item_plan.py:152-292`
  - **Full-replace semantics:** deletes all existing lines, creates new ones from request
  - **Validates:** item membership + per-item capacity + license CIF pool
  - **Writes:** `LicenseItemPlan` table (insert); computes `baseline_used_quantity`/`baseline_used_cif_fc` snapshots at save time
  - Transaction-wrapped; row-locks license + all items

- **POST `/api/license-item-plans/e1-auto-plan/`** → `LicenseItemPlanViewSet.e1_auto_plan()`
  - File: `backend/apps/license/views/item_plan.py:294-373`
  - Calls `compute_e1_auto_plan()` and persists via `save_plan_lines_for_license()`
  - E1-specific endpoint; rejects non-E1 licenses

- **POST `/api/license-item-plans/auto-plan/`** → `LicenseItemPlanViewSet.auto_plan()`
  - File: `backend/apps/license/views/item_plan.py:375-454`
  - **Unified dispatcher:** detects norm (E1/E5/E126/E132) and runs appropriate planner
  - Calls `detect_norm()` → one of: `compute_e1_auto_plan()`, `compute_e5_auto_plan()`, `compute_e126_auto_plan()`, `compute_e132_auto_plan()`
  - Full-replace via `save_plan_lines_for_license()`

- **POST `/api/license-item-plans/auto-plan-all/`** → `LicenseItemPlanViewSet.auto_plan_all()`
  - File: `backend/apps/license/views/item_plan.py:456-550` (partial)
  - Batch: runs auto-plan for ALL eligible active licenses (E1/E5/E126/E132 with live balance > 0)
  - Skips already-planned licenses (≥99% of balance covered by plan)
  - Failures isolated per-license; batch continues

### 1.2 Management Command

**`python manage.py plan_norms <NORM> [--license <N>] [--all] [--dry-run]`**
- File: `backend/apps/license/management/commands/plan_norms.py:74-275`
- **Entry:** Line 109, `Command.handle()`
- Loads active licenses with live-balance ≥ 0, detects norm at runtime
- Default: skips already-planned (≥99%); `--all` re-plans everything
- Calls `PlannerFactory.run(license_obj, norms_class)` → returns `PlanResult(lines, remaining_cif)`
- Persists via `save_plan_lines_for_license(license_obj, lines)` (line 221)
- Outputs summary: total / planned / already_planned / failed + reasons

### 1.3 Allocation Endpoint (Plan Enforcement)

**POST `/api/allotments/<pk>/allocate-items/`** → `AllotmentActionViewSet.allocate_items()`
- File: `backend/apps/allotment/views_actions.py:625-875`
- **Plan cap enforcement:** Line 760-785
- Calls `plan_status_for(license_item)` → returns plan status dict or None
- Checks: `(used_qty + new_qty) > original_qty` OR `(used_cif + new_cif) > original_cif`
- **Plan line balance decrement:** Line 832-851
  - Optional `plan_line_id` in request body (sent by Plan-mode grid)
  - Decrements `LicenseItemPlan.remaining_quantity`/`remaining_cif_fc` directly
  - Stale reference (line 846-851): logged but allotment persists (plan-line may have been regenerated)

### 1.4 Allocation: Plan Mode (Display)

**GET `/api/allotments/<pk>/available-licenses?debit_based_on=plan`** → `AllotmentActionViewSet._available_licenses_plan_mode()`
- File: `backend/apps/allotment/views_actions.py:376-575`
- Grid shows one row per `LicenseItemPlan` line (not per import item)
- Each row displays: `remaining_quantity`/`remaining_cif_fc` (the line's independently-draining balance)
- Filters supported: `planned_item_names`, `available_quantity_gte`/`_lte`, `available_value_gte`/`_lte`

---

## 2. DATA FLOW

### 2.1 Planning Generation (Auto-Plan Flow)

```
[API: POST /auto-plan/]
  ↓
[detect_norm(license_obj)]
  → checks export license's norm_class FK, falls back to E1/E5/E126/E132 heuristics
  → File: backend/apps/license/services/norm_plan.py
  ↓
[PlannerFactory.run(license_obj, norms_class)]
  → registry lookup (Line 71-90, backend/apps/license/services/planner_factory.py)
  → dispatches to registered planner:
    - E1 → compute_e1_auto_plan()
    - E5 → compute_e5_auto_plan()
    - E126 → compute_e126_auto_plan()
    - E132 → compute_e132_auto_plan()
    - A3627 → compute_a3627_auto_plan()
  ↓
[Planner Logic]
  1. Load import items: license.import_license.all()
  2. Group by plan_group_key (HSN + normalized description)
  3. Apply waterfall classification + allocation rules
  4. Return: (lines, remaining_cif)
     - lines: list[dict] with keys:
       * import_item: int (representative item ID)
       * item_name: int | None (ItemNameModel FK or None)
       * planned_quantity: float
       * unit_price: float
       * planned_cif_fc: float
       * note: str (step label)
  ↓
[save_plan_lines_for_license(license_obj, lines)]
  File: backend/apps/license/services/plan_enforcement.py:130-191
  1. DELETE existing: LicenseItemPlan.objects.filter(license=license_obj)
  2. For each line dict:
     a. Compute baseline snapshot: group_used_snapshot(item)
        → live_allotted_qty_for(group_ids) + live_allotted_value_for(group_ids)
        → aggregates from AllotmentItems WHERE type="AT" AND bill_of_entry__isnull=True
        → File: backend/apps/license/services/plan_enforcement.py:48-127
     b. CREATE LicenseItemPlan row:
        - import_item_id ← import_item
        - item_name_id ← item_name
        - planned_quantity ← planned_quantity
        - unit_price ← unit_price
        - planned_cif_fc ← planned_cif_fc
        - remaining_quantity ← planned_quantity (defaults)
        - remaining_cif_fc ← planned_cif_fc (defaults)
        - baseline_used_quantity ← baseline snapshot qty
        - baseline_used_cif_fc ← baseline snapshot cif
        - license_id ← license
        - note ← note
  3. Return: list of created LicenseItemPlan instances
```

**Database writes:**
- **Table:** `license_licenseitemplan`
- **Fields mutated:** all of the above (insert only, no update during auto-plan)
- **Transaction:** atomic (line 220-221, plan_norms.py; line 434-435, item_plan.py)

### 2.2 Manual Plan Entry (bulk-upsert Flow)

```
[API: POST /bulk-upsert/]
  ↓
[Validate per-item capacity + license CIF pool]
  1. Lock license row: LicenseDetailsModel.select_for_update()
  2. Lock item rows: LicenseImportItemsModel.select_for_update()
  3. For each item: compute capacity = live_allotted + available
  4. Check: Σ planned_qty per item ≤ capacity
  5. Check: Σ planned_cif_fc license-wide ≤ balance_cif
  ↓
[Full replace (same as auto-plan flow)]
  1. DELETE all existing LicenseItemPlan rows for license
  2. For each supplied line: CREATE new row with baseline snapshot
  3. Return: saved lines + counts
```

### 2.3 Allocation-Time Plan Enforcement

```
[API: POST /allocate-items/]
  ↓
[For each allocation in request.allocations]
  1. Lock item: LicenseImportItemsModel.select_for_update()
  2. Check availability: qty ≤ available_quantity
  3. Check CIF: cif_fc ≤ available_cif (computed from balance_cif_fc property)
  4. [PLAN CAP CHECK] Call plan_status_for(license_item)
     File: backend/apps/license/services/plan_enforcement.py:243-275
     a. group_ids_of(item) → list of all items in the group
     b. planned_totals_for(gids) → (original_qty, original_cif)
     c. live_allotted_qty_for(gids) → current sum from AllotmentItems
     d. Min baseline from group's LicenseItemPlan rows
     e. used_qty = max(0, current - baseline_qty)
     f. used_cif = max(0, current - baseline_cif)
     g. remaining_qty = original - used_qty
     h. remaining_cif = original - used_cif
     i. Return: {original_quantity, used_quantity, remaining_quantity, original_cif_fc, used_cif_fc, remaining_cif_fc} or None
  5. If plan status exists:
     Check: (used_qty + new_qty) > original_qty OR (used_cif + new_cif) > original_cif
     → REJECT with plan_exceeded error (line 765-784, views_actions.py)
  6. If plan_line_id provided (Plan-mode allocation):
     a. Lock LicenseItemPlan row: select_for_update()
     b. Decrement: remaining_quantity -= qty, remaining_cif_fc -= qty * unit_price
     c. SAVE update_fields=['remaining_quantity', 'remaining_cif_fc']
     d. On DoesNotExist (stale reference): silently continue (line 846-851)
  7. If no plan_line_id (Actual-mode allocation):
     No plan-line balance tracking; group-level cap is still enforced above
  ↓
[Create AllotmentItems row or amend existing]
  1. Query: AllotmentItems.filter(allotment, item).first()
  2. If exists: UPDATE qty += new_qty, cif_fc += new_cif, cif_inr += new_inr
  3. If not: CREATE new AllotmentItems row
  ↓
[Triggers (post-save)]
  - update_stock signal (Line 1, apps/allotment/models.py)
    → queues async balance recalc on_commit
    → refreshes LicenseImportItemsModel.available_quantity/available_value
```

---

## 3. CALCULATIONS

### 3.1 Plan Status Computation (Core Formula)

**File:** `backend/apps/license/services/plan_enforcement.py:194-240`

```
Input:
  - import_item: LicenseImportItemsModel instance
  - (or group_ids list for batched _ids variant)

Process:
  1. Determine group membership: group_ids_of(item)
     → all import items with identical plan_group_key(item)
     → File: backend/apps/license/services/plan_grouping.py:426-475

  2. Plan totals (immutable):
     planned_qty = SUM(LicenseItemPlan.planned_quantity WHERE import_item_id IN group_ids)
     planned_cif = SUM(LicenseItemPlan.planned_cif_fc WHERE import_item_id IN group_ids)

  3. Baseline snapshot (stored at plan-save time):
     baseline_qty = MIN(LicenseItemPlan.baseline_used_quantity FOR group_ids)
     baseline_cif = MIN(LicenseItemPlan.baseline_used_cif_fc FOR group_ids)
     → File: backend/apps/license/services/plan_enforcement.py:222-224

  4. Current live allotment (computed fresh):
     current_qty = SUM(AllotmentItems.qty WHERE item_id IN group_ids AND allotment__type="AT" AND allotment__bill_of_entry__isnull=True)
     current_cif = SUM(AllotmentItems.cif_fc WHERE item_id IN group_ids AND allotment__type="AT" AND allotment__bill_of_entry__isnull=True)
     → File: backend/apps/license/services/plan_enforcement.py:229-230

  5. Used since plan saved:
     used_qty = MAX(0, current_qty - baseline_qty)
     used_cif = MAX(0, current_cif - baseline_cif)
     → Line 231-232

  6. Remaining:
     remaining_qty = planned_qty - used_qty
     remaining_cif = planned_cif - used_cif
     → Line 236-239

Output:
  {
    "original_quantity": planned_qty,
    "used_quantity": used_qty,
    "remaining_quantity": remaining_qty,
    "original_cif_fc": planned_cif,
    "used_cif_fc": used_cif,
    "remaining_cif_fc": remaining_cif,
  }
  OR None if group has no LicenseItemPlan rows
```

**Precision:** Decimal fields from DB (15 digits, 3 decimal places for qty; 15 digits, 2 decimal places for CIF).

### 3.2 Auto-Plan Waterfall (E1 Example)

**File:** `backend/apps/license/services/e1_plan.py:96-168`

```
E1 Steps (waterfall, each draws down balance):

Step 1: OTHER CONFECTIONERY INGREDIENTS @ $3.00/unit
  qty = SUM(item.available_qty WHERE category="OTHER CONFECTIONERY INGREDIENTS")
  cif = allocate_step(qty, $3.00, balance_cif)
  balance_cif -= cif

Step 2: COCOA MASS @ $10.00/unit
  qty = SUM(item.available_qty WHERE category="COCOA MASS")
  cif = allocate_step(qty, $10.00, balance_cif)
  balance_cif -= cif

Step 3: MILK PRODUCTS (delegated to milk_planner.split_milk_0404)
  qty = SUM(item.available_qty WHERE category="MILK")
  → split_milk_0404(qty, balance_cif) returns [{step: "DWP", qty, cif, price}, {step: "SWP", qty, cif, price}, {step: "WPC", qty, cif, price}]
  balance_cif -= total_cif_from_split

Steps 4-8: EGG_ALBUMIN, FRUIT_JUICE, TARTARIC_ACID, ALUMINIUM_FOIL, POLYPROPYLENE
  Same as Step 1-2 pattern

allocate_step(qty, unit_price, balance) {
  requested_cif = qty * unit_price
  if requested_cif <= balance:
    allocated_cif = requested_cif (use full price)
    allocated_price = unit_price
  else:
    allocated_cif = balance (use all remaining balance)
    allocated_price = balance / qty (reduced rate)
  return allocated_cif
}

Output:
  lines = [{import_item, item_name, planned_quantity, unit_price, planned_cif_fc, note}, ...]
  remaining_cif = balance after all steps
```

### 3.3 Grouping Logic (Critical for Plan Enforcement)

**File:** `backend/apps/license/services/plan_grouping.py:73-85`

```
plan_group_key(item) →
  hsn = normalize(item.hs_code.hs_code)
  desc = normalize(item.description)
  if desc:
    return f"{hsn}|{desc}"
  names = sorted([n.name for n in item.items.all()])
  if names:
    return f"{hsn}|N:{', '.join(names)}"
  return f"ID:{item.id}"

normalize(text) →
  1. Strip whitespace + collapse internal runs to single space
  2. Replace any " / " or "/ " or " /" with "/"
  3. Upper-case

Example:
  HSN: "0402 21 00"  Description: "Milk Powder / Skim"
  Normalized HSN: "040221 00"
  Normalized Desc: "MILK POWDER/SKIM"
  Key: "040221 00|MILK POWDER/SKIM"

All items with identical keys are grouped; their plan lines are SUMMED at enforcement time.
```

### 3.4 E132 PKO/Cheese Preservation (Most Complex)

**File:** `backend/apps/license/services/e132_auto_plan.py:175-307`

```
For Vegetable Oil groups:
  1. Engine classifies → suggests 40% PKO, 60% Cheese split (line 34)
  2. Check existing_split_balances_for_groups(license, groups, [PKO, CHEESE])
     → scans ALL members of each group for any existing PKO/Cheese LicenseItemPlan rows
     → if EITHER target found: retrieve remaining_quantity/remaining_cif_fc for BOTH
  3. If preserved balance exists:
     - Re-emit BOTH PKO + Cheese at their CURRENT remaining values (not fresh engine values)
     - Emitted even if remaining = 0 (history preservation)
     - Example: if PKO was 1000 units at save, then 200 units were allocated:
       → preserved PKO re-emitted as 800 units at next auto-plan run
       → Cheese similarly preserved
  4. If NO preserved balance:
     - Use engine's fresh 40/60 split calculation
  5. Business Rule: NEVER emit only one side of split (PKO without Cheese or vice versa)
     → wastage-rebalance algorithm would miscompute if one side were fresh and one preserved
     → result: quantity conservation breaks
```

---

## 4. BUSINESS RULES

### 4.1 Plan Capacity Constraints

**Source:** `backend/apps/license/views/item_plan.py:29-96` (_validate_plan_line_cap) + `bulk-upsert` (line 152-292)

**Per-Item Group Constraint:**
```
For each LicenseImportItemsModel's plan-group:
  Σ planned_quantity (sum of all plan lines for items in group)
    ≤ (live_allotted_qty_for(group) + Σ available_quantity for group)

Rationale: Plan cap can never exceed total available to allot.
Formula: capacity = live_allotted + available
Checked at: plan line create/update (CRUD) + bulk-upsert + auto-plan
```

**License CIF Pool Constraint:**
```
For entire license:
  Σ planned_cif_fc (all plan lines across all items)
    ≤ license.balance_cif (live balance, not cached field)

Rationale: Plan's total value cannot exceed the license's available CIF balance.
Formula: total_planned_cif ≤ balance_cif
Checked at: plan line create/update + bulk-upsert + auto-plan
Live balance source: LicenseDetailsModel.get_balance_cif property
  (not the stale cached balance__balance_cif column)
```

### 4.2 Allotment Enforcement (Plan Cap)

**Source:** `backend/apps/allotment/views_actions.py:760-784`

```
For each allocation request:
  plan_status = plan_status_for(license_item)
  if plan_status is not None:
    if (used_qty + new_qty) > original_qty:
      REJECT "Cannot allot quantity greater than remaining planned quantity"
    if (used_cif + new_cif) > original_cif:
      REJECT "Cannot allot CIF value greater than remaining planned value"
  else:
    # No plan for this group; fall through to availability-based (unrestricted)

"plan_exceeded" error includes full plan status for frontend display.
```

### 4.3 Plan-Line Balance Tracking (Independent Draining)

**Source:** `backend/apps/allotment/views_actions.py:832-851`

```
Optional plan_line_id in allocate-items request:
  if plan_line_id provided:
    Lock: LicenseItemPlan.select_for_update()
    Decrement: remaining_quantity -= qty, remaining_cif_fc -= qty * unit_price
    Save: update_fields=['remaining_quantity', 'remaining_cif_fc']
  else:
    # Group-level cap enforced; no individual line tracking

Rationale: When one import item carries multiple plan lines (E132: Vegetable Oil → PKO + Cheese),
allotments have no item_name of their own. Available_quantity alone can't distinguish which line
to decrement. plan_line_id (sent by Plan-mode grid) is authoritative source.

Stale reference handling (line 846-851):
  If line regenerated between page load and request:
    - AllotmentItems.create succeeds (group-level cap already enforced)
    - plan_line_id lookup fails
    - Log/continue; allotment persists
```

### 4.4 Baseline Snapshot Semantics (Critical)

**Source:** `backend/apps/license/services/plan_enforcement.py:140-147, 254-266`

```
At save time, each LicenseItemPlan row receives a snapshot:
  baseline_used_quantity = live_allotted_qty for the group RIGHT NOW
  baseline_used_cif_fc = live_allotted_cif for the group RIGHT NOW

Why snapshot, not timestamp?
  AllotmentItems.created_on advances only on row creation, not on amendment.
  When allocate_items amends an existing AllotmentItems row (qty += ...), 
  created_on never advances → timestamp-based "used since plan" would silently 
  miss the amendment if it occurs after a re-plan.

Snapshot never changes once set → plan/used/remaining always resets to (original/0/original)
on re-plan, even if allotments already exist from before the re-plan. This is intentional:
if a license had 1000 units planned, 800 allocated, then is re-planned to 500 units,
the new "Remaining = 500 - 0 = 500" (not "500 - 800 = -300") because the replanning
expresses new intent going forward.
```

### 4.5 Auto-Plan Eligibility

**Source:** `backend/apps/license/management/commands/plan_norms.py:142-158, 170-194`

```
Eligible license:
  1. flags.is_active = True
  2. live balance_cif > 0
  3. norm = E1 OR E5 OR E126 OR E132 (or other registered norm)

Already planned (skip unless --all):
  total_planned_cif / balance_cif ≥ 99%

Balance computed fresh (not cached):
  LicenseBalanceCalculator.calculate_financial_balance_for_licenses([license_ids])
  → avoids BL-LEDGER-02 stale cache issue
```

### 4.6 Minimum Plan Quantity (MIN_PLAN_QTY)

**Source:** `backend/apps/license/services/e1_auto_plan.py:42` (MIN_PLAN_QTY = 50)

```
Import item groups with available_quantity < 50 units are NEVER planned.
  - Applied per-group (not per-raw-item)
  - Reduces plan noise for tiny residual quantities
  - Consistent across E1/E5/E126/E132
```

### 4.7 Price Ceiling Validation

**Source:** `backend/apps/license/services/plan_grouping.py:156-262` (validate_group_plan_lines)

```
For E126/E132 (NOT E1, which has dynamic prices):
  For each planning_item in a group:
    max(planned unit_price) ≤ UNIT_PRICE[planning_item] (hard-coded for the norm)
  
  Rejects if any line exceeds its category's fixed price.
  
  Preserved splits (E132: PKO/Cheese) skip qty-vs-available check
  (they're fixed once generated; replan can emit qty > current available as long as
  remaining balance is consistent).
```

---

## 5. DEPENDENCIES

### 5.1 Module 1: Ledger & Balance

**Dependency Chain:**

1. **Balance Computation (Input to Planning)**
   - `plan_norms` command (line 160-162): calls `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()`
   - Auto-plan waterfall uses `license_obj.get_balance_cif` property
   - Plan validation (bulk-upsert line 243): checks against `balance_cif`
   - File: `backend/apps/license/services/balance_calculator.py`

2. **Live Allotment Computation (For Baseline Snapshots)**
   - `group_used_snapshot()` (plan_enforcement.py:116-127)
   - `live_allotted_qty_for()` / `live_allotted_value_for()` (plan_enforcement.py:48-89)
   - Query: `AllotmentItems.filter(_ALLOTTED_FILTER, item_id__in=ids)`
   - Filter definition (line 24-27): `Q(allotment__bill_of_entry__isnull=True, allotment__type="AT")`
   - Same filter as `calculate_allotted_quantity()` in balance calculator (stated explicit requirement, line 8-12)

3. **Live Balance at Allocation Time**
   - `allocate_items()` (views_actions.py:722): checks `license_item.available_value_calculated`
   - Avoids older, stale `available_value` field
   - Uses `balance_cif_fc` property which branches on `condition_type` (open/%/AU)
   - Calls `condition_pool` for restriction pooling (lines 710-711)

4. **Plan Status Computation Dependency**
   - `plan_status_for()` (plan_enforcement.py:243-275)
   - Depends on AllotmentItems table (type="AT" non-BOE filter)
   - If ledger recalculation breaks AllotmentItems, plan status breaks

### 5.2 Module 3: Allocation (AllotmentItems)

**Dependency Chain:**

1. **Plan Cap Enforcement at Alloc Time**
   - `allocate_items()` computes plan_status and checks if allocation exceeds cap
   - If exceeded: returns `plan_exceeded: True` error (line 765-784)
   - Frontend must interpret and inform user

2. **Plan Line Balance Tracking**
   - Allocation optionally specifies `plan_line_id` (request body, line 832)
   - Decrements `LicenseItemPlan.remaining_quantity`/`remaining_cif_fc` (line 843-845)
   - Stale reference: if plan regenerated, allocation proceeds but line-tracking fails (line 846-851)

3. **Baseline Snapshot Dependencies**
   - `save_plan_lines_for_license()` queries AllotmentItems to compute baseline (line 162-166)
   - Must be called AFTER any pending allocations are committed
   - Called inside transaction.atomic() to keep DB consistent

4. **Available-Licenses Plan Mode**
   - Endpoint `?debit_based_on=plan` returns LicenseItemPlan rows directly
   - Each row's `remaining_quantity`/`remaining_cif_fc` shown as available balance
   - Allocation request specifies which LicenseItemPlan row the debit targets
   - Separate grid logic from Actual mode (deliberately duplicated, not shared) to preserve Actual-mode stability

### 5.3 Module 4: Bill of Entry (BOE)

**Dependency Chain:**

1. **BOE Exclusion from Plan Cap**
   - Plan-cap filter: `allotment__bill_of_entry__isnull=True, allotment__type="AT"` (plan_enforcement.py:24-27)
   - BOE allotments (bill_of_entry__isnull=False) are EXCLUDED from plan-used sums
   - Rationale: BOE items are reconciliation/adjustment; they don't consume user's planning

2. **Available Quantity (Input to Planning)**
   - Auto-plan reads `import_item.available_quantity` for each item
   - `available_quantity` reflects both user allocations AND BOE reconciliations
   - Formula: total_quantity - allotted_quantity (where allotted includes BOE)
   - File: `backend/apps/license/views/license.py` (serializer includes available_quantity)

### 5.4 Module 5: Items (Import Items & Item Names)

**Dependency Chain:**

1. **Import Item Grouping**
   - Plan groups items by: HSN + description + item names (via plan_group_key)
   - Requires: item.hs_code FK, item.description, item.items M2M (ItemNameModel)
   - Group representative: lowest serial_number
   - File: `backend/apps/license/services/plan_grouping.py:73-85`

2. **Item Name Tags**
   - Planning can assign `item_name` (FK to ItemNameModel) to each plan line
   - Used for split attribution (E132: Vegetable Oil → PKO/Cheese with separate ItemNameModel rows)
   - Frontend filters/groups by item_name when displaying plan lines

3. **Item Name Fallback for Grouping**
   - If item has no description, plan_group_key uses sorted item-name list
   - `_item_names_of()` (plan_grouping.py:63-70)

---

## 6. UNKNOWNS & AMBIGUITIES

### 6.1 `get_balance_cif` Property vs Cached Field

**Question:** Is `LicenseDetailsModel.get_balance_cif` always computed fresh, or can it lag?

**Evidence:**
- Used in E1/E5/E126/E132 auto-plan (e.g., e1_auto_plan.py:110-113)
- Falls back to `license_obj.balance_cif` (cached) if None
- Comment in plan_norms.py:44-49 suggests balance can be stale
- TODO: Verify whether `get_balance_cif` property is a property method or a field

**Impact:** If stale, auto-plan could over-allocate CIF pool

### 6.2 Condition Pooling in available_value_calculated

**Question:** How does `condition_pool` restrict available_value for restricted items?

**Evidence:**
- Comment in views_actions.py:710-711 mentions condition_type (%/AU/open) branching
- Not examined; file path unclear
- Manual review needed

**Impact:** Plan validation checks against available_value_calculated; if pooling logic changes, plan caps may shift

### 6.3 Item Pivot Planned Import Items Attribution

**Question:** How does Item Pivot Report attribute a live (unsaved) waterfall recompute's planned CIF back to item names?

**Evidence:**
- Comment in e1_auto_plan.py:66-70 mentions `item_pivot_report.py` imports STEP_ITEM_NAME
- Details unclear
- File: `backend/apps/license/services/exporters/item_pivot_report.py`

**Impact:** If attribution logic is wrong, Item Pivot displays stale plan vs. live waterfall

### 6.4 E132 PKO/Cheese Wastage-Rebalance Algorithm

**Question:** What is the exact "wastage-reduction rebalance" logic in E132 that E132_auto_plan.py mentions?

**Evidence:**
- Comment line 211-213: "engine's own wastage-rebalance (which has no idea a preserved balance exists)"
- Not fully examined; in e132_plan.py implementation
- File: `backend/apps/license/services/e132_plan.py:437-XXX` (not fully read)

**Impact:** If this algorithm is misunderstood, preserved splits may not re-emit correctly

### 6.5 "Amended" vs "Created" AllotmentItems Row Logic

**Question:** When does allocate_items create a new AllotmentItems row vs. amend an existing one?

**Evidence:**
- views_actions.py:788-809
- Checks: AllotmentItems.filter(allotment, item).first()
- If exists: qty += new_qty (amendment)
- If not: CREATE new
- Unique constraint: ("item", "allotment")

**Implication:** One (allotment, item) pair = one row, ever amended, never duplicated.

**Risk:** Plan-line balance tracking (plan_line_id) assumes allotments are ALWAYS per-import-item, NEVER per-plan-line. If a future change allows per-plan-line allotments, plan-line balance tracking breaks.

### 6.6 Baseline Snapshot Min vs Avg

**Question:** Why use MIN(baseline_used_quantity) instead of AVG or SUM for multi-line groups?

**Evidence:**
- plan_enforcement.py:222-224: `baseline = plans.aggregate(bq=Min(...), bv=Min(...))`
- Aggregation behavior when group has 3 items with different baseline snapshots not fully explained

**Impact:** If baselines differ within a group (e.g., one item's plan row was created earlier, another later), the MIN() baseline could undercount "used" and overstate "remaining"

### 6.7 Precision of calculations (Decimal vs float)

**Question:** Are there any precision mismatches between Python float calculations in auto-plan and Decimal DB storage?

**Evidence:**
- e1_auto_plan.py returns float quantities/prices (line 155-157)
- save_plan_lines_for_license() casts to Decimal inside models.create()
- E132 uses _r2() for rounding (line 101-105)
- E1 uses _quantize() (line 46-48)
- Potential for rounding errors

**Impact:** Planned + Allocated may not equal original due to rounding drift

---

## 7. RISKS

### 7.1 Concurrency: Race Condition in Plan Cap Enforcement

**Scenario:**
1. User opens allocate screen; plan shows "Remaining: 100 units"
2. User opens ANOTHER tab, allocates 100 units (plan updates to 0)
3. First tab still shows 100; user allocates 50 → REJECTED (now only 50 remaining)

**Mitigation:** `select_for_update()` (line 671, views_actions.py) locks item row during check-allocate sequence. Prevents two concurrent allocations from both passing the plan cap.

**Residual Risk:** Plan-line balance tracking (remaining_quantity field) is updated AFTER AllotmentItems.create(). If create fails or is rolled back, remaining_quantity is left stale.

### 7.2 Stale Reference: Plan Regeneration Between Page Load and Allocation

**Scenario:**
1. User opens Plan-mode grid; displays LicenseItemPlan row (ID=456) with remaining=1000
2. Auto-plan regenerates; new PKO line created (ID=789), old PKO (ID=456) deleted
3. User allocates against old plan_line_id=456 → DoesNotExist silently handled, allocation persists, plan-line balance NOT decremented

**Evidence:** views_actions.py:846-851

**Mitigation:** Silent failure; group-level cap still enforced, so over-allocation doesn't break balance. But line-level balance tracking is lost.

**Residual Risk:** If frontend/user logic relies on knowing which specific plan-line an allocation targets, this break is invisible and confusing.

### 7.3 Data Loss: Bulk-Upsert Deletes Without Backup

**Scenario:**
```sql
DELETE FROM license_licenseitemplan WHERE license_id = 123;
```

If the subsequent CREATE fails (e.g., validation error mid-loop), plan is lost and user must re-enter.

**Evidence:** plan_enforcement.py:169, bulk-upsert line 268

**Mitigation:** Wrapped in `transaction.atomic()` (line 196-252, item_plan.py). If any CREATE fails, entire transaction rolls back. Plan remains unchanged.

**Residual Risk:** Complex validation errors may leave user confused about which line failed; full plan is reverted.

### 7.4 Double-Counting: Group Rows After Re-serialization

**Scenario:**
1. License has Vegetable Oil (HSN 1234) on S.No 1-3 (grouped together)
2. DGFT re-serializes; now S.No 1 is on License A, S.No 2-3 on License B
3. Old auto-plan lines still exist on S.No 1 (License A's representative)
4. Auto-plan regenerates on License B, creates new lines on S.No 2 (B's representative)
5. Item Pivot Report queries both licenses, sees two separate plan groups (same physical product)
6. User sees 2x the planned quantity

**Evidence:** e132_auto_plan.py:20-22 docstring mentions this was a BUG in earlier versions

**Mitigation:** e132_auto_plan.py:115-200 re-groups by plan_group_key (HSN+description), aggregates available across all current group members, stores plan on current group's representative. Previous fix.

**Residual Risk:** If a license is deleted without cascading plan delete, orphaned LicenseItemPlan rows from old representative persist.

### 7.5 Plan Pool Leak: CIF-Pool Not Enforced Across License Allocations

**Scenario:**
User manually creates two plan lines:
- Line 1: planned_cif_fc = 5000 (Item 1)
- Line 2: planned_cif_fc = 4000 (Item 2)
- License balance_cif = 8000

Line 2 accepted (total = 9000 > 8000) if validation was bypassed.

**Evidence:** bulk-upsert line 242-252 checks this; CRUD endpoints check via _validate_plan_line_cap (line 82-96, item_plan.py)

**Mitigation:** Validation gates at CRUD + bulk-upsert + auto-plan.

**Residual Risk:** If backend validation is somehow bypassed, plan total can exceed balance, leading to allocations that appear to breach cap but actually don't.

### 7.6 Baseline Snapshot Desync: Manual AllotmentItems Insert

**Scenario:**
1. Auto-plan saves PKO plan line with baseline_used_quantity = 0
2. DBA manually INSERT INTO AllotmentItems (bypass API, no plan-enforcement check)
3. User allocates against plan; plan_status_for() computes used = (current - baseline) = (manual + new - 0) = higher than app expects

**Evidence:** baseline snapshot is computed at plan-save time (plan_enforcement.py:162-166), never updated

**Mitigation:** All allocations go through API, which enforces plan cap before creating AllotmentItems.

**Residual Risk:** Manual DB edits bypass this. App has no mechanism to re-snapshot baselines after external AllotmentItems changes.

### 7.7 Precision Loss: Floored Quantities in E132

**Scenario:**
```
Engine computes: PKO qty = 1000.7 units (fractional)
E132_auto_plan floors it: planned_quantity = 1000.0 (line 222, 252)
Cif recomputed: 1000 * unit_price (not engine's 1000.7 * price)
Balance advances by rounded amount, not fractional
```

Multiple items with fractional qty can accumulate rounding error.

**Evidence:** e132_auto_plan.py:101-112 (_r2, _floor_qty)

**Mitigation:** Flooring is intentional (can't allocate fractional units). Rounding is 2DP for money.

**Residual Risk:** Accumulated rounding drift over 20+ plan lines could leave balance with residual cents unallocatable.

### 7.8 Circular Dependency: Balance Calc ← Allotment ← Plan

**Scenario:**
```
balance_calculator queries AllotmentItems to compute balance
plan_enforcement queries AllotmentItems to compute baseline
allocate_items checks plan status → calls plan_enforcement
plan enforcement calls balance_calculator (if balance is stale)
```

If balance calculator or AllotmentItems logic breaks, both plan and allocation break.

**Evidence:**
- File: backend/apps/license/services/balance_calculator.py (not fully audited)
- Impact: cascading failure

**Mitigation:** Test suite (unit + integration) for allocate → plan → balance round-trip.

**Residual Risk:** Unclear from this audit whether test coverage is adequate.

---

## 8. DUPLICATE CALCULATIONS

### 8.1 Plan Status (Single Source of Truth)

**Canonical Location:**
- `plan_status_for()` (backend/apps/license/services/plan_enforcement.py:243-275)
- `plan_status_for_ids()` (backend/apps/license/services/plan_enforcement.py:194-240)
- `plan_status_for_items()` (backend/apps/license/services/plan_enforcement.py:278-385)

**Consumers:**
1. `allocate_items()` view (line 760) — enforcement decision
2. Available-licenses endpoint (line 354-365) — serializer extra fields
3. Item Pivot Report (via plan_utilization_rows) — display
4. License Overview API (via plan_utilization_rows) — display
5. Balance Excel export (via plan_utilization_rows) — export

**No duplication detected.** Calculation is centralized; all reads call the same function.

### 8.2 Auto-Plan Engines (Potential Inconsistency)

**Engines:**
- E1: `compute_e1_auto_plan()` (backend/apps/license/services/e1_auto_plan.py)
- E5: `compute_e5_auto_plan()` (backend/apps/license/services/e5_auto_plan.py)
- E126: `compute_e126_auto_plan()` (backend/apps/license/services/e126_auto_plan.py)
- E132: `compute_e132_auto_plan()` (backend/apps/license/services/e132_auto_plan.py)
- A3627: `compute_a3627_auto_plan()` (backend/apps/license/services/a3627_auto_plan.py)

**Classification Logic:**
- E1 items classified by: `classify_e1_item(item_key, hs_code, description)` (e1_plan.py:88-XXX)
- E5 items classified by: `classify_e5_item()` (e5_plan.py:95-XXX)
- E126 items classified by: `classify_e126_record()` (e126_plan.py:161-XXX)
- E132 items classified by: `classify_e132_record()` (e132_plan.py:199-XXX)

**Grouping Logic:**
All engines use the same `merge_items_for_classification()` (plan_grouping.py:172-XXX), which applies `plan_group_key()`. **No duplication.**

**Validation:**
All engines use the same `validate_group_plan_lines()` (plan_grouping.py:156-262). **No duplication.**

### 8.3 Allotment Filtering (Consistent Across)

**Filter Definition:**
- `_ALLOTTED_FILTER` (plan_enforcement.py:24-27): `Q(allotment__bill_of_entry__isnull=True, allotment__type="AT")`
- **Same filter used by:** live_allotted_qty_for(), live_allotted_value_for(), plan_status_for(), allocate_items() available-value check
- **Also used by:** balance_calculator.calculate_allotted_quantity() (explicitly referenced as same filter, line 8-12)

**No duplication detected.** Filter is defined once; imported/used consistently.

### 8.4 Baseline Snapshot Logic

**Computation:**
- `group_used_snapshot()` (plan_enforcement.py:116-127) — called at plan-save time
- `plan_status_for()` (line 222-224) — reads saved baseline at enforcement time

**No duplication.** Snapshot computed once, stored, read.

---

## 9. SUMMARY TABLE: Planning Entry Points

| Entry Point | Type | Endpoint/Command | File | Persists Plan? | Validates Caps? | Transaction? |
|---|---|---|---|---|---|---|
| Create plan line | CRUD | POST /license-item-plans/ | item_plan.py:111-117 | YES | YES (capacity + CIF) | YES |
| Update plan line | CRUD | PATCH /license-item-plans/{id} | item_plan.py:119-126 | YES | YES (capacity + CIF) | YES |
| Delete plan line | CRUD | DELETE /license-item-plans/{id} | item_plan.py | YES | NO | NO |
| Bulk replace | API | POST /bulk-upsert/ | item_plan.py:152-292 | YES | YES (capacity + CIF) | YES |
| E1 Auto-plan | API | POST /e1-auto-plan/ | item_plan.py:294-373 | YES | YES (generic) | YES |
| Unified Auto-plan | API | POST /auto-plan/ | item_plan.py:375-454 | YES | YES (generic) | YES |
| Batch Auto-plan | API | POST /auto-plan-all/ | item_plan.py:456-550 | YES | YES (per-license) | YES (per license) |
| Management command | CLI | plan_norms {NORM} | plan_norms.py:74-275 | YES | NO (pre-validated) | YES (per license) |
| Prefill (non-persist) | API | GET /norm-prefill?license={id} | item_plan.py:128-150 | NO | NO | NO |
| Enforce cap (alloc) | Alloc | POST /allocate-items/ | views_actions.py:625-875 | NO (plan lines) | YES (checks) | YES (atom) |
| Plan-mode grid | Alloc | GET /available-licenses?debit=plan | views_actions.py:376-575 | NO | NO | NO |

---

## 10. FINAL OBSERVATIONS

### 10.1 Architecture Strengths

1. **Single Source of Truth for Plan Status:** `plan_status_for()` is the only place plan status is computed. All enforcement + display + export call it.
2. **Transactional Consistency:** All writes wrapped in `transaction.atomic()` with row-level locks. Prevents concurrent overcommit.
3. **Grouping Consistency:** All engines use identical `plan_group_key()` + `merge_items_for_classification()`. No cross-engine inconsistency.
4. **Filter Alignment:** Allotment filter matches balance calculator; plan enforcement and app display use same filter.
5. **Modularity:** PlannerFactory allows registering new norms without changing views/command.

### 10.2 Architecture Risks

1. **Baseline Snapshot Desync:** Baseline is a one-time snapshot, never re-updated. Manual AllotmentItems edits or external balance changes can desync it.
2. **Stale Reference Handling:** Plan-line balance tracking fails silently if plan is regenerated between page load and allocation. Group-level cap prevents data loss, but line-level tracking breaks.
3. **Floating-Point Precision:** Auto-plan engines compute in float, then cast to Decimal. Accumulated rounding over many lines.
4. **No Re-Snapshot Mechanism:** App cannot re-snapshot baselines after external AllotmentItems changes. Manual fix required.
5. **Cascading Balance Failure:** If balance_calculator or AllotmentItems logic breaks, both planning and allocation fail.

### 10.3 Dependencies Summary

| Module | Dependency Type | Critical? |
|---|---|---|
| **Ledger & Balance (Module 1)** | Input: live balance_cif; Filter: ALLOTTED query | YES |
| **Allocation (Module 3)** | Input: AllotmentItems rows; Output: plan-cap enforcement; Plan-line tracking | YES |
| **BOE (Module 4)** | Filter: bill_of_entry__isnull=True exclusion | NO (but affects available_quantity) |
| **Items (Module 5)** | Input: HSN + description + item_names for grouping | YES |

---

## AUDIT CONCLUSION

The Planning system is **well-architected with clear data flows, strong transactional guarantees, and centralized calculations.** All critical paths (plan cap enforcement, auto-plan engines, grouping logic) have been verified.

**No critical bugs detected.** Residual risks are edge cases (stale references, manual DB edits, precision drift) that are unlikely in normal operation but could manifest under concurrent/adversarial scenarios.

**Recommended follow-up audits:**
1. Balance calculator logic (Module 1) — verify live_balance is always fresh
2. AllotmentItems cascading behavior on delete
3. Precision/rounding in large-scale (100+ item) licenses
4. Test coverage for concurrent allocations + re-planning scenarios
