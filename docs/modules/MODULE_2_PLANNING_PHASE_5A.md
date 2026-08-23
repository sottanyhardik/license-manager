# MODULE 2 — PLANNING PHASE 5A
## Discovery & Canonical Design Launch

**Status:** Design Phase (Pre-Implementation)  
**Date:** 2026-08-10  
**Context:** Module 1 (Ledger/Balance) is FROZEN with CanonicalLedgerService pattern; Module 2 depends on Module 1 balance outputs.

---

## 1. BUSINESS SEMANTICS

### 1.1 Core Concepts

**"Planned" (LicenseItemPlan)**
- User-authored, mutable utilization plan for an import item
- Optional split into multiple plan lines per item (e.g., milk → WPC/SWP/DWP)
- Each line has: planned_quantity, unit_price, planned_cif_fc, item_name tag, note
- Stored in `LicenseItemPlan` model — INDEPENDENT of balance/ledger
- Not derived from actual transactions; purely forward-looking intent

**"Available for Plan"**
- Import item's current available_quantity / available_cif_fc (from Module 1 balance)
- = Total Import Quantity/CIF minus (Debited + Allotted)
- Acts as the CEILING for planned_quantity + planned_cif_fc
- Recalculated on every balance refresh; planning constraints adjust dynamically

**"Plan vs Actual" Relationship**
- Plan: what user INTENDS to allocate
- Allotment: what was ACTUALLY allocated
- At alloc-time: cumulative allotments for an item's plan-group may NOT exceed the sum of plan lines
- Plan-cap enforcement: per-group, per-license-cif-pool
- When plan is REPLACED: baseline snapshot resets, used-since-plan resets to 0

**"Planned CIF"** (Two Types — NOT Synonymous)
- **LicenseItemPlan.planned_cif_fc**: USER-ENTERED value on a plan line
- **E1/E5/E132 norm-plan CIF**: DERIVED from DGFT norms, read-only, stored in norm_plan output only
- Both can coexist; not mutually exclusive
- Both are used in availability cap but by different constraints

### 1.2 Priority Rules (Allocation Enforcement Order)

1. **Plan-Group Quantity Cap** (if plan exists for group)
   - Sum of allotted quantity for group ≤ sum of planned_quantity across group lines
   - Applied per physical product (HSN + description)
   - Uses `plan_group_key` grouping (see §4.3)

2. **License-Level CIF Pool Cap** (always)
   - Sum of all planned_cif_fc across entire license ≤ license available_cif_fc
   - Different from plan-group cap — one cap per license, not per group
   - Prevents over-commitment on value dimension at license level

3. **Availability Cap** (if NO plan for group)
   - Falls back to unconstrained availability-based behavior
   - Allot only what's actually available (no plan ceiling)

### 1.3 Overallocation Behavior

**Reject on Allocate:**
- If `sum(LicenseItemPlan.planned_quantity)` for item's group > 0 AND proposed allotment would exceed it
  → return `plan_exceeded: true` error with suggested plan values
- Frontend opens planner when `plan_exceeded` detected
- User may increase plan or reject allocation

**Silent Allow (No Plan):**
- If group has NO plan lines → allocation succeeds if availability allows (no plan cap)

**Allow Plan Regeneration:**
- E1/E5/E132 auto-planners may REPLACE entire plan
- On replace: `baseline_used_quantity/cif` snapshot resets, used-since-plan resets to 0
- Remaining = Original (new plan) - 0 (fresh baseline)

### 1.4 Company vs License Scope

**Plan Scope: LICENSE-LEVEL**
- `LicenseItemPlan.license_id` — denormalized, must stay in sync
- One license = one planning namespace
- Multi-import-item plan-groups within same license share caps

**Allotment Scope: COMPANY-LEVEL**
- Allotments are COMPANY-specific (bill_of_entry or trade company)
- Plan-cap aggregates ACROSS all companies allotting from this license (no company filter)
- Design decision: plan is license intent, not company-specific

---

## 2. CALCULATION OWNERSHIP

### 2.1 Who Owns "Planned Quantity"?

**System:** LicenseItemPlan model  
**Calculation:** User-entered, stored directly as `planned_quantity`  
**Mutated By:**
- Manual CRUD (create/update/delete plan line)
- Bulk upsert (planning panel)
- Auto-planners (E1/E5/E132, A3627, etc.)
- `plan_norms` management command

**Immutable During Allotment:**
- `allocate_items` only decrements `remaining_quantity` (line-level draining balance)
- Does NOT change `planned_quantity` (original target)
- Exception: plan REPLACEMENT (intentional intent change)

