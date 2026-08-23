# E126 & E132 Planning Semantics Extraction & DB Migration Design

**Phase 2B Task**: Extract all E126 and E132 planning semantics from hard-coded planners and design migration to database rules (SionPlanningRule + execution).

Date: 2026-08-17  
Status: Analysis Complete  
Scope: Both E126 and E132 norms with split handling

---

## PART 1: E126 SEMANTICS EXTRACTION

### 1.1 Overview

**File(s)**: `/backend/apps/license/services/e126_plan.py` (primary), `/backend/apps/license/services/e126_auto_plan.py` (auto-execution)

**Norm Type**: E126 (Edible Oils and Oilseeds)

**Planning Items**: 3 categories
1. NUTS - E126 ($3.00/unit)
2. PALM KERNEL OIL - E126 ($1.80/unit)
3. OLIVE OIL - E126 ($5.00/unit)

**Special Feature**: PKO/Olive Oil **50%/50% split** when both signals present on same import item (per-record split, not license-wide pooled)

### 1.2 Classification Rules (Priority Order)

E126 uses an **ordered priority engine**: first matching rule wins. Records classified to internal `__PKO_OLIVE_SPLIT__` are expanded into PKO + Olive Oil lines at allocation time.

#### Priority 1: NUTS - E126

**Function**: `_rule_nuts(hsn, desc) → reason | None`

**Match Conditions**:
- **AND** HSN code is 0802 (prefix match: `0802`, `0802xxxx`, `0802.xx.xx`) **OR** description contains `0802` (word-boundary match)
- **AND** description contains the **word** `NUT` or `NUTS` (case-insensitive, word-boundary match)

**Examples**:
- `hs_code="08021100"`, `description="Cashew Nuts"` → NUTS ✓
- `hs_code="9999"`, `description="cashew 0802 grade nut"` → NUTS ✓
- `hs_code="08021100"`, `description="Almond Kernel"` → None (no word "nut"/"nuts") ✗
- `hs_code="08029090"`, `description="Peanut Kernels"` → None (word "peanut" ≠ word "nut") ✗

**Unit Price**: Fixed $3.00/unit

**Quantity**: Entire import item's current `available_quantity`

**CIF Allocation**: Waterfall-allocated (see §1.4)

#### Priority 2: Palm Kernel Oil (PKO) / Olive Oil / Split

**Sub-priority** (first match wins):
1. **Split**: 1513 signal **AND** Olive Oil signal both present on same record
2. **PKO alone**: 1513 signal without Olive Oil signal
3. **Olive Oil alone**: Olive Oil signal without 1513 signal

**Function**: `_rule_priority_2(hsn, desc) → (item_name, reason) | None`

##### PKO Detection (`_is_pko_signal`)

HSN 1513 (prefix match) **OR** description contains `1513` (word-boundary match)

Examples:
- `hs_code="15132900"` → PKO signal ✓
- `description="oil grade 1513"` → PKO signal ✓
- `description="batch 15130"` → PKO signal ✓ (1513 is word-boundary matched)

##### Olive Oil Detection (`_is_olive_oil_signal`)

**OR** condition (any match):
1. HSN 1509 (prefix match: `1509`, `1509xxxx`, `1509.xx.xx`)
2. Description contains `1500` (plain substring — no word-boundary)
3. Description contains `1509` (plain substring)
4. Description contains `1510` (plain substring)

Examples:
- `hs_code="15091000"` → Olive Oil signal ✓
- `hs_code="15090000"` → Olive Oil signal ✓
- `description="olive oil 1509 grade"` → Olive Oil signal ✓ (substring match)
- `description="batch 15091 grade"` → Olive Oil signal ✓ (1509 is substring of 15091)
- `description="vegetable fat 1500"` → Olive Oil signal ✓

##### Split Condition

When **both** 1513 **and** Olive Oil signals present on the same import item:
- Internal classification: `__PKO_OLIVE_SPLIT__` (never shown to user)
- Split target: 50% PKO, 50% Olive Oil of **this record's current available_quantity**
- Reason: `"HSN/desc=1513 AND Olive Oil signal (1509/1500/1510) — 50% PKO / 50% Olive Oil split"`

Example:
- `hs_code="15132900"`, `description="Palm Kernel and Olive 1509 blend"` → Split (1513 + 1509)
- Available qty: 1000 units → PKO gets 500, Olive Oil gets 500

##### PKO-Only Condition

When **only** 1513 signal present:
- Classification: `PALM KERNEL OIL - E126`
- Quantity: 100% of available_quantity
- Unit Price: $1.80/unit

##### Olive Oil-Only Condition

When **only** Olive Oil signal present:
- Classification: `OLIVE OIL - E126`
- Quantity: 100% of available_quantity
- Unit Price: $5.00/unit

##### No Match

If no rule fires → `(None, None)` → record goes to exception report (not classified)

### 1.3 Data Input Mapping

**Source Model**: `LicenseImportItemsModel` (E126 licence)

| Field | Mapping | Notes |
|-------|---------|-------|
| Norm | licence.export_norm_class == `"E126"` | Pre-filtered by caller |
| HSN Code | `item.hs_code.hs_code` | str; may be null/blank |
| Description | `item.description` | str; may be null/blank |
| Quantity | `item.available_quantity` | Decimal; current allocatable pool |
| Record ID | `item.id` | Preserved for traceability |

**Normalization** (applied before classification):
- HSN: Digits-only (`0802` → `0802`, `0802.20.00` → `080220`, `0802 20 00` → `080220`)
- Description: Lower-case, trim, collapse internal whitespace; `None`/blank → `""`

### 1.4 Aggregation & Waterfall Allocation

