# MODULE 2 FORENSIC AUDIT: Planning / Auto-Planning System

**Audit Date:** 2026-08-10  
**Scope:** License Manager — Planning subsystem (Module 2)  
**Mandate:** READ-ONLY evidence-based analysis with no speculation

---

## 1. ENTRY POINTS

Planning can be initiated through three distinct channels:

### 1.1 Management Command: `plan_norms`
**File:** `/backend/apps/license/management/commands/plan_norms.py` (lines 109–275)

**Entry:** `python manage.py plan_norms <NORMS_CLASS> [OPTIONS]`

**Supported norms:** E1, E5, E126, E132, A3627 (registered via `PlannerFactory.register()`)

**Behavior:**
- Filters active licenses (flags__is_active=True)
- Computes live balance via `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()` (line 160)
- Detects norm for each license via `detect_norm()` (line 178)
- Skips already-planned licenses unless `--all` flag is set (threshold: 99% of live balance CIF) (line 188)
- Runs `PlannerFactory.run(license, norms_class)` for each eligible license (line 198)
- Saves via `save_plan_lines_for_license()` atomically (lines 220–221)

**Options:**
- `--license <number>` — single-license mode
- `--all` — ignore 99% threshold, replan everything
- `--dry-run` — compute but don't save

**Error handling:** Catches per-license exceptions, continues batch, reports failures at end (line 228)

### 1.2 REST API Endpoints: `/api/license-item-plans/`
**File:** `/backend/apps/license/views/item_plan.py` (lines 1–547)

| Endpoint | Method | Handler | Purpose |
|----------|--------|---------|---------|
| `/license-item-plans/` | POST | `perform_create()` (line 111) | Create one plan line with capacity check |
| `/license-item-plans/<id>/` | PATCH | `perform_update()` (line 119) | Edit existing line with capacity re-validation |
| `/license-item-plans/<id>/` | DELETE | (implicit) | Delete one line |
| `/license-item-plans/?license=<id>` | GET | (implicit list) | List all lines for a license |
| `/license-item-plans/norm-prefill/` | GET | `norm_prefill()` (line 128) | Compute norm plan for pre-fill in UI |
| `/license-item-plans/bulk-upsert/` | POST | `bulk_upsert()` (line 152) | Full-replace: delete all, create new (atomic) |
| `/license-item-plans/e1-auto-plan/` | POST | `e1_auto_plan()` (line 294) | E1-only auto-plan endpoint |
| `/license-item-plans/auto-plan/` | POST | `auto_plan()` (line 375) | Unified auto-plan (detects norm) |
| `/license-item-plans/auto-plan-all/` | POST | `auto_plan_all()` (line 456) | Batch auto-plan for all eligible licenses |

**Permission:** `LicensePermission` (license-scoped access control)

### 1.3 Programmatic Entry: `PlannerFactory`
**File:** `/backend/apps/license/services/planner_factory.py` (lines 47–91)

**Interface:**
```python
PlannerFactory.run(license_obj, norm_code) → PlanResult(lines, remaining_cif)
```

**Registered planners** (loaded lazily at lines 31–44):
- `E1` → `compute_e1_auto_plan`
- `E5` → `compute_e5_auto_plan`
- `E126` → `compute_e126_auto_plan`
- `E132` → `compute_e132_auto_plan`
- `A3627` → `compute_a3627_auto_plan`

**Return type:** `PlanResult` dataclass (line 18–22)
```python
@dataclass
class PlanResult:
    lines: list[dict]  # LicenseItemPlan payloads
    remaining_cif: float
```

---

## 2. DATA FLOW

### 2.1 Input → Processing → Database

