# Allotment Allocation Error: ALLOCATION_PAIR_MISMATCH

## Error Details

```json
{
  "code": "ALLOCATION_PAIR_MISMATCH",
  "error": "CIF must equal the canonical unit price multiplied by the allocated quantity.",
  "expected_cif_fc": "20725.26",
  "item_id": 37019
}
```

## The Problem

When allocating items to an allotment with a canonical unit price, the **CIF value must match exactly** the formula:

```
Expected CIF = Quantity × Unit Price
Expected CIF = 4551 × 4.554 = 20725.254 (rounded up to 20725.26)
```

### Your Request
```json
{
  "item_id": 37019,
  "qty": "4551",
  "cif_fc": "20725.25",  // ❌ INCORRECT - off by 0.01
  "unit_value_per_unit": "4.554"
}
```

### The Calculation
```
Expected: 4551 × 4.554 = 20725.254
Rounded UP (ROUND_UP): 20725.26
You sent: 20725.25

Difference: 20725.26 - 20725.25 = -0.01 (0.01 under budget)
```

## Why This Happens

The system uses **ROUND_UP** rounding for canonical CIF calculations to ensure:
- No under-billing in commercial transactions
- Consistency across all allocation pairs with unit prices
- Proper financial accounting

## Solution

Change your request to use the correct CIF value:

```json
{
  "allocations": [
    {
      "item_id": 37019,
      "qty": "4551",
      "cif_fc": "20725.26",  // ✅ CORRECT - matches canonical calculation
      "debit_based_on": "ACTUAL",
      "search_mode": "ACTUAL",
      "allocation_basis": "ACTUAL",
      "license_status": "active",
      "actual_item_id": 168
    }
  ]
}
```

## Key Points

### ✅ When This Validation Applies
- Allotment has a `unit_value_per_unit` (unit price) defined
- You're allocating items with that unit price
- The CIF must match: `Qty × Unit Price` (rounded UP)

### ⚠️ Exceptions (Final Settlement)
There are TWO ways to close out an allotment with a final settlement:

#### Option 1: Exact Match
```
qty == remaining_required_qty  AND  cif_fc == remaining_required_cif
(with <= 0.01 tolerance for one-cent closings)
```

#### Option 2: Whole Unit Close
```
qty == remaining_required_qty  AND  cif_fc == canonical_cif
AND  canonical_cif <= remaining_required_cif + 20.00  ($20 buffer)
```

## Debugging Checklist

1. **Check Unit Price**: Is `unit_value_per_unit` set for this allotment?
   ```
   Your allotment: unit_value_per_unit = 4.554
   ```

2. **Calculate Expected CIF**:
   ```
   Expected = 4551 × 4.554 = 20725.254 → 20725.26 (rounded UP)
   ```

3. **Compare with Submitted CIF**:
   ```
   Expected: 20725.26
   Submitted: 20725.25
   Difference: -0.01
   ```

4. **Verify Quantity**:
   ```
   4551 is correct
   ```

5. **Fix the CIF Value**:
   ```
   Update: cif_fc: "20725.25" → cif_fc: "20725.26"
   ```

## API Response Example

### ❌ Before (Error)
```json
{
  "success": 0,
  "created_items": [],
  "errors": [
    {
      "item_id": 37019,
      "code": "ALLOCATION_PAIR_MISMATCH",
      "error": "CIF must equal the canonical unit price multiplied by the allocated quantity.",
      "expected_cif_fc": "20725.26"
    }
  ]
}
```

### ✅ After (Success)
```json
{
  "success": 1,
  "created_items": [
    {
      "id": <new-item-id>,
      "item_id": 37019,
      "allocation_qty": "4551",
      "allocation_cif_fc": "20725.26"
    }
  ],
  "errors": []
}
```

## Related Validation Rules

The system also validates:

| Code | Condition | Error |
|------|-----------|-------|
| `INVALID_ALLOTMENT_AMOUNT` | qty ≤ 0 OR cif_fc ≤ 0 | Quantity and value must be greater than zero |
| `ALLOTMENT_QTY_EXCEEDS_PLAN` | qty > remaining_planned_qty | Requested allotment exceeds remaining balance |
| `ALLOTMENT_CIF_EXCEEDS_PLAN` | cif_fc > remaining_planned_cif | Requested CIF exceeds remaining balance |
| `NO_PLANNED_QTY_BALANCE` | remaining_plan_qty ≤ 0 | No remaining planned quantity |
| `NO_PLANNED_CIF_BALANCE` | remaining_plan_cif ≤ 0 | No remaining planned CIF value |
| `ALLOCATION_PAIR_MISMATCH` | cif_fc ≠ canonical_cif | CIF must match qty × unit price |

## Quick Fix

**Change this:**
```bash
curl ... --data-raw '{"allocations":[{"item_id":37019,"qty":"4551","cif_fc":"20725.25",...}]}'
```

**To this:**
```bash
curl ... --data-raw '{"allocations":[{"item_id":37019,"qty":"4551","cif_fc":"20725.26",...}]}'
```

---

**Root Cause:** CIF value (20725.25) is 0.01 less than the canonical calculation (4551 × 4.554 = 20725.26)

**Fix:** Update cif_fc from 20725.25 to 20725.26 and retry