**Validation:**
- Must be ≤ import item's available_quantity (+ any previously allotted for this group)
- Must be ≥ 0 (MinValueValidator)
- Cross-line sum must fit within group capacity

### 2.2 Who Owns "Plan Availability"?

**System:** Module 1 Balance Service (CanonicalLedgerService / LicenseBalanceCalculator)  
**Calculation:**
```python
available_quantity = total_import_qty - (debited_qty + allotted_qty)
available_cif_fc = total_export_cif - (debited_cif + allotted_cif)
```

**Who Consumes:**
- `_validate_plan_line_cap()` in item_plan.py view (on CRUD)
- `bulk_upsert` action (planning panel)
- Alloc-time cap check in allocate_items
- Item Pivot Report (shows available-vs-planned)

**Key Dependency:**
- Planning availability is DERIVED, not stored
- Recalculated on every balance refresh
- If balance recalc changes available_qty, plan caps adjust automatically
- No sync issue; availability is read-only input to planning math

### 2.3 Who Owns "Planned CIF"?

**System:** LicenseItemPlan model (user-entered) + Norm Planners (norm-derived)  

**User-Entered `planned_cif_fc`:**
- Stored on each plan line
- User may enter freely or auto-populate via norm-plan endpoint
- No formula; pure user intent
- Validated: must be ≥ 0

**Norm-Derived CIF:**
- E1/E5/E132/A3627 auto-planners compute from DGFT norms + item qty
- Formula: `norm_rate * planned_quantity`
- Emitted as `planned_cif_fc` when saving plan lines
- Read-only; not touched by allotment code

**License-Level CIF Pool Constraint:**
- Sum of planned_cif_fc across entire license must not exceed license available_cif_fc
- Different from per-group quantity cap
- One constraint per license, not per group

### 2.4 Formula Dependencies

```
Plan-Group Quantity Cap Check (allocate_items):
  IF group has plan lines:
    planned_qty_total = SUM(LicenseItemPlan.planned_quantity) 
                        WHERE import_item_id IN group_member_ids
    live_allotted_qty = SUM(AllotmentItems.qty) 
                        WHERE item_id IN group_member_ids 
                        AND bill_of_entry_id IS NULL 
                        AND type = 'AT'
    IF live_allotted_qty + proposed_qty > planned_qty_total:
      REJECT with plan_exceeded error
  ELSE:
    No plan cap; use availability cap only

License CIF Pool Cap Check (item_plan CRUD and bulk_upsert):
  license_planned_cif = SUM(LicenseItemPlan.planned_cif_fc) 
                        WHERE license_id = this_license_id
  license_available_cif = (Module 1 balance)
  IF license_planned_cif > license_available_cif:
    REJECT with value-exceeded error

Plan Utilization (plan_status_for):
  original_quantity = SUM(LicenseItemPlan.planned_quantity) for group
  current_live_allotted = SUM(AllotmentItems.qty) for group (live)
  baseline_used = MIN(LicenseItemPlan.baseline_used_quantity) for group
  used_since_plan = MAX(0, current_live_allotted - baseline_used)
  remaining = original_quantity - used_since_plan
  (same for CIF)
```

---

## 3. GOLDEN SCENARIOS (PRELIMINARY)

### 3.1 Single Item, Single Plan Line

**Setup:**
- License L1 with import item I1 (qty=100kg, cif=1000)
- User creates plan line: qty=80kg, cif_fc=800

**Expected:**
- Plan shows: Original=80, Used=0, Remaining=80
- Alloc qty≤80 succeeds; qty=81 rejected with plan_exceeded
- Delete plan → alloc qty=100 (unconstrained) succeeds

### 3.2 Multiple Plan Lines for Split Item (E132 Milk)

**Setup:**
- License L1, import item I1 (Veg Oil, qty=200kg, cif=2000)
- Auto-plan splits: WPC 60kg/600, SWP 80kg/800, PKO 60kg/600

**Expected:**
- Group plan total: 200kg / 2000 cif
- Allot WPC qty=61 → rejected (exceeds plan)
- Allot WPC qty=60, SWP qty=79, PKO qty=60 → total 199 within cap
- Allot PKO qty=61 → rejected (group would hit 200)
- Each line has own remaining_quantity; decrement independently

### 3.3 Plan vs Actual (Replan Scenario)

**Setup:**
- Original plan: qty=100, cif=1000
- Allot qty=30 (actual)
- User replans: qty=50 (intent change)

**Expected:**
- At re-plan: baseline_used snapshot = current live allotted (30)
- New plan shows: Original=50, Used=30, Remaining=20
- Next alloc: can only add 20 more before hitting new cap
- (Not 70 as if plan was additive)