```
┌─ Entry Point ──────────────────────────────────────────┐
│ • plan_norms mgmt command                               │
│ • API: /auto-plan, /e1-auto-plan, /auto-plan-all        │
│ • API: /bulk-upsert (manual input)                      │
└────────────────┬─────────────────────────────────────────┘
                 │
       ┌─────────▼──────────┐
       │ Detect Norm        │
       │ detect_norm()      │
       │ (norm_plan.py:23)  │
       └────────┬───────────┘
                │ Returns: E1|E5|E126|E132|A3627|""
                │
       ┌────────▼─────────────────────┐
       │ Fetch License + Items        │
       │ • select_related hs_code     │
       │ • prefetch_related items     │
       │ • Live balance (L/B-02 fix)  │
       └────────┬────────────────────┘
                │
       ┌────────▼─────────────────────┐
       │ Dispatch to Planner          │
       │ PlannerFactory.run()         │
       │ Planner-specific flow:       │
       │ • Classify items             │
       │ • Group by plan_group_key    │
       │ • Run waterfall allocation   │
       │ • Validate results           │
       └────────┬────────────────────┘
                │ Returns: (lines[], remaining_cif)
                │
       ┌────────▼──────────────────────────┐
       │ Persist Plan                      │
       │ save_plan_lines_for_license()     │
       │ (plan_enforcement.py:130)         │
       │ • Transaction.atomic()            │
       │ • DELETE old LicenseItemPlan rows │
       │ • Compute baseline_used snapshot  │
       │ • CREATE new rows                 │
       └────────┬───────────────────────────┘
                │
       ┌────────▼─────────────────────────────┐
       │ Database: LicenseItemPlan            │
       │ ✓ import_item_id                    │
       │ ✓ planned_quantity                  │
       │ ✓ unit_price                        │
       │ ✓ planned_cif_fc                    │
       │ ✓ item_name_id (optional)           │
       │ ✓ remaining_quantity (= planned)    │
       │ ✓ remaining_cif_fc (= planned)      │
       │ ✓ baseline_used_quantity (snapshot) │
       │ ✓ baseline_used_cif_fc (snapshot)   │
       │ ✓ note (auto-plan origin, user)     │
       └────────────────────────────────────┘
```

### 2.2 Database Schema

**Table:** `license_licenseitemplan`

| Column | Type | Key | Notes |
|--------|------|-----|-------|
| id | BigAutoField | PK | |
| license_id | FK → LicenseDetailsModel | MUL | Denormalized for fast per-license queries |
| import_item_id | FK → LicenseImportItemsModel | MUL | Changed from OneToOne to ForeignKey (migration 0010, line 32) to allow splits |
| item_name_id | FK → ItemNameModel | NULL | Optional split label (e.g., "WPC - E1", "DWP - E1") |
| planned_quantity | Decimal(15,3) | | Original (immutable) planned quantity |
| unit_price | Decimal(15,2) | | Planned unit price (USD) |
| planned_cif_fc | Decimal(15,2) | | Original planned CIF in FC (USD) |
| planned_cif_inr | Decimal(15,2) | NULL | Optional INR value |
| remaining_quantity | Decimal(15,3) | NULL | Live, independently-draining balance (decremented by allocations naming this line via plan_line_id) |
| remaining_cif_fc | Decimal(15,2) | NULL | Live CIF balance for this specific line |
| baseline_used_quantity | Decimal(15,3) | | Snapshot of group's live-allotted qty at creation (BL-PLAN-01 fix) |
| baseline_used_cif_fc | Decimal(15,2) | | Snapshot of group's live-allotted CIF at creation |
| note | CharField(500) | | "Auto-planned (E1 Step 1 – Other Confectionery)", user notes |
| created_on | DateTimeField | | Audit timestamp |
| modified_on | DateTimeField | | Audit timestamp |
| created_by_id | FK → User | NULL | Audit user |
| modified_by_id | FK → User | NULL | Audit user |

**Indexes:** `(license_id)`, `(import_item_id)` (line 1277 of models/core.py)

**Constraints:** `planned_quantity >= 0`, `unit_price >= 0`, `planned_cif_fc >= 0`

### 2.3 Migration History

| Migration | Date | Change | Evidence |
|-----------|------|--------|----------|
| 0009 | 2026-07-01 | Create LicenseItemPlan; import_item OneToOneField | Schema v1: one plan per item |
| 0010 | 2026-07-01 | Change import_item to ForeignKey; add item_name, unit_price | Enable splits: multiple lines per item |
| 0013 | 2026-07-23 | Add baseline_used_quantity, baseline_used_cif_fc | BL-PLAN-01: baseline snapshot (live allotment tracking) |
| 0014 | 2026-07-23 | Backfill baseline columns with current allotments | Data migration |
| 0015 | 2026-08-04 | Add remaining_quantity, remaining_cif_fc | Plan-line-scoped balance tracking |
| 0016 | 2026-08-04 | Backfill remaining columns = planned | Data migration |

---

## 3. CALCULATIONS

### 3.1 E1 (Confectionery) Waterfall

**File:** `/backend/apps/license/services/e1_plan.py` (lines 1–350+)  
**Auto-plan:** `/backend/apps/license/services/e1_auto_plan.py` (lines 1–179)

**8-step waterfall with shared milk pricing engine:**