**Pipeline**:
1. Classify each record → planning item name or `__PKO_OLIVE_SPLIT__`
2. Aggregate by item: sum quantities, count source records
3. Waterfall-allocate planned value in PLANNING_ORDER (Nuts → PKO → Olive Oil)
4. Wastage-reduction rebalance (PKO → Olive Oil)

#### Aggregation

For records with item == `__PKO_OLIVE_SPLIT__`:
- Extract split: `{PKO: qty*0.5, OLIVE_OIL: qty*0.5}`
- Add **both** PKO and Olive Oil to their respective buckets

Example:
```
Record 1: 1000 units → NUTS
Record 2: 600 units → __PKO_OLIVE_SPLIT__ → {PKO: 300, OLIVE_OIL: 300}
Record 3: 400 units → PKO

Aggregated buckets:
- NUTS: qty=1000, count=1
- PKO: qty=300+400=700, count=2 (both records 2&3 count as sources)
- OLIVE_OIL: qty=300, count=1
```

#### Waterfall Allocation

Allocates planned value in priority order, capping total at `balance_cif` (licence Balance CIF).

**Algorithm**:
```
remaining_balance = balance_cif
for item in (NUTS, PKO, OLIVE_OIL):
    qty = agg[item].qty
    max_price = UNIT_PRICE[item]
    requested_value = qty * max_price
    if requested_value <= remaining_balance:
        allocated_value = requested_value
        effective_price = max_price
    else:
        allocated_value = remaining_balance
        effective_price = remaining_balance / qty  (or max_price if qty ≤ 0)
    remaining_balance -= allocated_value
    output[item] = {
        qty, value=allocated_value, price=effective_price, count
    }
```

**Key Rules**:
- **Capping**: Total planned value ≤ `balance_cif` (max debit per licence)
- **Per-item effective rate**: Dropped proportionally if item overflows remaining balance
- **Uncapped mode**: When `balance_cif=None`, value = qty × max_price (classification-only/report mode)

#### Wastage-Reduction Rebalance

If waterfall leaves remaining balance unused, shift quantity from PKO → Olive Oil on split records:
- **Why**: Olive Oil ($5.00) > PKO ($1.80), so shifting quantity increases total planned value without increasing total planned quantity
- **Value gain per unit shifted**: $5.00 - $1.80 = $3.20
- **Only on split records**: Non-split PKO records unaffected
- **Deterministic & idempotent**: Each split record shifted once, closed-form calc: `min(split_record.pko_qty, remaining_balance / $3.20)`
- **Order**: Split records visited in import item serial-number order
- **Stop conditions**: Either `remaining_balance ≤ 0` or all split records' PKO exhausted

### 1.5 Output Functions

#### `plan_e126_per_item(records, balance_cif=None) → dict`

**Returns**: `{record_id: {planning_item, reason, planned_quantity, unit_price, planned_cif}}`

One line per import record. **Split records report as one line** with blended PKO+Olive Oil rate.

**Blended Rate Calc** (for split records):
```
blended_rate = (pko_qty * pko_effective_rate + olive_qty * olive_effective_rate) / total_qty
```

#### `plan_e126_per_item_split(records, balance_cif=None) → dict`

**Returns**: `{record_id: [{planning_item, reason, planned_quantity, unit_price, planned_cif}, ...]}`

Multiple lines per import record. **Split records emit two lines** (one per PKO, one per Olive Oil) if qty > 0.

Example:
```
Record 2 (600 units, split):
  - {planning_item: "PALM KERNEL OIL - E126", planned_quantity: 250, unit_price: 1.75, planned_cif: 437.50}
  - {planning_item: "OLIVE OIL - E126", planned_quantity: 250, unit_price: 4.80, planned_cif: 1200.00}
```

#### `plan_e126(records, balance_cif=None) → dict`

**Returns aggregated plan result**:
```python
{
    "items": [
        {
            "norm": "E126",
            "planning_item_name": "NUTS - E126",
            "total_quantity": 1000,
            "unit_price": 3.00,  # effective rate
            "max_unit_price": 3.00,
            "planning_value": 3000.00,
            "num_source_records": 1,
            "unit_price_defined": true
        },
        # ... PKO, Olive Oil ...
    ],
    "classified": [ClassifiedRecord(...), ...],
    "exceptions": [...],  # unclassified records
    "missing_inputs": [],  # items with undefined prices (none for E126)
    "balance_cif": 50000,
    "total_planned": 8637.50,
    "wastage": 41362.50
}
```

### 1.6 Auto-Plan Pipeline (e126_auto_plan.py)

**Purpose**: Convert classification result into ready-to-save `LicenseItemPlan` rows.

**Key Differences from Pure Planning**:

1. **Group-Anchored**: Groups import items by `plan_group_key` (HSN + normalized description)
   - One group = one physical product (even if split across multiple DB rows after DGFT re-serialization)
   - Available quantity **summed** across group members
   - One plan is stored on the group's **representative** (lowest serial_number)

2. **Minimum Quantity Filter**: Groups with summed `available_quantity < 50` silently excluded

3. **Fixed-Once-Generated Split**:
   - Once a group's PKO/Olive Oil split is generated, it becomes a fixed commitment
   - On every subsequent Auto-Plan run, if group **still classifies as split-eligible**:
     - Check for existing PKO/Olive Oil `LicenseItemPlan` rows across **every group member**
     - If found: re-emit both PKO & Olive Oil at their **current** `remaining_quantity`/`remaining_cif_fc` (unchanged)
     - If not found: emit fresh 50%/50% split from current available_quantity
   - **Why**: Protects against silently double-counting a split when group members are re-serialized

4. **Quantity Rounding**: Floor all quantities to integer units before persistence

5. **CIF Recalc**: Recompute `planned_cif_fc = floor(qty) × unit_price` (never use un-floored qty)

### 1.7 Business Rule Decisions (E126)