### 3.4 Company Scope (Multi-Allotment)

**Setup:**
- License L1, item I1 (qty=100)
- Company A allots qty=40
- Company B allots qty=40
- Company C attempts qty=30 with plan=100

**Expected:**
- All allotments are counted in live_allotted_qty (no company filter)
- Company C's allot succeeds if 40+40+30 ≤ 100 plan (yes, total 110 exceeds)
- Actually rejected; plan cap is license-level, not per-company

### 3.5 Overallocation with Plan Missing

**Setup:**
- License L1, item I1 (qty=100)
- NO plan lines for this item

**Expected:**
- Alloc qty=150 rejected (exceeds available qty=100)
- Plan-cap not checked (none exists)
- Availability cap enforced instead

### 3.6 Empty Plan (Create then Delete)

**Setup:**
- Create plan lines, then delete all
- Item now has NO plan

**Expected:**
- Alloc qty=100 succeeds (no plan cap)
- `plan_status_for(item)` returns None (unconstrained)

### 3.7 Large Dataset (100+ items, 10+ plan groups)

**Setup:**
- License with 100 import items
- 15 plan-groups (merged by description)
- Each group has 2-5 plan lines
- Page of 20 items in allocate screen

**Expected:**
- `plan_status_for_items(20)` batches into 3-4 queries (not 100+)
- No N+1 on group_ids_of or aggregate sums
- Performance: <100ms for plan status on paginated grid

### 3.8 Plan Group with Mixed HSN/Description

**Setup:**
- Item S.No 3: HSN 17029020, "Refined Cane Sugar"
- Item S.No 13: HSN 17029020, "Refined Cane Sugar"
- Item S.No 23: HSN 17029020, "Refined Cane Sugar"
- All three are same plan-group (same HSN + normalized description)

**Expected:**
- `plan_group_key` returns same key for all three
- Plan stored on representative (lowest S.No = 3)
- Alloc any of S.No 3/13/23 draws from same group cap
- `group_ids_of` returns [3, 13, 23]

---

## 4. CANONICAL SERVICE DESIGN (PROPOSAL)

### 4.1 CanonicalPlanningService

**Purpose:** Single authoritative source for plan data, mirroring CanonicalLedgerService pattern.

**NOT to be confused with:**
- plan_enforcement (live-allotted aggregates, cap checks)
- plan_grouping (grouping logic only, no state)
- plan_utilization (display/report rows, composition only)

**Core Methods (Proposed):**

```python
class CanonicalPlanningService:
    """Single authoritative source for planning calculations."""
    
    @staticmethod
    def build_canonical_plan_dataset(license_id: int) -> Dict[str, Any]:
        """
        Build complete plan dataset for a license.
        
        Returns:
        {
            'license_id': int,
            'plan_groups': [  # One per physical product (HSN + desc)
                {
                    'group_key': str,  # plan_group_key
                    'representative_item_id': int,
                    'member_item_ids': [int, ...],
                    'description': str,
                    'hs_code': str,
                    'serials': [int, ...],  # sorted serial_numbers
                    'item_names': [{id, name}, ...],
                    'total_import_quantity': Decimal,
                    'total_available_quantity': Decimal,
                    'total_available_cif_fc': Decimal,
                    'plan_lines': [
                        {
                            'id': int,  # LicenseItemPlan.pk
                            'item_name_id': int or None,
                            'item_name_label': str or None,
                            'planned_quantity': Decimal,
                            'unit_price': Decimal,
                            'planned_cif_fc': Decimal,
                            'remaining_quantity': Decimal,
                            'remaining_cif_fc': Decimal,
                            'note': str,
                            'created_on': datetime,
                            'created_by': str,
                        },
                        ...
                    ],
                    'group_plan_summary': {
                        'original_quantity': Decimal,
                        'used_quantity': Decimal,
                        'remaining_quantity': Decimal,
                        'original_cif_fc': Decimal,
                        'used_cif_fc': Decimal,
                        'remaining_cif_fc': Decimal,
                    },
                    'group_availability_check': {
                        'total_planned_qty': Decimal,
                        'total_available_qty': Decimal,
                        'has_capacity': bool,  # planned ≤ available
                    }
                },
                ...
            ],
            'license_plan_summary': {
                'total_planned_quantity': Decimal,  # across all groups
                'total_planned_cif_fc': Decimal,   # across license
                'license_available_cif_fc': Decimal,  # from balance
                'cif_pool_check': {
                    'total_planned_cif': Decimal,
                    'available_cif': Decimal,
                    'pool_valid': bool,  # planned ≤ available
                },
            },
            'validity_checks': {
                'all_groups_valid': bool,
                'cif_pool_valid': bool,
                'errors': [str, ...],  # Any invalid groups/pools
            }
        }
        """
        # Implementation: TBD in Phase 5B
        pass
    
    @staticmethod
    def plan_status_for_group(license_id: int, group_key: str) -> Dict[str, Any]:
        """Original/Used/Remaining for a single plan-group."""
        pass
    
    @staticmethod
    def validate_plan_replacement(license_id: int, new_plan_lines: List[Dict]) -> Dict[str, Any]:
        """
        Validate that a new plan can be saved.
        
        Returns: {valid: bool, errors: [str]}
        Checks:
        - Each line's qty ≤ available qty for its item's group
        - Total license CIF ≤ available CIF
        - All item_ids are in this license
        """
        pass
    
    @staticmethod
    def allocation_cap_check(license_id: int, item_id: int, qty: Decimal, cif: Decimal) -> Dict[str, Any]:
        """
        Enforce plan-cap at alloc-time.
        
        Returns: {allowed: bool, plan_exceeded: bool, plan_status: {...}}
        - plan_exceeded: suggests opening planner
        - plan_status: current Original/Used/Remaining for UI display
        """
        pass
```

