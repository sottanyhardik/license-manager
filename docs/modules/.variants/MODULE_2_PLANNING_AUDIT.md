# MODULE 2 FORENSIC AUDIT: Planning System
## License Manager — Planning / Auto-Planning Engine

**Date:** 2026-08-10  
**Scope:** Planning model, business rules, calculations, data flows, transactions, and risks  
**Status:** Complete Execution Phase

---

## 1. ENTRY POINTS

### 1.1 Management Command: `plan_norms`

**File:** `backend/apps/license/management/commands/plan_norms.py`  
**Entry point:** Line 109, `handle()` method

**Usage:**
```bash
python manage.py plan_norms E1                          # Plan all E1 licenses with positive balance
python manage.py plan_norms E1 --all                    # Re-plan even fully-planned licenses
python manage.py plan_norms E1 --license 3411007711    # Single license
python manage.py plan_norms E1 --dry-run               # Compute without saving
```

**Process flow (lines 109-275):**
1. Validates norm code against `PlannerFactory.supported_norms()` (line 116)
2. Builds queryset: active licenses with `import_license__items` prefetched (lines 142-158)
3. Computes live balance via `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()` (lines 160-162)
   - **CRITICAL:** Uses live balance, NOT cached `license_obj.balance_cif` (comment BL-LEDGER-02, line 137)
4. For each license:
   - Checks eligibility: `live_balance > 0` (line 172)
   - Detects norm at runtime: `detect_norm(lic)` (line 178)
   - Checks if already planned (≥99% coverage): `_is_fully_planned()` (line 188)
   - Runs planner: `PlannerFactory.run(lic, norms_class)` (line 198)
   - **If dry-run:** prints plan without saving (line 208)
   - **If commit:** wraps save in `transaction.atomic()` (line 220-221)
5. Returns counters: total, skipped_norm, already_planned, succeeded, failed

**Error handling:** Catches all exceptions per-license (line 228), logs reason, continues to next

### 1.2 API Endpoints: `LicenseItemPlanViewSet`

**File:** `backend/apps/license/views/item_plan.py`  
**Class:** `LicenseItemPlanViewSet` (line 99)

**Endpoints:**
- `POST /api/license-item-plans/norm_prefill/` — Line 129
  - Pre-fills plan form with norm classification (E1, E5, E126, E132)
- `POST /api/license-item-plans/bulk_upsert/` — Line 153
  - Manual bulk upsert: replaces entire plan for a license (lines 153-293)
- `POST /api/license-item-plans/e1_auto_plan/` — Line 295
  - **DEPRECATED:** E1-specific auto-plan (superseded by unified `auto_plan/`)
- `POST /api/license-item-plans/auto_plan/` — Line 376
  - Universal auto-plan: runs `PlannerFactory` for any supported norm
- `POST /api/license-item-plans/auto_plan_all/` — Line 457
  - Batch auto-plan: processes all licenses of a given norm

**Permission:** `LicensePermission` (line 107) — all endpoints require license-read and license-write roles

---

## 2. DATA FLOW

### 2.1 Model: `LicenseItemPlan`

**File:** `backend/apps/license/models/core.py`  
**Class:** Lines 1181-1286

**Schema:**
```
LicenseItemPlan
├── import_item (FK → LicenseImportItemsModel) — CASCADE, db_index=True
├── item_name (FK → ItemNameModel, nullable) — SET_NULL [optional split label]
├── license (FK → LicenseDetailsModel, nullable) — CASCADE [denormalized, db_index=True]
├── planned_quantity (Decimal 15,3, default 0.000) — [immutable original]
├── unit_price (Decimal 15,2, default 0) — [immutable original]
├── planned_cif_fc (Decimal 15,2, default 0) — [immutable original]
├── planned_cif_inr (Decimal 15,2, nullable)
├── remaining_quantity (Decimal 15,3, nullable) — [live, drains on allocate]
├── remaining_cif_fc (Decimal 15,2, nullable) — [live, drains on allocate]
├── baseline_used_quantity (Decimal 15,3, default 0) — [snapshot at save time]
├── baseline_used_cif_fc (Decimal 15,2, default 0) — [snapshot at save time]
└── note (Char 500, nullable)
```

**Indexes:**
- `fields=["license"]` (line 1277)
- `fields=["import_item"]` (line 1277)

**Denormalization:** Line 1282, `save()` auto-populates `license_id` from `import_item.license_id`

### 2.2 Aggregation: `plan_status_for(item)`

**File:** `backend/apps/license/services/plan_enforcement.py`  
**Function:** Lines 243-276