| Decision | Rationale | Implementation |
|----------|-----------|-----------------|
| Split only on 50/50 when both signals present | Symmetrical across PKO/Olive Oil prices; simplest bookkeeping | `_rule_priority_2`: both signals → split |
| Per-record split, not license-wide | Each record's split is independent; available_qty already reflects real consumption | `_split_pko_olive_record(qty)`: 50% of **this qty** |
| Available_quantity is planning qty basis | Reflects current allocatable pool; self-corrects for consumed units | Never use original/total import qty |
| Fallback to 100% if only one signal | Business rule: must classify somewhere; can't drop a record | PKO-only → 100% PKO; Olive-only → 100% Olive |
| DFIA NIL / residual-balance **OUT OF SCOPE** | Not yet specified; no code here | Future phase |

---

## PART 2: E132 SEMANTICS EXTRACTION

### 2.1 Overview

**File(s)**: `/backend/apps/license/services/e132_plan.py` (primary), `/backend/apps/license/services/e132_auto_plan.py` (auto-execution)

**Norm Type**: E132 (Milk, Cheese, Oils, Nuts)

**Planning Items**: 6 categories
1. NUT & NUTS - E132 ($3.00/unit)
2. Yeast - E132 ($5.00/unit)
3. PKO - E132 ($1.80/unit)
4. RBD - E132 ($1.20/unit)
5. CHEESE CREAM BUTTER AND FATS - E132 ($5.50/unit)
6. Aluminium Foil - E132 ($4.50/unit)

**Special Features**:
- PKO/Cheese **40%/60% split** when both signals present on same import item
- Explicit Cheese override (highest precedence)
- RBD priority (blocks PKO/Cheese split)
- Strict Cheese signal (dairy code + vegetable + oil in description)

### 2.2 Classification Rules (Priority Order)

E132 uses an **ordered priority engine**: first matching rule wins.

#### Priority 1: NUT & NUTS - E132

**Function**: `_rule_nuts(hsn, desc) → reason | None`

**Match Conditions**:
- **AND** HSN code is 0802 (prefix match) **OR** description contains `0802` (word-boundary)
- **AND** description contains **word** `NUT` or `NUTS` (case-insensitive, word-boundary)

**Unit Price**: Fixed $3.00/unit

(Same as E126 Nuts)

#### Priority 2: Yeast - E132

**Function**: `_rule_yeast(hsn, desc) → reason | None`

**Match Conditions**:
- **AND** HSN is 2106 (prefix match) **OR** description contains `2106` (word-boundary)
- **AND** description contains word `YEAST` (case-insensitive, word-boundary)

**Examples**:
- `hs_code="210690"`, `description="Active Yeast"` → Yeast ✓
- `hs_code=None`, `description="2106 yeast preparation"` → Yeast ✓
- `hs_code="210690"`, `description="Dry Ingredients"` → None ✗

**Unit Price**: Fixed $5.00/unit

#### Priority 3: Palm Kernel Oil / RBD / Cheese (Sub-priority)

**Function**: `_rule_priority_3(hsn, desc) → (item_name, reason) | None`

**Sub-priority** (first match wins):
1. **Explicit Cheese override** (highest precedence)
2. **RBD Palmolein Oil**
3. **Split**: PKO + strict Cheese both present
4. **PKO alone**: 1513 signal without strict Cheese
5. **Cheese alone**: Strict Cheese signal without 1513

##### Explicit Cheese Override

**Function**: `_is_explicit_cheese(desc) → bool`

**Match**: Description contains **all three** (case-insensitive):
- `"cheese"`
- `"vegetable"`
- `"oil"`

**When Matched**:
- Classification: `CHEESE CREAM BUTTER AND FATS - E132`
- Quantity: 100% of available_quantity
- Reason: `"Description contains 'CHEESE', 'VEGETABLE' and 'OIL' (explicit override)"`
- **Never splits**, never subjected to wastage-rebalance

**Example**:
- `description="Cheese with vegetable oil blended"` → Cheese (explicit override) ✓

##### RBD Detection (`_is_rbd`)

**HSN 1510** (prefix match) **OR** description contains `1510` (word-boundary)

**When Matched**:
- Classification: `RBD - E132`
- Quantity: 100% of available_quantity
- Unit Price: $1.20/unit
- Reason: `"HSN/desc=1510"`
- **Blocks all split logic** (PKO signal ignored if 1510 also present)

**Example**:
- `hs_code="15101100"` → RBD ✓
- `description="refined palm 1510 oil"` → RBD ✓

##### Strict Cheese Detection (`_is_cheese_strict`)

**Match Conditions**:
- **AND** HSN is one of (0401, 0405, 0406) (prefix match) **OR** description contains any (word-boundary)
- **AND** description contains word `"vegetable"`
- **AND** description contains word `"oil"`

**Examples**:
- `hs_code="04011000"`, `description="Butter with vegetable oil"` → Strict Cheese signal ✓
- `hs_code="9999"`, `description="cream 0405 vegetable oil blend"` → Strict Cheese signal ✓
- `hs_code="04011000"`, `description="Butter only"` → Not strict Cheese (no "vegetable"/"oil") ✗

##### PKO Detection (`_is_pko_signal`)

**HSN 1513** (prefix match) **OR** description contains `1513` (word-boundary)

(Same as E126)

##### Split Condition

When **both** 1513 **and strict Cheese** signals present:
- Internal classification: `__VEG_OIL_SPLIT__` (never shown to user)
- Split target: **40% PKO, 60% Cheese** of **this record's current available_quantity**
- Reason: `"HSN/desc=1513 AND strict Cheese signal — 40% PKO / 60% Cheese split"`
- Value gain (Cheese > PKO): $5.50 - $1.80 = $3.70/unit (used in wastage rebalance)

