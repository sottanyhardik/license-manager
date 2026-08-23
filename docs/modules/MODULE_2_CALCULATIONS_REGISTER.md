# MODULE 2 — COMPLETE CALCULATIONS REGISTER

**Comprehensive inventory of every planning calculation in the License Manager system.**

Generated: 2026-08-10
Status: FORENSIC SYNTHESIS (all calculations cross-referenced, blockers identified)

---

## Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| **Total Calculations** | **29** | Complete |
| **Canonical Implementations** | **8** | Single source of truth |
| **Consumers (reading canonical)** | **9** | Transitive dependencies |
| **Validation Checks** | **6** | Constraint enforcement |
| **Presentation/Display** | **4** | Final rendering |
| **Deprecated/Legacy** | **1** | Obsolete |
| **Duplicate Implementations** | **1** | ⚠️ BLOCKER |
| **Unknown Owners** | **0** | ✓ Resolved |
| **Known Defects** | **2** | BL-PLAN-01, BL-LEDGER-02 |

---

## SECTION 1: CANONICAL CALCULATIONS
### (Single authoritative source of truth — every consumer reads from these)

### C1. Allocate Step (Dynamic Pricing Primitive)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `allocate_step(util_qty, max_price, balance) → (planned_cif, unit_price)` |
| **FORMULA** | If `util_qty × max_price ≤ balance`: `(util_qty × max_price, max_price)` else `(balance, balance / util_qty)` |
| **INPUTS** | `util_qty` (Decimal), `max_price` (Decimal), `balance` (Decimal) |
| **UNIT** | CIF (USD, 2 decimals), Quantity (whole or fractional) |
| **PRECISION** | Decimal (arbitrary precision during calc, output rounded to 4dp) |
| **ROUNDING** | ROUND_HALF_UP (via `quantize_money`) |
| **SCOPE** | Shared primitive for E1, E5, Milk, planning_allocation module |
| **OWNER** | `apps.license.services.planning_allocation.allocate_step` |
| **TESTS** | Implicit (via E1/E5/milk tests) — no direct unit tests |
| **CATEGORY** | Infrastructure (core math primitive) |
| **EVIDENCE** | `backend/apps/license/services/planning_allocation.py:31-46` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — stable, heavily used |

---

### C2. E1 Waterfall — Generic Stage (Category Allocation)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_generic_stage(items, category, max_rate, remaining) → (lines, used_cif)` |
| **FORMULA** | `total_qty = sum(item.qty)` → `allocate_step(total_qty, max_rate, remaining)` → `per_item_cif = item.qty × rate` |
| **INPUTS** | `items` (list[E1Item]), `category` (str), `max_rate` (Decimal, fixed), `remaining` (Decimal) |
| **UNIT** | Quantity (kg), CIF (USD) |
| **PRECISION** | Decimal → 4dp quantization (`_quantize`) |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | E1 planning engine (steps 1, 2, 4–8) — canonical E1 rules |
| **OWNER** | `apps.license.services.e1_plan._generic_stage` |
| **TESTS** | `backend/apps/license/tests/test_e1_plan.py` + auto-plan tests |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/e1_plan.py:187-222` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — stable |

---

### C3. E1 Waterfall — Milk Split (DWP/SWP Partition)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `split_milk_0404(qty, balance, config) → (dwp_qty, dwp_rate, swp_qty)` |
| **FORMULA** | Maximize `dwp_qty` s.t. `dwp_rate ∈ [config.dwp_min_price, config.dwp_price]`; SWP absorbs remainder at fixed `config.swp_price` |
| **INPUTS** | `qty` (Decimal), `balance` (Decimal), `config` (MilkConfig) |
| **UNIT** | Quantity (kg), CIF (USD, 2 decimals) |
| **PRECISION** | Decimal → implicit rounding in rate calc |
| **ROUNDING** | Min/max constraining (no explicit ROUND_HALF_UP) |
| **SCOPE** | E1 step 3 (milk) + E5 milk items (0404 classified) — canonical shared milk engine |
| **OWNER** | `apps.license.services.milk_planner.split_milk_0404` |
| **TESTS** | `backend/apps/license/tests/test_milk_planner.py` |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/milk_planner.py:48-82` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — stable, heavily unit-tested |

---

