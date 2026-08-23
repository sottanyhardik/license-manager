# MODULE 2 — PLANNING DUPLICATES & ENGINE ARCHITECTURE

## Overview

This document identifies whether multiple planning engines exist, which is canonical/authoritative, how they differ, and which consumers use which.

---

## 1. PLANNING ENGINE ARCHITECTURE

### 1.1 Single Canonical Auto-Plan Engine Per Norm

**Finding**: There is exactly ONE auto-plan engine per norm (E1, E5, E126, E132, A3627). No duplicates or competing implementations.

**Architecture**:

```
Per-Norm Auto-Plan Engines (Canonical)
├── compute_e1_auto_plan() → e1_auto_plan.py:96
├── compute_e5_auto_plan() → e5_auto_plan.py:128
├── compute_e126_auto_plan() → e126_auto_plan.py:118
├── compute_e132_auto_plan() → e132_auto_plan.py:115
└── compute_a3627_auto_plan() → a3627_auto_plan.py:205

Per-Norm Per-Item Planning Engine (Classification + Pricing)
├── plan_e1_items() → e1_plan.py:225
├── plan_e5_items() → e5_plan.py:233
├── plan_e126_per_item_split() → e126_plan.py:472
├── plan_e132_per_item_split() → e132_plan.py:532
└── (A3627 no separate per-item engine; uses fixed-rate allocation directly)

Per-Norm Per-Item Query Engine (For displays, not auto-plan)
├── plan_e1_per_item() → e1_plan.py (no separate function; uses plan_e1_items)
├── plan_e5_per_item() → e5_plan.py (no separate function; uses plan_e5_items)
├── plan_e126_per_item() → e126_plan.py:429
├── plan_e132_per_item() → e132_plan.py:489
└── (A3627 no separate query engine; no per-item display function)
```

**Consumers**:

| Auto-Plan Engine | Used By |
|------------------|---------|
| `compute_e1_auto_plan()` | `e1_auto_plan()` view + PlannerFactory.run() |
| `compute_e5_auto_plan()` | `auto_plan()` view + PlannerFactory.run() |
| `compute_e126_auto_plan()` | `auto_plan()` view + PlannerFactory.run() |
| `compute_e132_auto_plan()` | `auto_plan()` view + PlannerFactory.run() |
| `compute_a3627_auto_plan()` | `auto_plan()` view + PlannerFactory.run() |

| Per-Item Planning Engine | Used By |
|--------------------------|---------|
| `plan_e1_items()` | `norm_plan_for_license()` + Item Pivot Report |
| `plan_e5_items()` | `norm_plan_for_license()` + Item Pivot Report |
| `plan_e126_per_item_split()` | `norm_plan_for_license()` + `plan_e126_per_item()` |
| `plan_e132_per_item_split()` | `norm_plan_for_license()` + `plan_e132_per_item()` |

**Duplicates Found**: NONE (each norm has exactly one canonical engine per function type)

---

### 1.2 Shared Infrastructure (Not Per-Norm)

**Finding**: Some infrastructure is shared across norms; no conflicts or duplicates.

| Component | Location | Used By |
|-----------|----------|---------|
| Plan Enforcement | `plan_enforcement.py` | All norms |
| Plan Grouping | `plan_grouping.py` | All norms |
| Norm Detection | `norm_plan.py:detect_norm()` | All norms |
| Effective Plan Query | `norm_plan.py:effective_plan_for_license()` | All norms |
| Norm Plan Query | `norm_plan.py:norm_plan_for_license()` | All norms |
| Auto-Plan Factory | `planner_factory.py` | All norms |
| Shared Utilities | `auto_plan_shared.py` | E1/E5/E126/E132 |
| Milk Planning | `milk_planner.py` | E5/E132 |

**Duplicates Found**: NONE

---

## 2. CLASSIFICATION ENGINES

### 2.1 Per-Norm Classification

**Finding**: Each norm has its own classification function (item → planning category). No duplicates, but different patterns:

| Norm | Classification Function | Classification Type | Output |
|------|-------------------------|---------------------|--------|
| E1 | `classify_e1_item(name, hs, desc)` | Code-based (HS + description patterns) | Category name (e.g. "Cereals") |
| E5 | `classify_e5_item(name, hs, desc)` | Code-based (HS + description patterns) | Category name (e.g. "Oils", "Milk") |
| E126 | `classify_e126_record(record)` | Code-based (deterministic split on HSN 1513 + signals) | Planning item name (Nuts, PKO, Olive Oil) |
| E132 | `classify_e132_record(record)` | Code-based (deterministic classification into 6 categories) | Planning item name |
| A3627 | Implicit in `compute_a3627_auto_plan()` | Fixed-rate (no classification needed) | N/A |

**Pattern Differences**:

- **E1/E5**: Use category waterfall (many items → one category → one price)
- **E126/E132**: Use deterministic classification (one item → one planning item → fixed price)
- **A3627**: Use fixed-rate allocation (no classification)

**Duplicates Found**: NONE (each norm has 1 classification approach)

---

## 3. PRICING ENGINES

### 3.1 Per-Norm Pricing Models

**Finding**: Two distinct pricing patterns; no duplicates within pattern:

| Pricing Type | Norms | Mechanism | Example |
|--------------|-------|-----------|---------|
| **Category Waterfall** | E1, E5 | Allocate balance_cif to categories by weight; compute category unit price = cif / qty; apply to all items in category | E1 Cereals: 10 items in category, allocate category_cif to 10 items at category_price |
| **Fixed Planning Item Price** | E126, E132 | Each planning item has a fixed ceiling price stored in DB; multiply available_qty × fixed_price | E126 PKO: fixed price = 1.80, plan_qty × 1.80 = plan_cif |
| **Fixed Rate** | A3627 | Similar to fixed planning item, but with dynamic category-level aggregation | A3627 Rutile: fixed price × qty |

**Duplicates Found**: NONE (each model is unique to its norms)

**Interaction**: 

- Category waterfall (E1/E5) and fixed pricing (E126/E132) are mutually exclusive per license (one norm per license)
- No license can have mixed E1 + E126 planning

---

## 4. VALIDATION & ENFORCEMENT DUPLICATION

### 4.1 Single Validation Gate (Shared)

**Finding**: All norms use the same validation gate; no duplicate checks.

| Validation | Location | Used By | Checks |
|-----------|----------|---------|--------|
| `validate_group_plan_lines()` | `plan_grouping.py:330` | All auto-plan engines | (1) unit_price ≤ ceiling + 1%, (2) sum(qty) ≤ available + 1% |

**Duplicates Found**: NONE (single shared gate)

**Gap**: The gate does NOT check `planned_cif_fc == planned_quantity × unit_price` (per audit BL-PLAN-01)

---

### 4.2 Single Persistence Layer (Shared)

**Finding**: All norms save plan lines via the same function; no duplicate save paths.

| Function | Location | Used By | Behavior |
|----------|----------|---------|----------|
| `save_plan_lines_for_license()` | `plan_enforcement.py:130` | All auto-plan engines | Create LicenseItemPlan rows, handle preserved flag |

**Duplicates Found**: NONE

---

## 5. API ENDPOINT DISPATCH

### 5.1 Unified Endpoint with Dispatch

**Finding**: Single endpoint dispatches to per-norm engines; no duplicate endpoints.

```
POST /auto-plan/ → views.auto_plan()
  ├─ detect_norm(license_obj)
  ├─ PlannerFactory.run(license_obj, norm_code)
  │  └─ Dispatches to: compute_e1_auto_plan() | compute_e5_auto_plan() | ...
  └─ save_plan_lines_for_license()

POST /e1-auto-plan/ → views.e1_auto_plan()  [explicit E1, ignores norm detection]
  ├─ Force norm_code = 'E1'
  ├─ PlannerFactory.run(license_obj, 'E1')
  └─ save_plan_lines_for_license()

POST /auto-plan-all/ → views.auto_plan_all()
  └─ Loop: for each license, call auto_plan()
```

**Duplicates Found**: NONE (single dispatch layer with optional explicit norm)

---

## 6. PER-ITEM QUERY ENGINE DUPLICATION

### 6.1 Query Engines (For Display, Not Auto-Plan)

**Finding**: Each norm has a query engine for Item Pivot Report / License Overview; these are SEPARATE from auto-plan engines.

