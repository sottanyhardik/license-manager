# Quick Reference: Calculation Lookup

Use this guide to find where a specific calculation happens and how to validate it.

---

## Q: Where is Balance CIF calculated?

**Authoritative path**: 
```python
license.get_balance_cif  # Property in LicenseDetailsModel
  → LicenseBalanceCalculator.calculate_financial_balance(license)
    → Formula: Opening + Purchase - Sale - BOE_Debit - Allotment
```

**File**: `backend/apps/license/services/balance_calculator.py:1543`

**Validate**: 
1. Check `calculate_opening_balance()` result
2. Check `calculate_purchase_credit()` > 0 if purchased
3. Check `calculate_debit()` excludes only allocated BOEs
4. Check `calculate_allotment()` is sum of non-BOE-linked items only
5. Sum should match all reports/exports

**Regression Test**: `backend/apps/license/tests/test_dashboard_balance_cif.py`

---

## Q: How much of a BOE row is excluded from balance?

**Calculation**: Per-row unmatched remainder

```python
# In get_debit_rows() annotation:
allocated = SUM(InvoiceBOEAllocation.allocated_cif_fc 
                where row_details=this_row, status=ACTIVE, is_current=True)
linked_excluded = cif_fc if (bill_of_entry_id in represented_set AND allocated=0)
                = 0 otherwise
matched = min(cif_fc, allocated + linked_excluded)
contributed = max(cif_fc - matched, 0)  ← This is what gets summed for debit
```

**File**: `backend/apps/license/services/balance_calculator.py:349` (get_debit_rows)

**Key Rules**:
- Only ACTIVE, is_current=True allocations counted
- A row with zero allocation on a represented BOE gets full cif_fc excluded
- A row with partial allocation (e.g., 300 of 1000) leaves 700 in contributed debit
- Unmatched remainder NOT suppressed (this was the Phase A change)

**Validate**: 
```sql
SELECT sum(contributed) FROM get_debit_rows() 
-- Should match the debit component in financial_balance formula
```

**Regression Test**: 
- `backend/apps/reconciliation/tests/test_allocation_service.py::InvoiceBOEAllocationTests::test_partial_allocation_leaves_correct_unmatched_remainder`

---

## Q: Is a BOE "represented by invoice"?

**Check**: `LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license)`

**Returns**: `{bill_of_entry_id, ...}` — set of represented BOE IDs for this licence

**Two mechanisms** (both checked, both honored):
1. **Formal**: `InvoiceBOEAllocation` where `status=ACTIVE, is_current=True`
2. **Legacy**: `LicenseTrade.boes` M2M tag (SALE trades only, visible BOEs only)

**File**: `backend/apps/license/services/balance_calculator.py:190`

**Key Rule**: Once ANY row of a BOE is represented, entire BOE treated as represented for ALL its rows on this licence

**Validate**: 
```python
represented = LicenseBalanceCalculator.resolve_boes_represented_by_invoice(license)
for boe_id in represented:
  # Check either InvoiceBOEAllocation exists OR trade.boes tag exists
  # Either way, this BOE's debit is affected
```

---

## Q: How much of an allotment is consumed?

**Direct Calc**: 
```python
LicenseBalanceCalculator.calculate_allotment(license)
# Returns: sum(AllotmentItems.cif_fc) where allotment.bill_of_entry IS NULL
```

**Independent Track**: 
```python
# Allotments linked to BOE are tracked separately:
BOEAllotmentAllocation [status=ACTIVE, is_current=True]
  # These reduce "outstanding allotment" but separately from invoice allocations
```

**File**: 
- Outstanding allotment: `balance_calculator.py:949`
- Linked allotment: `reconciliation/models.py` (BOEAllotmentAllocation)

**Key Rule**: Once allotment is linked to BOE, it no longer reduces balance (moved to ledger)

**Validate**: 
```python
outstanding = calculate_allotment(license)
# outstanding + sum(BOEAllotmentAllocation) should equal total allotted value
```

---

## Q: What is the condition pool for item X?

**Calc**:
```python
pools = compute_condition_pools(license)
remaining = pools.get(item.condition_type, 0)
available_value = min(remaining, license.get_balance_cif)
```

**Formula**: For condition_type = "N%":
```
pool = N% × license_credit
used = SUM(debit + allotment + SALE_trade) for items in condition
remaining = max(pool - used, 0)
```

**File**: `backend/apps/license/services/condition_pool.py:46`

