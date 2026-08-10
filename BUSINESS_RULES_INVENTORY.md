# License Manager: Business Rules and Calculations Inventory

**Document Status**: Analysis Only (No Code Changes)  
**Last Updated**: 2026-08-10  
**Coverage**: V2 branch (feature branch with A3627 auto-plan engine)

---

## 1. BALANCE CALCULATIONS

### 1.1 Two Balance Engines (Intentional Divergence)

The system implements **two separate, intentionally divergent balance formulas**:

#### A. Customs Balance (Legacy/Comparison Only)
**Formula**: `Credit - (ALL BOE Debit + Allotment)` including hidden rows

**Calculation Path**: `LicenseBalanceCalculator.calculate_customs_balance()`
- **Credit**: `calculate_credit()` — Sum of `LicenseExportItemModel.cif_fc` (all export items)
- **BOE Debit**: `calculate_boe_debit_total()` + `calculate_hidden_boe_debit_total()` — ALL `RowDetails` where `transaction_type='D'` (DEBIT), unconditional raw `cif_fc`
- **Allotment**: `calculate_allotment()` — BOE-unlinked `AllotmentItems` only
- **Floor**: Minimum 0; quantized to 2 decimal places
- **Use**: Customs Ledger only; NOT used for business balance decisions

#### B. Financial Balance (Authoritative Business Balance)
**Formula**: `Opening Balance + Purchase Credit - Sale Debit - Our BOE Debit - Outstanding Allotments`

**Calculation Path**: `LicenseBalanceCalculator.calculate_financial_balance()`
```
balance = opening_balance + purchase_credit - sale_debit - boe_debit - allotment
```

**Components**:
1. **Opening Balance** (3-way gate: `calculate_opening_balance()`)
   - If hidden BOEs exist: `Credit - hidden_total - purchase_credit` (Previous Owner Utilisation)
   - Else if purchase trades exist: `0` (licence purchased, story told via trading history)
   - Else: `Credit` (untouched original face value)

2. **Purchase Credit**: `calculate_purchase_credit()` — Sum `LicenseTradeLine.cif_fc` where `direction='PURCHASE'`
   - Note: Added UNCONDITIONALLY, even if subtracted from opening balance (not a bug; Purchase re-enters as independent event)

3. **Sale Debit**: `calculate_trade()` — Sum `LicenseTradeLine.cif_fc` where `direction='SALE'`

4. **Our BOE Debit**: `calculate_debit()` — **ALLOCATION-NETTED** (see section 1.3)
   - NOT `calculate_boe_debit_total()` (raw, unconditional)
   - Subtracts only MATCHED/ALLOCATED amounts, leaving unmatched remainder visible
   - Excludes hidden rows via `get_debit_rows()`

5. **Outstanding Allotments**: `calculate_allotment()` — BOE-unlinked allotments only

**Floor**: Minimum 0; quantized to 2 decimal places
**Use**: Primary business metric; read by all consumers (`list_views`, `dashboard`, cached field, exports)

---

### 1.2 Credit Calculation (Unchanged Across Both Engines)

**Formula**: `SUM(LicenseExportItemModel.cif_fc)` for the licence

**Calculation**: `LicenseBalanceCalculator.calculate_credit(license_obj)`

**Source**: `apps/license/models/core.py` → `LicenseExportItemModel.cif_fc` (CIF in foreign currency)

**Precision**: 2 decimal places (quantized via `quantize_2dp()`)

**Properties**:
- Same for both Customs and Financial engines
- Coalesced to 0 if no export items
- Includes all export-side items regardless of condition_type/restrictions

---

### 1.3 Allocation-Driven Debit Calculation (Phase A — Partial Allocation Ledger)

**Concept**: Instead of binary "BOE excluded/not excluded", calculate per-row unmatched remainder.

**Formula (per BOE row)**: 
```
contributed = max(cif_fc - matched, 0)
where matched = min(cif_fc, allocated + linked_excluded)
```

**Calculation Path**: `LicenseBalanceCalculator.calculate_debit()` → `get_debit_rows()`

**Annotations on each RowDetails row**:
1. **allocated**: Sum of `InvoiceBOEAllocation.allocated_cif_fc` where `status='ACTIVE', is_current=True`
2. **linked_excluded**: Full `cif_fc` if:
   - BOE is "represented by invoice" (via legacy trade.boes tag), AND
   - Row itself has NO active allocation (`allocated = 0`)
3. **matched**: `min(cif_fc, allocated + linked_excluded)`
4. **contributed**: `max(cif_fc - matched, 0)` (the unmatched portion)

**Total Debit**: `SUM(contributed)` across all DEBIT rows