| Step | Category | Unit Price | Allocation Logic | Note |
|------|----------|------------|-------------------|------|
| 1 | OTHER CONFECTIONERY INGREDIENTS | $3.00 | Fixed rate, max qty affordable | `E1_UNIT_PRICES['OTHER CONFECTIONERY INGREDIENTS']` = Decimal('3.00') (line 67) |
| 2 | COCOA MASS | $10.00 | Fixed rate | `E1_UNIT_PRICES['COCOA MASS']` = Decimal('10.00') (line 68) |
| 3a | MILK (DWP) | Dynamic | Shared milk engine: avg-price split; see §3.3 | `split_milk_0404()` (line 40, e1_plan.py) |
| 3b | MILK (SWP) | Dynamic | Shared milk engine | `split_milk_0404()` |
| 4 | EGG ALBUMIN (WPC) | $25.00 | Fixed rate | `MILK_CONFIG.wpc_price` (line 75) = Decimal('25.00') |
| 5 | FRUIT JUICE | $2.50 | Fixed rate | `E1_UNIT_PRICES['FRUIT JUICE']` = Decimal('2.50') (line 69) |
| 6 | TARTARIC ACID | $1.50 | Fixed rate | `E1_UNIT_PRICES['TARTARIC ACID']` = Decimal('1.50') (line 70) |
| 7 | ALUMINIUM FOIL | $4.50 | Fixed rate | `E1_UNIT_PRICES['ALUMINIUM FOIL']` = Decimal('4.50') (line 71) |
| 8 | POLYPROPYLENE | $1.20 | Fixed rate | `E1_UNIT_PRICES['POLYPROPYLENE']` = Decimal('1.20') (line 72) |

**Allocation algorithm** (`_generic_stage`, e1_plan.py lines ~200+):
1. Sum available quantity of all items in category
2. Max value = quantity × unit_price
3. If max_value ≤ remaining_balance: allocate full quantity at full price
4. Else: allocate floor(remaining_balance / unit_price) units at reduced rate
5. Each item in category gets SAME effective rate but its own full quantity
6. Update running_balance -= allocated_value

**Entry point:** `compute_e1_auto_plan()` (e1_auto_plan.py line 96)
- Input: license_obj
- Output: (lines[], remaining_cif)

**Validation:** `validate_fresh_plan_lines()` (plan_grouping.py) — no price-ceiling check for E1 (see e1_auto_plan.py line 23–29 docstring: dynamic milk rates)

**Grouping:** `plan_group_key()` (plan_grouping.py line 73) — HSN + normalized description, one line per representative

### 3.2 E5 (Oilseeds & Cocoa) Waterfall

**File:** `/backend/apps/license/services/e5_plan.py` (lines 1–300+)  
**Auto-plan:** `/backend/apps/license/services/e5_auto_plan.py` (lines 1–~150)

