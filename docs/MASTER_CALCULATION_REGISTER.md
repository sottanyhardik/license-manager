# MASTER CALCULATION REGISTER
## Consolidated Planning & Balance Calculations

**Last Updated**: 2026-08-10  
**Scope**: All planning calculations, balance computations, and validation checks  
**Purpose**: Single source of truth for every calculation in the license-manager system

---

## Quick Reference: All Calculations

| ID | Calculation | Classification | Formula | Owner | Status |
|----|-------------|-----------------|---------|-------|--------|
| **PLAN-001** | Category CIF Allocation (E1/E5) | CANONICAL | `category_share = balance_cif × (weight/total)` | E1/E5 planning | ✓ HIGH |
| **PLAN-002** | Per-Item Unit Price from Category | CANONICAL | `per_item_price = category_cif / category_qty` | E1/E5 planning | ✓ HIGH |
| **PLAN-003** | Per-Item Planned CIF | CANONICAL | `planned_cif = planned_qty × unit_price` | E1/E5 planning | ✓ HIGH |
| **PLAN-004** | Item Remaining Qty (Planned − Allotted) | CONSUMER/DUPLICATE | `remaining = max(planned_qty − allotted_qty, 0)` | Multiple locations | ⚠️ DUPLICATE |
| **PLAN-005** | Item Remaining CIF (Planned − Allotted) | CONSUMER/DUPLICATE | `remaining = max(planned_cif − allotted_value, 0)` | Multiple locations | ⚠️ DUPLICATE |
| **PLAN-006** | Floor Quantity to Whole (E126/E132) | CANONICAL | `floored = floor(raw_qty)` | E126/E132 auto-plan | ✓ HIGH |
| **PLAN-007** | **[DEFECT]** CIF Not Recomputed After Floor | DUPLICATE/DEFECT | ~~`planned_cif = floored_qty × price`~~ (NOT DONE) | E126/E132 auto-plan | ❌ **BL-PLAN-01** |
| **PLAN-008** | Milk 40% CIF Allocation | CANONICAL | `milk_40_cif = balance_cif × 0.40` | E5/E132 milk planner | ✓ HIGH |
| **PLAN-009** | Milk 40% Qty Allocation | CANONICAL | `milk_40_qty = min(avail_qty, 40_cif / price_40)` | E5/E132 milk planner | ✓ HIGH |
| **PLAN-010** | Milk 60% CIF Allocation | CANONICAL | `milk_60_cif = balance_cif × 0.60` | E5/E132 milk planner | ✓ HIGH |
| **PLAN-011** | Milk 60% Qty Allocation | CANONICAL | `milk_60_qty = min(avail_qty − qty_40, 60_cif / price_60)` | E5/E132 milk planner | ✓ HIGH |
| **PLAN-012** | Round to 2 Decimals (_r2) | CANONICAL | `round(x, 2) → float` | Infrastructure | ✓ HIGH |
| **PLAN-013** | Validate Unit Price ≤ Ceiling | VALIDATION | `is_valid = unit_price ≤ ceiling × 1.01` | plan_grouping | ✓ HIGH |
| **PLAN-014** | Validate Total Qty ≤ Available Qty | VALIDATION | `is_valid = sum(qty) ≤ available × 1.01` | plan_grouping | ✓ HIGH |
| **PLAN-015** | Preserved Plan Passthrough | INFRASTRUCTURE | `output = input` (no change) | plan_enforcement | ⚠️ INHERITS BL-PLAN-01 |
| **PLAN-016** | License Available Qty (Sum) | CANONICAL | `avail = sum(import_item.available_qty)` | All planners | ✓ HIGH |
| **PLAN-017** | Item Available Qty (Persisted) | CANONICAL | `avail = LicenseImportItemsModel.available_qty` | Persisted in DB | ✓ HIGH |
| **PLAN-018** | A3627 Fixed-Rate Allocation | CANONICAL | `planned_qty=min(qty,remaining/price); cif=(qty×price).quantize()` | A3627 auto-plan | ✓ HIGH |
| **BAL-001** | License Balance CIF (Aggregate) | CANONICAL | `BALANCE = CREDIT − DEBIT` | balance_calculator | ⚠️ CACHING |
| **BAL-002** | BOE DEBIT Total | CANONICAL | `DEBIT = sum(boe_rows.cif where visible)` | balance_calculator | ✓ HIGH |
| **BAL-003** | BOE CREDIT Total | CANONICAL | `CREDIT = sum(boe_debit_rows.cif)` | balance_calculator | ✓ HIGH |
| **BAL-004** | Group Used Qty Snapshot | CONSUMER | `used = sum(item.allotted_qty for group)` | plan_enforcement | ✓ HIGH |
| **BAL-005** | Group Used CIF Snapshot | CONSUMER | `used = sum(item.allotted_value for group)` | plan_enforcement | ✓ HIGH |

