# GATE 3: Financial Number Contract — Global Rules for All Numbers

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Define authoritative, system-wide rules for EVERY financial, quantity, and business-critical number to prevent silent numeric divergence.

**Applies to:** All modules (License, Planning, Allotment, BOE, Invoice, Trade, Reconciliation, Reporting).

---

## GLOBAL RULE: Type

**EVERY financial value MUST use `Decimal` type, NEVER `float`.**

### Why
- Float has rounding errors (0.1 + 0.2 ≠ 0.3 in binary)
- Decimal preserves exact precision (critical for ledgers, tax, duty)
- Database enforces Decimal (DecimalField with max_digits, decimal_places)
- Python's `decimal.Decimal` matches database exactly

### Implementation
```python
# CORRECT
from decimal import Decimal
balance: Decimal = Decimal("1000.50")
total = balance + Decimal("100.25")

# WRONG — Will cause silent drift
balance: float = 1000.50
total = balance + 100.25  # ← Accuracy issues accumulate
```

### Enforcement
- Linter rule: Any `float` variable assigned from a financial calculation is an error
- Code review: Any arithmetic on float values is flagged
- Type hints: Always use `Decimal`, never `float`, in service layer

---

## GLOBAL RULE: Precision (Decimal Places)

**All financial values use THREE precision tiers:**

### Tier 1: Storage Precision (Database)
- **Rule:** Always store with 2 decimal places
- **Schema:** DecimalField(max_digits=..., decimal_places=2)
- **Examples:**
  - License balance: DecimalField(15, 2) → Up to 999,999,999.99
  - BOE CIF: DecimalField(15, 2) → Up to 999,999,999.99
  - Allotment value: DecimalField(15, 2) → Up to 999,999,999.99
- **Guarantee:** No value stored will ever have >2 decimal places
- **Exception:** CIF/FC intermediate fields may use 3 places during calculation (see below)

### Tier 2: Calculation Precision (In-Memory)
- **Rule:** Use full Decimal precision; DO NOT round during intermediate steps
- **Example:**
  ```python
  # CORRECT: Let Decimal maintain full precision
  balance = Decimal("1000.125")  # Allowed in calculation
  allocated = Decimal("300.333")
  remaining = balance - allocated  # = 699.792 (full precision)
  
  # ONLY round at final output
  return remaining.quantize(DECIMAL_2DP, rounding=ROUND_HALF_UP)
  ```
- **Justification:** Rounding during intermediate steps accumulates error
- **Max digits in calculation:** 20 (matches LicenseTradeLine.cif_fc size)

### Tier 3: Display Precision (API/UI/Export)
- **Rule:** Serialize/display with exactly 2 decimal places
- **Format:** "1000.50" (never "1000.5", never "1000.500")
- **Examples:**
  ```python
  # API Serializer
  balance = DecimalField(required=True)  # DRF handles formatting
  
  # Frontend Display
  fmtNum(1000.505)  # → "1000.51" (rounded ROUND_HALF_UP)
  
  # Excel Export
  format_decimal(value, places=2)  # → "1000.50"
  ```

---

## GLOBAL RULE: Rounding

**Default rounding mode for all financial calculations:**

### Rule
```python
rounding=ROUND_HALF_UP
```

### Definition
- 0.5 rounds up (away from zero for positive, toward zero for negative)
- Examples:
  - 1.125 → 1.13
  - 1.124 → 1.12
  - 1.115 → 1.12
  - -1.125 → -1.13 (IMPORTANT: HALF_UP rounds away from zero for negative too)

### When to Apply
| Context | Rounding Point | Rule |
|---------|---|---|
| Calculation intermediate | NEVER round | Use full Decimal |
| Final balance output | ALWAYS round | ROUND_HALF_UP to 2dp |
| Aggregation (SUM) | ALWAYS round final | ROUND_HALF_UP to 2dp |
| Weighted average | ALWAYS round final | ROUND_HALF_UP to 2dp |
| Tax/duty calculation | ALWAYS round final | ROUND_HALF_UP to 2dp |
| Per-unit price | ALWAYS round final | ROUND_HALF_UP to 2dp |

### Implementation
```python
from decimal import Decimal, ROUND_HALF_UP

DECIMAL_2DP = Decimal("0.01")

def quantize_2dp(value: Decimal) -> Decimal:
    """Quantize to 2 decimal places with ROUND_HALF_UP."""
    return to_decimal(value, Decimal("0")).quantize(
        DECIMAL_2DP, 
        rounding=ROUND_HALF_UP
    )

# Every final output uses this
balance = quantize_2dp(calculated_balance)
```

### Special Cases

#### Case 1: Negative Values
- Allowed in balance (over-consumed license)
- Rounding rule is same: ROUND_HALF_UP
- Never floor negative to zero during calculation; only at final display if business rule says so

#### Case 2: Zero
- Exactly `Decimal("0.00")` after quantization
- Never NULL or missing
- Testing: verify `-0.00` does not occur

