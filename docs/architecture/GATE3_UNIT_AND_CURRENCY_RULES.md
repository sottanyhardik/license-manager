# GATE 3: Unit and Currency Rules

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Define authoritative units for every quantity and financial field so no conversion ever happens silently or incorrectly.

---

## Base Units (Defined Once, Used Everywhere)

### Financial Units

```python
UNIT_USD = "USD"        # US Dollars (default)
UNIT_INR = "INR"        # Indian Rupees (specific cases only)
UNIT_CIF = "USD"        # Cost, Insurance, Freight value (always USD)
```

### Physical Quantity Units

```python
UNIT_KG = "KG"          # Kilogram (most common)
UNIT_MT = "MT"          # Metric Tonne (1000 KG)
UNIT_LTR = "LTR"        # Liter (volume)
UNIT_PCS = "PCS"        # Pieces (discrete items)
UNIT_PERCENT = "%"      # Percentage (for restrictions, plan %)
UNIT_ABSTRACT = ""      # No unit (dimensionless)
```

### Central Definition Location

**File:** `backend/apps/core/constants.py`

```python
# Unit definitions (SINGLE SOURCE OF TRUTH)
UNIT_CODES = {
    "KG": {"label": "Kilogram", "abbr": "kg", "type": "mass"},
    "MT": {"label": "Metric Tonne", "abbr": "mt", "type": "mass", "conversion_to_kg": 1000},
    "LTR": {"label": "Liter", "abbr": "ltr", "type": "volume"},
    "PCS": {"label": "Pieces", "abbr": "pcs", "type": "discrete"},
    "USD": {"label": "US Dollar", "abbr": "$", "type": "currency"},
    "INR": {"label": "Indian Rupee", "abbr": "₹", "type": "currency"},
}
```

---

## SION Norm Unit Pricing (Master Data)

**Authority:** SION norms (DGFT regulatory data, imported into `SionNormClassModel`, `SionNormNote`, etc.)

### Contract

Every SION norm defines:

```python
class SionNormNote:
    norm_class = ForeignKey(SionNormClass)  # E.g., "E1"
    unit_type = CharField()                  # E.g., "KG" (must match UNIT_CODES)
    unit_price = DecimalField()             # E.g., Decimal("1000.00") per unit
    effective_from = DateField()            # Rate validity window
    effective_to = DateField()
    percentage = DecimalField()             # Plan percentage (e.g., 0.02 for 2%)
```

### Rule: Never Invent Conversions

```python
# WRONG: Custom conversion rate invented mid-code
kg_to_usd_rate = 10.5  # ← No source, arbitrary
cif_usd = quantity_kg * kg_to_usd_rate

# CORRECT: Use SION norm unit price
unit_price = SionNormNote.objects.get(
    norm_class="E1", 
    effective_from__lte=today, 
    effective_to__gte=today
).unit_price
cif_usd = quantity_kg * unit_price
```

---

## Currency Affinity Rules

### By Field Type

| Field Type | Default Currency | Override Allowed | Example |
|---|---|---|---|
| Balance (financial) | USD | Only for historical INR data | LicenseBalance.balance_cif = USD |
| CIF (Cost, Insurance, Freight) | USD | No | RowDetails.cif_fc = USD |
| Unit Price | USD | No | SionNormNote.unit_price = USD per KG |
| Exchange Rate | N/A (pair) | No | ExchangeRateModel(from_usd_to_inr) |
| Duty/Tax | Same as parent | No | If parent is USD, duty is USD |

### By Module

| Module | Currency | Justification |
|---|---|---|
| License | USD | All balances in USD; SION prices in USD |
| Planning | USD | Plan CIF is USD |
| Allotment | USD | CIF values are USD |
| BOE | USD | CIF debit is USD |
| Invoice | USD | Invoices are USD unless explicitly marked INR |
| Trade | USD | SALE trades in USD |
| Reconciliation | USD | Matching against USD values |