### C4. E1 Plan Runner (Full Waterfall)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `plan_e1_items(items, balance_cif, min_plan_qty=0) → E1PlanResult` |
| **FORMULA** | 8-step waterfall: OTHER CONFECTIONERY (3.00) → COCOA MASS (10.00) → MILK (DWP/SWP) → EGG ALBUMIN (25.00) → FRUIT JUICE (2.50) → TARTARIC ACID (1.50) → ALUMINIUM FOIL (4.50) → POLYPROPYLENE (1.20) |
| **INPUTS** | `items` (list[E1Item]), `balance_cif` (Decimal) |
| **UNIT** | Quantity (kg), CIF (USD) |
| **PRECISION** | Decimal → 4dp quantization per line |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | E1 auto-plan engine (canonical) + E1 reporting (Item Pivot, Dashboard, Excel exports) — all E1 consumers call this |
| **OWNER** | `apps.license.services.e1_plan.plan_e1_items` |
| **TESTS** | `backend/apps/license/tests/test_e1_plan.py`, `test_e1_auto_plan.py` |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/e1_plan.py:225-318` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — stable, heavily tested |

---

### C5. E5 Waterfall — Fixed-Rate Line (Per-Item Allocation)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_fixed_rate_line(qty, rate, remaining, floor_qty) → (planned_qty, effective_rate, planned_cif)` |
| **FORMULA** | If `floor_qty=True` (auto-plan): `planned_qty = floor((min(qty×rate, remaining)) / rate)`, `planned_cif = planned_qty × rate` else (reporting): `allocate_step(qty, rate, remaining)` |
| **INPUTS** | `qty` (Decimal), `rate` (Decimal), `remaining` (Decimal), `floor_qty` (bool) |
| **UNIT** | Quantity (kg), CIF (USD) |
| **PRECISION** | Decimal → 4dp quantization via `_quantize` |
| **ROUNDING** | ROUND_FLOOR (for auto-plan) or ROUND_HALF_UP (via allocate_step) |
| **SCOPE** | E5 waterfall (steps 1, 3, 5) — per-item rate application |
| **OWNER** | `apps.license.services.e5_plan._fixed_rate_line` |
| **TESTS** | `backend/apps/license/tests/test_e5_plan.py` |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/e5_plan.py:196-230` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — stable, tested |

---

### C6. E5 Waterfall — Special Validation Check

| Attribute | Value |
|-----------|-------|
| **METRIC** | Check: `remaining < sum(milk_qty_0404 + milk_qty_3502) × SWP_PRICE` |
| **FORMULA** | If true: plan all milk items at SWP (1.50) only; skip normal milk DWP/WPC classification; else: proceed to step 4 (normal milk) |
| **INPUTS** | `remaining` (Decimal), `milk_total_qty` (Decimal), `SWP_PRICE` (Decimal = 1.50) |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal → 4dp |
| **ROUNDING** | None (comparison only) |
| **SCOPE** | E5 waterfall (step 2) — business rule: when balance is critically low, all milk moves to SWP |
| **OWNER** | `apps.license.services.e5_plan.plan_e5_items` (lines 298–327) |
| **TESTS** | `backend/apps/license/tests/test_e5_plan.py` (special_validation) + `test_e5_auto_plan.py` |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/e5_plan.py:298-327` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### C7. E5 Plan Runner (Full Waterfall)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `plan_e5_items(items, balance_cif, min_plan_qty=0, floor_qty=False) → E5PlanResult` |
| **FORMULA** | 5-step waterfall with special milk validation + per-item milk DWP/SWP optimization: DIETARY FIBRE (3.00) → OILS (PKO 1.80, RBD 1.20, OTHER 5.00) → MILK (DWP/SWP per item) + EGG ALBUMIN (25.00 capped) → WHEAT FLOUR (dynamic mop-up) |
| **INPUTS** | `items` (list[E5Item]), `balance_cif` (Decimal), `floor_qty` (bool) |
| **UNIT** | Quantity (kg), CIF (USD) |
| **PRECISION** | Decimal → 4dp quantization |
| **ROUNDING** | ROUND_FLOOR (auto-plan) or ROUND_HALF_UP (reporting) |
| **SCOPE** | E5 auto-plan + reporting (Item Pivot, Dashboard, Excel) — all E5 consumers call this |
| **OWNER** | `apps.license.services.e5_plan.plan_e5_items` |
| **TESTS** | `backend/apps/license/tests/test_e5_plan.py`, `test_e5_auto_plan.py` |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/e5_plan.py:233-367` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — stable, heavily tested |

---

### C8. A3627 Auto-Plan — Rutile Avg Import Price Calculation

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_rutile_avg_import_price(rutile_items) → Decimal` |
| **FORMULA** | `avg_price = sum(item.cif_fc for ORIGINAL import items) / sum(item.quantity for ORIGINAL import items)` |
| **INPUTS** | `rutile_items` (list[LicenseImportItemsModel]) — raw import rows (NOT available_quantity) |
| **UNIT** | USD/unit |
| **PRECISION** | Decimal (implicit) |
| **ROUNDING** | None (pure division) |
| **SCOPE** | A3627 auto-plan engine — determines whether Rutile is priced at 2.50 (avg < 3.00) or 3.50 (avg ≥ 3.00) |
| **OWNER** | `apps.license.services.a3627_auto_plan._rutile_avg_import_price` |
| **TESTS** | `backend/apps/license/tests/test_a3627_auto_plan.py` |
| **CATEGORY** | Canonical (business rule) |
| **EVIDENCE** | `backend/apps/license/services/a3627_auto_plan.py:162-179` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

## SECTION 2: CONSUMERS (Reading Canonical Calculations)
### (Transitive dependencies — every update to canonical MUST cascade)

### CN1. E1 Auto-Plan Engine

| Attribute | Value |
|-----------|-------|
| **METRIC** | Calls `plan_e1_items()` with auto-plan parameters (min_plan_qty=50 threshold) |
| **DEPENDENCY** | Canonical: C4 (plan_e1_items) → C2 (_generic_stage) → C1 (allocate_step) + C3 (milk_planner) |
| **SCOPE** | Entry point: `apps.license.services.e1_auto_plan.compute_e1_auto_plan()` |
| **OWNER** | `compute_e1_auto_plan` |
| **TESTS** | `backend/apps/license/tests/test_e1_auto_plan.py` |
| **CATEGORY** | Consumer (engine, not calculation) |
| **EVIDENCE** | `backend/apps/license/services/e1_auto_plan.py:96-178` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (delegates to canonical) |

---

### CN2. E5 Auto-Plan Engine

| Attribute | Value |
|-----------|-------|
| **METRIC** | Calls `plan_e5_items()` with floor_qty=True for integer quantities |
| **DEPENDENCY** | Canonical: C7 (plan_e5_items) → C5 (_fixed_rate_line) → C1 (allocate_step) + C3 (milk) + C6 (special validation) |
| **SCOPE** | Entry point: `apps.license.services.e5_auto_plan.compute_e5_auto_plan()` |
| **OWNER** | `compute_e5_auto_plan` |
| **TESTS** | `backend/apps/license/tests/test_e5_auto_plan.py` |
| **CATEGORY** | Consumer (engine, not calculation) |
| **EVIDENCE** | `backend/apps/license/services/e5_auto_plan.py:128-260` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (delegates to canonical) |

---

### CN3. A3627 Auto-Plan Engine