#### Case 3: Sum of Already-Rounded Values
```python
# WRONG: Rounding twice compounds error
total = quantize_2dp(Decimal("1.125")) + quantize_2dp(Decimal("2.335"))
# ↑ Results in 1.13 + 2.34 = 3.47, but
# ↓ Should be SUM first, then round
total = 1.125 + 2.335  # = 3.46, then quantize to 3.46

# CORRECT
parts = [Decimal("1.125"), Decimal("2.335")]
total = quantize_2dp(sum(parts))  # sum([...]) then round once
```

---

## GLOBAL RULE: Currency Handling

### Single Currency Default
- **Default:** USD (US Dollars)
- **Alternate:** INR (Indian Rupees) — only for specific fields where documented
- **Rule:** If a field stores currency, its name or documentation MUST indicate which

### Currency in Database
```python
class LicenseDetailsModel:
    balance_cif = DecimalField(...)  # Always USD per contract
    balance_inr = DecimalField(...)  # Explicitly INR
    # ↑ Separate fields, no ambiguity

class Invoice:
    amount_usd = DecimalField(...)  # Explicit currency in name
    amount_inr = DecimalField(...)  # Explicit currency in name
```

### Currency in API
```json
{
  "balance": 1000.50,
  "balance_currency": "USD",
  "balance_inr": 83000.00,
  "balance_inr_currency": "INR"
}
```

### Exchange Rate Application
- **Source:** Central `ExchangeRateModel`
- **Application point:** Always at boundary (API intake or export), never mid-calculation
- **Logging:** Log which rate was applied (audit trail)
- **Example:**
  ```python
  # CORRECT: Apply rate at boundary
  usd_amount = Decimal("1000.00")
  rate = ExchangeRateModel.get_current_rate("USD", "INR")
  inr_amount = quantize_2dp(usd_amount * rate.rate)  # Rate applied here
  
  # WRONG: Hidden rate conversion mid-calc
  balance = usd_amount - inr_amount_without_rate_clarity
  ```

---

## GLOBAL RULE: Quantity vs. Financial Separation

**These are DIFFERENT units. NEVER mix without explicit conversion.**

### Quantity (Physical Units)
- Measured in: KG, MT, LTR, PCS, etc.
- Type: Decimal (same precision rules)
- Storage: DecimalField(15, 2)
- Examples:
  - LicenseImportItem.quantity (KG)
  - AllotmentItems.quantity (KG or per-norm unit)
  - RowDetails.quantity (KG or per-norm unit)

### Financial (Currency)
- Measured in: USD, INR, etc.
- Type: Decimal (same precision rules)
- Storage: DecimalField(15, 2)
- Examples:
  - LicenseExportItem.cif_fc (USD)
  - RowDetails.cif_fc (USD)
  - Invoice.amount (USD)

### Conversion: Quantity ↔ Financial
- **Only via:** SION Norm Unit Price
- **Rule:** Never invent a conversion rate
- **Example:**
  ```python
  # CORRECT: SION norm defines price/unit
  quantity_kg = Decimal("100.00")
  unit_price = SionNormNote.get_unit_price()  # e.g., Decimal("1000.00") per KG
  cif_usd = quantize_2dp(quantity_kg * unit_price)
  
  # WRONG: Making up a conversion
  cif_usd = quantity_kg * 10  # ← Arbitrary conversion rate
  ```

---

## GLOBAL RULE: NULL Handling

### Financial Values (Always Non-NULL)
```python
# WRONG
balance = None  # ← Invalid

# CORRECT
balance = Decimal("0.00")  # Zero is valid; NULL is not
```

### Quantity Values (Always Non-NULL)
```python
# WRONG
quantity = None  # ← Invalid

# CORRECT
quantity = Decimal("0.00")  # Zero is valid; NULL is not
```

### Optional Related Fields (Can be NULL)
```python
# Allowed to be NULL (business context, not calculation)
company = None  # Not all transactions are company-specific
supplier_id = None  # May be unknown for some BOEs
```

### Aggregation Handling
```python
# Handle NULL correctly in aggregates
from django.db.models import Coalesce, Sum

# CORRECT: Coalesce NULL to zero
total = MyModel.objects.aggregate(
    total=Coalesce(Sum("balance"), Value(Decimal("0")), output_field=DecimalField())
)["total"]

# WRONG: Allowing NULL to propagate
total = MyModel.objects.aggregate(Sum("balance"))["balance"]  # ← Could be None
```

---

## GLOBAL RULE: Zero Handling

| Scenario | Valid? | Example | Business Logic |
|----------|--------|---------|-----------------|
| Zero balance | ✅ YES | Decimal("0.00") | License fully consumed |
| Zero quantity | ✅ YES | Decimal("0.00") | Item not allocated |
| Zero amount | ✅ YES | Decimal("0.00") | No transactions |
| Zero plan cap | ✅ YES | Decimal("0.00") | Item cannot be planned |
| Zero allocation | ✅ YES | Decimal("0.00") | Allotment not filled |

### Testing
- Every calculation must test zero input → zero output
- Every aggregate must test empty set → zero output
- Every boundary must handle zero gracefully