**Single-item status (returns dict | None):**
```python
{
    "original_quantity": Decimal,        # Sum of planned_quantity for group
    "used_quantity": Decimal,            # Current allotments - baseline snapshot
    "remaining_quantity": Decimal,       # original - used
    "original_cif_fc": Decimal,          # Sum of planned_cif_fc for group
    "used_cif_fc": Decimal,              # Current allotments - baseline snapshot
    "remaining_cif_fc": Decimal,         # original - used
}
```

**Calling sequence:**
1. `group_ids_of(item)` — Get all import items in item's plan-group (same HSN + description)
2. `plan_status_for_ids(gids)` — Aggregates:
   - `planned_totals_for(gids)` (line 228) — Sum of `planned_quantity`/`planned_cif_fc`
   - `live_allotted_qty_for(gids)` (line 229) — Sum of `AllotmentItems.qty` where non-BOE + type=AT
   - `live_allotted_value_for(gids)` (line 230) — Sum of `AllotmentItems.cif_fc` where non-BOE + type=AT
   - Baseline snapshot: `MIN(baseline_used_quantity)` / `MIN(baseline_used_cif_fc)` across group (lines 222-224)
3. Computes Used = max(0, current_live - baseline) (lines 231-232)
4. Computes Remaining = original - used (lines 236-239)

**Returns `None`:** No `LicenseItemPlan` rows for group at all → item is unconstrained (falls back to availability-based behavior)

### 2.3 Save/Replace Cycle: `save_plan_lines_for_license()`

**File:** `backend/apps/license/services/plan_enforcement.py`  
**Function:** Lines 130-191

**Input:** `license_obj`, `lines` (list of dicts), `delete_existing=True`

**Dict schema per line:**
```python
{
    "import_item": int,                  # Required
    "item_name": int | None,             # Optional
    "planned_quantity": Decimal,
    "unit_price": Decimal,
    "planned_cif_fc": Decimal,
    "note": str | None,
    "remaining_quantity": Decimal | None,  # If None, defaults to planned_quantity
    "remaining_cif_fc": Decimal | None,    # If None, defaults to planned_cif_fc
}
```

**Atomic operation (lines 168-191):**
1. **If `delete_existing=True`** (default): Delete all existing `LicenseItemPlan` rows for license (line 169)
2. For each line:
   - Compute `baseline_qty`, `baseline_val` = `group_used_snapshot(item)` (lines 173, 162-166)
     - Calls `live_allotted_qty_for(gids)` + `live_allotted_value_for(gids)` at that moment
   - Create new `LicenseItemPlan` row with:
     - `planned_quantity`, `unit_price`, `planned_cif_fc` (immutable)
     - `remaining_quantity`, `remaining_cif_fc` (live, defaults to planned if not supplied)
     - `baseline_used_quantity`, `baseline_used_cif_fc` (snapshots stamped NOW)
     - `note` (optional)

**Why baseline snapshot:** Lines 258-266
- Re-planning resets Used to 0 and Remaining to new Original, even when prior allotments exist
- Timestamp filtering (`AllotmentItems.created_on`) fails because `allocate_items` amends existing rows (qty += ...) in-place, never advancing `created_on`
- Snapshot = "how much was live-allotted when this plan was saved"; doesn't care HOW that total moved, only that it did

### 2.4 Enforcement: `allocate_items()` in Allotment View

**File:** `backend/apps/allotment/views_actions.py`  
**Method:** Lines 625-876, `@transaction.atomic` decorator required

**Plan-cap check (lines 744-785):**
1. Gets plan status: `plan_status_for(license_item)` (line 761)
2. If plan exists (`plan_status is not None`):
   - Check: `(used_quantity + qty) ≤ original_quantity` (line 763)
   - Check: `(used_cif_fc + cif_fc) ≤ original_cif_fc` (line 764)
   - If either exceeds: return `plan_exceeded=True` error (lines 773-784)
3. If no plan (`plan_status is None`): falls through to availability-based behavior

**Plan-line balance tracking (lines 820-852, triggered by `plan_line_id` in request):**
```python
# Sent by Plan-mode grid when allocating from a specific split
plan_line_id = allocation.get('plan_line_id')
if plan_line_id:
    plan_line = LicenseItemPlan.objects.select_for_update().get(id=plan_line_id)
    current_remaining = plan_line.remaining_quantity or plan_line.planned_quantity
    new_remaining_qty = max(Decimal('0'), current_remaining - qty)
    plan_line.remaining_quantity = new_remaining_qty
    plan_line.remaining_cif_fc = new_remaining_qty * plan_line.unit_price  # ← CALCULATION
    plan_line.save(update_fields=['remaining_quantity', 'remaining_cif_fc'])
```

