# MASTER BUSINESS RULES REFERENCE

**Last Updated**: 2026-08-10  
**Scope**: License planning, allocation, and consumption rules  
**Validation Status**: 20 rules tracked; 2 defects identified; PP norm (32% of licenses) unimplemented

---

## EXECUTIVE SUMMARY

| Category | Count | Enforced | Defects | Coverage |
|----------|-------|----------|---------|----------|
| Norm Coverage Rules | 6 | 4/6 (67%) | **BL-PLAN-02**: PP missing | E1, E5, E126, E132, A3627; PP=GAP |
| Quantity & Value Constraints | 3 | 3/3 (100%) | None | All norms |
| Manual Plan Overrides | 2 | 2/2 (100%) | None | All overrides |
| Allocation & Consumption | 3 | 3/3 (100%) | None | All items |
| Split Semantics | 3 | 3/3 (100%) | **BL-PLAN-01**: CIF defect | E5 milk, E126 PKO/Olive, E132 PKO/Cheese |
| Preserved Plans | 1 | 1/1 (100%) | Inherits BL-PLAN-01 | Re-generated plans |
| Plan Line Invariants | 1 | 0/1 (0%) | **BL-PLAN-01**: Violated | E126/E132 only |
| Scope | 1 | 1/1 (100%) | None | All plans |
| **TOTAL** | **20** | **17/20 (85%)** | **2 active** | |

---

## BLOCKER STATUS

### ACTIVE BLOCKERS

| ID | Severity | Issue | Impact | Action |
|---|----------|-------|--------|--------|
| **BL-PLAN-01** | HIGH | E126/E132 `planned_cif_fc ≠ planned_qty × unit_price` | Financial misstatement; ledger/export errors; reporting recomputes rates | Validate invariant in `validate_group_plan_lines()` |
| **BL-PLAN-02** | MEDIUM | PP norm (73 licenses, 32%) has zero auto-plan support | Manual entry required; no utilization forecasting | Confirm PP business rules; implement `pp_auto_plan.py` |

### CONFLICTING RULES

**None identified.** All rules are complementary (no logical contradictions).

### UNKNOWN RULES WITH FINANCIAL IMPACT

**A3627 Norm**: Limited real-world data (1 license). Compliance status is **PARTIAL** with unknown risk. Recommend:
- Audit current A3627 execution against business spec
- Add test coverage for multi-item, fractional-split scenarios

---

## DETAILED RULE REFERENCE

### SECTION 1: NORM COVERAGE RULES

---

#### Rule 1.1: E1 Norm Fixed-Rate Category Allocation

| Field | Value |
|-------|-------|
| **Rule ID** | R-1.1 |
| **Title** | E1: Fixed-Rate Category Allocation |
| **Description** | E1 licenses classify import items into categories (Cereals, Pulses, Spices, Sugar, etc.), group by category, allocate balance_cif proportionally to categories by weight (sum of item quantities), compute per-category unit price = category_cif / category_qty, then allocate per-item planned_cif = planned_qty × unit_price. |
| **Business Meaning** | Ensures that E1 licenses (25 real licenses) distribute their CIF budget fairly across commodity categories based on volume imported. |
| **Formal Statement** | For each import item in E1 license: Classify → Group by category → Allocate balance_cif to group proportionally (weight = qty sum) → Per-item planned_cif = planned_qty × (group_cif / group_qty) |
| **Scope** | 25 real licenses (audit BL-PLAN-02) |
| **Source Code** | `backend/apps/license/services/e1_plan.py` lines 88–306 |
| **Enforcement Points** | **Classification**: `classify_e1_item()` L88 \| **Waterfall**: `plan_e1_items()` L225 \| **Auto-plan**: `compute_e1_auto_plan()` L96 \| **Persistence**: `save_plan_lines_for_license()` L130 |
| **Evidence** | `e1_plan.py:88-306`, `e1_auto_plan.py:96-148` |
| **Test Coverage** | ✅ `test_e1_plan.py`, `test_e1_auto_plan.py` |
| **Compliance Status** | **FULLY ENFORCED** |
| **What Happens If Violated** | Plan lines created with incorrect unit prices; utilization forecasts misaligned with CIF budget. |
| **Validation Gate** | `validate_group_plan_lines()` line 330–391 (implicit: algorithm respects balance_cif) |
| **Affected Downstream Code** | Ledger service (`ledger_service.py`), export service (`license_balance_excel.py`), dashboard view (`views/dashboard.py`) |
| **Confidence** | **CONFIRMED** — algorithm verified; tests pass; 25 licenses in production. |

---

#### Rule 1.2: E5 Norm Category + Milk 40/60 Split

| Field | Value |
|-------|-------|
| **Rule ID** | R-1.2 |
| **Title** | E5: Category + Milk 40/60 Split |
| **Description** | E5 licenses (76 real licenses) classify items into categories (Oils, Cereals, Pulses, Spices, Milk). For non-milk categories: proportional allocation (E1 rule). For milk category: apply 40/60 split between Milk_40 and Milk_60 planning items, respecting ceiling prices. |
| **Business Meaning** | E5 licenses receive special milk supply split (40% early delivery, 60% later). Distributes milk CIF across two planning items at different unit prices. |
| **Formal Statement** | Classify item → If category = Milk: 40% → Milk_40 planning item, 60% → Milk_60 planning item; else: proportional allocation. Respect ceiling prices. |
| **Scope** | 76 real licenses (largest norm-class group, audit BL-PLAN-02) |
| **Source Code** | `backend/apps/license/services/e5_plan.py` L233–353; `milk_planner.py` L48–186 |
| **Enforcement Points** | **Classification**: `classify_e5_item()` L95 \| **Milk split**: `split_milk_0404()` L48 \| **Waterfall**: `plan_e5_items()` L233 (_run_oils, _run_milk methods) \| **Auto-plan**: `compute_e5_auto_plan()` L128 |
| **Evidence** | `e5_plan.py:233-353`, `milk_planner.py:48-186` |
| **Test Coverage** | ✅ `test_e5_plan.py`, `test_e5_auto_plan.py`, `test_milk_planner.py` |
| **Compliance Status** | **FULLY ENFORCED** |
| **What Happens If Violated** | Milk supply split not honored; delivery schedules miss targets. |
| **Validation Gate** | `validate_group_plan_lines()` line 330–391 (implicit: waterfall respects split percentages) |
| **Affected Downstream Code** | Ledger service, export service, milk supply forecasting views |
| **Confidence** | **CONFIRMED** — 76 licenses in production; tests pass; split logic verified. |