---

## GLOBAL RULE: Negative Values

### Allowed
- **Negative balance:** Yes (overuse detected, flagged separately)
- **Negative quantity:** No (catch at API level; should never exist in DB)
- **Negative CIF:** No (catch at entry; should never exist in DB)
- **Negative exchange rate:** No (catch at entry)

### Handling
```python
def validate_quantity(value: Decimal) -> None:
    if value < Decimal("0"):
        raise ValidationError("Quantity cannot be negative")

def validate_price(value: Decimal) -> None:
    if value < Decimal("0"):
        raise ValidationError("Price cannot be negative")

# But negative balance is OK
balance = calculate_balance()  # Can be negative (overuse)
if balance < Decimal("0"):
    mark_as_overused()  # Flag, don't error
```

---

## GLOBAL RULE: Aggregation

### Sum of Balances
- ✅ Valid if all in same scope (all licenses, all items)
- ❌ Invalid if mixed scopes (license-level + item-level)
- ✅ Test: SUM(L1_balance) + SUM(L2_balance) ≠ SUM(all balances) if overlapping

### Sum of Different Units
- ❌ INVALID: Never sum USD + KG
- ❌ INVALID: Never sum per-company totals without re-grouping
- ✅ Valid: SUM(all item quantities in same unit) per item
- ✅ Valid: SUM(all item CIFs) grouped by unit

### Weighted Average
- **Formula:** (SUM qty × price) / SUM qty
- **Example:** Blended unit price per license item
- **Rounding:** Apply ROUND_HALF_UP to final result only
- **Test:** Verify low/high/edge weights don't drift

### Counting vs. Summing
- **Separate operations:** COUNT(rows) is not SUM(values)
- **Example:**
  ```python
  # Wrong: mixing operations
  total = COUNT(*) + SUM(balance)  # ← Incompatible units
  
  # Correct: keep separate
  row_count = COUNT(*)
  balance_total = SUM(balance)
  ```

---

## Migration Checklist (for Gate 4)

Before any financial calculation goes live:

- [ ] Type: All Decimal, no float
- [ ] Precision: Stored with 2 decimal places in DB
- [ ] Calculation: Full Decimal precision in-memory, no intermediate rounding
- [ ] Rounding: ROUND_HALF_UP to 2dp at output boundary
- [ ] Currency: Explicit USD/INR, no ambiguity
- [ ] Unit separation: No mixing quantity and financial units
- [ ] NULL handling: No NULL in financial values, use Decimal("0")
- [ ] Zero handling: Tested with zero inputs
- [ ] Negative handling: Validated against business rules
- [ ] Aggregation: Verified correct scope and unit mixing
- [ ] Test coverage: Golden dataset with edge cases (zero, max, negative, missing)

---

## Numeric Type Standards by Module

| Module | Field | Type | Storage | Calculation | Display | Notes |
|--------|-------|------|---------|-------------|---------|-------|
| License | balance_cif | Decimal | 15,2 | Full (3dp) | 2dp | Per balance_calculator.py |
| License | cif_fc (export) | Decimal | 15,2 | Full (3dp) | 2dp | Source data, no calc |
| BOE | cif_fc (debit) | Decimal | 15,2 | Full (3dp) | 2dp | Source data, no calc |
| Allotment | cif_fc | Decimal | 15,2 | Full (3dp) | 2dp | Derived from unit price × qty |
| Allotment | quantity | Decimal | 15,2 | Full (3dp) | 2dp | Item unit (KG/MT/LTR/etc.) |
| Plan | planned_cif | Decimal | 15,2 | Full (3dp) | 2dp | Norm-derived value |
| Invoice | cif | Decimal | 15,2 | Full (3dp) | 2dp | Source data, no calc |
| Trade | cif_fc | Decimal | 20,2 | Full (3dp) | 2dp | Larger due to line aggregation |
| Exchange Rate | rate | Decimal | 10,6 | Full precision | 6dp | Special precision for rates |

---

## Code Example: Correct Implementation

```python
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Decimal as DecimalField

# Service layer (calculate)
class LicenseBalanceCalculator:
    @staticmethod
    def calculate_balance(license_id: int) -> Decimal:
        """Calculate balance with full precision, round at output."""
        # Gather source data (Decimal from DB)
        export_total = fetch_export_total(license_id)  # Decimal
        debit_total = fetch_debit_total(license_id)    # Decimal
        
        # Calculate with full precision (no rounding)
        balance = export_total - debit_total  # Full Decimal precision
        
        # Round ONLY at output boundary
        return quantize_2dp(balance)

# Serializer layer (output to API)
class LicenseSerializer:
    balance = DecimalField(max_digits=15, decimal_places=2)
    # DRF handles formatting to 2dp in JSON

# Frontend layer (display)
export function formatBalance(balance: Decimal): string {
  return fmtNum(balance);  // Ensures 2dp display
}
```

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Compliance:** Mandatory for all new financial calculations
- **Enforcement:** Code review, linter rules, type hints
- **Next Update:** Post-approval, when implementation begins