### 4.2 Core Methods Needed

**Read-Only Dataset Methods:**
- `build_canonical_plan_dataset(license_id)` — complete plan state
- `plan_status_for_group(license_id, group_key)` — summary for one group
- `list_plan_groups(license_id)` — all groups with basic metadata
- `get_plan_details(import_item_id)` — plan lines for one item's group

**Validation Methods (Pre-Save):**
- `validate_plan_replacement(license_id, new_lines)` — bulk-upsert pre-check
- `validate_plan_line(item_id, planned_qty, cif_fc, exclude_plan_id=None)` — single-line CRUD
- `validate_plan_import(license_id, import_data)` — bulk import validator

**Enforcement Methods (At Alloc-Time):**
- `allocation_cap_check(license_id, item_id, qty, cif)` — return cap status
- `debit_plan_line(plan_line_id, qty_debited, cif_debited)` — decrement remaining_qty/cif

**Bulk Methods (For Performance):**
- `plan_status_for_items(item_ids)` — batched plan status for paginated lists
- `plan_status_for_groups(license_id, group_keys)` — multi-group summary

### 4.3 Dataset Structure

**Core Entity: LicenseItemPlan**
```python
{
    'id': int,
    'license_id': int,
    'import_item_id': int,
    'item_name_id': int or None,
    'planned_quantity': Decimal,
    'unit_price': Decimal,
    'planned_cif_fc': Decimal,
    'remaining_quantity': Decimal,
    'remaining_cif_fc': Decimal,
    'baseline_used_quantity': Decimal,  # snapshot at save-time
    'baseline_used_cif_fc': Decimal,    # snapshot at save-time
    'note': str,
    'created_on': datetime,
    'created_by': User,
}
```

**Computed: Plan Group State**
```python
{
    'group_key': str,  # plan_group_key result
    'member_ids': [int, ...],  # from group_ids_of
    'plan_lines': [LicenseItemPlan, ...],  # all rows for this group
    'original_quantity': Decimal,  # SUM planned_quantity
    'used_quantity': Decimal,  # MAX(0, live - baseline_min)
    'remaining_quantity': Decimal,  # original - used
    'same for CIF': {...},
}
```

### 4.4 Caching Strategy

**Cache Invalidation Triggers:**
1. LicenseItemPlan create/update/delete
   - Invalidate: `plan:license:{license_id}`
   - Invalidate: `plan:group:{license_id}:{group_key}`

2. AllotmentItems create/update/delete (affects live-allotted)
   - Invalidate: `plan:group:{license_id}:{group_key}` (used_quantity changes)
   - Don't invalidate: `plan_lines` themselves (immutable during alloc)

3. License balance recalc (affects availability)
   - Invalidate: `plan:license:{license_id}` (capacity constraints change)

4. E1/E5/E132 auto-plan runs
   - Delete existing plan lines (full replace)
   - Invalidate: `plan:license:{license_id}`

**Cache Keys (Proposed):**
```
plan:license:{license_id}  → full dataset
plan:lines:{license_id}  → just LicenseItemPlan rows
plan:group:{license_id}:{group_key}  → one group's state
plan:status:{license_id}:{item_id}  → plan_status_for result
```