**Exclusion Logic** (`_linked_boe_debit_exclusion_case`):
- A BOE is "represented by invoice" if **ANY** of its debit rows has an `InvoiceBOEAllocation` OR the BOE is tagged to a SALE trade via legacy `trade.boes` M2M
- Once ANY row of a BOE is represented, EVERY OTHER row of the same physical BOE with no allocation of its own (`allocated=0`) also gets its full `cif_fc` excluded
- **Known trade-off**: A BOE debiting 2 items; if represented on one, both items' full debit is excluded (even item with no relationship to matched invoice)
- **Rationale**: Explicit product decision, not oversight; see Financial Ledger BOE Invoice Status Consistency spec

**Hidden Row Handling**:
- `get_debit_rows()` default excludes hidden rows via `exclude_hidden(qs)`
- Hidden rows excluded via audit-trail check: `annotate_and_exclude_hidden()` with `hidden_only=True`
- Sets `RowDetails.is_hidden=True` for previous-owner BOEs

**Test Coverage**: `apps/reconciliation/tests/test_allocation_service.py`
- `InvoiceBOEAllocationTests.test_partial_allocation_leaves_correct_unmatched_remainder` — demonstrates partial allocation does NOT suppress unmatched remainder

---

### 1.4 Allotment Calculation

**Formula**: `SUM(AllotmentItems.cif_fc)` for BOE-unlinked allotments only

**Calculation Path**: `LicenseBalanceCalculator.calculate_allotment(license_obj)`

**Query Scope**:
```sql
AllotmentItems WHERE
  item__license = license_obj AND
  allotment__bill_of_entry IS NULL  -- NOT linked to any BOE
```

**Precision**: 2 decimal places

**Key Rule**: Once an allotment is linked to a BOE (via `BOEAllotmentAllocation`), it no longer contributes to outstanding allotment total
- Transition: Recorded in `BOEAllotmentAllocation` ledger (see section 5.2)
- Similar to invoice-BOE pairing; independent consumption tracks

---

### 1.5 Item-Level Balance (Restricted Availability)

**Concept**: Some items are condition-restricted (2%, 3%, 5%, 10% pools); available value = min(pool_remaining, license_balance)

**Calculation Path**: `LicenseDetailsModel.get_restriction_balances()` → `compute_condition_pools()`

**Pool Formula**:
```
pool = condition_pct * license_credit
used = SUM(debit + allotment + trade) for items in this condition group
remaining = max(pool - used, 0)
available_value = min(remaining, license_balance_cif)
```

**Condition Types**:
- `"N%"` (e.g., "2%", "3%", "5%", "10%"): Creates shared pool
- `""` (empty/null): No restriction, available_value = license_balance
- `"AU"` (Actual User): Non-transferable but usable to license_balance
- Other values: Treated as empty (no restriction)

**Used Components** (`used` in pool calculation):
1. **Debited**: `RowDetails.cif_fc` where item matches condition group, `transaction_type='D'`, hidden-excluded
2. **Allotted**: `AllotmentItems.cif_fc` where item matches, `bill_of_entry IS NULL`
3. **Traded**: `LicenseTradeLine.cif_fc` where item matches, `direction='SALE'` (Purchase does NOT reduce pool)

**Bulk Calculation**: `compute_condition_pools_bulk(license_ids)` — optimized for reports querying 100s of licences

**Test Coverage**: `backend/apps/license/tests/test_dashboard_balance_cif.py` — verifies pool restrictions enforce correctly

---

## 2. PLANNED ALLOCATION RULES

### 2.1 Planning Fundamentals

**Core Concept**: Import items are planned per PHYSICAL PRODUCT (not per serial), grouped by HSN + normalized description.

**Planning Lifecycle**:
1. Auto-plan engines compute suggested lines per physical-product group
2. Lines stored on group's representative item (lowest serial)
3. Allotment enforcement aggregates across entire group
4. Consumed quantity/CIF reduces `remaining_quantity` / `remaining_cif_fc` on plan row
5. Full history preserved (never deleted); only `is_current=True` rows used for calculations

---

### 2.2 Item Grouping and Merge Key

**Single Canonical Grouping**: `plan_grouping.merge_items_for_classification()`

**Group Key** (`plan_group_key`):
```
IF description present:
  key = normalize(HSN) + "|" + normalize(description)
ELSE IF item names exist:
  key = normalize(HSN) + "|N:" + sorted_item_names
ELSE:
  key = "ID:" + import_item_id  (never merge un-named items)
```

**Normalization** (`_normalize_text`):
- Trim whitespace
- Case-insensitive (upper-case internally)
- Collapse internal whitespace runs to single space
- Remove whitespace around "/" (e.g., "Packing Material / PP" = "Packing Material/PP")

**Merge Key** (Item Pivot Report read-only): `merge_key(hs_code, description)` — same rules, given plain strings

**Representative Selection**: **Lowest serial_number** (not lowest id)
- Fallback: id if serial_number unavailable
- Plan lines stored on representative; consuming any group member draws from shared plan