**CRITICAL:** `remaining_cif_fc` is recalculated from `remaining_quantity * unit_price` (line 844)
- This introduces rounding/precision drift if `unit_price` is not exact
- Example: `100.333 * 0.99 = 99.32967` → stored as `99.33` (rounded up) → next decrement uses stale price

---

## 3. CALCULATIONS

### 3.1 Planning Engines: Norm-Specific Calculation

**Architecture:** `PlannerFactory` dispatch pattern

**Registry (planner_factory.py, lines 40-44):**
```python
_REGISTRY = {
    'E1':    compute_e1_auto_plan,
    'E5':    compute_e5_auto_plan,
    'E126':  compute_e126_auto_plan,
    'E132':  compute_e132_auto_plan,
    'A3627': compute_a3627_auto_plan,
}
```

**Common signature:** `compute_<norm>_auto_plan(license_obj) → (lines, remaining_cif)`

### 3.2 E1 (Confectionery) — Most Complex

**File:** `backend/apps/license/services/e1_auto_plan.py`  
**Function:** `compute_e1_auto_plan()` (lines 96-178)

**Input:** `license_obj` (LicenseDetailsModel)

**Process:**
1. **Ensure item names exist** (line 101): Create any missing `ItemNameModel` rows for 9 E1-specific names
2. **Fetch live balance** (lines 110-113):
   ```python
   balance_cif = Decimal(str(
       license_obj.get_balance_cif  # Live property
       if license_obj.get_balance_cif is not None 
       else (license_obj.balance_cif or 0)  # Fallback to cached
   ))
   ```
3. **Classify items** (lines 126-134): Call `classify_e1_item(item_names, hs_code, description)` per import item
   - Returns category key (9 categories) or None
   - Buckets by category
4. **Merge by group** (lines 136-145): For each bucket, group items by `merge_items_for_classification()`
   - Merges by HSN + description (same as `plan_group_key`)
   - Returns `representative_id`, `available_quantity` per group
5. **Call shared engine** (line 147): `plan_e1_items(items, balance_cif, min_plan_qty=50)`
   - Per-item classification in `E1Item(key=rep_id, category=cat, qty=available)`
   - Runs waterfall algorithm in `e1_plan.py` (see 3.3 below)
   - Returns `E1PlanResult` with `.lines`, `.remaining_cif`
6. **Map to DB shape** (lines 150-159):
   - Each `E1PlanLine` in result → dict with `import_item`, `item_name` (mapped via STEP_ITEM_NAME), `planned_quantity`, `unit_price`, `planned_cif_fc`, `note`
7. **Validate group totals** (lines 161-177):
   - Call `validate_fresh_plan_lines(group_lines, available_qty)` per group
   - Checks: non-negative, sum ≤ available (line 167)
   - If validation fails: logs warning, skips group entirely

**Output:** `(lines, remaining_cif)` where `remaining_cif = float(result.remaining_cif)`

**Item names generated (E1 waterfall steps):**
```python
STEP_ITEM_NAME = {
    'OTHER CONFECTIONERY INGREDIENTS': 'OTHER CONFECTIONERY INGREDIENTS - E1',
    'COCOA MASS': 'FRUIT/COCOA - E1',
    'DWP': 'DWP - E1',
    'SWP': 'SWP - E1',
    'EGG ALBUMIN': 'WPC - E1',
    'FRUIT JUICE': 'FRUIT JUICE - E1',
    'TARTARIC ACID': 'CITRIC ACID / TARTARIC ACID - E1',
    'ALUMINIUM FOIL': 'ALUMINIUM FOIL - E1',
    'POLYPROPYLENE': 'PP - E1',
}
```

### 3.3 E1 Waterfall Algorithm

**File:** `backend/apps/license/services/e1_plan.py`  
**Function:** `plan_e1_items(items, balance_cif, min_plan_qty)` — NOT SHOWN IN AUDIT (file too large)

**Documented behavior (from e1_auto_plan.py comments):**
- Bucket items by category (9 categories, processed in order)
- Allocate balance sequentially per category (Step 1 → Step 9)
- Milk split (DWP/SWP/WPC) uses `optimal_milk_split()` from `auto_plan_shared.py`
- Each item must have ≥50 units to be planned (MIN_PLAN_QTY)
- Returns remaining balance after all allocations

**Validation guarantee (lines 161-177):**
- `validate_fresh_plan_lines()` ensures waterfall never produces negative or over-available totals
- If validation fails: **entire group is skipped** (no partial plans)