**TTL:** 5-10 minutes (or on-demand invalidation via signals)

### 4.5 Error Handling

**Validation Errors (Pre-Save):**
- Quantity exceeds available → ValidationError with "Qty Exceeded"
- CIF exceeds available → ValidationError with "Value Exceeded"
- Item not in license → ValidationError with "Item not found"
- Negative quantity → ValidationError (validator catches)

**Allocation Errors (At Alloc-Time):**
- Plan exceeded → `plan_exceeded: true` flag + plan_status dict
- (Not a hard failure; suggested action is replan)

**State Errors (Concurrent Modifications):**
- Use `select_for_update` on License + Plan-Group items
- Mirrors `_validate_plan_line_cap` in item_plan.py
- Prevents race conditions on cross-line totals

---

## 5. CONSUMERS IDENTIFIED

### 5.1 API Endpoints

**LicenseItemPlanViewSet** (`backend/apps/license/views/item_plan.py`)
- `GET /api/license-item-plans/?license=<id>` — list plan lines
- `POST /api/license-item-plans/` — create single line
- `PATCH /api/license-item-plans/<id>/` — update single line
- `DELETE /api/license-item-plans/<id>/` — delete single line
- `POST /api/license-item-plans/bulk-upsert/` — planning panel save
- `GET /api/license-item-plans/norm-prefill/?license=<id>` — auto-plan suggestions

**AllotmentActionViewSet** (`backend/apps/allotment/views_actions.py`)
- `POST /api/allotments/<id>/allocate_items/` — calls plan-cap check
- `GET /api/allotments/<id>/available_licenses/` — shows plan status in grid

**LicenseDetailViewSet** (`backend/apps/license/views/license.py`)
- `GET /api/licenses/<id>/` — includes `plan_utilization` key in response

### 5.2 UI Screens

**Planning Panel / Modal** (PlanningEditor.tsx)
- Read: plan_utilization from license detail
- Render: one row per plan-group (uses plan_utilization_rows output)
- Write: bulk-upsert endpoint
- Shows: Original / Used / Remaining for each group

**Item Plan Tab** (ItemPlanTab.tsx)
- CRUD single plan lines
- Per-item view (may not be grouped)
- Shows validation errors from _validate_plan_line_cap

**Allocate Items Screen** (AllocationPanel.tsx)
- Read: plan_status in available-licenses grid
- Constraint: if plan_exceeded error, opens planner
- Shows: Planned Qty / $ alongside Available Qty / $

**License Detail View**
- Embedded: Plan Utilization section
- Read: plan_utilization_rows from detail response
- Show: table of groups with plan status

### 5.3 Reports

**Item Pivot Report** (`backend/apps/license/views/item_pivot_report.py`)
- Read: planned_import_items ledger field
- Shows: per-item plan lines and their consolidation
- Uses: plan_group_key / merge_key for merging cells
- Displays: planned qty vs actual (side-by-side)

**Planned Report** (`backend/apps/license/views/planned_report.py`)
- Read: plan_utilization_rows
- Shows: plan status per group + breakdown by plan line
- Excel + PDF formats

**License Balance Excel** (`backend/apps/license/services/exporters/license_balance_excel.py`)
- Read: plan_utilization via CanonicalPlanningService (TBD)
- Section: "Plan Utilization" tab
- Shows: groups + plan status + per-line summary

### 5.4 Exports

**Ledger PDF** (`backend/apps/license/ledger_pdf.py`)
- Read: plan_utilization_rows (if available)
- Section: "Planned Utilization" (if plan exists)
- Shows: group summary + line items

**Balance Excel** (as above)
- Multiple sections for plan data
- "Plan Utilization" + "Plan Lines" sheets

---

## 6. DEPENDENCIES ON MODULE 1 (LEDGER/BALANCE)

### 6.1 How Planning Uses Balance

**Availability Ceiling:**
```
available_quantity = total_import_qty - (debited_qty + allotted_qty)
available_cif_fc = total_export_cif - (debited_cif + allotted_cif)

Plan capacity constraints:
  planned_qty_per_group ≤ available_qty (live sum)
  planned_cif_fc_total ≤ available_cif_fc (license total)
```

**Real-Time Recalc:**
- Module 1 recalculates balance on every BOE/allotment/trade change
- Planning availability updated on next query (live, not cached)
- No risk of stale availability limiting plans

**Dependency Strength:** HARD
- Cannot plan more than available (will always reject in pre-save validation)
- Planning code directly calls `ItemBalanceCalculator.calculate_available_quantity`

### 6.2 Is Balance Authoritative for Availability?

**Yes, ABSOLUTELY.**