**Example**:
- `hs_code="15132900"`, `description="Oil 0401 vegetable"` (has 1513 + 0401 + vegetable + oil) → Split (40% PKO, 60% Cheese)
- Available qty: 1000 units → PKO gets 400, Cheese gets 600

##### PKO-Only Condition

When **only** 1513 signal present (no strict Cheese):
- Classification: `PKO - E132`
- Quantity: 100% of available_quantity
- Unit Price: $1.80/unit

##### Cheese-Only Condition

When **only strict Cheese** signal present (no 1513):
- Classification: `CHEESE CREAM BUTTER AND FATS - E132`
- Quantity: 100% of available_quantity
- Unit Price: $5.50/unit

#### Priority 4: Aluminium Foil - E132

**Function**: `_rule_aluminium(hsn, desc) → reason | None`

**Match Conditions** (any match):
1. HSN is 7607 (exact, no prefix) → `"HSN=7607"`
2. Description contains `7607` (word-boundary) → `"Description contains '7607'"`
3. Description contains `"aluminium foil"` or `"aluminum foil"` (case-insensitive) → `"Description contains 'aluminium foil'"`

**Examples**:
- `hs_code="7607190090"` → Aluminium ✓
- `description="foil laminate under 7607 code"` → Aluminium ✓
- `description="Aluminium Foil Roll 200m"` → Aluminium ✓
- `description="PP/foil laminate packing"` → Aluminium (if contains "aluminium foil") ✓

**Unit Price**: Fixed $4.50/unit

**Reason**: Aluminium foil packing material often declared under non-7607 HSN; description is fallback

#### No Match

If no rule fires → `(None, None)` → exception report

### 2.3 Aggregation & Waterfall Allocation

**Same algorithm as E126** (see §1.4), but applied to E132 items in PLANNING_ORDER:

```
Nuts → Yeast → PKO → RBD → Cheese → Aluminium
```

#### Wastage-Reduction Rebalance (E132)

If waterfall leaves remaining balance unused, shift quantity from PKO → Cheese **on split records only**:
- **Why**: Cheese ($5.50) > PKO ($1.80), so shifting quantity increases total planned value without increasing total planned quantity
- **Value gain per unit shifted**: $5.50 - $1.80 = $3.70
- **Only on split records**: Non-split PKO records unaffected
- **Deterministic & idempotent**: Each split record shifted once, closed-form calc: `min(split_record.pko_qty, remaining_balance / $3.70)`

**No other buckets touched** (Nuts, Yeast, RBD, Aluminium finalized by waterfall)

### 2.4 Output Functions

Same structure as E126 (§1.5):

- `plan_e132_per_item()` → one line per record, split records report blended rate
- `plan_e132_per_item_split()` → multiple lines per record, split records emit PKO + Cheese lines
- `plan_e132()` → aggregated plan result

### 2.5 Auto-Plan Pipeline

Same as E126 (§1.6), except:
- **Fixed split**: PKO/Cheese (not PKO/Olive Oil)
- `_SPLIT_TARGET_NAMES = (PKO, CHEESE)`
- Min quantity: 50 units

---

## PART 3: DB RULE MIGRATION DESIGN

### 3.1 Architecture Overview

**Current State**: E126 & E132 use hard-coded classification + allocation functions in `e*_plan.py`

**Target State**: Fully data-driven rules stored in `SionPlanningRule` + `SionPlanningAction` with generic execution via `CanonicalPlanningService`

**New Models**:
- `SionPlanningRule`: One row per classification rule (e.g., "E126 Nuts", "E126 PKO/Olive Split")
- `SionPlanningProfile`: One per norm, references all active rules in execution order
- `SionPlanningAction`: Pipeline stages (MATCH, ALLOCATE, SPLIT, REBALANCE, etc.)

### 3.2 Expression Syntax (SionPlanningRule)

**Safe, Data-Driven Evaluator** (no Python/SQL eval):

```json
{
  "operator": "AND" | "OR" | "NOT",
  "conditions": [
    {
      "field": "hs_code" | "description" | "...",
      "operator": "eq" | "contains" | "starts_with" | "in" | "word_contains" | "...",
      "value": "string" | ["array"] | {...}
    },
    { ... }
  ]
}
```

**Available Fields**:
- `hs_code`: HSN digits (normalized, no punctuation)
- `description`: Lowercased text (normalized whitespace)
- `hs_code_original`: Raw HSN (for debugging)
- `description_original`: Raw description

**Available Operators**:
- `eq`, `ne`, `contains`, `not_contains`, `starts_with`, `not_starts_with`
- `word_contains` (word-boundary match, e.g., "nut" ≠ "peanut")
- `in` (array membership)

### 3.3 E126 Rule Design

#### Rule 1: E126 Nuts (Priority 1)

```json
{
  "sion": "E126",
  "stable_key": "e126_rule_nuts",
  "name": "E126 - NUTS (0802 + 'nut'/'nuts' word)",
  "version": 1,
  "priority": 1,
  "max_unit_price": "3.00",
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          {
            "field": "hs_code",
            "operator": "starts_with",
            "value": "0802"
          },
          {
            "field": "description",
            "operator": "word_contains",
            "value": "0802"
          }
        ]
      },
      {
        "operator": "OR",
        "conditions": [
          {
            "field": "description",
            "operator": "word_contains",
            "value": "nut"
          },
          {
            "field": "description",
            "operator": "word_contains",
            "value": "nuts"
          }
        ]
      }
    ]
  },
  "execution_output": "NUTS - E126"
}
```

#### Rule 2: E126 PKO/Olive Split (Priority 2a)