**Test Coverage**: `backend/apps/license/tests/test_plan_grouping.py`
- `test_plan_grouping_uses_trimmed_uppercase_description`
- `test_plan_grouping_never_merges_when_hsn_differs`

---

### 2.3 Plan Validation (Shared Across All Engines)

**Validator**: `plan_grouping.validate_group_plan_lines()` — single shared implementation

**Validation Gates** (group-level, not per-line):
1. **Quantity Check**: `SUM(planned_qty) <= available_qty`
   - Fresh lines: strict `<=` check
   - Preserved lines: may exceed available (legacy balances across reserialized items)

2. **Price Ceiling Check** (if `unit_price_map` provided):
   - Fresh lines: `unit_price <= ceiling`
   - Preserved lines: allow any price (legacy debt)

3. **Negative Rejection**:
   - Quantity < 0: reject
   - CIF < 0: reject

**Tolerance** (optional): qty_tolerance, price_tolerance (default 0.01) for float comparison

**Failure Mode**: Entire group rejected if ANY line fails; caller must NOT save partial group

**Test Coverage**: `backend/apps/license/tests/test_plan_grouping.py` → `TestValidateGroupPlanLines`, `TestValidateFreshPlanLines`

---

## 3. AUTO-PLAN ENGINES AND SION NORMS

### 3.1 Auto-Plan Architecture (Shared Pattern)

All auto-plan engines follow this shape:

1. **Ensure Plan Item Names** (`ensure_plan_item_names()`) — get-or-create each category's `ItemNameModel` row
   - Name format: `"{base_name} - {norm_code}"` (e.g., "RUTILE - A3627")
   - Never fail plan if row missing

2. **Load & Classify** — fetch import items, classify RAW items into engine's categories
   - Use existing item-matcher rules (`item_matcher.get_item_filters()`)
   - One query per category (batch all filters, single `filter(combined_q)`)

3. **Group** — merge each classified bucket via `merge_items_for_classification()`
   - Result: one plan line per physical product per category

4. **Plan** — run the engine's waterfall/allocation logic
   - Starting balance: `license.get_balance_cif` (live)
   - Decrement remaining after each step