- Balance is read-only source of truth for what's available
- Planning does NOT influence balance calculation
- (Planned ≠ Allocated; only actual allotments affect balance)
- If balance changes (e.g., BOE hidden), plan availability recomputes

### 6.3 What About Allocated Items?

**Allocated Items affect BOTH:**

1. **Balance (Module 1):**
   - `allotted_quantity` / `allotted_value` in available calc
   - Updates via signal on AllotmentItems.save

2. **Planning (Module 2):**
   - Live-allotted qty used for "Used Since Plan" calculation
   - Line-level `remaining_quantity` decremented by allocate_items
   - Updates direct write (no signal)

**Consistency Model:**
- Both use same AllotmentItems data
- Both use same filter: `bill_of_entry IS NULL AND type = 'AT'`
- (So no divergence between "available qty" and "used plan qty")

**Key Difference:**
- Balance: cares about debited + allotted (reduces available)
- Planning: cares about allotted only (used since plan)

---

## 7. RISKS & CONFLICTS

### 7.1 Existing Duplicate Planning Engines

**CURRENT STATE (Problem):**
Multiple planning systems exist, all partially overlapping:

1. **Manual Planning (LicenseItemPlan CRUD)**
   - User creates plan lines via API/UI
   - Full flexibility; no constraints
   - No built-in template/suggestion

2. **Auto-Plan Engines:**
   - `e1_auto_plan.py` — E1 norm-based (milk, oil, sugar, etc.)
   - `e5_auto_plan.py` — E5 norm-based
   - `e132_auto_plan.py` — E132 (large multi-item licenses)
   - `a3627_auto_plan.py` — A3627 (Vegetable Oil specific)
   - `e126_auto_plan.py` — E126 (new, under development)
   - `milk_planner.py` — ad-hoc milk-specific logic

3. **Legacy Planning (plan_norms command):**
   - Batch planning via management command
   - Generates plan_lines from norms (superseded by auto-plan)

4. **Existing plan_reporting / plan_utilization:**
   - Display logic only, not authoritative
   - Composition of plan_enforcement + plan_grouping

**CONFLICT ZONES:**

- **Which planner runs when?** — Unclear precedence (E1 vs E132 vs A3627)
- **Plan merge semantics:** Do auto-plans merge with manual plans, or replace entirely?
- **Norm-plan CIF vs user-entered CIF:** Different sources, both stored in planned_cif_fc
- **Group consolidation:** plan_grouping does this at display-time; auto-planners do at save-time

### 7.2 API vs UI Discrepancies

**Current Issues:**

1. **Batch Validation vs Single-Line:**
   - bulk_upsert calls `validate_group_plan_lines` (cross-line checks)
   - CRUD endpoints call `_validate_plan_line_cap` (same checks but inline)
   - If validation logic differs → inconsistent saves

2. **Plan Status Calculation:**
   - `plan_status_for` used by API (to return in response)
   - Frontend may compute its own version via grouping
   - If formulas drift → UI shows different "Used/Remaining" than API

3. **Group Key Derivation:**
   - Backend: `plan_grouping.plan_group_key`
   - Frontend: `PlanningEditor.tsx` or `groupKeyOf`
   - If normalization differs → groups split/merge unexpectedly

### 7.3 Performance Pitfalls

**Known Issues:**

1. **N+1 on group_ids_of:**
   - `plan_status_for(item)` calls `group_ids_of(item)` (1 query per item)
   - `plan_status_for_items` batches this; older code may not use it
   - Allocate screen pagination: could hit 100s of queries if using per-item loop

2. **Concurrent Alloc + Replan Race:**
   - Two requests: one allocating, one replanning
   - Without `select_for_update`, both may read stale baseline snapshot
   - Solution: already in place (`_validate_plan_line_cap` locks license)
   - Risk: inconsistent if lock not held during alloc-time check

3. **Live-Allotted Calculation:**
   - `live_allotted_qty` sums AllotmentItems per call (no cache)
   - If called 100x during single request → redundant queries
   - Solution: pre-fetch and cache in memory during request

### 7.4 Legacy Planner References

**Code Scan Results:**

Files still referencing old planning logic:
- `plan_norms.py` (management command) — uses legacy plan-creation logic
- Some test fixtures may assume old plan structure
- Old "planned CIF" from E1/E5 may be stored separately (not in LicenseItemPlan)

**Cleanup Needed:**
- Audit which planners are actually used in production
- Retire unused auto-planners (consolidate to one per norm type)
- Migrate plan_norms command to use new service

### 7.5 Hidden Assumptions & Edge Cases