### 3.4 E126 (Oils/Fats) and E132 (Spices)

**Similar architecture:**
- File: `e126_auto_plan.py`, `e132_auto_plan.py`
- Call shared engine: `plan_e126_items()`, `plan_e132_items()`
- Price-ceiling validation: `validate_group_plan_lines()` (enforces max rates per item-group)
- Min plan qty: 50 units

### 3.5 A3627 (Rutile) — Special Case

**File:** `backend/apps/license/services/a3627_auto_plan.py`

**Unique calculation (lines 162-204):**
- Fixed rate: 1000 INR/kg (per business rule)
- Allocates entire license to single line
- Auto-detects category via `_matched_ids_by_category()` (lines 129-141)
- No validation: assumes business rule guarantees correctness

---

## 4. BUSINESS RULES

### 4.1 Grouping & Representativeness

**Rule:** Import items grouped by (HSN, normalized_description) — the `plan_group_key`

**File:** `backend/apps/license/services/plan_grouping.py`, lines 73-86

**Grouping logic:**
- IF description present: `f"{hsn}|{desc}"`
- ELSE IF item_names present: `f"{hsn}|N:{sorted_names}"`
- ELSE: `f"ID:{item_id}"` (never merge undescribed items)

**Representativeness:** Group stored on lowest serial number import item (line 22-24)

**Evidence (plan_enforcement.py):**
- Plan cap enforces SUM across group (lines 229-230): `live_allotted_qty_for(gids)`, `live_allotted_value_for(gids)`
- Plan display uses same grouping (plan_utilization.py, plan_reporting.py)
- Split rows (Plan view) show same grouping per row

### 4.2 Min Plan Qty

**Rule:** Import items with <50 units never planned

**Enforcement:**
- E1: MIN_PLAN_QTY = 50 (line 42, e1_auto_plan.py)
- E126: MIN_PLAN_QTY = 50 (imported in e126_auto_plan.py)
- E132: MIN_PLAN_QTY = 50 (imported in e132_auto_plan.py)
- A3627: No min check (allocates entire license)

**Consequence:** Small leftover items remain unconstrained (fall back to availability-based behavior)

### 4.3 Plan Cap: Exhaustion + Remaining

**Rule:** Cumulative allotment for a group ≤ original planned qty/CIF-FC

**Enforcement:**
- Check at allocate-time (views_actions.py, lines 763-764)
- Uses `plan_status_for()` (single source of truth)
- Used = (current live allotted) - (baseline snapshot at plan creation)
- Remaining = Original - Used

**Edge case (lines 258-266, plan_enforcement.py):**
- Re-planning resets Used=0, Remaining=Original even if prior allotments exist
- Example: Plan 1000, allocate 700, re-plan to 800 → Used=0, Remaining=800 (user intends new target)
- Without baseline snapshot: Remaining would stay 300, permanently blocking further allocation

### 4.4 Baseline Snapshot at Plan Creation

**Rule:** Every plan group gets MIN(baseline_used_qty/cif) snapshot at save time

**File:** plan_enforcement.py, lines 162-166

**Trigger:** `save_plan_lines_for_license()` computes snapshot via `group_used_snapshot(item)`
- Calls `live_allotted_qty_for(gids)` / `live_allotted_value_for(gids)` at that moment
- Stamps same baseline on every row in group

**Why MIN:** (line 223) `baseline = plans.aggregate(bq=Min("baseline_used_quantity"), ...)`
- If group has 3 items, all 3 get same MIN baseline
- Ensures "used since plan" calculation is consistent across group

### 4.5 Plan vs. Availability: Two Modes

**No plan on item/group:**
- Allotment capped by `available_quantity` / `available_value_calculated` (live)
- Used by: Actual-mode allocations, default behavior

**Plan exists on item/group:**
- Allotment capped by MIN(available, remaining_planned)
- Used by: All allocations (whether Actual-mode or Plan-mode)

**Evidence (allocate_items):**
- Availability check: lines 696-702, 724-729
- Plan check: lines 762-784
- Plan check executes AFTER availability check (nested, not either-or)

### 4.6 Plan-line balance tracking (Plan view only)

**Rule:** When allocating via Plan view with `plan_line_id`, decrement that line's own remaining balance

**Motivation (lines 821-831, views_actions.py):**
- Real debits have no item_name
- When item has 2+ plan lines (E132 veg oil → PKO + Cheese), can't tell which split this debit came from
- Plan-mode grid knows and sends `plan_line_id` → use it to decrement that specific line

