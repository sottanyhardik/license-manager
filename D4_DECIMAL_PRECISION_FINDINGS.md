# D4 FINDINGS: Decimal Precision Alignment

## Current Precision Definitions

| Field Type | Model | Precision | Rounding |
|---|---|---|---|
| **Quantity** | LicenseImportItemsModel | 15, 3 (0.001) | ROUND_HALF_UP |
| **Quantity** | LicenseItemPlan.planned_quantity | 15, 3 | ROUND_HALF_UP |
| **Quantity** | LicenseItemPlan.remaining_quantity | 15, 3 | ROUND_HALF_UP |
| **Quantity** | AllotmentItems.qty | 15, 3 | ROUND_HALF_UP |
| **Unit Price** | AllotmentModel.unit_value_per_unit | 15, 3 | ROUND_UP (unusual) |
| **Unit Price** | LicenseItemPlan.unit_price | 15, 2 | ROUND_HALF_UP |
| **CIF** | AllotmentModel.cif_fc | 15, 2 | ROUND_HALF_UP |
| **CIF** | LicenseItemPlan.planned_cif_fc | 15, 2 | ROUND_HALF_UP |
| **CIF** | LicenseItemPlan.remaining_cif_fc | 15, 2 | ROUND_HALF_UP |
| **CIF** | AllotmentItems.cif_fc | 15, 2 | ROUND_HALF_UP |
| **CIF INR** | AllotmentModel.cif_inr | 15, 2 | ROUND_HALF_UP |
| **Exchange Rate** | AllotmentModel.exchange_rate | 15, 6 | N/A |
| **Balance** | LicenseImportItemsModel.available_quantity | 15, 3 | Varies |

---

## Current Rounding Functions

**File:** backend/apps/core/utils/decimal_utils.py

```python
def round_decimal(dec_value, decimal_places, rounding=ROUND_HALF_UP):
    """Generic rounding utility"""
    return dec_value.quantize(..., rounding=rounding)

def round_decimal_down(dec_value, decimal_places):
    """Round DOWN to prevent overcommit"""
    return dec_value.quantize(..., rounding=ROUND_FLOOR)
```

**Used in:**
- AllotmentModel.save() — uses ROUND_HALF_UP
- calculate_balance.py — uses `round_down()` for available_value, `round()` for others
- CanonicalPlanningService — uses ROUND_HALF_UP

**Finding:** Inconsistent rounding:
- Most calculations use ROUND_HALF_UP
- Balance availability uses ROUND_FLOOR (down)
- Derivations inconsistent

---

## Database Precision

**Quantity columns:** decimal_places=3
- Allows 0.001 precision (e.g., 100.123 kg)
- Database enforces this constraint

**CIF/Price columns:** decimal_places=2
- Allows 0.01 precision (e.g., 100.25 USD)
- Database enforces this constraint

**Inconsistency:** unit_value_per_unit is 3-dp while unit_price is 2-dp.

---

## Frontend Precision

**JavaScript number handling:**
- JSON serializes Decimal as string (safe)
- Frontend parses as parseFloat (limited precision)
- Input fields may allow arbitrary decimals (no validation)

**No frontend precision enforcement currently.**

---

## Potential Balance-Creep Scenarios

### Scenario 1: qty(3-dp) × price(2-dp) rounding
```
qty = 10.123
price = 1.50

Expected CIF = 10.123 × 1.50 = 15.1845
Rounded (HALF_UP, 2-dp) = 15.18

But: 10.123 × 1.50 = 15.1845 → rounds down to 15.18 (loss of 0.0045)
Or: rounds up to 15.19 (gain of 0.0055)
```

**Impact:** Small discrepancies accumulate across many allocations.

### Scenario 2: Derived unit_price from CIF and qty
```
cif_fc = 100.00 (given)
qty = 33.333 (3-dp)

unit_price = 100.00 / 33.333 = 3.00030003...
Rounded (HALF_UP, 2-dp) = 3.00

Verify: 33.333 × 3.00 = 99.999 ≠ 100.00 (loss of 0.01)
```

**Impact:** Derived unit prices don't reconcile back to CIF.

### Scenario 3: Balance update with float arithmetic
```
# From calculate_balance.py: uses to_float(), round()
balance = round(credit - debited - allotted, 2)
```

**Impact:** Float has 15-17 significant digits. For large numbers, rounding errors accumulate.

---

## Recommended Canonical Rule

**Single rule for all calculations:**

```python
# Rule: Quantity × Unit Price = CIF (ALWAYS)
cif = (qty * unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Verification: CIF must round correctly
# No manual unit_price adjustment; derive and accept the result
```

**Precision:**
- Quantities: keep 3-dp (0.001)
- Prices: standardize to 2-dp (0.01)
- CIF: 2-dp (0.01)
- Exchange rates: 6-dp as-is

**Rounding:**
- **ROUND_HALF_UP** for all normal calculations
- **ROUND_DOWN** only for ceilings/availability (to prevent overcommit)

**Changes needed:**
1. Change AllotmentModel.unit_value_per_unit to 2-dp (not 3-dp)
2. Consistent ROUND_HALF_UP everywhere except availability
3. Use Decimal throughout (avoid float in calculate_balance.py)
4. Add validation: assert cif == qty × price (within 0.01 tolerance)

---

## Affected Models/Services

**Models requiring migration:**
- AllotmentModel.unit_value_per_unit: change from 3-dp to 2-dp

**Services requiring update:**
- calculate_balance.py: replace float with Decimal
- CanonicalPlanningService: already correct (ROUND_HALF_UP)
- allocate_items: add cif validation (Req 8 fix)

**No changes needed:**
- LicenseItemPlan (already 2-dp, ROUND_HALF_UP)
- LicenseImportItemsModel (qty is 3-dp, correct)

---

## Risk

**Backward compatibility:**
- Existing AllotmentModel rows with 3-dp unit_value_per_unit would be truncated/rounded
- May change existing CIF calculations
- Migration must audit impact on existing allocations

**Financial impact:**
- Changing precision could alter existing balance calculations
- May discover balance discrepancies (hidden by current rounding)
- Requires careful migration and audit

---

## Recommendation for Phase A

**Implement canonical rule:**

1. **Quantity × Unit Price = CIF (always)**
   - Standardize unit_price to 2-dp (migrate AllotmentModel.unit_value_per_unit)
   - Use ROUND_HALF_UP consistently
   - Add validation in allocate_items (D2 fix)

2. **Availability ceiling uses ROUND_DOWN**
   - Prevents overcommit
   - Keep existing calculate_balance.py logic

3. **Use Decimal throughout**
   - Replace float in calculate_balance.py
   - Prevent precision loss

4. **Migration for AllotmentModel.unit_value_per_unit**
   - Change precision from 3-dp to 2-dp
   - Backfill existing rows (round existing values)
   - Audit impact on existing allocations

**This fixes F10 (float arithmetic, silent failures) and establishes single canonical rule.**

No changes to LicenseItemPlan required.