**Key Rules**:
- Non-percentage conditions ("", "AU") have no pool (available = balance)
- PURCHASE trades explicitly excluded (add to licence, don't reduce pool)
- Debit and allotment both reduce pool (independent from restrictions)

**Validate**: 
```python
for item in license.import_items.filter(condition_type="3%"):
  available = get_available_value(item)  # Should be min(3% pool, balance)
  allocated = calculate_allocated_for_item(item)
  assert allocated <= available
```

**Regression Test**: Implicit in Item Pivot Report golden-master tests

---

## Q: How are import items grouped for planning?

**Single Implementation**: `merge_items_for_classification(import_items)`

**File**: `backend/apps/license/services/plan_grouping.py:172`

**Group Key**: Per item:
```python
if description:
  key = normalize(HSN) + "|" + normalize(description)
else if names:
  key = normalize(HSN) + "|N:" + sorted_names
else:
  key = "ID:" + id
```

**Normalization**: 
- Trim, uppercase, collapse internal spaces, remove spaces around "/"

**Representative**:
- Lowest serial_number (not id)
- Fallback: id if serial unavailable

**Key Rule**: TWO items are same group ONLY if both HSN and normalized description match

**Validate**: 
```python
groups = merge_items_for_classification(license.import_items.all())
for group in groups:
  assert len(group['member_ids']) >= 1
  assert group['representative_id'] == min(ids, key=serial)
```

**Regression Test**: `backend/apps/license/tests/test_plan_grouping.py`

---

## Q: Can I allocate X CIF to this item from allotment Y?

**Constraint Check**: `AllocationService.calculate_max_allocation(allotment, item, unit_price)`

**File**: `backend/apps/allotment/services/allocation_service.py:29`

**Returns**: `{'max_quantity': Q, 'max_value': V}`

**Constraints**:
1. `max_qty = min(allotment.balanced_qty, item.available_qty)`
2. `max_value = max_qty * unit_price`
3. If `max_value > item.balance_cif_fc`: reduce qty
4. If `max_value > allotment.required_value_with_buffer - allotted`: reduce qty

**Key Rule**: Item balance CIF is a hard constraint; cannot over-allocate value

**Validate**: 
```python
max_alloc = calculate_max_allocation(allotment, item, unit_price)
assert max_alloc['max_quantity'] >= 0
assert max_alloc['max_value'] >= 0
assert max_alloc['max_value'] <= item.get_balance_cif
```

---

## Q: Is this plan line valid for this group?

**Validator**: `validate_group_plan_lines(item_lines, item_names, avail_qty, unit_price_map, is_preserved)`

**File**: `backend/apps/license/services/plan_grouping.py:330`

**Returns**: `bool` (True = pass, False = reject)

**Gates** (entire group must pass):
1. **Quantity**: `SUM(planned_qty) <= available_qty` (strict for fresh, loose for preserved)
2. **Price**: `unit_price <= price_ceiling` (if preserved=False, only for fresh)
3. **No negatives**: Qty >= 0, CIF >= 0

**Key Rule**: Entire group rejected if ANY line fails; caller must NOT save partial

**Validate**: 
```python
passed = validate_group_plan_lines(
  item_lines=[{unit_price: 2.50, planned_quantity: 100}, ...],
  item_planning_items=["RUTILE - A3627", ...],
  avail_qty=1000,
  unit_price_map={"RUTILE - A3627": Decimal("3.50")},
  is_preserved=False
)
assert passed  # or handle rejection
```

**Regression Test**: `backend/apps/license/tests/test_plan_grouping.py::TestValidateGroupPlanLines`

---

## Q: How does A3627 pick RUTILE price?

**Calc**: `_rutile_avg_import_price(rutile_items)`

**File**: `backend/apps/license/services/a3627_auto_plan.py:162`

**Formula**:
```python
avg = sum(item.cif_fc) / sum(item.quantity)  # RAW import, not available
if avg < USD 3.00:
  price = USD 2.50
else:
  price = USD 3.50
```

**Key Rules**:
- Uses ORIGINAL import quantity/CIF (not available_quantity)
- NOT LicenseDetailsModel.average_unit_price (Glass-Formers report, different logic)
- If no RUTILE items or zero quantity: avg=0, price=2.50 (harmless; zero qty produces zero plan anyway)

**Validate**: 
```python
rutile_items = classify_a3627(license)["RUTILE"]
avg = _rutile_avg_import_price(rutile_items)
if avg < 3.00:
  assert planned_price == Decimal("2.50")
else:
  assert planned_price == Decimal("3.50")
```

**Regression Test**: `backend/apps/license/tests/test_a3627_auto_plan.py::TestRutileAveragePriceThreshold`

---

## Q: Does this allocation over-allocate?

**Prevention**: `allocation_service.create_invoice_boe_allocation()` inside transaction.atomic()

**File**: `backend/apps/reconciliation/services/allocation_service.py:224`

**Checks**:
1. `remaining_for_row_details_invoice_side() >= allocated_cif` (no over-alloc)
2. `remaining_for_trade_line() >= allocated_cif` (invoice side, not allotment side)
3. Row-level locking (SELECT ... FOR UPDATE) to close race window

**Key Rule**: No DB-level constraint (Postgres CHECK cannot aggregate rows); service-layer enforcement only

**Validate**: 
```python
try:
  allocation_service.create_invoice_boe_allocation(trade_line, row_details, amount)
except ValidationError as e:
  # Expect: "Value exceeds maximum allowed"
  print(f"Over-allocation rejected: {e}")
```

**Regression Test**: `backend/apps/reconciliation/tests/test_allocation_service.py::InvoiceBOEAllocationTests::test_over_allocation_rejected_*`

---

## Q: What was the old value of this allocation?

**History**: `InvoiceBOEAllocation.superseded_by` chain

**Ledger Rule**: Allocations never mutated; edits create NEW row, mark old `is_current=False`

**File**: `backend/apps/reconciliation/models.py:226` (InvoiceBOEAllocation)

**Query**: 
```python
current = InvoiceBOEAllocation.objects.get(pk=X, is_current=True)
prev = current.superseded_by  # Reverse link (old row)
# Walk the chain backward to see all edits
```

**Audit Trail**: `ReconciliationLog` also captures before/after JSON snapshots

**Key Rule**: Never deleted; only `is_current` flag changes. Full history always reconstructable.

---

## Q: Why is my balance different in two screens?

**Two Engines** (intentional divergence):

| Engine | Formula | Hidden Rows | Used By | File |
|--------|---------|-------------|---------|------|
| **Financial** | Opening + Purchase - Sale - Debit - Allot | Excluded via gate | `get_balance_cif`, UI | `balance_calculator.py:1543` |
| **Customs** | Credit - (Visible + Hidden Debit) - Allot | Included | Customs Ledger only | `balance_calculator.py:1385` |

**Why Different**:
- Financial uses 3-way Opening Balance gate (handles hidden BOEs + purchase)
- Customs includes hidden BOEs unconditionally (literal Customs definition)
- Both are correct; they answer different questions

**Validate**: 
```python
financial = license.get_balance_cif
customs = LicenseBalanceCalculator.calculate_customs_balance(license)
# If license has hidden BOEs:
#   financial > customs (financial excluded hidden via opening balance)
# Else:
#   financial == customs (identical formula)
```

**Regression Test**: `backend/apps/license/tests/test_dashboard_balance_cif.py`

---

## Q: Which calculation owns which database table/field?

| Table/Field | Read By | Updated By | File |
|-------------|---------|-----------|------|
| `LicenseExportItemModel.cif_fc` | `calculate_credit()` | DGFT import | `balance_calculator.py:83` |
| `RowDetails.cif_fc` | `calculate_debit()` (via get_debit_rows) | BOE import | `balance_calculator.py:349` |
| `AllotmentItems.cif_fc` | `calculate_allotment()` | Allocation UI | `balance_calculator.py:949` |
| `LicenseTradeLine.cif_fc` | `calculate_trade()` | Trade creation | `balance_calculator.py:1042` |
| `InvoiceBOEAllocation.allocated_cif_fc` | `calculate_debit()` (allocation-driven) | Allocation UI | `balance_calculator.py:395` |
| `BOEAllotmentAllocation.allocated_cif_fc` | `calculate_allotment()` (implicit) | Allocation UI | `reconciliation/models.py:331` |
| `LicenseBalance.balance_cif` | Cached read | Signal or explicit update | `models/balance.py` |

---

## Q: What queries run when I call get_balance_cif?

**Query Count**: ~8-12 queries (depends on hidden BOEs, purchases, trades)

**Breakdown** (per `calculate_financial_balance`):
1. Export items (credit): 1 query
2. Debit rows (get_debit_rows): 1 query
3. Allocations (per debit row): 1 subquery (batched)
4. Represented BOEs (resolve_boes_represented): 1-2 queries (formal + legacy)
5. Hidden BOEs (calculate_hidden_boe_debit_total): 1 query
6. Allotments (calculate_allotment): 1 query
7. Purchase credit (calculate_purchase_credit): 1 query
8. Sale debit (calculate_trade): 1 query

**Optimization**: Use bulk variants (`*_for_licenses`) when calculating 10+ licences

**File**: Watch query count in `django-debug-toolbar` or `django.test.TestCase` assertions

---

## Q: Is there a DB-level constraint preventing X?

**No constraints on**:
- Negative balance (prevented in calculation layer only)
- Over-allocation (service-layer validation only, no CHECK)
- Orphaned references (FK PROTECT, yes; but not balanced totals)

**DB Constraints that DO exist**:
- `InvoiceBOEAllocation.row_details`: FK PROTECT (cannot delete BOE row with active allocation)
- `InvoiceBOEAllocation.trade_line`: FK PROTECT (cannot delete trade line with active allocation)
- Decimal precision (max_digits, decimal_places enforced)

**Key Philosophy**: Decimal/balance reconciliation validation is business logic layer, not DB layer

---

## Quick Validation Checklist

```
□ All Decimals (never float) — check constants use Decimal("...")
□ Quantize to 2dp — check quantize_2dp() called before returning balance
□ Floor at 0 — check `balance if balance >= DEC_0 else DEC_0`
□ Hidden rows excluded — check exclude_hidden() or annotate_and_exclude_hidden()
□ Allotments are BOE-unlinked — check bill_of_entry IS NULL filter
□ Represented BOEs check both legacy + formal — check both mechanisms in resolver
□ Group validation passes/fails entirely — no partial saves
□ Allocation edits create new rows — check is_current flag, never UPDATE old rows
□ Prices use Decimal — check Decimal("2.50"), not float 2.5
```