**Implementation (lines 836-851):**
- SELECT_FOR_UPDATE on line (no concurrent drains)
- Decrement: `remaining_qty = max(0, current - qty)`
- Recalculate: `remaining_cif = remaining_qty * unit_price`
- **NOTE:** This recalculation can drift if unit_price is not exact divisor

---

## 5. DEPENDENCIES

### 5.1 Module 1 (Balance/Ledger)

**Critical dependency:** Planning uses LIVE balance, not cached

**Evidence (plan_norms.py, lines 159-162):**
```python
live_balance_by_license = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
    [lic.id for lic in qs]
)
```

**Flow:**
- `LicenseBalanceCalculator.calculate_financial_balance()` computes live balance from:
  - Bill of Entry debits (BOE.total_quantity, BOE.total_value)
  - Reconciliation credits (from APP/TR/PB)
  - Allotment debits (non-BOE AT rows)

**Risk:** If balance calculation has stale aggregates or missing rows, plan eligibility is wrong

### 5.2 Module 3 (Allocation)

**One-way dependency:** Planning caps allocations, allocation doesn't trigger plan recompute

**Evidence (views_actions.py, lines 762-784):**
- Plan cap enforced before AllotmentItems.create()
- Allocation never changes `LicenseItemPlan` rows (except plan-line balance tracking)

**Exception:** Plan-line balance tracking (lines 836-851)
- Decrements `remaining_quantity`/`remaining_cif_fc` when `plan_line_id` supplied
- No validation: assumes request sent correct plan_line_id

### 5.3 Module 4 (BOE)

**No direct dependency:** BOE allotments excluded from plan-cap calc

**Evidence (plan_enforcement.py, lines 24-27):**
```python
_ALLOTTED_FILTER = Q(
    allotment__bill_of_entry__isnull=True,
    allotment__type="AT",
)
```

**Implication:** BOE items can exceed planned cap (if they exist) since they're not counted

---

## 6. UNKNOWNS & AMBIGUITIES

### 6.1 Precision Loss in Remaining-CIF Recalculation

**File:** views_actions.py, line 844

**Code:**
```python
plan_line.remaining_cif_fc = new_remaining_qty * plan_line.unit_price
```

**Unknown:**
- How many scenarios have non-exact unit_price (e.g., 1000/3 = 333.33...)?
- What is acceptable cumulative rounding error before "remaining" becomes misleading?
- Is there a test covering repeated allocations with fractional prices?

**Risk:** If allocating 3 times from same line, each time recalculating cif_fc:
- Original: qty=100, unit_price=1000/3=333.33, cif=33333.00
- After 1st debit (qty=10): remaining_qty=90, remaining_cif=90*333.33=29999.70
- After 2nd debit (qty=10): remaining_qty=80, remaining_cif=80*333.33=26666.40
- After 3rd debit (qty=10): remaining_qty=70, remaining_cif=70*333.33=23333.10
- **Lost:** 3.30 INR of rounding drift; cumulative cap enforcement still valid, but "remaining_cif" display is misleading

### 6.2 Null Handling: `remaining_quantity` May Be NULL

**File:** models/core.py, lines 1248-1255

**Schema:** `remaining_quantity` and `remaining_cif_fc` are nullable

**Migration:** Added 2026-08-04 (migration 0015, line 22)

**Unknown:**
- Pre-2026-08-04 rows may have NULL remaining_quantity
- Allocate-items handler converts NULL → planned_quantity at runtime (line 840, views_actions.py)
- **But:** plan_status_for() doesn't explicitly handle NULL — what if a group has mixed (NULL + non-NULL)?

**Evidence (views_actions.py, lines 838-841):**
```python
current_remaining = (
    plan_line.remaining_quantity
    if plan_line.remaining_quantity is not None
    else plan_line.planned_quantity
)
```

**Risk:** Mixed NULLs + values in group could give inconsistent "remaining" display

### 6.3 Transaction Atomicity: When is Plan Save Atomic?

**File:** plan_norms.py, line 220

**Code:**
```python
with transaction.atomic():
    _save_lines(lic, result.lines)
```

**Questions:**
- Does `transaction.atomic()` wrap the entire allocate_items call, or just save_plan_lines_for_license?
- If allocation happens mid-plan (between delete old rows and create new rows), what state does cap-check see?
- **Evidence:** allocate_items has `@transaction.atomic` (line 625, views_actions.py), so nested transactions are supported

**Implication:** Concurrent allocate-items on same license during a plan_norms run could:
- See deleted old plan rows (cap check returns None → falls back to availability)
- Race with baseline snapshot computation
- But `select_for_update()` on import_item should serialize