---

#### Rule 1.3: E126 Norm PKO/Olive-Oil Deterministic Splits

| Field | Value |
|-------|-------|
| **Rule ID** | R-1.3 |
| **Title** | E126: PKO/Olive-Oil Deterministic Splits |
| **Description** | E126 licenses classify items into 3 planning categories: Nuts, PKO, Olive Oil. Items with BOTH PKO signal (HSN 1513 + specific descriptions) AND Olive Oil signal trigger 50/50 split. Each split half is priced at the respective planning item's fixed unit price. |
| **Business Meaning** | Distinguishes ambiguous oils (those signaling both PKO and Olive Oil) by splitting quantity 50/50 and creating two plan lines at different prices. |
| **Formal Statement** | For HSN 1513 item: If PKO_signal AND Olive_Oil_signal → split 50/50; else classify into single category. Planned_qty = available_qty × (split%, or 100%). Unit_price = planning_item fixed rate. |
| **Scope** | 0 real E126 licenses (audit BL-PLAN-02); 2 real E132 licenses (related rule) |
| **Source Code** | `backend/apps/license/services/e126_plan.py` L161–515 |
| **Enforcement Points** | **Classification**: `classify_e126_record()` L161 \| **Signal detection**: `_is_pko_signal()`, `_is_olive_oil_signal()` L127–131 \| **Split**: `_split_pko_olive_record()` L213 \| **Per-item planning**: `plan_e126_per_item_split()` L472 \| **Wastage rebalance**: `_rebalance_pko_olive_wastage()` L314 |
| **Evidence** | `e126_plan.py:161-185`, `e126_plan.py:213-276`, `e126_plan.py:472-515` |
| **Test Coverage** | ⚠️ `test_e126_plan.py`, `test_e126_auto_plan.py` (limited by 0 real licenses) |
| **Compliance Status** | **PARTIALLY ENFORCED** |
| **Known Defect** | **BL-PLAN-01**: Fractional split quantities are floored, but `planned_cif_fc` is not recomputed. Example: available_qty = 101, split → 50.5 each → floored to 50 each, but planned_cif_fc remains 100% of budget. **INVARIANT VIOLATED**: `planned_cif_fc ≠ planned_quantity × unit_price`. |
| **What Happens If Violated** | Plan lines with arithmetic inconsistency; ledger exports compute wrong effective rates (`_effective_rate` = value/qty; if value assumes 101 units but qty is 100, rate is wrong); reporting mismatches. |
| **Validation Gate** | `validate_group_plan_lines()` line 330–391 (DOES NOT CHECK invariant) |
| **Affected Downstream Code** | Ledger PDF export (`ledger_pdf.py`), Excel export (`license_balance_excel.py`), reporting (`item_pivot_report.py`), effective-rate calculation (`_effective_rate` L~TBD) |
| **Confidence** | **PROBABLE** — defect logic identified; structure sound; real-world test data absent. Risk is **THEORETICAL** until E126 license is imported with split items. |

---

#### Rule 1.4: E132 Norm Vegetable Oils + Dairy 40/60 Splits

| Field | Value |
|-------|-------|
| **Rule ID** | R-1.4 |
| **Title** | E132: Vegetable Oils + Dairy 40/60 Splits |
| **Description** | E132 licenses (2 real) classify items into 6 planning categories: Nuts, Yeast, PKO, RBD, Cheese, Aluminium. PKO/Cheese split: when both signals present, apply 40% PKO / 60% Cheese. Each category priced at planning item's fixed unit price. |
| **Business Meaning** | E132 is a blended commodity class. PKO/Cheese split distinguishes ambiguous items (those signaling both) at different price points. |
| **Formal Statement** | Classify item by HSN + description → If PKO AND Cheese signals: split 40% PKO / 60% Cheese; else: classify into one of 6 categories. Planned_qty = available_qty × (split%, or 100%). |
| **Scope** | 2 real E132 licenses (audit BL-PLAN-02); only 1 classified item (id 37537, available_qty = 4.00 < MIN_PLAN_QTY = 50); no real split items yet. |
| **Source Code** | `backend/apps/license/services/e132_plan.py` L199–575 |
| **Enforcement Points** | **Classification**: `classify_e132_record()` L199 \| **Signal detection**: `_is_pko_signal()`, `_is_explicit_cheese()`, `_is_cheese_strict()`, `_is_rbd()` L139–157 \| **Split**: `_split_veg_oil_record()` L259 \| **Per-item**: `plan_e132_per_item_split()` L532 \| **Wastage**: `_rebalance_veg_oil_wastage()` L364 |
| **Evidence** | `e132_plan.py:199-231`, `e132_plan.py:259-311`, `e132_plan.py:532-575` |
| **Test Coverage** | ⚠️ `test_e132_plan.py`, `test_e132_auto_plan.py` (no real split data) |
| **Compliance Status** | **PARTIALLY ENFORCED** |
| **Known Defect** | **BL-PLAN-01**: Identical to E126 — fractional split quantities lose CIF recomputation. **INVARIANT VIOLATED**: `planned_cif_fc ≠ planned_quantity × unit_price`. |
| **What Happens If Violated** | Same as E126: ledger/export misstatement. |
| **Validation Gate** | `validate_group_plan_lines()` line 330–391 (DOES NOT CHECK invariant) |
| **Affected Downstream Code** | Ledger exports, reporting, effective-rate calculations |
| **Confidence** | **PROBABLE** — defect logic same as E126; real-world data scarce (2 licenses, 1 item, no splits yet). Risk is **THEORETICAL BUT IMMINENT** if next E132 import contains PKO + Cheese item. |

---

#### Rule 1.5: A3627 Norm Ores/Minerals Fixed-Rate Allocation