| Query Engine | Location | Used By | Purpose |
|--------------|----------|---------|---------|
| `plan_e1_items()` | `e1_plan.py:225` | `norm_plan_for_license()`, Item Pivot Report | Generate E1 plan for display |
| `plan_e5_items()` | `e5_plan.py:233` | `norm_plan_for_license()`, Item Pivot Report | Generate E5 plan for display |
| `plan_e126_per_item()` | `e126_plan.py:429` | `norm_plan_for_license()` | Generate E126 plan for display |
| `plan_e132_per_item()` | `e132_plan.py:489` | `norm_plan_for_license()` | Generate E132 plan for display |

**Relationship to Auto-Plan**:

- `compute_e1_auto_plan()` internally calls `plan_e1_items()` (reuses the query engine)
- `compute_e5_auto_plan()` internally calls `plan_e5_items()` (reuses)
- `compute_e126_auto_plan()` does NOT directly call `plan_e126_per_item()` (separate paths)
- `compute_e132_auto_plan()` does NOT directly call `plan_e132_per_item()` (separate paths)

**Duplicates Found**: NONE (each query engine is called by one code path for display)

**Architecture Implication**: 

- For E1/E5: The auto-plan and display plans use the SAME underlying calculation (`plan_e1_items()`, `plan_e5_items()`), so they always match
- For E126/E132: The auto-plan uses `plan_e126_per_item_split()` (with flooring defect), while display uses `plan_e126_per_item()` (may differ due to BL-PLAN-01 defect)

---

## 7. PRESERVED PLAN RE-EMISSION

### 7.1 Single Preserved Branch (Shared)

**Finding**: All norms use the same preserved re-emission logic; no duplicate implementation.

```
save_plan_lines_for_license()
├─ preserved_branch: if (LicenseItemPlan.preserved_during_re_generation == True)
│  └─ Re-emit line verbatim (no recomputation)
└─ fresh_branch: Create new line
```

**Duplicates Found**: NONE

---

## 8. IDENTIFICATION OF AMBIGUOUS DUPLICATION

### 8.1 E126/E132 Per-Item vs. Per-Item-Split Functions

**Potential Confusion**: E126 and E132 each have TWO per-item functions:

| Norm | Function 1 | Function 2 | Difference |
|------|-----------|-----------|-----------|
| E126 | `plan_e126_per_item()` (line 429) | `plan_e126_per_item_split()` (line 472) | `per_item()` groups items by classification, returns one line per import_item. `per_item_split()` handles splits internally, returns multiple lines if split |
| E132 | `plan_e132_per_item()` (line 489) | `plan_e132_per_item_split()` (line 532) | Same distinction as E126 |

**Clarification**: NOT duplicates — different responsibilities:

- `plan_e126_per_item(import_item)` → Called from `norm_plan_for_license()` for display; groups all items, returns aggregated plan
- `plan_e126_per_item_split(import_item)` → Called from `plan_e126_per_item()` internally for classification/split logic; handles per-item splitting

**Call Chain**:
```
norm_plan_for_license() [for display]
  └─ plan_e126_per_item(all_items)
     └─ (internally calls classify_e126_record for each item)
        └─ plan_e126_per_item_split() [for split detection]
           └─ Returns {planning_item_id: {...}}
```

**No duplication**: Clear separation of concerns

---

## Summary: Duplicate Analysis

| Component | Count | Duplicates | Status |
|-----------|-------|-----------|--------|
| Per-Norm Auto-Plan Engines | 5 | 0 | CLEAN |
| Per-Norm Classification Engines | 5 | 0 | CLEAN |
| Per-Norm Pricing Models | 3 types | 0 | CLEAN |
| Shared Validation | 1 | 0 | CLEAN |
| Shared Persistence | 1 | 0 | CLEAN |
| API Endpoints | 3 | 0 | CLEAN |
| Per-Item Query Engines | 4 | 0 | CLEAN (separate from auto-plan) |
| Preserved Re-Emission | 1 | 0 | CLEAN |
| **TOTAL** | | **0 duplicates** | **NO REDUNDANCY** |

**Conclusion**: The planning system has a clean, non-duplicated architecture. Each norm has exactly one canonical auto-plan engine, one classification approach, and one pricing model. All norms share infrastructure (validation, persistence, dispatch) appropriately. No competing implementations or redundant code paths identified.