---

## Quantity Unit Scoping

### By SION Norm Class

| Norm Class | Unit | Authority | Scope |
|---|---|---|---|
| E1 (Petroleum Products) | KG or LTR | SionNormClass | Per item, fixed for E1 items |
| E5 (Agricultural Products) | KG | SionNormClass | Per item, fixed for E5 items |
| E132 (Dairy Products) | KG | SionNormClass | Per item, fixed for E132 items |
| A3627 | KG | SionNormClass | Per item, fixed for A3627 items |
| (Custom/Non-SION) | PCS or KG | Manual assignment | Custom norms assigned by admin |

### Rule: Unit is Immutable Once Set

Once a SION norm class is assigned to an item, its unit is fixed:

```python
class LicenseImportItem:
    norm_class = ForeignKey(SionNormClass)  # Determines unit
    quantity = DecimalField()               # ALWAYS in norm_class.unit
    # ↓ quantity is ALWAYS in KG if E1, LTR if some E1 items, etc.
    # ↓ Never mix units on same item
```

**Consequence:** Database integrity rule — if `norm_class` changes, `quantity` must NOT change value, only interpretation.

---

## Exchange Rate Application

### Source of Truth

```python
class ExchangeRateModel:
    from_currency = CharField()         # "USD"
    to_currency = CharField()           # "INR"
    rate = DecimalField()               # E.g., Decimal("83.50")
    effective_from = DateField()
    effective_to = DateField()
    source = CharField()                # E.g., "RBI", "DGFT", "manual"
```

### Application Point Rule

**Exchange rate conversion happens ONLY at system boundaries (API intake or export), NEVER mid-calculation.**

```python
# CORRECT: Apply at boundary
def get_license_balance_inr(license_id):
    # Get USD balance
    balance_usd = LicenseBalanceCalculator.calculate_balance(license_id)
    
    # Apply rate ONLY at output boundary
    rate = ExchangeRateModel.get_current_rate("USD", "INR")
    balance_inr = quantize_2dp(balance_usd * rate.rate)
    
    return balance_inr

# WRONG: Conversion hidden in mid-calculation
def calculate_balance_mixed(license_id):
    export_total_usd = fetch_export_total(license_id)
    
    # ✗ Convert mid-calc without logging
    export_total_inr = export_total_usd * Decimal("83.50")
    
    # ✗ Balance is now a mix of USD and INR
    balance = export_total_inr - fetch_debit_total(license_id)  # WRONG
```

### Audit Trail

Every rate application must log:
```python
import logging

logger = logging.getLogger(__name__)

rate = ExchangeRateModel.get_current_rate("USD", "INR")
logger.info(f"Applied USD->INR rate {rate.rate} effective {rate.effective_from}")

balance_inr = balance_usd * rate.rate
```

---

## Unit Conversion Rules (When Needed)

### Allowed Conversions

Only these conversions are allowed:

| From | To | Formula | Authority | When |
|---|---|---|---|---|
| KG | MT | ÷ 1000 | SION (fixed ratio) | For display purposes only |
| MT | KG | × 1000 | SION (fixed ratio) | For display purposes only |
| USD | INR | × current rate | ExchangeRateModel | At output boundary |
| INR | USD | ÷ current rate | ExchangeRateModel | At input boundary |

### Forbidden Conversions

These are NEVER allowed:
- KG ↔ LTR (different dimension, no conversion formula)
- KG ↔ PCS (different dimension, no conversion formula)
- USD ↔ KG (currency ↔ quantity, never mix)
- Any custom rate not in ExchangeRateModel

### Implementation