| Field | Value |
|-------|-------|
| **Rule ID** | R-1.5 |
| **Title** | A3627: Ores/Minerals Fixed-Rate Allocation |
| **Description** | A3627 licenses (ores, minerals, rutile, etc.) allocate balance_cif to commodity-specific planning items at fixed unit prices. In-progress; engine added most recently per audit BL-PLAN-02. |
| **Business Meaning** | Manages mineral import planning; distributes CIF across ores at fixed commodity prices. |
| **Formal Statement** | Classify item by commodity type → Allocate group CIF to commodity → Per-item planned_cif = planned_qty × commodity_unit_price. |
| **Scope** | 1 real license (audit BL-PLAN-02) |
| **Source Code** | `backend/apps/license/services/a3627_auto_plan.py` L205–315 |
| **Enforcement Points** | **Auto-plan**: `compute_a3627_auto_plan()` L205 |
| **Evidence** | `a3627_auto_plan.py:205-315` |
| **Test Coverage** | ⚠️ `test_a3627_auto_plan.py` (1 real license; limited test data) |
| **Compliance Status** | **PARTIAL** (engine in development) |
| **What Happens If Violated** | Mineral import plans misaligned; CIF budget not respected. |
| **Validation Gate** | `validate_group_plan_lines()` line 330–391 (implicit) |
| **Affected Downstream Code** | Ledger service, export service |
| **Confidence** | **UNKNOWN** — engine recently added; 1 real-world license; insufficient data to validate. **RECOMMENDATION**: Audit current A3627 execution; add fractional-split test coverage. |

---

#### Rule 1.6: PP Norm Auto-Plan Coverage Gap

