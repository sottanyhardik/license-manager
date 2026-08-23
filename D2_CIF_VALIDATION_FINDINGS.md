# D2 FINDINGS: CIF Validation (Authoritative vs Derived)

## Current CIF Source

**Three places CIF is used:**

### 1. AllotmentModel (backend/apps/allotment/models.py:46)

**Fields:**
```python
unit_value_per_unit: DecimalField(15, 3)      # ← precision 3-dp (unusual)
required_quantity: DecimalField(15, 2)
cif_fc: DecimalField(15, 2)
cif_inr: DecimalField(15, 2)
exchange_rate: DecimalField(15, 6)
```

**Auto-calculation logic in save():**
```python
# Priority 1: If unit_value + required_qty → calculate cif_fc
if unit_value > 0 and required_qty > 0:
    cif_fc = unit_value × required_qty  (ROUND_HALF_UP, 2-dp)

# Priority 2: If cif_fc provided but no unit_value → derive unit_value
elif cif_fc > 0 and required_qty > 0 and unit_value == 0:
    unit_value = cif_fc / required_qty  (ROUND_UP, 3-dp)

# Priority 3: If cif_fc + exchange_rate → calculate cif_inr
if cif_fc > 0 and exchange_rate > 0:
    cif_inr = cif_fc × exchange_rate  (ROUND_HALF_UP, 2-dp)
```

**Finding:** AllotmentModel treats CIF as **potentially both**:
- **Derived** if unit_value is provided (auto-calculated)
- **Authoritative** if cif_fc is provided directly and unit_value is missing

---

### 2. LicenseItemPlan (backend/apps/license/models/core.py:1228)

**Fields:**
```python
planned_quantity: DecimalField(15, 3)
unit_price: DecimalField(15, 2)
planned_cif_fc: DecimalField(15, 2)         # User-entered or auto-planned
planned_cif_inr: DecimalField(15, 2)        # Nullable
remaining_quantity: DecimalField(15, 3)     # Tracks plan-line balance
remaining_cif_fc: DecimalField(15, 2)       # Tracks plan-line CIF balance
```

**Source:** CanonicalPlanningService (Module 2)
```python
def build_canonical_plan(...):
    # Calculates: planned_cif_fc = planned_quantity × unit_price
    #             ROUND_HALF_UP, 2-dp precision
```

**Finding:** LicenseItemPlan CIF is **derived** from quantity × unit_price by CanonicalPlanningService.

---

### 3. AllotmentItems (backend/apps/allotment/models.py:209)

**Fields:**
```python
qty: DecimalField(15, 3)
cif_fc: DecimalField(15, 2)
cif_inr: DecimalField(15, 2)
```

**No auto-calculation** — values come directly from allocate_items request.

**Finding:** AllotmentItems CIF is **user-provided** (from request body):
```python
{
    "item_id": 123,
    "qty": 100.00,
    "cif_fc": 1000.00,      # ← User supplies this
    "cif_inr": 83000.00,    # ← User supplies this
}
```

**No validation** that cif_fc matches qty × unit_price.

---

## Current Formula

**AllotmentModel (explicit):**
```
cif_fc = unit_value_per_unit × required_quantity
```

**LicenseItemPlan (via CanonicalPlanningService):**
```
planned_cif_fc = planned_quantity × unit_price
```

**AllotmentItems (none — user-supplied):**
```
cif_fc = (client-provided value, unchecked)
```

---

## Current Validation

**AllotmentModel.save():**
- Recalculates cif_fc if unit_value + required_qty change
- Derives unit_value if cif_fc provided but unit_value missing
- Calculates cif_inr from cif_fc × exchange_rate

**LicenseItemPlan:**
- No explicit validation
- Relies on CanonicalPlanningService to calculate correctly

**AllotmentItems:**
- **Zero validation**
- Client can send any cif_fc value
- No check that qty × unit_price matches

---

## Current Precision