```json
{
  "sion": "E126",
  "stable_key": "e126_rule_pko_olive_split",
  "name": "E126 - PKO/Olive Split (1513 + 1509/1500/1510)",
  "version": 1,
  "priority": 2,
  "max_unit_price": null,  // Split: no single price
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          { "field": "hs_code", "operator": "starts_with", "value": "1513" },
          { "field": "description", "operator": "word_contains", "value": "1513" }
        ]
      },
      {
        "operator": "OR",
        "conditions": [
          { "field": "hs_code", "operator": "starts_with", "value": "1509" },
          { "field": "description", "operator": "contains", "value": "1500" },
          { "field": "description", "operator": "contains", "value": "1509" },
          { "field": "description", "operator": "contains", "value": "1510" }
        ]
      }
    ]
  },
  "execution_output": "__SPLIT__:PKO - E126,OLIVE OIL - E126:50,50"
}
```

#### Rule 3: E126 PKO Alone (Priority 2b)

```json
{
  "sion": "E126",
  "stable_key": "e126_rule_pko_alone",
  "name": "E126 - PKO Alone (1513 without Olive signal)",
  "version": 1,
  "priority": 3,
  "max_unit_price": "1.80",
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          { "field": "hs_code", "operator": "starts_with", "value": "1513" },
          { "field": "description", "operator": "word_contains", "value": "1513" }
        ]
      },
      {
        "operator": "NOT",
        "conditions": [
          {
            "operator": "OR",
            "conditions": [
              { "field": "hs_code", "operator": "starts_with", "value": "1509" },
              { "field": "description", "operator": "contains", "value": "1500" },
              { "field": "description", "operator": "contains", "value": "1509" },
              { "field": "description", "operator": "contains", "value": "1510" }
            ]
          }
        ]
      }
    ]
  },
  "execution_output": "PALM KERNEL OIL - E126"
}
```

#### Rule 4: E126 Olive Oil Alone (Priority 2c)

```json
{
  "sion": "E126",
  "stable_key": "e126_rule_olive_alone",
  "name": "E126 - Olive Oil Alone (1509/1500/1510 without 1513)",
  "version": 1,
  "priority": 4,
  "max_unit_price": "5.00",
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          { "field": "hs_code", "operator": "starts_with", "value": "1509" },
          { "field": "description", "operator": "contains", "value": "1500" },
          { "field": "description", "operator": "contains", "value": "1509" },
          { "field": "description", "operator": "contains", "value": "1510" }
        ]
      },
      {
        "operator": "NOT",
        "conditions": [
          {
            "operator": "OR",
            "conditions": [
              { "field": "hs_code", "operator": "starts_with", "value": "1513" },
              { "field": "description", "operator": "word_contains", "value": "1513" }
            ]
          }
        ]
      }
    ]
  },
  "execution_output": "OLIVE OIL - E126"
}
```

### 3.4 E132 Rule Design

#### Rule 1: E132 Nuts (Priority 1)

```json
{
  "sion": "E132",
  "stable_key": "e132_rule_nuts",
  "name": "E132 - NUT & NUTS (0802 + 'nut'/'nuts' word)",
  "version": 1,
  "priority": 1,
  "max_unit_price": "3.00",
  "unit": "unit",
  "expression": { ... }  // Same as E126 Nuts
}
```

#### Rule 2: E132 Yeast (Priority 2)

```json
{
  "sion": "E132",
  "stable_key": "e132_rule_yeast",
  "name": "E132 - Yeast (2106 + 'yeast' word)",
  "version": 1,
  "priority": 2,
  "max_unit_price": "5.00",
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          { "field": "hs_code", "operator": "starts_with", "value": "2106" },
          { "field": "description", "operator": "word_contains", "value": "2106" }
        ]
      },
      { "field": "description", "operator": "word_contains", "value": "yeast" }
    ]
  },
  "execution_output": "Yeast - E132"
}
```

#### Rule 3: E132 Explicit Cheese Override (Priority 3a)

```json
{
  "sion": "E132",
  "stable_key": "e132_rule_cheese_explicit",
  "name": "E132 - Cheese Explicit Override (cheese + vegetable + oil)",
  "version": 1,
  "priority": 3,
  "max_unit_price": "5.50",
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      { "field": "description", "operator": "word_contains", "value": "cheese" },
      { "field": "description", "operator": "word_contains", "value": "vegetable" },
      { "field": "description", "operator": "word_contains", "value": "oil" }
    ]
  },
  "execution_output": "CHEESE CREAM BUTTER AND FATS - E132"
}
```

#### Rule 4: E132 RBD (Priority 3b)

```json
{
  "sion": "E132",
  "stable_key": "e132_rule_rbd",
  "name": "E132 - RBD Palmolein (1510)",
  "version": 1,
  "priority": 4,
  "max_unit_price": "1.20",
  "unit": "unit",
  "expression": {
    "operator": "OR",
    "conditions": [
      { "field": "hs_code", "operator": "starts_with", "value": "1510" },
      { "field": "description", "operator": "word_contains", "value": "1510" }
    ]
  },
  "execution_output": "RBD - E132"
}
```

#### Rule 5: E132 PKO/Cheese Split (Priority 3c)

```json
{
  "sion": "E132",
  "stable_key": "e132_rule_pko_cheese_split",
  "name": "E132 - PKO/Cheese Split (1513 + strict Cheese)",
  "version": 1,
  "priority": 5,
  "max_unit_price": null,  // Split: no single price
  "unit": "unit",
  "expression": {
    "operator": "AND",
    "conditions": [
      {
        "operator": "OR",
        "conditions": [
          { "field": "hs_code", "operator": "starts_with", "value": "1513" },
          { "field": "description", "operator": "word_contains", "value": "1513" }
        ]
      },
      {
        "operator": "AND",
        "conditions": [
          {
            "operator": "OR",
            "conditions": [
              { "field": "hs_code", "operator": "starts_with", "value": "0401" },
              { "field": "hs_code", "operator": "starts_with", "value": "0405" },
              { "field": "hs_code", "operator": "starts_with", "value": "0406" },
              { "field": "description", "operator": "word_contains", "value": "0401" },
              { "field": "description", "operator": "word_contains", "value": "0405" },
              { "field": "description", "operator": "word_contains", "value": "0406" }
            ]
          },
          { "field": "description", "operator": "word_contains", "value": "vegetable" },
          { "field": "description", "operator": "word_contains", "value": "oil" }
        ]
      }
    ]
  },
  "execution_output": "__SPLIT__:PKO - E132,CHEESE CREAM BUTTER AND FATS - E132:40,60"
}
```