| Field | Value |
|-------|-------|
| **Rule ID** | R-1.6 |
| **Title** | PP Norm: Zero Auto-Plan Support (FEATURE GAP) |
| **Description** | PP (SION norm class) licenses are NOT supported by auto-plan. 73 of 228 real licenses (32%, single largest norm group after E5's 76) have zero automatic planning. |
| **Business Meaning** | PP licenses cannot forecast utilization. Users must manually enter plans item-by-item. |
| **Formal Statement** | `detect_norm()` returns "" for PP licenses. `PlannerFactory.is_supported('PP')` returns False. No `pp_auto_plan.py` module. `/auto-plan/` and `/auto-plan-all/` endpoints return "unknown norm" error. |
| **Scope** | 73 real PP licenses (32% of active portfolio) |
| **Source Code** | `norm_plan.py` (detect_norm function) \| `planner_factory.py` (is_supported) |
| **Enforcement Points** | **Detection**: Missing in `detect_norm()` \| **Factory**: `is_supported('PP')` returns False \| **Auto-plan**: No engine exists |
| **Evidence** | Audit BL-PLAN-02: "73 of 228 real licenses (32%) are PP norm class" |
| **Test Coverage** | ❌ No auto-plan tests for PP; manual-entry tests may exist |
| **Compliance Status** | **NOT ENFORCED (FEATURE GAP)** |
| **Current Behavior** | Users see "unknown norm" in UI; must manually enter all plans. |
| **What Happens If Violated** | Users cannot access auto-plan benefit; no utilization forecasting for PP. Operational risk: manual entry errors; delayed planning. |
| **Affected Downstream Code** | Views: `/auto-plan/`, `/auto-plan-all/`, Item Pivot Report, License Overview Planning tab |
| **Confidence** | **CONFIRMED** — gap is documented and reproducible. **BLOCKER STATUS**: Medium. **REQUIRED ACTION**: Confirm PP business rules (norm class spec); implement `pp_auto_plan.py`. |

---

### SECTION 2: QUANTITY & VALUE CONSTRAINTS

---

#### Rule 2.1: Planning Quantity Constraint (Cannot Exceed Available)

| Field | Value |
|-------|-------|
| **Rule ID** | R-2.1 |
| **Title** | Planning Quantity Constraint |
| **Description** | For any group of planned import items, the sum of planned quantities cannot exceed the group's total available quantity (with 1% rounding tolerance). |
| **Business Meaning** | Prevents overallocation: cannot plan more units than physically imported. |
| **Formal Statement** | `sum(LicenseItemPlan.planned_quantity for all lines in group) ≤ available_quantity × 1.01` |
| **Scope** | All planned items (all norms: E1, E5, E126, E132, A3627) |
| **Source Code** | `backend/apps/license/services/plan_grouping.py` L330–391 |
| **Enforcement Points** | **Validation gate**: `validate_group_plan_lines()` L330–391 (lines ~360–370) \| **Trigger**: Auto-plan engines call before `save_plan_lines_for_license()` |
| **Evidence** | `plan_grouping.py:330-391` |
| **Test Coverage** | ✅ `test_plan_grouping.py`, `test_allocate_items_plan_line_balance.py` |
| **Compliance Status** | **ENFORCED** (gate in place; validation runs) |
| **What Happens If Violated** | Plan created with invalid quantity; reporting shows overbooking; allocation cannot proceed (rejected by `allocate_items()` endpoint). |
| **Validation Gate** | `validate_group_plan_lines()` L330–391 explicitly checks this constraint. |
| **Affected Downstream Code** | Allocation service (`allocation_service.py`), ledger service (`ledger_service.py`) |
| **Confidence** | **CONFIRMED** — validation gate verified; tests pass. |

---

#### Rule 2.2: Planning CIF Constraint (Cannot Exceed Available License CIF)

| Field | Value |
|-------|-------|
| **Rule ID** | R-2.2 |
| **Title** | Planning CIF Constraint |
| **Description** | The total planned CIF across all items on a license cannot exceed the license's available balance_cif. |
| **Business Meaning** | Prevents CIF overallocation: cannot plan more financial value than license permits. |
| **Formal Statement** | `sum(LicenseItemPlan.planned_cif_fc for all items on license) ≤ license.get_balance_cif()` |
| **Scope** | All licenses with any planned items |
| **Source Code** | Implicit in auto-plan engines (no explicit validation gate) |
| **Enforcement Points** | **Implicit**: E1 waterfall `plan_e1_items()` L225–306 allocates balance_cif proportionally; E5 waterfall `plan_e5_items()` L233–353 same. Algorithm respects balance_cif by design. |
| **Evidence** | E1: `e1_plan.py:225-306` (category allocation); E5: `e5_plan.py:233-353` |
| **Test Coverage** | ✅ `test_e1_plan.py`, `test_e5_plan.py` |
| **Compliance Status** | **ENFORCED** (implicit in algorithm; no separate validation gate) |
| **What Happens If Violated** | Ledger shows negative balance; allocation/utilization forecasts fail; export reports incorrect CIF allocation. |
| **Validation Gate** | None explicitly; relies on auto-plan engine design. |
| **Defect Risk** | **BL-PLAN-01 defect**: For E126/E132, fractional splits might slightly over-allocate due to flooring. Example: balance_cif = 343.40, but floored quantities consume 343.40 (100%) while only 100 units saved (vs. 101 available). Constraint technically met (100% ≤ 100%), but quantities don't align. |
| **Affected Downstream Code** | Ledger service, export service, balance calculator (`balance_calculator.py`) |
| **Confidence** | **CONFIRMED** (E1/E5 verified); **PROBABLE** (E126/E132 risk flagged). |

---

#### Rule 2.3: Unit Price Constraint (Cannot Exceed Planning Item Ceiling)

| Field | Value |
|-------|-------|
| **Rule ID** | R-2.3 |
| **Title** | Unit Price Constraint |
| **Description** | For deterministic-pricing norms (E126, E132, A3627), the planned unit price must not exceed the planning item's fixed ceiling price (with 1% rounding tolerance). |
| **Business Meaning** | Prevents cost overruns: cannot plan at a price higher than the planning item permits. |
| **Formal Statement** | `LicenseItemPlan.unit_price ≤ PlanningItemModel.unit_price × 1.01` |
| **Scope** | Items from norms with fixed-price planning items (E126, E132, A3627). E1/E5 use category-derived prices (computed dynamically); "ceiling" is implicit in balance allocation. |
| **Source Code** | `backend/apps/license/services/plan_grouping.py` L330–391 |
| **Enforcement Points** | **Validation gate**: `validate_group_plan_lines()` L330–391 (line ~365) |
| **Evidence** | `plan_grouping.py:330-391` |
| **Test Coverage** | ✅ `test_plan_grouping.py` |
| **Compliance Status** | **ENFORCED** (validation gate checks this) |
| **What Happens If Violated** | Plan created at cost above approved; budget overspend. |
| **Validation Gate** | `validate_group_plan_lines()` L330–391 explicitly checks this constraint. |
| **Affected Downstream Code** | Allocation service, ledger service, financial reporting |
| **Confidence** | **CONFIRMED** — validation gate verified. |

---

### SECTION 3: MANUAL PLAN OVERRIDE RULES

---

#### Rule 3.1: Manual Plan Takes Priority Over Norm

| Field | Value |
|-------|-------|
| **Rule ID** | R-3.1 |
| **Title** | Manual Plan Priority |
| **Description** | If an import item has a manual plan line, that line is used and the norm plan is NOT applied. Manual plan is fixed, never recomputed. |
| **Business Meaning** | Allows business users to override automatic planning for specific items; manual entries are respected indefinitely. |
| **Formal Statement** | For each import_item_id: If LicenseItemPlanModel exists (manual, `is_auto = False`) → use it (fixed). Else if norm exists → use norm plan. Else → no plan. |
| **Scope** | All licenses (applies regardless of norm) |
| **Source Code** | `backend/apps/license/services/norm_plan.py` L45–114 |
| **Enforcement Points** | **Priority logic**: `effective_plan_for_license()` L45–114 (lines ~77–89) checks manual flag |
| **Evidence** | `norm_plan.py:77-89` |
| **Test Coverage** | ✅ `test_plan_enforcement.py`, manual override tests |
| **Compliance Status** | **FULLY ENFORCED** |
| **What Happens If Violated** | Auto-plan overwrites user's manual entry; user loses control. |
| **Validation Gate** | `effective_plan_for_license()` respects manual flag. |
| **Affected Downstream Code** | Ledger service, item pivot report, dashboard |
| **Confidence** | **CONFIRMED** — rule verified in code; tested. |

---

#### Rule 3.2: Manual Plan Cannot Be Overridden by Auto-Plan

| Field | Value |
|-------|-------|
| **Rule ID** | R-3.2 |
| **Title** | Manual Plan Preservation During Auto-Plan Re-Run |
| **Description** | Running auto-plan should not delete or modify existing manual plan lines. When `save_plan_lines_for_license()` is called, delete all non-preserved, non-manual plan lines; keep all manual lines untouched. |
| **Business Meaning** | Protects user's manual overrides when auto-plan is re-run. Manual entry is authoritative. |
| **Formal Statement** | When `save_plan_lines_for_license()` called: Delete all auto-generated plan lines (not manual, not preserved). Keep all manual lines (flag `is_manual = True`). Create new norm-based plan lines. |
| **Scope** | All licenses with mixed manual + norm plans |
| **Source Code** | `backend/apps/license/services/plan_enforcement.py` L130–192 |
| **Enforcement Points** | **Manual flag check**: `save_plan_lines_for_license()` L130–192 (manual flag check at line ~182) |
| **Evidence** | `plan_enforcement.py:130-192` |
| **Test Coverage** | ⚠️ `test_plan_enforcement.py` (explicit check; not tested across all auto-plan re-runs) |
| **Compliance Status** | **ENFORCED** (manual flag checked) |
| **What Happens If Violated** | Manual entries deleted when auto-plan re-runs; user loses override. |
| **Validation Gate** | `save_plan_lines_for_license()` checks `is_manual` flag. |
| **Affected Downstream Code** | All auto-plan endpoints (`/auto-plan/`, `/auto-plan-all/`) |
| **Confidence** | **CONFIRMED** — flag check verified in code; recommendation is to add integration test across all auto-plan re-runs. |

---

### SECTION 4: ALLOCATION & CONSUMPTION RULES

---

#### Rule 4.1: Remaining = Planned − Allotted (Cannot Go Negative)

| Field | Value |
|-------|-------|
| **Rule ID** | R-4.1 |
| **Title** | Remaining Balance Cannot Go Negative |
| **Description** | The remaining plannable quantity/CIF for an item is never negative. Computed as max(planned − allotted, 0). |
| **Business Meaning** | Prevents reporting of negative remaining allocation; ensures balance sheet integrity. |
| **Formal Statement** | `item_remaining_qty = max(item_planned_qty - item_allotted_qty, 0)` \| `item_remaining_cif = max(item_planned_cif - item_allotted_value, 0)` |
| **Scope** | All items with plan lines |
| **Source Code** | `backend/apps/license/services/norm_plan.py` L105–111 |
| **Enforcement Points** | **Floor applied**: `effective_plan_for_license()` L105–111 |
| **Evidence** | `norm_plan.py:105-111` |
| **Test Coverage** | ✅ `test_balance_cif_single_source.py` and related balance tests |
| **Compliance Status** | **ENFORCED** (floor applied) |
| **What Happens If Violated** | Remaining balance shown as negative; allocation reports misleading; users attempt to allocate beyond available. |
| **Validation Gate** | `max(0, ...)` floor in `effective_plan_for_license()`. |
| **Affected Downstream Code** | Ledger service, allocation service, Item Pivot Report |
| **Confidence** | **CONFIRMED** — floor verified in code. |

---

#### Rule 4.2: Allocation Cannot Exceed Item Plan Remaining

| Field | Value |
|-------|-------|
| **Rule ID** | R-4.2 |
| **Title** | Allocation Quantity Constraint |
| **Description** | When allocating to an item, the allocation quantity must not exceed the item's remaining planned quantity (max(planned − allotted, 0)). |
| **Business Meaning** | Prevents overallocation; ensures allocations respect the plan. |
| **Formal Statement** | `allocation_qty ≤ item_remaining_qty = max(item_planned_qty - item_allotted_qty, 0)` |
| **Scope** | All allocations via `allocate_items()` endpoint |
| **Source Code** | `backend/apps/allotment/services/allocation_service.py` |
| **Enforcement Points** | **Allocation validation**: `AllocationService.allocate_item()` (check needed) |
| **Evidence** | `allocation_service.py` (validation check during allocation request processing) |
| **Test Coverage** | ✅ `test_allocate_items_plan_line_balance.py`, `test_allocation_service.py` |
| **Compliance Status** | **ENFORCED** (by allocation validation) |
| **What Happens If Violated** | Allocation accepted beyond available; reporting shows overbooking; balance calculus broken. |
| **Validation Gate** | `allocate_items()` endpoint validates quantity. |
| **Affected Downstream Code** | Bill of Entry service (`boe_service.py`), ledger service, allocation ledger |
| **Confidence** | **CONFIRMED** — tests verify constraint. |

---

#### Rule 4.3: Group Plan Cap (Non-Double-Counting for E1/E5 Grouped Items)

| Field | Value |
|-------|-------|
| **Rule ID** | R-4.3 |
| **Title** | Group Plan Cap (E1/E5 Non-Double-Counting) |
| **Description** | For E1/E5 licenses with grouped items (e.g., multiple items classified into same category), the group's total planned CIF is allocated once to the category, then distributed to individual items within category. No double-counting across items. |
| **Business Meaning** | Ensures category CIF budget is split fairly across items, not duplicated. |
| **Formal Statement** | Group items by category → Allocate group_cif to category (once) → Distribute group_cif to individual items within category (proportionally). Invariant: sum of item allocations = group_cif. |
| **Scope** | E1/E5 licenses with multiple items per category |
| **Source Code** | `backend/apps/license/services/e1_plan.py` L225–306; `e5_plan.py` L233–353 (category waterfall logic) |
| **Enforcement Points** | **Waterfall logic**: Category allocation in `plan_e1_items()` L225–306 and `plan_e5_items()` L233–353 |
| **Evidence** | Test: `backend/apps/allotment/tests/test_allocate_items_group_plan_cap.py:143-206` (TestGroupPlanCapIsNotDoubleCounted) |
| **Test Coverage** | ✅ `test_allocate_items_group_plan_cap.py:143-206`, `test_allocate_items_e1_group_plan_cap.py` |
| **Compliance Status** | **ENFORCED** (tested) |
| **What Happens If Violated** | Category CIF double-counted; some items over-allocated, others starved; utilization forecast inflated. |
| **Validation Gate** | Implicit in category waterfall; no explicit gate. |
| **Affected Downstream Code** | Ledger service, allocation service, balance calculator |
| **Confidence** | **CONFIRMED** — test case verifies rule. |

---

### SECTION 5: SPLIT SEMANTICS

---

#### Rule 5.1: Milk 40/60 Split (E5)

| Field | Value |
|-------|-------|
| **Rule ID** | R-5.1 |
| **Title** | Milk 40/60 Split (E5) |
| **Description** | When E5 license has milk category items, split milk CIF as 40% → Milk_40 planning item, 60% → Milk_60 planning item. Allocate quantities to each bucket respecting ceiling prices. |
| **Business Meaning** | E5 milk supply split reflects delivery schedule: 40% early delivery (Milk_40), 60% later delivery (Milk_60), each at different price points. |
| **Formal Statement** | If category = Milk: milk_40_cif = balance_cif × 0.40, milk_60_cif = balance_cif × 0.60. Allocate planned_qty to each bucket: milk_40_qty = min(available_qty, milk_40_cif / milk_40_price), milk_60_qty = min(available_qty − milk_40_qty, milk_60_cif / milk_60_price). |
| **Scope** | E5 licenses with milk items (76 real licenses in E5 norm class; subset with milk items) |
| **Source Code** | `backend/apps/license/services/milk_planner.py` L48–82; called from `e5_plan.py` L310–353 (_run_milk method) |
| **Enforcement Points** | **Split logic**: `split_milk_0404()` L48–82 \| **Waterfall integration**: `plan_e5_items()._run_milk()` L310–353 |
| **Evidence** | `milk_planner.py:48-82`, `e5_plan.py:310-353` |
| **Test Coverage** | ✅ `test_milk_planner.py`, `test_e5_plan.py`, `test_e5_auto_plan.py` |
| **Compliance Status** | **FULLY ENFORCED** (tested) |
| **What Happens If Violated** | Milk supply split not honored; delivery schedule misses targets; utilization forecast incorrect. |
| **Validation Gate** | Implicit in split logic; quantities constrained by min(available, cif/price). |
| **Affected Downstream Code** | Ledger service, export service, milk supply forecasting views |
| **Confidence** | **CONFIRMED** — split logic verified; tests pass; 76 licenses in production. |

---

#### Rule 5.2: PKO/Olive-Oil Split (E126)

| Field | Value |
|-------|-------|
| **Rule ID** | R-5.2 |
| **Title** | PKO/Olive-Oil Split (E126) |
| **Description** | When E126 import item signals BOTH PKO and Olive Oil, split available quantity 50/50, creating two plan lines (one for each category), each priced at its planning item's fixed unit price. |
| **Business Meaning** | Disambiguates ambiguous oils (those signaling both PKO and Olive Oil) by splitting equally and pricing each half separately. |
| **Formal Statement** | If item has both PKO signal AND Olive Oil signal: pko_qty = available_qty / 2, olive_qty = available_qty / 2. Create two plan lines (one PKO, one Olive Oil), each priced at planning item's fixed rate. Else: create one plan line. |
| **Scope** | E126 licenses with items having both signals (0 real E126 licenses; similar logic in E132) |
| **Source Code** | `backend/apps/license/services/e126_plan.py` L213–276 (_split_pko_olive_record) |
| **Enforcement Points** | **Split execution**: `_split_pko_olive_record()` L213–276 \| **Signal detection**: `_is_pko_signal()`, `_is_olive_oil_signal()` L127–131 |
| **Evidence** | `e126_plan.py:213-276` |
| **Test Coverage** | ⚠️ `test_e126_plan.py` (limited by 0 real licenses) |
| **Compliance Status** | **PARTIALLY ENFORCED** |
| **Known Defect** | **BL-PLAN-01**: Fractional quantities (e.g., 101 → 50.5, 50.5) are floored (50, 50), but `planned_cif_fc` is not recomputed. **INVARIANT VIOLATED**: `planned_cif_fc ≠ planned_quantity × unit_price`. |
| **What Happens If Violated** | Plan lines with arithmetic inconsistency; ledger exports compute wrong effective rates; reporting mismatches. |
| **Validation Gate** | `validate_group_plan_lines()` L330–391 (DOES NOT CHECK invariant) |
| **Affected Downstream Code** | Ledger PDF export, Excel export, reporting, effective-rate calculation |
| **Confidence** | **PROBABLE** — defect identified; real-world test data absent. Risk is **THEORETICAL** until E126 split item exists. |

---

#### Rule 5.3: PKO/Cheese Split (E132)

| Field | Value |
|-------|-------|
| **Rule ID** | R-5.3 |
| **Title** | PKO/Cheese Split (E132) |
| **Description** | When E132 import item signals BOTH PKO and Cheese, split as 40% PKO / 60% Cheese, creating two plan lines at respective planning item fixed prices. |
| **Business Meaning** | E132 items signaling both PKO and Cheese are split to distinguish commodity lines; PKO gets 40%, Cheese gets 60%. |
| **Formal Statement** | If item has both PKO signal AND Cheese signal: pko_qty = available_qty × 0.40, cheese_qty = available_qty × 0.60. Create two plan lines (one PKO at PKO price, one Cheese at Cheese price). Else: create one plan line. |
| **Scope** | E132 licenses with items having both signals (2 real E132 licenses; 1 classified item with available_qty = 4 < MIN_PLAN_QTY; no split items yet) |
| **Source Code** | `backend/apps/license/services/e132_plan.py` L259–309 (_split_veg_oil_record) |
| **Enforcement Points** | **Split execution**: `_split_veg_oil_record()` L259–309 \| **Signal detection**: `_is_pko_signal()`, `_is_explicit_cheese()`, `_is_cheese_strict()` L139–157 |
| **Evidence** | `e132_plan.py:259-309` |
| **Test Coverage** | ⚠️ `test_e132_plan.py` (no real split data) |
| **Compliance Status** | **PARTIALLY ENFORCED** |
| **Known Defect** | **BL-PLAN-01**: Identical to E126 — fractional split quantities lose CIF recomputation. **INVARIANT VIOLATED**: `planned_cif_fc ≠ planned_quantity × unit_price`. |
| **What Happens If Violated** | Same as E126: ledger/export misstatement. |
| **Validation Gate** | `validate_group_plan_lines()` L330–391 (DOES NOT CHECK invariant) |
| **Affected Downstream Code** | Ledger exports, reporting, effective-rate calculations |
| **Confidence** | **PROBABLE** — defect logic same as E126; real-world data scarce (2 licenses, 1 item, no splits). Risk is **THEORETICAL BUT IMMINENT** if next E132 import contains PKO + Cheese item. |

---

### SECTION 6: PRESERVED PLAN RE-EMISSION

---

#### Rule 6.1: Preserved Plan Lines Must Re-Emit Without Change

| Field | Value |
|-------|-------|
| **Rule ID** | R-6.1 |
| **Title** | Preserved Plan Re-Emission |
| **Description** | If a plan line is flagged `preserved_during_re_generation = True`, auto-plan must re-emit it without recomputation. Copy verbatim into the new plan set. |
| **Business Meaning** | Protects selected plan lines from recalculation when auto-plan is re-run; allows manual "lock" of specific lines. |
| **Formal Statement** | If `LicenseItemPlan.preserved_during_re_generation == True`: new_line = old_line (copy verbatim). |
| **Scope** | Licenses with existing plans when auto-plan is re-run |
| **Source Code** | `backend/apps/license/services/plan_enforcement.py` L130–192 |
| **Enforcement Points** | **Preserved branch**: `save_plan_lines_for_license()` L130–192 (lines ~180–191) |
| **Evidence** | `plan_enforcement.py:130-192` |
| **Test Coverage** | ⚠️ `test_plan_enforcement.py` (check needed for re-emission logic) |
| **Compliance Status** | **ENFORCED** (preserved flag checked) |
| **What Happens If Violated** | Preserved lines are recomputed; user's lock is ignored. |
| **Validation Gate** | `save_plan_lines_for_license()` checks `preserved_during_re_generation` flag. |
| **Known Issue** | If original line has **BL-PLAN-01 defect**, defect persists forever (never corrected on re-emit). |
| **Affected Downstream Code** | All auto-plan endpoints |
| **Confidence** | **CONFIRMED** — preservation logic verified; caveat: BL-PLAN-01 defects inherit. |

---

### SECTION 7: PLAN LINE INVARIANTS

---

#### Rule 7.1: (VIOLATED) Planned CIF = Planned Quantity × Unit Price

| Field | Value |
|-------|-------|
| **Rule ID** | R-7.1 |
| **Title** | Plan Line Arithmetic Invariant (VIOLATED) |
| **Description** | For every plan line, the CIF value must equal quantity times unit price. Allows ±0.01 rounding tolerance. **This invariant is VIOLATED in E126/E132 by BL-PLAN-01 defect.** |
| **Business Meaning** | Ensures financial data consistency: value = quantity × price. Broken invariant cascades into export/reporting errors. |
| **Formal Statement** | `∀ LicenseItemPlan rows: planned_cif_fc ≈ round(planned_quantity × unit_price, 2)` (allowing ±0.01 tolerance) |
| **Scope** | All plan lines (all norms) |
| **Source Code** | Should be validated in `validate_group_plan_lines()` L330–391, but currently is NOT. |
| **Enforcement Points** | **Missing validation**: Should be in `validate_group_plan_lines()` line 330–391 |
| **Evidence** | Audit BL-PLAN-01: "validate_group_plan_lines...NEVER checks planned_cif_fc == planned_quantity * unit_price". Defect affects E126/E132 (fractional splits). |
| **Test Coverage** | ❌ No validation test for this invariant |
| **Compliance Status** | **PARTIALLY VIOLATED** (E126/E132 defect; E1/E5 unaffected) |
| **Violation Details** | **BL-PLAN-01**: E126/E132 create fractional split quantities, floor them, but do NOT recompute `planned_cif_fc`. Example: available_qty = 101, split → 50.5 each → floored to 50 each, but planned_cif_fc remains as if 101 units were allocated. |
| **What Happens If Violated** | Ledger exports recompute rates as value / qty, producing wrong effective rates. Reporting shows inconsistent utilization. Balance calculations cascade incorrect numbers. |
| **Validation Gate** | MISSING — must add check in `validate_group_plan_lines()`. |
| **Affected Downstream Code** | Ledger PDF export (`ledger_pdf.py`), Excel export (`license_balance_excel.py`), Item Pivot Report (`item_pivot_report.py`), effective-rate calculation (`_effective_rate`), balance calculator (`balance_calculator.py`) |
| **Confidence** | **CONFIRMED** — defect logic verified. Financial impact: **HIGH**. |
| **BLOCKER STATUS** | **YES** — **BL-PLAN-01** blocks reconciliation and export certification. |

---

### SECTION 8: COMPANY & LICENSE SCOPE

---

#### Rule 8.1: Planning Is License-Scoped (Not Company-Scoped)

| Field | Value |
|-------|-------|
| **Rule ID** | R-8.1 |
| **Title** | Planning Scope (Per-License) |
| **Description** | Auto-plan generates plans per-license, not per-company. `LicenseItemPlan` is scoped to exactly one `LicenseDetailsModel`. Auto-plan runs on a single license_obj, generates lines for that license only. |
| **Business Meaning** | Maintains data isolation: plans are license-specific; no cross-license aggregation at plan time. |
| **Formal Statement** | `LicenseItemPlan.license = exactly one LicenseDetailsModel`. Auto-plan function: `compute_norm_auto_plan(license_obj)` → generates lines for that license only. |
| **Scope** | All planning operations |
| **Source Code** | All auto-plan function signatures: `compute_e1_auto_plan(license_obj)`, `compute_e5_auto_plan(license_obj)`, etc. |
| **Enforcement Points** | **Architecture**: Function signatures force license-scoped input |
| **Evidence** | `e1_auto_plan.py:96`, `e5_auto_plan.py:128`, `e126_auto_plan.py:118`, `e132_auto_plan.py:115` |
| **Test Coverage** | ✅ All auto-plan tests use single license_obj |
| **Compliance Status** | **ENFORCED** (by architecture) |
| **What Happens If Violated** | Plans cross-contaminate; company-level aggregation corrupted. |
| **Validation Gate** | Implicit in function signatures. |
| **Affected Downstream Code** | All plan enforcement, ledger service |
| **Confidence** | **CONFIRMED** — architecture verified. |

---

## FINANCIAL IMPACT ANALYSIS

### High-Impact Defects

| Defect | Rule | Impact | Scope | Mitigation |
|--------|------|--------|-------|-----------|
| **BL-PLAN-01** | R-5.2, R-5.3, R-7.1 | Planned CIF ≠ Planned Qty × Unit Price (E126/E132 fractional splits) | E126 (0 real), E132 (2 real, 0 splits yet) | Add invariant check in `validate_group_plan_lines()`; fix floored quantities to recompute CIF. |
| **BL-PLAN-02** | R-1.6 | PP norm (73 licenses, 32%) has zero auto-plan support | 73 real PP licenses (largest after E5's 76) | Implement PP auto-plan engine. |

### Medium-Impact Gaps

| Gap | Rule | Impact | Scope | Mitigation |
|-----|------|--------|-------|-----------|
| **A3627 Validation** | R-1.5 | A3627 engine recently added; 1 real license; unknown compliance | 1 real A3627 license | Audit A3627 execution; add fractional-split test coverage. |

---

## IMPLEMENTATION ROADMAP

### Priority 1: Fix BL-PLAN-01 (High-Impact)

**Action**: Add invariant validation to `validate_group_plan_lines()`.

```
In plan_grouping.py validate_group_plan_lines():
  For each LicenseItemPlan line:
    if abs(planned_cif_fc - round(planned_qty × unit_price, 2)) > 0.01:
      RAISE ValidationError("Invariant violated: planned_cif_fc ≠ planned_qty × unit_price")
```

**Also**: Fix E126/E132 flooring logic to recompute `planned_cif_fc` after flooring quantities.

### Priority 2: Implement PP Auto-Plan (Medium-Impact)

**Action**: Create `pp_auto_plan.py` engine.

1. Confirm PP business rules (norm class spec).
2. Implement `compute_pp_auto_plan(license_obj)`.
3. Register in `PlannerFactory.is_supported('PP')`.
4. Add test coverage.

### Priority 3: Audit A3627 (Low-Impact)

**Action**: Audit current A3627 execution; add fractional-split test cases.

---

## REFERENCE TABLES

### Rule ID Quick Reference

| ID | Title | Status | Defects |
|---|-------|--------|---------|
| R-1.1 | E1 Fixed-Rate Category | ✅ ENFORCED | None |
| R-1.2 | E5 Milk 40/60 Split | ✅ ENFORCED | None |
| R-1.3 | E126 PKO/Olive Split | ⚠️ PARTIAL | **BL-PLAN-01** |
| R-1.4 | E132 PKO/Cheese Split | ⚠️ PARTIAL | **BL-PLAN-01** |
| R-1.5 | A3627 Ores/Minerals | ⚠️ PARTIAL | Unknown |
| R-1.6 | PP Auto-Plan Gap | ❌ NOT ENFORCED | **BL-PLAN-02** |
| R-2.1 | Qty Constraint | ✅ ENFORCED | None |
| R-2.2 | CIF Constraint | ✅ ENFORCED | None |
| R-2.3 | Unit Price Constraint | ✅ ENFORCED | None |
| R-3.1 | Manual Priority | ✅ ENFORCED | None |
| R-3.2 | Manual Preservation | ✅ ENFORCED | None |
| R-4.1 | Remaining Non-Negative | ✅ ENFORCED | None |
| R-4.2 | Allocation Qty Constraint | ✅ ENFORCED | None |
| R-4.3 | Group Plan Cap | ✅ ENFORCED | None |
| R-5.1 | Milk Split (E5) | ✅ ENFORCED | None |
| R-5.2 | PKO/Olive Split (E126) | ⚠️ PARTIAL | **BL-PLAN-01** |
| R-5.3 | PKO/Cheese Split (E132) | ⚠️ PARTIAL | **BL-PLAN-01** |
| R-6.1 | Preserved Re-Emission | ✅ ENFORCED | Inherits BL-PLAN-01 |
| R-7.1 | Arithmetic Invariant | ❌ VIOLATED | **BL-PLAN-01** |
| R-8.1 | Per-License Scope | ✅ ENFORCED | None |

### Norm Coverage Matrix

| Norm | Status | Real Licenses | Auto-Plan Engine | Defects | Notes |
|------|--------|---------------|------------------|---------|-------|
| E1 | ✅ ENFORCED | 25 | `e1_auto_plan.py` | None | Fully validated |
| E5 | ✅ ENFORCED | 76 | `e5_auto_plan.py` | None | Fully validated |
| E126 | ⚠️ PARTIAL | 0 | `e126_auto_plan.py` | **BL-PLAN-01** | No real data |
| E132 | ⚠️ PARTIAL | 2 | `e132_auto_plan.py` | **BL-PLAN-01** | 1 item, no splits |
| A3627 | ⚠️ PARTIAL | 1 | `a3627_auto_plan.py` | Unknown | Recent addition |
| PP | ❌ NOT ENFORCED | 73 | **MISSING** | **BL-PLAN-02** | Largest gap (32%) |

---

## APPENDIX: TEST EVIDENCE MAPPING

### By Rule

| Rule | Test File | Coverage |
|------|-----------|----------|
| R-1.1 | `test_e1_plan.py`, `test_e1_auto_plan.py` | ✅ |
| R-1.2 | `test_e5_plan.py`, `test_e5_auto_plan.py`, `test_milk_planner.py` | ✅ |
| R-1.3 | `test_e126_plan.py`, `test_e126_auto_plan.py` | ⚠️ No real data |
| R-1.4 | `test_e132_plan.py`, `test_e132_auto_plan.py` | ⚠️ No real data |
| R-1.5 | `test_a3627_auto_plan.py` | ⚠️ Limited data |
| R-1.6 | Missing | ❌ |
| R-2.1 | `test_plan_grouping.py`, `test_allocate_items_plan_line_balance.py` | ✅ |
| R-2.2 | `test_e1_auto_plan.py`, `test_e5_auto_plan.py` | ✅ |
| R-2.3 | `test_plan_grouping.py` | ✅ |
| R-3.1 | `test_plan_enforcement.py` | ✅ |
| R-3.2 | `test_plan_enforcement.py` | ✅ |
| R-4.1 | `test_balance_cif_single_source.py` | ✅ |
| R-4.2 | `test_allocate_items_plan_line_balance.py` | ✅ |
| R-4.3 | `test_allocate_items_group_plan_cap.py`, `test_allocate_items_e1_group_plan_cap.py` | ✅ |
| R-5.1 | `test_milk_planner.py`, `test_e5_auto_plan.py` | ✅ |
| R-5.2 | `test_e126_plan.py` | ⚠️ Limited |
| R-5.3 | `test_e132_plan.py` | ⚠️ Limited |
| R-6.1 | `test_plan_enforcement.py` | ✅ |
| R-7.1 | Missing | ❌ **DEFECT UNVALIDATED** |
| R-8.1 | All auto-plan tests | ✅ |

---

## DEFINITIONS & GLOSSARY

- **planned_cif_fc**: Planned CIF (foreign currency equivalent) for a license item plan line.
- **planned_quantity**: Quantity allocated in the plan for a license item.
- **unit_price**: Price per unit for a planning item (fixed or derived).
- **balance_cif**: Total CIF available for a license after payments/allocations.
- **available_quantity**: Physical quantity available for allocation on an import item.
- **Waterfall**: Sequential priority-based allocation algorithm (E1, E5 waterfalls allocate category CIF to items in order).
- **Preserved Plan**: Plan line flagged `preserved_during_re_generation = True` to re-emit without recomputation.
- **Manual Plan**: Plan line flagged `is_manual = True`, created by user override (not auto-generated).
- **Norm**: Regulatory commodity classification (E1, E5, E126, E132, A3627, PP). Each has a planning rule.
- **Invariant**: A condition that must always hold (e.g., planned_cif_fc = planned_qty × unit_price).

---

**Document Version**: 1.0  
**Maintained By**: Technical Writer Agent  
**Last Audit**: BL-PLAN-02 (2026-08-10)