### 6.4 A3627 "Fixed Rate" — Where is the 1000 INR/kg Rule Stored?

**File:** a3627_auto_plan.py

**Code (lines 182-204):** Hard-coded 1000.0 INR rate

**Unknown:**
- Is this rate configurable anywhere?
- Should it be in a master table (like ExchangeRate)?
- What if actual A3627 market rate changes?
- No validation: assumes all A3627 items fit one line

### 6.5 Milk Split Algorithm: `optimal_milk_split()` — Undocumented

**File:** auto_plan_shared.py, line 63

**Function signature:** `optimal_milk_split(available_qty, balance_cif) → (dwp_qty, swp_qty, wpc_qty, unit_prices)`

**Unknown:**
- What is the optimality criterion? (Balance coverage? Cost efficiency?)
- What are the hard-coded rates per milk type?
- Does this function ever fail, or always returns 3-way split?

### 6.6 Norm Detection: `detect_norm()` — Location Unknown

**File:** plan_norms.py, line 178 calls it; imported from `apps.license.services.norm_plan`

**Unknown:**
- Is norm detection deterministic?
- Can one license be both E1 and E5 simultaneously?
- What happens if norm can't be detected?

### 6.7 Plan Grouping: Normalized Description Drift

**File:** plan_grouping.py, lines 37-50

**Normalization rules:**
- Trim, case-fold, collapse whitespace, remove slash-spacing
- "Fruit /Juice" == "Fruit / Juice" == "Fruit/ Juice"

**Unknown:**
- If description is edited post-plan (via DGFT resync or manual edit), does the group key change?
- If group key changes, does old plan get orphaned?
- Is there a test for re-synced descriptions changing grouping?

### 6.8 Plan-Mode Split Rows: Availability Calculation

**File:** views_actions.py, lines 376-419 (`_available_licenses_plan_mode()`)

**Unknown:**
- When plan splits an item into multiple rows, how is `available_qty` divided among rows?
- Is it divided by remaining-qty, or something else?
- Test: `test_available_licenses_plan_mode.py` — unclear if all edge cases covered

---

## 7. RISKS & DATA INTEGRITY ISSUES

### 7.1 Race Condition: Concurrent Allocate-Items + Plan Regenerate

**Scenario:**
1. Planner runs: deletes old plan, creates new plan rows
2. Concurrent allocate-items request arrives during (1), after old delete, before new create

**State during race:**
- Old `LicenseItemPlan` rows deleted
- `plan_status_for()` returns None (no rows in group)
- Cap-check falls back to availability-based behavior
- Allocation succeeds, bypassing intended cap

**Mitigation:**
- `@transaction.atomic` on both paths
- But: `select_for_update()` on import_item only — doesn't lock `LicenseItemPlan` rows
- **Risk:** Non-atomic from cap-check's perspective if it spans commit boundaries

**Verdict:** MEDIUM RISK. Unlikely in practice (concurrent manual alloc + auto-plan rare), but plausible.

### 7.2 Precision Drift: Remaining-CIF Recalculation

**Evidence:** views_actions.py, line 844

**Scenario:**
- Item with unit_price = 1000/3 = 333.33 (not exact)
- Allocate 3 times with qty=10 each
- Each time: `remaining_cif = new_qty * unit_price`
- Cumulative rounding error

**Example:**
```
Original: qty=100, unit=333.33, cif=33333.00
After alloc(10): remaining_qty=90, remaining_cif=30000*0.3333=10000 WRONG!
```

**Verdict:** MEDIUM RISK. Visible as discrepancy in "remaining CIF" display, but cap enforcement still works (qty-based).

### 7.3 Stale Baseline Snapshot: Multi-Update Scenario

**Scenario:**
1. Create plan P1 for license L at time T0: baseline_qty=100, baseline_cif=1000
2. Allocate 50 units between T0 and T1
3. Delete allotments (undo)
4. Create new plan P2 at time T1: baseline_qty=100 (still), baseline_cif=1000 (still)
5. Allocate 50 units again

**Result:**
- Used = current_live (50) - baseline (100) = -50 → clamped to 0
- Remaining = 100 - 0 = 100 ✓ Correct

**Verdict:** SAFE. Baseline snapshot handles this correctly via `max(0, ...)` clamping.

### 7.4 Data Loss: Plan Delete Without Backup

**Evidence:** plan_enforcement.py, line 169

**Code:**
```python
if delete_existing:
    LicenseItemPlan.objects.filter(license=license_obj).delete()
```