#### Rule 6: E132 PKO Alone (Priority 3d)

#### Rule 7: E132 Cheese Alone (Priority 3e)

#### Rule 8: E132 Aluminium Foil (Priority 4)

(Similar structure to E126; see pattern)

### 3.5 SionPlanningAction Configuration

**Shared across E126 & E132**:

#### Action 1: MATCH Rules

```json
{
  "stable_key": "match_rules",
  "action_type": "MATCH",
  "priority": 1,
  "config": {
    "rule_selection_mode": "PRIORITY_ORDER",
    "skip_unmatched": true
  }
}
```

#### Action 2: WATERFALL ALLOCATE

```json
{
  "stable_key": "waterfall_allocate",
  "action_type": "ALLOCATE",
  "priority": 2,
  "config": {
    "allocation_type": "WATERFALL",
    "order": "PRIORITY",
    "cap_to_balance": true,
    "cap_field": "license_balance_cif"
  }
}
```

#### Action 3: SPLIT (if applicable)

```json
{
  "stable_key": "apply_split",
  "action_type": "SPLIT",
  "priority": 3,
  "config": {
    "split_records_only": true,
    "preserve_existing": true
  }
}
```

#### Action 4: REBALANCE WASTAGE

```json
{
  "stable_key": "rebalance_wastage",
  "action_type": "REBALANCE",
  "priority": 4,
  "config": {
    "rebalance_mode": "PKO_TO_TARGET",
    "target_item": "OLIVE OIL - E126" | "CHEESE CREAM BUTTER AND FATS - E132",
    "source_item": "PALM KERNEL OIL - E126" | "PKO - E132"
  }
}
```

### 3.6 Migration Strategy: Rules → DB

**Total Rules Required**:

| Norm | Nuts | Yeast | RBD | Explicit Cheese | Split | PKO Alone | Cheese Alone | Aluminium | Total |
|------|------|-------|-----|-----------------|-------|----------|--------------|-----------|-------|
| E126 | 1    | —     | —   | —               | 1     | 1        | 1            | —         | 4     |
| E132 | 1    | 1     | 1   | 1               | 1     | 1        | 1            | 1         | 8     |
| **Total** | | | | | | | | | **12** |

**Migration Complexity**:

| Component | Complexity | Notes |
|-----------|-----------|-------|
| SionPlanningRule rows | Low (12 static rows) | One-time creation; stable_keys never change |
| Expression JSON | Medium (54 conditions total) | Systematic translation of Python logic → JSON predicates |
| SionPlanningAction pipeline | Low (4 actions) | Reusable template for all norms |
| SionPlanningProfile config | Low | One profile per norm, references all rules + actions |
| CanonicalPlanningService integration | High | Must handle split logic, wastage rebalance, per-record context |
| Test migration | Medium | Golden test cases to verify DB rules match hard-coded output |

---

## PART 4: GOLDEN TEST CASES

### 4.1 E126 Golden Case: 5-Item License with Split

**Input License**: E126 export, Balance CIF = $50,000

| Item ID | HSN | Description | Available Qty |
|---------|-----|-------------|---------------|
| 1 | 0802 | Cashew Nuts Grade A | 1000 |
| 2 | 1513 | Palm Oil 1509 Blend | 600 |
| 3 | 1513 | Pure PKO | 400 |
| 4 | 1509 | Extra Virgin Olive Oil | 300 |
| 5 | 9999 | Unknown Item | 200 |

**Expected Classification**:

| Item | Planning Item | Reason | Qty |
|------|---------------|--------|-----|
| 1 | NUTS - E126 | HSN/desc=0802 AND nut word | 1000 |
| 2 | **SPLIT** | 1513 + 1509 signal | 600 (300 PKO, 300 Olive) |
| 3 | PKO - E126 | HSN/desc=1513 | 400 |
| 4 | OLIVE OIL - E126 | HSN starts 1509 | 300 |
| 5 | None | No match | 0 |

**Aggregation** (pre-waterfall):

| Item | Qty | Count |
|------|-----|-------|
| NUTS | 1000 | 1 |
| PKO | 300+400=700 | 2 |
| OLIVE OIL | 300+300=600 | 2 |

**Waterfall Allocation** (capping at $50,000):

```
remaining = $50,000

NUTS: 1000 × $3.00 = $3,000 → allocated=$3,000, eff_rate=$3.00, remaining=$47,000
PKO: 700 × $1.80 = $1,260 → allocated=$1,260, eff_rate=$1.80, remaining=$45,740
OLIVE OIL: 600 × $5.00 = $3,000 → allocated=$3,000, eff_rate=$5.00, remaining=$42,740
```

**Wastage Rebalance** ($3.20 gain per unit: Olive $5.00 - PKO $1.80):

```
split_records = [Item 2]
remaining_balance = $42,740

Item 2 split: {PKO: 300, OLIVE: 300}
  shift = min(300, $42,740 / $3.20) = min(300, 13,356) = 300
  → PKO now 0, OLIVE now 600
  → PKO bucket: 700 - 300 = 400, value = $400×$1.80 = $720
  → OLIVE bucket: 600 + 300 = 900, value = $3,000 + $300×$5.00 = $4,500
  → remaining = $42,740 - $300×$3.20 = $42,740 - $960 = $41,780
```

**Final Result**:

```python
{
  "items": [
    {
      "norm": "E126",
      "planning_item_name": "NUTS - E126",
      "total_quantity": 1000,
      "unit_price": 3.00,
      "max_unit_price": 3.00,
      "planning_value": 3000.00,
      "num_source_records": 1,
      "unit_price_defined": true
    },
    {
      "norm": "E126",
      "planning_item_name": "PALM KERNEL OIL - E126",
      "total_quantity": 400,  # After rebalance: 700 - 300 = 400
      "unit_price": 1.80,
      "max_unit_price": 1.80,
      "planning_value": 720.00,  # 400 × 1.80
      "num_source_records": 2,
      "unit_price_defined": true
    },
    {
      "norm": "E126",
      "planning_item_name": "OLIVE OIL - E126",
      "total_quantity": 900,  # After rebalance: 600 + 300 = 900
      "unit_price": 5.00,
      "max_unit_price": 5.00,
      "planning_value": 4500.00,  # 900 × 5.00
      "num_source_records": 2,
      "unit_price_defined": true
    }
  ],
  "classified": [
    ClassifiedRecord(1, 0802, "Cashew Nuts Grade A", 1000, "NUTS - E126", "..."),
    ClassifiedRecord(2, 1513, "Palm Oil 1509 Blend", 600, "PALM KERNEL OIL - E126 / OLIVE OIL - E126", "..."),
    ClassifiedRecord(3, 1513, "Pure PKO", 400, "PALM KERNEL OIL - E126", "..."),
    ClassifiedRecord(4, 1509, "Extra Virgin Olive Oil", 300, "OLIVE OIL - E126", "..."),
    ClassifiedRecord(5, 9999, "Unknown Item", 200, None, None)
  ],
  "exceptions": [
    ClassifiedRecord(5, 9999, "Unknown Item", 200, None, None)
  ],
  "missing_inputs": [],
  "balance_cif": Decimal("50000"),
  "total_planned": Decimal("8220.00"),  # 3000 + 720 + 4500
  "wastage": Decimal("41780.00")
}
```

### 4.2 E132 Golden Case: 6-Item License with Split & RBD

**Input License**: E132 export, Balance CIF = $80,000

| Item ID | HSN | Description | Available Qty |
|---------|-----|-------------|---------------|
| 1 | 0802 | Brazil Nuts | 500 |
| 2 | 2106 | Yeast Preparation | 300 |
| 3 | 1510 | RBD Palmolein Oil | 400 |
| 4 | 1513 0401 | Oil with Cheese vegetable blend | 800 |
| 5 | 1513 | Pure PKO | 500 |
| 6 | 0401 | Butter vegetable oil | 200 |

**Expected Classification**:

| Item | Planning Item | Reason | Qty |
|------|---------------|--------|-----|
| 1 | NUT & NUTS - E132 | 0802 + nut word | 500 |
| 2 | Yeast - E132 | 2106 + yeast word | 300 |
| 3 | RBD - E132 | 1510 HSN | 400 |
| 4 | **SPLIT** | 1513 + strict Cheese (0401+veg+oil) | 800 (320 PKO, 480 Cheese) |
| 5 | PKO - E132 | 1513 alone | 500 |
| 6 | CHEESE - E132 | 0401+vegetable+oil | 200 |

**Aggregation**:

| Item | Qty | Count |
|------|-----|-------|
| NUT & NUTS | 500 | 1 |
| Yeast | 300 | 1 |
| PKO | 320+500=820 | 2 |
| RBD | 400 | 1 |
| CHEESE | 480+200=680 | 2 |
| ALUMINIUM | 0 | 0 |

**Waterfall Allocation** (capping at $80,000):

```
remaining = $80,000

NUT & NUTS: 500 × $3.00 = $1,500 → $1,500, remaining=$78,500
Yeast: 300 × $5.00 = $1,500 → $1,500, remaining=$77,000
PKO: 820 × $1.80 = $1,476 → $1,476, remaining=$75,524
RBD: 400 × $1.20 = $480 → $480, remaining=$75,044
CHEESE: 680 × $5.50 = $3,740 → $3,740, remaining=$71,304
ALUMINIUM: 0 → $0
```

**Wastage Rebalance** ($3.70 gain per unit: Cheese $5.50 - PKO $1.80):

```
split_records = [Item 4]
remaining_balance = $71,304

Item 4 split: {PKO: 320, CHEESE: 480}
  shift = min(320, $71,304 / $3.70) = min(320, 19,271) = 320
  → PKO now 0, CHEESE now 800
  → PKO bucket: 820 - 320 = 500, value = $500×$1.80 = $900
  → CHEESE bucket: 680 + 320 = 1000, value = $3,740 + $320×$5.50 = $5,500
  → remaining = $71,304 - $320×$3.70 = $71,304 - $1,184 = $70,120
```

**Final Result**:

```python
{
  "items": [
    {"norm": "E132", "planning_item_name": "NUT & NUTS - E132", "total_quantity": 500, "unit_price": 3.00, "planning_value": 1500.00, ...},
    {"norm": "E132", "planning_item_name": "Yeast - E132", "total_quantity": 300, "unit_price": 5.00, "planning_value": 1500.00, ...},
    {"norm": "E132", "planning_item_name": "PKO - E132", "total_quantity": 500, "unit_price": 1.80, "planning_value": 900.00, ...},
    {"norm": "E132", "planning_item_name": "RBD - E132", "total_quantity": 400, "unit_price": 1.20, "planning_value": 480.00, ...},
    {"norm": "E132", "planning_item_name": "CHEESE CREAM BUTTER AND FATS - E132", "total_quantity": 1000, "unit_price": 5.50, "planning_value": 5500.00, ...},
  ],
  "total_planned": Decimal("9880.00"),
  "wastage": Decimal("70120.00")
}
```

---