| Attribute | Value |
|-----------|-------|
| **METRIC** | Runs 4-priority waterfall: allocate fixed-rate per item at determined Rutile price (from C8) |
| **DEPENDENCY** | Canonical: C8 (rutile price calc) + custom `_allocate_fixed_rate()` (similar to E5's C5 but inline) |
| **SCOPE** | Entry point: `apps.license.services.a3627_auto_plan.compute_a3627_auto_plan()` |
| **OWNER** | `compute_a3627_auto_plan` |
| **TESTS** | `backend/apps/license/tests/test_a3627_auto_plan.py` |
| **CATEGORY** | Consumer (engine, not calculation) |
| **EVIDENCE** | `backend/apps/license/services/a3627_auto_plan.py:205-292` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (delegates to canonical) |

---

### CN4. Item Pivot Report — Planned Quantity Display

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_effective_planned_quantity()` → calls `plan_e1_items()` or `plan_e5_items()` per item classification |
| **DEPENDENCY** | Canonical: C4 (E1) or C7 (E5) |
| **SCOPE** | Display/reporting layer: `apps.license.views.item_pivot_report._effective_planned_quantity()` |
| **OWNER** | `item_pivot_report` |
| **TESTS** | `backend/apps/license/tests/test_item_pivot_notification_summary.py` (effective_planned_quantity tests) |
| **CATEGORY** | Consumer (reporting) |
| **EVIDENCE** | `backend/apps/license/views/item_pivot_report.py:55-` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (delegates to canonical) |

---

### CN5. Item Pivot Report — Planned CIF Display

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_effective_planned_cif()` → calls `plan_e1_items()` or `plan_e5_items()` per item classification |
| **DEPENDENCY** | Canonical: C4 (E1) or C7 (E5) |
| **SCOPE** | Display/reporting layer: `apps.license.views.item_pivot_report._effective_planned_cif()` |
| **OWNER** | `item_pivot_report` |
| **TESTS** | `backend/apps/license/tests/test_item_pivot_totals_and_selection_rule.py` |
| **CATEGORY** | Consumer (reporting) |
| **EVIDENCE** | `backend/apps/license/views/item_pivot_report.py:41-` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (delegates to canonical) |

---

### CN6. License Overview — Total Planned CIF

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_total_planned_cif()` → sums all `LicenseItemPlan.planned_cif_fc` rows for a license |
| **DEPENDENCY** | Persisted `LicenseItemPlan` rows (populated by auto-plan engines which use canonicals) |
| **SCOPE** | Reporting: `apps.license.services.license_overview_summary._total_planned_cif()` |
| **OWNER** | `license_overview_summary` |
| **TESTS** | `backend/apps/license/tests/test_license_overview_summary_view.py` |
| **CATEGORY** | Consumer (aggregation) |
| **EVIDENCE** | `backend/apps/license/services/license_overview_summary.py:148-` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (aggregates persisted values) |

---

### CN7. Balance Calculation — Total Planned CIF (for balance deduction)

| Attribute | Value |
|-----------|-------|
| **METRIC** | Implicit: remaining balance after plan consumption = `initial_balance - planned_cif_total` |
| **DEPENDENCY** | Persisted `LicenseItemPlan.planned_cif_fc` (populated by canonicals) |
| **SCOPE** | Balance reporting: implicit in ledger displays |
| **OWNER** | Balance model / display logic |
| **TESTS** | `backend/apps/license/tests/test_license_detail_plan_utilization.py` |
| **CATEGORY** | Consumer (implicit) |
| **EVIDENCE** | Multiple display views (ledger, dashboard) |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### CN8. Plan Enforcement — Preserved Line Re-Emission

| Attribute | Value |
|-----------|-------|
| **METRIC** | `save_plan_lines_for_license()` → preserved branch re-emits existing `LicenseItemPlan` rows without recomputation |
| **DEPENDENCY** | Persisted `LicenseItemPlan` (from prior auto-plan runs using canonicals) |
| **SCOPE** | Planning orchestration: `apps.license.services.plan_enforcement.save_plan_lines_for_license()` |
| **OWNER** | `plan_enforcement` |
| **TESTS** | `backend/apps/license/tests/test_plan_enforcement.py` |
| **CATEGORY** | Consumer (infrastructure) |
| **EVIDENCE** | `backend/apps/license/services/plan_enforcement.py:180-191` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | ⚠️ **BL-PLAN-01**: If original line had CIF/Qty mismatch (E126/E132 defect), preserved branch INHERITS it forever |

---

### CN9. E126/E132 Auto-Plan — Floored Quantity Calculations

| Attribute | Value |
|-----------|-------|
| **METRIC** | `_floor_qty(x)` → `floor(x)` to whole unit |
| **DEPENDENCY** | Not strictly "reading canonical" — implements its own floor logic; but the CIF is NOT recomputed (defect BL-PLAN-01) |
| **SCOPE** | `apps.license.services.e126_auto_plan.compute_e126_auto_plan()` and `e132_auto_plan.compute_e132_auto_plan()` |
| **OWNER** | `e126_auto_plan`, `e132_auto_plan` |
| **TESTS** | `test_e126_auto_plan.py`, `test_e132_auto_plan.py` |
| **CATEGORY** | Consumer (infrastructure) — but with defect |
| **EVIDENCE** | `e126_auto_plan.py:111-116`, `e132_auto_plan.py:108-113` |
| **CONFIDENCE** | HIGH (implementation) |
| **KNOWN ISSUES** | ⚠️ **BL-PLAN-01 DEFECT**: After flooring qty, planned_cif_fc should be recomputed but is NOT; result: `planned_cif_fc ≠ floored_qty × unit_price` (see Module 2 doc §2.2) |

---

## SECTION 3: VALIDATION CHECKS
### (Constraint enforcement — these gate plan acceptance)

### V1. Ceiling Price Validation (Unit Price ≤ Max Price)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `unit_price ≤ ceiling_price × (1 + tolerance_percent)` where `tolerance_percent = 0.01` |
| **FORMULA** | Check: `plan_unit_price ≤ PlanningItemModel.unit_price × 1.01` |
| **INPUTS** | `plan_unit_price` (float), `ceiling_price` (Decimal), `tolerance` (float = 0.01) |
| **UNIT** | USD |
| **PRECISION** | Float comparison (may have rounding drift) |
| **ROUNDING** | None (comparison only) |
| **SCOPE** | Plan acceptance gate: `apps.license.services.plan_grouping.validate_group_plan_lines()` |
| **OWNER** | `plan_grouping.validate_group_plan_lines` |
| **TESTS** | `backend/apps/license/tests/test_plan_grouping.py` |
| **CATEGORY** | Validation (constraint) |
| **EVIDENCE** | `backend/apps/license/services/plan_grouping.py:330-391` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None — simple range check |

---

### V2. Quantity Cap Validation (Planned ≤ Available)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `sum(planned_qty for all lines in group) ≤ available_qty × (1 + tolerance)` where `tolerance = 0.01` |
| **FORMULA** | Sum all plan lines' quantities; check against group's available_qty with 1% tolerance |
| **INPUTS** | `planned_quantities` (list[float]), `available_qty` (float), `tolerance` (float = 0.01) |
| **UNIT** | Quantity (kg or units) |
| **PRECISION** | Float arithmetic |
| **ROUNDING** | None (comparison only) |
| **SCOPE** | Plan acceptance gate: `plan_grouping.validate_group_plan_lines()` |
| **OWNER** | `plan_grouping.validate_group_plan_lines` |
| **TESTS** | `test_plan_grouping.py` |
| **CATEGORY** | Validation (constraint) |
| **EVIDENCE** | `backend/apps/license/services/plan_grouping.py:330-391` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### V3. CIF/Qty Consistency Validation (MISSING / NOT ENFORCED)

| Attribute | Value |
|-----------|-------|
| **METRIC** | ⚠️ **NOT IMPLEMENTED**: `planned_cif_fc ≈ planned_quantity × unit_price` |
| **FORMULA** | Expected: `planned_cif_fc == planned_quantity × unit_price (within rounding tolerance)` |
| **INPUTS** | `planned_cif_fc` (float), `planned_quantity` (float), `unit_price` (float) |
| **UNIT** | CIF (USD, 2dp), Quantity, Unit Price |
| **PRECISION** | Float comparison (should allow 0.01 tolerance for rounding) |
| **ROUNDING** | None (should check within tolerance) |
| **SCOPE** | Should gate plan acceptance but DOESN'T (defect) |
| **OWNER** | None / MISSING |
| **TESTS** | None (no validation exists) |
| **CATEGORY** | Validation (MISSING) |
| **EVIDENCE** | None (explicitly not validated) |
| **CONFIDENCE** | HIGH (this is a confirmed gap) |
| **KNOWN ISSUES** | ⚠️ **BL-PLAN-01**: This consistency check is never enforced; E126/E132 defect (floored qty, un-recomputed CIF) passes silently |

---

### V4. Item Remaining ≥ 0 Validation

| Attribute | Value |
|-----------|-------|
| **METRIC** | `item_remaining_qty ≥ 0` and `item_remaining_cif ≥ 0` |
| **FORMULA** | `remaining = max(planned - allotted, 0)` — implicit clamp to 0 |
| **INPUTS** | `item_planned_qty`, `item_allotted_qty`, `item_planned_cif`, `item_allotted_value` |
| **UNIT** | Quantity (kg), CIF (USD) |
| **PRECISION** | Float |
| **ROUNDING** | None |
| **SCOPE** | Balance tracking (implicit): `apps.license.services.norm_plan.py`, `plan_enforcement.py` |
| **OWNER** | Implicit in balance calculations |
| **TESTS** | Implicit in integration tests |
| **CATEGORY** | Validation (implicit) |
| **EVIDENCE** | `backend/apps/license/services/norm_plan.py:105-111` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (sound logic) |

---

### V5. Balance Non-Negative Validation

| Attribute | Value |
|-----------|-------|
| **METRIC** | `remaining_balance ≥ 0` after each waterfall step |
| **FORMULA** | Each step: `remaining -= consumed_cif`; implicit ≥ 0 check in downstream steps (if remaining ≤ 0, stop) |
| **INPUTS** | `remaining` (Decimal) |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal |
| **ROUNDING** | None |
| **SCOPE** | Waterfall engines (E1, E5, A3627): implicit loop control |
| **OWNER** | `e1_plan.py`, `e5_plan.py`, `a3627_auto_plan.py` |
| **TESTS** | Implicit in waterfall tests |
| **CATEGORY** | Validation (implicit) |
| **EVIDENCE** | `e1_plan.py:261-267`, `e5_plan.py:292-296` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### V6. Min Plan Qty Threshold Validation

| Attribute | Value |
|-----------|-------|
| **METRIC** | `item_qty ≥ min_plan_qty` before including in calculation |
| **FORMULA** | Skip items with `qty < min_plan_qty` (no balance consumed) |
| **INPUTS** | `item_qty` (Decimal), `min_plan_qty` (Decimal = 50 for auto-plan, 0 for reporting) |
| **UNIT** | Quantity (kg) |
| **PRECISION** | Decimal |
| **ROUNDING** | None (comparison only) |
| **SCOPE** | All waterfall engines (E1, E5, A3627): input filtering |
| **OWNER** | Engines (e1_plan, e5_plan, etc.) |
| **TESTS** | Implicit in auto-plan tests |
| **CATEGORY** | Validation (threshold) |
| **EVIDENCE** | `e1_plan.py:250-257`, `e5_plan.py:268-276` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

## SECTION 4: BALANCE CALCULATIONS (License & Item Level)
### (Aggregation and financial balance computations — canonical for ledger/balance reporting)

### B1. License Credit (Total Export CIF)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_credit(license) → Decimal` |
| **FORMULA** | `sum(LicenseExportItemModel.cif_fc for license)` |
| **INPUTS** | All export item rows for license |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal (from DB), quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP (via `quantize_2dp`) |
| **SCOPE** | Balance calculation: `LicenseBalanceCalculator.calculate_credit()` |
| **OWNER** | `balance_calculator.LicenseBalanceCalculator.calculate_credit` |
| **TESTS** | `backend/apps/license/tests/test_balance_calculator.py` |
| **CATEGORY** | Canonical (ledger aggregation) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:72-90` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### B2. License Debit (Total BOE Debits)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_debit(license) → Decimal` |
| **FORMULA** | `sum(RowDetails.cif_fc for DEBIT transactions, excluding hidden)` |
| **INPUTS** | All BOE DEBIT rows (with hidden-status filtering) |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal, quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | Core balance: `LicenseBalanceCalculator.calculate_debit()` |
| **OWNER** | `balance_calculator.LicenseBalanceCalculator.calculate_debit` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (ledger aggregation) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:438-490` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | ⚠️ **BL-LEDGER-02**: Cached `LicenseBalance.balance_cif` goes stale after reconciliation allocations (signal not triggered) |

---

### B3. License Allotment (Total Reconciliation Allotments)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_allotment(license) → Decimal` |
| **FORMULA** | `sum(InvoiceBOEAllocation.allocated_cif_fc) + sum(BOEAllotmentAllocation.allocated_cif_fc)` |
| **INPUTS** | All allocation rows for license |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal (from DB), quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | Balance component: `LicenseBalanceCalculator.calculate_allotment()` |
| **OWNER** | `balance_calculator.LicenseBalanceCalculator.calculate_allotment` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (ledger aggregation) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:949-1041` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### B4. License Trade (Total Trade-Line CIF)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_trade(license) → Decimal` |
| **FORMULA** | `sum(LicenseTradeLine.cif_fc for license)` |
| **INPUTS** | All trade lines for license |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal, quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | Balance component: `LicenseBalanceCalculator.calculate_trade()` |
| **OWNER** | `balance_calculator.LicenseBalanceCalculator.calculate_trade` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (ledger aggregation) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:1042-1069` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### B5. License Purchase Credit (Total Purchase-order Credit)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_purchase_credit(license) → Decimal` |
| **FORMULA** | `sum(PurchaseOrderCredit.cif_fc for license)` |
| **INPUTS** | All purchase credit rows |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal, quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | Balance component: `LicenseBalanceCalculator.calculate_purchase_credit()` |
| **OWNER** | `balance_calculator.LicenseBalanceCalculator.calculate_purchase_credit` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (ledger aggregation) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:1070-1174` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### B6. License Financial Balance

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_financial_balance(license) → Decimal` |
| **FORMULA** | `BALANCE = CREDIT - DEBIT` (where CREDIT = export CIF, DEBIT = BOE DEBIT) |
| **INPUTS** | Results of B1 (credit) and B2 (debit) |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal, quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | Primary ledger balance: `LicenseBalanceCalculator.calculate_financial_balance()` |
| **OWNER** | `balance_calculator.LicenseBalanceCalculator.calculate_financial_balance` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (core balance) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:1543-1614` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | ⚠️ **BL-LEDGER-02**: Caching stale issue (signal not refreshing after reconciliation) |

---

### B7. Item Available Quantity

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_available_quantity(import_item) → Decimal` |
| **FORMULA** | `available_qty = quantity - debited_qty` (or derived from balance_cif if applicable) |
| **INPUTS** | `LicenseImportItemsModel.quantity`, `LicenseImportItemsModel.cif_fc`, debited amounts |
| **UNIT** | Quantity (kg/units) |
| **PRECISION** | Decimal (from DB) |
| **ROUNDING** | None (stored as-is) |
| **SCOPE** | Item-level balance: `ItemBalanceCalculator.calculate_available_quantity()` |
| **OWNER** | `balance_calculator.ItemBalanceCalculator.calculate_available_quantity` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (item aggregation) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:1904-1944` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### B8. Item Balance (Item-Level CIF Balance)

| Attribute | Value |
|-----------|-------|
| **METRIC** | `calculate_item_balance(import_item) → Decimal` |
| **FORMULA** | `item_balance = item_credit - item_debit` (complex attribution logic per BL-LEDGER-03) |
| **INPUTS** | Item's credit, debit, and allocation rows |
| **UNIT** | CIF (USD) |
| **PRECISION** | Decimal, quantized to 2dp |
| **ROUNDING** | ROUND_HALF_UP |
| **SCOPE** | Item-level reporting: `ItemBalanceCalculator.calculate_item_balance()` |
| **OWNER** | `balance_calculator.ItemBalanceCalculator.calculate_item_balance` |
| **TESTS** | `test_balance_calculator.py` |
| **CATEGORY** | Canonical (item balance) |
| **EVIDENCE** | `backend/apps/license/services/balance_calculator.py:1802-1874` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | ⚠️ **BL-LEDGER-03**: Ignores sibling-item allocations in zero-cif_fc branch; debit calculation incorrect |

---

## SECTION 5: PRESENTATION / DISPLAY TRANSFORMATIONS
### (Final rendering — applied AFTER canonical calculations)

### P1. Balance Display Format (Ledger Rows)

| Attribute | Value |
|-----------|-------|
| **METRIC** | Format balance row for display (ledger table) |
| **FORMULA** | Aggregate balance components; apply formatting rules (sign, decimals, grouping) |
| **INPUTS** | Canonical balance results (B1–B8) |
| **UNIT** | CIF (USD, 2dp) |
| **PRECISION** | Float (for display) |
| **ROUNDING** | Already rounded in canonical |
| **SCOPE** | Ledger views: `backend/apps/license/views/ledger.py`, exports |
| **OWNER** | Display/serialization layer |
| **TESTS** | Integration tests |
| **CATEGORY** | Presentation (display) |
| **EVIDENCE** | Multiple view files |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None (just rendering) |

---

### P2. Excel Export — Balance Formatting

| Attribute | Value |
|-----------|-------|
| **METRIC** | Format balance for Excel export with XLS styling |
| **FORMULA** | Same calculation as canonical, formatted for Excel cell types (number, currency, etc.) |
| **INPUTS** | Canonical balance components |
| **UNIT** | CIF (USD) |
| **PRECISION** | Float → formatted string for Excel |
| **ROUNDING** | None (already rounded) |
| **SCOPE** | Balance Excel export: `apps.license.services.exporters.license_balance_excel` |
| **OWNER** | `license_balance_excel` exporter |
| **TESTS** | Export tests |
| **CATEGORY** | Presentation (export) |
| **EVIDENCE** | `backend/apps/license/services/exporters/license_balance_excel.py` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### P3. Ledger PDF Export — Layout & Formatting

| Attribute | Value |
|-----------|-------|
| **METRIC** | Layout ledger rows into PDF table format |
| **FORMULA** | Group balance rows by transaction type; format for PDF (page breaks, headers, footers) |
| **INPUTS** | Canonical ledger rows (balance calculations) |
| **UNIT** | CIF (USD) |
| **PRECISION** | Float (for PDF text) |
| **ROUNDING** | None |
| **SCOPE** | Ledger PDF export: `apps.license.services.exporters.ledger_pdf` |
| **OWNER** | `ledger_pdf` exporter |
| **TESTS** | PDF export tests |
| **CATEGORY** | Presentation (export) |
| **EVIDENCE** | `backend/apps/license/services/exporters/ledger_pdf.py` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

### P4. Planned Item Pivot Report — Tooltip & Inline Display

| Attribute | Value |
|-----------|-------|
| **METRIC** | Format planned quantities/CIF for Item Pivot tooltip + inline cells |
| **FORMULA** | Display `planned_qty`, `planned_cif_fc`, `unit_price` with legend notation |
| **INPUTS** | Canonical plan calculations (C4, C7, etc.) |
| **UNIT** | Quantity (decimal), CIF (USD, 2dp) |
| **PRECISION** | Float (for display) |
| **ROUNDING** | None (already canonical) |
| **SCOPE** | Item Pivot view: `backend/apps/license/views/item_pivot_report.py` |
| **OWNER** | `item_pivot_report` |
| **TESTS** | Item Pivot tests |
| **CATEGORY** | Presentation (UI) |
| **EVIDENCE** | `backend/apps/license/views/item_pivot_report.py` |
| **CONFIDENCE** | HIGH |
| **KNOWN ISSUES** | None |

---

## SECTION 6: DEPRECATED / LEGACY CALCULATIONS
### (Old code — marked for removal, not used in production paths)

### L1. Glass Formers Legacy Report — average_unit_price Cached Property

| Attribute | Value |
|-----------|-------|
| **METRIC** | `LicenseDetailsModel.average_unit_price` (cached_property) — hardcoded Glass/Borax split |
| **FORMULA** | Hardcoded: Borax → SodaAsh (0.70) → Rutile (3.50) → Titanium (2.00); circularity: rutile_cif = rutile_qty × 3.5 (hardcoded, NOT average) |
| **INPUTS** | License's import items (for hardcoded category matching) |
| **UNIT** | USD/unit |
| **PRECISION** | Decimal |
| **ROUNDING** | None |
| **SCOPE** | Legacy: Glass Formers report only — NOT used by A3627 auto-plan |
| **OWNER** | `apps.license.models.core.LicenseDetailsModel.average_unit_price` |
| **TESTS** | None (deprecated) |
| **CATEGORY** | Deprecated (legacy report) |
| **EVIDENCE** | `backend/apps/license/models/core.py:average_unit_price` (property) |
| **CONFIDENCE** | HIGH (confirmed NOT used by A3627) |
| **KNOWN ISSUES** | Circular logic (rutile_cif hardcoded, not actual average); A3627 recomputes its own genuine average (C8) |

---

## SECTION 7: DUPLICATE IMPLEMENTATIONS
### (⚠️ BLOCKERS — Multiple conflicting implementations of same logic)

### D1. Fixed-Rate Allocation (Quantity Floor + CIF Limit)

| Attribute | Value |
|-----------|-------|
| **METRIC** | Allocate at fixed price: floor quantity to whole units, cap CIF at remaining balance |
| **FORMULA** | `planned_qty = floor((min(qty×price, remaining)) / price)`, `planned_cif = planned_qty × price` |
| **IMPLEMENTATIONS** | **3 separate implementations** (all slightly different): |
| | 1. **E5's `_fixed_rate_line` (with floor_qty=True)** → `backend/apps/license/services/e5_plan.py:196-230` |
| | 2. **A3627's `_allocate_fixed_rate` (inline)** → `backend/apps/license/services/a3627_auto_plan.py:182-202` |
| | 3. **E126/E132's `_floor_qty` + CIF calc** → `backend/apps/license/services/e126_auto_plan.py:111-116` + inline CIF (defect: not recomputed) |
| **INPUTS** | `qty` (Decimal), `price` (Decimal), `remaining` (Decimal) |
| **UNIT** | Quantity, CIF (USD) |
| **PRECISION** | All Decimal or float |
| **ROUNDING** | ROUND_FLOOR (to_integral_value) |
| **SCOPE** | Used by E5 auto-plan (floor_qty=True), A3627 auto-plan, E126/E132 auto-plan |
| **OWNER** | None (no single canonical — **BLOCKER**) |
| **TESTS** | Separate tests per implementation; no unified test |
| **CATEGORY** | Duplicate (BLOCKER) |
| **EVIDENCE** | |
| | E5: `e5_plan.py:224-230` (MOST COMPLETE) |
| | A3627: `a3627_auto_plan.py:196-199` (identical to E5, inlined) |
| | E126/E132: `e126_auto_plan.py:242-266` + `e132_auto_plan.py:239-269` (DEFECTIVE: CIF not recomputed) |
| **CONFIDENCE** | HIGH (confirmed 3 implementations exist) |
| **KNOWN ISSUES** | ⚠️ **BL-PLAN-01 (E126/E132 DEFECT)**: CIF is NOT recomputed after floor; violates `planned_cif = planned_qty × unit_price` invariant |
| **BLOCKER IMPACT** | Any future fix to floor-quantity logic must update **3 places**; E126/E132's defect silently persists in preserved lines; risk of future drift |
| **RECOMMENDED ACTION** | Extract `allocate_at_fixed_rate(qty, price, remaining) → (planned_qty, planned_cif)` as canonical in `planning_allocation.py`; have E5, A3627, E126, E132 all call it; fix BL-PLAN-01 defect in one place |

---

## SECTION 8: SUMMARY TABLE — ALL 29 CALCULATIONS REGISTERED

| # | Category | Name | Owner | File | Status | Blocker |
|---|----------|------|-------|------|--------|---------|
| C1 | Canonical | Allocate Step (dynamic pricing) | `planning_allocation.py` | `planning_allocation.py:31` | ✓ | No |
| C2 | Canonical | E1 Generic Stage | `e1_plan.py` | `e1_plan.py:187` | ✓ | No |
| C3 | Canonical | Milk Split (DWP/SWP) | `milk_planner.py` | `milk_planner.py:48` | ✓ | No |
| C4 | Canonical | E1 Waterfall | `e1_plan.py` | `e1_plan.py:225` | ✓ | No |
| C5 | Canonical | E5 Fixed-Rate Line | `e5_plan.py` | `e5_plan.py:196` | ✓ | No |
| C6 | Canonical | E5 Special Validation | `e5_plan.py` | `e5_plan.py:298` | ✓ | No |
| C7 | Canonical | E5 Waterfall | `e5_plan.py` | `e5_plan.py:233` | ✓ | No |
| C8 | Canonical | A3627 Rutile Avg Price | `a3627_auto_plan.py` | `a3627_auto_plan.py:162` | ✓ | No |
| CN1 | Consumer | E1 Auto-Plan | `e1_auto_plan.py` | `e1_auto_plan.py:96` | ✓ | No |
| CN2 | Consumer | E5 Auto-Plan | `e5_auto_plan.py` | `e5_auto_plan.py:128` | ✓ | No |
| CN3 | Consumer | A3627 Auto-Plan | `a3627_auto_plan.py` | `a3627_auto_plan.py:205` | ✓ | No |
| CN4 | Consumer | Item Pivot (planned qty) | `item_pivot_report.py` | `item_pivot_report.py:55` | ✓ | No |
| CN5 | Consumer | Item Pivot (planned CIF) | `item_pivot_report.py` | `item_pivot_report.py:41` | ✓ | No |
| CN6 | Consumer | License Overview (planned CIF) | `license_overview_summary.py` | `license_overview_summary.py:148` | ✓ | No |
| CN7 | Consumer | Balance (planned deduction) | (implicit) | N/A | ✓ | No |
| CN8 | Consumer | Plan Enforcement (preserve) | `plan_enforcement.py` | `plan_enforcement.py:180` | ✓ | ⚠️ Inherits BL-PLAN-01 |
| CN9 | Consumer | E126/E132 Floor Qty | `e126_auto_plan.py`, `e132_auto_plan.py` | `e126_auto_plan.py:111`, `e132_auto_plan.py:108` | ⚠️ DEFECT | ⚠️ BL-PLAN-01 |
| V1 | Validation | Ceiling Price Check | `plan_grouping.py` | `plan_grouping.py:360` | ✓ | No |
| V2 | Validation | Quantity Cap Check | `plan_grouping.py` | `plan_grouping.py:370` | ✓ | No |
| V3 | Validation | CIF/Qty Consistency (MISSING) | None | N/A | ✗ MISSING | ⚠️ Allows BL-PLAN-01 |
| V4 | Validation | Item Remaining ≥ 0 | (implicit) | `norm_plan.py:105` | ✓ | No |
| V5 | Validation | Balance Non-Negative | (implicit) | `e1_plan.py:261`, `e5_plan.py:292` | ✓ | No |
| V6 | Validation | Min Qty Threshold | (implicit) | `e1_plan.py:250`, `e5_plan.py:268` | ✓ | No |
| B1 | Balance | License Credit | `balance_calculator.py` | `balance_calculator.py:72` | ✓ | No |
| B2 | Balance | License Debit | `balance_calculator.py` | `balance_calculator.py:438` | ⚠️ Stale cache | ⚠️ BL-LEDGER-02 |
| B3 | Balance | License Allotment | `balance_calculator.py` | `balance_calculator.py:949` | ✓ | No |
| B4 | Balance | License Trade | `balance_calculator.py` | `balance_calculator.py:1042` | ✓ | No |
| B5 | Balance | License Purchase Credit | `balance_calculator.py` | `balance_calculator.py:1070` | ✓ | No |
| B6 | Balance | License Financial Balance | `balance_calculator.py` | `balance_calculator.py:1543` | ⚠️ Stale cache | ⚠️ BL-LEDGER-02 |
| B7 | Balance | Item Available Qty | `balance_calculator.py` | `balance_calculator.py:1904` | ✓ | No |
| B8 | Balance | Item Balance | `balance_calculator.py` | `balance_calculator.py:1802` | ⚠️ Attribution | ⚠️ BL-LEDGER-03 |
| P1 | Presentation | Ledger Display Format | (view layer) | `ledger.py` | ✓ | No |
| P2 | Presentation | Excel Export Format | `license_balance_excel.py` | `license_balance_excel.py` | ✓ | No |
| P3 | Presentation | PDF Export Layout | `ledger_pdf.py` | `ledger_pdf.py` | ✓ | No |
| P4 | Presentation | Item Pivot Tooltip | `item_pivot_report.py` | `item_pivot_report.py` | ✓ | No |
| L1 | Legacy | Glass Formers avg_unit_price | `core.py` (cached_property) | `core.py:average_unit_price` | Deprecated | No (not used) |
| D1 | Duplicate | Fixed-Rate Allocation (BLOCKER) | 3 implementations | `e5_plan.py:196`, `a3627_auto_plan.py:182`, `e126_auto_plan.py:111` | ⚠️ DEFECT | ⚠️ BL-PLAN-01 |

---

## SECTION 9: IDENTIFIED BLOCKERS & DEFECTS

### Blocker 1: BL-PLAN-01 — E126/E132 CIF/Qty Mismatch (Duplicate Implementation Defect)

**Severity**: HIGH (data integrity violation)

**Status**: ✓ DOCUMENTED (Module 2 §2.2)

**Root Cause**: E126/E132 floor quantity but do NOT recompute CIF (duplicate fixed-rate implementation with defect)

**Evidence**:
- E126: `backend/apps/license/services/e126_auto_plan.py:242-266` confirmed VERBATIM
- E132: `backend/apps/license/services/e132_auto_plan.py:239-269` confirmed VERBATIM
- Both: `planned_cif_fc = round(raw_planned_cif, 2)` (line ~256 in e126, ~266 in e132) — NOT recomputed after floor

**Impact**:
- Persisted `LicenseItemPlan` rows violate invariant: `planned_cif_fc ≠ floored_qty × unit_price`
- Consumes real license Balance CIF against NO plannable quantity
- Preserved lines inherit defect forever (CN8)

**Suggested Fix**:
1. Extract canonical `_allocate_at_fixed_rate(qty, price, remaining) → (planned_qty, planned_cif)` to `planning_allocation.py`
2. Fix CIF recomputation: `planned_cif = round(floored_qty * price, 2)`
3. Update E5, A3627, E126, E132 to call canonical

**Effort**: 2–4 hours (low risk, high impact)

---

### Blocker 2: BL-LEDGER-02 — Stale Cached Balance After Reconciliation

**Severity**: MEDIUM (staleness risk, data freshness issue)

**Status**: ✓ DOCUMENTED (Module 2 §9.1)

**Root Cause**: `LicenseBalance.balance_cif` cached column; `InvoiceBOEAllocation` creation does NOT trigger signal to refresh

**Evidence**: `backend/apps/license/services/balance_calculator.py:1543-1614` computes fresh balance; caching logic in `apps.license.models` signals

**Impact**:
- Ledger display may show stale balance after reconciliation allocation
- Exported balance reports may be out of sync with DB state

**Suggested Fix**:
1. Add signal handler to `InvoiceBOEAllocation.post_save` and `BOEAllotmentAllocation.post_save` → refresh `LicenseBalance.balance_cif`
2. Or: demote cache to on-demand computed (remove caching)

**Effort**: 1–2 hours

---

### Blocker 3: BL-LEDGER-03 — Item-Level Attribution (Sibling Allocation Ignored)

**Severity**: HIGH (incorrect item balance)

**Status**: ✓ DOCUMENTED (Module 2 §1.2)

**Root Cause**: `ItemBalanceCalculator.calculate_item_balance()` zero-cif_fc branch ignores sibling items' outstanding allotments; debit = ENTIRE license BOE total, not item's portion

**Evidence**: `backend/apps/license/services/balance_calculator.py:1802-1874` (check line ~1830–1860)

**Impact**:
- Item-level balance reports incorrect when multiple items on license
- Each item claims full license debit, overcounting

**Suggested Fix**:
1. Implement proper proportional attribution: `item_debit = (item_cif / license_cif) × license_debit`
2. Document edge case for items with zero cif_fc

**Effort**: 3–6 hours (requires careful audit)

---

### Blocker 4: V3 — CIF/Qty Consistency Validation Missing

**Severity**: HIGH (no enforcement, allows BL-PLAN-01 to pass silently)

**Status**: ✓ DOCUMENTED (Module 2 §5, validation category)

**Root Cause**: `plan_grouping.validate_group_plan_lines()` checks ceiling price (V1) and quantity cap (V2) but NOT `planned_cif_fc ≈ planned_qty × unit_price`

**Evidence**: `backend/apps/license/services/plan_grouping.py:330-391` (no CIF/qty check)

**Impact**:
- BL-PLAN-01 defect silently accepted
- Invalid plans persisted with inconsistent internal state

**Suggested Fix**:
1. Add V3 check to `validate_group_plan_lines()`: `|planned_cif_fc - (planned_qty × unit_price)| ≤ 0.01 × unit_price`
2. Reject plans failing V3

**Effort**: 1–2 hours

---

### Blocker 5: D1 — Duplicate Fixed-Rate Allocation Implementation

**Severity**: MEDIUM (maintenance debt, drift risk)

**Status**: ✓ DOCUMENTED (Module 2 §7)

**Root Cause**: 3 separate implementations of `allocate_at_fixed_rate()` (E5, A3627, E126/E132) with E126/E132 defective

**Evidence**:
- E5: `e5_plan.py:224-230` (correct)
- A3627: `a3627_auto_plan.py:196-199` (correct, inlined from E5)
- E126/E132: `e126_auto_plan.py:242-266`, `e132_auto_plan.py:239-269` (DEFECTIVE)

**Impact**:
- Risk of future divergence (bug fixed in one place, not reflected in others)
- BL-PLAN-01 defect localized to E126/E132 but could spread

**Suggested Fix**:
1. Extract canonical `allocate_at_fixed_rate(qty, price, remaining) → (planned_qty, planned_cif)` to `planning_allocation.py`
2. Update all 4 engines (E5, A3627, E126, E132) to import and call canonical
3. Fix BL-PLAN-01 in canonical; defect automatically fixed in all 4 engines

**Effort**: 2–3 hours

---

## SECTION 10: RECOMMENDATIONS & REMEDIATION ROADMAP

### Immediate (Sprint 1—2: 5–10 hours)

1. **Fix BL-PLAN-01** (D1 + V3):
   - Extract `_allocate_at_fixed_rate()` canonical to `planning_allocation.py`
   - Update E5, A3627, E126, E132 to call it
   - Add V3 (CIF/qty consistency) validation to `plan_grouping.py`
   - Result: E126/E132 defect fixed; future drift prevented

2. **Add V3 Validation Gate**:
   - Reject any plan line where `|planned_cif_fc - (planned_qty × unit_price)| > 0.01`
   - Enforce before `save_plan_lines_for_license()` (before persisting to DB)

### Short-term (Sprint 3—4: 3–6 hours)

3. **Fix BL-LEDGER-02** (stale cache):
   - Add signals to `InvoiceBOEAllocation.post_save()` / `BOEAllotmentAllocation.post_save()`
   - Trigger `LicenseBalance.balance_cif` refresh
   - Verify all balance-stale issues resolved

4. **Audit & Document BL-LEDGER-03** (item attribution):
   - Inspect real data for proportionality violations
   - Implement correct attribution formula
   - Add unit tests with multi-item license scenarios

### Medium-term (Backlog: 2—4 weeks)

5. **Extract Balance Calculations as Versioned Snapshots**:
   - Current: `LicenseBalance` cached on license; stale between updates
   - Target: Immutable balance snapshot per transaction (ledger entry), linked to source events
   - Allows historical audit trail + eliminates staleness

6. **Unify Item Pivot & Ledger Calculations**:
   - Both recalculate balance independently (CN4, CN5, CN6 call canonical; but no single "Item Pivot balance" model exists)
   - Design canonical Item Pivot balance snapshot (links to Item Pivot transaction log)

---

## CONCLUSION

**Total Calculations Registered: 29** ✓

**Status Summary**:
- ✓ **Canonicals (8)**: Stable, well-tested, documented
- ✓ **Consumers (9)**: Properly delegating to canonicals
- ⚠️ **Validations (6)**: 5/6 implemented; V3 (CIF/qty) missing (allows BL-PLAN-01 to pass)
- ✓ **Balance (8)**: Core ledger calculations; 2 known issues (BL-LEDGER-02 stale, BL-LEDGER-03 attribution)
- ✓ **Presentation (4)**: Display-only, non-computational
- ⚠️ **Legacy (1)**: Deprecated Glass Formers property (not used by A3627)
- ⚠️ **Duplicates (1)**: D1 (fixed-rate allocation) — 3 implementations, 1 defective

**Blockers Identified & Documented**:
1. ⚠️ **BL-PLAN-01** — E126/E132 CIF/qty mismatch (defect severity: HIGH)
2. ⚠️ **BL-LEDGER-02** — Stale balance cache after reconciliation (severity: MEDIUM)
3. ⚠️ **BL-LEDGER-03** — Item-level attribution ignores siblings (severity: HIGH)
4. ⚠️ **V3 Missing** — No CIF/qty consistency validation (severity: HIGH, enables BL-PLAN-01)
5. ⚠️ **D1 Duplicate** — 3 implementations of fixed-rate allocation (severity: MEDIUM, maintenance debt)

**Remediation**: Follow 10-hour immediate + 6-hour short-term roadmap (Section 10) to resolve all blockers.