**Risk:**
- `save_plan_lines_for_license(..., delete_existing=True)` is the default
- If new plan is empty (no lines), license loses plan entirely
- No soft-delete, no historical record

**Mitigation:**
- Caller must check `if result.lines:` before saving (plan_norms.py, line 200)
- But: bulk_upsert endpoint (line 153, item_plan.py) doesn't validate `result.lines` before save

**Verdict:** LOW RISK. Calls are guarded, but bulk_upsert is an edge case.

### 7.5 Integer Overflow Risk (Decimal Fields)

**Field precision:** Decimal(15,3) for qty, Decimal(15,2) for CIF

**Max value:** 999,999,999,999.999 (Q: is this enough for annual imports?)

**Likelihood:** VERY LOW. Typical import licenses are 100-100,000 units.

### 7.6 Foreign Key Cascades: Auto-Delete Plan on Item Delete

**Evidence:** models/core.py, line 1199

**Schema:**
```python
import_item = models.ForeignKey(..., on_delete=models.CASCADE)
```

**Risk:**
- If import item is deleted (rare: only via manual DB edit), plan for that group orphaned
- Cascade deletes the row silently (no audit trail)

**Verdict:** LOW RISK. Import items are rarely deleted; PROTECT would be safer but breaks existing migrations.

### 7.7 Concurrency: No Row-Level Lock on Plan Status

**Evidence:** plan_enforcement.py, lines 220-240

**Code:**
```python
def plan_status_for_ids(gids) -> dict | None:
    plans = LicenseItemPlan.objects.filter(import_item_id__in=gids)
    baseline = plans.aggregate(...)  # ← NO select_for_update
```

**Risk:**
- Two concurrent cap-checks on same group see different baseline snapshots
- Both think they're within limit, both allocate, cumulative exceeds cap

**Scenario:**
1. Plan cap = 100. Current allocated = 0.
2. Allocate-A reads: baseline=0, allocated=0, remaining=100, requests 60
3. Allocate-B reads: baseline=0, allocated=0, remaining=100, requests 60
4. A allocates 60 (live now 60)
5. B allocates 60 (live now 120) ← EXCEEDS CAP!

**Mitigation:**
- `@transaction.atomic` + `select_for_update()` on import_item (not plan rows)
- Serializes allocations on same item, but not on group-level cap

**Verdict:** MEDIUM-HIGH RISK. Likely in high-concurrency scenario (many users allocating same group).

---

## 8. DUPLICATE CALCULATIONS

### 8.1 Single Engine, Multi-Entry Point

**Norms calculation:**
- `plan_norms` command: calls `PlannerFactory.run()`
- `auto_plan` endpoint: calls `PlannerFactory.run()` identically
- `auto_plan_all` endpoint: loop calling `PlannerFactory.run()` per license

**Verdict:** NO DUPLICATION. Single factory, three entry points.

### 8.2 Plan Status Calculation: Two Code Paths

**Path 1:** `plan_status_for(item)` (single item)
- Groups item
- Calls `plan_status_for_ids(gids)` (line 275)

**Path 2:** `plan_status_for_items(items)` (batch, lines 278-385)
- Groups all items in one query
- Aggregates baseline/original/allotted with grouped queries
- Returns dict of item_id → status

**Verdict:** INTENTIONAL DUPLICATION. Batch version (Path 2) is optimized for paginated views; both compute identically.

### 8.3 Waterfall Algorithms: Five Separate Implementations

**Files:**
- `e1_plan.py` — Confectionery (9 steps)
- `e5_plan.py` — Dairy products
- `e126_plan.py` — Oils/fats
- `e132_plan.py` — Spices
- `a3627_auto_plan.py` — Rutile (trivial, all-to-one)

**Verdict:** INTENTIONAL. Each norm has distinct business logic; no shared algorithm.

### 8.4 Validation: Duplicate Checks

**Check 1:** `validate_fresh_plan_lines()` (plan_grouping.py)
- Validates: non-negative values, total ≤ available

**Check 2:** `validate_group_plan_lines()` (plan_grouping.py)
- Validates: price ceiling (E126, E132 only)

**Check 3:** Allocate-time cap check (views_actions.py, lines 763-764)
- Validates: `(used + request) ≤ original`

**Verdict:** NO DUPLICATION. Three distinct checks at different points:
- Plan generation validation (freshness)
- Plan ceiling validation (business rule)
- Allocation-time cap validation (enforcement)

---

## 9. EDGE CASES & POTENTIAL FAILURES

### 9.1 License with No Import Items

**Input:** License has 0 import items