```python
# Define conversions once
UNIT_CONVERSIONS = {
    ("KG", "MT"): Decimal("0.001"),  # KG / 1000 = MT
    ("MT", "KG"): Decimal("1000"),   # MT * 1000 = KG
    # NO cross-domain conversions
}

def convert_unit(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert between compatible units."""
    if (from_unit, to_unit) not in UNIT_CONVERSIONS:
        raise ValueError(f"Conversion {from_unit} -> {to_unit} not allowed")
    
    factor = UNIT_CONVERSIONS[(from_unit, to_unit)]
    return quantize_2dp(value * factor)
```

---

## Field-to-Unit Mapping

### Backend

| Model.Field | Unit | Authority | Notes |
|---|---|---|---|
| LicenseExportItem.cif_fc | USD | SION/import | Always USD |
| LicenseImportItem.quantity | Item's norm unit | SION norm class | KG for E1, E5, E132, A3627 |
| LicenseImportItem.available_quantity | Item's norm unit | Derived from quantity | Same unit as quantity |
| RowDetails.cif_fc | USD | BOE import | Always USD |
| RowDetails.quantity | Item's norm unit | BOE data | Same unit as item |
| AllotmentItems.quantity | Item's norm unit | Allotment data | Same unit as item |
| AllotmentItems.cif_fc | USD | Calculated | Unit price × quantity |
| LicenseItemPlan.planned_quantity | Item's norm unit | Plan data | Same unit as item |
| LicenseItemPlan.planned_cif_fc | USD | Calculated | Norm unit price × planned qty |
| InvoiceItem.cif | USD | Invoice | Always USD |
| LicenseTradeLine.cif_fc | USD | Trade | Always USD |
| SionNormNote.unit_price | USD per norm unit | SION master | E.g., USD/KG |
| ExchangeRateModel.rate | Decimal ratio | Rate master | E.g., INR per USD |

### Frontend

| Component | Display Unit | Authority | Notes |
|---|---|---|---|
| Item Pivot Report balance column | USD | Backend API | No conversion |
| Item Pivot Report qty column | Norm unit + label | Backend API | E.g., "100 KG" |
| License Ledger balance column | USD | Backend API | No conversion |
| Invoice Report amount | USD | Backend API | No conversion |
| Available Items quantity filter | Norm unit | Backend API | User enters unit of item |

---

## API Contract (Request/Response)

### Balance Request (GET /license/{id}/balance)

**Response:**
```json
{
  "balance": "1000.50",           // USD, 2dp, string to avoid float loss
  "balance_unit": "USD",          // Explicit unit
  "available": "500.25",          // USD, 2dp
  "allocated": "500.25"           // USD, 2dp
}
```

### Item Quantity Request (GET /license/{id}/items)

**Response:**
```json
{
  "items": [
    {
      "id": 123,
      "quantity": "100.00",       // 2dp, in item's norm unit
      "quantity_unit": "KG",      // Explicit unit from SION norm
      "available": "50.00",       // Same unit as quantity
      "available_unit": "KG"
    }
  ]
}
```

### Rate Request (GET /rates/usd-to-inr)

**Response:**
```json
{
  "from_currency": "USD",
  "to_currency": "INR",
  "rate": "83.50",               // 6dp for rates (higher precision)
  "rate_unit": "INR/USD",        // Explicit unit
  "effective_from": "2026-01-01",
  "effective_to": "2026-12-31",
  "source": "RBI"
}
```

---

## Migration Checklist (for Gate 4)

Before any calculation using units goes live:

- [ ] Unit authority identified (SION norm, master data, or constant)
- [ ] Unit is immutable (not changed mid-calculation)
- [ ] No arbitrary conversion rates invented
- [ ] Exchange rates applied only at boundary
- [ ] All financial values default to USD (no ambiguity)
- [ ] All quantity values explicitly labeled with unit in API
- [ ] Cross-unit checks prevent mixing (e.g., KG + LTR)
- [ ] Audit logging for every rate application
- [ ] Test coverage: conversions, missing rates, invalid units

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Compliance:** Mandatory for all calculations involving units or exchange
- **Next Update:** Post-approval, when implementation begins