| Field | Precision | Rounding |
|-------|-----------|----------|
| Quantity (qty) | 15, 3 | ROUND_HALF_UP |
| Unit Price (unit_value_per_unit) | 15, 3 | (unusual, typically 2) |
| Unit Price (on LicenseItemPlan) | 15, 2 | ROUND_HALF_UP |
| CIF/Price (cif_fc) | 15, 2 | ROUND_HALF_UP |
| CIF INR (cif_inr) | 15, 2 | ROUND_HALF_UP |
| Exchange rate | 15, 6 | N/A |

**Issue:** AllotmentModel.unit_value_per_unit is 3-dp (unusual), while LicenseItemPlan.unit_price is 2-dp (standard).

---

## Affected Models/Services

**Models:**
- AllotmentModel (auto-calculates)
- LicenseItemPlan (CanonicalPlanningService provides)
- AllotmentItems (user-provided, unvalidated)

**Services:**
- CanonicalPlanningService (calculates planned_cif_fc)
- allocate_items view (accepts client cif_fc without validation)

**Tests:**
- test_canonical_planning.py (asserts planned_cif_fc = qty × price)
- No tests for AllotmentItems CIF validation

---

## Recommended Implementation

**Approach: CIF is DERIVED**

1. **For AllotmentModel:**
   - Keep current behavior (calculate cif_fc from unit_value)
   - Optionally validate: if client sends cif_fc, check tolerance band or ignore it

2. **For LicenseItemPlan:**
   - Keep CanonicalPlanningService behavior (derive from qty × price)
   - No change needed

3. **For AllotmentItems:**
   - **NEW:** Validate that cif_fc matches qty × unit_price within tolerance
   - Or: **Derive** cif_fc from qty × relevant_unit_price
   - Unit price source: from the license item or from the request

**Tolerance band (if validation):**
```python
# Allow ±0.01 tolerance for rounding
expected_cif = qty × unit_price
tolerance = Decimal('0.01')
assert abs(cif_fc - expected_cif) <= tolerance
```

**Or derive it (preferred, simpler):**
```python
# Don't trust client's cif_fc, derive it
unit_price = get_unit_price_for_item(item_id)  # From where?
cif_fc = qty × unit_price
cif_inr = cif_fc × allotment.exchange_rate
```

**Decision needed:** Where does allocate_items get unit_price?
- Option A: From the LicenseItemPlan (if plan_line_id provided)
- Option B: From the AllotmentModel
- Option C: From the request (but then we're back to user-provided)
- Option D: From LicenseImportItemsModel.unit_price (if it has one)

---

## Risk

**Backward compatibility:**
- Existing AllotmentItems rows may have cif_fc values that don't match qty × unit_price
- Changing validation could break existing allocations
- Migration/audit needed to identify mismatches

**Financial correctness:**
- If CIF is derived, no way for user to set a custom price
- If CIF is authoritative, no validation against qty × price mismatch (current state, risky)

**F8 defect (from Module 3):**
- Current implementation trusts client's cif_fc blindly
- Could allow financial manipulation or data-entry errors
- Needs fixing regardless of D2 decision

---

## Recommendation for Phase A

**Implement CIF as DERIVED:**

1. **AllotmentModel:** Keep current (derives cif_fc from unit_value)
2. **LicenseItemPlan:** Keep current (CanonicalPlanningService derives)
3. **AllotmentItems:** 
   - Add validation or derivation step
   - If plan_line_id provided: use LicenseItemPlan.unit_price
   - If not: use AllotmentModel.unit_value_per_unit
   - Derive: cif_fc = qty × unit_price (ROUND_HALF_UP, 2-dp)
   - Validate: assert abs(client_cif_fc - derived_cif_fc) <= 0.01, or use derived value
   - Derive: cif_inr = cif_fc × allotment.exchange_rate (ROUND_HALF_UP, 2-dp)

**This fixes F8 (client-supplied money unvalidated).**

**Unit price source logic:**
```python
if plan_line_id:
    unit_price = LicenseItemPlan.objects.get(id=plan_line_id).unit_price
else:
    unit_price = allotment.unit_value_per_unit
```

**No changes to AllotmentModel or LicenseItemPlan required.**