5. **Validate** — `validate_group_plan_lines()` before accepting lines
   - Price ceiling check (fixed-price engines) or looser gate (E5's continuous)

6. **Persist** — write `LicenseItemPlan` rows on group representatives
   - Never overwrite `is_current=True` rows; mark old `is_current=False` instead

---

### 3.2 E1 Auto-Plan (General Unrestricted)

**Norm Code**: E1

**Categories**: 
- Classified via `item_matcher.get_item_filters()` rules (E1 norm)
- Items can belong to multiple categories (e.g., "other confectionery", "tartaric acid")
- Priority order breaks ties (first-match-wins)

**Planning Logic**: Per-category waterfall
- **Planned quantity** per group = `available_qty * (group_pct / 100)` for some category-specific split
- Milk split (E1-specific): calls `optimal_milk_split()` for Milk vs. other goods

**Prices**: Per-category fixed unit prices (from `auto_plan_shared.py`)

**Grouping**: E1 classifies RAW items first (HSN/description pre-grouped), then calls `merge_items_for_classification()`

**Validation**: `validate_fresh_plan_lines()` — looser gate (no price ceiling, just qty <= available)

**Test Coverage**: 
- `backend/apps/license/tests/test_e1_auto_plan.py`
- `TestComputeE1AutoPlanParity` — verifies mixed-licence totals match shared engine
- `TestComputeE1AutoPlanIsIdempotent` — rerun produces identical rows

---

### 3.3 E5 Auto-Plan (Biscuits/Oils)

**Norm Code**: E5

**Categories** (via item-matcher):
- Milk products
- Non-milk goods
- Special splits: PKO (Palm Kernel Oil) vs Olive Oil (40/60 split)

**Planning Logic**: Waterfall with fractional-residual optimization
- Allocates max affordable qty at each fixed price
- Fractional remainder flows to next category unchanged (continuous, not floored)
- Special case: if PKO available and Oil available, split 40/60 of available qty

**Prices**: 
- Milk products: fixed price (e.g., 0.50)
- Non-milk: fixed price (e.g., 1.00)
- PKO/Oil: each fixed, split proportion stable

**Grouping**: Classify raw items per category, then group each classified bucket

**Validation**: `validate_fresh_plan_lines()` — No fixed price ceiling (continuous fractional logic, prices vary per allocation step)

**Preserved Plan Handling**: 
- Partially-consumed plans preserved (not recalculated)
- Reserialization/item consolidation tracked via `existing_split_balances_for_groups()`

**Test Coverage**: 
- `backend/apps/license/tests/test_e5_auto_plan.py`
- `TestComputeE5AutoPlanParity` — mixed-licence totals agree
- `TestComputeE5AutoPlanIsIdempotent` — stable reruns

---

### 3.4 E126 Auto-Plan (Vegetable Oils)

**Norm Code**: E126

**Categories** (via item-matcher):
- RBD Palmolein Oil (fixed price USD 1.00)
- PKO (Palm Kernel Oil) — special 50/50 split target with Olive Oil
- Olive Oil — complementary to PKO split

**Planning Logic**: 
1. Fixed-price allocation per plain category
2. PKO + Olive: if both available, split 50/50 of available_qty across two groups
3. Leftover in PKO flows to Olive Oil (wastage rebalance)

**Prices**: 
- RBD: fixed USD 1.00
- PKO: fixed USD 1.25
- Olive: fixed USD 1.50
- Ceiling validation: all prices bounded

**Split Preservation**: 
- Once a split is generated, rerun preserves it (partial consumption allowed)
- Corruption check: if preserved price exceeds ceiling, reject whole group

**Fractional Invariant** (CIF × quantity consistency):
- Floored allocation: `planned_qty = floor(capped_cif / price)`
- Ensures `planned_qty * price ≤ remaining_cif` exactly (no fractional remainder)
- Tested extensively across fractional available_qty values

**Test Coverage**: 
- `backend/apps/license/tests/test_e126_auto_plan.py`
- `TestPkoOliveSplitAvailableQuantity` — 50/50 split logic
- `TestPkoOliveWastageRebalanceAutoPlan` — leftover rebalance
- `TestFractionalQuantityCifInvariant` — qty×price consistency across fractional values

---

### 3.5 E132 Auto-Plan (Vegetable Oils / Cheese)

**Norm Code**: E132

**Categories** (via item-matcher):
- RBD Palmolein Oil (fixed price USD 1.00)
- PKO (Palm Kernel Oil) — special 40/60 split target with Cheese
- Cheese — complementary to PKO split

**Planning Logic**: 
1. Fixed-price allocation per plain category
2. PKO + Cheese: if both available, split 40/60 of available_qty across two groups
3. Leftover in PKO flows to Cheese (wastage rebalance)

**Prices**: 
- RBD: fixed USD 1.00
- PKO: fixed USD 1.25
- Cheese: fixed USD 1.50
- Ceiling validation: all prices bounded

**Split Preservation**: Same as E126 (corruption check on preserved price)

**Fractional Invariant**: Same as E126 (floored allocation)

**Test Coverage**: `backend/apps/license/tests/test_e132_auto_plan.py` — mirrors E126 test suite

---

### 3.6 A3627 Auto-Plan (Glass & Ceramics) — NEW

**Norm Code**: A3627 (committed 23a16ab8)

**Categories** (via item-matcher, priority-ordered):
1. **RUTILE** — Priority 1
2. **TITANIUM DIOXIDE** — Priority 2
3. **SODA ASH** — Priority 3
4. **PP** — Priority 4

**Planning Logic**: 4-priority waterfall
- Start with remaining balance
- For each priority (in order):
  - Allocate max affordable qty at that priority's price
  - Floor qty to whole unit (ensures `qty * price ≤ remaining` exactly)
  - Deduct from remaining
  - Pass remainder to next priority

**Prices**: 
- RUTILE: USD 2.50 (avg < 3.00) or USD 3.50 (avg >= 3.00) — depends on licence's **own import history**
- TITANIUM DIOXIDE: USD 2.00
- SODA ASH: USD 0.70
- PP: USD 1.20

**Rutile Average Price** (Custom Calculation):
```python
avg = sum(rutile_items.cif_fc) / sum(rutile_items.quantity)
if avg < USD 3.00:
  price = USD 2.50
else:
  price = USD 3.50
```
- Uses ORIGINAL import `quantity` / `cif_fc` (not available_quantity)
- **NOT** `LicenseDetailsModel.average_unit_price` (that's for Glass-Formers report, different hardcoded prices)

**Grouping**: Classify raw items into 4 categories, then group each bucket

**Validation**: `validate_group_plan_lines()` with price ceiling map (every line's price is known constant)

**Test Coverage**: `backend/apps/license/tests/test_a3627_auto_plan.py`
- `TestRutileAveragePriceThreshold` — avg price branching
- `TestWaterfallOrderAndConsumption` — priority waterfall correctly drains balance
- `TestPartialMultiItemAllocation` — groups share balance within priority
- `TestRoundingEdges` — floored qty vs fractional available_qty

---

## 4. CONDITION POOLS AND RESTRICTIONS

### 4.1 Condition-Type Pool Rules

**Pool Definition**: For each `condition_type` = "N%" on import items:
```
pool = N% × license_total_credit
used = SUM(debit + allotment + SALE_trade) for items in this condition
remaining = max(pool - used, 0)
```

**Components of Used**:
1. **Debit**: `RowDetails.cif_fc` where `sr_number` matches condition group, `transaction_type='D'`
   - Hidden rows excluded via `annotate_and_exclude_hidden()`
2. **Allotment**: `AllotmentItems.cif_fc` where `item` matches, `bill_of_entry IS NULL`
3. **Trade**: `LicenseTradeLine.cif_fc` where `sr_number` matches, `direction='SALE'`
   - PURCHASE trades explicitly excluded (add to licence, do NOT reduce pool)

**Available Value** (for restricted item):
```
available_value = min(remaining, license_balance_cif)
```

**Non-Percentage Conditions**:
- `""` (empty): available_value = license_balance (no restriction)
- `"AU"` (Actual User): available_value = license_balance (non-transferable, but still usable)
- Other values: treated as empty

**Bulk Calculation**: `compute_condition_pools_bulk(license_ids)` — optimized for Item Pivot Report
- Single query per component, results aggregated per license/condition

**Test Coverage**: Implicit in Item Pivot Report golden-master tests; condition restrictions enforced in allocation UI

---

## 5. RECONCILIATION AND ALLOCATION LEDGERS

### 5.1 BOE / Invoice Linking (Legacy + Phase A Formal)

**Core Business Rule**: "One physical import may generate multiple documents, but it must produce exactly one licence debit."

**Two Mechanisms** (both implemented, both checked):

#### A. Legacy Mechanism (Trade.boes M2M Tag)
- SALE trade carries `trade.boes` M2M linking to physical BOEs
- Indicates "invoice invoiced this BOE"
- Symmetric across all debit rows of that BOE (BOE-level, not per-item)
- Scanned by `_scan_linked_boe_candidates()` (one query per trade batch)
- Visible = `annotate_and_exclude_hidden()` excludes hidden BOEs even here

#### B. Phase A Mechanism (InvoiceBOEAllocation Ledger)
- Formal, partial-allocation records: `{trade_line} → {row_details}, allocated_cif_fc=X`
- Per-row, per-trade-line, supports many-to-many and fractional amounts
- Scope: licence-item level (sr_number), so multi-item BOEs/trades can express item-level attribution

**Resolution** (`resolve_boes_represented_by_invoice[_for_licenses]`):
- Returns `{bill_of_entry_id}` for each licence
- Includes BOEs from BOTH mechanisms
- One query for formal allocations + one trade scan (bulk, not per-trade)

**Impact on Balance**:
- Debit calculation (`calculate_debit()`) uses per-row **unmatched remainder** after both mechanisms
- Financial Ledger uses same set of represented BOEs for "Pending" row suppression
- Customs Ledger's "Matched/Unmatched" status also reads this set

---

### 5.2 Invoice-BOE Allocation Ledger (Phase A)

**Model**: `InvoiceBOEAllocation`

**Scope**: Per `LicenseTradeLine` → Per `RowDetails`, recording how much of the BOE debit "explains" the invoice line

**Ledger Semantics** (never mutated, only versioned):
- `status`: ACTIVE / REVERSED
- `is_current`: True/False (edits create new row, mark old as superseded)
- `superseded_by`: FK to replacement row (tracks edit history)

**Allocation Amounts**:
- `allocated_qty`: Decimal(20, 4) — quantity matched
- `allocated_cif_fc`: Decimal(20, 3) — CIF (foreign currency) matched
- `allocated_cif_inr`: Decimal(20, 3) — CIF (INR) matched

**Precision Sizing**:
- `allocated_cif_fc`: max_digits=20, decimal_places=3 (covers `RowDetails.cif_fc` 15,3)
- Room for larger `LicenseTradeLine.cif_fc` (20,2) sum across multiple rows

**Debit Impact**: Only ACTIVE, is_current=True rows counted
```python
allocated = SUM(allocated_cif_fc) where status='ACTIVE', is_current=True
contributed = max(row.cif_fc - allocated, 0)  # unmatched remainder
```

**Over-Allocation Prevention**:
- No DB-level CHECK (Postgres cannot aggregate across rows in constraints)
- Service-layer validation in `allocation_service.create_invoice_boe_allocation()`
- Enforced inside `transaction.atomic()` + row-level locking

**Test Coverage**: `backend/apps/reconciliation/tests/test_allocation_service.py`
- `InvoiceBOEAllocationTests.*` — full allocation lifecycle

---

### 5.3 BOE-Allotment Allocation Ledger (Phase A)

**Model**: `BOEAllotmentAllocation`

**Scope**: Per `AllotmentItems` → Per `RowDetails`, recording how much of a BOE debit is "sourced from" an allotment

**Ledger Semantics**: Identical to `InvoiceBOEAllocation` (never mutated, versioned, ACTIVE/REVERSED/is_current/superseded_by)

**Allocation Amounts**: 
- `allocated_qty`, `allocated_cif_fc`, `allocated_cif_inr` (same precision as invoice side)

**Allotment Impact**:
- Once linked to BOE, allotment no longer counts in `calculate_allotment()` (balance deduction)
- Transition tracked in formal ledger (no binary exclusion)

**Independent Consumption Tracks**:
- `InvoiceBOEAllocation` (invoice side) and `BOEAllotmentAllocation` (allotment side) are SEPARATE
- Same `RowDetails` row can simultaneously be "explained" by invoice AND "sourced from" allotment
- Each track calculates its own remaining balance independently
  - `remaining_for_row_details_invoice_side()` → subtracts only invoice allocations
  - `remaining_for_row_details_allotment_side()` → subtracts only allotment allocations

**Test Coverage**: `backend/apps/reconciliation/tests/test_allocation_service.py`
- `BOEAllotmentAllocationTests.*` — allocation lifecycle

---

## 6. RECONCILIATION QUERIES AND DETECTION

### 6.1 Reconciliation Warnings (Detection Rules)

**Purpose**: Surface where "one physical import = one licence debit" rule is violated

**Queries** (in `apps/reconciliation/services/queries.py`):

| Query | Detection | Source | Remedy |
|-------|-----------|--------|--------|
| `missing_boe()` | SALE trade line has no linked BOE | BOE absence | Link to matching BOE |
| `missing_invoice()` | BOE has blank `invoice_no` | Invoice absence | Set invoice_no |
| `duplicate_debits()` | Same BOE + licence_item, two trade lines | Double-link | Merge BOEs or link one |
| `duplicate_boes()` | Two BOEs with near-identical CIF for same trade | Physical duplicate | Merge the BOEs |
| `cif_comparison()` | Trade line CIF vs BOE CIF differ beyond tolerance | Data quality | Note/ignore, reconciliation flag |
| `qty_comparison()` | Trade line qty vs BOE qty differ | Data quality | Note/ignore |
| `multi_boe_per_invoice()` | One trade line linked to 2+ BOEs | Fragmented import | Link to 1 BOE or merge |
| `multi_invoice_per_boe()` | One BOE linked to 2+ trade lines | Partial invoice | Link to 1 or split |

**Tolerance** (CIF/qty mismatch):
- CIF within 0.5% → pass
- Qty exact match required (or note as mismatch)

---

## 7. SION NORMS AND ITEM CLASSIFICATION

### 7.1 SION Norm Model

**Table**: `core.SIONNorm` (master data from DGFT)

**Fields**:
- `norm_class`: Code (e.g., "A3627", "E1", "E5", "E126", "E132")
- `description`: Human-readable (e.g., "Glass & Ceramic", "General Unrestricted")

**Link to Licence**: `LicenseImportItemsModel.norm_class` (FK)

**Link to Planning Items**: `ItemNameModel` carries `(base_name, norm)` pair
- `base_name` = category name (e.g., "RUTILE", "MILK PRODUCTS")
- `norm` = norm code (e.g., "A3627", "E1")

---

### 7.2 Item Name Classification

**Table**: `ItemNameModel` (junction of category + norm)

**Auto-Plan Item Matching** (`item_matcher.py`):
- `get_item_filters()` returns `{base_name, norm, filters: [Q(...), Q(...)]}` 
- Q-filters match `LicenseImportItemsModel` fields (HS code, description, M2M tags)
- Each auto-plan engine uses these exact filters (no custom regex)

**Example** (A3627 — Glass):
```python
{
  'base_name': 'RUTILE',
  'norm': 'A3627',
  'filters': [Q(hs_code__hs_code__in=['2610.00']), ...]
}
```

**Bulk Matching** (`bulk_auto_link_license_items`):
- One query per category: `filter(combined_q = reduce(or_, filters))`
- Sets `item.items.add(ItemNameModel)` for matches (M2M junction)

---

## 8. CALCULATION OWNERSHIP (Service/View/Model Mapping)

| Calculation | Owner | Path | Used By |
|-----------|-------|------|---------|
| **Credit** | `LicenseBalanceCalculator.calculate_credit()` | `apps/license/services/balance_calculator.py:72` | Both engines, allotment, condition pools |
| **Customs Balance** | `LicenseBalanceCalculator.calculate_customs_balance()` | `balance_calculator.py:1385` | Customs Ledger only |
| **Financial Balance** (Business) | `LicenseBalanceCalculator.calculate_financial_balance()` | `balance_calculator.py:1543` | `get_balance_cif`, all UI consumers |
| **BOE Debit (Raw)** | `LicenseBalanceCalculator.calculate_boe_debit_total()` | `balance_calculator.py:491` | Customs engine, financial (via get_debit_rows) |
| **BOE Debit (Allocation-Netted)** | `LicenseBalanceCalculator.calculate_debit()` | `balance_calculator.py:438` | Financial engine, Financial Ledger |
| **Hidden BOE Debit** | `LicenseBalanceCalculator.calculate_hidden_boe_debit_total()` | `balance_calculator.py:541` | Opening balance gate, customs |
| **Allotment** | `LicenseBalanceCalculator.calculate_allotment()` | `balance_calculator.py:949` | Both engines |
| **Purchase Credit** | `LicenseBalanceCalculator.calculate_purchase_credit()` | `balance_calculator.py:1070` | Financial engine only |
| **Sale Debit (Trade)** | `LicenseBalanceCalculator.calculate_trade()` | `balance_calculator.py:1042` | Financial engine only |
| **Opening Balance** | `LicenseBalanceCalculator.calculate_opening_balance()` | `balance_calculator.py:1465` | Financial engine anchor |
| **Item Restriction Pools** | `condition_pool.compute_condition_pools()` | `apps/license/services/condition_pool.py:46` | Item allocation UI, reports |
| **Item Balance** | `ItemBalanceCalculator.calculate_item_balance()` | `balance_calculator.py:1659+` | Item allocation, Item Pivot |
| **Debit Rows (Annotated)** | `LicenseBalanceCalculator.get_debit_rows()` | `balance_calculator.py:349` | Financial Ledger PDF, balance calculations |
| **BOEs Represented** | `LicenseBalanceCalculator.resolve_boes_represented_by_invoice[_for_licenses]()` | `balance_calculator.py:190` | Debit exclusion, Financial Ledger status |

---

## 9. BUSINESS RULES BY FUNCTION

### 9.1 Balance Constraints
- **Minimum balance**: 0 (never negative)
- **Precision**: 2 decimal places (quantize via `quantize_2dp()`)
- **Hidden row handling**: Excluded from live calculations, included in Customs Ledger
- **BOE representation**: Once ANY row of a BOE is represented, entire BOE excluded from "Pending" row

### 9.2 Allocation Constraints
- **Over-allocation**: Prevented in service layer (not DB-level)
- **Partial allocation**: Supported; unmatched remainder visible in debit
- **Ledger immutability**: Allocations never mutated; edits create new rows, mark old as superseded
- **Independent tracks**: Invoice-BOE and BOE-Allotment consume the same row independently

### 9.3 Planning Constraints
- **Grouping**: HSN + normalized description (never serial-number based)
- **Representative**: Lowest serial_number (fallback: lowest id)
- **Plan storage**: On group representative only
- **Validation**: Entire group passes/fails together (no partial save)
- **Preservation**: Partially-consumed plans preserved on rerun (no recalculation)

### 9.4 Condition Pool Constraints
- **Pool cap**: N% × licence credit (hard limit for that condition)
- **Used components**: Debit + Allotment + SALE_Trade (Purchase excluded)
- **Available**: min(remaining_pool, licence_balance)
- **Fallback**: Empty condition_type or "AU" → no pool restriction

### 9.5 Reconciliation Constraints
- **One import = one debit**: Enforced via warnings, not automation
- **BOE level**: Representation decided at BOE level, applies to all its rows
- **CIF tolerance**: 0.5% mismatch allowable (warning, not rejection)
- **Dual mechanism**: Both legacy trade.boes tag AND formal InvoiceBOEAllocation honored

---

## 10. TEST FIXTURES AND HIDDEN RULES

### 10.1 Common Test Patterns (Reveals Business Rules)

**Balance Consistency**:
- `test_balance_cif_single_source.py` — Export item CIF flows through, BOE debit reduces
- `test_item_pivot_balance_consistency.py` — Group totals match per-item sums

**Allocation**:
- `test_allocate_items_*.py` — Multiple validation gates (qty cap, CIF cap, group plan cap, condition pool cap, E1/E126/E132 plan-specific rules)
- Tests show CIF is Decimal, never float
- Over-allocation rejected with error message

**Plan Preservation**:
- `test_e126_auto_plan.py::TestPkoOliveSplitPreservedOnceGenerated` — Plan not recalculated on rerun
- `test_e1_auto_plan.py::TestComputeE1AutoPlanIsIdempotent` — Identical rows on rerun

**Reconciliation**:
- `test_reconciliation.py` — Missing BOE, missing invoice, duplicate debits, CIF mismatch detection
- `test_allocation_service.py` — Partial allocation does NOT suppress unmatched remainder
- `test_boe_link_reconciler.py` — Legacy vs formal allocation both honored

---

## 11. KNOWN DIVERGENCES AND TRADE-OFFS

### 11.1 Balance Engine Divergence
- **Intentional**: Customs engine includes hidden rows; Financial engine (business) excludes them via Opening Balance gate
- **Reconciliation**: Customs Ledger running total uses Customs formula; Financial Balance uses Financial formula
- **Test**: `test_dashboard_balance_cif.py` verifies both paths compute independently

### 11.2 Rutile Average Price (A3627)
- **NOT** `LicenseDetailsModel.average_unit_price` (Glass-Formers report, different hardcoded prices)
- **CUSTOM**: Weighted average of ORIGINAL (not available) quantity/CIF across classified RUTILE items
- **Threshold**: < USD 3.00 → price 2.50; >= 3.00 → price 3.50

### 11.3 BOE Representation Scope (Known Trade-off)
- **Rule**: Once ANY debit row of a BOE is represented, entire BOE treated as represented
- **Impact**: A BOE debiting 2 licence items; if represented on one, both items' full debit excluded from balance
- **Rationale**: Explicit product decision; BOE is a physical document; one invoice invoices the whole BOE, not per-item
- **Confirmed against**: BOE 7836435 (concrete example: debit two items, only one had invoice, both still excluded)

### 11.4 Condition Pool Trade Exclusion
- **SALE trades reduce pool**: Deliberate (sale is debit-like)
- **PURCHASE trades excluded**: Deliberate (purchase is credit-like, re-enters balance separately)

---

## 12. DATA QUALITY AND AUDIT

### 12.1 Audit Trail
- Every reconciliation action logged: `ReconciliationLog` (append-only)
- Actions: LINK, MERGE_BOE, ALLOCATE, EDIT_ALLOCATION, REVERSE_ALLOCATION, etc.
- Before/after snapshots captured for all write actions

### 12.2 Constraints and Validation
- **No negative balance**: Minimum 0, enforced in calculation, not DB
- **No orphaned allocations**: FK PROTECT on trade_line, row_details, allotment_items
- **No silent over-allocation**: Rejected in service layer with user-facing error
- **No partial plan saves**: Entire group passes/fails validation

### 12.3 Bulk Operations and Performance
- Bulk calculations (`*_for_licenses`) preferred over N per-licence queries
- Batch item classification (one query per category, combined Q-filters)
- Bulk condition pool computation (4-5 queries, not 13+ per licence)

---

## 13. APPENDIX: KEY FILE PATHS

| Component | File Path |
|-----------|-----------|
| **Balance Calculation** | `backend/apps/license/services/balance_calculator.py` |
| **Condition Pools** | `backend/apps/license/services/condition_pool.py` |
| **Plan Grouping** | `backend/apps/license/services/plan_grouping.py` |
| **A3627 Auto-Plan** | `backend/apps/license/services/a3627_auto_plan.py` |
| **E1/E5/E126/E132** | `backend/apps/license/services/e*_auto_plan.py` |
| **Allocation Service** | `backend/apps/allotment/services/allocation_service.py` |
| **Reconciliation Queries** | `backend/apps/reconciliation/services/queries.py` |
| **Reconciliation Allocation** | `backend/apps/reconciliation/services/allocation_service.py` |
| **Reconciliation Models** | `backend/apps/reconciliation/models.py` |
| **Item Matcher** | `backend/apps/license/utils/item_matcher.py` |
| **License Models (Balance)** | `backend/apps/license/models/core.py` (methods: get_balance_cif, balance_cif property) |
| **Import Item Model** | `backend/apps/license/models/core.py` (LicenseImportItemsModel) |
| **Test: Balance Consistency** | `backend/apps/license/tests/test_item_pivot_balance_consistency.py` |
| **Test: Allocation** | `backend/apps/allotment/tests/test_allocate_items_*.py` |
| **Test: Plans** | `backend/apps/license/tests/test_e*_auto_plan.py` |
| **Test: Reconciliation** | `backend/apps/reconciliation/tests/test_*.py` |

---

## 14. QUICK REFERENCE: FORMULAS

```
CUSTOMS BALANCE = Credit - (Visible BOE Debit + Hidden BOE Debit + Allotment)

FINANCIAL BALANCE = Opening Balance 
                    + Purchase Credit 
                    - Sale Debit 
                    - Our BOE Debit (allocation-netted) 
                    - Outstanding Allotments

WHERE:
  Opening Balance = Credit - Hidden - Purchase  (if hidden > 0)
                  = 0                           (if purchased)
                  = Credit                      (else)
  
  Our BOE Debit = SUM(max(row.cif_fc - matched, 0))
  
  matched = min(row.cif_fc, allocated + linked_excluded)
  
  allocated = SUM(InvoiceBOEAllocation.allocated_cif_fc 
                  where status='ACTIVE', is_current=True)
  
  linked_excluded = row.cif_fc  (if BOE represented AND row.allocated=0)
                  = 0            (else)

CONDITION POOL = N% × Credit
USED = Debit + Allotment + SALE_Trade
REMAINING = max(Pool - Used, 0)
AVAILABLE = min(Remaining, Balance)
```