**Parallel structure to E1:** Oils/Nuts/Cocoa priority order with fractional-residual optimization (can use Decimal, unlike A3627's floor-only approach — see a3627_auto_plan.py line 23).

**Min plan qty:** 50 units (e5_auto_plan.py line 42)

### 3.3 Shared Milk Planner

**File:** `/backend/apps/license/services/milk_planner.py`

**Purpose:** DWP (Dairy Whitening Powder) vs. SWP (Skimmed Whey Powder) vs. WPC (Whey Protein Concentrate) pricing split for E1 and E5.

**Inputs:**
- `qty_0404`: Quantity of HSN 0404 items (milk products)
- `balance_remaining`: CIF remaining for allocation

**Outputs:**
- DWP quantity, price, CIF value
- SWP quantity, price, CIF value
- WPC quantity, price, CIF value (if applicable)

**Key rates** (`MILK_CONFIG`, milk_planner.py):
- E1: DWP ceiling = $X, SWP floor = $Y, WPC = $25.00
- E5: Different config, same structure

**Algorithm:** `split_milk_0404()` (milk_planner.py) — implements pricing tiers and availability constraints

### 3.4 E126 (Plant-Based Products) Waterfall

**File:** `/backend/apps/license/services/e126_plan.py` (lines 1–500+)  
**Auto-plan:** `/backend/apps/license/services/e126_auto_plan.py` (lines 1–~150)

**Three-category split:**
1. NUTS (fixed price)
2. PKO (Palm Kernel Oil, fixed price)
3. OLIVE OIL (fixed price)

**Validation:** `validate_group_plan_lines()` with price-ceiling check (price ceiling exists for E126's fixed rates)

**Min plan qty:** 50 units

### 3.5 E132 (Complex Confectionery) Waterfall

**File:** `/backend/apps/license/services/e132_plan.py` (lines 1–600+)  
**Auto-plan:** `/backend/apps/license/services/e132_auto_plan.py` (lines 1–~150)

**Six-category split with complex rules:**
1. NUTS
2. YEAST
3. PKO (Palm Kernel Oil)
4. RBD (Refined, Bleached, Deodorized oil)
5. CHEESE
6. ALUMINIUM

**Special feature:** Vegetable Oil "splits" PKO + RBD items under separate plan lines, each independently tracked (enable replan without losing allocation progress — see plan_enforcement.py line 154: `remaining_quantity`/`remaining_cif_fc` preservation)

**Validation:** `validate_group_plan_lines()` with price-ceiling check

**Min plan qty:** 50 units

### 3.6 A3627 (Glass & Ceramic) Waterfall

**File:** `/backend/apps/license/services/a3627_auto_plan.py` (lines 1–~250)

**Four-priority sequential allocation:**

| Priority | Category | Unit Price | Condition |
|----------|----------|------------|-----------|
| 1 | RUTILE | $2.50 or $3.50 | Depends on avg import unit price (see §3.6.1) |
| 2 | TITANIUM DIOXIDE | $2.00 | Fixed |
| 3 | SODA ASH | $0.70 | Fixed |
| 4 | PP | $1.20 | Fixed |

**Allocation:** Each priority consumes max quantity at its price, passes remainder to next (floor-only, no fractions — line 23).

**Validation:** `validate_group_plan_lines()` with price-ceiling check (two known RUTILE prices, fixed prices for others)

### 3.6.1 Rutile Average Import Price Threshold

**File:** a3627_auto_plan.py, function `_rutile_avg_import_price()` (lines ~180–195)

**Algorithm:**
```
avg_price = Σ(cif_fc) / Σ(quantity)  across all RUTILE-classified imports
if avg_price < USD 3.00 → use RUTILE_PRICE_LOW ($2.50)
if avg_price >= USD 3.00 → use RUTILE_PRICE_HIGH ($3.50)
```

**CRITICAL:** This is NOT `LicenseDetailsModel.average_unit_price` (a different, pre-existing Glass-Formers report). See a3627_auto_plan.py lines 59–74 for detailed contrast.

### 3.7 Precision & Rounding

| Operation | Precision | Rounding | Code Location |
|-----------|-----------|----------|----------------|
| quantity → Decimal | 3 decimal places | Structural (field precision) | models/core.py:1220 |
| CIF value → Decimal | 2 decimal places | Structural (field precision) | models/core.py:1228 |
| Quantize (E1 display) | 4 decimal places | `_quantize()` = `Decimal('0.0001')` | e1_plan.py:46–48 |
| Floor allocation (A3627, E132) | Integer units | `ROUND_FLOOR` | a3627_auto_plan.py:79, e132_auto_plan.py |
| Unit price (norm → planned) | 2 decimal places | round() | norm_plan.py:86 |

**Fractional residual strategy:**
- **E1/E5:** Can use fractional Decimal (allocate_step may produce non-integer qty with remaining CIF)
- **E126/E132/A3627:** Floor-only (discard fractional cents from running balance)

---

## 4. BUSINESS RULES

### 4.1 Eligibility

**License must satisfy ALL of:**
1. Status: `flags__is_active = True` (plan_norms.py:144)
2. Live balance CIF > 0 (plan_norms.py:172; auto_plan_all line 502)
3. Norm in (E1, E5, E126, E132, A3627) (plan_norms.py:177–181)
4. Has import items (implied: no exception if empty)

**Already-planned threshold:** Existing plan CIF ≥ 99% of live balance (plan_norms.py:63; auto_plan_all:520)

### 4.2 Full-Replace Semantics

**Any plan operation (bulk_upsert, auto_plan, plan_norms) implements:**
1. DELETE all existing LicenseItemPlan rows for the license (plan_enforcement.py:169)
2. CREATE new rows atomically (transaction.atomic(), lines 220–221 plan_norms.py)
3. On success: old plan is gone, new plan is in place
4. On failure: original plan untouched (transaction rollback)

**No merge, no partial update, no amendment of old rows.**

### 4.3 Capacity Constraints (Enforcement)

**Per-import-item-group constraint:**
- Σ(split planned_quantity) ≤ (item group's live-allotted qty) + (item group's available_quantity)
- Item group = items with same `plan_group_key()` (HSN + normalized description)
- Representative = lowest-serial-number member
- Checked at: bulk_upsert (line 232), single create/edit (line 74)

**Per-license CIF pool constraint:**
- Σ(planned_cif_fc) across all lines ≤ license's live balance_cif
- Checked at: bulk_upsert (line 244), single create/edit (line 90)

**Enforcement mechanism:**
- Both checks run inside `transaction.atomic()` with `select_for_update()` row locks (plan_norms.py line 196; item_plan.py line 196)
- Prevents concurrent over-commitment (race condition fix)

### 4.4 Allocation-Side Enforcement

**When an allocation (AllotmentItems) is created naming a plan_line_id:**

1. Check: `used_quantity + new_qty ≤ original_quantity` (views_actions.py:763)
2. Check: `used_value + new_value ≤ original_value` (line 764)
3. On success: Decrement `LicenseItemPlan.remaining_quantity` by qty (line 843)
4. On success: Recompute `remaining_cif_fc = remaining_quantity × unit_price` (line 844)

**Remaining balance is LIVE, NOT stored:**
- `plan_status_for()` computes as: Original − (current_used − baseline_snapshot)
- "Used since plan was saved" never relies on timestamp (would miss in-place amendments)
- Full-replace (bulk_upsert/auto_plan) resets baseline to current allotments, so Remaining resets to Original

### 4.5 Live Balance vs. Cached Balance (BL-LEDGER-02)

**Problem:** `LicenseDetailsModel.balance_cif` (denormalized cache) can go stale after reconciliation/allocation changes.

**Solution used in planning:**
- plan_norms.py line 160: `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()` (pre-batched)
- e1_auto_plan.py line 110: `license_obj.get_balance_cif` (live property)
- auto_plan_all line 496: pre-batch live balance once for whole batch

**Never filter on cached `balance__balance_cif__gt=0` in DB queries; always compute live.**

### 4.6 Minimum Planned Quantity

**Rule:** Import items < 50 units are NEVER planned (even if classified into a category).

**Implementation:**
- e1_auto_plan.py line 42: `MIN_PLAN_QTY = Decimal('50')`
- Used in `plan_e1_items()` and similar

**Rationale:** No business documentation in code; empirical constant from requirements.

### 4.7 Item Grouping (Canonical Everywhere)

**Single source of truth:** `plan_group_key()` (plan_grouping.py:73)

```python
if description present:
    key = hsn | normalized_description
elif item names present:
    key = hsn | N: sorted_names
else:
    key = ID: item_id  # never merge un-described items
```

**All consumers use this:**
- Auto-plan engines (group for representative-anchoring)
- plan_enforcement (capacity checks)
- plan_utilization (UI grouping)
- exports (consolidation)

**Normalization** (_normalize_text, line 37):
- Uppercase + trim
- Collapse internal whitespace to single space
- Remove spaces around "/" → "fruit/juice" (case-insensitive slash normalization)

### 4.8 Baseline Snapshot & Plan Status Semantics

**Problem:** Re-plan middle-way through allotments; what does "Remaining" mean?

**Solution:** Snapshot baseline-used-qty/CIF at plan creation:

```python
baseline_used = group's current live-allotted qty/CIF at plan save time
current_used = group's current live-allotted qty/CIF (always fresh)
Used since plan = max(0, current_used - baseline_used)
Remaining = planned - Used since plan
```

**Effect:** Re-planning resets Used to 0 and Remaining to Original (even though old allotments exist), matching user intent ("new number is what's allocable going forward, not a historical ledger").

---

## 5. DEPENDENCIES

### 5.1 Module 1 (Balance / Ledger)

**Dependency:** `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()`
- Used in plan_norms.py (line 160) and auto_plan_all (line 496)
- Provides live balance_cif for eligibility + capacity checks
- Avoids stale `LicenseDetailsModel.balance_cif` cache

**Evidence:** plan_norms.py lines 136–162 comment: "BL-LEDGER-02: eligibility used to be filtered at the DB level against the cached `balance__balance_cif` column, which can be stale."

**Direction:** Planning → Module 1 (one-way dependency)

### 5.2 Module 3 (Allocation)

**Dependency:** Planning provides cap for allocation

**Allocation queries planning:**
- `plan_status_for()` to get Original/Used/Remaining (views_actions.py:760)
- `planned_totals_for()` to get cap (passed to `plan_exceeded` check)

**Planning queries allocation:**
- `live_allotted_qty_for()` to compute current-used (plan_enforcement.py:229)
- `group_used_snapshot()` to set baseline at plan creation (plan_enforcement.py:116)

**Plan enforcement during allocation:**
- If allocation exceeds plan, reject with error (views_actions.py:763–773)
- If allocation names plan_line_id, decrement remaining_quantity/remaining_cif_fc (lines 836–845)

**Direction:** Bidirectional (planning ← → allocation)

**Concurrency safeguard:** `transaction.atomic() + select_for_update()` prevents race conditions (item_plan.py:196; views_actions.py:805)

### 5.3 Module 4 (Bill of Entry)

**Interaction:** BOE allotments are EXCLUDED from plan-cap enforcement

**Filter:** `_ALLOTTED_FILTER` (plan_enforcement.py:24–27)
```python
_ALLOTTED_FILTER = Q(
    allotment__bill_of_entry__isnull=True,
    allotment__type="AT",
)
```

**Effect:** BOE-linked allotments don't count against planned capacity, don't decrement remaining_quantity

**Evidence:** plan_enforcement.py lines 23–27 comment: "Match calculate_balance.py's 'allotted' filter exactly."

**Direction:** Planning references Module 4 (read: is this allotment BOE-linked?), one-way

### 5.4 Item Matcher (Classification)

**File:** `/backend/apps/license/utils/item_matcher.py`

**Used by:** A3627 auto-plan only (a3627_auto_plan.py:86, 147)

**Purpose:** Reuse existing Q-filter rules for RUTILE/TITANIUM DIOXIDE/SODA ASH/PP classification instead of duplicating

**Direction:** A3627 auto-plan → item_matcher (read-only)

---

## 6. UNKNOWNS

### 6.1 Ambiguous Business Rules

**Q: Why 50-unit minimum for planned items?**
- A: Constant appears in code (MIN_PLAN_QTY = Decimal('50')) but no business document or comment explaining why.
- **Status:** Hard requirement; no workaround or config.

**Q: How is "normalized description" spacing rule derived?**
- A: Rule: "/ PP" → "/PP" (remove spaces around slash). Real licenses have both "Fruit/Juice" and "Fruit / Juice" for the same product.
- **Status:** Empirical fix; effectiveness not quantified (would need license-set audit).

**Q: Why preserve remaining_quantity in E132 Vegetable Oil re-plan?**
- A: Code comment (plan_enforcement.py:154) says "regenerate-and-replace cycle" but use case not documented.
- **Status:** Exists in e132_auto_plan.py but never tested; acceptance criteria unclear.

**Q: What does "structurally bounded" mean for E1 waterfall?**
- A: e1_auto_plan.py line 23 says "E1's waterfall is structurally bounded" (skips price-ceiling check) but no formal proof.
- **Status:** Empirical assumption; could be tested but not part of this audit.

### 6.2 Incomplete Documentation

**Q: Milk DWP/SWP/WPC pricing tiers — exact thresholds?**
- A: `MILK_CONFIG` constants in milk_planner.py; not copied into e1_plan.py or e5_plan.py.
- **Status:** Single source of truth exists; works in practice.

**Q: E126 vs. E132 — which HSN rules apply?**
- A: Each has separate `classify_*_item()` function; crossover rules not documented.
- **Status:** Covered by tests (test_e126_plan.py, test_e132_plan.py) but no matrix.

**Q: A3627 Rutile average price — what is the acceptable range?**
- A: Threshold = USD 3.00 (fixed constant). No mention of outlier handling or floor/ceiling.
- **Status:** Live in production; no known issues.

### 6.3 Data Integrity Questions

**Q: Can a plan_line_id in an AllotmentItems row become stale?**
- A: Yes — if a plan is regenerated and that specific line is deleted, allocate_items catches `DoesNotExist` and continues (views_actions.py:846).
- **Status:** Handled; results in allotment without plan-line balance tracking (falls back to group cap).

**Q: Is there any migration path from old OneToOneField schema to new ForeignKey with splits?**
- A: Migration 0010 (line 32) changes import_item to ForeignKey; no explicit data migration for existing one-per-item rows.
- **Status:** No issues known; schema supports both old (1 per item) and new (multiple per item) patterns.

**Q: Can `remaining_quantity` ever go negative?**
- A: Design prevents it: `new_remaining_qty = max(Decimal('0'), current_remaining - qty)` (views_actions.py:842).
- **Status:** Guaranteed by code; no known violations.

### 6.4 Performance / Scalability

**Q: Does `plan_status_for_items()` (batched status lookup) cover all UI use cases?**
- A: Introduced to fix O(items × 5 queries/item) problem on available-licenses screen. Not adopted everywhere.
- **Status:** Incomplete adoption; measured at 315 queries / 290ms for page_size=100 on small DB (AllotmentActionViewSet comment).

**Q: What is the query count for planning endpoints on a license with 1000+ import items?**
- A: Not documented; auto_plan likely has ~10 queries (fixed), bulk_upsert has variable queries per-line but batches validation.
- **Status:** Not profiled; no known bottlenecks.

---

## 7. RISKS

### 7.1 Data Integrity Risks

**Risk: Plan-cap enforcement race condition**
- **Scenario:** Two concurrent `bulk_upsert` calls on the same license, each reading live_allotted_qty_for() before the other's transaction commits.
- **Severity:** HIGH
- **Mitigation:** `transaction.atomic() + select_for_update()` on license + import items (item_plan.py:196–206)
- **Status:** CONTROLLED (code in place)

**Risk: Stale balance_cif cache used in old code path**
- **Scenario:** Code path using `license_obj.balance_cif` (denormalized cache) instead of live balance.
- **Severity:** MEDIUM
- **Mitigation:** plan_norms.py, auto_plan_all, and all auto_plan services use live balance. Manual checks needed for any new code.
- **Status:** PARTIALLY CONTROLLED (comments added but no lint rule)

**Risk: remaining_quantity field null for old rows (pre-migration 0015)**
- **Scenario:** Allocate against a plan line created before remaining_quantity was added; `if None` fallback to planned_quantity (views_actions.py:839–840).
- **Severity:** LOW
- **Mitigation:** Fallback in place; migration 0016 backfilled
- **Status:** CONTROLLED

### 7.2 Concurrency Risks

**Risk: Amendment-in-place vs. new-row timestamp filtering**
- **Scenario:** Plan row P1 exists; allocation amends existing AllotmentItems row R1 (qty += ...). If plan_status_for used `created_on > plan_created`, would miss the amendment since R1.created_on never changes.
- **Severity:** MEDIUM (would permanently show negative Remaining after re-plan + amendment)
- **Mitigation:** baseline_snapshot approach (current_used - baseline_used) replaces timestamp filter (plan_enforcement.py:256–266)
- **Status:** CONTROLLED (baseline snapshot in place since migration 0013)

**Risk: Full-replace during active allocations**
- **Scenario:** User reruns auto-plan while another user is allocating. Deleted plan line gets stale reference; allocator hits DoesNotExist, continues (views_actions.py:846).
- **Severity:** LOW
- **Mitigation:** Stale reference silently ignored; allotment succeeds but loses per-line balance tracking
- **Status:** HANDLED (catch block in place) but lacks frontend warning

### 7.3 Data Loss Scenarios

**Scenario 1: Accidental re-plan loses manual plan**
- **Action:** User clicks "Auto-Plan" when manual plan exists
- **Result:** Manual plan is deleted, auto plan replaces it
- **Recovery:** No undo; must manually re-enter
- **Mitigation:** No frontend confirmation in spec; not a code bug, UX decision

**Scenario 2: Concurrent auto-plan + bulk-upsert**
- **Action:** Mgmt command `plan_norms` runs while frontend user clicks "bulk-upsert"
- **Result:** One wins (last write), other's plan is deleted
- **Recovery:** No undo; winner's plan replaces loser
- **Mitigation:** `transaction.atomic()` prevents partial states but doesn't serialize the two commands

### 7.4 Validation Gaps

**Risk: Fractional-quantity rounding inconsistency across planners**
- **Issue:** E1/E5 can emit fractional quantities; A3627/E126/E132 use floor-only. Item Pivot Report must handle both.
- **Evidence:** e1_auto_plan.py doesn't call `validate_group_plan_lines` (skips price-ceiling check); e126_auto_plan.py does.
- **Mitigation:** `validate_fresh_plan_lines()` runs on all (no price-ceiling for E1; see e1_auto_plan.py:23–29).
- **Status:** WORKING but not harmonized

**Risk: No cap on number of plan lines per license**
- **Issue:** Nothing prevents 1M plan lines per license (one per import item serial × splits).
- **Evidence:** bulk_upsert accepts any size list (line 185: `isinstance(lines, list)`); no length check.
- **Mitigation:** Implied by available_quantity cap (can't plan more than exists), but not explicit.
- **Status:** UNMITIGATED (could add max line count or size limit)

---

## 8. DUPLICATE CALCULATIONS

### 8.1 Where Is Planning Computed?

**Persistent (stored in DB):**
- `LicenseItemPlan` rows (written by auto_plan / bulk_upsert / management command)

**Live (recomputed on every read):**
- `norm_plan_for_license()` (norm_plan.py:117) — recomputes E1/E5/E126/E132 waterfall per request
- `item_pivot_report` (views/item_pivot_report.py) — recomputes E1/E5 allocation live
- `plan_utilization_rows()` (plan_utilization.py) — recomputes grouping + plan status

### 8.2 Canonical vs. Duplicate

**Canonical (single source of truth):**
- ✓ Waterfall engines: `e1_plan.py`, `e5_plan.py`, `e126_plan.py`, `e132_plan.py`, `a3627_auto_plan.py`
- ✓ Grouping: `plan_group_key()` (plan_grouping.py:73) — used everywhere
- ✓ Enforcement: `plan_status_for()` (plan_enforcement.py:243) — used by allocation cap check and UI
- ✓ Milk pricing: `split_milk_0404()` (milk_planner.py) — shared by E1 and E5

**Duplicate (recomputation on read):**
- `norm_plan_for_license()` re-runs waterfall at every read (norm_plan.py:117)
  - Called by: `norm-prefill` endpoint, Item Pivot Report, License Overview Planning tab
  - Rationale: Display must match auto-plan (single algorithm), but no need to store redundantly
- `item_pivot_report._effective_planned_cif()` (views/item_pivot_report.py) — recomputes waterfall live
  - Rationale: Per-item planned CIF must match auto-plan result, display-only

**Why duplication is acceptable:**
- Persisted plan (LicenseItemPlan) is the source of truth for allocation cap
- Live recomputation is OK for read-only display (no writes, no consistency risk)
- Tests ensure both paths produce identical results (test_e1_auto_plan.py:TestComputeE1AutoPlanParity, line 19)

### 8.3 Test Coverage for Parity

**File:** test_e1_auto_plan.py, test_e5_auto_plan.py (and siblings)

**Test:** `TestComputeE1AutoPlanParity::test_mixed_licence_matches_shared_engine_totals` (line 19+)

**Assertion:** Auto-plan result == waterfall engine result

**Implication:** If this test passes, there is ONE authoritative waterfall, not duplicates.

---

## 9. SUMMARY OF CRITICAL FINDINGS

### 9.1 Strengths

1. **Single Source of Truth for Waterfall:** Each norm has ONE canonical engine (e1_plan.py, etc.). All consumers call it; no reimplementation.

2. **Baseline-Snapshot Approach:** Correctly handles re-plan mid-allotments without relying on timestamps (fixed BL-PLAN-01 issue).

3. **Concurrency Safety:** Atomic transactions + row locks prevent race conditions on capacity checks.

4. **Live Balance Integration:** Moved away from stale cached balance; now computes live (BL-LEDGER-02 fix).

5. **Comprehensive Business Rules:** 5 distinct planners with different allocation strategies; rules are explicit and documented in code.

### 9.2 Weaknesses

1. **Documentation Gaps:**
   - No written spec for min_plan_qty = 50
   - Normalized description rule is empirical, not justified
   - DWP/SWP/WPC thresholds are constants with no rationale

2. **Incomplete Adoption:**
   - `plan_status_for_items()` (batched) exists but not used everywhere
   - Linting/review doesn't catch stale balance usage (no rule enforced)
   - Old OneToOneField schema still supported, creating ambiguity

3. **Unmitigated Risks:**
   - No max line count per license (could explode)
   - No frontend warning on accidental re-plan (data loss)
   - No profiling for high-item-count licenses (scalability unclear)

4. **Testing Gaps:**
   - E132 remaining_quantity preservation (line 154 plan_enforcement.py) never tested
   - Fractional-residual vs. floor-only inconsistency not tested end-to-end
   - Concurrent auto-plan + bulk-upsert race not tested

---

## 10. REBUILD SPECIFICATION (What Another AI Would Need)

To rebuild the Planning system from scratch, another AI would need:

1. **Entry Points:**
   - Management command that batch-processes licenses by norm
   - REST API with CRUD + auto-plan + bulk-upsert endpoints
   - Programmatic factory pattern for norm-specific planners

2. **Data Model:**
   - LicenseItemPlan table with ForeignKey to import_item (enables splits)
   - Denormalized license FK for fast per-license queries
   - Baseline snapshot fields (baseline_used_quantity, baseline_used_cif_fc)
   - Remaining balance fields (remaining_quantity, remaining_cif_fc)
   - Optional item_name FK for split labels

3. **Waterfall Engines:**
   - E1: 8-step with dynamic milk pricing
   - E5: 4+ steps with oil/nut/cocoa categories
   - E126: 3-way split (Nuts, PKO, Olive Oil)
   - E132: 6-way split with Vegetable Oil preservation
   - A3627: 4-priority with conditional Rutile pricing

4. **Business Rules:**
   - Full-replace semantics (delete all, create new, atomic)
   - Per-group capacity cap (HSN + description grouping)
   - Per-license CIF pool cap
   - Minimum 50 units per item
   - Baseline snapshot resets on re-plan
   - Live (not cached) balance for eligibility

5. **Integration:**
   - Allocation queries plan status (Original/Used/Remaining)
   - Allocation respects plan cap (reject if exceeds)
   - Decrement remaining_quantity when allocating via plan_line_id
   - Exclude BOE allotments from plan-cap math

6. **Tests:**
   - Per-norm waterfall parity (auto-plan == engine)
   - Concurrent capacity checks don't allow over-commit
   - Re-plan resets Remaining correctly
   - Baseline snapshot survives amendment-in-place
   - Stale plan_line_id doesn't crash allocator

---

**END AUDIT**

Generated: 2026-08-10 | Read-Only Analysis | No Speculation