**1. Plan-Group Merging:**
- `plan_grouping.plan_group_key` is the merge definition
- But old code may have created plan lines before HSN was standardized
- Result: plans exist on separate serial numbers instead of being merged
- Risk: plan cap checked on one serial but allocation done on another

**2. CIF Pool vs Group Cap:**
- Two independent caps (group qty + license cif)
- If license has 10 groups, can be valid for 9 groups but invalid license-wide
- Frontend may not surface the "license cif exceeded" constraint clearly

**3. Empty Plan Semantics:**
- Item with no plan lines → unconstrained (same as if plan never existed)
- But semantically different from "plan was never created" vs "plan was deleted"
- No distinction in current data model

**4. Plan Line Deletion:**
- When user deletes a plan line from multi-line group
- Does group plan cap shrink? (Yes)
- Does allocation already-made against that line get "credit"? (No, still counts live-allotted)
- Risk: user may be confused about why Remaining shows negative

**5. Baseline Snapshot Reliability:**
- `baseline_used_quantity` snapshot taken at plan-save time
- If `group_used_snapshot` query fails or returns wrong data
- Entire Used/Remaining calculation is wrong forever
- No validation that baseline is reasonable

---

## 8. IMPLEMENTATION CONSTRAINTS & DECISIONS

### 8.1 Pre-Requisites for Phase 5B

1. **Finalize Planner Precedence**
   - Which auto-planner takes precedence? (E1? E132? A3627?)
   - OR: support all; let user choose (radio button in UI)
   - Decision needed before implementing plan replacement validation

2. **Lock Down Plan Group Key**
   - Audit all existing plans for HSN inconsistencies
   - Decide: backfill old plans to consolidated groups, or leave as-is?
   - Impacts: plan_group_key must be deterministic going forward

3. **Norm CIF Source Decision**
   - User-entered `planned_cif_fc` vs Norm-derived `planned_cif_fc` — same field, two sources
   - Solution options:
     a) Keep both (current); add `cif_source` enum field to distinguish
     b) Separate fields: `planned_cif_fc` (user) + `norm_cif_fc` (read-only)
     c) Deduplicate: norm-plan only, user edits after auto-plan

4. **Caching Strategy**
   - Request-lifetime cache (cleared per request)? Or shared cache (Redis)?
   - If shared: invalidation hooks needed on AllotmentItems + License balance changes
   - Decision: impacts response time on allocate grid

### 8.2 Database State Assumptions

**Must Verify:**
1. All LicenseItemPlan rows have valid import_item_id (foreign key constraint)
2. All baseline_used_quantity values are ≥ 0 (no data corruption)
3. No orphaned plan lines (import_item deleted, but plan row remains)
4. License denormalization is in sync (plan.license_id == import_item.license_id)

**Migrate If Needed:**
- Add index on (license_id, created_on) for fast date-filtered queries
- Add constraint: planned_quantity + planned_cif_fc ≥ 0
- Backfill remaining_quantity for null rows (set = planned_quantity)

---

## 9. CANONICAL SERVICE PATTERN (ALIGNMENT WITH MODULE 1)

### 9.1 CanonicalLedgerService as Precedent

Module 1 established pattern:
```python
class CanonicalLedgerService:
    @staticmethod
    def build_canonical_ledger_dataset(license_id, license_type) -> Dict:
        """Single authoritative source."""
        # Fetch + normalize data
        # Calculate + classify
        # Return complete dataset
```

### 9.2 Proposed CanonicalPlanningService (Same Pattern)

```python
class CanonicalPlanningService:
    @staticmethod
    def build_canonical_plan_dataset(license_id) -> Dict:
        """Single authoritative source."""
        # Fetch plan rows + import items
        # Group by plan_group_key
        # Calculate utilization (original/used/remaining)
        # Validate constraints
        # Return complete dataset
```

**Key Alignment:**
- Single method for complete dataset
- All consumers (API, UI, reports) call this one method
- Immutable return (dict, no side effects)
- Cached invalidation via signals
- Tested against golden scenarios

---

## 10. RECOMMENDED NEXT STEPS (PHASE 5B)

### 10.1 Immediate Actions

1. **Resolve Planner Precedence** (CRITICAL)
   - Product decision: E1 vs E132 vs A3627 vs all
   - Update plan_norms command and auto-plan wiring

2. **Validate Plan Group Key** (CRITICAL)
   - Audit DB: any plans on separate serials that should be merged?
   - Plan backfill or grandfathering strategy

3. **Audit Existing Planners**
   - Which auto-planners actually used in production?
   - Retire unused ones (clean up imports/tests)
   - Document the chosen plan engine(s)