**Expected:** Auto-plan returns empty `lines` list, `remaining_cif=0`

**Code:** plan_norms.py, line 200 checks `if not result.lines:` and skips save

**Verdict:** SAFE.

### 9.2 License with All Items <50 Units (Min Plan Qty)

**Input:** E1 license with 10 items, each 30 units

**Expected:** None of them planned; `lines=[], remaining_cif=original_balance`

**Code:** e1_auto_plan.py, line 147 passes `min_plan_qty=50` to waterfall

**Verdict:** SAFE. Items fall back to availability-based behavior.

### 9.3 License with Zero Balance

**Input:** License balance = 0

**Plan filter (plan_norms.py, line 172):** `if live_balance <= 0: continue`

**Expected:** License skipped entirely

**Verdict:** SAFE.

### 9.4 Allocation Request with `plan_line_id` That No Longer Exists

**Scenario:** Auto-plan regenerates plan, deleting old line; concurrent allocate-items request references old line

**Code (views_actions.py, lines 846-851):**
```python
try:
    plan_line = LicenseItemPlan.objects.select_for_update().get(id=plan_line_id)
    ...
except LicenseItemPlan.DoesNotExist:
    # Stale reference — allotment above already succeeded
    pass
```

**Expected:** Allocation succeeds, plan-line balance NOT decremented

**Verdict:** SAFE. Gracefully handles stale reference.

### 9.5 Unit Price = 0

**Scenario:** Auto-plan produces line with unit_price=0

**At allocation time (line 844, views_actions.py):**
```python
plan_line.remaining_cif_fc = new_remaining_qty * plan_line.unit_price  # 0
```

**Expected:** `remaining_cif_fc` always 0, CIF-cap never triggered

**Risk:** CIF cap becomes meaningless; qty cap still enforced

**Verdict:** MEDIUM RISK. No validation prevents unit_price=0; unclear if business rule allows it.

---

## 10. MISSING EVIDENCE

### 10.1 No Locking on LicenseItemPlan Reads

**File:** plan_enforcement.py, all aggregation functions

**Evidence:** No `select_for_update()` on plan row reads

**Risk:** Plan status can change between read and cap-check decision

**Recommendation:** Add `select_for_update()` to `plan_status_for_ids()` when used in allocate-items context

### 10.2 No Explicit Test for Multi-Debit Rounding

**File:** test_plan_enforcement.py

**Missing test:**
```python
def test_remaining_cif_precision_across_three_allocations_with_fractional_price(...)
```

### 10.3 No Backward Compatibility Test for Pre-Aug-2026 Null `remaining_quantity`

**File:** test_plan_enforcement.py

**Missing test:**
```python
def test_plan_status_with_legacy_null_remaining_quantities(...)
```

---

## SUMMARY TABLE

| Category | Finding | Severity | File/Line |
|----------|---------|----------|-----------|
| **Entry Points** | 3 sources: command, auto_plan endpoint, auto_plan_all endpoint | Low | plan_norms.py:109, item_plan.py:376, item_plan.py:457 |
| **Data Flow** | Complex: plan → baseline snapshot → alloc-cap check → plan-line balance | Medium | plan_enforcement.py, views_actions.py:625 |
| **Calculations** | 5 independent waterfall engines + shared aggregations | Medium | e1_plan.py, e5_plan.py, e126_plan.py, e132_plan.py, a3627_auto_plan.py |
| **Race Condition** | Concurrent plan regen + allocate can bypass cap | Medium | views_actions.py:625, plan_norms.py:220 |
| **Precision Drift** | Remaining-CIF recalculated per debit, accumulates rounding | Medium | views_actions.py:844 |
| **Null Handling** | Pre-Aug-2026 rows may have NULL remaining_quantity | Low | models/core.py:1248 |
| **Group Concurrency** | No row-level lock on plan reads during cap-check | Medium-High | plan_enforcement.py:220 |
| **Duplicate Calcs** | No duplication; intentional multi-path design | Low | Various |

---

## RECOMMENDATIONS

1. **Add `select_for_update()` to `plan_status_for_ids()`** when called from allocate-items to serialize concurrent cap-checks on same group
2. **Add test coverage** for repeated allocations with fractional unit_price to quantify precision drift
3. **Backfill `remaining_quantity`** for pre-Aug-2026 rows to eliminate NULL checks
4. **Document `optimal_milk_split()` algorithm** and make rates configurable
5. **Add soft-delete to plan rows** to preserve historical audit trail
6. **Validate unit_price ≠ 0** at plan creation time

---

**End of Audit Report**