---

## Detailed Calculation Specifications

### SECTION 1: CATEGORY ALLOCATION (E1 / E5 Planning)

#### PLAN-001: Category CIF Allocation
| Attribute | Value |
|-----------|-------|
| **Name** | Category CIF Allocation (Waterfall) |
| **Type** | Financial / Category-Level |
| **Classification** | **CANONICAL** |
| **Purpose** | Distribute license balance_cif to item categories proportionally by weight |
| **Formula** | `category_share_cif = balance_cif × (category_weight / total_weight)` |
| **Input Variables** | • `balance_cif` (Decimal) — license's available CIF budget<br/>• `category_weight` (Decimal) — sum of available_qty for all items in category<br/>• `total_weight` (Decimal) — sum of available_qty across ALL categories |
| **Output Type** | Decimal, rounded to 2 decimals |
| **Precision** | Decimal (Python Decimal type); rounded via `_quantize(Decimal("0.01"), ROUND_HALF_UP)` |
| **Rounding Rule** | ROUND_HALF_UP (banker's rounding) |
| **Unit** | CIF (Currency/Financial) |
| **Consumers** | PLAN-002 (per-item unit price) |
| **Source File** | `backend/apps/license/services/e1_plan.py:225-306` |
| **Confidence** | HIGH |
| **Known Issues** | None |
| **Test Coverage** | ✓ Covered in test suite |
| **Validation Checks** | None (assumed valid input) |

---

#### PLAN-002: Per-Item Unit Price from Category
| Attribute | Value |
|-----------|-------|
| **Name** | Per-Item Unit Price |
| **Type** | Financial / Item-Level |
| **Classification** | **CANONICAL** |
| **Purpose** | Compute uniform unit price for all items in a category |
| **Formula** | `per_item_unit_price = category_share_cif / category_weight` |
| **Input Variables** | • `category_share_cif` (Decimal) — output of PLAN-001<br/>• `category_weight` (Decimal) — sum of available_qty |
| **Output Type** | Decimal, rounded to 2 decimals |
| **Precision** | Decimal; result rounded to 2 decimals |
| **Rounding Rule** | ROUND_HALF_UP |
| **Unit** | CIF per kg/unit |
| **Consumers** | PLAN-003 (per-item planned cif), validation checks |
| **Source File** | `backend/apps/license/services/e1_plan.py:280-290` |
| **Confidence** | HIGH |
| **Known Issues** | None |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Validated against ceiling price (PLAN-013) |

---

#### PLAN-003: Per-Item Planned CIF
| Attribute | Value |
|-----------|-------|
| **Name** | Per-Item Planned CIF Value |
| **Type** | Financial / Item-Level |
| **Classification** | **CANONICAL** |
| **Purpose** | Compute planned CIF value for each item: quantity × unit_price |
| **Formula** | `planned_cif_fc = planned_quantity × per_item_unit_price` |
| **Input Variables** | • `planned_quantity` (Decimal) — available quantity for item<br/>• `per_item_unit_price` (Decimal) — output of PLAN-002 |
| **Output Type** | Decimal, rounded to 2 decimals |
| **Precision** | Decimal; result `quantize(Decimal("0.01"), ROUND_HALF_UP)` |
| **Rounding Rule** | ROUND_HALF_UP |
| **Unit** | CIF (Currency) |
| **Consumers** | Ledger calculations, balance tracking, reports |
| **Source File** | `backend/apps/license/services/e1_plan.py:290-306` |
| **Confidence** | HIGH |
| **Known Issues** | None (applies to E1 only; E126/E132 have defect PLAN-007) |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Invariant: `planned_cif_fc == planned_qty × unit_price` (violated by PLAN-007) |

---

### SECTION 2: ITEM REMAINING CALCULATIONS

#### PLAN-004: Item Remaining Quantity
| Attribute | Value |
|-----------|-------|
| **Name** | Item Remaining Quantity (Planned − Allotted) |
| **Type** | Quantity Tracking / Item-Level |
| **Classification** | **CONSUMER / DUPLICATE** ⚠️ |
| **Purpose** | Track unallocated quantity after allotments are made |
| **Formula** | `remaining_qty = max(planned_qty − allotted_qty, 0)` |
| **Input Variables** | • `planned_quantity` (float) — from LicenseItemPlan.planned_quantity<br/>• `allotted_quantity` (float) — from LicenseImportItemsModel (maintained by signals) |
| **Output Type** | float ≥ 0 |
| **Precision** | No additional rounding (already rounded in source fields) |
| **Rounding Rule** | None |
| **Unit** | kg / units (commodity-dependent) |
| **Consumers** | Ledger display, balance reports, plan_enforcement |
| **Source Files** | **Multiple locations (DUPLICATE CALCULATION):**<br/>• `backend/apps/license/services/norm_plan.py:105-111` (effective_plan_for_license)<br/>• `backend/apps/license/services/plan_enforcement.py:252-265` (plan_status_for)<br/>• `backend/apps/license/services/balance_calculator.py` (ledger calculations) |
| **Confidence** | HIGH (but duplicated) |
| **Known Issues** | **[BL-LEDGER-03]** `ItemBalanceCalculator.calculate_item_balance()` ignores sibling items' outstanding allotments in zero-cif_fc branch (debit uses ENTIRE license's BOE, not item's portion) |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Result must be ≥ 0 (enforced by max()) |

---

#### PLAN-005: Item Remaining CIF
| Attribute | Value |
|-----------|-------|
| **Name** | Item Remaining CIF Value |
| **Type** | Financial / Item-Level |
| **Classification** | **CONSUMER / DUPLICATE** ⚠️ |
| **Purpose** | Track unallocated CIF value after allotments |
| **Formula** | `remaining_cif = max(planned_cif − allotted_value, 0)` |
| **Input Variables** | • `planned_cif_fc` (float) — from LicenseItemPlan.planned_cif_fc<br/>• `allotted_value` (float) — from LicenseImportItemsModel (maintained by signals) |
| **Output Type** | float ≥ 0 |
| **Precision** | No additional rounding |
| **Rounding Rule** | None |
| **Unit** | CIF (Currency) |
| **Consumers** | Ledger display, balance reports, plan_enforcement |
| **Source Files** | **Multiple locations (DUPLICATE):**<br/>• `backend/apps/license/services/norm_plan.py:105-111`<br/>• `backend/apps/license/services/plan_enforcement.py:252-265` |
| **Confidence** | HIGH (but duplicated) |
| **Known Issues** | **[BL-LEDGER-03]** Same issue as PLAN-004 |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Result must be ≥ 0 (enforced by max()) |

---

### SECTION 3: QUANTITY FLOORING (E126 / E132 Auto-Plan)

#### PLAN-006: Floor Quantity to Whole Number
| Attribute | Value |
|-----------|-------|
| **Name** | Quantity Floor to Integer |
| **Type** | Quantity Normalization / Item-Level |
| **Classification** | **CANONICAL** |
| **Purpose** | Convert fractional split quantities to whole units for E126/E132 auto-plans |
| **Formula** | `floored_qty = floor(raw_planned_qty)` |
| **Input Variables** | • `raw_planned_quantity` (Decimal or float) — from plan_e126_per_item_split / plan_e132_per_item_split (may be fractional, e.g., 50.5) |
| **Output Type** | float (integer value, no fractional part) |
| **Precision** | float; no fractional part |
| **Rounding Rule** | **FLOOR** (toward −∞), NOT ROUND_HALF_UP |
| **Unit** | kg / units |
| **Consumers** | LicenseItemPlan.planned_quantity (persisted) |
| **Source Code (E126)** | ```python<br/>def _floor_qty(x) -> float:<br/>    try:<br/>        return float(math.floor(float(x)))<br/>    except (TypeError, ValueError):<br/>        return 0.0<br/>``` |
| **Source Code (E132)** | ```python<br/>def _floor_qty(x) -> float:<br/>    try:<br/>        return float(math.floor(float(x)))<br/>    except (TypeError, ValueError):<br/>        return 0.0<br/>``` |
| **Source Files** | • E126: `backend/apps/license/services/e126_auto_plan.py:111-116` + `242-266` (usage)<br/>• E132: `backend/apps/license/services/e132_auto_plan.py:108-113` + `239-269` (usage) |
| **Confidence** | HIGH |
| **Known Issues** | **[INDIRECT]** CIF NOT recomputed after flooring (see PLAN-007) |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | None |

---

#### PLAN-007: **[DEFECT]** CIF Not Recomputed After Flooring
| Attribute | Value |
|-----------|-------|
| **Name** | **[BL-PLAN-01]** CIF Value Mismatch Post-Floor |
| **Type** | Financial / Item-Level |
| **Classification** | **DUPLICATE / DEFECT** ❌ |
| **Purpose** | **[SHOULD]** Recompute planned_cif_fc after flooring quantity |
| **Expected Formula** | `planned_cif_fc = round(floored_qty × unit_price, 2)` |
| **Actual Formula (DEFECT)** | `planned_cif_fc = round(raw_planned_cif, 2)` ← **NOT recomputed!** |
| **Impact** | • Violates invariant: `planned_cif_fc ≠ planned_qty × unit_price`<br/>• Consumes real balance CIF against non-plannable quantity<br/>• Makes `LicenseItemPlan` internally inconsistent |
| **Numerical Example** | **Input:** PKO/Olive Oil split, available_qty=101, balance_cif=343.40<br/>**Raw split:** PKO 50.5@1.80=90.90, Olive Oil 50.5@5.00=252.50<br/>**Expected output (if corrected):**<br/>&nbsp;&nbsp;PKO: qty=50, price=1.80, cif=50×1.80=**90.00**<br/>&nbsp;&nbsp;Olive Oil: qty=50, price=5.00, cif=50×5.00=**250.00**<br/>**Actual output (DEFECT):**<br/>&nbsp;&nbsp;PKO: qty=50, price=1.80, cif=**90.90** (mismatch +0.90)<br/>&nbsp;&nbsp;Olive Oil: qty=50, price=5.00, cif=**252.50** (mismatch +2.50) |
| **Sources** | • E126: `backend/apps/license/services/e126_auto_plan.py:242-266`<br/>• E132: `backend/apps/license/services/e132_auto_plan.py:239-269` |
| **Confidence** | **HIGH** (independently reproduced; skeptic check with qty=77 confirmed) |
| **Known Issues** | **YES — CRITICAL**<br/>• Preserved plan branch (PLAN-015) **inherits** this defect<br/>• Re-running auto-plan does NOT fix it<br/>• Defect persists until manually corrected or auto-plan engine is changed |
| **Test Coverage** | ⚠️ May not be caught if tests don't validate `qty × price == cif` invariant |
| **Suggested Fix** | Recompute: `planned_cif_fc = round(floored_qty × _r2(unit_price), 2)` (mirroring E5's pattern) |
| **Blocker Status** | **YES — Classification DUPLICATE; defect affects E126 & E132** |

---

### SECTION 4: MILK SPLIT ALLOCATION (E5 / E132)

#### PLAN-008 to PLAN-011: Milk 40/60 Split
| Attribute | Value |
|-----------|-------|
| **Name** | Milk 40/60 Split Allocation |
| **Type** | Financial / Category-Level |
| **Classification** | **CANONICAL** |
| **Purpose** | Allocate milk balance_cif into 40% and 60% buckets with separate unit prices |
| **Formula** | **PLAN-008:** `milk_40_cif = balance_cif × 0.40`<br/>**PLAN-009:** `milk_40_qty = min(milk_avail_qty, milk_40_cif / milk_price_40)`<br/>**PLAN-010:** `milk_60_cif = balance_cif × 0.60`<br/>**PLAN-011:** `milk_60_qty = min(milk_avail_qty − milk_40_qty, milk_60_cif / milk_price_60)` |
| **Input Variables** | • `milk_avail_qty` (float) — available milk quantity for license<br/>• `balance_cif` (Decimal) — available license CIF budget<br/>• `milk_price_40` (Decimal) — fixed ceiling price (40% bucket)<br/>• `milk_price_60` (Decimal) — fixed ceiling price (60% bucket) |
| **Output Type** | (qty_40, qty_60, cif_40, cif_60) — all Decimal or float, rounded to 2 decimals |
| **Precision** | Decimal; results via `_quantize(Decimal("0.01"), ROUND_HALF_UP)` |
| **Rounding Rule** | ROUND_HALF_UP |
| **Unit** | Qty: kg / units; CIF: Currency |
| **Consumers** | LicenseItemPlan rows for milk category items |
| **Source File** | `backend/apps/license/services/milk_planner.py:48-82` (split_milk_0404) |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | • Qty must be ≤ available<br/>• CIF must be ≤ balance_cif |

---

### SECTION 5: PRECISION & ROUNDING INFRASTRUCTURE

#### PLAN-012: Round to 2 Decimals (_r2)
| Attribute | Value |
|-----------|-------|
| **Name** | _r2() Rounding Utility |
| **Type** | Infrastructure / Precision Control |
| **Classification** | **CANONICAL** |
| **Purpose** | Universal helper to round values to 2 decimal places |
| **Formula** | `round(x, 2) → float` |
| **Input Variables** | • `x` (any type) — coerced to float |
| **Output Type** | float with max 2 decimal places |
| **Precision** | Python's float (16 significant digits) |
| **Rounding Rule** | Python's default (banker's rounding, not ROUND_HALF_UP) |
| **Error Handling** | Returns 0.0 if x is unparseable |
| **Source Code (E126)** | ```python<br/>def _r2(x) -> float:<br/>    try:<br/>        return round(float(x), 2)<br/>    except (TypeError, ValueError):<br/>        return 0.0<br/>``` |
| **Source Code (E132)** | ```python<br/>def _r2(x) -> float:<br/>    try:<br/>        return round(float(x), 2)<br/>    except (TypeError, ValueError):<br/>        return 0.0<br/>``` |
| **Source Files** | • E126: `backend/apps/license/services/e126_auto_plan.py:104-109`<br/>• E132: `backend/apps/license/services/e132_auto_plan.py:101-106` |
| **Confidence** | HIGH (byte-identical in both files) |
| **Known Issues** | None (consistent use across codebase) |
| **Test Coverage** | ✓ Implicit (used in all CIF calculations) |
| **Validation Checks** | None |

---

### SECTION 6: VALIDATION CHECKS

#### PLAN-013: Validate Unit Price ≤ Ceiling Price
| Attribute | Value |
|-----------|-------|
| **Name** | Unit Price Ceiling Validation |
| **Type** | Validation / Constraint Check |
| **Classification** | **VALIDATION** |
| **Purpose** | Ensure auto-plan unit prices respect planning item ceiling prices |
| **Formula** | `is_valid = unit_price ≤ ceiling_price × 1.01` (1% tolerance for rounding) |
| **Input Variables** | • `unit_price` (float) — computed by auto-plan engine<br/>• `ceiling_price` (Decimal) — from PlanningItemModel<br/>• `tolerance` (float) — hardcoded 0.01 (1%) |
| **Output Type** | Boolean (True = valid, False = invalid) |
| **Precision** | N/A (comparison only) |
| **Unit** | CIF per kg/unit |
| **Consumers** | plan_grouping validation logic |
| **Source File** | `backend/apps/license/services/plan_grouping.py:330-391` (validate_group_plan_lines) |
| **Confidence** | HIGH |
| **Known Issues** | ❌ Does NOT validate `planned_cif_fc == planned_qty × unit_price` invariant (per BL-PLAN-01) |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Primary validation (gates plan creation) |

---

#### PLAN-014: Validate Total Quantity ≤ Available Quantity
| Attribute | Value |
|-----------|-------|
| **Name** | Group Quantity Cap Validation |
| **Type** | Validation / Constraint Check |
| **Classification** | **VALIDATION** |
| **Purpose** | Ensure group plan lines don't exceed group's available quantity |
| **Formula** | `is_valid = sum(planned_qty for all lines in group) ≤ available_qty × 1.01` |
| **Input Variables** | • `planned_qty` (list of floats) — from each plan line<br/>• `available_qty` (float) — sum of import items in group<br/>• `tolerance` (float) — hardcoded 0.01 (1%) |
| **Output Type** | Boolean (True = valid, False = invalid) |
| **Precision** | N/A (comparison only) |
| **Unit** | kg / units |
| **Consumers** | plan_grouping validation logic |
| **Source File** | `backend/apps/license/services/plan_grouping.py:330-391` |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Primary validation (gates plan creation) |

---

### SECTION 7: INFRASTRUCTURE & LEGACY

#### PLAN-015: Preserved Plan Passthrough
| Attribute | Value |
|-----------|-------|
| **Name** | Preserved Plan Re-Emission |
| **Type** | Infrastructure / Non-Computation |
| **Classification** | **INFRASTRUCTURE / LEGACY** |
| **Purpose** | For licenses with existing auto-plans, re-emit same lines without recomputation during re-generation |
| **Formula** | `output = input` (no calculation; copy all fields verbatim) |
| **Input Variables** | Existing `LicenseItemPlan` row with `preserved_during_re_generation=True` |
| **Output Type** | Identical `LicenseItemPlan` row |
| **Precision** | N/A |
| **Unit** | N/A |
| **Consumers** | Database persistence |
| **Source File** | `backend/apps/license/services/plan_enforcement.py:180-191` (save_plan_lines_for_license, preserved branch) |
| **Confidence** | HIGH |
| **Known Issues** | ⚠️ **If original line has BL-PLAN-01 mismatch, this branch INHERITS it**<br/>Re-running auto-plan does NOT fix the defect; it persists forever |
| **Test Coverage** | ✓ Covered (but does not validate invariant) |
| **Validation Checks** | None (uses existing row as-is) |

---

### SECTION 8: AVAILABLE QUANTITY CALCULATIONS

#### PLAN-016: License Available Quantity (Sum)
| Attribute | Value |
|-----------|-------|
| **Name** | License Total Available Quantity |
| **Type** | Financial / Aggregate Balance |
| **Classification** | **CANONICAL** |
| **Purpose** | Compute license-level available quantity for planning |
| **Formula** | `license_available_qty = sum(import_item.available_qty for all import items)` |
| **Input Variables** | • List of `LicenseImportItemsModel` rows for license |
| **Output Type** | float (kg / units, commodity-dependent) |
| **Precision** | Depends on source (DGFT data, typically 2-3 decimals for weights) |
| **Rounding Rule** | None (summed as-is from source) |
| **Unit** | kg / units |
| **Consumers** | All planning engines (E1, E5, E126, E132, A3627) |
| **Source File** | Implicit across all planners |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Result must be ≥ 0 |

---

#### PLAN-017: Item Available Quantity (Persisted)
| Attribute | Value |
|-----------|-------|
| **Name** | Per-Item Available Quantity |
| **Type** | Financial / Balance Tracking |
| **Classification** | **CANONICAL** (persisted, not computed) |
| **Purpose** | Track per-import-item available quantity from DGFT import |
| **Formula** | `item_available_qty = LicenseImportItemsModel.available_quantity` (persisted field, not computed) |
| **Input Variables** | • `balance_cif_fc` (float, if applicable)<br/>• Or weight/volume from import |
| **Output Type** | float |
| **Precision** | As per DGFT source (typically 2-3 decimals) |
| **Rounding Rule** | None (stored as-is) |
| **Unit** | kg / units / CIF (depends on commodity) |
| **Consumers** | All calculations that need item-level quantity |
| **Source File** | Set during license import; persisted in DB |
| **Confidence** | HIGH |
| **Known Issues** | None (source data issue, not calculation)<br/>**Audit Evidence:** 22 of 2401 import items have fractional available_qty (e.g., 3066.09, 5110.15, 9637.11) |
| **Test Coverage** | ✓ Implicit (used as source in all other calculations) |
| **Validation Checks** | None (source data assumed valid) |

---

### SECTION 9: A3627 FIXED-RATE ALLOCATION

#### PLAN-018: A3627 Fixed-Rate Allocation
| Attribute | Value |
|-----------|-------|
| **Name** | A3627 Fixed-Rate Item Allocation |
| **Type** | Financial / Item-Level |
| **Classification** | **CANONICAL** |
| **Purpose** | Auto-plan allocation for A3627 licenses with fixed per-item prices |
| **Formula** | `planned_qty = min(item_qty, remaining_cif / price)`<br/>`planned_cif = (planned_qty × price).quantize(Decimal("0.01"))` |
| **Input Variables** | • `item_qty` (Decimal) — item's available quantity<br/>• `price` (Decimal) — fixed per-item price<br/>• `remaining` (Decimal) — remaining license CIF budget |
| **Output Type** | (planned_qty, planned_cif) — both Decimal, cif rounded to 2 decimals |
| **Precision** | Decimal; cif via `.quantize(Decimal("0.01"))` |
| **Rounding Rule** | ROUND_HALF_UP (default for Decimal.quantize()) |
| **Unit** | qty: units; cif: Currency |
| **Consumers** | LicenseItemPlan rows |
| **Source File** | `backend/apps/license/services/a3627_auto_plan.py:??-??` (_allocate_fixed_rate function) |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Tests in test_auto_plan_all_live_balance.py (WIP) |
| **Validation Checks** | • planned_qty ≤ item_qty<br/>• planned_cif ≤ remaining_cif |

---

### SECTION 10: BALANCE CALCULATIONS

#### BAL-001: License Balance CIF (Aggregate)
| Attribute | Value |
|-----------|-------|
| **Name** | License Financial Balance |
| **Type** | Financial / Aggregate Balance |
| **Classification** | **CANONICAL** |
| **Purpose** | Compute license's available CIF budget (legal cap on import value) |
| **Formula** | `BALANCE = CREDIT − DEBIT`<br/>where:<br/>&nbsp;&nbsp;`DEBIT = sum(boe_rows.cif where visible & type=DEBIT)`<br/>&nbsp;&nbsp;`CREDIT = sum(boe_rows.cif where type=CREDIT)` |
| **Input Variables** | • All `BillOfEntryRowDetails` rows for license<br/>• Status field (hidden vs. visible)<br/>• Transaction type (DEBIT vs. CREDIT) |
| **Output Type** | Decimal (cached in `LicenseBalance.balance_cif`) |
| **Precision** | Decimal |
| **Rounding Rule** | N/A (sum of already-precise values) |
| **Unit** | CIF (Currency) |
| **Consumers** | All planning engines, ledger reports, balance displays |
| **Source File** | `backend/apps/license/services/balance_calculator.py:calculate_financial_balance()` |
| **Confidence** | MEDIUM (caching issue identified) |
| **Known Issues** | ⚠️ **[BL-LEDGER-02]** Cached `LicenseBalance.balance_cif` can go **stale** after reconciliation allocation actions<br/>• `InvoiceBOEAllocation` creation does NOT trigger balance refresh |
| **Test Coverage** | ✓ Covered (but caching issue may cause failures in concurrent tests) |
| **Validation Checks** | Result must be ≥ 0 (legally) |

---

#### BAL-002: BOE DEBIT Total
| Attribute | Value |
|-----------|-------|
| **Name** | Bill of Entry DEBIT Sum |
| **Type** | Financial / Aggregate |
| **Classification** | **CANONICAL** |
| **Purpose** | Compute total DEBIT (consumption) from BOE entries |
| **Formula** | `BOE_DEBIT = sum(boe_rows.cif where visible & type=DEBIT)` |
| **Input Variables** | • All `BillOfEntryRowDetails` rows for license<br/>• Visibility status (hidden vs. visible) |
| **Output Type** | Decimal |
| **Precision** | Decimal |
| **Unit** | CIF (Currency) |
| **Consumers** | BAL-001 (License Balance), ledger reports |
| **Source File** | `backend/apps/license/services/balance_calculator.py:calculate_boe_debit_total()` |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Result must be ≥ 0 |

---

#### BAL-003: BOE CREDIT Total
| Attribute | Value |
|-----------|-------|
| **Name** | Bill of Entry CREDIT Sum |
| **Type** | Financial / Aggregate |
| **Classification** | **CANONICAL** |
| **Purpose** | Compute total CREDIT (issuance) from BOE entries |
| **Formula** | `BOE_CREDIT = sum(boe_rows.cif where type=CREDIT)` |
| **Input Variables** | • All `BillOfEntryRowDetails` rows for license |
| **Output Type** | Decimal |
| **Precision** | Decimal |
| **Unit** | CIF (Currency) |
| **Consumers** | BAL-001 (License Balance), ledger reports |
| **Source File** | `backend/apps/license/services/balance_calculator.py:calculate_credit()` |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | Result must be ≥ 0 |

---

#### BAL-004 & BAL-005: Group Used Snapshots
| Attribute | Value |
|-----------|-------|
| **Name** | Group Used Quantity & CIF (Snapshot) |
| **Type** | Quantity Tracking / Group-Level |
| **Classification** | **CONSUMER** |
| **Purpose** | Snapshot allotted quantity and CIF for group of related items |
| **Formula (BAL-004)** | `group_used_qty = sum(item.allotted_quantity for item in group)` |
| **Formula (BAL-005)** | `group_used_cif = sum(item.allotted_value for item in group)` |
| **Input Variables** | • List of `LicenseImportItemsModel` with same group key |
| **Output Type** | (used_qty, used_cif) — tuple of floats |
| **Precision** | float (no additional rounding) |
| **Unit** | qty: kg/units; cif: Currency |
| **Consumers** | plan_enforcement validation logic |
| **Source File** | `backend/apps/license/services/plan_enforcement.py:116-128` (group_used_snapshot) |
| **Confidence** | HIGH |
| **Known Issues** | None identified |
| **Test Coverage** | ✓ Covered |
| **Validation Checks** | None |

---

## Classification Summary

### CANONICAL (Authoritative, Single Source)
| ID | Calculation |
|----|-------------|
| PLAN-001 | Category CIF Allocation |
| PLAN-002 | Per-Item Unit Price |
| PLAN-003 | Per-Item Planned CIF |
| PLAN-006 | Floor Quantity to Integer |
| PLAN-008 to 011 | Milk 40/60 Split |
| PLAN-012 | _r2() Rounding |
| PLAN-016 | License Available Qty (Sum) |
| PLAN-017 | Item Available Qty (Persisted) |
| PLAN-018 | A3627 Fixed-Rate Allocation |
| BAL-001 | License Balance CIF |
| BAL-002 | BOE DEBIT Total |
| BAL-003 | BOE CREDIT Total |
| **CANONICAL COUNT** | **16** |

---

### CONSUMER (Reads from Canonical)
| ID | Calculation | Status |
|----|-------------|--------|
| PLAN-004 | Item Remaining Qty | ⚠️ DUPLICATE |
| PLAN-005 | Item Remaining CIF | ⚠️ DUPLICATE |
| BAL-004 | Group Used Qty | ✓ Single location |
| BAL-005 | Group Used CIF | ✓ Single location |
| **CONSUMER COUNT** | **4** | **2 DUPLICATES** |

---

### VALIDATION (Constraint Checking)
| ID | Calculation |
|----|-------------|
| PLAN-013 | Unit Price ≤ Ceiling |
| PLAN-014 | Total Qty ≤ Available Qty |
| **VALIDATION COUNT** | **2** |

---

### INFRASTRUCTURE
| ID | Calculation | Notes |
|----|-------------|-------|
| PLAN-015 | Preserved Plan Passthrough | Non-computation; inherits defects |
| **INFRASTRUCTURE COUNT** | **1** |

---

### DEFECT / DUPLICATE
| ID | Calculation | Severity |
|----|-------------|----------|
| PLAN-007 | **[BL-PLAN-01]** CIF Not Recomputed After Floor | ❌ **CRITICAL** |
| **DEFECT COUNT** | **1** | **BLOCKER** |

---

## Aggregate Statistics

| Metric | Count |
|--------|-------|
| **Total Calculations** | **24** |
| **CANONICAL** | **16** |
| **CONSUMER** | **4** |
| **VALIDATION** | **2** |
| **INFRASTRUCTURE** | **1** |
| **DEFECT/DUPLICATE** | **1** |
| | |
| **Duplicate Calculations** | **2** (PLAN-004, PLAN-005) |
| **Unknown Classification** | **0** |
| **Known Defects** | **2** (BL-PLAN-01, BL-LEDGER-02) |
| **Blockers** | **1** (BL-PLAN-01: qty×price≠cif invariant violation) |

---

## Critical Issues & Risks

### 🔴 BLOCKER: BL-PLAN-01 — CIF Mismatch Post-Floor
- **Severity**: CRITICAL
- **Classification**: DUPLICATE + DEFECT
- **Affected Engines**: E126, E132
- **Description**: After flooring `planned_qty`, `planned_cif_fc` is NOT recomputed, violating `qty × price == cif` invariant
- **Impact**:
  - Consumes real balance CIF against non-plannable quantity
  - Makes `LicenseItemPlan` internally inconsistent
  - Persisted defect inherits through preserved plan branch (PLAN-015)
  - Misleads ledger balance calculations
- **Test Gap**: No test validates the `qty × price == cif` invariant
- **Suggested Fix**: Recompute `planned_cif = round(floored_qty × _r2(unit_price), 2)` (mirror E5 pattern)

---

### ⚠️ MEDIUM: BL-LEDGER-02 — Stale Balance Cache
- **Severity**: MEDIUM
- **Classification**: CANONICAL (but with caching issue)
- **Affected Calculation**: BAL-001 (License Balance CIF)
- **Description**: Cached `LicenseBalance.balance_cif` goes stale after reconciliation allocation actions
- **Root Cause**: `InvoiceBOEAllocation` creation does NOT trigger balance refresh signal
- **Impact**: Concurrent tests may see stale balance; plan validation may use wrong budget
- **Suggested Fix**: Add signal handler to refresh balance on `InvoiceBOEAllocation` creation

---

### ⚠️ HIGH: BL-LEDGER-03 — Item Balance Sibling Ignorance
- **Severity**: HIGH
- **Classification**: CONSUMER/DUPLICATE
- **Affected Calculations**: PLAN-004, PLAN-005
- **Description**: `ItemBalanceCalculator.calculate_item_balance()` ignores sibling items' outstanding allotments in zero-cif_fc branch
- **Impact**: Ledger debit uses ENTIRE license BOE instead of item's portion
- **Fix**: Account for sibling outstanding allotments in debit calculation

---

### ✅ DUPLICATE (Non-Critical): Item Remaining Calculations
- **Classifications**: PLAN-004, PLAN-005
- **Issue**: Same logic implemented in 3 locations (`norm_plan.py`, `plan_enforcement.py`, `balance_calculator.py`)
- **Impact**: Low (logic is simple: `max(planned - allotted, 0)`)
- **Recommendation**: Keep as-is for now; extract to shared helper in future refactor

---

## Recommendations

### Priority 1: Fix BL-PLAN-01 (BLOCKER)
1. Modify E126 & E132 engines to recompute `planned_cif` after flooring
2. Add test validating `planned_qty × unit_price == planned_cif` invariant
3. Audit existing E126/E132 plans for mismatches; flag for re-run

### Priority 2: Fix BL-LEDGER-02 (MEDIUM)
1. Add signal handler to refresh balance on `InvoiceBOEAllocation` creation
2. Add test validating balance recalc after reconciliation actions

### Priority 3: Clarify BL-LEDGER-03 (HIGH)
1. Verify intended behavior (should item balance include siblings?)
2. If intended, document explicitly; if bug, fix debit calculation

### Priority 4: Refactor (Future)
1. Extract item remaining calculation to shared helper
2. Document all calculations in single place (this register)
3. Add comprehensive invariant validation tests

---

## Document Metadata

| Field | Value |
|-------|-------|
| **Created** | 2026-08-10 |
| **Source Module** | docs/modules/MODULE_2_PLANNING_CALCULATIONS.md |
| **Codebase** | license-manager |
| **Reviewers** | Backend engineers, QA |
| **Maintainer** | Technical Writer / Backend Lead |
| **Last Verified** | 2026-08-10 |
| **Next Review** | After BL-PLAN-01 fix |