## PART 5: COMPLEXITY ESTIMATE & EFFORT

### 5.1 Migration Breakdown

| Phase | Task | Complexity | Est. Hours | Notes |
|-------|------|-----------|-----------|-------|
| 1. Schema | Add SionPlanningRule/Action/Profile migrations | Low | 1 | Already exist; no changes needed |
| 2. Rules | Create 12 SionPlanningRule rows in seed migration | Low | 3 | JSON expression translation; systematic |
| 3. Engine | Extend CanonicalPlanningService for splits | High | 8 | Handle `__SPLIT__` output, preserve balance tracking |
| 4. Actions | Implement SPLIT, REBALANCE action types | High | 10 | Rebalance logic: PKO→target with closed-form shift calc |
| 5. Tests | Golden cases: hard-coded vs DB rule output | Medium | 6 | Per-item verification; balance conservation checks |
| 6. Integration | Route E126/E132 to new engine, deprecate old | Medium | 4 | Feature flag? Parallel run? Cutover plan |
| **Total** | | | **32 hours** | ~1 week full-time |

### 5.2 Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Split logic mismatch | 🔴 High | Golden cases + parallel testing (old vs new) |
| Balance overflow | 🔴 High | Closed-form wastage rebalance guarantees convergence |
| Per-record vs group semantics | 🔴 High | Auto-Plan: verify group representative logic preserved |
| Decimal precision (float→Decimal) | 🟡 Medium | Test harness for CIF rounding edge cases |
| Performance (rule evaluation per item) | 🟡 Medium | Benchmark simple rules; optimize field normalization |
| Backwards compatibility | 🟡 Medium | Preserve existing LicenseItemPlan rows during cutover |

### 5.3 Success Criteria

- [ ] All 12 SionPlanningRule rows created & tested
- [ ] Golden case 1 (E126 split): DB rules match hard-coded within $0.01
- [ ] Golden case 2 (E132 split + RBD): DB rules match hard-coded within $0.01
- [ ] Wastage rebalance converges in closed form (no iterative drift)
- [ ] Auto-Plan: existing split preservation logic works end-to-end
- [ ] Performance: rule evaluation < 100ms per item
- [ ] No regression: all existing E126/E132 tests pass with new engine

---

## PART 6: IMPLEMENTATION ROADMAP

### Phase 6.1: Rule Creation (Week 1)

1. Create seed migration `0011_seed_e126_e132_planning_rules.py`
2. Define all 12 SionPlanningRule rows in code
3. Validate JSON expressions with safe evaluator
4. Test rule matching against golden cases (hard-coded functions still running)

### Phase 6.2: Action Pipeline (Week 2)

1. Extend CanonicalPlanningService:
   - Add split handling (expand `__SPLIT__` into two output items)
   - Add wastage rebalance stage
   - Add quantity floor rounding
2. Implement SionPlanningAction types:
   - `SPLIT`: Expand split records
   - `REBALANCE`: PKO→target shifting
3. Create SionPlanningProfile for E126 & E132

### Phase 6.3: Testing & Validation (Week 3)

1. Unit tests: golden cases (E126 + E132)
2. Integration tests: end-to-end with Auto-Plan
3. Regression: all existing tests pass
4. Performance: rule eval benchmarks
5. Data consistency: balance conservation checks

### Phase 6.4: Cutover (Week 4)

1. Feature flag: route E126/E132 to new engine (enabled for staging)
2. Production gradual rollout (10% → 50% → 100%)
3. Monitor: license plan generation logs
4. Rollback plan: feature flag to old engine

---

## PART 7: APPENDIX: REFERENCE MATERIALS

### A. Hard-Coded vs Data-Driven Mapping

| Hard-Coded | Data-Driven | Location |
|-----------|------------|----------|
| `_rule_nuts()` | SionPlanningRule (E126 Nuts, priority 1) | `stable_key=e126_rule_nuts` |
| `_rule_priority_2()` | SionPlanningRule (E126 Split/PKO/Olive, pri 2-4) | `stable_key=e126_rule_pko_*` |
| `classify_e126_record()` | SionRuleEngine.evaluate() | Engine evaluates all rules in priority |
| `_allocate_buckets()` | SionPlanningAction (ALLOCATE) | `action_type=ALLOCATE` |
| `_rebalance_pko_olive_wastage()` | SionPlanningAction (REBALANCE) | `action_type=REBALANCE` |
| `plan_e126_per_item_split()` | CanonicalPlanningService.execute() | Aggregates rule matches + actions |

### B. Expression Operator Reference

```
Comparison:
  - eq, ne: string equality
  - contains, not_contains: substring (case-sensitive)
  - starts_with, not_starts_with: prefix
  - word_contains: word-boundary match (case-sensitive, normalized text)
  - in: array membership

Logic:
  - AND: all conditions true
  - OR: any condition true
  - NOT: negate one condition
```

### C. Field Definitions

```json
{
  "hs_code": "HSN digits only (normalized: 0802, 150910, 7607)",
  "description": "Lowercased text, normalized whitespace",
  "available_qty": "Item's available quantity (Decimal)",
  "license_balance_cif": "Licence Balance CIF ($)",
  "item_key": "Group key (HSN + normalized description)"
}
```

---

## Summary

**E126 Semantics**: 3 planning items, 1 split (50/50 PKO/Olive Oil), 4 matching rules, waterfall + wastage rebalance

**E132 Semantics**: 6 planning items, 1 split (40/60 PKO/Cheese), 8 matching rules, explicit Cheese override, RBD priority

**DB Migration**: 12 SionPlanningRule rows + 4 SionPlanningAction stages, 32 hrs effort, 3 golden test cases

**Risk**: High complexity in split & rebalance logic; medium performance impact; manageable with feature flag cutover

**Success Criteria**: Golden cases match within $0.01, balance conservation guaranteed, no regression