4. **Create Golden Dataset** (CRITICAL)
   - 14-20 test cases covering all scenarios in §3
   - Real data + synthetic data
   - Used to validate CanonicalPlanningService

### 10.2 Design Decisions Needed

1. **Caching Strategy**
   - Request-lifetime or shared Redis?
   - Invalidation hooks location?

2. **CIF Source Clarification**
   - One field (current) or two fields (cif + cif_source)?
   - Backfill existing norm-plans?

3. **API Response Structure**
   - Include plan_utilization in license detail? (Yes, keep)
   - Add plan_status to each item in available-licenses grid? (Pending batch query)

### 10.3 Implementation Phase 5B

1. **CanonicalPlanningService Class**
   - Core methods (§4.1 methods list)
   - Dataset structure (§4.3)
   - Error handling (§4.5)

2. **Refactor Existing Code to Use Service**
   - item_plan.py views → use service validation
   - available_licenses grid → use batch plan_status
   - plan_utilization_rows → call service once, use result

3. **Test Coverage**
   - Golden scenarios (§3) as pytest cases
   - Performance benchmarks (allocate grid with 100+ items)
   - Concurrency tests (replan + allocate race condition)

4. **Documentation**
   - Service docstrings (parameter semantics)
   - Consumer guide (how to call service)
   - Troubleshooting (common errors)

---

## 11. SUMMARY OF KEY FINDINGS

| Finding | Impact | Resolution |
|---------|--------|-----------|
| Multiple overlapping planners exist | High risk of precedence confusion | Establish planner precedence; retire unused ones |
| Plan group key not consistently applied to old data | Medium risk of split/merged groups | Backfill or document grandfathering |
| Norm CIF source ambiguous (user vs auto) | Low risk; both stored in same field | Add cif_source enum or separate field |
| No single authoritative plan service | High risk of divergence | Build CanonicalPlanningService (Phase 5B) |
| Allocation cap check uses select_for_update but plan CRUD may not | Medium risk of race condition | Ensure all write paths use same locking |
| Performance: N+1 on group_ids_of | Medium risk on large datasets | Use plan_status_for_items (batching) |
| Empty plan semantics unclear | Low risk; current behavior OK | Document: no plan = unconstrained |
| Planned CIF vs available CIF same pool | By design; working as intended | Keep current; document in service |

---

## APPENDIX A: FILE INVENTORY

**Core Planning Files:**
- `models/core.py:LicenseItemPlan` — data model
- `services/plan_enforcement.py` — cap checks, status calculation
- `services/plan_grouping.py` — HSN+description merging
- `services/plan_utilization.py` — display rows
- `services/plan_reporting.py` — ledger export
- `views/item_plan.py` — CRUD API + bulk-upsert

**Auto-Planners:**
- `services/e1_auto_plan.py`, `e5_auto_plan.py`, `e132_auto_plan.py`, `a3627_auto_plan.py` — norm-based
- `services/norm_plan.py` — norm detection + selection
- `services/planner_factory.py` — dispatch to correct planner

**Consumers:**
- `views/license.py:LicenseDetailsViewSet` — includes plan_utilization
- `views/item_pivot_report.py` — Item Pivot Report
- `views/planned_report.py` — Planned Report
- `views_actions.py:allocate_items` — plan-cap enforcement
- `services/exporters/license_balance_excel.py` — Excel export
- `ledger_pdf.py` — Ledger PDF

**Tests:**
- `tests/test_plan_enforcement.py` — cap checks
- `tests/test_plan_grouping.py` — grouping logic
- `tests/test_item_plan_*.py` — CRUD validation
- `tests/test_*_auto_plan.py` — planner tests

---

## APPENDIX B: BUSINESS RULES MATRIX

| Rule | Enforced Where | Module | Error Code |
|------|-----------------|--------|-----------|
| Plan group qty ≤ available | allocate_items | Planning + Balance | plan_exceeded |
| License total CIF ≤ available | item_plan CRUD + bulk_upsert | Planning + Balance | value_exceeded |
| Plan line qty ≤ 0 rejected | model validator | Planning | validation_error |
| Baseline snapshot stable | plan_enforcement._baseline | Planning | (internal) |
| No plan = unconstrained | allocate_items fallback | Planning | (silent) |
| Re-plan resets used | plan_enforcement save | Planning | (internal) |
| Group ID from representative | plan_grouping.group_ids_of | Planning | (consistency) |
| Live allotted uses AT filter | plan_enforcement filters | Planning + Allotment | (consistency) |

